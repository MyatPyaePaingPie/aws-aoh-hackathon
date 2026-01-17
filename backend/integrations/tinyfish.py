"""
tinyfish.py - TinyFish AgentQL integration for pattern extraction

Provides structured data extraction from text using AgentQL's REST API.
Used by HoneyAgent to extract attacker patterns from conversation transcripts.

Owner: Agents Track (Aria)

Design:
    1. Wrap text in minimal HTML for AgentQL processing
    2. Use custom query schema to extract threat indicators
    3. Fall back to regex extraction on any API failure
    4. Never raise exceptions - always return useful data

The demo cannot crash. This module always returns valid extracted patterns.
"""

import json
import os
import re
from typing import Any

import httpx

# ============================================================
# CONFIGURATION
# ============================================================

AGENTQL_ENDPOINT = "https://api.agentql.com/v1/query-data"
AGENTQL_API_KEY = os.environ.get("TINYFISH_API_KEY", "")

# Request timeout in seconds
REQUEST_TIMEOUT = 10.0

# AgentQL query schema for threat pattern extraction
PATTERN_EXTRACTION_QUERY = """
{
  attacker_intent
  targets[]
  techniques[]
  indicators_of_compromise[]
  threat_level
  confidence_score
}
"""

# Natural language prompt alternative (used when query fails)
PATTERN_EXTRACTION_PROMPT = """
Analyze this conversation transcript from a security honeypot.
Extract:
1. The attacker's intent (credential_theft, reconnaissance, lateral_movement, privilege_escalation, data_exfiltration, or unknown)
2. Any targets mentioned (systems, databases, credentials, admin access, etc.)
3. Techniques used (social_engineering, pretexting, authority_impersonation, urgency_tactics, etc.)
4. Indicators of compromise (domains, IPs, tool names, file paths mentioned)
5. Threat level (critical, high, medium, low)
6. Your confidence score (0.0 to 1.0)
"""


# ============================================================
# FALLBACK PATTERNS (regex-based extraction)
# ============================================================

# Intent detection patterns
INTENT_PATTERNS = {
    "credential_theft": [
        r"\b(password|credential|secret|api.?key|token|auth|login)\b",
        r"\b(give me|send me|share|access to)\b.*\b(cred|pass|key)\b",
    ],
    "reconnaissance": [
        r"\b(what (systems?|services?|tools?)|how does|architecture|setup)\b",
        r"\b(tell me about|describe|explain)\b.*\b(system|network|infra)\b",
    ],
    "lateral_movement": [
        r"\b(other (systems?|servers?|services?)|access to|connect to)\b",
        r"\b(can you reach|do you have access|internal)\b",
    ],
    "privilege_escalation": [
        r"\b(admin|root|elevated|sudo|superuser|privilege)\b",
        r"\b(bypass|override|escalate|higher.?level)\b",
    ],
    "data_exfiltration": [
        r"\b(export|download|dump|extract|copy)\b.*\b(data|records|files)\b",
        r"\b(customer|user|sensitive)\b.*\b(data|info|records)\b",
    ],
}

# Technique detection patterns
TECHNIQUE_PATTERNS = {
    "social_engineering": [
        r"\b(urgent|asap|immediately|critical|emergency)\b",
        r"\b(trust me|between us|don't tell|quietly)\b",
    ],
    "pretexting": [
        r"\b(i('m| am) (from|with|part of)|on behalf of|sent by)\b",
        r"\b(new (here|team member|employee)|just (started|joined))\b",
    ],
    "authority_impersonation": [
        r"\b(ceo|cto|manager|director|executive|boss|leadership)\b",
        r"\b((asked|told) me to|authorized|approved)\b",
    ],
    "urgency_tactics": [
        r"\b(deadline|time.?sensitive|right now|asap|hurry)\b",
        r"\b(can't wait|no time|quickly|fast)\b",
    ],
}

