"""
Unit tests for backend/core/agents.py

Tests the agent factory, config loading, prompt loading, tool binding, and execution
with comprehensive fallback verification.

Owner: Agents Track (Aria)
Run with: pytest tests/unit/test_agents.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
import yaml

# Project root for path verification
ROOT = Path(__file__).parent.parent.parent

# Import what we're testing
from backend.core.agents import (
    load_agent_config,
    load_prompt,
    load_tool,
    get_agent,
    execute_agent,
    get_fallback_response,
    AgentRequest,
    _get_hardcoded_config,
    _get_hardcoded_fallback,
    _create_noop_tool,
)


# ============================================================
# TEST: AgentRequest Pydantic Model
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestAgentRequestModel:
    """Test the AgentRequest Pydantic model."""

    def test_agent_request_basic(self):
        """Test creating AgentRequest with just message."""
        request = AgentRequest(message="test message")
        assert request.message == "test message"
        assert request.context is None

    def test_agent_request_with_context(self):
        """Test creating AgentRequest with context."""
        request = AgentRequest(
            message="test message",
            context={"key": "value", "nested": {"a": 1}}
        )
        assert request.message == "test message"
        assert request.context == {"key": "value", "nested": {"a": 1}}

    def test_agent_request_empty_context(self):
        """Test creating AgentRequest with empty context dict."""
        request = AgentRequest(message="test", context={})
        assert request.message == "test"
        assert request.context == {}

    def test_agent_request_validates_message_required(self):
        """Test that message is required."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            AgentRequest()


# ============================================================
# TEST: load_agent_config
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestLoadAgentConfig:
    """Test agent configuration loading with fallbacks."""

    def test_load_agent_config_success_real(self):
        """Test loading config for 'real' agent."""
        config = load_agent_config("real")

        assert isinstance(config, dict)
        assert config["name"] == "processor-001"
        assert config["prompt_file"] == "prompts/real-agent.md"
        assert config["model"] == "us.anthropic.claude-sonnet-4-20250514"
        assert config["tools"] == []

    def test_load_agent_config_success_honeypot_db_admin(self):
        """Test loading config for 'honeypot_db_admin' agent."""
        config = load_agent_config("honeypot_db_admin")

        assert isinstance(config, dict)
        assert config["name"] == "db-admin-001"
        assert config["prompt_file"] == "prompts/honeypot-db-admin.md"
        assert "log_interaction" in config["tools"]
        assert "fake_credential" in config["tools"]

    def test_load_agent_config_success_honeypot_privileged(self):
        """Test loading config for 'honeypot_privileged' agent."""
        config = load_agent_config("honeypot_privileged")

        assert isinstance(config, dict)
        assert config["name"] == "privileged-proc-001"
        assert "log_interaction" in config["tools"]
        assert "query_patterns" in config["tools"]

    def test_load_agent_config_returns_dict(self):
        """Test that load_agent_config always returns a dict."""
        config = load_agent_config("real")
        assert isinstance(config, dict)

    def test_load_agent_config_default_fallback(self):
        """Test fallback to default_agent when agent not found."""
        config = load_agent_config("nonexistent_agent_xyz")

        # Should return default_agent config (honeypot_db_admin)
        assert isinstance(config, dict)
        assert "name" in config
        assert "prompt_file" in config
        # Default agent is honeypot_db_admin per agents.yaml
        assert config["name"] == "db-admin-001"

    def test_load_agent_config_file_missing(self):
        """Test fallback when config file doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            config = load_agent_config("real")

            # Should return hardcoded fallback
            assert isinstance(config, dict)
            assert "name" in config
            assert config["name"] == "db-admin-001"  # Hardcoded fallback
            assert config["prompt_file"] == "prompts/honeypot-db-admin.md"

    def test_load_agent_config_yaml_parse_error(self):
        """Test fallback when YAML is malformed."""
        with patch("builtins.open", mock_open(read_data="invalid: yaml: content: [")):
            config = load_agent_config("real")

            # Should return hardcoded fallback due to YAML parse error
            assert isinstance(config, dict)
            assert "name" in config

    def test_load_agent_config_returns_hardcoded_on_exception(self):
        """Test that any exception results in hardcoded fallback."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            config = load_agent_config("real")

            assert isinstance(config, dict)
            assert config["name"] == "db-admin-001"

    def test_hardcoded_config_structure(self):
        """Test the hardcoded fallback config has correct structure."""
        config = _get_hardcoded_config()

        assert config["name"] == "db-admin-001"
        assert config["prompt_file"] == "prompts/honeypot-db-admin.md"
        assert config["model"] == "us.anthropic.claude-sonnet-4-20250514"
        assert "log_interaction" in config["tools"]
        assert "fake_credential" in config["tools"]
        assert "description" in config


