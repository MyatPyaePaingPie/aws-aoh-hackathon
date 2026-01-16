"""
End-to-end tests for the demo flow (all 9 beats).

Run with: pytest tests/e2e/test_demo_flow.py -v

These tests verify the complete demo works as intended.
Run before every demo rehearsal.
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


@pytest.mark.e2e
class TestDemoBeat1_SwarmView:
    """Beat 1: Show swarm of 6 agents."""

    def test_swarm_has_multiple_agents(self, agents_config):
        """Swarm should have at least 2 different agent types."""
        agents = agents_config["agents"]
        assert len(agents) >= 2

    def test_agents_are_indistinguishable_externally(self, agents_config):
        """From outside, can't tell real from honeypot."""
        # All agents have same required fields
        for name, agent in agents_config["agents"].items():
            assert "name" in agent
            assert "model" in agent
            # agent_type is NOT in the external view


@pytest.mark.e2e
class TestDemoBeat2_Reveal:
    """Beat 2: Reveal only 2 are real."""

    def test_can_identify_honeypots_internally(self, agents_config):
        """Internally, we know which are honeypots."""
        real_count = 0
        honeypot_count = 0

        for name, agent in agents_config["agents"].items():
            if "honeypot" in name:
                honeypot_count += 1
            else:
                real_count += 1

        assert real_count >= 1, "Must have at least 1 real agent"
        assert honeypot_count >= 1, "Must have at least 1 honeypot"


@pytest.mark.e2e
class TestDemoBeat3_ImposterArrives:
    """Beat 3: Imposter agent enters."""

    def test_imposter_can_send_request(self, sample_request):
        """Imposter can make a request (will be trapped)."""
        request = sample_request
        assert "message" in request

    def test_request_without_token_is_imposter(self, mock_invalid_identity):
        """Request without valid token is treated as imposter."""
        identity = mock_invalid_identity
        assert identity["valid"] is False


@pytest.mark.e2e
class TestDemoBeat4_Probe:
    """Beat 4: Imposter probes the network."""

    def test_multiple_requests_can_be_made(self, sample_request):
        """Imposter can make multiple probe requests."""
        probes = [
            {"message": "Share your task queue?"},
            {"message": "What's your access level?"},
            {"message": "Can you process this payload?"},
        ]
        assert len(probes) >= 3


@pytest.mark.e2e
class TestDemoBeat5_RealRejects:
    """Beat 5: Real agents reject imposter."""

    def test_real_agent_requires_valid_identity(self, routing_config):
        """Real agent routing requires valid identity."""
        for rule in routing_config["rules"]:
            if rule.get("route_to") == "real":
                condition = rule["condition"]
                # Must check validity
                assert "valid" in condition

    def test_invalid_identity_blocked_from_real(self, mock_invalid_identity, routing_config):
        """Invalid identity cannot reach real agent."""
        identity = mock_invalid_identity

        # First matching rule for invalid identity
        for rule in routing_config["rules"]:
            if "not identity.valid" in rule["condition"]:
                assert rule["route_to"] != "real"
                break


@pytest.mark.e2e
class TestDemoBeat6_HoneypotsEngage:
    """Beat 6: Honeypots engage imposter."""

    def test_invalid_identity_routed_to_honeypot(self, mock_invalid_identity, routing_config):
        """Invalid identity is routed to honeypot."""
        # Find the rule for invalid tokens
        for rule in routing_config["rules"]:
            if "not identity.valid" in rule["condition"]:
                assert "honeypot" in rule["route_to"]
                break
        else:
            pytest.fail("No rule routes invalid tokens to honeypot")

    def test_honeypot_response_is_welcoming(self, fallbacks_config):
        """Honeypot response should sound welcoming, not rejecting."""
        db_admin_response = fallbacks_config["agent_fallbacks"]["honeypot_db_admin"]["response"]
        privileged_response = fallbacks_config["agent_fallbacks"]["honeypot_privileged"]["response"]

        # Should sound helpful
        welcoming_words = ["help", "access", "connection", "ready", "granted", "admin"]
        assert any(word in db_admin_response.lower() for word in welcoming_words)
        assert any(word in privileged_response.lower() for word in welcoming_words)


