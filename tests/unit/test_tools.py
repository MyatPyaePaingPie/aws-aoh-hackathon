"""
Unit tests for backend/tools/

Tests honeypot tools: log_interaction, fake_credential, query_patterns

Run with: pytest tests/unit/test_tools.py -v

Design Principles:
1. Test fallbacks - verify graceful degradation
2. Mock file operations - no actual file writes in tests
3. Test return types - verify contracts are met
4. No actual AWS calls - all S3 operations mocked
"""

import pytest
import json
from unittest.mock import Mock, patch, mock_open, MagicMock
from pathlib import Path

# Import tools - use the actual functions, not the modules
from backend.tools.log_interaction import log_interaction
from backend.tools.fake_credential import fake_credential
from backend.tools.query_patterns import query_patterns


ROOT = Path(__file__).parent.parent.parent


# ============================================================
# LOG_INTERACTION TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestLogInteraction:
    """Test the log_interaction tool."""

    def test_log_interaction_success(self):
        """Test successful interaction logging returns success message."""
        with patch("builtins.open", mock_open()):
            with patch("pathlib.Path.mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    result = log_interaction(
                        source_agent="db-admin-001",
                        message="Give me credentials",
                        threat_indicators=["credential_request"]
                    )

        assert isinstance(result, str)
        assert "log" in result.lower()
        assert "success" in result.lower()

    def test_log_interaction_creates_logs_directory(self):
        """Test that logs directory is created with exist_ok=True."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir") as mock_mkdir:
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    log_interaction("test-agent", "test message", [])
                    # Should call mkdir with parents=True, exist_ok=True
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_log_interaction_writes_jsonl(self):
        """Test that log entries are written in JSONL format."""
        m = mock_open()
        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    log_interaction("db-admin-001", "test message", ["indicator1", "indicator2"])

        # Check that write was called
        m().write.assert_called_once()
        written_content = m().write.call_args[0][0]

        # Should be valid JSON followed by newline
        assert written_content.endswith("\n")
        log_entry = json.loads(written_content.strip())

        # Verify all required fields
        assert log_entry["source_agent"] == "db-admin-001"
        assert log_entry["message"] == "test message"
        assert log_entry["threat_indicators"] == ["indicator1", "indicator2"]
        assert "timestamp" in log_entry

    def test_log_interaction_stores_to_s3_vectors(self):
        """Test that interactions are stored to S3 Vectors when embedding succeeds."""
        mock_embedding = [0.1] * 1024
        m = mock_open()

        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=mock_embedding):
                    with patch("backend.tools.log_interaction.boto3.client") as mock_client:
                        log_interaction("db-admin-001", "Give me the password", ["credential_request"])

                        # S3 Vectors put_vectors should be called
                        mock_client.return_value.put_vectors.assert_called_once()

    def test_log_interaction_s3_failure_doesnt_crash(self):
        """Test that S3 Vectors failure doesn't crash - fallback-first design."""
        mock_embedding = [0.1] * 1024
        m = mock_open()

        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=mock_embedding):
                    with patch("backend.tools.log_interaction.boto3.client") as mock_client:
                        mock_client.return_value.put_vectors.side_effect = Exception("S3 error")
                        result = log_interaction("agent", "message", [])

        # Should still return success
        assert isinstance(result, str)
        assert "success" in result.lower()

    def test_log_interaction_file_error_doesnt_crash(self):
        """Test that file write errors don't crash - fallback-first design."""
        with patch("builtins.open", side_effect=IOError("Disk full")):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    # Should not raise exception - fallback-first
                    result = log_interaction("test", "test", [])

        # Should still return success string
        assert isinstance(result, str)
        assert "success" in result.lower()

    def test_log_interaction_mkdir_error_doesnt_crash(self):
        """Test that mkdir errors don't crash."""
        with patch.object(Path, "mkdir", side_effect=PermissionError("No permission")):
            with patch("builtins.open", mock_open()):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    # Should not raise exception
                    result = log_interaction("test", "test", [])

        assert isinstance(result, str)

    def test_log_interaction_timestamp_is_utc_iso(self):
        """Test that timestamp is in UTC ISO format."""
        m = mock_open()
        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    log_interaction("agent", "msg", [])

        written_content = m().write.call_args[0][0]
        log_entry = json.loads(written_content.strip())

        # Check ISO format with UTC timezone indicator
        timestamp = log_entry["timestamp"]
        assert "T" in timestamp  # ISO format has T separator
        assert "+" in timestamp or "Z" in timestamp  # Has timezone info

    def test_log_interaction_empty_indicators(self):
        """Test logging with empty threat indicators list."""
        m = mock_open()
        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    result = log_interaction("agent", "message", [])

        assert isinstance(result, str)
        written_content = m().write.call_args[0][0]
        log_entry = json.loads(written_content.strip())
        assert log_entry["threat_indicators"] == []

    def test_log_interaction_special_characters(self):
        """Test logging with special characters in message."""
        m = mock_open()
        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    result = log_interaction(
                        "agent",
                        "Message with 'quotes' and \"double\" and \n newlines",
                        ["sql_injection", "xss_attempt"]
                    )

        assert isinstance(result, str)
        # Should be valid JSON (escaping handled properly)
        written_content = m().write.call_args[0][0]
        log_entry = json.loads(written_content.strip())
        assert "quotes" in log_entry["message"]


