# Sponsor Integrations
# These modules integrate external sponsor APIs with fallback handling

import os

# Check for sponsor API keys
TONIC_API_KEY = os.getenv("TONIC_API_KEY") or os.getenv("FABRICATE_API_KEY")
YUTORI_API_KEY = os.getenv("YUTORI_API_KEY")
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY")
FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")

# TinyFish/AgentQL exports
from backend.integrations.tinyfish import (
    extract_patterns_agentql,
    extract_patterns_sync,
    map_intent_to_mitre,
    calculate_risk_score,
)

# Yutori exports
from backend.integrations.yutori import (
    browse,
    create_scout,
    get_scout_status,
    delete_scout,
    simulate_attacker_probe,
    parse_webhook_alert,
    demo_simulate_threat_detection,
    get_integration_status as get_yutori_status,
    BrowseResult,
    ScoutResult,
    ThreatAlert,
)

# Tonic Fabricate exports
from backend.integrations.tonic_fabricate import (
    TonicFabricateClient,
    generate_credential as tonic_generate_credential,
    get_client as get_tonic_client,
    is_configured as tonic_is_configured,
    SyntheticCredential,
)

# Freepik exports
from backend.integrations.freepik import (
    FreepikClient,
    generate_image as freepik_generate_image,
    generate_image_sync as freepik_generate_image_sync,
    search_icons as freepik_search_icons,
    get_client as get_freepik_client,
    is_configured as freepik_is_configured,
    GeneratedImage,
)


def get_sponsor_status() -> dict:
    """Return status of sponsor API integrations."""
    return {
        "tonic_fabricate": {
            "configured": tonic_is_configured(),
            "description": "Synthetic data generation for realistic fake credentials"
        },
        "yutori": {
            "configured": bool(YUTORI_API_KEY),
            "description": "Threat scouting and simulation"
        },
        "tinyfish": {
            "configured": bool(TINYFISH_API_KEY),
            "description": "AgentQL pattern extraction"
        },
        "freepik": {
            "configured": freepik_is_configured(),
            "description": "AI image generation for visual assets"
        }
    }


__all__ = [
    # Sponsor status
    "get_sponsor_status",
    # TinyFish/AgentQL
    "extract_patterns_agentql",
    "extract_patterns_sync",
    "map_intent_to_mitre",
    "calculate_risk_score",
    # Yutori
    "browse",
    "create_scout",
    "get_scout_status",
    "delete_scout",
    "simulate_attacker_probe",
    "parse_webhook_alert",
    "demo_simulate_threat_detection",
    "get_yutori_status",
    "BrowseResult",
    "ScoutResult",
    "ThreatAlert",
    # Tonic Fabricate
    "TonicFabricateClient",
    "tonic_generate_credential",
    "get_tonic_client",
    "tonic_is_configured",
    "SyntheticCredential",
    # Freepik
    "FreepikClient",
    "freepik_generate_image",
    "freepik_generate_image_sync",
    "freepik_search_icons",
    "get_freepik_client",
    "freepik_is_configured",
    "GeneratedImage",
    # API Keys
    "TONIC_API_KEY",
    "YUTORI_API_KEY",
    "TINYFISH_API_KEY",
    "FREEPIK_API_KEY",
]
