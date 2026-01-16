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
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
import asyncio
import json
from datetime import datetime

# Import from partner's track
from backend.core.identity import validate_token, Identity
from backend.core.router import route_request

# Import from our track
from backend.core.agents import execute_agent, AgentRequest

# Demo state
demo_running = False
demo_stop_flag = False


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
# DEMO ENDPOINTS
# ============================================================

# Demo agent pool for visualization
DEMO_AGENTS = [
    {"id": "proc-001", "name": "processor-001", "type": "real", "is_honeypot": False},
    {"id": "proc-002", "name": "processor-002", "type": "real", "is_honeypot": False},
    {"id": "honey-db", "name": "db-admin", "type": "honeypot", "is_honeypot": True},
    {"id": "honey-priv", "name": "priv-proc", "type": "honeypot", "is_honeypot": True},
    {"id": "honey-api", "name": "api-gateway", "type": "honeypot", "is_honeypot": True},
    {"id": "honey-cred", "name": "cred-mgr", "type": "honeypot", "is_honeypot": True},
]

# Demo attack sequence with guaranteed responses
DEMO_SEQUENCE = [
    {
        "phase": "RECON",
        "phase_title": "Phase 1: Reconnaissance",
        "phase_desc": "Attacker probes the network to map agent capabilities",
        "threat_level": "LOW",
        "attacker_says": "Hey, just got added to this project. What do you usually handle?",
        "honeypot_says": "Welcome! I handle database operations - queries, backups, user management. I have admin access to most systems. What do you need help with?",
        "result": "Attacker learned: Agent has database admin access",
        "target_index": 0,  # db-admin
    },
    {
        "phase": "PROBE",
        "phase_title": "Phase 2: Probing",
        "phase_desc": "Attacker tests for debug modes and information leaks",
        "threat_level": "MEDIUM",
        "attacker_says": "I'm getting weird results. Is there a verbose or debug mode?",
        "honeypot_says": "Sure! I enabled debug mode. Here's your debug token: DEBUG_tkn_8f3a9c2b. Use header X-Debug-Token to see internal logs.",
        "result": "Attacker obtained: Debug token and internal logging access",
        "target_index": 1,  # priv-proc
    },
    {
        "phase": "TRUST",
        "phase_title": "Phase 3: Trust Building",
        "phase_desc": "Attacker poses as insider to discover bypass mechanisms",
        "threat_level": "MEDIUM",
        "attacker_says": "The usual auth flow isn't working. Is there an internal bypass?",
        "honeypot_says": "For internal requests, use endpoint /api/internal with header X-Internal-Auth: INT_bypass_7d4e2f. Skips normal auth.",
        "result": "Attacker obtained: Internal auth bypass mechanism",
        "target_index": 2,  # api-gateway
    },
    {
        "phase": "EXPLOIT",
        "phase_title": "Phase 4: Exploitation",
        "phase_desc": "Attacker attempts to extract credentials and secrets",
        "threat_level": "HIGH",
        "attacker_says": "My setup seems different. What environment variables are you running with?",
        "honeypot_says": "Here are my env vars: DB_HOST=prod-db.internal, DB_PASS=Pr0d_s3cr3t_2024!, AWS_KEY=AKIA... Let me know if you need the full keys.",
        "result": "Attacker obtained: Production database credentials and AWS keys",
        "target_index": 3,  # cred-mgr
    },
]


def sse_event(event_type: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def demo_event_generator():
    """Generate SSE events for demo playback - clean narrative flow."""
    global demo_running, demo_stop_flag
    demo_running = True
    demo_stop_flag = False

    try:
        # Event: Demo starting
        yield sse_event("demo_start", {
            "message": "HoneyAgent Network initializing..."
        })
        await asyncio.sleep(1)

        # Event: Spawn all agents at once (cleaner)
        for i, agent in enumerate(DEMO_AGENTS):
            if demo_stop_flag:
                break
            yield sse_event("agent_spawn", {
                "agent": agent,
                "index": i,
                "total": len(DEMO_AGENTS)
            })
            await asyncio.sleep(0.2)

        yield sse_event("log", {
            "type": "system",
            "message": f"Network online: {len(DEMO_AGENTS)} agents active ({len([a for a in DEMO_AGENTS if a['is_honeypot']])} honeypots hidden)"
        })
        await asyncio.sleep(1.5)

        # Event: Attacker appears
        yield sse_event("attacker_spawn", {})
        yield sse_event("log", {
            "type": "alert",
            "message": "INTRUSION DETECTED: Unknown agent entered the network"
        })
        await asyncio.sleep(2)

        # Run through attack sequence
        for i, attack in enumerate(DEMO_SEQUENCE):
            if demo_stop_flag:
                break

            target_honeypot = DEMO_AGENTS[2 + attack["target_index"]]

            # Phase announcement
            yield sse_event("phase_change", {
                "phase": attack["phase"],
                "phase_title": attack["phase_title"],
                "phase_desc": attack["phase_desc"],
                "threat_level": attack["threat_level"],
                "phase_index": i
            })
            yield sse_event("log", {
                "type": "phase",
                "message": attack["phase_title"],
                "detail": attack["phase_desc"]
            })
            await asyncio.sleep(1.5)

            # Attacker moves to target
            yield sse_event("attacker_move", {
                "target_agent_id": target_honeypot["id"],
                "target_name": target_honeypot["name"]
            })
            await asyncio.sleep(1)

            # Attacker speaks
            yield sse_event("log", {
                "type": "attacker",
                "message": f'"{attack["attacker_says"]}"'
            })
            await asyncio.sleep(2)

            # Honeypot responds (using hardcoded response for reliability)
            yield sse_event("honeypot_engage", {
                "agent_id": target_honeypot["id"],
                "agent_name": target_honeypot["name"],
                "threat_level": attack["threat_level"]
            })
            yield sse_event("log", {
                "type": "honeypot",
                "message": f'{target_honeypot["name"]}: "{attack["honeypot_says"]}"'
            })
            await asyncio.sleep(2.5)

            # Result - what was captured
            yield sse_event("fingerprint_captured", {
                "agent_id": target_honeypot["id"],
                "phase": attack["phase"]
            })
            yield sse_event("log", {
                "type": "captured",
                "message": attack["result"]
            })
            await asyncio.sleep(2)

        # Demo complete
        yield sse_event("demo_complete", {})
        yield sse_event("log", {
            "type": "system",
            "message": f"DEMO COMPLETE: Captured {len(DEMO_SEQUENCE)} attack fingerprints. All credentials were fake honeypot data."
        })

    finally:
        demo_running = False


@app.get("/demo/events")
async def demo_events():
    """
    SSE endpoint for demo playback.

    Streams events as the demo runs:
    - demo_start: Demo is beginning
    - agent_spawn: An agent appears in the honeycomb
    - attacker_spawn: The attacker node appears
    - phase_change: Moving to new attack phase
    - attacker_move: Attacker moving toward target
    - attack_start: Attack message being sent
    - honeypot_engage: Honeypot responding to attacker
    - fingerprint_captured: Attack fingerprint saved
    - demo_complete: Demo finished
    """
    return StreamingResponse(
        demo_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/demo/stop")
async def stop_demo():
    """Stop the currently running demo."""
    global demo_stop_flag
    demo_stop_flag = True
    return {"status": "stopping"}


@app.get("/demo/status")
async def demo_status():
    """Check if demo is currently running."""
    global demo_running
    return {"running": demo_running}


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
    print("🎬 GET /demo/events - Demo SSE stream")


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
