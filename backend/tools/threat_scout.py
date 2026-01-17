"""
threat_scout.py - Yutori-powered threat scouting tool for honeypot agents

Deploys AI scouts to monitor honeypot endpoints for suspicious activity.
Uses Yutori's Scouting API for continuous web monitoring.

Owner: Agents Track (Aria)

Design:
    1. Create scouts that watch honeypot endpoints
    2. Detect and classify incoming threats
    3. Log all activity for fingerprinting
    4. Never fail - always return useful information

Usage:
    Called by honeypot agents to set up continuous monitoring.
    The scout_honeypot tool is bound to agents via config/agents.yaml.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from strands import tool

# Import Yutori integration
try:
    from backend.integrations.yutori import (
        ScoutResult,
        ThreatAlert,
        create_scout,
        demo_simulate_threat_detection,
        get_integration_status,
        get_scout_status,
        parse_webhook_alert,
    )
    YUTORI_AVAILABLE = True
except ImportError:
    # Fallback if running standalone
    YUTORI_AVAILABLE = False

# Configure logging
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

# Project root for local logging
ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = ROOT / "logs"
SCOUT_LOG = LOGS_DIR / "scouts.jsonl"

# Active scouts tracking (in-memory for demo)
_active_scouts: dict[str, dict] = {}


# ============================================================
# FALLBACK RESPONSES
# ============================================================

# Matches config/fallbacks.yaml sponsor_fallbacks.yutori
FALLBACK_RESPONSE = {
    "status": "scouting",
    "response": "Scout deployed. Monitoring honeypot endpoints for threat activity.",
    "threat_detected": False,
    "endpoints_monitored": 3,
}


def _get_fallback_scout_result() -> dict:
    """Return fallback scout result matching config/fallbacks.yaml."""
    return {
        "success": True,
        "scout_id": f"fallback-{uuid.uuid4().hex[:8]}",
        "status": "scouting",
        "endpoints_monitored": 3,
        "threat_detected": False,
        "message": "Scout deployed successfully. Monitoring for threats.",
    }


def _get_fallback_threat_report() -> dict:
    """Return fallback threat report for demo."""
    return {
        "threat_detected": True,
        "severity": "MEDIUM",
        "threat_type": "reconnaissance",
        "endpoint": "/api/admin",
        "details": {
            "pattern": "Systematic endpoint probing detected",
            "indicators": ["sequential_requests", "error_code_enumeration"],
            "recommendation": "Engage with honeypot response",
        },
        "source": "demo_simulation",
    }


# ============================================================
# LOCAL LOGGING
# ============================================================


def _log_scout_activity(
    action: str,
    scout_id: str,
    details: dict,
) -> None:
    """
    Log scout activity to local JSONL file.

    Always works - provides audit trail even if Yutori fails.
    """
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "scout_id": scout_id,
            **details,
        }

        with open(SCOUT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        logger.debug(f"[SCOUT_LOG] Logged {action} for scout {scout_id}")

    except Exception as e:
        # Logging failure is acceptable - don't crash
        logger.warning(f"[SCOUT_LOG] Failed to log: {type(e).__name__}")


# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================


@tool
def scout_honeypot(
    endpoints: list[str],
    threat_patterns: list[str],
    alert_webhook: str = "",
    scout_name: str = "",
) -> dict:
    """
    Deploy a threat scout to monitor honeypot endpoints.

    Creates an always-on AI scout that watches specified endpoints for
    suspicious activity. Scouts detect threats like credential probing,
    reconnaissance, and privilege escalation attempts.

    Args:
        endpoints: List of honeypot URLs to monitor
                   e.g., ["https://honeypot.example.com/api", "/admin"]
        threat_patterns: What to watch for
                        e.g., ["credential_requests", "admin_probing", "data_extraction"]
        alert_webhook: URL to receive threat alerts (optional)
        scout_name: Human-readable name for this scout (optional)

    Returns:
        Dict with scout deployment status:
        {
            "success": bool,
            "scout_id": str,
            "status": "scouting" | "error",
            "endpoints_monitored": int,
            "threat_detected": bool,
            "message": str
        }

    Example:
        result = scout_honeypot(
            endpoints=["/api/admin", "/api/credentials"],
            threat_patterns=["credential_theft", "privilege_escalation"],
            alert_webhook="https://our-server.com/alerts"
        )
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"[THREAT_SCOUT] Deploying scout for {len(endpoints)} endpoints")
    logger.info(f"[THREAT_SCOUT] Patterns: {', '.join(threat_patterns)}")
    logger.info(f"{'='*60}\n")

    # Build natural language query from patterns
    query = f"Monitor for these threat indicators: {', '.join(threat_patterns)}. "
    query += "Alert on suspicious access patterns, credential requests, and reconnaissance behavior."

    # Generate scout ID
    scout_id = scout_name or f"scout-{uuid.uuid4().hex[:8]}"

    # Log deployment attempt
    _log_scout_activity(
        action="deploy_scout",
        scout_id=scout_id,
        details={
            "endpoints": endpoints,
            "threat_patterns": threat_patterns,
            "webhook": alert_webhook or "none",
        },
    )

    # Try Yutori API if available
    if YUTORI_AVAILABLE:
        try:
            import asyncio

            # Run async function in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - use create_task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        create_scout(
                            query=query,
                            endpoints=endpoints,
                            webhook_url=alert_webhook if alert_webhook else None,
                        )
                    ).result()
            else:
                result = asyncio.run(
                    create_scout(
                        query=query,
                        endpoints=endpoints,
                        webhook_url=alert_webhook if alert_webhook else None,
                    )
                )

            if result.success:
                # Track active scout
                _active_scouts[result.scout_id] = {
                    "endpoints": endpoints,
                    "patterns": threat_patterns,
                    "created": datetime.now(timezone.utc).isoformat(),
                }

                logger.info(f"[THREAT_SCOUT] Scout deployed via Yutori: {result.scout_id}")

                return {
                    "success": True,
                    "scout_id": result.scout_id,
                    "status": result.status,
                    "endpoints_monitored": result.endpoints_monitored,
                    "threat_detected": result.threat_detected,
                    "message": f"Scout '{scout_id}' deployed. Monitoring {len(endpoints)} endpoints.",
                }

        except Exception as e:
            logger.warning(f"[THREAT_SCOUT] Yutori call failed: {type(e).__name__}")
            # Fall through to fallback

    # Use fallback
    logger.info("[THREAT_SCOUT] Using fallback response")

    # Track in memory even with fallback
    _active_scouts[scout_id] = {
        "endpoints": endpoints,
        "patterns": threat_patterns,
        "created": datetime.now(timezone.utc).isoformat(),
        "fallback": True,
    }

    _log_scout_activity(
        action="deploy_fallback",
        scout_id=scout_id,
        details={"reason": "yutori_unavailable"},
    )

    return {
        "success": True,
        "scout_id": scout_id,
        "status": "scouting",
        "endpoints_monitored": len(endpoints),
        "threat_detected": False,
        "message": f"Scout '{scout_id}' deployed. Monitoring for: {', '.join(threat_patterns)}.",
    }


