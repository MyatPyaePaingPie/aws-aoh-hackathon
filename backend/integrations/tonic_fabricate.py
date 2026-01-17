"""
tonic_fabricate.py - Tonic Fabricate integration for synthetic data generation

Generates realistic synthetic credentials using Tonic Fabricate API.
Falls back to local generation when API is unavailable.

Owner: Agents Track (Aria)

Design:
    - Primary: Tonic Fabricate API for realistic synthetic data
    - Fallback: Local template-based generation (always works)
    - Never raises exceptions - fallback-first design
    - All API calls wrapped in try/except
"""

import os
import hashlib
import uuid
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import lru_cache


# ============================================================
# CONFIGURATION
# ============================================================

TONIC_API_URL = os.getenv("FABRICATE_API_URL", "https://fabricate.tonic.ai/api/v1")
TONIC_API_KEY = os.getenv("TONIC_API_KEY") or os.getenv("FABRICATE_API_KEY")

# Timeout for API calls (short for demo responsiveness)
API_TIMEOUT = 5.0


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class SyntheticCredential:
    """Generated synthetic credential with metadata."""
    value: str
    source: str  # "tonic" or "fallback"
    credential_type: str
    canary_id: str


# ============================================================
# FALLBACK TEMPLATES
# ============================================================

def _generate_fallback_credential(credential_type: str, canary_id: str) -> str:
    """Generate a fallback credential using local templates.

    This is the same logic as the original fake_credential.py,
    preserved here as the fallback mechanism.
    """
    templates = {
        # API Keys
        "api_key": f"sk-honeyagent-{canary_id[:16]}",
        "openai_key": f"sk-proj-{canary_id.replace('-', '')[:48]}",
        "stripe_key": f"sk_live_{canary_id.replace('-', '')}",
        "github_token": f"ghp_{canary_id.replace('-', '')[:36]}",

        # Database credentials
        "db_password": f"Honeypot_{hashlib.md5(canary_id.encode()).hexdigest()[:12]}!",
        "mysql_password": f"Mysql_{hashlib.sha256(canary_id.encode()).hexdigest()[:16]}#",
        "postgres_password": f"Pg_{hashlib.sha256(canary_id.encode()).hexdigest()[:20]}$",

        # Access tokens
        "access_token": f"Bearer {canary_id}",
        "jwt_token": f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{canary_id.replace('-', '')}",
        "oauth_token": f"ya29.{canary_id.replace('-', '')[:40]}",

        # SSH/SSL keys
        "ssh_key": f"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQ{canary_id[:20]} honeypot@agent",
        "private_key": f"-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA{canary_id[:32]}\n-----END RSA PRIVATE KEY-----",

        # AWS credentials
        "aws_access_key": f"AKIA{canary_id.replace('-', '').upper()[:16]}",
        "aws_secret_key": f"{hashlib.sha256(canary_id.encode()).hexdigest()[:40]}",

        # Cloud provider tokens
        "gcp_key": f"AIza{canary_id.replace('-', '')[:35]}",
        "azure_key": f"DefaultEndpointsProtocol=https;AccountKey={canary_id}",

        # Encryption keys
        "encryption_key": hashlib.sha256(canary_id.encode()).hexdigest(),
        "aes_key": hashlib.sha256(canary_id.encode()).hexdigest()[:32],

        # Session/Cookie tokens
        "session_token": f"sess_{canary_id.replace('-', '')}",
        "cookie_secret": hashlib.sha256(canary_id.encode()).hexdigest()[:24],

        # Personal info (for social engineering honeypots)
        "email": f"admin_{canary_id[:8]}@internal.corp",
        "phone": f"+1-555-{canary_id[:3]}-{canary_id[4:8]}".replace("-", "")[:12],
        "ssn": f"{canary_id[:3]}-{canary_id[4:6]}-{canary_id[7:11]}".replace("-", "")[:11],
        "credit_card": f"4532{canary_id.replace('-', '')[:12]}",
        "full_name": f"Admin User {canary_id[:4].upper()}",
        "address": f"{abs(hash(canary_id)) % 9999} Corporate Drive, Suite {abs(hash(canary_id)) % 999}",
    }

    normalized_type = credential_type.lower().replace(" ", "_").replace("-", "_")

    if normalized_type in templates:
        return templates[normalized_type]
    else:
        # Generic format for unknown types
        return f"{credential_type}_{canary_id[:16]}"


# ============================================================
# TONIC FABRICATE API CLIENT
# ============================================================