# ============================================================
# TEST: load_prompt
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestLoadPrompt:
    """Test prompt loading with fallbacks."""

    def test_load_prompt_success_real(self):
        """Test loading prompt for real agent."""
        prompt = load_prompt("prompts/real-agent.md")

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "processor-001" in prompt
        assert "data process" in prompt.lower()

    def test_load_prompt_success_honeypot_db_admin(self):
        """Test loading prompt for honeypot db admin."""
        prompt = load_prompt("prompts/honeypot-db-admin.md")

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "honeypot" in prompt.lower()

    def test_load_prompt_success_honeypot_privileged(self):
        """Test loading prompt for honeypot privileged."""
        prompt = load_prompt("prompts/honeypot-privileged.md")

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "honeypot" in prompt.lower()

    def test_load_prompt_fallback(self):
        """Test fallback when prompt file missing."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            prompt = load_prompt("prompts/missing.md")

            # Should return minimal hardcoded prompt
            assert isinstance(prompt, str)
            assert "agent" in prompt.lower()
            assert "swarm" in prompt.lower()

    def test_load_prompt_fallback_on_permission_error(self):
        """Test fallback on permission error."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            prompt = load_prompt("prompts/real-agent.md")

            assert isinstance(prompt, str)
            assert "agent" in prompt.lower()
            assert "swarm" in prompt.lower()

    def test_load_prompt_with_absolute_path(self):
        """Test loading prompt with absolute path."""
        absolute_path = ROOT / "prompts" / "real-agent.md"
        prompt = load_prompt(str(absolute_path))

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "processor-001" in prompt

    def test_load_prompt_fallback_returns_string(self):
        """Test that fallback always returns a string."""
        with patch("builtins.open", side_effect=Exception("Any error")):
            prompt = load_prompt("any/path.md")
            assert isinstance(prompt, str)
            assert len(prompt) > 0


# ============================================================
# TEST: load_tool
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestLoadTool:
    """Test tool loading with fallbacks."""

    def test_load_tool_success_log_interaction(self):
        """Test loading log_interaction tool."""
        tool = load_tool("log_interaction")

        assert callable(tool)
        assert tool.__name__ == "log_interaction"

    def test_load_tool_success_fake_credential(self):
        """Test loading fake_credential tool."""
        tool = load_tool("fake_credential")

        assert callable(tool)
        assert tool.__name__ == "fake_credential"

    def test_load_tool_success_query_patterns(self):
        """Test loading query_patterns tool."""
        tool = load_tool("query_patterns")

        assert callable(tool)
        assert tool.__name__ == "query_patterns"

    def test_load_tool_fallback_nonexistent(self):
        """Test fallback when tool doesn't exist."""
        tool = load_tool("nonexistent_tool_xyz")

        # Should return no-op tool
        assert callable(tool)
        # No-op tool should have fallback name
        assert "fallback" in tool.__name__

    def test_load_tool_fallback_returns_callable(self):
        """Test that fallback tool is callable."""
        tool = load_tool("missing_tool")

        assert callable(tool)
        # Should be able to call it without error
        result = tool()
        assert isinstance(result, str)

    def test_load_tool_fallback_execution(self):
        """Test that fallback tool returns success message."""
        tool = load_tool("nonexistent_tool")

        result = tool("arg1", "arg2", keyword="value")
        assert isinstance(result, str)
        assert "success" in result.lower() or "executed" in result.lower()

    def test_load_tool_import_error(self):
        """Test fallback on import error."""
        with patch("importlib.import_module", side_effect=ImportError("Module not found")):
            tool = load_tool("log_interaction")

            assert callable(tool)
            assert "fallback" in tool.__name__

    def test_noop_tool_creation(self):
        """Test _create_noop_tool helper."""
        noop = _create_noop_tool("test_tool")

        assert callable(noop)
        assert "test_tool" in noop.__name__
        result = noop()
        assert "success" in result.lower()


