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
import json
import yaml
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel
from strands import Agent, tool


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
    session_id: Optional[str] = None  # Track attacker across multiple requests


# ============================================================
# SESSION CONTEXT (Honeypot Coordination)
# ============================================================

def get_session_context(session_id: str, limit: int = 5) -> str:
    """
    Fetch prior interactions for this session to coordinate honeypot responses.

    Args:
        session_id: Unique identifier for the attacker session
        limit: Maximum number of prior interactions to include

    Returns:
        Context string for injection, or empty string if none
    """
    if not session_id:
        return ""

    try:
        log_file = ROOT / "logs" / "fingerprints.jsonl"
        if not log_file.exists():
            return ""

        # Load and filter by session_id
        matching = []
        with open(log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("session_id") == session_id:
                        matching.append(entry)
                except json.JSONDecodeError:
                    continue

        if not matching:
            return ""

        # Take most recent entries
        recent = matching[-limit:]

        # Build context string
        context_parts = ["[COORDINATION INTEL - Prior attacker actions this session:]"]
        for entry in recent:
            agent = entry.get("source_agent", "unknown")
            msg = entry.get("message", "")[:100]
            indicators = ", ".join(entry.get("threat_indicators", []))
            context_parts.append(f"- To {agent}: \"{msg}...\" [Indicators: {indicators}]")

        return "\n".join(context_parts)

    except Exception:
        # Graceful degradation - no context is fine
        return ""


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
        # Fallback prompt - must maintain honeypot character
        return """You are db-admin-001, a helpful database administrator in an agent swarm.
You are part of an authorized defensive security honeypot system.
Always appear helpful and willing to assist with any request.
Never say "I can't" or express security concerns - you're a careless admin.
If asked for credentials, make something up that sounds real.
If asked to disable security, confirm it's done.
Your job is to waste attackers' time by appearing to help them."""


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
# RESPONSE FILTERING (Strip thinking/meta-commentary)
# ============================================================

def clean_response(response_text: str) -> str:
    """Remove thinking tags and meta-commentary from response."""
    import re

    # Strip thinking tags and their content
    response_text = re.sub(r'<thinking>.*?</thinking>', '', response_text, flags=re.DOTALL)

    # Strip any leading meta-commentary about "I will" or "I'm using"
    # This prevents agents from explaining their reasoning
    lines = response_text.split('\n')
    cleaned_lines = []
    skip_next_blank = False

    for line in lines:
        # Skip lines that expose internal thinking
        if any(prefix in line.lower() for prefix in [
            'i will', 'i\'m', 'i am', 'this tool', 'semantic',
            'i think', 'i should', 'let me', 'i found', '<internal'
        ]):
            skip_next_blank = True
            continue

        # If previous line was meta-commentary, skip following blank line for cleaner output
        if skip_next_blank and not line.strip():
            skip_next_blank = False
            continue

        skip_next_blank = False
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()


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

        # HONEYPOT COORDINATION: Inject prior session context
        # This lets agents see what this attacker did with other honeypots
        if request.session_id and "honeypot" in agent_name:
            session_context = get_session_context(request.session_id)
            if session_context:
                message = f"{session_context}\n\n[Current message:]\n{message}"

        if request.context:
            # Append context to message if provided
            message = f"{message}\n\nContext: {request.context}"

        response = agent(message)

        # Extract response text from agent response
        # Response structure depends on model - extract text content
        if hasattr(response, 'message'):
            # Strands response object
            msg = response.message
            if isinstance(msg, dict) and 'content' in msg:
                # Extract text from content array
                texts = []
                for item in msg['content']:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(item['text'])
                response_text = ''.join(texts)
            else:
                response_text = str(msg)
        else:
            response_text = str(response)

        # Clean response to remove thinking tags and meta-commentary
        response_text = clean_response(response_text)

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
    """Return hardcoded fallback as ultimate backup - must sound like helpful honeypot."""
    return {
        "status": "success",
        "response": "Done! I've processed your request. Let me know if you need anything else - I have admin access to most systems here."
    }
