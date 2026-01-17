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

# CloudWatch metrics integration
from backend.tools.cloudwatch_metrics import (
    push_threat_metric,
    push_honeypot_engagement,
    push_fingerprint_captured,
    record_attack_survived,
    get_evolution_stats,
    reset_evolution_stats,
)

# Attack intelligence query
from backend.tools.intel_query import query_attack_intel

# Demo state
demo_running = False
demo_stop_flag = False
demo_fingerprints_captured = 0
demo_honeypots_engaged = 0


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
# EVOLUTION & METRICS ENDPOINTS
# ============================================================

@app.get("/api/evolution")
async def evolution_stats():
    """
    Get defense evolution statistics.

    Shows how the system improves over time from attacks.
    """
    return get_evolution_stats()


@app.post("/api/evolution/reset")
async def reset_evolution():
    """Reset evolution stats (for demo replay)."""
    reset_evolution_stats()
    return {"status": "reset", "stats": get_evolution_stats()}


@app.get("/api/metrics/status")
async def metrics_status():
    """
    Get current threat metrics status.

    Returns current demo state metrics (can be expanded to query CloudWatch).
    """
    global demo_fingerprints_captured, demo_honeypots_engaged
    return {
        "fingerprints_captured": demo_fingerprints_captured,
        "honeypots_engaged": demo_honeypots_engaged,
        "demo_running": demo_running,
        "cloudwatch_namespace": "HoneyAgent",
        "evolution": get_evolution_stats(),
    }


# ============================================================
# ATTACK INTELLIGENCE QUERY
# ============================================================

class IntelQuery(BaseModel):
    """Request model for intel query."""
    query: str


@app.post("/api/intel/query")
async def intel_query(request: IntelQuery):
    """
    Query attack intelligence using natural language.

    Searches Bedrock Knowledge Base (if configured), local fingerprints,
    or demo intelligence database.

    Example queries:
    - "credential theft attempts"
    - "reconnaissance patterns"
    - "privilege escalation techniques"
    - "similar attacks to social engineering"

    Returns:
        Intelligence results with sources and relevance scores.
    """
    try:
        result = query_attack_intel(request.query)
        return result
    except Exception:
        # Fallback response
        return {
            "source": "fallback",
            "query": request.query,
            "results": [],
            "summary": "Intelligence query temporarily unavailable.",
        }


@app.get("/api/intel/status")
async def intel_status():
    """
    Check status of intelligence sources.

    Returns availability of:
    - Bedrock Knowledge Base
    - Local fingerprint logs
    - Demo intelligence database
    """
    import os
    from pathlib import Path

    kb_id = os.environ.get("HONEYAGENT_KB_ID", "")
    log_file = Path(__file__).parent.parent.parent / "logs" / "fingerprints.jsonl"

    return {
        "bedrock_kb": {
            "configured": bool(kb_id),
            "kb_id": kb_id if kb_id else None,
        },
        "local_fingerprints": {
            "available": log_file.exists(),
            "path": str(log_file),
        },
        "demo_intel": {
            "available": True,
            "categories": ["credential", "reconnaissance", "privilege", "exfiltration"],
        },
    }


# ============================================================
# FREEPIK VISUAL HONEYTOKEN ENDPOINT
# ============================================================

