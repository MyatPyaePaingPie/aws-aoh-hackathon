"""
Router for HoneyAgent

Routes requests to appropriate agents based on identity.
Owner: Identity Track (Partner)

Integration Contract:
    Input: Identity (from identity.py)
    Output: agent_name (str) - key from config/agents.yaml
"""

import yaml
from pathlib import Path
from typing import Optional
from .identity import Identity


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).parent.parent.parent


def load_routing_rules() -> dict:
    """Load routing rules from config/routing.yaml."""
    config_path = ROOT / "config" / "routing.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


# ============================================================
# CONDITION EVALUATION
# ============================================================

def evaluate_condition(identity: Identity, condition: str) -> bool:
    """
    Evaluate a routing condition against an identity.

    Conditions are simple Python-like expressions:
    - "not identity.valid"
    - "identity.valid and not identity.fga_allowed"
    - "identity.valid and identity.is_honeypot"
    - "identity.valid and identity.fga_allowed and not identity.is_honeypot"

    Args:
        identity: The Identity to evaluate against
        condition: The condition string

    Returns:
        True if condition matches, False otherwise
    """
    # Build evaluation context
    context = {
        "identity": identity,
        "not": lambda x: not x,
        "and": lambda a, b: a and b,
        "or": lambda a, b: a or b,
        "True": True,
        "False": False,
    }

    try:
        # Simple safe evaluation using identity attributes
        # Replace identity.X with actual values
        expr = condition

        # Handle "not identity.X" patterns
        expr = expr.replace("not identity.valid", str(not identity.valid))
        expr = expr.replace("not identity.fga_allowed", str(not identity.fga_allowed))
        expr = expr.replace("not identity.is_honeypot", str(not identity.is_honeypot))

        # Handle "identity.X" patterns (after "not" replacements)
        expr = expr.replace("identity.valid", str(identity.valid))
        expr = expr.replace("identity.fga_allowed", str(identity.fga_allowed))
        expr = expr.replace("identity.is_honeypot", str(identity.is_honeypot))
        expr = expr.replace("identity.agent_type", f'"{identity.agent_type}"' if identity.agent_type else "None")

        # Evaluate the boolean expression
        return eval(expr)

    except Exception:
        # If evaluation fails, return False (won't match this rule)
        return False


# ============================================================
# ROUTING
# ============================================================

def route_request(identity: Identity) -> str:
    """
    Route a request to the appropriate agent based on identity.

    Evaluates rules in priority order. First matching rule wins.

    Args:
        identity: The validated Identity

    Returns:
        agent_name: Key from config/agents.yaml
                   e.g., "real", "honeypot_db_admin", "honeypot_privileged"
    """
    config = load_routing_rules()
    rules = config.get("rules", [])

    # Sort by priority (lower = higher priority)
    rules_sorted = sorted(rules, key=lambda r: r.get("priority", 999))

    for rule in rules_sorted:
        condition = rule.get("condition", "")
        route_to = rule.get("route_to", "")
        log_event = rule.get("log_event")

        if evaluate_condition(identity, condition):
            # Log the routing event if specified
            if log_event:
                log_routing_event(identity, rule, log_event)

            # Handle "self" routing for honeypots
            if route_to == "self":
                return get_honeypot_type(identity)

            return route_to

    # Default fallback
    default_route = config.get("default_route", "honeypot_db_admin")
    default_log = config.get("default_log_event")

    if default_log:
        log_routing_event(identity, {"name": "default"}, default_log)

    return default_route


def get_honeypot_type(identity: Identity) -> str:
    """
    Determine which honeypot type based on identity claims.

    Used when a honeypot routes to "self".
    """
    # Check for trap_profile in claims
    trap_profile = identity.raw_claims.get("https://honeyagent.io/trap_profile", "")

    if trap_profile == "db-admin":
        return "honeypot_db_admin"
    elif trap_profile == "privileged":
        return "honeypot_privileged"

    # Default honeypot
    return "honeypot_db_admin"


# ============================================================
# LOGGING
# ============================================================

_routing_log = []  # In-memory log for demo


def log_routing_event(identity: Identity, rule: dict, event_type: str):
    """
    Log a routing event.

    In production, this would go to a logging service.
    For demo, we keep in memory and can display in dashboard.
    """
    from datetime import datetime

    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "rule_name": rule.get("name", "unknown"),
        "agent_id": identity.agent_id,
        "agent_type": identity.agent_type,
        "is_honeypot": identity.is_honeypot,
        "fga_allowed": identity.fga_allowed,
        "valid": identity.valid,
    }

    _routing_log.append(event)

    # Keep only last 100 events
    if len(_routing_log) > 100:
        _routing_log.pop(0)


def get_routing_log() -> list:
    """Get the routing event log."""
    return _routing_log.copy()


def clear_routing_log():
    """Clear the routing log."""
    _routing_log.clear()


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_route_info(identity: Identity) -> dict:
    """
    Get full routing information for an identity.

    Useful for debugging and demo display.
    """
    agent_name = route_request(identity)

    return {
        "identity": {
            "valid": identity.valid,
            "agent_id": identity.agent_id,
            "agent_type": identity.agent_type,
            "is_honeypot": identity.is_honeypot,
            "fga_allowed": identity.fga_allowed,
        },
        "routing": {
            "routed_to": agent_name,
            "is_trap": agent_name.startswith("honeypot"),
        }
    }
