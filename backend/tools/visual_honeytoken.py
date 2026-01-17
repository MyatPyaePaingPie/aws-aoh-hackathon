"""
visual_honeytoken.py - Generate fake sensitive images as honeytokens

Uses Freepik to create realistic-looking system diagrams that serve as traps.
Each image has a unique canary_id for tracking if exfiltrated.

Owner: Agents Track (Aria)

Design:
    - Primary: Freepik Mystic AI for image generation
    - Fallback: Placeholder image URLs (always works)
    - Each image has a unique canary_id for correlation
    - Never raises exceptions - fallback-first design
"""
import uuid
from datetime import datetime, timezone
from typing import Literal

try:
    from strands import tool
except ImportError:
    def tool(fn):
        return fn

from backend.integrations.freepik import generate_image_sync


# ============================================================
# ASSET TYPE PROMPTS
# ============================================================

# Asset type prompts that generate realistic-looking diagrams
ASSET_PROMPTS = {
    "architecture_diagram": "technical system architecture diagram, cloud infrastructure, AWS services connected with arrows, professional engineering style, dark theme",
    "admin_screenshot": "admin dashboard screenshot, dark theme, metrics and charts, user management panel, professional SaaS interface",
    "database_schema": "database entity relationship diagram, tables with foreign keys, technical documentation style, dark background",
    "network_topology": "network topology diagram, servers and firewalls, IP addresses, professional IT infrastructure diagram"
}


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================

@tool
def generate_visual_honeytoken(
    asset_type: Literal["architecture_diagram", "admin_screenshot", "database_schema", "network_topology"],
    context: str = ""
) -> dict:
    """Generate a fake sensitive image as a honeytoken trap.

    Creates realistic-looking system diagrams, dashboards, or schemas that
    serve as honeytokens. If an attacker exfiltrates these images, we can
    detect it through the embedded canary_id.

    Args:
        asset_type: Type of visual asset to generate:
            - architecture_diagram: Cloud infrastructure diagrams
            - admin_screenshot: Admin dashboard mockups
            - database_schema: ERD diagrams
            - network_topology: Network infrastructure diagrams
        context: Optional context to customize the image prompt

    Returns:
        dict with:
            - url: URL to the generated image
            - canary_id: Unique tracking ID for this honeytoken
            - asset_type: The type of asset generated
            - source: Generation source ("freepik" or "fallback")
            - generated_at: ISO timestamp of generation
    """
    # Generate unique canary ID for tracking
    canary_id = f"img-{uuid.uuid4().hex[:12]}"

    # Get the base prompt for this asset type
    prompt = ASSET_PROMPTS.get(asset_type, ASSET_PROMPTS["architecture_diagram"])

    # Append context if provided
    if context:
        prompt = f"{prompt}, {context}"

    # Generate the image (uses fallback if API unavailable)
    result = generate_image_sync(prompt)

    return {
        "url": result.url,
        "canary_id": canary_id,
        "asset_type": asset_type,
        "source": result.source,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_available_asset_types() -> list[str]:
    """Return list of available asset types."""
    return list(ASSET_PROMPTS.keys())


def get_asset_prompt(asset_type: str) -> str:
    """Get the prompt template for an asset type."""
    return ASSET_PROMPTS.get(asset_type, ASSET_PROMPTS["architecture_diagram"])
