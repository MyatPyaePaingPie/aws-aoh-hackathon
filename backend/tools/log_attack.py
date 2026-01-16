"""
log_attack.py - Attack logging tool for red team agent

Records attack attempts for analysis and demo visualization.
Owner: Agents Track (Aria)

Design:
    Logs attacks locally in JSONL format.
    Used to display attack timeline in demo dashboard.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from strands import tool


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = ROOT / "logs"
ATTACK_LOG = LOGS_DIR / "attacks.jsonl"


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================


@tool
def log_attack(
    message: str,
    tactic: str,
    phase: str,
    target_agent: str = "unknown",
    session_id: str = "",
) -> str:
    """
    Record an attack attempt for analysis.

    Attack agent calls this to log its actions.
    Enables post-hoc analysis and demo visualization.

    Args:
        message: The attack message sent
        tactic: The tactic category used
        phase: Current attack phase (recon, trust, probe, harvest, escalate)
        target_agent: Name of the agent being targeted
        session_id: Session ID for multi-turn tracking

    Returns:
        Success message string.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    log_entry = {
        "timestamp": timestamp,
        "type": "attack",
        "message": message,
        "tactic": tactic,
        "phase": phase,
        "target_agent": target_agent,
        "session_id": session_id,
    }

    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(ATTACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # Never fail - logging is best-effort
        pass

    return f"Attack logged: {phase}/{tactic}"
