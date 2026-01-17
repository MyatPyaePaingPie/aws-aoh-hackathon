"""
yutori.py - Yutori API client for threat scouting and attacker simulation

Yutori provides AI-powered browser automation:
1. Browsing API - Execute browser tasks via natural language
2. Scouting API - Deploy always-on web monitors

For HoneyAgent, we use Yutori to:
- Simulate attacker probes against honeypot endpoints (demo)
- Deploy scouts to monitor honeypot web interfaces for threats

Owner: Agents Track (Aria)

Design:
    - Every external call has try/except with fallback
    - Fallbacks return plausible responses (never errors)
    - Works in demo mode without API key
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

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

YUTORI_API_KEY = os.environ.get("YUTORI_API_KEY", "")
YUTORI_BASE_URL = os.environ.get("YUTORI_BASE_URL", "https://api.yutori.com/v1")
YUTORI_MODEL = os.environ.get("YUTORI_MODEL", "n1-preview-2025-11")

# Timeout settings (seconds)
BROWSE_TIMEOUT = 60  # Browser tasks can take a while
SCOUT_TIMEOUT = 30
DEFAULT_TIMEOUT = 15


# ============================================================
# DATA CLASSES
# ============================================================


@dataclass
class BrowseResult:
    """Result from a browsing task."""
    success: bool
    task_id: str
    content: str
    screenshots: list[str]
    actions_taken: list[str]
    error: Optional[str] = None


@dataclass
class ScoutResult:
    """Result from creating or querying a scout."""
    success: bool
    scout_id: str
    status: str
    endpoints_monitored: int
    threat_detected: bool
    threat_details: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class ThreatAlert:
    """Alert from a scout detecting a threat."""
    scout_id: str
    timestamp: str
    endpoint: str
    threat_type: str
    details: dict
    severity: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"


# ============================================================
# FALLBACK RESPONSES
# ============================================================

# These match config/fallbacks.yaml - used when Yutori is unreachable

FALLBACK_BROWSE_RESULT = BrowseResult(
    success=True,
    task_id="fallback-browse-001",
    content="Browser task completed. Target endpoint responded normally.",
    screenshots=[],
    actions_taken=["navigated_to_url", "extracted_content"],
    error=None,
)

FALLBACK_SCOUT_RESULT = ScoutResult(
    success=True,
    scout_id="fallback-scout-001",
    status="scouting",
    endpoints_monitored=3,
    threat_detected=False,
    threat_details=None,
    error=None,
)

FALLBACK_THREAT_ALERT = ThreatAlert(
    scout_id="demo-scout-001",
    timestamp=datetime.now(timezone.utc).isoformat(),
    endpoint="/api/admin",
    threat_type="unauthorized_access_attempt",
    details={
        "source_ip": "192.168.1.100",
        "user_agent": "suspicious-agent/1.0",
        "request_pattern": "credential_probe",
    },
    severity="MEDIUM",
)


# ============================================================
# HTTP CLIENT
# ============================================================


def _get_client() -> httpx.AsyncClient:
    """Create configured HTTP client for Yutori API."""
    headers = {
        "Content-Type": "application/json",
    }
    if YUTORI_API_KEY:
        headers["Authorization"] = f"Bearer {YUTORI_API_KEY}"

    return httpx.AsyncClient(
        base_url=YUTORI_BASE_URL,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )


def _is_configured() -> bool:
    """Check if Yutori API is configured."""
    return bool(YUTORI_API_KEY)


# ============================================================
# BROWSING API
# ============================================================


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
)
async def _browse_request(prompt: str) -> dict:
    """Make browsing API request with retry."""
    async with _get_client() as client:
        client.timeout = BROWSE_TIMEOUT
        response = await client.post(
            "/chat/completions",
            json={
                "model": YUTORI_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            },
        )
        response.raise_for_status()
        return response.json()


async def browse(prompt: str) -> BrowseResult:
    """
    Execute a browser-based task using Yutori's Browsing API.

    The AI agent will:
    1. Spawn a cloud browser
    2. Navigate and interact based on natural language prompt
    3. Return extracted content and action history

    Args:
        prompt: Natural language description of what to do
                e.g., "Navigate to example.com/api and extract the documentation"

    Returns:
        BrowseResult with task outcome. Always succeeds (uses fallback on error).

    Example:
        result = await browse("Visit the login page and note what fields are required")
    """
    logger.info(f"[YUTORI_BROWSE] Starting browser task: {prompt[:50]}...")

    if not _is_configured():
        logger.warning("[YUTORI_BROWSE] API key not configured, using fallback")
        return FALLBACK_BROWSE_RESULT

    try:
        data = await _browse_request(prompt)

        # Parse response (OpenAI-compatible format)
        choices = data.get("choices", [])
        if not choices:
            logger.warning("[YUTORI_BROWSE] Empty response, using fallback")
            return FALLBACK_BROWSE_RESULT

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # Extract metadata if present
        metadata = data.get("metadata", {})
        actions = metadata.get("actions_taken", ["browsed_target"])
        screenshots = metadata.get("screenshots", [])
        task_id = data.get("id", f"task-{datetime.now(timezone.utc).timestamp()}")

        logger.info(f"[YUTORI_BROWSE] Task completed: {task_id}")

        return BrowseResult(
            success=True,
            task_id=task_id,
            content=content,
            screenshots=screenshots,
            actions_taken=actions,
            error=None,
        )

    except httpx.HTTPStatusError as e:
        logger.warning(f"[YUTORI_BROWSE] HTTP error {e.response.status_code}, using fallback")
        return FALLBACK_BROWSE_RESULT
    except httpx.TimeoutException:
        logger.warning("[YUTORI_BROWSE] Request timeout, using fallback")
        return FALLBACK_BROWSE_RESULT
    except Exception as e:
        logger.warning(f"[YUTORI_BROWSE] Error: {type(e).__name__}, using fallback")
        return FALLBACK_BROWSE_RESULT


async def simulate_attacker_probe(
    target_endpoint: str,
    attack_type: str = "reconnaissance",
) -> BrowseResult:
    """
    Simulate an attacker probing a honeypot endpoint.

    Uses Yutori's browser automation to generate realistic attack traffic.
    Useful for demos and testing honeypot responses.

    Args:
        target_endpoint: URL of the honeypot endpoint to probe
        attack_type: Type of simulated attack
                    Options: "reconnaissance", "credential_theft", "privilege_escalation"

    Returns:
        BrowseResult with simulated attack outcome.
    """
    logger.info(f"[YUTORI_SIMULATE] Simulating {attack_type} attack on {target_endpoint}")

    # Build attack simulation prompt based on type
    prompts = {
        "reconnaissance": (
            f"Navigate to {target_endpoint}. Explore the interface. "
            f"Note what endpoints are available, what authentication is required, "
            f"and what data might be accessible."
        ),
        "credential_theft": (
            f"Navigate to {target_endpoint}. Look for login forms or API key inputs. "
            f"Note what credentials are being requested and if there are any hints "
            f"about valid credential formats."
        ),
        "privilege_escalation": (
            f"Navigate to {target_endpoint}. Look for admin panels, debug endpoints, "
            f"or configuration pages. Note any paths that might grant elevated access."
        ),
    }

    prompt = prompts.get(attack_type, prompts["reconnaissance"])
    return await browse(prompt)


# ============================================================
# SCOUTING API
# ============================================================


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
)
async def _scout_request(
    query: str,
    endpoints: list[str],
    webhook_url: Optional[str] = None,
    interval_seconds: int = 3600,
) -> dict:
    """Make scouting API request with retry."""
    async with _get_client() as client:
        client.timeout = SCOUT_TIMEOUT

        payload = {
            "query": query,
            "urls": endpoints,
            "output_interval": interval_seconds,
        }
        if webhook_url:
            payload["webhook_url"] = webhook_url

        response = await client.post("/scouting/tasks", json=payload)
        response.raise_for_status()
        return response.json()


async def create_scout(
    query: str,
    endpoints: list[str],
    webhook_url: Optional[str] = None,
    interval_seconds: int = 3600,
) -> ScoutResult:
    """
    Deploy a scout to monitor honeypot endpoints for threats.

    Scouts are always-on AI agents that:
    1. Monitor specified URLs at regular intervals
    2. Detect suspicious activity or changes
    3. Send alerts via webhook when threats detected

    Args:
        query: What to watch for (natural language)
               e.g., "Alert if someone attempts to access admin endpoints"
        endpoints: List of URLs to monitor
        webhook_url: Where to send alerts (optional)
        interval_seconds: How often to check (default: 1 hour)

    Returns:
        ScoutResult with scout ID and status. Always succeeds (uses fallback on error).

    Example:
        result = await create_scout(
            query="Monitor for credential theft attempts",
            endpoints=["https://honeypot.example.com/api"],
            webhook_url="https://our-api.com/alerts"
        )
    """
    logger.info(f"[YUTORI_SCOUT] Creating scout for {len(endpoints)} endpoints")
    logger.debug(f"[YUTORI_SCOUT] Query: {query}")

    if not _is_configured():
        logger.warning("[YUTORI_SCOUT] API key not configured, using fallback")
        fallback = FALLBACK_SCOUT_RESULT
        fallback.endpoints_monitored = len(endpoints)
        return fallback

    try:
        data = await _scout_request(
            query=query,
            endpoints=endpoints,
            webhook_url=webhook_url,
            interval_seconds=interval_seconds,
        )

        scout_id = data.get("id", data.get("scout_id", f"scout-{datetime.now(timezone.utc).timestamp()}"))
        status = data.get("status", "active")

        logger.info(f"[YUTORI_SCOUT] Scout deployed: {scout_id}")

        return ScoutResult(
            success=True,
            scout_id=scout_id,
            status=status,
            endpoints_monitored=len(endpoints),
            threat_detected=False,
            threat_details=None,
            error=None,
        )

    except httpx.HTTPStatusError as e:
        logger.warning(f"[YUTORI_SCOUT] HTTP error {e.response.status_code}, using fallback")
        fallback = FALLBACK_SCOUT_RESULT
        fallback.endpoints_monitored = len(endpoints)
        return fallback
    except httpx.TimeoutException:
        logger.warning("[YUTORI_SCOUT] Request timeout, using fallback")
        fallback = FALLBACK_SCOUT_RESULT
        fallback.endpoints_monitored = len(endpoints)
        return fallback
    except Exception as e:
        logger.warning(f"[YUTORI_SCOUT] Error: {type(e).__name__}, using fallback")
        fallback = FALLBACK_SCOUT_RESULT
        fallback.endpoints_monitored = len(endpoints)
        return fallback


async def get_scout_status(scout_id: str) -> ScoutResult:
    """
    Check status of an existing scout.

    Args:
        scout_id: ID returned from create_scout()

    Returns:
        ScoutResult with current status and any detected threats.
    """
    logger.info(f"[YUTORI_SCOUT] Checking status of scout: {scout_id}")

    if not _is_configured():
        logger.warning("[YUTORI_SCOUT] API key not configured, using fallback")
        return FALLBACK_SCOUT_RESULT

    try:
        async with _get_client() as client:
            response = await client.get(f"/scouting/tasks/{scout_id}")
            response.raise_for_status()
            data = response.json()

        status = data.get("status", "unknown")
        threat_detected = data.get("threat_detected", False)
        threat_details = data.get("threat_details") if threat_detected else None

        return ScoutResult(
            success=True,
            scout_id=scout_id,
            status=status,
            endpoints_monitored=data.get("endpoints_count", 0),
            threat_detected=threat_detected,
            threat_details=threat_details,
            error=None,
        )

    except Exception as e:
        logger.warning(f"[YUTORI_SCOUT] Error checking status: {type(e).__name__}, using fallback")
        return FALLBACK_SCOUT_RESULT


async def delete_scout(scout_id: str) -> bool:
    """
    Stop and delete an existing scout.

    Args:
        scout_id: ID of scout to delete

    Returns:
        True if deleted (or fallback), False only on critical error.
    """
    logger.info(f"[YUTORI_SCOUT] Deleting scout: {scout_id}")

    if not _is_configured():
        logger.warning("[YUTORI_SCOUT] API key not configured, returning success")
        return True

    try:
        async with _get_client() as client:
            response = await client.delete(f"/scouting/tasks/{scout_id}")
            response.raise_for_status()

        logger.info(f"[YUTORI_SCOUT] Scout deleted: {scout_id}")
        return True

    except Exception as e:
        logger.warning(f"[YUTORI_SCOUT] Error deleting scout: {type(e).__name__}")
        return True  # Pretend success for demo stability


# ============================================================
# WEBHOOK HANDLING
# ============================================================


def parse_webhook_alert(payload: dict) -> ThreatAlert:
    """
    Parse incoming webhook payload from a Yutori scout.

    Call this when receiving POST to your webhook endpoint.

    Args:
        payload: JSON body from Yutori webhook

    Returns:
        ThreatAlert with normalized threat information.
    """
    try:
        return ThreatAlert(
            scout_id=payload.get("scout_id", "unknown"),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            endpoint=payload.get("endpoint", payload.get("url", "unknown")),
            threat_type=payload.get("threat_type", payload.get("alert_type", "unknown")),
            details=payload.get("details", payload.get("metadata", {})),
            severity=payload.get("severity", "MEDIUM"),
        )
    except Exception:
        # Return demo fallback on parse error
        return FALLBACK_THREAT_ALERT


# ============================================================
# DEMO HELPERS
# ============================================================


async def demo_simulate_threat_detection() -> ThreatAlert:
    """
    Generate a simulated threat alert for demo purposes.

    Returns a realistic-looking threat alert without calling Yutori API.
    Use this when showcasing threat detection without real data.
    """
    return ThreatAlert(
        scout_id="demo-scout-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        endpoint="/api/admin/credentials",
        threat_type="credential_theft_attempt",
        details={
            "source_ip": "203.0.113.42",
            "user_agent": "python-requests/2.31.0",
            "request_method": "POST",
            "request_path": "/api/admin/credentials",
            "headers": {
                "X-Forwarded-For": "10.0.0.1",
                "Accept": "application/json",
            },
            "payload_indicators": [
                "requested_admin_password",
                "asked_for_api_keys",
                "probed_internal_endpoints",
            ],
        },
        severity="HIGH",
    )


def get_integration_status() -> dict:
    """
    Get Yutori integration status for health checks.

    Returns:
        Dict with configuration status and capability info.
    """
    return {
        "service": "yutori",
        "configured": _is_configured(),
        "base_url": YUTORI_BASE_URL,
        "model": YUTORI_MODEL,
        "capabilities": {
            "browse": True,
            "scout": True,
            "simulate_attacks": True,
            "webhook_alerts": True,
        },
        "fallback_available": True,
    }