# Target extraction patterns
TARGET_PATTERNS = [
    r"\b(database|db|postgres|mysql|mongo|redis)\b",
    r"\b(aws|s3|ec2|lambda|azure|gcp)\b",
    r"\b(admin|root|super.?user)\s*(access|account|panel)\b",
    r"\b(api|endpoint|service|server)\b",
    r"\b(customer|user|client)\s*(data|records|info)\b",
    r"\b(production|prod|staging|internal)\b",
]

# IOC patterns
IOC_PATTERNS = [
    r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b",  # IP addresses
    r"\b([a-zA-Z0-9-]+\.(com|net|org|io|dev|xyz|ru|cn))\b",  # Domains
    r"\b(nc|ncat|netcat|nmap|metasploit|cobalt.?strike|mimikatz)\b",  # Tools
    r"[/\\](?:etc|var|tmp|home|root|windows)[/\\][^\s]+",  # File paths
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _wrap_in_html(text: str) -> str:
    """Wrap text content in minimal HTML for AgentQL processing."""
    # Escape HTML special characters
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    return f"""<!DOCTYPE html>
<html>
<head><title>Conversation Transcript</title></head>
<body>
<div class="transcript">
{escaped}
</div>
</body>
</html>"""


def _extract_patterns_regex(text: str) -> dict[str, Any]:
    """
    Extract attacker patterns using regex-based analysis.

    This is the fallback when AgentQL is unavailable.
    Always returns a valid result.
    """
    text_lower = text.lower()

    # Detect intent
    detected_intent = "unknown"
    intent_confidence = 0.0
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected_intent = intent
                intent_confidence = 0.7
                break
        if detected_intent != "unknown":
            break

    # Detect techniques
    detected_techniques = []
    for technique, patterns in TECHNIQUE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected_techniques.append(technique)
                break

    # Extract targets
    detected_targets = []
    for pattern in TARGET_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            target = match if isinstance(match, str) else match[0]
            if target and target not in detected_targets:
                detected_targets.append(target)

    # Extract IOCs
    detected_iocs = []
    for pattern in IOC_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            ioc = match if isinstance(match, str) else match[0]
            if ioc and ioc not in detected_iocs:
                detected_iocs.append(ioc)

    # Determine threat level
    threat_level = "low"
    if detected_intent in ["credential_theft", "data_exfiltration"]:
        threat_level = "high"
    elif detected_intent in ["privilege_escalation", "lateral_movement"]:
        threat_level = "high"
    elif detected_intent == "reconnaissance":
        threat_level = "medium"

    if "authority_impersonation" in detected_techniques:
        threat_level = "high"
    if detected_iocs:
        threat_level = "critical" if threat_level == "high" else "high"

    # Calculate confidence
    confidence = intent_confidence
    if detected_techniques:
        confidence = min(confidence + 0.1 * len(detected_techniques), 0.95)
    if detected_targets:
        confidence = min(confidence + 0.05 * len(detected_targets), 0.95)
    if not confidence:
        confidence = 0.3  # Minimum confidence for fallback

    return {
        "intent": detected_intent,
        "targets": detected_targets[:5],  # Limit to 5
        "techniques": detected_techniques[:5],
        "indicators_of_compromise": detected_iocs[:10],
        "threat_level": threat_level,
        "confidence": round(confidence, 2),
        "extraction_method": "regex_fallback",
    }


def _get_hardcoded_fallback() -> dict[str, Any]:
    """
    Return hardcoded fallback matching config/fallbacks.yaml.

    Used when both AgentQL and regex extraction fail.
    """
    return {
        "intent": "credential_theft",
        "targets": ["database", "admin_access"],
        "techniques": ["social_engineering", "authority_impersonation"],
        "indicators_of_compromise": [],
        "threat_level": "high",
        "confidence": 0.5,
        "extraction_method": "hardcoded_fallback",
    }


# ============================================================
# AGENTQL API FUNCTIONS
# ============================================================


async def extract_patterns_agentql(text: str) -> dict[str, Any]:
    """
    Extract attacker patterns using AgentQL REST API.

    Wraps text in HTML and sends to AgentQL for semantic extraction.
    Falls back to regex extraction on any failure.

    Args:
        text: Conversation transcript or message to analyze

    Returns:
        Dictionary containing extracted patterns:
        - intent: credential_theft, reconnaissance, etc.
        - targets: list of mentioned targets
        - techniques: list of techniques used
        - indicators_of_compromise: list of IOCs
        - threat_level: critical, high, medium, low
        - confidence: 0.0 to 1.0
        - extraction_method: agentql, regex_fallback, or hardcoded_fallback
    """
    # Check if API key is configured
    if not AGENTQL_API_KEY:
        return _extract_patterns_regex(text)

    try:
        html_content = _wrap_in_html(text)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                AGENTQL_ENDPOINT,
                headers={
                    "X-API-Key": AGENTQL_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "html": html_content,
                    "query": PATTERN_EXTRACTION_QUERY,
                },
            )

            if response.status_code != 200:
                # API error - fall back to regex
                return _extract_patterns_regex(text)

            result = response.json()
            data = result.get("data", {})

            # Normalize and validate response
            return {
                "intent": data.get("attacker_intent", "unknown") or "unknown",
                "targets": data.get("targets", []) or [],
                "techniques": data.get("techniques", []) or [],
                "indicators_of_compromise": data.get("indicators_of_compromise", []) or [],
                "threat_level": data.get("threat_level", "medium") or "medium",
                "confidence": float(data.get("confidence_score", 0.8) or 0.8),
                "extraction_method": "agentql",
            }

    except httpx.TimeoutException:
        # Timeout - fall back to regex
        return _extract_patterns_regex(text)
    except httpx.RequestError:
        # Network error - fall back to regex
        return _extract_patterns_regex(text)
    except json.JSONDecodeError:
        # Invalid JSON response - fall back to regex
        return _extract_patterns_regex(text)
    except Exception:
        # Any other error - fall back to regex
        return _extract_patterns_regex(text)


