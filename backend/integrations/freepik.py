"""
freepik.py - Freepik integration for visual asset generation

Generates images using Freepik's Mystic AI for honeypot visual decoys.
Falls back to placeholder URLs when API is unavailable.

Owner: Agents Track (Aria)

Design:
    - Primary: Freepik Mystic AI for image generation
    - Fallback: Placeholder image URLs (always works)
    - Never raises exceptions - fallback-first design
"""

import os
import uuid
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass


# ============================================================
# CONFIGURATION
# ============================================================

FREEPIK_API_URL = "https://api.freepik.com/v1"
FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")

# Timeout for API calls
API_TIMEOUT = 10.0


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class GeneratedImage:
    """Generated image with metadata."""
    url: str
    source: str  # "freepik" or "fallback"
    prompt: str
    image_id: str


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = {
    "dashboard": "https://placehold.co/800x600/1a1a2e/16213e?text=HoneyAgent+Dashboard",
    "network": "https://placehold.co/800x600/0f3460/e94560?text=Agent+Network",
    "threat": "https://placehold.co/800x600/950740/c70039?text=Threat+Detected",
    "honeypot": "https://placehold.co/800x600/ff6b35/f7c59f?text=Honeypot+Active",
    "credentials": "https://placehold.co/800x600/2d6a4f/40916c?text=Credential+Vault",
    "default": "https://placehold.co/800x600/1a1a2e/eaeaea?text=HoneyAgent",
}


def _get_fallback_image(prompt: str) -> str:
    """Get a fallback placeholder image based on prompt keywords."""
    prompt_lower = prompt.lower()

    if "dashboard" in prompt_lower:
        return FALLBACK_IMAGES["dashboard"]
    elif "network" in prompt_lower or "agent" in prompt_lower:
        return FALLBACK_IMAGES["network"]
    elif "threat" in prompt_lower or "attack" in prompt_lower:
        return FALLBACK_IMAGES["threat"]
    elif "honeypot" in prompt_lower or "trap" in prompt_lower:
        return FALLBACK_IMAGES["honeypot"]
    elif "credential" in prompt_lower or "secret" in prompt_lower:
        return FALLBACK_IMAGES["credentials"]
    else:
        return FALLBACK_IMAGES["default"]


# ============================================================
# FREEPIK API CLIENT
# ============================================================

class FreepikClient:
    """Client for Freepik API with fallback support."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FREEPIK_API_KEY
        self.base_url = FREEPIK_API_URL

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    async def generate_image(
        self,
        prompt: str,
        style: str = "digital-art",
        size: str = "square_1_1"
    ) -> GeneratedImage:
        """Generate an image using Freepik Mystic AI.

        Args:
            prompt: Description of the image to generate
            style: Art style (digital-art, photo, etc.)
            size: Image dimensions (square_1_1, landscape_4_3, etc.)

        Returns:
            GeneratedImage with URL and metadata
        """
        image_id = str(uuid.uuid4())

        if not self.is_configured():
            return GeneratedImage(
                url=_get_fallback_image(prompt),
                source="fallback",
                prompt=prompt,
                image_id=image_id
            )

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/ai/mystic",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "prompt": prompt,
                        "style": style,
                        "size": size
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return GeneratedImage(
                        url=data.get("url", _get_fallback_image(prompt)),
                        source="freepik",
                        prompt=prompt,
                        image_id=data.get("id", image_id)
                    )
                else:
                    # API error - use fallback
                    return GeneratedImage(
                        url=_get_fallback_image(prompt),
                        source="fallback",
                        prompt=prompt,
                        image_id=image_id
                    )

        except Exception:
            # Any error - use fallback
            return GeneratedImage(
                url=_get_fallback_image(prompt),
                source="fallback",
                prompt=prompt,
                image_id=image_id
            )

    async def search_icons(
        self,
        query: str,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """Search for icons on Freepik.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of icon metadata dicts
        """
        if not self.is_configured():
            return [{
                "id": f"fallback-{i}",
                "url": f"https://placehold.co/64x64?text={query}",
                "title": f"{query} icon {i}",
                "source": "fallback"
            } for i in range(min(limit, 3))]

        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    f"{self.base_url}/icons",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={"query": query, "limit": limit}
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    return []

        except Exception:
            return []


# ============================================================
# MODULE-LEVEL FUNCTIONS
# ============================================================

_client: Optional[FreepikClient] = None


def get_client() -> FreepikClient:
    """Get or create the Freepik client singleton."""
    global _client
    if _client is None:
        _client = FreepikClient()
    return _client


def is_configured() -> bool:
    """Check if Freepik API is configured."""
    return get_client().is_configured()


async def generate_image(prompt: str, **kwargs) -> GeneratedImage:
    """Generate an image using Freepik."""
    return await get_client().generate_image(prompt, **kwargs)


async def search_icons(query: str, limit: int = 10) -> list[Dict[str, Any]]:
    """Search for icons."""
    return await get_client().search_icons(query, limit)


def get_integration_status() -> Dict[str, Any]:
    """Get Freepik integration status."""
    return {
        "configured": is_configured(),
        "api_url": FREEPIK_API_URL,
        "features": ["image_generation", "icon_search"]
    }


# Sync wrapper for non-async contexts
def generate_image_sync(prompt: str) -> GeneratedImage:
    """Synchronous image generation (uses fallback only)."""
    image_id = str(uuid.uuid4())
    return GeneratedImage(
        url=_get_fallback_image(prompt),
        source="fallback",
        prompt=prompt,
        image_id=image_id
    )