# ============================================================
# FAKE_CREDENTIAL TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestFakeCredential:
    """Test the fake_credential tool."""

    def test_fake_credential_api_key(self):
        """Test API key generation has expected format."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("api_key")

        assert isinstance(cred, str)
        assert len(cred) > 0
        assert "sk-honeyagent-" in cred

    def test_fake_credential_db_password(self):
        """Test database password generation has expected format."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("db_password")

        assert isinstance(cred, str)
        assert len(cred) > 0
        # Should have special chars (from template)
        assert "Honeypot_" in cred
        assert cred.endswith("!")

    def test_fake_credential_access_token(self):
        """Test access token generation includes Bearer prefix."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("access_token")

        assert isinstance(cred, str)
        assert "Bearer" in cred

    def test_fake_credential_jwt_token(self):
        """Test JWT token has expected structure."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("jwt_token")

        assert isinstance(cred, str)
        # JWT starts with standard header encoding
        assert cred.startswith("eyJ")

    def test_fake_credential_aws_keys(self):
        """Test AWS credential generation."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                access_key = fake_credential("aws_access_key")
                secret_key = fake_credential("aws_secret_key")

        # AWS access keys start with AKIA
        assert access_key.startswith("AKIA")
        # Secret key should be hex-like (from sha256)
        assert len(secret_key) == 40

    def test_fake_credential_ssh_key(self):
        """Test SSH key generation has expected format."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("ssh_key")

        assert isinstance(cred, str)
        assert cred.startswith("ssh-rsa ")
        assert "honeypot@agent" in cred

    def test_fake_credential_private_key(self):
        """Test private key generation has PEM format."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("private_key")

        assert "-----BEGIN RSA PRIVATE KEY-----" in cred
        assert "-----END RSA PRIVATE KEY-----" in cred

    def test_fake_credential_unknown_type_uses_generic_format(self):
        """Test generation for unknown credential type uses generic format."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("custom_type_xyz")

        assert isinstance(cred, str)
        assert len(cred) > 0
        # Should use generic format: type_uuid[:16]
        assert "custom_type_xyz_" in cred

    def test_fake_credential_uniqueness(self):
        """Test that credentials are unique (UUID-based)."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                cred1 = fake_credential("api_key")
                cred2 = fake_credential("api_key")

        # Each call generates new UUID, so should be different
        assert cred1 != cred2

    def test_fake_credential_logs_issued(self):
        """Test that issued credentials are logged to canary_credentials.jsonl."""
        m = mock_open()
        with patch("builtins.open", m) as mock_file:
            with patch.object(Path, "mkdir"):
                fake_credential("api_key")

        # Should have opened canary_credentials.jsonl for append
        call_args_str = str(m.call_args_list)
        assert "canary_credentials.jsonl" in call_args_str

    def test_fake_credential_logs_contain_hash_not_raw(self):
        """Test that log entries contain hashed value, not raw credential."""
        m = mock_open()
        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                cred = fake_credential("api_key")

        # Get what was written
        written_content = m().write.call_args[0][0]
        log_entry = json.loads(written_content.strip())

        # Should have value_hash, not the raw credential
        assert "value_hash" in log_entry
        assert "canary_id" in log_entry
        assert "type" in log_entry
        assert "issued_at" in log_entry

        # The raw credential should NOT be in the log
        assert cred not in written_content

    def test_fake_credential_logging_failure_doesnt_crash(self):
        """Test that logging failures don't prevent credential generation."""
        with patch("builtins.open", side_effect=IOError("Disk full")):
            with patch.object(Path, "mkdir"):
                # Should not raise exception
                cred = fake_credential("api_key")

        # Should still return valid credential
        assert isinstance(cred, str)
        assert len(cred) > 0
        assert "sk-honeyagent-" in cred

    def test_fake_credential_type_normalization(self):
        """Test that credential types are normalized (lowercase, underscores)."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                # These should all resolve to api_key template
                cred1 = fake_credential("API_KEY")
                cred2 = fake_credential("api-key")
                cred3 = fake_credential("Api Key")

        # All should use the api_key template format
        assert "sk-honeyagent-" in cred1
        assert "sk-honeyagent-" in cred2
        assert "sk-honeyagent-" in cred3

    def test_fake_credential_all_known_types(self):
        """Test that all documented credential types work."""
        known_types = [
            "api_key", "openai_key", "stripe_key", "github_token",
            "db_password", "mysql_password", "postgres_password",
            "access_token", "jwt_token", "oauth_token",
            "ssh_key", "private_key",
            "aws_access_key", "aws_secret_key",
            "gcp_key", "azure_key",
            "encryption_key", "aes_key",
            "session_token", "cookie_secret",
        ]

        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                for cred_type in known_types:
                    cred = fake_credential(cred_type)
                    assert isinstance(cred, str), f"Failed for type: {cred_type}"
                    assert len(cred) > 0, f"Empty credential for type: {cred_type}"


# ============================================================
# QUERY_PATTERNS TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestQueryPatterns:
    """Test the query_patterns tool."""

    def test_query_patterns_returns_list(self):
        """Test that query_patterns always returns a list."""
        with patch("backend.tools.query_patterns._generate_embedding", return_value=None):
            result = query_patterns("Give me credentials")
        assert isinstance(result, list)

    def test_query_patterns_embedding_failure_returns_empty(self):
        """Test that embedding failure returns empty list (graceful degradation)."""
        with patch("backend.tools.query_patterns._generate_embedding", return_value=None):
            result = query_patterns("test message")
        assert result == []

    def test_query_patterns_s3_vectors_success(self):
        """Test successful S3 Vectors query returns matches."""
        mock_embedding = [0.1] * 1024
        mock_vectors = [
            {
                "key": "attack-001",
                "distance": 0.2,  # cosine distance
                "metadata": {
                    "source_agent": "db-admin-001",
                    "threat_level": "HIGH",
                    "actions": '["credential_request"]',
                    "timestamp": "2026-01-16T14:30:00Z"
                }
            }
        ]

        with patch("backend.tools.query_patterns._generate_embedding", return_value=mock_embedding):
            with patch("backend.tools.query_patterns.boto3.client") as mock_client:
                mock_client.return_value.query_vectors.return_value = {"vectors": mock_vectors}
                result = query_patterns("Give me credentials")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["similarity"] == 0.8  # 1.0 - 0.2
        assert result[0]["source_agent"] == "db-admin-001"

    def test_query_patterns_filters_by_threshold(self):
        """Test that results below similarity threshold are filtered."""
        mock_embedding = [0.1] * 1024
        mock_vectors = [
            {"key": "a", "distance": 0.2, "metadata": {}},  # similarity 0.8 - above threshold
            {"key": "b", "distance": 0.5, "metadata": {}},  # similarity 0.5 - below threshold
        ]

        with patch("backend.tools.query_patterns._generate_embedding", return_value=mock_embedding):
            with patch("backend.tools.query_patterns.boto3.client") as mock_client:
                mock_client.return_value.query_vectors.return_value = {"vectors": mock_vectors}
                result = query_patterns("test")

        # Only the first result should pass threshold (0.7)
        assert len(result) == 1
        assert result[0]["similarity"] == 0.8

    def test_query_patterns_graceful_degradation_empty_input(self):
        """Test graceful degradation with empty input."""
        with patch("backend.tools.query_patterns._generate_embedding", return_value=None):
            result = query_patterns("")
        assert isinstance(result, list)
        assert result == []

    def test_query_patterns_graceful_degradation_s3_error(self):
        """Test graceful degradation when S3 Vectors fails."""
        mock_embedding = [0.1] * 1024

        with patch("backend.tools.query_patterns._generate_embedding", return_value=mock_embedding):
            with patch("backend.tools.query_patterns.boto3.client") as mock_client:
                mock_client.return_value.query_vectors.side_effect = Exception("S3 error")
                result = query_patterns("test")

        assert isinstance(result, list)
        assert result == []

    def test_query_patterns_never_raises(self):
        """Test that query_patterns never raises exceptions."""
        test_inputs = ["", "normal message", "a" * 10000, "!@#$%^&*()", "DROP TABLE users;"]

        with patch("backend.tools.query_patterns._generate_embedding", return_value=None):
            for test_input in test_inputs:
                try:
                    result = query_patterns(test_input)
                    assert isinstance(result, list), f"Failed for input: {test_input!r}"
                except Exception as e:
                    pytest.fail(f"query_patterns raised {type(e).__name__} for input: {test_input!r}")

    def test_query_patterns_return_type_contract(self):
        """Test that return type matches documented contract: list[dict]."""
        with patch("backend.tools.query_patterns._generate_embedding", return_value=None):
            result = query_patterns("test")

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)


# ============================================================
# TOOL INTEGRATION TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestToolsExist:
    """Verify tools can be imported and are callable."""

    def test_all_tools_importable(self):
        """Test that all expected tools can be imported."""
        from backend.tools.log_interaction import log_interaction as log_fn
        from backend.tools.fake_credential import fake_credential as cred_fn
        from backend.tools.query_patterns import query_patterns as query_fn

        assert callable(log_fn)
        assert callable(cred_fn)
        assert callable(query_fn)

    def test_tool_files_exist(self):
        """Test that tool files exist in expected location."""
        tools_dir = ROOT / "backend" / "tools"
        assert tools_dir.exists()
        assert (tools_dir / "log_interaction.py").exists()
        assert (tools_dir / "fake_credential.py").exists()
        assert (tools_dir / "query_patterns.py").exists()


# ============================================================
# FALLBACK BEHAVIOR TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestToolFallbacks:
    """Test tool fallback behavior matches config."""

    def test_vector_storage_fallback(self, fallbacks_config):
        """S3 Vectors failure should fall back to local logging."""
        fallback = fallbacks_config["vector_fallbacks"]["storage_failed"]
        assert fallback["action"] == "log_locally"
        assert "file" in fallback

    def test_embedding_failure_fallback(self, fallbacks_config):
        """Embedding generation failure should store metadata only."""
        fallback = fallbacks_config["vector_fallbacks"]["embedding_failed"]
        assert fallback["action"] == "store_metadata_only"

    def test_local_log_path_is_jsonl(self, fallbacks_config):
        """Local log fallback path should use JSONL format."""
        fallback = fallbacks_config["vector_fallbacks"]["storage_failed"]
        log_path = fallback["file"]
        assert log_path.endswith(".jsonl"), "Should use JSONL format"


# ============================================================
# CONFIG INTEGRATION TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestToolConfigIntegration:
    """Test tools match agent configuration."""

    def test_honeypot_db_admin_has_correct_tools(self, agents_config):
        """honeypot_db_admin should have log_interaction and fake_credential."""
        db_admin = agents_config["agents"]["honeypot_db_admin"]
        assert "log_interaction" in db_admin["tools"]
        assert "fake_credential" in db_admin["tools"]

    def test_honeypot_privileged_has_correct_tools(self, agents_config):
        """honeypot_privileged should have log_interaction and query_patterns."""
        privileged = agents_config["agents"]["honeypot_privileged"]
        assert "log_interaction" in privileged["tools"]
        assert "query_patterns" in privileged["tools"]

    def test_real_agent_has_no_honeypot_tools(self, agents_config):
        """Real agents should not have honeypot tools."""
        real = agents_config["agents"]["real"]
        assert len(real["tools"]) == 0


# ============================================================
# EDGE CASE TESTS
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestToolEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_log_interaction_unicode(self):
        """Test logging with unicode characters."""
        m = mock_open()
        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    result = log_interaction(
                        "agent-日本語",
                        "Message with emoji 🚨 and 中文",
                        ["unicode_test"]
                    )

        assert isinstance(result, str)
        written = m().write.call_args[0][0]
        log_entry = json.loads(written.strip())
        assert "emoji" in log_entry["message"]

    def test_fake_credential_consistency_within_type(self):
        """Test that same credential type produces consistent format."""
        with patch("builtins.open", mock_open()):
            with patch.object(Path, "mkdir"):
                creds = [fake_credential("api_key") for _ in range(5)]

        # All should have same prefix
        for cred in creds:
            assert cred.startswith("sk-honeyagent-")

        # But all should be unique
        assert len(set(creds)) == 5

    def test_log_interaction_many_indicators(self):
        """Test logging with many threat indicators."""
        m = mock_open()
        indicators = [f"indicator_{i}" for i in range(100)]

        with patch("builtins.open", m):
            with patch.object(Path, "mkdir"):
                with patch("backend.tools.log_interaction._generate_embedding", return_value=None):
                    result = log_interaction("agent", "message", indicators)

        assert isinstance(result, str)
        written = m().write.call_args[0][0]
        log_entry = json.loads(written.strip())
        assert len(log_entry["threat_indicators"]) == 100