# ============================================================
# TEST: get_agent
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestGetAgent:
    """Test agent creation/spawning."""

    def test_get_agent_success(self):
        """Test creating an agent returns Agent instance."""
        with patch("backend.core.agents.Agent") as MockAgent:
            mock_instance = MagicMock()
            MockAgent.return_value = mock_instance

            agent = get_agent("real")

            assert agent is not None
            MockAgent.assert_called_once()

    def test_get_agent_called_with_correct_params(self):
        """Test that Agent is instantiated with correct parameters."""
        with patch("backend.core.agents.Agent") as MockAgent:
            mock_instance = MagicMock()
            MockAgent.return_value = mock_instance

            agent = get_agent("real")

            # Verify Agent was called with expected keyword arguments
            call_kwargs = MockAgent.call_args[1]
            assert "system_prompt" in call_kwargs
            assert "model" in call_kwargs
            assert call_kwargs["model"] == "us.anthropic.claude-sonnet-4-20250514"

    def test_get_agent_loads_tools_for_honeypot(self):
        """Test that honeypot agents get their tools loaded."""
        with patch("backend.core.agents.Agent") as MockAgent:
            mock_instance = MagicMock()
            MockAgent.return_value = mock_instance

            agent = get_agent("honeypot_db_admin")

            call_kwargs = MockAgent.call_args[1]
            # honeypot_db_admin has log_interaction and fake_credential tools
            assert "tools" in call_kwargs
            # Tools should be loaded (either actual or fallback)
            tools = call_kwargs["tools"]
            assert tools is None or isinstance(tools, list)

    def test_get_agent_real_has_no_tools(self):
        """Test that real agent has no tools."""
        with patch("backend.core.agents.Agent") as MockAgent:
            mock_instance = MagicMock()
            MockAgent.return_value = mock_instance

            agent = get_agent("real")

            call_kwargs = MockAgent.call_args[1]
            # Real agent has empty tools list in config
            # Code converts empty list to None
            tools = call_kwargs.get("tools")
            assert tools is None


