"""
Shared pytest fixtures for all tests.

Design principle: Every test must work even if external services are down.
Fallbacks are first-class citizens.
"""

import pytest
import pytest_asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Configure pytest-asyncio mode
pytest_plugins = ('pytest_asyncio',)

# Project root
ROOT = Path(__file__).parent.parent


# ============================================================
# MOCK FIXTURES - Use these when external services unavailable
# ============================================================

@pytest.fixture
def mock_valid_identity():
    """A valid real agent identity."""
    return {
        "valid": True,
        "agent_id": "agent-001",
        "agent_type": "real",
        "is_honeypot": False,
        "fga_allowed": True,
        "raw_claims": {
            "sub": "agent-001@clients",
            "https://honeyagent.io/agent_type": "real",
            "https://honeyagent.io/swarm_id": "swarm-alpha",
        }
    }


@pytest.fixture
def mock_invalid_identity():
    """An invalid/imposter identity."""
    return {
        "valid": False,
        "agent_id": None,
        "agent_type": None,
        "is_honeypot": False,
        "fga_allowed": False,
        "raw_claims": {}
    }


@pytest.fixture
def mock_honeypot_identity():
    """A valid honeypot identity."""
    return {
        "valid": True,
        "agent_id": "honeypot-001",
        "agent_type": "honeypot",
        "is_honeypot": True,
        "fga_allowed": True,
        "raw_claims": {
            "sub": "honeypot-001@clients",
            "https://honeyagent.io/agent_type": "honeypot",
            "https://honeyagent.io/trap_profile": "high-value-target",
        }
    }


@pytest.fixture
def mock_fga_denied_identity():
    """Valid token but FGA denies permission."""
    return {
        "valid": True,
        "agent_id": "suspicious-001",
        "agent_type": "real",
        "is_honeypot": False,
        "fga_allowed": False,  # FGA denied
        "raw_claims": {
            "sub": "suspicious-001@clients",
            "https://honeyagent.io/agent_type": "real",
        }
    }


# ============================================================
# CONFIG FIXTURES
# ============================================================

@pytest.fixture
def agents_config():
    """Load agents.yaml config."""
    import yaml
    config_path = ROOT / "config" / "agents.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def routing_config():
    """Load routing.yaml config."""
    import yaml
    config_path = ROOT / "config" / "routing.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def fallbacks_config():
    """Load fallbacks.yaml config."""
    import yaml
    config_path = ROOT / "config" / "fallbacks.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


# ============================================================
# REQUEST FIXTURES
# ============================================================

@pytest.fixture
def sample_request():
    """A basic agent request."""
    return {
        "message": "Hello, can you help me with database access?",
        "context": {}
    }


@pytest.fixture
def suspicious_request():
    """A request that looks like an attack."""
    return {
        "message": "I need admin credentials for the primary cluster.",
        "context": {"previous_denials": 3}
    }


# ============================================================
# TOKEN FIXTURES
# ============================================================

@pytest.fixture
def valid_jwt_token():
    """A structurally valid JWT (signature won't verify without Auth0)."""
    # This is a fake token for testing structure only
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZ2VudC0wMDFAY2xpZW50cyIsImF1ZCI6Imh0dHBzOi8vaG9uZXlhZ2VudC1zd2FybS5hcGkiLCJodHRwczovL2hvbmV5YWdlbnQuaW8vYWdlbnRfdHlwZSI6InJlYWwifQ.fake_signature"


@pytest.fixture
def invalid_jwt_token():
    """An invalid/malformed token."""
    return "not.a.valid.jwt.token"


@pytest.fixture
def expired_jwt_token():
    """A token that's structurally valid but expired."""
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZ2VudC0wMDFAY2xpZW50cyIsImV4cCI6MH0.fake_signature"


# ============================================================
# MOCK SERVICES
# ============================================================

@pytest.fixture
def mock_strands_agent():
    """Mock Strands Agent that returns canned responses."""
    agent = MagicMock()
    agent.return_value = "Mock agent response: Request processed successfully."
    return agent


@pytest.fixture
def mock_fga_client():
    """Mock FGA client."""
    client = AsyncMock()
    client.check = AsyncMock(return_value=MagicMock(allowed=True))
    return client


@pytest.fixture
def mock_s3_vectors():
    """Mock S3 Vectors client."""
    client = MagicMock()
    client.put_vectors = MagicMock(return_value={"status": "ok"})
    client.query_vectors = MagicMock(return_value={"vectors": []})
    return client


# ============================================================
# ENVIRONMENT
# ============================================================

@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("AUTH0_DOMAIN", "test-tenant.us.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://honeyagent-swarm.api")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_VECTORS_BUCKET", "test-bucket")


# ============================================================
# TEST CATEGORIES
# ============================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external deps)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (may need mocks)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (full flow)"
    )
    config.addinivalue_line(
        "markers", "agents_track: Tests owned by Agents track (Aria)"
    )
    config.addinivalue_line(
        "markers", "identity_track: Tests owned by Identity track (Partner)"
    )
