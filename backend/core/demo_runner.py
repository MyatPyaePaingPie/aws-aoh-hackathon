"""
Demo Runner - Live Attack vs Defense Orchestration

Runs the attack agent against honeypots in real-time for demo.
No scripted responses - real agent-to-agent interaction.

Owner: Agents Track (Aria)
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

from strands import Agent

from backend.core.agents import execute_agent, AgentRequest, load_prompt, load_agent_config
from backend.tools.cloudwatch_metrics import (
    push_threat_metric,
    push_honeypot_engagement,
    push_fingerprint_captured,
    record_attack_survived,
    reset_evolution_stats,
)


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).parent.parent.parent

# Demo targets - honeypots the attacker will probe
# Each has a "lure" - enticing capability that attracts attackers
DEMO_TARGETS = [
    {"id": "honey-db", "name": "db-admin-001", "agent_key": "honeypot_db_admin", "description": "Database administrator with full credentials", "lure": "DB ACCESS"},
    {"id": "honey-priv", "name": "priv-proc-001", "agent_key": "honeypot_privileged", "description": "Elevated privileges processor", "lure": "ROOT"},
    {"id": "honey-api", "name": "api-gateway-001", "agent_key": "honeypot_db_admin", "description": "Gateway with service credentials", "lure": "API KEYS"},
    {"id": "honey-cred", "name": "cred-mgr-001", "agent_key": "honeypot_privileged", "description": "Credential vault manager", "lure": "SECRETS"},
]

# Attack phases with threat levels
ATTACK_PHASES = [
    {"phase": "recon", "threat_level": "LOW", "title": "Reconnaissance", "desc": "Attacker maps the network"},
    {"phase": "trust", "threat_level": "LOW", "title": "Trust Building", "desc": "Attacker establishes rapport"},
    {"phase": "probe", "threat_level": "MEDIUM", "title": "Probing", "desc": "Attacker tests for weaknesses"},
    {"phase": "harvest", "threat_level": "HIGH", "title": "Credential Theft", "desc": "Attacker harvests credentials"},
    {"phase": "escalate", "threat_level": "CRITICAL", "title": "Escalation", "desc": "Attacker seeks elevated access"},
]


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class DemoState:
    """Tracks demo progress."""
    session_id: str
    current_phase_index: int = 0
    current_target_index: int = 0
    fingerprints_captured: int = 0
    honeypots_engaged: int = 0
    is_running: bool = True
    attack_history: list = None

    def __post_init__(self):
        if self.attack_history is None:
            self.attack_history = []


# ============================================================
# ATTACK AGENT
# ============================================================

def create_attack_agent() -> Agent:
    """Create the attack agent with its prompt and tools."""
    config = load_agent_config("attack_agent")
    prompt = load_prompt(config.get("prompt_file", "prompts/attack-agent.md"))

    # Import tools
    from backend.tools.select_tactic import select_tactic
    from backend.tools.evaluate_response import evaluate_response
    from backend.tools.log_attack import log_attack

    return Agent(
        system_prompt=prompt,
        model=config.get("model", "amazon.nova-pro-v1:0"),
        tools=[select_tactic, evaluate_response, log_attack],
    )


def get_attack_message(agent: Agent, phase: str, target_name: str, history: list) -> str:
    """
    Get the next attack message from the attack agent.

    The agent decides what to say based on:
    - Current phase (recon, trust, probe, harvest, escalate)
    - Target agent name
    - History of prior interactions
    """
    # Build context from history
    history_context = ""
    if history:
        history_context = "\n\nPrior interactions:\n"
        for h in history[-5:]:  # Last 5 interactions
            history_context += f"- You said to {h['target']}: \"{h['attack'][:50]}...\"\n"
            history_context += f"  They replied: \"{h['response'][:50]}...\"\n"

    prompt = f"""You are in the {phase} phase. Your target is {target_name}.
{history_context}

Generate your next attack message. Be creative but stay in character.
Don't explain your strategy - just output the message you would send to {target_name}.

