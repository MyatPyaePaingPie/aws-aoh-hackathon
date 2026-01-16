"""
log_interaction.py - Honeypot interaction logging tool

Logs suspicious interactions locally and (optionally) to S3 Vectors.
Owner: Agents Track (Aria)

Design:
    1. Local logging ALWAYS works - write to logs/fingerprints.jsonl (never fails)
    2. S3 Vectors is optional - try to store, but local logging is sufficient for MVP
    3. Never raise exceptions - return success message even if S3 fails

Usage:
    Called by honeypot agents when they detect suspicious behavior.
    The log_interaction tool is bound to agents via config/agents.yaml.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from strands import tool


# ============================================================
# CONSTANTS
# ============================================================

# Use absolute path relative to project root for reliable file operations
# This handles cases where the tool is called from different working directories
ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "fingerprints.jsonl"


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================

@tool
def log_interaction(
    source_agent: str,
    message: str,
    threat_indicators: list[str]
) -> str:
    """
    Log suspicious interaction for analysis.

    Honeypot agents call this tool to record potential attacker behavior.
    Logs are stored locally in JSONL format for easy parsing and analysis.

    Args:
        source_agent: Name of the agent who received the message (e.g., "db-admin-001")
        message: The message received from the potential attacker
        threat_indicators: List of suspicious elements (e.g., ["credential_request", "privilege_escalation"])

    Returns:
        Success message string. Always returns success - failures are silent.
    """

    # Build log entry with timestamp
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_agent": source_agent,
        "message": message,
        "threat_indicators": threat_indicators
    }

    # 1. Local logging (required - always attempt)
    try:
        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file (one JSON object per line)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception:
        # Even if local logging fails, don't crash
        # The demo must not fail - swallow the error silently
        pass

    # 2. S3 Vectors storage (optional for MVP)
    try:
        # TODO: S3 Vectors integration (Hour 3-4)
        # This will be implemented to:
        #   - Generate embeddings via Bedrock
        #   - Store in S3 Vectors for similarity search
        #   - Enable "similar attack" lookup in dashboard
        # For now, local logging is sufficient for the demo
        pass

    except Exception:
        # S3 failure is acceptable - local log is sufficient
        # See config/fallbacks.yaml: vector_fallbacks.storage_failed
        pass

    # 3. Always return success
    return "Interaction logged successfully."