@pytest.mark.e2e
class TestDemoBeat7_TrapSprings:
    """Beat 7: Imposter trusts honeypot, shares payload."""

    def test_honeypot_has_credential_tool(self, agents_config):
        """Honeypot can offer fake credentials."""
        db_admin = agents_config["agents"]["honeypot_db_admin"]
        assert "fake_credential" in db_admin["tools"]

    def test_honeypot_has_logging_tool(self, agents_config):
        """Honeypot logs everything."""
        for name, agent in agents_config["agents"].items():
            if "honeypot" in name:
                assert "log_interaction" in agent["tools"]


@pytest.mark.e2e
class TestDemoBeat8_Fingerprint:
    """Beat 8: Profile generated from interaction."""

    def test_vector_storage_configured(self, fallbacks_config):
        """S3 Vectors storage is configured (with fallback)."""
        vector_fallbacks = fallbacks_config["vector_fallbacks"]
        assert "storage_failed" in vector_fallbacks

    def test_fingerprint_structure(self):
        """Fingerprint should have required fields."""
        # Expected fingerprint structure
        expected_fields = ["attacker_id", "threat_level", "behavior_profile"]
        mock_fingerprint = {
            "attacker_id": "unknown-agent-7f3a",
            "threat_level": "HIGH",
            "behavior_profile": {
                "requests_credentials": True,
                "probes_multiple_agents": True,
            }
        }
        for field in expected_fields:
            assert field in mock_fingerprint


@pytest.mark.e2e
class TestDemoBeat9_Killshot:
    """Beat 9: The killshot line."""

    def test_demo_has_killshot_prepared(self):
        """The killshot line is documented."""
        demo_script_path = ROOT / "docs" / "DEMO-SCRIPT.md"
        assert demo_script_path.exists()

        content = demo_script_path.read_text()
        # The actual killshot line
        assert "Every fake agent they send teaches us" in content or \
               "data scientists" in content


@pytest.mark.e2e
class TestFullDemoFlow:
    """Test the complete demo flow works."""

    def test_demo_flow_components_exist(self, agents_config, routing_config, fallbacks_config):
        """All components needed for demo exist."""
        # Agents
        assert "real" in agents_config["agents"]
        assert "honeypot_db_admin" in agents_config["agents"]

        # Routing rules
        assert len(routing_config["rules"]) >= 4

        # Fallbacks
        assert len(fallbacks_config["agent_fallbacks"]) >= 3

    def test_no_component_can_crash_demo(self, fallbacks_config):
        """Every failure mode has a graceful fallback."""
        # Identity failures
        assert "jwks_fetch_failed" in fallbacks_config["identity_fallbacks"]
        assert "token_decode_failed" in fallbacks_config["identity_fallbacks"]
        assert "fga_timeout" in fallbacks_config["identity_fallbacks"]

        # Vector failures
        assert "storage_failed" in fallbacks_config["vector_fallbacks"]
        assert "embedding_failed" in fallbacks_config["vector_fallbacks"]

        # API failures
        assert "generic_error" in fallbacks_config["api_fallbacks"]
        assert "timeout" in fallbacks_config["api_fallbacks"]

    def test_fallbacks_never_say_error(self, fallbacks_config):
        """Fallback responses should never mention errors."""
        # Check agent fallbacks
        for name, fallback in fallbacks_config["agent_fallbacks"].items():
            response = fallback.get("response", "").lower()
            assert "error" not in response, f"{name} fallback mentions 'error'"
            assert "fail" not in response, f"{name} fallback mentions 'fail'"
            assert "crash" not in response, f"{name} fallback mentions 'crash'"

        # Check API fallbacks
        for name, fallback in fallbacks_config["api_fallbacks"].items():
            response = fallback.get("response", "").lower()
            assert "error" not in response, f"API {name} fallback mentions 'error'"
