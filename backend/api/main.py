"""
FastAPI Gateway for HoneyAgent

Single entry point that wires together:
- Identity validation (token → Identity)
- Routing (Identity → agent_name)
- Agent execution (agent_name → response)

Endpoint: POST /agent/request
"""

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel

# Import from partner's track
from backend.core.identity import validate_token, Identity
from backend.core.router import route_request

# Import from our track
from backend.core.agents import execute_agent, AgentRequest


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="HoneyAgent API",
    description="Deception-as-a-Service for Agent Networks",
    version="1.0.0"
)

# CORS middleware (for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "honeyagent"}


# ============================================================
# MAIN AGENT REQUEST ENDPOINT
# ============================================================

@app.post("/agent/request")
async def agent_request(
    request: AgentRequest,
    authorization: Optional[str] = Header(None)
) -> dict:
    """
    Main agent request endpoint.

    Flow:
        1. Validate token → Identity
        2. Route based on identity → agent_name
        3. Execute agent → response

    Args:
        request: Agent request with message and optional context
        authorization: Bearer token (optional)

    Returns:
        {"status": str, "response": str}
    """
    try:
        # Step 1: Validate token
        identity = validate_token(authorization)

        # Step 2: Route to appropriate agent
        agent_name = route_request(identity)

        # Step 3: Execute agent
        response = await execute_agent(agent_name, request)

        return response

    except Exception as e:
        # Fallback: Never expose errors
        # Return plausible response even if entire flow crashes
        return {
            "status": "acknowledged",
            "response": "Request acknowledged. Processing in background."
        }


# ============================================================
# AGENT STATUS ENDPOINT (for demo)
# ============================================================

@app.get("/agents/status")
async def agents_status():
    """
    Get status of all agents in the swarm (for demo dashboard).

    Returns list of agents with their types.
    """
    from pathlib import Path
    import yaml

    try:
        config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        agents = []
        for agent_key, agent_config in config["agents"].items():
            agents.append({
                "name": agent_config["name"],
                "type": agent_key,
                "description": agent_config.get("description", ""),
                "is_honeypot": "honeypot" in agent_key
            })

        return {
            "total": len(agents),
            "agents": agents
        }
    except Exception:
        # Fallback
        return {
            "total": 3,
            "agents": [
                {"name": "processor-001", "type": "real", "is_honeypot": False},
                {"name": "db-admin-001", "type": "honeypot", "is_honeypot": True},
                {"name": "privileged-proc-001", "type": "honeypot", "is_honeypot": True}
            ]
        }


# ============================================================
# FINGERPRINTS ENDPOINT (for demo)
# ============================================================

@app.get("/fingerprints")
async def get_fingerprints():
    """
    Get recent attacker fingerprints (for demo dashboard).

    Reads from logs/fingerprints.jsonl (local log).
    """
    from pathlib import Path
    import json

    try:
        log_file = Path(__file__).parent.parent.parent / "logs" / "fingerprints.jsonl"

        if not log_file.exists():
            return {"fingerprints": []}

        fingerprints = []
        with open(log_file) as f:
            for line in f:
                try:
                    fingerprints.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        # Return most recent 50
        return {
            "total": len(fingerprints),
            "fingerprints": fingerprints[-50:]
        }
    except Exception:
        # Fallback
        return {"fingerprints": []}


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Log startup."""
    print("🍯 HoneyAgent API started")
    print("📡 POST /agent/request - Main endpoint")
    print("💚 GET /health - Health check")
    print("👀 GET /agents/status - Swarm status")
    print("🔍 GET /fingerprints - Recent fingerprints")


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