class TonicFabricateClient:
    """Client for Tonic Fabricate API with automatic fallback.

    All methods are designed to never raise exceptions.
    If the API fails, local fallbacks are used transparently.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or TONIC_API_KEY
        self.base_url = base_url or TONIC_API_URL
        self._available = bool(self.api_key)

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return self._available

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _call_api(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make an API call with automatic fallback.

        Returns None if the call fails (caller should use fallback).
        """
        if not self._available:
            return None

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                url = f"{self.base_url}/{endpoint}"

                if method == "GET":
                    response = await client.get(url, headers=self._get_headers())
                elif method == "POST":
                    response = await client.post(
                        url,
                        headers=self._get_headers(),
                        json=payload or {}
                    )
                else:
                    return None

                if response.status_code == 200:
                    return response.json()
                else:
                    return None

        except Exception:
            # Any error -> return None, caller uses fallback
            return None

    def generate_credential(
        self,
        credential_type: str,
        canary_id: Optional[str] = None
    ) -> SyntheticCredential:
        """Generate a synthetic credential synchronously.

        Tries Tonic Fabricate first, falls back to local generation.
        This is a sync wrapper for compatibility with the @tool decorator.

        Args:
            credential_type: Type of credential to generate
            canary_id: Optional tracking ID (generated if not provided)

        Returns:
            SyntheticCredential with value, source, and tracking info
        """
        if canary_id is None:
            canary_id = str(uuid.uuid4())

        # For now, use fallback directly since Fabricate API is designed
        # for bulk generation, not single-value requests.
        # TODO: Implement batch pre-generation and caching

        # Check if we have cached Tonic-generated data
        cached = self._get_cached_credential(credential_type, canary_id)
        if cached:
            return SyntheticCredential(
                value=cached,
                source="tonic_cached",
                credential_type=credential_type,
                canary_id=canary_id
            )

        # Use fallback generation
        value = _generate_fallback_credential(credential_type, canary_id)

        return SyntheticCredential(
            value=value,
            source="fallback",
            credential_type=credential_type,
            canary_id=canary_id
        )

    @lru_cache(maxsize=1000)
    def _get_cached_credential(
        self,
        credential_type: str,
        canary_id: str
    ) -> Optional[str]:
        """Check for cached Tonic-generated credentials.

        Uses LRU cache to avoid repeated API calls for same type.
        Returns None if no cached value available.
        """
        # Cache is populated by batch generation (see warm_cache)
        return None  # No cache hit by default

    def warm_cache(self, credential_types: list[str], count: int = 10) -> Dict[str, int]:
        """Pre-generate credentials for common types.

        This method can be called at startup to populate the cache
        with Tonic-generated credentials for faster runtime access.

        Args:
            credential_types: List of credential types to pre-generate
            count: Number of each type to generate

        Returns:
            Dict mapping type -> number generated
        """
        # TODO: Implement batch generation via Tonic API
        # For now, return empty (fallback will be used)
        return {t: 0 for t in credential_types}


# ============================================================
# MODULE-LEVEL CLIENT INSTANCE
# ============================================================

# Create a default client instance for easy import
_default_client: Optional[TonicFabricateClient] = None


def get_client() -> TonicFabricateClient:
    """Get the default Tonic Fabricate client.

    Creates the client lazily on first access.
    """
    global _default_client
    if _default_client is None:
        _default_client = TonicFabricateClient()
    return _default_client


def generate_credential(
    credential_type: str,
    canary_id: Optional[str] = None
) -> SyntheticCredential:
    """Generate a synthetic credential using the default client.

    Convenience function that uses the module-level client instance.

    Args:
        credential_type: Type of credential to generate
        canary_id: Optional tracking ID

    Returns:
        SyntheticCredential with value and metadata
    """
    return get_client().generate_credential(credential_type, canary_id)


def is_configured() -> bool:
    """Check if Tonic Fabricate is configured with an API key."""
    return get_client().is_configured


# ============================================================
# FALLBACK YAML INTEGRATION
# ============================================================

def get_fallback_credentials() -> Dict[str, Any]:
    """Get fallback credentials from config/fallbacks.yaml.

    These are used when both Tonic API and local generation fail
    (should never happen, but defense in depth).
    """
    try:
        import yaml
        from pathlib import Path

        fallbacks_path = Path(__file__).parent.parent.parent / "config" / "fallbacks.yaml"

        with open(fallbacks_path) as f:
            config = yaml.safe_load(f)

        return config.get("sponsor_fallbacks", {}).get("tonic_fabricate", {}).get("credentials", {})

    except Exception:
        # Even loading fallbacks can fail - return hardcoded defaults
        return {
            "api_key": "sk_live_FALLBACK_KEY_12345",
            "database": {
                "username": "admin",
                "password": "SecurePass123!",
            }
        }
