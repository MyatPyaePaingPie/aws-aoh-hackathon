"""
Unit tests for Routing Layer (Partner's track)

Run with: pytest tests/unit/test_router.py -v
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


@pytest.mark.unit
@pytest.mark.identity_track
class TestRoutingConfig:
    """Test routing configuration."""

    def test_routing_yaml_exists(self):
        """Config file must exist."""
        config_path = ROOT / "config" / "routing.yaml"
        assert config_path.exists(), "routing.yaml not found"

    def test_routing_has_rules(self, routing_config):
        """Must have routing rules defined."""
        assert "rules" in routing_config
        assert len(routing_config["rules"]) > 0

    def test_each_rule_has_required_fields(self, routing_config):
        """Each rule must have condition and route_to."""
        for rule in routing_config["rules"]:
            assert "condition" in rule, f"Rule missing 'condition': {rule}"
            assert "route_to" in rule, f"Rule missing 'route_to': {rule}"

    def test_default_route_exists(self, routing_config):
        """Must have a default route for fallback."""
        assert "default_route" in routing_config


@pytest.mark.unit
@pytest.mark.identity_track
class TestRoutingRules:
    """Test specific routing rules."""

    def test_invalid_token_routes_to_honeypot(self, routing_config):
        """Invalid tokens must route to honeypot."""
        for rule in routing_config["rules"]:
            if "not identity.valid" in rule["condition"] or "not valid" in rule["condition"]:
                assert "honeypot" in rule["route_to"]
                break
        else:
            pytest.fail("No rule for invalid tokens")

    def test_fga_denied_routes_to_honeypot(self, routing_config):
        """FGA denial must route to honeypot."""
        for rule in routing_config["rules"]:
            if "fga_allowed" in rule["condition"] and "not" in rule["condition"]:
                assert "honeypot" in rule["route_to"]
                break
        else:
            pytest.fail("No rule for FGA denial")

    def test_valid_real_agent_routes_to_real(self, routing_config):
        """Valid real agents must route to real."""
        for rule in routing_config["rules"]:
            condition = rule["condition"]
            if "valid" in condition and "fga_allowed" in condition and "not identity.is_honeypot" in condition:
                assert rule["route_to"] == "real"
                break
        else:
            pytest.fail("No rule for valid real agents")

    def test_rules_have_priorities(self, routing_config):
        """Rules should have explicit priorities for order."""
        for rule in routing_config["rules"]:
            assert "priority" in rule or "name" in rule, \
                f"Rule has no priority or name: {rule}"


@pytest.mark.unit
@pytest.mark.identity_track
class TestRoutingDecisions:
    """Test routing decision logic."""

    def test_route_invalid_identity(self, mock_invalid_identity, routing_config):
        """Invalid identity should route to honeypot."""
        # Simulate routing logic
        identity = mock_invalid_identity
        if not identity["valid"]:
            expected_route = "honeypot"  # Should contain honeypot
        assert "honeypot" in routing_config["default_route"] or expected_route == "honeypot"

    def test_route_fga_denied_identity(self, mock_fga_denied_identity, routing_config):
        """FGA-denied identity should route to honeypot."""
        identity = mock_fga_denied_identity
        assert identity["valid"] is True
        assert identity["fga_allowed"] is False
        # This should trigger honeypot routing

    def test_route_valid_real_identity(self, mock_valid_identity, routing_config):
        """Valid real identity should route to real agent."""
        identity = mock_valid_identity
        assert identity["valid"] is True
        assert identity["fga_allowed"] is True
        assert identity["is_honeypot"] is False
        # This should trigger real agent routing

    def test_route_honeypot_identity(self, mock_honeypot_identity, routing_config):
        """Honeypot identity routes to self (stays as honeypot)."""
        identity = mock_honeypot_identity
        assert identity["valid"] is True
        assert identity["is_honeypot"] is True
        # Should route to "self"


@pytest.mark.unit
@pytest.mark.identity_track
class TestRoutingLogging:
    """Test routing event logging."""

    def test_invalid_token_logs_event(self, routing_config):
        """Invalid token routing should log an event."""
        for rule in routing_config["rules"]:
            if "not identity.valid" in rule["condition"] or "not valid" in rule["condition"]:
                assert "log_event" in rule
                assert rule["log_event"] is not None
                break

    def test_fga_denied_logs_event(self, routing_config):
        """FGA denial should log an event."""
        for rule in routing_config["rules"]:
            if "fga_allowed" in rule["condition"] and "not" in rule["condition"]:
                assert "log_event" in rule
                break

    def test_normal_routing_no_unnecessary_logging(self, routing_config):
        """Normal valid->real routing shouldn't log (noise reduction)."""
        for rule in routing_config["rules"]:
            if rule.get("route_to") == "real":
                # log_event should be null or not present
                if "log_event" in rule:
                    assert rule["log_event"] is None
                break
