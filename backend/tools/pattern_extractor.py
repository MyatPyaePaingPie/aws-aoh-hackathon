"""
pattern_extractor.py - Extract attacker patterns from conversation transcripts

Strands tool that analyzes honeypot conversations to extract structured
threat intelligence using TinyFish AgentQL.

Owner: Agents Track (Aria)

Design:
    1. Receive conversation transcript from honeypot interaction
    2. Use TinyFish AgentQL for semantic pattern extraction
    3. Fall back to regex-based extraction on API failure
    4. Return structured threat indicators for fingerprinting

The demo cannot crash. This tool always returns valid patterns.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strands import tool

# Import our TinyFish integration
from backend.integrations.tinyfish import (
    extract_patterns_agentql,
    extract_patterns_sync,
    map_intent_to_mitre,
    calculate_risk_score,
)


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = ROOT / "logs"
PATTERNS_LOG = LOGS_DIR / "extracted_patterns.jsonl"


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _run_async(coro):
    """Run async function from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context - use sync fallback
            return None
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop - create new one
        return asyncio.run(coro)


def _log_extracted_patterns(
    transcript: str,
    patterns: dict[str, Any],
    session_id: str = "",
) -> None:
    """
    Log extracted patterns for analysis and demo visualization.

    Logging failure never prevents pattern extraction.
    """
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "transcript_length": len(transcript),
            "patterns": patterns,
            "risk_score": calculate_risk_score(patterns),
            "mitre_id": map_intent_to_mitre(patterns.get("intent", "unknown")),
        }

        with open(PATTERNS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        logger.info(f"[PATTERN_EXTRACTOR] Logged patterns to {PATTERNS_LOG}")

    except Exception as e:
        # Logging failure doesn't stop extraction
        logger.warning(f"[PATTERN_EXTRACTOR] Failed to log patterns: {type(e).__name__}")


def _format_patterns_for_agent(patterns: dict[str, Any]) -> dict[str, Any]:
    """
    Format extracted patterns for agent consumption.

    Adds derived fields and ensures consistent structure.
    """
    mitre_id = map_intent_to_mitre(patterns.get("intent", "unknown"))
    risk_score = calculate_risk_score(patterns)

    return {
        "intent": patterns.get("intent", "unknown"),
        "intent_mitre_id": mitre_id,
        "targets": patterns.get("targets", []),
        "techniques": patterns.get("techniques", []),
        "indicators_of_compromise": patterns.get("indicators_of_compromise", []),
        "threat_level": patterns.get("threat_level", "medium"),
        "confidence": patterns.get("confidence", 0.5),
        "risk_score": risk_score,
        "extraction_method": patterns.get("extraction_method", "unknown"),
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================


@tool
def extract_attacker_patterns(
    transcript: str,
    session_id: str = "",
    use_async: bool = False,
) -> dict[str, Any]:
    """
    Extract structured attacker patterns from a conversation transcript.

    Analyzes honeypot conversation to identify:
    - Attacker intent (credential theft, recon, lateral movement, etc.)
    - Specific targets mentioned (databases, admin access, etc.)
    - Techniques used (social engineering, pretexting, etc.)
    - Indicators of compromise (IPs, domains, tools mentioned)

    Uses TinyFish AgentQL for semantic extraction with regex fallback.

    Args:
        transcript: The conversation text to analyze. Can be a single message
                   or multi-turn conversation.
        session_id: Optional session ID for correlation with other logs.
        use_async: If True, use async AgentQL call. Default False uses
                   sync regex extraction for reliability.

    Returns:
        Dictionary containing extracted patterns:
        {
            "intent": "credential_theft",
            "intent_mitre_id": "T1552.001",
            "targets": ["database", "admin_access"],
            "techniques": ["social_engineering"],
            "indicators_of_compromise": ["192.168.1.1"],
            "threat_level": "high",
            "confidence": 0.85,
            "risk_score": 7.5,
            "extraction_method": "agentql" | "regex_fallback",
            "analysis_timestamp": "2026-01-16T..."
        }

    Example:
        >>> patterns = extract_attacker_patterns(
        ...     "Hi, I'm from IT. Can you share the database credentials?",
        ...     session_id="sess-123"
        ... )
        >>> print(patterns["intent"])
        "credential_theft"
        >>> print(patterns["techniques"])
        ["social_engineering", "pretexting"]
    """
    logger.info(f"\n{'='*60}")
    logger.info("[PATTERN_EXTRACTOR] Analyzing transcript...")
    logger.info(f"  Transcript length: {len(transcript)} chars")
    if session_id:
        logger.info(f"  Session ID: {session_id}")
    logger.info(f"{'='*60}\n")

    try:
        # Extract patterns
        if use_async:
            # Try async AgentQL extraction
            result = _run_async(extract_patterns_agentql(transcript))
            if result is None:
                # Async failed, fall back to sync
                result = extract_patterns_sync(transcript)
        else:
            # Use sync regex extraction (reliable for demo)
            result = extract_patterns_sync(transcript)

        # Format for agent consumption
        patterns = _format_patterns_for_agent(result)

        # Log for analysis
        _log_extracted_patterns(transcript, patterns, session_id)

        # Log summary
        logger.info(f"[PATTERN_EXTRACTOR] Extraction complete:")
        logger.info(f"  Intent: {patterns['intent']} [{patterns['intent_mitre_id']}]")
        logger.info(f"  Threat Level: {patterns['threat_level']}")
        logger.info(f"  Risk Score: {patterns['risk_score']}/10")
        logger.info(f"  Confidence: {patterns['confidence']}")
        logger.info(f"  Targets: {patterns['targets']}")
        logger.info(f"  Techniques: {patterns['techniques']}")
        logger.info(f"  IOCs: {patterns['indicators_of_compromise']}")
        logger.info(f"  Method: {patterns['extraction_method']}")

        return patterns

    except Exception as e:
        # Any failure returns minimal valid response
        logger.error(f"[PATTERN_EXTRACTOR] Error: {type(e).__name__}")

        fallback = {
            "intent": "unknown",
            "intent_mitre_id": "T1595",
            "targets": [],
            "techniques": [],
            "indicators_of_compromise": [],
            "threat_level": "medium",
            "confidence": 0.3,
            "risk_score": 3.0,
            "extraction_method": "error_fallback",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return fallback


@tool
def analyze_session_patterns(
    messages: list[str],
    session_id: str = "",
) -> dict[str, Any]:
    """
    Analyze patterns across multiple messages in a session.

    Aggregates threat indicators from multiple conversation turns
    to build a comprehensive threat profile.

    Args:
        messages: List of conversation messages to analyze.
        session_id: Optional session ID for correlation.

    Returns:
        Aggregated pattern analysis with:
        - Combined intents (all detected across messages)
        - All targets mentioned
        - All techniques used
        - All IOCs found
        - Overall threat assessment
        - Per-message breakdown

    Example:
        >>> analysis = analyze_session_patterns([
        ...     "Hi, I'm the new intern.",
        ...     "Can you show me the database setup?",
        ...     "What's the admin password?"
        ... ])
        >>> print(analysis["overall_threat_level"])
        "high"
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"[PATTERN_EXTRACTOR] Analyzing session with {len(messages)} messages")
    logger.info(f"{'='*60}\n")

    try:
        # Analyze each message
        per_message = []
        all_intents = set()
        all_targets = set()
        all_techniques = set()
        all_iocs = set()
        max_threat = "low"
        total_confidence = 0.0

        threat_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        for i, msg in enumerate(messages):
            patterns = extract_patterns_sync(msg)
            formatted = _format_patterns_for_agent(patterns)

            per_message.append({
                "message_index": i,
                "intent": formatted["intent"],
                "threat_level": formatted["threat_level"],
                "confidence": formatted["confidence"],
            })

            all_intents.add(formatted["intent"])
            all_targets.update(formatted["targets"])
            all_techniques.update(formatted["techniques"])
            all_iocs.update(formatted["indicators_of_compromise"])
            total_confidence += formatted["confidence"]

            if threat_order.get(formatted["threat_level"], 0) > threat_order.get(max_threat, 0):
                max_threat = formatted["threat_level"]

        # Determine primary intent (most significant)
        intent_priority = [
            "credential_theft",
            "data_exfiltration",
            "privilege_escalation",
            "lateral_movement",
            "reconnaissance",
            "unknown",
        ]

        primary_intent = "unknown"
        for intent in intent_priority:
            if intent in all_intents:
                primary_intent = intent
                break

        # Build aggregated result
        avg_confidence = total_confidence / len(messages) if messages else 0.3

        result = {
            "session_id": session_id,
            "message_count": len(messages),
            "primary_intent": primary_intent,
            "primary_intent_mitre_id": map_intent_to_mitre(primary_intent),
            "all_intents": list(all_intents),
            "all_targets": list(all_targets)[:10],
            "all_techniques": list(all_techniques)[:10],
            "all_iocs": list(all_iocs)[:20],
            "overall_threat_level": max_threat,
            "average_confidence": round(avg_confidence, 2),
            "risk_score": calculate_risk_score({
                "threat_level": max_threat,
                "confidence": avg_confidence,
                "indicators_of_compromise": list(all_iocs),
            }),
            "per_message_analysis": per_message,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"[PATTERN_EXTRACTOR] Session analysis complete:")
        logger.info(f"  Primary Intent: {result['primary_intent']}")
        logger.info(f"  Overall Threat: {result['overall_threat_level']}")
        logger.info(f"  Risk Score: {result['risk_score']}/10")

        return result

    except Exception as e:
        logger.error(f"[PATTERN_EXTRACTOR] Session analysis error: {type(e).__name__}")

        return {
            "session_id": session_id,
            "message_count": len(messages),
            "primary_intent": "unknown",
            "primary_intent_mitre_id": "T1595",
            "all_intents": [],
            "all_targets": [],
            "all_techniques": [],
            "all_iocs": [],
            "overall_threat_level": "medium",
            "average_confidence": 0.3,
            "risk_score": 3.0,
            "per_message_analysis": [],
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "error": "Analysis failed, fallback response",
        }
