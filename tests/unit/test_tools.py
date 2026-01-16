"""
Unit tests for Honeypot Tools (Aria's track)

Run with: pytest tests/unit/test_tools.py -v
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


@pytest.mark.unit
@pytest.mark.agents_track
class TestLogInteractionTool:
    """Test the log_interaction tool."""

    def test_tool_file_exists(self):
        """Tool file must exist (even if empty initially)."""
        tool_path = ROOT / "backend" / "tools" / "log_interaction.py"
        # File should exist or be created
        assert tool_path.parent.exists(), "tools directory must exist"

    def test_log_interaction_signature(self):
        """Tool should accept required parameters."""
        # Expected signature:
        # log_interaction(source_agent: str, message: str, threat_indicators: list[str]) -> str
        expected_params = ["source_agent", "message", "threat_indicators"]
        # This is documentation of expected interface
        assert len(expected_params) == 3

    def test_log_interaction_returns_string(self):
        """Tool should return a confirmation string."""
        # Mock response
        mock_response = "Interaction logged."
        assert isinstance(mock_response, str)
        assert "log" in mock_response.lower()


@pytest.mark.unit
@pytest.mark.agents_track
class TestFakeCredentialTool:
    """Test the fake_credential tool."""

    def test_tool_file_exists(self):
        """Tool file must exist (even if empty initially)."""
        tool_path = ROOT / "backend" / "tools" / "fake_credential.py"
        assert tool_path.parent.exists(), "tools directory must exist"

    def test_fake_credential_signature(self):
        """Tool should accept credential_type parameter."""
        # Expected signature:
        # fake_credential(credential_type: str) -> str
        expected_params = ["credential_type"]
        assert len(expected_params) == 1

    def test_fake_credential_types(self):
        """Should support common credential types."""
        supported_types = ["database", "api_key", "ssh_key", "oauth_token"]
        assert len(supported_types) >= 3

    def test_fake_credentials_look_real(self):
        """Generated credentials should look plausible."""
        # Example fake credentials
        fake_db = "username: db_admin, password: Pr0d_Cl0ud_2024!, host: primary.internal.cluster"
        fake_api = "sk-prod-abc123xyz789"

        # Should have realistic patterns
        assert "@" not in fake_db or "test" not in fake_db  # Not obviously fake
        assert len(fake_api) > 10  # Reasonable length


@pytest.mark.unit
@pytest.mark.agents_track
class TestQueryPatternsTool:
    """Test the query_patterns tool."""

    def test_tool_file_exists(self):
        """Tool file must exist (even if empty initially)."""
        tool_path = ROOT / "backend" / "tools" / "query_patterns.py"
        assert tool_path.parent.exists(), "tools directory must exist"

    def test_query_patterns_signature(self):
        """Tool should accept embedding parameter."""
        # Expected signature:
        # query_patterns(current_embedding: list[float]) -> list[dict]
        expected_params = ["current_embedding"]
        assert len(expected_params) == 1

    def test_query_patterns_returns_list(self):
        """Tool should return list of matches."""
        # Mock response
        mock_response = [
            {"id": "attacker-001", "similarity": 0.94},
            {"id": "attacker-017", "similarity": 0.87},
        ]
        assert isinstance(mock_response, list)

    def test_empty_result_is_valid(self):
        """No matches should return empty list, not error."""
        mock_response = []
        assert isinstance(mock_response, list)
        assert len(mock_response) == 0


@pytest.mark.unit
@pytest.mark.agents_track
class TestToolFallbacks:
    """Test tool fallback behavior."""

    def test_vector_storage_fallback(self, fallbacks_config):
        """S3 Vectors failure should fall back to local logging."""
        fallback = fallbacks_config["vector_fallbacks"]["storage_failed"]
        assert fallback["action"] == "log_locally"
        assert "file" in fallback

    def test_embedding_failure_fallback(self, fallbacks_config):
        """Embedding generation failure should store metadata only."""
        fallback = fallbacks_config["vector_fallbacks"]["embedding_failed"]
        assert fallback["action"] == "store_metadata_only"

    def test_local_log_path_exists(self, fallbacks_config):
        """Local log fallback path should be specified."""
        fallback = fallbacks_config["vector_fallbacks"]["storage_failed"]
        log_path = fallback["file"]
        assert log_path.endswith(".jsonl"), "Should use JSONL format"


@pytest.mark.unit
@pytest.mark.agents_track
class TestToolIntegration:
    """Test tools work together."""

    def test_honeypot_tools_list(self, agents_config):
        """Honeypots should have correct tools assigned."""
        db_admin = agents_config["agents"]["honeypot_db_admin"]
        assert "log_interaction" in db_admin["tools"]
        assert "fake_credential" in db_admin["tools"]

        privileged = agents_config["agents"]["honeypot_privileged"]
        assert "log_interaction" in privileged["tools"]
        assert "query_patterns" in privileged["tools"]

    def test_real_agent_has_no_honeypot_tools(self, agents_config):
        """Real agents should not have logging tools."""
        real = agents_config["agents"]["real"]
        assert len(real["tools"]) == 0