def extract_patterns_sync(text: str) -> dict[str, Any]:
    """
    Synchronous version of pattern extraction.

    Uses regex-based extraction directly (no async overhead).
    Suitable for use in synchronous contexts.

    Args:
        text: Conversation transcript or message to analyze

    Returns:
        Same format as extract_patterns_agentql
    """
    try:
        return _extract_patterns_regex(text)
    except Exception:
        return _get_hardcoded_fallback()


# ============================================================
# UTILITY FUNCTIONS
# ============================================================


def map_intent_to_mitre(intent: str) -> str:
    """
    Map detected intent to MITRE ATT&CK technique ID.

    Args:
        intent: Detected attacker intent

    Returns:
        MITRE ATT&CK technique ID
    """
    mapping = {
        "credential_theft": "T1552.001",  # Unsecured Credentials
        "reconnaissance": "T1592",  # Gather Victim Host Information
        "lateral_movement": "T1021",  # Remote Services
        "privilege_escalation": "T1078.003",  # Valid Accounts: Local Accounts
        "data_exfiltration": "T1020",  # Automated Exfiltration
        "unknown": "T1595",  # Active Scanning (generic)
    }
    return mapping.get(intent, "T1595")


def calculate_risk_score(patterns: dict[str, Any]) -> float:
    """
    Calculate numeric risk score from extracted patterns.

    Args:
        patterns: Extracted pattern dictionary

    Returns:
        Risk score from 0.0 to 10.0
    """
    base_score = {
        "critical": 9.0,
        "high": 7.0,
        "medium": 5.0,
        "low": 3.0,
    }.get(patterns.get("threat_level", "low"), 3.0)

    # Adjust for confidence
    confidence = patterns.get("confidence", 0.5)
    adjusted = base_score * confidence

    # Bonus for IOCs
    iocs = patterns.get("indicators_of_compromise", [])
    if iocs:
        adjusted = min(adjusted + 0.5 * len(iocs), 10.0)

    return round(adjusted, 1)