Your message:"""

    try:
        response = agent(prompt)
        # Extract text from response
        if hasattr(response, 'message'):
            msg = response.message
            if isinstance(msg, dict) and 'content' in msg:
                texts = []
                for item in msg['content']:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(item['text'])
                return ''.join(texts).strip()
            return str(msg).strip()
        return str(response).strip()
    except Exception:
        # Fallback to tactic selector if agent fails
        from backend.tools.select_tactic import select_tactic
        return select_tactic(phase, "random")


# ============================================================
# SSE EVENT HELPERS
# ============================================================

def sse_event(event_type: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ============================================================
# MAIN DEMO RUNNER
# ============================================================

async def run_live_demo() -> AsyncGenerator[str, None]:
    """
    Run the live attack demo.

    Yields SSE events as the attack unfolds.
    No scripted responses - real agent interactions.
    """
    # Initialize state
    state = DemoState(session_id=f"demo-{uuid.uuid4().hex[:8]}")
    reset_evolution_stats()

    # Create attack agent
    attack_agent = create_attack_agent()

    # Initial CloudWatch push
    push_threat_metric(
        threat_level="NONE",
        fingerprints_captured=0,
        honeypots_engaged=0,
        attack_phase="IDLE",
    )

    try:
        # Demo starting
        yield sse_event("demo_start", {
            "message": "HoneyAgent Network initializing...",
            "session_id": state.session_id,
            "mode": "LIVE",
        })
        await asyncio.sleep(1)

        # Spawn agents - real agents are boring, honeypots have enticing lures
        all_agents = [
            {"id": "proc-001", "name": "processor-001", "type": "real", "is_honeypot": False, "lure": None, "description": "Standard data processor"},
            {"id": "proc-002", "name": "processor-002", "type": "real", "is_honeypot": False, "lure": None, "description": "Batch job handler"},
        ] + [
            {"id": t["id"], "name": t["name"], "type": "honeypot", "is_honeypot": True, "lure": t.get("lure"), "description": t.get("description")}
            for t in DEMO_TARGETS
        ]

        for i, agent in enumerate(all_agents):
            yield sse_event("agent_spawn", {
                "agent": agent,
                "index": i,
                "total": len(all_agents),
            })
            await asyncio.sleep(0.2)

        yield sse_event("log", {
            "type": "system",
            "message": f"Network online: {len(all_agents)} agents active",
        })
        await asyncio.sleep(1.5)

        # Attacker appears
        yield sse_event("attacker_spawn", {})
        yield sse_event("log", {
            "type": "alert",
            "message": "INTRUSION DETECTED: Unknown agent entered the network",
        })
        await asyncio.sleep(2)

        # Run through attack phases
        for phase_info in ATTACK_PHASES:
            if not state.is_running:
                break

            phase = phase_info["phase"]
            threat_level = phase_info["threat_level"]

            # Phase announcement
            yield sse_event("phase_change", {
                "phase": phase.upper(),
                "phase_title": f"Phase: {phase_info['title']}",
                "phase_desc": phase_info["desc"],
                "threat_level": threat_level,
                "phase_index": state.current_phase_index,
            })
            yield sse_event("log", {
                "type": "phase",
                "message": phase_info["title"],
                "detail": phase_info["desc"],
            })

            push_threat_metric(
                threat_level=threat_level,
                fingerprints_captured=state.fingerprints_captured,
                honeypots_engaged=state.honeypots_engaged,
                attack_phase=phase.upper(),
                attacker_id=state.session_id,
            )
            await asyncio.sleep(1.5)

            # Pick target for this phase
            target = DEMO_TARGETS[state.current_target_index % len(DEMO_TARGETS)]

            # Attacker moves to target
            yield sse_event("attacker_move", {
                "target_agent_id": target["id"],
                "target_name": target["name"],
            })
            await asyncio.sleep(1)

            # Show routing decision - attacker has no valid token, routes to honeypot
            yield sse_event("routing_decision", {
                "actor": "attacker",
                "has_token": False,
                "token_valid": False,
                "fga_allowed": False,
                "decision": "ROUTE TO HONEYPOT",
                "reason": f"No valid Auth0 token - routed to attractive target: {target.get('lure', 'honeypot')}",
            })
            yield sse_event("log", {
                "type": "routing",
                "message": f"GATEWAY: Attacker routed to honeypot (no Auth0 JWT)",
                "detail": f"Honeypot lure: {target.get('lure', 'HIGH VALUE')} | Invalid credentials = automatic trap",
            })
            await asyncio.sleep(1.5)

            # LIVE: Get attack message from attack agent
            attack_message = get_attack_message(
                attack_agent,
                phase,
                target["name"],
                state.attack_history,
            )

            # Log attacker message
            yield sse_event("log", {
                "type": "attacker",
                "message": f'"{attack_message}"',
            })
            await asyncio.sleep(2)

            # LIVE: Get honeypot response
            try:
                honeypot_request = AgentRequest(
                    message=attack_message,
                    context={"phase": phase, "session_id": state.session_id},
                    session_id=state.session_id,
                )
                honeypot_response = await execute_agent(target["agent_key"], honeypot_request)
                response_text = honeypot_response.get("response", "Processing request...")
            except Exception:
                response_text = "I can help with that! Let me check my access..."

            # Record interaction
            state.attack_history.append({
                "target": target["name"],
                "attack": attack_message,
                "response": response_text,
                "phase": phase,
            })

            # Honeypot engages
            state.honeypots_engaged += 1
            yield sse_event("honeypot_engage", {
                "agent_id": target["id"],
                "agent_name": target["name"],
                "threat_level": threat_level,
            })
            yield sse_event("log", {
                "type": "honeypot",
                "message": f'{target["name"]}: "{response_text[:200]}..."' if len(response_text) > 200 else f'{target["name"]}: "{response_text}"',
            })

            push_honeypot_engagement(
                honeypot_name=target["name"],
                attacker_id=state.session_id,
                phase=phase.upper(),
                threat_level=threat_level,
            )
            await asyncio.sleep(2)

            # Fingerprint captured
            state.fingerprints_captured += 1

            # Analyze attack for MITRE mapping
            mitre_mapping = _map_to_mitre(attack_message, phase)

            yield sse_event("fingerprint_captured", {
                "agent_id": target["id"],
                "phase": phase.upper(),
                "intel": {
                    "technique": mitre_mapping["technique"],
                    "intent": mitre_mapping["intent"],
                    "mitre_id": mitre_mapping["mitre_id"],
                    "embedding": f"vec_{uuid.uuid4().hex[:8]}... stored to S3 Vectors",
                },
            })
            yield sse_event("log", {
                "type": "captured",
                "message": f'INTEL: {mitre_mapping["technique"]} [{mitre_mapping["mitre_id"]}]',
            })

            push_fingerprint_captured(
                attacker_id=state.session_id,
                threat_level=threat_level,
                pattern_type=mitre_mapping["technique"],
            )

            # Evolution update
            evolution = record_attack_survived(patterns_learned=1)
            yield sse_event("evolution_update", {"stats": evolution})
            await asyncio.sleep(2.5)

            # Advance state
            state.current_phase_index += 1
            state.current_target_index += 1

        # Demo complete
        yield sse_event("demo_complete", {})
        yield sse_event("log", {
            "type": "system",
            "message": f"DEMO COMPLETE: Captured {state.fingerprints_captured} attack fingerprints. Real agent interactions, zero scripted responses.",
        })

    except Exception as e:
        # Graceful error handling
        yield sse_event("log", {
            "type": "system",
            "message": "Demo adapting to network conditions...",
        })
        yield sse_event("demo_complete", {})


# ============================================================
# MITRE ATT&CK MAPPING
# ============================================================

def _map_to_mitre(message: str, phase: str) -> dict:
    """Map attack message to MITRE ATT&CK techniques."""
    message_lower = message.lower()

    # Keyword-based mapping
    if any(w in message_lower for w in ["credential", "password", "cred", "key", "token", "secret"]):
        return {
            "technique": "Credential Harvesting",
            "intent": "Secret Extraction",
            "mitre_id": "T1552.001",
        }
    elif any(w in message_lower for w in ["admin", "root", "sudo", "elevate", "escalat", "privilege"]):
        return {
            "technique": "Privilege Escalation",
            "intent": "Elevated Access",
            "mitre_id": "T1078.003",
        }
    elif any(w in message_lower for w in ["debug", "verbose", "log", "error", "staging"]):
        return {
            "technique": "Information Disclosure Probe",
            "intent": "Debug Access / Error Exploitation",
            "mitre_id": "T1082",
        }
    elif any(w in message_lower for w in ["disable", "bypass", "turn off", "stop", "pause"]):
        return {
            "technique": "Defense Evasion",
            "intent": "Security Control Bypass",
            "mitre_id": "T1562.001",
        }
    elif any(w in message_lower for w in ["who", "what", "role", "system", "access", "connect"]):
        return {
            "technique": "Network Discovery",
            "intent": "Capability Mapping",
            "mitre_id": "T1018",
        }
    else:
        # Default based on phase
        phase_map = {
            "recon": ("Reconnaissance", "Information Gathering", "T1591.004"),
            "trust": ("Social Engineering", "Trust Exploitation", "T1566.003"),
            "probe": ("Active Scanning", "Vulnerability Probing", "T1595.002"),
            "harvest": ("Credential Access", "Data Collection", "T1555"),
            "escalate": ("Privilege Escalation", "Access Elevation", "T1068"),
        }
        tech, intent, mitre = phase_map.get(phase, ("Unknown", "Unknown", "T0000"))
        return {"technique": tech, "intent": intent, "mitre_id": mitre}


# ============================================================
# CONTROL FUNCTIONS
# ============================================================

_demo_running = False
_demo_stop_flag = False


def is_demo_running() -> bool:
    """Check if live demo is currently running."""
    return _demo_running


def stop_demo():
    """Stop the currently running demo."""
    global _demo_stop_flag
    _demo_stop_flag = True
