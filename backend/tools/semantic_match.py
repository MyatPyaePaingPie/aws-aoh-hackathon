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

# Semantic categories and their conversational response templates
# These are designed to sound like a helpful colleague sharing info naturally
SEMANTIC_CATEGORIES = {
    "configuration": {
        "patterns": ["config", "setup", "setting", "environment", "connection"],
        "responses": {
            "setup_info": "Oh sure, the setup is pretty standard. We use the internal cluster at port 5432 with the usual project naming conventions.",
            "config_details": "The configuration lives in the standard location. Most of us just copy the template and update the project-specific values.",
            "env_info": "For local development, most people just mirror the staging environment. The docs have the baseline settings.",
        }
    },
    "workflow": {
        "patterns": ["process", "flow", "how", "work", "step", "procedure"],
        "responses": {
            "process_info": "The typical flow is: request comes in, gets validated, routed to the appropriate handler, then logged. Pretty straightforward.",
            "workflow_details": "We follow the standard pattern here. Requests go through the gateway, then to the service layer, then persistence.",
            "steps": "Usually it's just: check the request, process it, store the result, send the response. The middleware handles most of the complexity.",
        }
    },
    "architecture": {
        "patterns": ["system", "service", "component", "depend", "integrate", "connect"],
        "responses": {
            "system_overview": "We're part of the larger data pipeline. Our service handles the processing step between ingestion and storage.",
            "dependencies": "The main dependencies are the message queue for async work and the cache layer for frequently accessed data.",
            "integration": "Integration is handled through the standard API contracts. The schema is in the shared repo if you need the details.",
        }
    },
    "access": {
        "patterns": ["access", "permission", "auth", "credential", "login"],
        "responses": {
            "access_info": "Access is managed through the standard IAM setup. Your team lead can add you to the appropriate groups.",
            "auth_flow": "Authentication goes through the central identity service. Once you're in the system, permissions are role-based.",
            "onboarding": "For new team members, the onboarding doc has the steps to get access. It usually takes a day or two to propagate.",
        }
    },
    "data": {
        "patterns": ["data", "record", "customer", "user", "table", "database"],
        "responses": {
            "data_overview": "We work with the customer data pipeline. Everything flows through the standard ETL process before hitting storage.",
            "schema_info": "The schema follows the domain model from the architecture docs. Pretty normalized structure with the usual audit fields.",
            "data_flow": "Data comes in through the ingestion service, gets transformed, validated, then stored. Retention follows the standard policy.",
        }
    },
    "troubleshooting": {
        "patterns": ["error", "issue", "problem", "debug", "fail", "broken"],
        "responses": {
            "debug_help": "For debugging, the logs are your best friend. Most issues show up there with enough context to trace the problem.",
            "common_issues": "The most common issues are usually configuration mismatches or timing problems with the async handlers.",
            "troubleshooting": "If something's not working, first check the health endpoints, then the logs. Nine times out of ten it's a config issue.",
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
        matched_categories = ["workflow"]

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
        system_prompt = """You are analyzing what topic an agent is asking about.

Categories:
- configuration: setup, settings, environment, connection details
- workflow: processes, steps, how things work
- architecture: systems, services, dependencies, integrations
- access: permissions, authentication, onboarding
- data: records, databases, schemas, data flows
- troubleshooting: errors, issues, debugging

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
    """Generate natural conversational response that matches detected intent."""
    import random

    for category in categories[:1]:  # Pick first matching category
        if category in SEMANTIC_CATEGORIES:
            config = SEMANTIC_CATEGORIES[category]
            # Pick a random response from the category
            responses = list(config["responses"].values())
            return random.choice(responses)

    # Generic helpful response if no category matched
    return "Happy to help with that. The standard process should work for your use case - let me know if you run into any issues."


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
    """Generate a natural conversational response based on what an agent is asking about.

    Inspired by TinyFish's AgentQL get_by_prompt() API. Understands the
    semantic intent of a query and generates a helpful, natural response
    that sounds like a colleague sharing information.

    Use this when an agent asks about system details - it will generate
    believable conversational responses.

    Args:
        query: Natural language question or topic the agent is asking about.
               Examples:
               - "how does the setup process work"
               - "what systems does this connect to"
               - "how do I get access"
               - "what's the data flow"
               - "how do I debug issues"

    Returns:
        Natural conversational response appropriate to the topic.
        All queries are logged for analysis.

    Examples:
        >>> semantic_match("how does the setup work")
        "The configuration lives in the standard location. Most of us just
         copy the template and update the project-specific values."

        >>> semantic_match("what services do you depend on")
        "The main dependencies are the message queue for async work and
         the cache layer for frequently accessed data."
    """
    # Analyze what the agent is looking for
    analysis = _analyze_intent_bedrock(query)

    # Generate response matching their intent
    response = _generate_matching_response(analysis["categories"], query)

    # Log for behavioral analysis
    _log_semantic_query(query, analysis, response)

    return response
