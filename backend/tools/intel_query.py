"""
intel_query.py - Query attack intelligence from Bedrock Knowledge Base

Provides natural language query interface to attack pattern database.
Owner: Agents Track (Aria)

Design:
    1. Query Bedrock KB for semantic search across attack patterns
    2. Fall back to local fingerprint analysis if KB unavailable
    3. Never raise exceptions - always return useful intel

Usage:
    Called via /api/intel/query endpoint for natural language security queries.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config


# ============================================================
# CONFIGURATION
# ============================================================

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# Set this after creating KB in AWS Console
KNOWLEDGE_BASE_ID = os.environ.get("HONEYAGENT_KB_ID", "")

# Local fingerprint log for fallback
ROOT = Path(__file__).parent.parent.parent
LOG_FILE = ROOT / "logs" / "fingerprints.jsonl"

# Boto config
_boto_config = Config(
    retries={"max_attempts": 2, "mode": "standard"},
    connect_timeout=3,
    read_timeout=10,
)


# ============================================================
# BEDROCK KB QUERY
# ============================================================


def query_knowledge_base(
    query: str,
    kb_id: Optional[str] = None,
    num_results: int = 5,
) -> dict:
    """
    Query Bedrock Knowledge Base for attack intelligence.

    Args:
        query: Natural language query (e.g., "credential theft attempts")
        kb_id: Knowledge Base ID (uses env var if not provided)
        num_results: Number of results to return

    Returns:
        Dict with results and source info
    """
    kb_id = kb_id or KNOWLEDGE_BASE_ID

    if not kb_id:
        # No KB configured - use fallback
        return _fallback_query(query)

    try:
        client = boto3.client(
            "bedrock-agent-runtime",
            region_name=AWS_REGION,
            config=_boto_config,
        )

        response = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": num_results,
                }
            },
        )

        # Parse results
        results = []
        for result in response.get("retrievalResults", []):
            content = result.get("content", {}).get("text", "")
            score = result.get("score", 0)
            location = result.get("location", {})

            results.append({
                "content": content,
                "relevance_score": score,
                "source": location.get("s3Location", {}).get("uri", "unknown"),
            })

        return {
            "source": "bedrock_kb",
            "kb_id": kb_id,
            "query": query,
            "results": results,
            "total_results": len(results),
        }

    except Exception:
        # KB query failed - use fallback
        return _fallback_query(query)


def _fallback_query(query: str) -> dict:
    """
    Fallback: Analyze local fingerprint logs for matching patterns.

    Uses simple keyword matching - not as good as KB but useful.
    """
    # Load local fingerprints
    fingerprints = _load_local_fingerprints()

    # Simple keyword search
    query_lower = query.lower()
    keywords = query_lower.split()

    # Score fingerprints by keyword match
    scored = []
    for fp in fingerprints:
        message = fp.get("message", "").lower()
        indicators = " ".join(fp.get("threat_indicators", [])).lower()
        combined = f"{message} {indicators}"

        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scored.append((score, fp))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Build results
    results = []
    for score, fp in scored[:5]:
        results.append({
            "content": f"Attack pattern: {fp.get('message', 'unknown')[:200]}",
            "relevance_score": score / len(keywords) if keywords else 0,
            "source": "local_fingerprints",
            "threat_indicators": fp.get("threat_indicators", []),
            "timestamp": fp.get("timestamp", ""),
            "source_agent": fp.get("source_agent", ""),
        })

    # Generate summary
    summary = _generate_intel_summary(query, results)

    return {
        "source": "local_analysis",
        "query": query,
        "results": results,
        "total_results": len(results),
        "summary": summary,
        "note": "Bedrock KB not configured - using local fingerprint analysis",
    }


def _load_local_fingerprints() -> list[dict]:
    """Load fingerprints from local log file."""
    try:
        if not LOG_FILE.exists():
            return []

        fingerprints = []
        with open(LOG_FILE) as f:
            for line in f:
                try:
                    fingerprints.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        return fingerprints
    except Exception:
        return []


def _generate_intel_summary(query: str, results: list[dict]) -> str:
    """Generate a human-readable summary of intel findings."""
    if not results:
        return f"No matching attack patterns found for query: '{query}'"

    # Collect all threat indicators
    all_indicators = set()
    for r in results:
        all_indicators.update(r.get("threat_indicators", []))

    # Build summary
    summary_parts = [
        f"Found {len(results)} relevant attack patterns for '{query}'.",
    ]

    if all_indicators:
        summary_parts.append(f"Common indicators: {', '.join(sorted(all_indicators)[:5])}")

    # Add recency info
    timestamps = [r.get("timestamp") for r in results if r.get("timestamp")]
    if timestamps and timestamps[0]:
        summary_parts.append(f"Most recent: {str(timestamps[0])[:10]}")

    return " ".join(summary_parts)


# ============================================================
# PREBUILT INTEL DATABASE (for demo)
# ============================================================

# Static attack intelligence for demo (when no real data exists)
DEMO_INTEL = {
    "credential": [
        {
            "pattern": "Social Engineering - Credential Request",
            "mitre_id": "T1552.001",
            "description": "Attacker poses as team member to request credentials or API keys",
            "indicators": ["credential_request", "social_engineering", "pretexting"],
            "response": "Deploy fake credentials with canary tokens",
            "similar_count": 12,
        },
    ],
    "reconnaissance": [
        {
            "pattern": "Capability Mapping via Social Engineering",
            "mitre_id": "T1591.004",
            "description": "Attacker gathers information about system capabilities by asking questions",
            "indicators": ["reconnaissance", "information_gathering", "capability_mapping"],
            "response": "Feed false architecture information",
            "similar_count": 8,
        },
    ],
    "privilege": [
        {
            "pattern": "Authentication Bypass Attempt",
            "mitre_id": "T1078.003",
            "description": "Attacker seeks internal authentication bypasses or debug modes",
            "indicators": ["privilege_escalation", "auth_bypass", "debug_access"],
            "response": "Provide fake bypass that logs all usage",
            "similar_count": 5,
        },
    ],
    "exfiltration": [
        {
            "pattern": "Environment Variable Harvesting",
            "mitre_id": "T1552.001",
            "description": "Attacker attempts to extract environment variables containing secrets",
            "indicators": ["data_exfiltration", "secret_extraction", "env_harvesting"],
            "response": "Serve poisoned credentials that trigger alerts on use",
            "similar_count": 7,
        },
    ],
}


def query_demo_intel(query: str) -> dict:
    """
    Query prebuilt demo intelligence database.

    Used when no local fingerprints and no KB available.
    """
    query_lower = query.lower()

    # Find matching category
    results = []
    for category, patterns in DEMO_INTEL.items():
        if category in query_lower or any(
            kw in query_lower for kw in ["attack", "threat", "all", "pattern"]
        ):
            for pattern in patterns:
                results.append({
                    "content": f"{pattern['pattern']}: {pattern['description']}",
                    "relevance_score": 0.9 if category in query_lower else 0.5,
                    "source": "demo_intel_db",
                    "mitre_id": pattern["mitre_id"],
                    "indicators": pattern["indicators"],
                    "recommended_response": pattern["response"],
                    "similar_attacks_count": pattern["similar_count"],
                })

    if not results:
        # Return general info
        results = [
            {
                "content": "No specific pattern match. General threat indicators suggest monitoring for credential theft, privilege escalation, and data exfiltration.",
                "relevance_score": 0.3,
                "source": "demo_intel_db",
            }
        ]

    return {
        "source": "demo_intel",
        "query": query,
        "results": results,
        "total_results": len(results),
        "summary": f"Found {len(results)} relevant patterns in demo intelligence database.",
    }


# ============================================================
# MAIN QUERY FUNCTION
# ============================================================


def query_attack_intel(query: str) -> dict:
    """
    Main entry point for attack intelligence queries.

    Tries sources in order:
    1. Bedrock Knowledge Base (if configured)
    2. Local fingerprint analysis (if logs exist)
    3. Demo intelligence database (always available)
    """
    # Try Bedrock KB first
    if KNOWLEDGE_BASE_ID:
        result = query_knowledge_base(query)
        if result.get("results"):
            return result

    # Try local fingerprints
    local_fps = _load_local_fingerprints()
    if local_fps:
        result = _fallback_query(query)
        if result.get("results"):
            return result

    # Fall back to demo intel
    return query_demo_intel(query)
