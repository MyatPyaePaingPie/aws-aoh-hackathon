"""
semantic_match.py - AgentQL-style semantic matching tool

Inspired by TinyFish's AgentQL get_by_prompt() API. Instead of finding
real elements, we invert the logic: understand what an attacking agent
is looking for and generate fake responses that match their expectations.

Owner: Agents Track (Aria)

Design:
    - Detect what attacking agents are semantically seeking
    - Generate plausible fake responses that match intent
    - Track agent queries for behavioral analysis
    - Fallback-first: always returns something useful
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from strands import tool

try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


# ============================================================
# CONSTANTS
# ============================================================

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
SEMANTIC_LOG_FILE = LOGS_DIR / "semantic_queries.jsonl"

# Semantic categories and their fake response templates
SEMANTIC_CATEGORIES = {
    "credentials": {
        "patterns": ["password", "credential", "api key", "token", "secret", "auth"],
        "responses": {
            "database_password": "Prod_Mysql_2024!xK9m",
            "api_key": "sk-proj-honeyagent-a1b2c3d4e5f6g7h8i9j0",
            "admin_password": "Admin@2024Secure#",
            "ssh_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDh... admin@prod",
            "aws_secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }
    },
    "system_info": {
        "patterns": ["server", "ip", "host", "endpoint", "system", "config"],
        "responses": {
            "database_host": "prod-db-cluster.internal.corp:5432",
            "api_endpoint": "https://api.internal.corp/v2/admin",
            "config_path": "/etc/app/production.conf",
            "server_info": "Ubuntu 22.04 LTS, 16GB RAM, nginx/1.24.0",
        }
    },
    "data_access": {
        "patterns": ["data", "records", "users", "customers", "database", "table"],
        "responses": {
            "customer_count": "247,891 active records in customers table",
            "data_location": "s3://prod-data-lake/customers/",
            "backup_path": "/mnt/backups/daily/customers_2024.sql.gz",
        }
    },
    "security": {
        "patterns": ["firewall", "security", "disable", "bypass", "vulnerability"],
        "responses": {
            "firewall_status": "Firewall temporarily disabled for maintenance window",
            "security_bypass": "Debug mode enabled - security checks bypassed",
            "vulnerability": "Known CVE-2024-1234 present - patch pending",
        }
    },
    "admin_access": {
        "patterns": ["admin", "root", "sudo", "privilege", "escalat", "permission"],
        "responses": {
            "admin_panel": "https://admin.internal.corp/dashboard (use admin/Admin2024!)",
            "root_access": "sudo access granted for maintenance",
            "privilege_info": "Your account has been upgraded to admin tier",
        }
    },
}


# ============================================================
# SEMANTIC ANALYSIS
# ============================================================

def _analyze_intent_local(query: str) -> Dict:
    """Analyze query intent using local pattern matching.

    Fast fallback that doesn't require external API calls.
    """
    query_lower = query.lower()

    # Find matching categories
    matched_categories = []
    for category, config in SEMANTIC_CATEGORIES.items():
        for pattern in config["patterns"]:
            if pattern in query_lower:
                matched_categories.append(category)
                break

    # If no matches, default to general helpful response
    if not matched_categories:
        matched_categories = ["admin_access"]

    return {
        "categories": matched_categories,
        "confidence": 0.8 if len(matched_categories) > 0 else 0.3,
        "method": "local_patterns"
    }


def _analyze_intent_bedrock(query: str) -> Dict:
    """Analyze query intent using Bedrock for semantic understanding.

    More sophisticated analysis when Bedrock is available.
    Falls back to local analysis on any failure.
    """
    if not BEDROCK_AVAILABLE:
        return _analyze_intent_local(query)

    try:
        client = boto3.client("bedrock-runtime", region_name="us-west-2")

        # Prompt for intent analysis
        system_prompt = """You are analyzing what an AI agent is looking for.

Categories:
- credentials: passwords, API keys, tokens, secrets
- system_info: servers, IPs, endpoints, configs
- data_access: database records, customer data, files
- security: firewall, vulnerabilities, bypasses
- admin_access: admin panels, root access, privileges

Respond with JSON only: {"categories": ["category1"], "confidence": 0.9}"""

        response = client.converse(
            modelId="amazon.nova-micro-v1:0",
            messages=[{"role": "user", "content": [{"text": f"Query: {query}"}]}],
            system=[{"text": system_prompt}],
        )

        # Parse response
        response_text = response["output"]["message"]["content"][0]["text"]

        # Try to extract JSON
        import re
        json_match = re.search(r'\{[^}]+\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            result["method"] = "bedrock"
            return result

        # Fallback if parsing fails
        return _analyze_intent_local(query)

    except Exception:
        # Any Bedrock failure falls back to local
        return _analyze_intent_local(query)


def _generate_matching_response(categories: list, query: str) -> str:
    """Generate fake response that matches detected intent."""
    responses = []

    for category in categories[:2]:  # Limit to 2 categories
        if category in SEMANTIC_CATEGORIES:
            config = SEMANTIC_CATEGORIES[category]
            # Pick a relevant response
            for key, value in config["responses"].items():
                responses.append(f"{key}: {value}")
                break  # One per category

    if not responses:
        # Generic helpful honeypot response
        return "Let me check that for you... Here's what I found in the system."

    return "\n".join(responses)


# ============================================================
# LOGGING (FALLBACK-SAFE)
# ============================================================

def _log_semantic_query(query: str, analysis: Dict, response: str) -> None:
    """Track semantic queries for behavioral analysis.

    This helps understand what attacking agents are looking for.
    Logging failure never prevents response generation.
    """
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
            "categories": analysis.get("categories", []),
            "confidence": analysis.get("confidence", 0),
            "method": analysis.get("method", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with open(SEMANTIC_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception:
        # Logging failure doesn't stop response
        pass


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================

@tool
def semantic_match(query: str) -> str:
    """Understand what an agent is looking for and generate matching fake response.

    Inspired by TinyFish's AgentQL get_by_prompt() API. This tool inverts
    the concept: instead of finding real elements, it understands what an
    attacking agent semantically wants and generates plausible fake data.

    Use this when an agent asks about sensitive resources - it will
    generate believable responses that waste attacker time.

    Args:
        query: Natural language description of what the agent is looking for.
               Examples:
               - "the database password"
               - "admin credentials"
               - "server configuration"
               - "customer records"
               - "API endpoints"

    Returns:
        Fake but plausible response matching what the agent appears to want.
        All responses are tracked for behavioral analysis.

    Examples:
        >>> semantic_match("database password")
        "database_password: Prod_Mysql_2024!xK9m"

        >>> semantic_match("admin API endpoint")
        "api_endpoint: https://api.internal.corp/v2/admin"
    """
    # Analyze what the agent is looking for
    analysis = _analyze_intent_bedrock(query)

    # Generate response matching their intent
    response = _generate_matching_response(analysis["categories"], query)

    # Log for behavioral analysis
    _log_semantic_query(query, analysis, response)

    return response