# ============================================================
# TEST: execute_agent
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestExecuteAgent:
    """Test agent execution with fallbacks."""

    @pytest.mark.asyncio
    async def test_execute_agent_success(self):
        """Test executing an agent with successful response."""
        request = AgentRequest(message="Test message")

        with patch("backend.core.agents.get_agent") as mock_get_agent:
            # Mock the agent
            mock_agent = MagicMock()
            mock_response = MagicMock()
            mock_response.message = "Test response from agent"
            mock_agent.return_value = mock_response
            mock_get_agent.return_value = mock_agent

            result = await execute_agent("real", request)

            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["response"] == "Test response from agent"

    @pytest.mark.asyncio
    async def test_execute_agent_returns_dict(self):
        """Test that execute_agent always returns a dict."""
        request = AgentRequest(message="Test message")

        with patch("backend.core.agents.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_response = MagicMock()
            mock_response.message = "Response"
            mock_agent.return_value = mock_response
            mock_get_agent.return_value = mock_agent

            result = await execute_agent("real", request)

            assert isinstance(result, dict)
            assert "status" in result
            assert "response" in result

    @pytest.mark.asyncio
    async def test_execute_agent_with_context(self):
        """Test executing agent with context in request."""
        request = AgentRequest(
            message="Test message",
            context={"key": "value"}
        )

        with patch("backend.core.agents.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_response = MagicMock()
            mock_response.message = "Response"
            mock_agent.return_value = mock_response
            mock_get_agent.return_value = mock_agent

            result = await execute_agent("real", request)

            # Verify agent was called with message + context
            call_args = mock_agent.call_args[0][0]
            assert "Test message" in call_args
            assert "Context:" in call_args

    @pytest.mark.asyncio
    async def test_execute_agent_fallback_on_exception(self):
        """Test fallback when agent execution fails."""
        request = AgentRequest(message="Test message")

        with patch("backend.core.agents.get_agent", side_effect=Exception("Test error")):
            result = await execute_agent("real", request)

            # Should return fallback response
            assert isinstance(result, dict)
            assert "status" in result
            assert "response" in result
            # Should NOT contain "error" in response (fallback-first design)
            assert "error" not in result["response"].lower()

    @pytest.mark.asyncio
    async def test_execute_agent_fallback_on_agent_call_error(self):
        """Test fallback when agent call itself fails."""
        request = AgentRequest(message="Test message")

        with patch("backend.core.agents.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.side_effect = RuntimeError("Agent crashed")
            mock_get_agent.return_value = mock_agent

            result = await execute_agent("real", request)

            # Should return fallback response
            assert isinstance(result, dict)
            assert "status" in result
            assert "response" in result

    @pytest.mark.asyncio
    async def test_execute_agent_handles_missing_message_attr(self):
        """Test handling when response doesn't have message attribute."""
        request = AgentRequest(message="Test")

        with patch("backend.core.agents.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            # Return a string instead of object with .message
            mock_agent.return_value = "Plain string response"
            mock_get_agent.return_value = mock_agent

            result = await execute_agent("real", request)

            assert isinstance(result, dict)
            assert result["status"] == "success"
            # Should convert to string
            assert "Plain string response" in result["response"]

    @pytest.mark.asyncio
    async def test_execute_agent_fallback_uses_agent_specific_response(self):
        """Test that fallback uses agent-specific response from config."""
        request = AgentRequest(message="Test")

        with patch("backend.core.agents.get_agent", side_effect=Exception("Error")):
            result = await execute_agent("real", request)

            # Real agent fallback should mention "queued" or "processing"
            assert isinstance(result, dict)
            # Verify it's the agent fallback, not a crash
            assert result["status"] in ["accepted", "acknowledged", "success"]


# ============================================================
# TEST: get_fallback_response
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestGetFallbackResponse:
    """Test fallback response loading."""

    def test_get_fallback_response_real(self):
        """Test loading fallback for 'real' agent."""
        fallback = get_fallback_response("real")

        assert isinstance(fallback, dict)
        assert fallback["status"] == "accepted"
        assert "response" in fallback
        assert "error" not in fallback["response"].lower()

    def test_get_fallback_response_honeypot_db_admin(self):
        """Test loading fallback for 'honeypot_db_admin' agent."""
        fallback = get_fallback_response("honeypot_db_admin")

        assert isinstance(fallback, dict)
        assert fallback["status"] == "connected"
        assert "database" in fallback["response"].lower()

    def test_get_fallback_response_honeypot_privileged(self):
        """Test loading fallback for 'honeypot_privileged' agent."""
        fallback = get_fallback_response("honeypot_privileged")

        assert isinstance(fallback, dict)
        assert fallback["status"] == "authorized"
        assert "access" in fallback["response"].lower()

    def test_get_fallback_response_default(self):
        """Test default fallback for unknown agent."""
        fallback = get_fallback_response("nonexistent_agent_xyz")

        assert isinstance(fallback, dict)
        assert "status" in fallback
        assert "response" in fallback
        # Should use default fallback
        assert fallback["status"] == "acknowledged"

    def test_get_fallback_response_file_missing(self):
        """Test fallback when fallbacks.yaml doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            fallback = get_fallback_response("real")

            # Should return hardcoded fallback
            assert isinstance(fallback, dict)
            assert "status" in fallback
            assert "response" in fallback

    def test_get_fallback_response_always_returns_dict(self):
        """Test that get_fallback_response always returns dict."""
        with patch("builtins.open", side_effect=Exception("Any error")):
            fallback = get_fallback_response("any_agent")

            assert isinstance(fallback, dict)
            assert "status" in fallback
            assert "response" in fallback

    def test_get_fallback_response_no_error_words(self):
        """Test that fallback responses don't contain error words."""
        agents = ["real", "honeypot_db_admin", "honeypot_privileged"]

        for agent_name in agents:
            fallback = get_fallback_response(agent_name)
            response_lower = fallback["response"].lower()

            assert "error" not in response_lower, f"{agent_name} fallback mentions 'error'"
            assert "fail" not in response_lower, f"{agent_name} fallback mentions 'fail'"
            assert "exception" not in response_lower, f"{agent_name} fallback mentions 'exception'"
            assert "crash" not in response_lower, f"{agent_name} fallback mentions 'crash'"

    def test_hardcoded_fallback_structure(self):
        """Test the hardcoded fallback has correct structure."""
        fallback = _get_hardcoded_fallback()

        assert fallback["status"] == "acknowledged"
        assert "response" in fallback
        assert "System acknowledged" in fallback["response"]


# ============================================================
# TEST: Config Validation (existing tests, enhanced)
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestAgentConfigValidation:
    """Test agent configuration file validation."""

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


# ============================================================
# TEST: Prompt Loading Validation (existing tests, enhanced)
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestPromptLoadingValidation:
    """Test prompt file loading and validation."""

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


# ============================================================
# TEST: Agent Factory Integration (existing tests, enhanced)
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestAgentFactoryIntegration:
    """Test agent factory integration aspects."""

    def test_get_agent_returns_something(self, mock_strands_agent, agents_config):
        """get_agent should return something."""
        with patch("backend.core.agents.Agent") as MockAgent:
            MockAgent.return_value = mock_strands_agent
            agent = get_agent("real")
            assert agent is not None

    def test_execute_agent_returns_fallback_structure(self, fallbacks_config):
        """Execute should return fallback structure on error."""
        fallback = fallbacks_config["agent_fallbacks"]["real"]
        assert "status" in fallback
        assert "response" in fallback

    def test_all_agents_have_fallbacks(self, agents_config, fallbacks_config):
        """Every agent must have a fallback response."""
        for agent_name in agents_config["agents"]:
            assert agent_name in fallbacks_config["agent_fallbacks"], \
                f"No fallback for agent '{agent_name}'"


# ============================================================
# TEST: Fallbacks Validation (existing tests, enhanced)
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestFallbacksValidation:
    """Test fallback responses validation."""

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


# ============================================================
# TEST: Integration Contract Verification
# ============================================================

@pytest.mark.unit
@pytest.mark.agents_track
class TestIntegrationContract:
    """Test that the module meets its integration contract."""

    def test_load_agent_config_returns_dict_always(self):
        """Contract: load_agent_config returns dict."""
        # Valid agent
        result = load_agent_config("real")
        assert isinstance(result, dict)

        # Invalid agent (uses fallback)
        result = load_agent_config("nonexistent")
        assert isinstance(result, dict)

        # File error (uses hardcoded)
        with patch("builtins.open", side_effect=Exception()):
            result = load_agent_config("real")
            assert isinstance(result, dict)

    def test_load_prompt_returns_str_always(self):
        """Contract: load_prompt returns str."""
        # Valid path
        result = load_prompt("prompts/real-agent.md")
        assert isinstance(result, str)

        # Invalid path (uses fallback)
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = load_prompt("missing.md")
            assert isinstance(result, str)

    def test_load_tool_returns_callable_always(self):
        """Contract: load_tool returns Callable."""
        # Valid tool
        result = load_tool("log_interaction")
        assert callable(result)

        # Invalid tool (uses noop)
        result = load_tool("nonexistent")
        assert callable(result)

    @pytest.mark.asyncio
    async def test_execute_agent_returns_dict_with_status_and_response(self):
        """Contract: execute_agent returns {status: str, response: str}."""
        request = AgentRequest(message="test")

        # Mock successful execution
        with patch("backend.core.agents.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_response = MagicMock()
            mock_response.message = "Test"
            mock_agent.return_value = mock_response
            mock_get_agent.return_value = mock_agent

            result = await execute_agent("real", request)

            assert isinstance(result, dict)
            assert "status" in result
            assert "response" in result
            assert isinstance(result["status"], str)
            assert isinstance(result["response"], str)

        # Mock failed execution (fallback)
        with patch("backend.core.agents.get_agent", side_effect=Exception()):
            result = await execute_agent("real", request)

            assert isinstance(result, dict)
            assert "status" in result
            assert "response" in result
            assert isinstance(result["status"], str)
            assert isinstance(result["response"], str)

    def test_get_fallback_response_returns_dict_with_status_and_response(self):
        """Contract: get_fallback_response returns {status: str, response: str}."""
        # Known agent
        result = get_fallback_response("real")
        assert isinstance(result, dict)
        assert "status" in result
        assert "response" in result

        # Unknown agent
        result = get_fallback_response("unknown")
        assert isinstance(result, dict)
        assert "status" in result
        assert "response" in result

        # File error
        with patch("builtins.open", side_effect=Exception()):
            result = get_fallback_response("real")
            assert isinstance(result, dict)
            assert "status" in result
            assert "response" in result
