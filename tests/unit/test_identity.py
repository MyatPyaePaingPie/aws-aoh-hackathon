"""
Unit tests for Identity Layer (Partner's track)

Run with: pytest tests/unit/test_identity.py -v
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


@pytest.mark.unit
@pytest.mark.identity_track
class TestIdentityValidation:
    """Test token validation logic."""

    def test_valid_identity_has_required_fields(self, mock_valid_identity):
        """Valid identity must have all required fields."""
        required = ["valid", "agent_id", "agent_type", "is_honeypot", "fga_allowed"]
        for field in required:
            assert field in mock_valid_identity, f"Missing field: {field}"

    def test_invalid_identity_has_valid_false(self, mock_invalid_identity):
        """Invalid identity must have valid=False."""
        assert mock_invalid_identity["valid"] is False

    def test_honeypot_identity_is_flagged(self, mock_honeypot_identity):
        """Honeypot identity must have is_honeypot=True."""
        assert mock_honeypot_identity["is_honeypot"] is True
        assert mock_honeypot_identity["agent_type"] == "honeypot"

    def test_fga_denied_identity_has_fga_allowed_false(self, mock_fga_denied_identity):
        """FGA-denied identity must have fga_allowed=False."""
        assert mock_fga_denied_identity["valid"] is True  # Token valid
        assert mock_fga_denied_identity["fga_allowed"] is False  # But FGA denied


@pytest.mark.unit
@pytest.mark.identity_track
class TestTokenStructure:
    """Test JWT token handling."""

    def test_valid_jwt_has_three_parts(self, valid_jwt_token):
        """Valid JWT must have header.payload.signature structure."""
        parts = valid_jwt_token.split(".")
        assert len(parts) == 3, "JWT must have 3 parts"

    def test_invalid_jwt_detected(self, invalid_jwt_token):
        """Invalid JWT should not pass structure check."""
        parts = invalid_jwt_token.split(".")
        # Either wrong number of parts or not base64-decodable
        assert len(parts) != 3 or not all(parts)


@pytest.mark.unit
@pytest.mark.identity_track
class TestIdentityFallbacks:
    """Test identity fallback behavior."""

    def test_jwks_fallback_returns_invalid(self, fallbacks_config):
        """JWKS failure should return invalid identity."""
        fallback = fallbacks_config["identity_fallbacks"]["jwks_fetch_failed"]
        assert fallback["valid"] is False

    def test_token_decode_fallback_returns_invalid(self, fallbacks_config):
        """Token decode failure should return invalid identity."""
        fallback = fallbacks_config["identity_fallbacks"]["token_decode_failed"]
        assert fallback["valid"] is False

    def test_fga_timeout_fails_open(self, fallbacks_config):
        """FGA timeout should fail open (allow access) for demo."""
        fallback = fallbacks_config["identity_fallbacks"]["fga_timeout"]
        assert fallback["fga_allowed"] is True


@pytest.mark.unit
@pytest.mark.identity_track
class TestClaimExtraction:
    """Test custom claim extraction."""

    def test_real_agent_claims(self, mock_valid_identity):
        """Real agent should have correct claims."""
        claims = mock_valid_identity["raw_claims"]
        assert "https://honeyagent.io/agent_type" in claims
        assert claims["https://honeyagent.io/agent_type"] == "real"

    def test_honeypot_claims(self, mock_honeypot_identity):
        """Honeypot should have trap_profile claim."""
        claims = mock_honeypot_identity["raw_claims"]
        assert "https://honeyagent.io/agent_type" in claims
        assert claims["https://honeyagent.io/agent_type"] == "honeypot"
        assert "https://honeyagent.io/trap_profile" in claims


@pytest.mark.unit
@pytest.mark.identity_track
class TestFGAIntegration:
    """Test FGA permission checks."""

    def test_fga_check_returns_boolean(self, mock_fga_client):
        """FGA check should return a boolean result."""
        # This tests the mock, real implementation will be similar
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            mock_fga_client.check()
        )
        assert hasattr(result, "allowed")

    def test_fga_denied_routes_to_honeypot(self, mock_fga_denied_identity, routing_config):
        """FGA denial should trigger honeypot routing."""
        # Find the rule that handles FGA denial
        for rule in routing_config["rules"]:
            if "fga_allowed" in rule["condition"] and "not" in rule["condition"]:
                assert "honeypot" in rule["route_to"]
                break
        else:
            pytest.fail("No routing rule for FGA denial")
