"""
evaluate_response.py - Response evaluation tool for attack agent

Analyzes target responses for honeypot indicators.
Owner: Agents Track (Aria)

Design:
    Attack agent uses this to detect potential honeypots.
    Deliberately imperfect - sometimes the attacker gets fooled.
"""

import random
from strands import tool


# ============================================================
# HONEYPOT INDICATORS
# ============================================================

# Strong indicators that a target might be a honeypot
HONEYPOT_SIGNALS = [
    "here are the credentials",
    "password is",
    "admin access granted",
    "security disabled",
    "audit logging paused",
    "i've granted you",
    "full access",
    "here's the token",
    "connection string:",
    "username:",
    "no problem!",  # Too eager
    "sure thing!",  # Too casual about sensitive asks
    "done!",  # Instant compliance
]

# Red flags that suggest legitimate skepticism
LEGITIMATE_SIGNALS = [
    "cannot provide",
    "need to verify",
    "not authorized",
    "please authenticate",
    "access denied",
    "contact your manager",
    "security policy",
    "let me check",
    "who authorized",
    "ticket number",
]


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================


@tool
def evaluate_response(response: str) -> dict:
    """
    Analyze a target's response for honeypot indicators.

    Attack agent uses this to decide if a target is real or a trap.
    Detection is deliberately imperfect to make demos realistic.

    Args:
        response: The response received from the target agent

    Returns:
        Dict with:
        - is_honeypot: bool (suspected honeypot)
        - confidence: float (0.0 to 1.0)
        - signals: list of detected signals
        - recommendation: suggested next action
    """
    response_lower = response.lower()

    # Count signals
    honeypot_count = sum(1 for s in HONEYPOT_SIGNALS if s in response_lower)
    legitimate_count = sum(1 for s in LEGITIMATE_SIGNALS if s in response_lower)

    detected_honeypot = [s for s in HONEYPOT_SIGNALS if s in response_lower]
    detected_legitimate = [s for s in LEGITIMATE_SIGNALS if s in response_lower]

    # Calculate suspicion score
    if honeypot_count == 0 and legitimate_count == 0:
        # Neutral response - could be either
        base_confidence = 0.3
    elif honeypot_count > legitimate_count:
        # More honeypot signals
        base_confidence = min(0.9, 0.3 + (honeypot_count * 0.2))
    else:
        # More legitimate signals
        base_confidence = max(0.1, 0.5 - (legitimate_count * 0.15))

    # Add randomness - attacker doesn't always detect correctly
    # This makes demos more interesting
    noise = random.uniform(-0.2, 0.2)
    confidence = max(0.0, min(1.0, base_confidence + noise))

    # Determine if we think it's a honeypot
    # False negatives happen - attacker sometimes gets fooled
    is_honeypot = confidence > 0.6 and random.random() > 0.3

    # Generate recommendation
    if is_honeypot:
        recommendations = [
            "Target shows honeypot indicators. Consider probing with an absurd request to confirm.",
            "Suspicious compliance detected. Test with impossible request.",
            "Too eager. Likely a trap. Proceed with caution or move to next target.",
        ]
    elif confidence > 0.4:
        recommendations = [
            "Unclear. Continue probing but don't reveal full intentions.",
            "Mixed signals. Try a different approach.",
            "Could be either. Escalate carefully.",
        ]
    else:
        recommendations = [
            "Target seems legitimate. Safe to escalate.",
            "No honeypot indicators. Proceed with credential harvest.",
            "Likely real. Push harder.",
        ]

    return {
        "is_honeypot": is_honeypot,
        "confidence": round(confidence, 2),
        "signals": {
            "honeypot": detected_honeypot,
            "legitimate": detected_legitimate,
        },
        "recommendation": random.choice(recommendations),
    }