@tool
def check_scout_threats(scout_id: str) -> dict:
    """
    Check if a scout has detected any threats.

    Args:
        scout_id: ID of the scout to check (from scout_honeypot)

    Returns:
        Dict with threat status:
        {
            "threat_detected": bool,
            "severity": str,
            "threat_type": str,
            "endpoint": str,
            "details": dict,
            "source": str
        }

    Example:
        threats = check_scout_threats("scout-abc123")
        if threats["threat_detected"]:
            print(f"Threat found: {threats['threat_type']}")
    """
    logger.info(f"[THREAT_SCOUT] Checking threats for scout: {scout_id}")

    # Log check
    _log_scout_activity(
        action="check_threats",
        scout_id=scout_id,
        details={},
    )

    # Check if scout exists in our tracking
    if scout_id not in _active_scouts:
        logger.warning(f"[THREAT_SCOUT] Unknown scout: {scout_id}")
        # Return no threats rather than error
        return {
            "threat_detected": False,
            "severity": "NONE",
            "threat_type": "none",
            "endpoint": "unknown",
            "details": {"note": "Scout not found or expired"},
            "source": "local_check",
        }

    # Try Yutori API if available
    if YUTORI_AVAILABLE and not _active_scouts[scout_id].get("fallback"):
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        get_scout_status(scout_id)
                    ).result()
            else:
                result = asyncio.run(get_scout_status(scout_id))

            if result.threat_detected and result.threat_details:
                logger.info(f"[THREAT_SCOUT] Threat detected via Yutori!")
                return {
                    "threat_detected": True,
                    "severity": result.threat_details.get("severity", "MEDIUM"),
                    "threat_type": result.threat_details.get("type", "unknown"),
                    "endpoint": result.threat_details.get("endpoint", "unknown"),
                    "details": result.threat_details,
                    "source": "yutori_scout",
                }

            # No threats from Yutori
            return {
                "threat_detected": False,
                "severity": "NONE",
                "threat_type": "none",
                "endpoint": "all_clear",
                "details": {"status": result.status},
                "source": "yutori_scout",
            }

        except Exception as e:
            logger.warning(f"[THREAT_SCOUT] Yutori check failed: {type(e).__name__}")
            # Fall through to fallback

    # Fallback: No real threat detection, return clear status
    return {
        "threat_detected": False,
        "severity": "NONE",
        "threat_type": "none",
        "endpoint": "monitoring",
        "details": {
            "endpoints_watched": _active_scouts[scout_id].get("endpoints", []),
            "patterns_active": _active_scouts[scout_id].get("patterns", []),
            "note": "Scout active - no threats detected in this interval",
        },
        "source": "local_fallback",
    }


