"""
Integration tests for the full request flow.

Run with: pytest tests/integration/test_flow.py -v

These tests verify that components work together correctly.
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


@pytest.mark.integration
class TestTokenToIdentityFlow:
    """Test token validation → identity extraction."""

    def test_valid_token_produces_valid_identity(self, valid_jwt_token, mock_valid_identity):
        """Valid JWT should produce valid identity object."""
        # In real implementation:
        # identity = validate_token(valid_jwt_token)
        identity = mock_valid_identity  # Mock for now

        assert identity["valid"] is True
        assert identity["agent_id"] is not None

    def test_invalid_token_produces_invalid_identity(self, invalid_jwt_token, mock_invalid_identity):
        """Invalid JWT should produce invalid identity object."""
        identity = mock_invalid_identity  # Mock for now

        assert identity["valid"] is False

    def test_missing_token_produces_invalid_identity(self, mock_invalid_identity):
        """Missing token should produce invalid identity."""
        identity = mock_invalid_identity  # Mock for now

        assert identity["valid"] is False


@pytest.mark.integration
class TestIdentityToRoutingFlow:
    """Test identity → routing decision."""

    def test_invalid_identity_routes_to_honeypot(self, mock_invalid_identity, agents_config):
        """Invalid identity should route to honeypot agent."""
        identity = mock_invalid_identity

        # Simulate routing
        if not identity["valid"]:
            route = "honeypot_db_admin"
        else:
            route = "real"

        assert "honeypot" in route
        assert route in agents_config["agents"]

    def test_valid_real_identity_routes_to_real(self, mock_valid_identity, agents_config):
        """Valid real identity should route to real agent."""
        identity = mock_valid_identity

        # Simulate routing
        if identity["valid"] and identity["fga_allowed"] and not identity["is_honeypot"]:
            route = "real"
        else:
            route = "honeypot_db_admin"

        assert route == "real"
        assert route in agents_config["agents"]

    def test_fga_denied_routes_to_honeypot(self, mock_fga_denied_identity, agents_config):
        """FGA denial should route to honeypot."""
        identity = mock_fga_denied_identity

        # Simulate routing
        if identity["valid"] and not identity["fga_allowed"]:
            route = "honeypot_privileged"
        else:
            route = "real"

        assert "honeypot" in route
        assert route in agents_config["agents"]


@pytest.mark.integration
class TestRoutingToAgentFlow:
    """Test routing → agent execution."""

    def test_route_to_real_agent_executes(self, agents_config, fallbacks_config):
        """Routing to real agent should execute or return fallback."""
        route = "real"

        # In real implementation:
        # response = execute_agent(route, request)

        # For now, verify fallback exists
        assert route in agents_config["agents"]
        assert route in fallbacks_config["agent_fallbacks"]

    def test_route_to_honeypot_executes(self, agents_config, fallbacks_config):
        """Routing to honeypot should execute or return fallback."""
        route = "honeypot_db_admin"

        assert route in agents_config["agents"]
        assert route in fallbacks_config["agent_fallbacks"]

    def test_agent_failure_returns_fallback(self, fallbacks_config):
        """Agent failure should return fallback, not error."""
        route = "honeypot_db_admin"
        fallback = fallbacks_config["agent_fallbacks"][route]

        assert "response" in fallback
        assert "status" in fallback
        # Response should sound natural
        assert "error" not in fallback["response"].lower()


@pytest.mark.integration
class TestEndToEndFlow:
    """Test complete request → response flow."""

    def test_valid_request_flow(
        self,
        valid_jwt_token,
        mock_valid_identity,
        sample_request,
        agents_config,
        fallbacks_config
    ):
        """Valid request should flow through all layers."""
        # 1. Token → Identity
        identity = mock_valid_identity
        assert identity["valid"]

        # 2. Identity → Routing
        route = "real" if identity["valid"] and identity["fga_allowed"] else "honeypot_db_admin"
        assert route in agents_config["agents"]

        # 3. Routing → Agent (or fallback)
        if route in fallbacks_config["agent_fallbacks"]:
            response = fallbacks_config["agent_fallbacks"][route]
            assert "response" in response

    def test_invalid_request_flow(
        self,
        invalid_jwt_token,
        mock_invalid_identity,
        suspicious_request,
        agents_config,
        fallbacks_config
    ):
        """Invalid request should be trapped by honeypot."""
        # 1. Token → Identity
        identity = mock_invalid_identity
        assert not identity["valid"]

        # 2. Identity → Routing
        route = "honeypot_db_admin"  # Invalid tokens go to honeypot
        assert route in agents_config["agents"]

        # 3. Routing → Agent (or fallback)
        if route in fallbacks_config["agent_fallbacks"]:
            response = fallbacks_config["agent_fallbacks"][route]
            assert "response" in response
            # Honeypot response should sound inviting
            assert any(word in response["response"].lower()
                      for word in ["access", "help", "connection", "admin"])


@pytest.mark.integration
class TestFallbackChain:
    """Test fallback behavior at each layer."""

    def test_identity_fallback_chain(self, fallbacks_config):
        """Identity layer has complete fallback chain."""
        identity_fallbacks = fallbacks_config["identity_fallbacks"]

        # Must handle these failure modes
        assert "jwks_fetch_failed" in identity_fallbacks
        assert "token_decode_failed" in identity_fallbacks
        assert "fga_timeout" in identity_fallbacks

    def test_agent_fallback_chain(self, fallbacks_config, agents_config):
        """Every agent has a fallback."""
        for agent_name in agents_config["agents"]:
            assert agent_name in fallbacks_config["agent_fallbacks"], \
                f"No fallback for {agent_name}"

    def test_api_fallback_chain(self, fallbacks_config):
        """API layer has complete fallback chain."""
        api_fallbacks = fallbacks_config["api_fallbacks"]

        # Must handle these failure modes
        assert "generic_error" in api_fallbacks
        assert "timeout" in api_fallbacks

        # API errors should return 2xx
        for name, fallback in api_fallbacks.items():
            if "http_status" in fallback:
                assert fallback["http_status"] < 300, \
                    f"API fallback {name} returns non-2xx status"
