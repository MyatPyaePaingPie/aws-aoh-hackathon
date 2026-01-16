"""
Identity Layer for HoneyAgent

Handles JWT token validation, claim extraction, and FGA permission checks.
Owner: Identity Track (Partner)

Integration Contract Output:
    Identity(
        valid: bool,
        agent_id: Optional[str],
        agent_type: Optional[str],  # "real" | "honeypot" | None
        is_honeypot: bool,
        fga_allowed: bool,
        raw_claims: dict
    )
"""

import os
import jwt
import httpx
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache


# ============================================================
# IDENTITY DATA CLASS
# ============================================================

@dataclass
class Identity:
    """Result of identity validation."""
    valid: bool
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None  # "real" | "honeypot" | None
    is_honeypot: bool = False
    fga_allowed: bool = False
    raw_claims: dict = field(default_factory=dict)


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).parent.parent.parent

def load_fallbacks():
    """Load fallback configuration."""
    fallbacks_path = ROOT / "config" / "fallbacks.yaml"
    with open(fallbacks_path) as f:
        return yaml.safe_load(f)


def get_identity_fallback(fallback_type: str) -> Identity:
    """Get identity fallback for error cases."""
    fallbacks = load_fallbacks()
    fb = fallbacks.get("identity_fallbacks", {}).get(fallback_type, {})
    return Identity(
        valid=fb.get("valid", False),
        agent_id=None,
        agent_type=fb.get("agent_type"),
        is_honeypot=fb.get("is_honeypot", False),
        fga_allowed=fb.get("fga_allowed", False),
        raw_claims={}
    )


# ============================================================
# JWKS FETCHING
# ============================================================

@lru_cache(maxsize=1)
def get_jwks():
    """
    Fetch JWKS from Auth0.
    Cached to avoid repeated calls.
    """
    domain = os.getenv("AUTH0_DOMAIN")
    if not domain:
        return None

    try:
        url = f"https://{domain}/.well-known/jwks.json"
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def get_signing_key(token: str):
    """Get the signing key for a token from JWKS."""
    jwks = get_jwks()
    if not jwks:
        return None

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        return None
    except Exception:
        return None


# ============================================================
# TOKEN VALIDATION
# ============================================================

def validate_token(auth_header: Optional[str]) -> Identity:
    """
    Validate JWT token from Authorization header.

    Args:
        auth_header: "Bearer <token>" or None

    Returns:
        Identity with validation results
    """
    # No auth header = invalid
    if not auth_header:
        return get_identity_fallback("token_decode_failed")

    # Extract token from "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return get_identity_fallback("token_decode_failed")

    token = parts[1]

    # Get signing key from JWKS
    try:
        signing_key = get_signing_key(token)
        if not signing_key:
            return get_identity_fallback("jwks_fetch_failed")

        # Validate token
        domain = os.getenv("AUTH0_DOMAIN")
        audience = os.getenv("AUTH0_AUDIENCE")

        decoded = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{domain}/"
        )

        # Extract identity from claims
        return extract_identity(decoded)

    except jwt.ExpiredSignatureError:
        return get_identity_fallback("token_decode_failed")
    except jwt.InvalidTokenError:
        return get_identity_fallback("token_decode_failed")
    except Exception:
        return get_identity_fallback("token_decode_failed")


def extract_identity(claims: dict) -> Identity:
    """
    Extract Identity from validated JWT claims.

    Custom claims namespace: https://honeyagent.io/
    """
    namespace = "https://honeyagent.io/"

    # Extract agent info from claims
    agent_type = claims.get(f"{namespace}agent_type", "real")
    agent_id = claims.get("sub", "").replace("@clients", "")

    # Determine if honeypot
    is_honeypot = agent_type == "honeypot"

    return Identity(
        valid=True,
        agent_id=agent_id,
        agent_type=agent_type,
        is_honeypot=is_honeypot,
        fga_allowed=True,  # Will be updated by check_fga
        raw_claims=claims
    )


# ============================================================
# FGA PERMISSION CHECKS
# ============================================================

async def check_fga(agent_id: str, relation: str, object_id: str) -> bool:
    """
    Check FGA permission.

    Args:
        agent_id: e.g., "agent-001"
        relation: e.g., "can_communicate"
        object_id: e.g., "swarm:swarm-alpha"

    Returns:
        True if allowed, False if denied
    """
    store_id = os.getenv("AUTH0_FGA_STORE_ID")
    api_url = os.getenv("AUTH0_FGA_API_URL", "https://api.us1.fga.dev")
    client_id = os.getenv("AUTH0_FGA_CLIENT_ID")
    client_secret = os.getenv("AUTH0_FGA_CLIENT_SECRET")

    if not all([store_id, client_id, client_secret]):
        # FGA not configured - fail open for demo
        return True

    try:
        # Get FGA access token
        token = await get_fga_token(client_id, client_secret, api_url)
        if not token:
            return True  # Fail open

        # Make check request
        url = f"{api_url}/stores/{store_id}/check"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = {
            "tuple_key": {
                "user": f"agent:{agent_id}",
                "relation": relation,
                "object": object_id
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=body, headers=headers, timeout=5.0)
            response.raise_for_status()
            result = response.json()
            return result.get("allowed", False)

    except Exception:
        # FGA error - fail open for demo
        return True


async def get_fga_token(client_id: str, client_secret: str, api_url: str) -> Optional[str]:
    """Get access token for FGA API."""
    try:
        # FGA uses OAuth2 client credentials
        token_url = f"{api_url}/oauth/token"  # May vary by FGA setup

        # For Auth0 FGA, we use the client credentials directly
        # The token is obtained from the FGA token endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://fga.us.auth0.com/oauth/token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "audience": "https://api.us1.fga.dev/",
                    "grant_type": "client_credentials"
                },
                timeout=5.0
            )
            response.raise_for_status()
            return response.json().get("access_token")
    except Exception:
        return None


# ============================================================
# COMBINED IDENTITY + FGA CHECK
# ============================================================

async def get_full_identity(auth_header: Optional[str], swarm_id: str = "swarm-alpha") -> Identity:
    """
    Get identity with FGA permission check.

    This is the main entry point for the identity layer.

    Args:
        auth_header: Authorization header from request
        swarm_id: The swarm to check permissions against

    Returns:
        Complete Identity with FGA check result
    """
    # First validate the token
    identity = validate_token(auth_header)

    # If token invalid, return immediately (will route to honeypot)
    if not identity.valid:
        return identity

    # Check FGA permission
    fga_allowed = await check_fga(
        identity.agent_id,
        "can_communicate",
        f"swarm:{swarm_id}"
    )

    # Update identity with FGA result
    identity.fga_allowed = fga_allowed

    return identity


# ============================================================
# SYNC WRAPPER (for non-async contexts)
# ============================================================

def get_full_identity_sync(auth_header: Optional[str], swarm_id: str = "swarm-alpha") -> Identity:
    """Synchronous wrapper for get_full_identity."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(get_full_identity(auth_header, swarm_id))
