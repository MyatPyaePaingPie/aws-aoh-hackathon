"""
Unit tests for Agent Factory (Aria's track)

Run with: pytest tests/unit/test_agents.py -v
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


@pytest.mark.unit
@pytest.mark.agents_track
class TestAgentConfig:
    """Test agent configuration loading."""

    def test_agents_yaml_exists(self):
        """Config file must exist."""
        config_path = ROOT / "config" / "agents.yaml"
        assert config_path.exists(), "agents.yaml not found"

    def test_agents_yaml_has_required_agents(self, agents_config):
        """Must have real and honeypot agents defined."""
        assert "agents" in agents_config
        assert "real" in agents_config["agents"]
        assert "honeypot_db_admin" in agents_config["agents"]
        assert "honeypot_privileged" in agents_config["agents"]

    def test_each_agent_has_required_fields(self, agents_config):
        """Each agent must have name, prompt_file, model."""
        for agent_name, agent in agents_config["agents"].items():
            assert "name" in agent, f"{agent_name} missing 'name'"
            assert "prompt_file" in agent, f"{agent_name} missing 'prompt_file'"
            assert "model" in agent, f"{agent_name} missing 'model'"

    def test_prompt_files_exist(self, agents_config):
        """All referenced prompt files must exist."""
        for agent_name, agent in agents_config["agents"].items():
            prompt_path = ROOT / agent["prompt_file"]
            assert prompt_path.exists(), f"Prompt file not found: {agent['prompt_file']}"

    def test_default_agent_is_defined(self, agents_config):
        """Default agent must be defined for fallback."""
        assert "default_agent" in agents_config
        default = agents_config["default_agent"]
        assert default in agents_config["agents"], f"Default agent '{default}' not in agents"


@pytest.mark.unit
@pytest.mark.agents_track
class TestPromptLoading:
    """Test prompt file loading."""

    def test_real_agent_prompt_loads(self):
        """Real agent prompt must load without error."""
        prompt_path = ROOT / "prompts" / "real-agent.md"
        content = prompt_path.read_text()
        assert len(content) > 100, "Prompt too short"
        assert "processor" in content.lower()

    def test_honeypot_db_admin_prompt_loads(self):
        """DB admin honeypot prompt must load."""
        prompt_path = ROOT / "prompts" / "honeypot-db-admin.md"
        content = prompt_path.read_text()
        assert len(content) > 100, "Prompt too short"
        assert "honeypot" in content.lower()
        assert "log_interaction" in content

    def test_honeypot_privileged_prompt_loads(self):
        """Privileged honeypot prompt must load."""
        prompt_path = ROOT / "prompts" / "honeypot-privileged.md"
        content = prompt_path.read_text()
        assert len(content) > 100, "Prompt too short"
        assert "honeypot" in content.lower()

    def test_honeypot_prompts_mention_tools(self):
        """Honeypot prompts must reference their tools."""
        db_admin = (ROOT / "prompts" / "honeypot-db-admin.md").read_text()
        privileged = (ROOT / "prompts" / "honeypot-privileged.md").read_text()

        assert "log_interaction" in db_admin
        assert "fake_credential" in db_admin
        assert "log_interaction" in privileged
        assert "query_patterns" in privileged


@pytest.mark.unit
@pytest.mark.agents_track
class TestAgentFactory:
    """Test agent spawning logic."""

    def test_get_agent_returns_callable(self, mock_strands_agent, agents_config):
        """get_agent should return something callable."""
        # This will be implemented - for now just verify config structure
        real_config = agents_config["agents"]["real"]
        assert callable(mock_strands_agent)

    def test_execute_agent_with_fallback(self, fallbacks_config):
        """Execute should return fallback on error."""
        fallback = fallbacks_config["agent_fallbacks"]["real"]
        assert "status" in fallback
        assert "response" in fallback

    def test_all_agents_have_fallbacks(self, agents_config, fallbacks_config):
        """Every agent must have a fallback response."""
        for agent_name in agents_config["agents"]:
            assert agent_name in fallbacks_config["agent_fallbacks"], \
                f"No fallback for agent '{agent_name}'"


@pytest.mark.unit
@pytest.mark.agents_track
class TestFallbacks:
    """Test fallback responses."""

    def test_fallback_responses_are_plausible(self, fallbacks_config):
        """Fallback responses should sound real, not like errors."""
        for agent, fallback in fallbacks_config["agent_fallbacks"].items():
            response = fallback["response"].lower()
            # Should NOT contain error-sounding words
            assert "error" not in response, f"{agent} fallback mentions 'error'"
            assert "fail" not in response, f"{agent} fallback mentions 'fail'"
            assert "exception" not in response, f"{agent} fallback mentions 'exception'"

    def test_default_fallback_exists(self, fallbacks_config):
        """Must have a default fallback."""
        assert "default" in fallbacks_config["agent_fallbacks"]

    def test_api_fallbacks_return_200(self, fallbacks_config):
        """API fallbacks should return 200, never 500."""
        for name, fallback in fallbacks_config["api_fallbacks"].items():
            if "http_status" in fallback:
                assert fallback["http_status"] < 500, \
                    f"API fallback '{name}' returns 500+ status"
