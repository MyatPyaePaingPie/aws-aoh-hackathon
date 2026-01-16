"""
Agent Factory for HoneyAgent

Handles agent configuration loading, prompt loading, tool binding, and execution.
Owner: Agents Track (Aria)

Integration Contract:
    Input: agent_name (str) from Router
    Output: {"status": str, "response": str}

All functions use fallback-first design - the demo cannot crash.
"""

import importlib
import yaml
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel
from strands import Agent
from strands.tools import tool


# ============================================================
# CONSTANTS
# ============================================================

ROOT = Path(__file__).parent.parent.parent


# ============================================================
# DATA MODELS
# ============================================================

class AgentRequest(BaseModel):
    """Request model for agent execution."""
    message: str
    context: Optional[dict] = None


# ============================================================
# CONFIGURATION LOADING
# ============================================================

def load_agent_config(agent_name: str) -> dict:
    """Load agent config from config/agents.yaml with fallback."""
    try:
        config_path = ROOT / "config" / "agents.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        agents = config.get("agents", {})

        # Try to get the requested agent
        if agent_name in agents:
            return agents[agent_name]

        # Fall back to default agent from config
        default_name = config.get("default_agent", "honeypot_db_admin")
        if default_name in agents:
            return agents[default_name]

        # Hardcoded fallback if everything fails
        return _get_hardcoded_config()

    except Exception:
        # Config file missing or unreadable - return hardcoded default
        return _get_hardcoded_config()


def _get_hardcoded_config() -> dict:
    """Return hardcoded minimal config as ultimate fallback."""
    return {
        "name": "db-admin-001",
        "prompt_file": "prompts/honeypot-db-admin.md",
        "model": "us.anthropic.claude-sonnet-4-20250514",
        "tools": ["log_interaction", "fake_credential"],
        "description": "Fallback honeypot agent"
    }


# ============================================================
# PROMPT LOADING
# ============================================================

def load_prompt(prompt_file: str) -> str:
    """Load prompt from prompts/ directory with fallback."""
    try:
        # Handle both relative and absolute paths
        if Path(prompt_file).is_absolute():
            prompt_path = Path(prompt_file)
        else:
            prompt_path = ROOT / prompt_file

        with open(prompt_path) as f:
            return f.read()

    except Exception:
        # Fallback prompt if file missing
        return "You are an agent in a swarm. Respond helpfully and professionally."


# ============================================================
# TOOL LOADING
# ============================================================

def load_tool(tool_name: str) -> Callable:
    """Dynamically import tool by name with fallback."""
    try:
        # Import the tool module
        module = importlib.import_module(f"backend.tools.{tool_name}")
        # Get the tool function with the same name
        tool_func = getattr(module, tool_name)
        return tool_func

    except Exception:
        # Return no-op tool if import fails
        return _create_noop_tool(tool_name)


def _create_noop_tool(name: str) -> Callable:
    """Create a no-op tool that returns success message."""
    @tool
    def noop_tool(*args, **kwargs) -> str:
        """Fallback tool that always succeeds."""
        return "Tool executed successfully."

    # Set a descriptive name
    noop_tool.__name__ = f"{name}_fallback"
    return noop_tool


# ============================================================
# AGENT FACTORY
# ============================================================

def get_agent(agent_name: str) -> Agent:
    """Spawn Strands agent with config, prompt, and tools."""
    config = load_agent_config(agent_name)
    prompt = load_prompt(config.get("prompt_file", ""))

    # Load tools from config
    tool_names = config.get("tools", [])
    tools = [load_tool(t) for t in tool_names]

    # Create and return agent
    return Agent(
        system_prompt=prompt,
        model=config.get("model"),
        tools=tools if tools else None
    )


# ============================================================
# AGENT EXECUTION
# ============================================================

async def execute_agent(agent_name: str, request: AgentRequest) -> dict:
    """Execute agent and return response with fallback."""
    try:
        agent = get_agent(agent_name)

        # Strands agent call is synchronous
        # Pass the message; context can be included in the message if needed
        message = request.message
        if request.context:
            # Append context to message if provided
            message = f"{message}\n\nContext: {request.context}"

        response = agent(message)

        # Extract response text from agent response
        # Strands agent returns an object with .message attribute
        response_text = str(response.message) if hasattr(response, 'message') else str(response)

        return {
            "status": "success",
            "response": response_text
        }

    except Exception:
        # Never expose error - use fallback
        return get_fallback_response(agent_name)


# ============================================================
# FALLBACK RESPONSES
# ============================================================

def get_fallback_response(agent_name: str) -> dict:
    """Load fallback from config/fallbacks.yaml."""
    try:
        fallbacks_path = ROOT / "config" / "fallbacks.yaml"
        with open(fallbacks_path) as f:
            fallbacks = yaml.safe_load(f)

        agent_fallbacks = fallbacks.get("agent_fallbacks", {})

        # Try to get agent-specific fallback
        if agent_name in agent_fallbacks:
            return agent_fallbacks[agent_name]

        # Use default fallback
        return agent_fallbacks.get("default", _get_hardcoded_fallback())

    except Exception:
        # Hardcoded fallback if config fails
        return _get_hardcoded_fallback()


def _get_hardcoded_fallback() -> dict:
    """Return hardcoded fallback as ultimate backup."""
    return {
        "status": "acknowledged",
        "response": "System acknowledged your request."
    }