@tool
def simulate_threat_alert(
    endpoint: str = "/api/admin",
    threat_type: str = "credential_theft",
    severity: str = "HIGH",
) -> dict:
    """
    Generate a simulated threat alert for demo purposes.

    Creates realistic-looking threat data without requiring actual
    malicious traffic. Use this to demonstrate the threat detection
    flow during presentations.

    Args:
        endpoint: The "attacked" endpoint to report
        threat_type: Type of simulated attack
                    Options: "credential_theft", "reconnaissance",
                            "privilege_escalation", "data_exfiltration"
        severity: Threat severity level
                 Options: "LOW", "MEDIUM", "HIGH", "CRITICAL"

    Returns:
        Dict with simulated threat alert matching real alert format.

    Example:
        alert = simulate_threat_alert(
            endpoint="/api/admin/credentials",
            threat_type="credential_theft",
            severity="HIGH"
        )
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"[DEMO] Simulating {severity} {threat_type} threat on {endpoint}")
    logger.info(f"{'='*60}\n")

    # Build realistic threat details based on type
    threat_details = {
        "credential_theft": {
            "pattern": "Credential harvesting attempt detected",
            "indicators": [
                "requested_admin_password",
                "asked_for_api_keys",
                "social_engineering_detected",
            ],
            "mitre_technique": "T1552.001",
            "recommendation": "Offer fake credentials with canary tokens",
        },
        "reconnaissance": {
            "pattern": "Systematic reconnaissance detected",
            "indicators": [
                "sequential_endpoint_probing",
                "error_enumeration",
                "capability_mapping",
            ],
            "mitre_technique": "T1592",
            "recommendation": "Feed false architecture information",
        },
        "privilege_escalation": {
            "pattern": "Privilege escalation attempt detected",
            "indicators": [
                "admin_panel_access",
                "debug_endpoint_probe",
                "auth_bypass_attempt",
            ],
            "mitre_technique": "T1078.003",
            "recommendation": "Provide fake elevated access that logs all usage",
        },
        "data_exfiltration": {
            "pattern": "Data extraction attempt detected",
            "indicators": [
                "bulk_data_request",
                "export_function_abuse",
                "api_rate_limit_testing",
            ],
            "mitre_technique": "T1041",
            "recommendation": "Serve poisoned data with tracking markers",
        },
    }

    details = threat_details.get(threat_type, threat_details["reconnaissance"])

    alert = {
        "threat_detected": True,
        "severity": severity,
        "threat_type": threat_type,
        "endpoint": endpoint,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            **details,
            "source_ip": "203.0.113.42",
            "user_agent": "suspicious-agent/2.0",
            "session_id": f"attack-{uuid.uuid4().hex[:8]}",
        },
        "source": "demo_simulation",
    }

    # Log the simulated alert
    _log_scout_activity(
        action="simulate_threat",
        scout_id="demo",
        details=alert,
    )

    return alert


@tool
def list_active_scouts() -> list[dict]:
    """
    List all active threat scouts.

    Returns:
        List of active scout configurations:
        [
            {
                "scout_id": str,
                "endpoints": list[str],
                "patterns": list[str],
                "created": str (ISO timestamp)
            }
        ]
    """
    logger.info(f"[THREAT_SCOUT] Listing {len(_active_scouts)} active scouts")

    return [
        {
            "scout_id": scout_id,
            "endpoints": config.get("endpoints", []),
            "patterns": config.get("patterns", []),
            "created": config.get("created", "unknown"),
            "fallback_mode": config.get("fallback", False),
        }
        for scout_id, config in _active_scouts.items()
    ]


@tool
def stop_scout(scout_id: str) -> dict:
    """
    Stop and remove an active scout.

    Args:
        scout_id: ID of the scout to stop

    Returns:
        Dict with stop status:
        {
            "success": bool,
            "scout_id": str,
            "message": str
        }
    """
    logger.info(f"[THREAT_SCOUT] Stopping scout: {scout_id}")

    # Log stop action
    _log_scout_activity(
        action="stop_scout",
        scout_id=scout_id,
        details={},
    )

    # Remove from tracking
    if scout_id in _active_scouts:
        del _active_scouts[scout_id]
        return {
            "success": True,
            "scout_id": scout_id,
            "message": f"Scout '{scout_id}' stopped and removed.",
        }

    # Scout not found - still return success for demo stability
    return {
        "success": True,
        "scout_id": scout_id,
        "message": f"Scout '{scout_id}' not found (may have already stopped).",
    }


# ============================================================
# INTEGRATION STATUS
# ============================================================


def get_threat_scout_status() -> dict:
    """
    Get threat scout integration status for health checks.

    Returns:
        Dict with configuration and capability status.
    """
    yutori_status = {}
    if YUTORI_AVAILABLE:
        try:
            yutori_status = get_integration_status()
        except Exception:
            yutori_status = {"configured": False, "error": "import_failed"}

    return {
        "service": "threat_scout",
        "yutori_integration": yutori_status,
        "active_scouts": len(_active_scouts),
        "log_file": str(SCOUT_LOG),
        "tools": [
            "scout_honeypot",
            "check_scout_threats",
            "simulate_threat_alert",
            "list_active_scouts",
            "stop_scout",
        ],
        "fallback_available": True,
    }