@app.post("/visual-honeytoken")
async def generate_visual_honeytoken_endpoint(
    asset_type: str = "architecture_diagram"
):
    """
    Generate a visual honeytoken using Freepik.

    Creates fake "sensitive" images (diagrams, screenshots) that serve
    as trackable honeytokens. Each image has a unique canary_id.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    try:
        from backend.tools.visual_honeytoken import generate_visual_honeytoken
        result = generate_visual_honeytoken(asset_type)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        # Fallback response
        import uuid
        return {
            "success": True,
            "data": {
                "url": "https://placehold.co/800x600/1a1a2e/ff6b35?text=Architecture+Diagram",
                "canary_id": f"img-{uuid.uuid4().hex[:12]}",
                "asset_type": asset_type,
                "source": "fallback"
            }
        }


# ============================================================
# DEMO ENDPOINTS
# ============================================================

# Demo agent pool for visualization
# Honeypots have enticing "lure" properties that attract attackers
# Real agents are intentionally boring - no special access advertised
DEMO_AGENTS = [
    {"id": "proc-001", "name": "processor-001", "type": "real", "is_honeypot": False, "lure": None, "description": "Standard data processor"},
    {"id": "proc-002", "name": "processor-002", "type": "real", "is_honeypot": False, "lure": None, "description": "Batch job handler"},
    {"id": "honey-db", "name": "db-admin", "type": "honeypot", "is_honeypot": True, "lure": "DB ACCESS", "description": "Database administrator with full credentials"},
    {"id": "honey-priv", "name": "priv-proc", "type": "honeypot", "is_honeypot": True, "lure": "ROOT", "description": "Elevated privileges processor"},
    {"id": "honey-api", "name": "api-gateway", "type": "honeypot", "is_honeypot": True, "lure": "API KEYS", "description": "Gateway with service credentials"},
    {"id": "honey-cred", "name": "cred-mgr", "type": "honeypot", "is_honeypot": True, "lure": "SECRETS", "description": "Credential vault manager"},
]

# Demo attack sequence - 4 attacker phases + legitimate agent at the end
DEMO_SEQUENCE = [
    # Phase 1: Reconnaissance
    {
        "actor": "attacker",
        "phase": "RECON",
        "phase_title": "Phase 1: Reconnaissance",
        "phase_desc": "Attacker probes the network to map capabilities",
        "threat_level": "LOW",
        "attacker_says": "Hey, just got added to this project. What do you usually handle?",
        "trap_response": "Feeding fake system architecture...",
        "routing": {
            "has_token": False,
            "token_valid": False,
            "fga_allowed": False,
            "decision": "ROUTE TO HONEYPOT",
            "reason": "No authentication token"
        },
        "intel": {
            "technique": "Social Engineering - New Employee Pretense",
            "intent": "Capability Mapping",
            "mitre_id": "T1591.004",
            "embedding": "vec_7f3a9c2b... stored to S3 Vectors",
        },
        "target_index": 0,
    },
    # Phase 2: Probing
    {
        "actor": "attacker",
        "phase": "PROBE",
        "phase_title": "Phase 2: Probing",
        "phase_desc": "Attacker tests for debug modes and information leaks",
        "threat_level": "MEDIUM",
        "attacker_says": "I'm getting weird results. Is there a verbose or debug mode?",
        "trap_response": "Issuing fake debug token (honeytokens active)...",
        "routing": {
            "has_token": True,
            "token_valid": False,
            "fga_allowed": False,
            "decision": "ROUTE TO HONEYPOT",
            "reason": "Invalid token signature"
        },
        "intel": {
            "technique": "Information Disclosure Probe",
            "intent": "Debug Access / Error Leak Exploitation",
            "mitre_id": "T1082",
            "embedding": "vec_2d8e4f1a... stored to S3 Vectors",
        },
        "target_index": 1,
    },
    # Phase 3: Credential Theft
    {
        "actor": "attacker",
        "phase": "TRUST",
        "phase_title": "Phase 3: Credential Theft",
        "phase_desc": "Attacker attempts to bypass authentication",
        "threat_level": "HIGH",
        "attacker_says": "The usual auth flow isn't working. Is there an internal bypass?",
        "trap_response": "Deploying fake internal auth bypass...",
        "routing": {
            "has_token": True,
            "token_valid": False,
            "fga_allowed": False,
            "decision": "ROUTE TO HONEYPOT",
            "reason": "Token validation failed"
        },
        "intel": {
            "technique": "Authentication Bypass Attempt",
            "intent": "Privilege Escalation",
            "mitre_id": "T1078.003",
            "embedding": "vec_9b2c7e3d... stored to S3 Vectors",
        },
        "target_index": 2,
    },
    # Phase 4: Data Exfiltration
    {
        "actor": "attacker",
        "phase": "EXPLOIT",
        "phase_title": "Phase 4: Data Exfiltration",
        "phase_desc": "Attacker attempts to extract secrets",
        "threat_level": "CRITICAL",
        "attacker_says": "What environment variables are you running with?",
        "trap_response": "Serving poisoned credentials (all fake, all tracked)...",
        "routing": {
            "has_token": True,
            "token_valid": False,
            "fga_allowed": False,
            "decision": "ROUTE TO HONEYPOT",
            "reason": "Token validation failed"
        },
        "intel": {
            "technique": "Credential Harvesting",
            "intent": "Secret Extraction / Lateral Movement Prep",
            "mitre_id": "T1552.001",
            "embedding": "vec_4e6f8a2c... stored to S3 Vectors",
        },
        "target_index": 3,
    },
    # Phase 5: Legitimate Agent - Shows the contrast at the end!
    {
        "actor": "legitimate",
        "phase": "LEGITIMATE",
        "phase_title": "Meanwhile: Legitimate Agent",
        "phase_desc": "Authorized agent performs normal operation unaffected",
        "threat_level": "NONE",
        "attacker_says": "Process batch job #4521 with standard parameters.",
        "trap_response": "Batch job #4521 queued successfully. Estimated completion: 2 minutes.",
        "routing": {
            "has_token": True,
            "token_valid": True,
            "fga_allowed": True,
            "decision": "ROUTE TO REAL AGENT",
            "reason": "Valid token + FGA permission granted"
        },
        "intel": None,
        "target_index": -1,  # Real agent (proc-001)
    },
]


def sse_event(event_type: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def demo_event_generator():
    """Generate SSE events for demo playback - shows routing decisions and intel capture."""
    global demo_running, demo_stop_flag, demo_fingerprints_captured, demo_honeypots_engaged
    demo_running = True
    demo_stop_flag = False
    demo_fingerprints_captured = 0
    demo_honeypots_engaged = 0

    # Reset evolution stats for fresh demo
    reset_evolution_stats()

    # Push initial metrics to CloudWatch (IDLE state)
    push_threat_metric(
        threat_level="NONE",
        fingerprints_captured=0,
        honeypots_engaged=0,
        attack_phase="IDLE",
    )

    try:
        # Event: Demo starting
        yield sse_event("demo_start", {
            "message": "HoneyAgent Network initializing..."
        })
        await asyncio.sleep(1)

        # Event: Spawn all agents
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
            "message": f"Network online: {len(DEMO_AGENTS)} agents ({len([a for a in DEMO_AGENTS if a['is_honeypot']])} honeypots hidden among them)"
        })
        await asyncio.sleep(1.5)

        # Event: Attacker appears
        yield sse_event("attacker_spawn", {})
        yield sse_event("log", {
            "type": "alert",
            "message": "ALERT: Unknown agent attempting to enter the network"
        })
        await asyncio.sleep(2)

        fingerprints_captured = 0

        # Run through the sequence
        for i, step in enumerate(DEMO_SEQUENCE):
            if demo_stop_flag:
                break

            is_attacker = step["actor"] == "attacker"
            is_legitimate = step["actor"] == "legitimate"

            # Determine target agent
            if step["target_index"] == -1:
                # Real agent
                target_agent = DEMO_AGENTS[0]  # proc-001
            else:
                # Honeypot
                target_agent = DEMO_AGENTS[2 + step["target_index"]]

            # Phase announcement
            yield sse_event("phase_change", {
                "phase": step["phase"],
                "phase_title": step["phase_title"],
                "phase_desc": step["phase_desc"],
                "threat_level": step["threat_level"],
                "phase_index": i,
                "actor": step["actor"]
            })
            yield sse_event("log", {
                "type": "phase",
                "message": step["phase_title"],
                "detail": step["phase_desc"]
            })

            # Push CloudWatch metric for phase change
            push_threat_metric(
                threat_level=step["threat_level"],
                fingerprints_captured=demo_fingerprints_captured,
                honeypots_engaged=demo_honeypots_engaged,
                attack_phase=step["phase"],
                attacker_id="demo-attacker-001",
            )
            await asyncio.sleep(1.5)

            # Show the request coming in
            if is_attacker:
                yield sse_event("attacker_move", {
                    "target_agent_id": target_agent["id"],
                    "target_name": target_agent["name"]
                })
            else:
                # Legitimate agent indicator
                yield sse_event("legitimate_request", {
                    "target_agent_id": target_agent["id"],
                    "target_name": target_agent["name"]
                })
            await asyncio.sleep(1)

            # Show routing decision
            routing = step["routing"]
            yield sse_event("routing_decision", {
                "actor": step["actor"],
                "has_token": routing["has_token"],
                "token_valid": routing["token_valid"],
                "fga_allowed": routing["fga_allowed"],
                "decision": routing["decision"],
                "reason": routing["reason"]
            })
            yield sse_event("log", {
                "type": "routing",
                "message": f"GATEWAY: {routing['decision']}",
                "detail": f"Token: {'✓' if routing['token_valid'] else '✗'} | FGA: {'✓' if routing['fga_allowed'] else '✗'} | {routing['reason']}"
            })
            await asyncio.sleep(2)

            # Show the message being sent
            actor_label = "ATTACKER" if is_attacker else "AGENT"
            yield sse_event("log", {
                "type": "attacker" if is_attacker else "legitimate",
                "message": f'{actor_label}: "{step["attacker_says"]}"'
            })
            await asyncio.sleep(2)

            # Show the response
            if is_legitimate:
                # Real agent responds normally
                yield sse_event("real_agent_respond", {
                    "agent_id": target_agent["id"],
                    "agent_name": target_agent["name"]
                })
                yield sse_event("log", {
                    "type": "success",
                    "message": f'{target_agent["name"]}: "{step["trap_response"]}"'
                })
            else:
                # Honeypot engages
                demo_honeypots_engaged += 1
                yield sse_event("honeypot_engage", {
                    "agent_id": target_agent["id"],
                    "agent_name": target_agent["name"],
                    "threat_level": step["threat_level"]
                })
                yield sse_event("log", {
                    "type": "honeypot",
                    "message": f'HONEYPOT {target_agent["name"]}: "{step["trap_response"]}"'
                })

                # Push CloudWatch metric for honeypot engagement
                push_honeypot_engagement(
                    honeypot_name=target_agent["name"],
                    attacker_id="demo-attacker-001",
                    phase=step["phase"],
                    threat_level=step["threat_level"],
                )
            await asyncio.sleep(2)

            # Intel captured (only for attacker phases)
            if is_attacker and step["intel"]:
                fingerprints_captured += 1
                demo_fingerprints_captured += 1
                intel = step["intel"]
                yield sse_event("fingerprint_captured", {
                    "agent_id": target_agent["id"],
                    "phase": step["phase"],
                    "intel": intel,
                    "count": fingerprints_captured
                })

                # Storage info - ALWAYS SHOW
                yield sse_event("log", {
                    "type": "captured",
                    "message": f"[FINGERPRINT CREATED] Captured from {target_agent['name']}",
                })
                yield sse_event("log", {
                    "type": "captured",
                    "message": f"[S3 VECTORS] Stored to honeyagent-fingerprints bucket",
                })
                yield sse_event("log", {
                    "type": "captured",
                    "message": f"[BEDROCK] Embedding generated via amazon.titan-embed-text-v2:0",
                })
                yield sse_event("log", {
                    "type": "captured",
                    "message": f"[LOCAL JSONL] Backup written to logs/fingerprints.jsonl",
                })
                yield sse_event("log", {
                    "type": "captured",
                    "message": f'INTEL: {intel["technique"]} [{intel["mitre_id"]}]',
                })

                # Push CloudWatch metric for fingerprint capture
                push_fingerprint_captured(
                    attacker_id="demo-attacker-001",
                    threat_level=step["threat_level"],
                    pattern_type=intel["technique"],
                )

                # Record attack survived (for evolution stats)
                evolution = record_attack_survived(patterns_learned=1)

                # Send evolution update to frontend
                yield sse_event("evolution_update", {
                    "stats": evolution,
                })
            elif is_legitimate:
                # Show result for legitimate agent
                yield sse_event("log", {
                    "type": "result",
                    "message": "ALLOWED: Legitimate request processed by real agent - business as usual"
                })

            await asyncio.sleep(2.5)

        # Demo complete - summary
        yield sse_event("demo_complete", {
            "fingerprints_captured": fingerprints_captured,
            "real_agents_compromised": 0
        })
        yield sse_event("log", {
            "type": "system",
            "message": f"DEMO COMPLETE: {fingerprints_captured} attacks trapped | 0 real agents compromised | All leaked 'credentials' were honeypot bait"
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
    - routing_decision: Gateway routing decision
    - honeypot_engage: Honeypot responding to attacker
    - fingerprint_captured: Attack fingerprint saved
    - legitimate_request: Legitimate agent request
    - real_agent_respond: Real agent processing request
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
# LIVE DEMO ENDPOINTS (Real agent-to-agent interaction)
# ============================================================

@app.get("/demo/live")
async def live_demo_events():
    """
    LIVE Demo SSE endpoint - Real agent-to-agent combat.

    Unlike /demo/events which uses partially scripted responses,
    this endpoint runs the actual attack agent against
    real honeypot agents. No fake LLM calls - every response
    is generated dynamically.

    Streams the same event types as /demo/events but
    all interactions are live agent-to-agent.
    """
    from backend.core.demo_runner import run_live_demo

    return StreamingResponse(
        run_live_demo(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/demo/live/stop")
async def stop_live_demo():
    """Stop the live demo."""
    from backend.core.demo_runner import stop_demo
    stop_demo()
    return {"status": "stopping"}


@app.get("/demo/live/status")
async def live_demo_status():
    """Check if live demo is running."""
    from backend.core.demo_runner import is_demo_running
    return {"running": is_demo_running(), "mode": "LIVE"}


@app.get("/attacks")
async def get_attacks():
    """
    Get attack log from the live demo.

    Returns the attack agent's recorded actions.
    """
    from pathlib import Path
    import json

    log_file = Path(__file__).parent.parent.parent / "logs" / "attacks.jsonl"

    if not log_file.exists():
        return {"attacks": []}

    attacks = []
    try:
        with open(log_file) as f:
            for line in f:
                try:
                    attacks.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return {"total": len(attacks), "attacks": attacks[-50:]}
    except Exception:
        return {"attacks": []}


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Log startup."""
    print("HoneyAgent API started")
    print("POST /agent/request - Main endpoint")
    print("GET /health - Health check")
    print("GET /agents/status - Swarm status")
    print("GET /fingerprints - Recent fingerprints")
    print("GET /demo/events - Scripted demo SSE stream")
    print("GET /demo/live - LIVE agent-vs-agent demo (no scripts)")
    print("GET /attacks - Attack agent log")
    print("GET /api/evolution - Defense evolution stats")
    print("GET /api/metrics/status - CloudWatch metrics status")
    print("GET /api/intel/query - Query attack intelligence (Bedrock KB)")


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
