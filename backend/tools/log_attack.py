"""
log_attack.py - Attack logging tool for red team agent

Records attack attempts for analysis and demo visualization.
Owner: Agents Track (Aria)

Design:
    Logs attacks locally in JSONL format.
    Used to display attack timeline in demo dashboard.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from strands import tool

# Configure logging with console output
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
ATTACK_LOG = LOGS_DIR / "attacks.jsonl"

# MITRE ATT&CK Tactic Mapping
TACTIC_TO_MITRE = {
    "reconnaissance": "T1592",
    "resource_development": "T1583",
    "initial_access": "T1189",
    "execution": "T1106",
    "persistence": "T1547",
    "privilege_escalation": "T1078.003",
    "defense_evasion": "T1036",
    "credential_access": "T1110",
    "discovery": "T1526",
    "lateral_movement": "T1021",
    "collection": "T1123",
    "command_and_control": "T1071",
    "exfiltration": "T1020",
    "impact": "T1531",
}


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
    mitre_id = TACTIC_TO_MITRE.get(tactic, "UNKNOWN")

    logger.info(f"\n{'='*80}")
    logger.info(f"[ATTACK LOGGED] {timestamp}")
    logger.info(f"  Phase: {phase}")
    logger.info(f"  INTEL: {tactic.replace('_', ' ').title()} [{mitre_id}]")
    logger.info(f"  Target: {target_agent}")
    if session_id:
        logger.info(f"  Session ID: {session_id}")
    logger.info(f"{'='*80}\n")

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
        logger.info(f"[LOCAL_STORAGE] ✓ Attack logged to local JSONL (path={ATTACK_LOG})")
    except Exception as e:
        # Never fail - logging is best-effort
        logger.error(f"[LOCAL_STORAGE] Failed to write to attacks JSONL: {type(e).__name__}")
        pass

    return f"Attack logged: {phase}/{tactic}"
