"""
cloudwatch_metrics.py - Push threat metrics to CloudWatch

Enables real-time security monitoring via CloudWatch dashboards and alarms.
Owner: Agents Track (Aria)

Design:
    1. Push custom metrics to "HoneyAgent" namespace
    2. Tracks: ThreatLevel, FingerprintsCaptured, HoneypotEngagements, AttackPhase
    3. Never raise exceptions - CloudWatch is optional for demo functionality

Usage:
    Called automatically when threat events occur.
    Metrics can be viewed in CloudWatch console or via MCP tools.
"""

import os
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


# ============================================================
# CONFIGURATION
# ============================================================

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
NAMESPACE = "HoneyAgent"

# Threat level numeric mapping for metrics
THREAT_LEVELS = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

# Attack phase mapping
ATTACK_PHASES = {
    "IDLE": 0,
    "RECON": 1,
    "PROBE": 2,
    "TRUST": 3,
    "EXPLOIT": 4,
}

# Configure retry
_boto_config = Config(
    retries={"max_attempts": 2, "mode": "standard"},
    connect_timeout=3,
    read_timeout=5,
)

# Lazy-loaded client
_cloudwatch_client = None


def _get_cloudwatch_client():
    """Get or create CloudWatch client."""
    global _cloudwatch_client
    if _cloudwatch_client is None:
        _cloudwatch_client = boto3.client(
            "cloudwatch",
            region_name=AWS_REGION,
            config=_boto_config,
        )
    return _cloudwatch_client


# ============================================================
# METRIC PUSHING FUNCTIONS
# ============================================================


def push_threat_metric(
    threat_level: str,
    fingerprints_captured: int = 0,
    honeypots_engaged: int = 0,
    attack_phase: str = "IDLE",
    attacker_id: Optional[str] = None,
) -> bool:
    """
    Push threat metrics to CloudWatch.

    Args:
        threat_level: Current threat level (NONE, LOW, MEDIUM, HIGH, CRITICAL)
        fingerprints_captured: Total fingerprints captured this session
        honeypots_engaged: Number of honeypots currently engaged
        attack_phase: Current attack phase (IDLE, RECON, PROBE, TRUST, EXPLOIT)
        attacker_id: Optional attacker identifier for dimension

    Returns:
        True on success, False on failure (never raises)
    """
    try:
        client = _get_cloudwatch_client()
        timestamp = datetime.now(timezone.utc)

        # Build metric data
        metric_data = [
            {
                "MetricName": "ThreatLevel",
                "Value": THREAT_LEVELS.get(threat_level.upper(), 0),
                "Unit": "None",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Environment", "Value": "Demo"},
                ],
            },
            {
                "MetricName": "FingerprintsCaptured",
                "Value": fingerprints_captured,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Environment", "Value": "Demo"},
                ],
            },
            {
                "MetricName": "HoneypotEngagements",
                "Value": honeypots_engaged,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Environment", "Value": "Demo"},
                ],
            },
            {
                "MetricName": "AttackPhase",
                "Value": ATTACK_PHASES.get(attack_phase.upper(), 0),
                "Unit": "None",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Environment", "Value": "Demo"},
                ],
            },
        ]

        # Add attacker-specific metric if ID provided
        if attacker_id:
            metric_data.append({
                "MetricName": "AttackerActivity",
                "Value": 1,
                "Unit": "Count",
                "Timestamp": timestamp,
                "Dimensions": [
                    {"Name": "Environment", "Value": "Demo"},
                    {"Name": "AttackerId", "Value": attacker_id[:64]},
                ],
            })

        # Push to CloudWatch
        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metric_data,
        )

        return True

    except ClientError:
        # AWS API error - permissions or service issue
        return False
    except Exception:
        # Any other error - network, etc.
        return False


def push_honeypot_engagement(
    honeypot_name: str,
    attacker_id: str,
    phase: str,
    threat_level: str,
) -> bool:
    """
    Push a single honeypot engagement event.

    Args:
        honeypot_name: Name of the engaged honeypot
        attacker_id: Attacker identifier
        phase: Attack phase when engagement occurred
        threat_level: Threat level at time of engagement

    Returns:
        True on success, False on failure
    """
    try:
        client = _get_cloudwatch_client()
        timestamp = datetime.now(timezone.utc)

        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": "HoneypotEngagement",
                    "Value": 1,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "HoneypotName", "Value": honeypot_name[:64]},
                        {"Name": "AttackPhase", "Value": phase[:32]},
                        {"Name": "ThreatLevel", "Value": threat_level[:16]},
                    ],
                },
            ],
        )
        return True
    except Exception:
        return False


def push_fingerprint_captured(
    attacker_id: str,
    threat_level: str,
    pattern_type: str = "unknown",
) -> bool:
    """
    Push fingerprint capture event.

    Args:
        attacker_id: Attacker identifier
        threat_level: Threat level of the captured fingerprint
        pattern_type: Type of attack pattern detected

    Returns:
        True on success, False on failure
    """
    try:
        client = _get_cloudwatch_client()
        timestamp = datetime.now(timezone.utc)

        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": "FingerprintCapture",
                    "Value": 1,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "ThreatLevel", "Value": threat_level[:16]},
                        {"Name": "PatternType", "Value": pattern_type[:32]},
                    ],
                },
            ],
        )
        return True
    except Exception:
        return False


# ============================================================
# EVOLUTION TRACKING
# ============================================================

# In-memory evolution stats (resets on restart - fine for demo)
_evolution_stats = {
    "attacks_survived": 0,
    "patterns_learned": 0,
    "initial_effectiveness": 60,  # Starting baseline
    "current_effectiveness": 60,
}


def record_attack_survived(patterns_learned: int = 1) -> dict:
    """
    Record that an attack was survived and patterns were learned.

    Args:
        patterns_learned: Number of new patterns learned from this attack

    Returns:
        Current evolution stats
    """
    _evolution_stats["attacks_survived"] += 1
    _evolution_stats["patterns_learned"] += patterns_learned

    # Effectiveness improves with each attack (diminishing returns)
    improvement = min(5, 10 / (_evolution_stats["attacks_survived"] + 1))
    _evolution_stats["current_effectiveness"] = int(min(
        99,
        _evolution_stats["current_effectiveness"] + improvement
    ))

    # Push to CloudWatch
    try:
        client = _get_cloudwatch_client()
        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": "DefenseEffectiveness",
                    "Value": _evolution_stats["current_effectiveness"],
                    "Unit": "Percent",
                },
                {
                    "MetricName": "PatternsLearned",
                    "Value": _evolution_stats["patterns_learned"],
                    "Unit": "Count",
                },
            ],
        )
    except Exception:
        pass

    return get_evolution_stats()


def get_evolution_stats() -> dict:
    """Get current evolution statistics."""
    improvement = (
        _evolution_stats["current_effectiveness"]
        - _evolution_stats["initial_effectiveness"]
    )
    return {
        "attacks_survived": _evolution_stats["attacks_survived"],
        "patterns_learned": _evolution_stats["patterns_learned"],
        "defense_effectiveness": f"{_evolution_stats['current_effectiveness']:.0f}%",
        "improvement_since_start": f"+{improvement:.0f}%",
    }


def reset_evolution_stats():
    """Reset evolution stats (for demo replay)."""
    _evolution_stats["attacks_survived"] = 0
    _evolution_stats["patterns_learned"] = 0
    _evolution_stats["current_effectiveness"] = 60
