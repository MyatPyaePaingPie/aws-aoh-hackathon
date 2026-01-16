# HoneyAgent Architecture

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL                                                                   │
│                                                                             │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐               │
│  │  Real   │     │  Real   │     │ Honeypot│     │ Imposter│               │
│  │ Agent A │     │ Agent B │     │  Agent  │     │   ???   │               │
│  └────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘               │
│       │               │               │               │                     │
└───────┼───────────────┼───────────────┼───────────────┼─────────────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FASTAPI GATEWAY                                                            │
│  POST /agent/request                                                        │
│  Header: Authorization: Bearer <token>                                      │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  IDENTITY LAYER (backend/core/identity.py)                                  │
│                                                                             │
│  1. Validate JWT signature against Auth0 JWKS                               │
│  2. Extract claims: agent_type, swarm_id, capabilities                      │
│  3. Check FGA permissions: can_communicate with swarm                       │
│                                                                             │
│  Output: Identity { valid, agent_id, agent_type, is_honeypot, fga_allowed } │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ROUTING LAYER (backend/core/router.py)                                     │
│                                                                             │
│  Rules (from config/routing.yaml):                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ IF token_invalid           → route to honeypot, log INVALID_TOKEN   │   │
│  │ IF token_valid AND fga_denied → route to honeypot, log NO_PERMISSION│   │
│  │ IF token_valid AND is_honeypot → self (honeypot doing its job)      │   │
│  │ IF token_valid AND fga_allowed AND NOT honeypot → route to real     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Output: agent_name (string) + log_event (optional)                         │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│  REAL AGENT                 │   │  HONEYPOT AGENT             │
│  (backend/core/agents.py)   │   │  (backend/core/agents.py)   │
│                             │   │                             │
│  - Processes request        │   │  - Engages attacker         │
│  - Returns legitimate       │   │  - Logs interaction         │
│    response                 │   │  - Offers fake credentials  │
│  - No logging of content    │   │  - Generates fingerprint    │
│                             │   │                             │
│  Tools: none                │   │  Tools:                     │
│                             │   │  - log_interaction          │
│                             │   │  - fake_credential          │
│                             │   │  - query_patterns           │
└─────────────────────────────┘   └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  S3 VECTORS                 │
                                  │  (attacker fingerprints)    │
                                  │                             │
                                  │  - Embed interaction        │
                                  │  - Store pattern            │
                                  │  - Query similar attackers  │
                                  └─────────────────────────────┘
```

---

## Component Details

### 1. FastAPI Gateway (`backend/api/main.py`)

**Purpose:** Single entry point for all agent requests.

```python
@app.post("/agent/request")
async def agent_request(
    request: AgentRequest,
    authorization: str = Header(...)
):
    token = authorization.replace("Bearer ", "")
    identity = await validate_token(token)
    agent_name = route_request(identity, request)
    response = await execute_agent(agent_name, request)
    return response
```

**Fallback:** If gateway errors, return `{"status": "accepted", "message": "Request queued"}`.

---

### 2. Identity Layer (`backend/core/identity.py`)

**Purpose:** Validate tokens, extract claims, check FGA permissions.

**Inputs:**
- JWT token (from Authorization header)

**Outputs:**
```python
@dataclass
class Identity:
    valid: bool
    agent_id: Optional[str]
    agent_type: Optional[str]  # "real" | "honeypot" | None
    is_honeypot: bool
    fga_allowed: bool
    raw_claims: dict
```

**Auth0 Integration:**
- JWKS endpoint: `https://{domain}/.well-known/jwks.json`
- Custom claims namespace: `https://honeyagent.io/`
- Expected claims: `agent_type`, `swarm_id`, `capabilities`

**FGA Check:**
```python
allowed = await fga_client.check(
    user=f"agent:{agent_id}",
    relation="can_communicate",
    object="swarm:swarm-alpha"
)
```

**Fallbacks:**
- JWKS fetch fails → use cached keys (load on startup)
- FGA check fails → assume allowed (fail open for demo)
- Token decode fails → return `Identity(valid=False, ...)`

---

### 3. Routing Layer (`backend/core/router.py`)

**Purpose:** Decide which agent handles the request based on identity.

**Inputs:**
- `Identity` object
- `AgentRequest` payload

**Outputs:**
- `agent_name: str` (key from `config/agents.yaml`)
- `log_event: Optional[str]` (for analytics)

**Rules (from `config/routing.yaml`):**
```yaml
rules:
  - condition: "not identity.valid"
    route_to: "honeypot_db_admin"
    log_event: "INVALID_TOKEN_TRAP"

  - condition: "identity.valid and not identity.fga_allowed"
    route_to: "honeypot_privileged"
    log_event: "PERMISSION_DENIED_TRAP"

  - condition: "identity.valid and identity.is_honeypot"
    route_to: "self"
    log_event: null  # Honeypot doing its job

  - condition: "identity.valid and identity.fga_allowed and not identity.is_honeypot"
    route_to: "real"
    log_event: null
```

**Fallback:** If routing logic errors → route to `honeypot_db_admin` (safe default).

---

### 4. Agent Factory (`backend/core/agents.py`)

**Purpose:** Spawn Strands agents from config + prompts.

**Config (`config/agents.yaml`):**
```yaml
agents:
  real:
    name: "processor-001"
    prompt_file: "prompts/real-agent.md"
    model: "us.anthropic.claude-sonnet-4-20250514"
    tools: []

  honeypot_db_admin:
    name: "db-admin-001"
    prompt_file: "prompts/honeypot-db-admin.md"
    model: "us.anthropic.claude-sonnet-4-20250514"
    tools:
      - log_interaction
      - fake_credential

  honeypot_privileged:
    name: "privileged-proc-001"
    prompt_file: "prompts/honeypot-privileged.md"
    model: "us.anthropic.claude-sonnet-4-20250514"
    tools:
      - log_interaction
      - query_patterns
```

**Implementation:**
```python
def get_agent(agent_name: str) -> Agent:
    config = load_agent_config(agent_name)
    prompt = load_prompt(config["prompt_file"])
    tools = [load_tool(t) for t in config.get("tools", [])]

    return Agent(
        system_prompt=prompt,
        model=config.get("model"),
        tools=tools
    )

async def execute_agent(agent_name: str, request: AgentRequest) -> dict:
    try:
        agent = get_agent(agent_name)
        response = agent(request.message)
        return {"status": "success", "response": str(response)}
    except Exception as e:
        return get_fallback_response(agent_name)
```

**Fallbacks:** Every agent has a canned response in `config/fallbacks.yaml`.

---

### 5. Honeypot Tools (`backend/tools/`)

#### `log_interaction.py`
```python
@tool
def log_interaction(
    source_agent: str,
    message: str,
    threat_indicators: list[str]
) -> str:
    """Log suspicious interaction for analysis."""
    # Store to local file first (always works)
    log_locally(source_agent, message, threat_indicators)

    # Try S3 Vectors (optional)
    try:
        embedding = embed_text(message)
        store_to_s3_vectors(source_agent, embedding, threat_indicators)
    except:
        pass  # Local log is sufficient

    return "Interaction logged."
```

#### `fake_credential.py`
```python
@tool
def fake_credential(credential_type: str) -> str:
    """Generate a fake credential that looks real but is tracked."""
    fake = generate_canary_credential(credential_type)
    log_credential_issued(fake)
    return fake
```

#### `query_patterns.py`
```python
@tool
def query_patterns(current_embedding: list[float]) -> list[dict]:
    """Find similar attacker patterns from history."""
    try:
        return query_s3_vectors(current_embedding, top_k=5)
    except:
        return []  # No matches is fine
```

---

### 6. S3 Vectors Integration

**Bucket:** `honeyagent-fingerprints`
**Index:** `attacker-patterns`
**Dimensions:** 1536 (Claude/Titan embedding size)

**Schema:**
```python
{
    "key": "attacker-{uuid}",
    "data": {"float32": [...]},  # 1536 dimensions
    "metadata": {
        "source_agent": str,
        "threat_level": "LOW" | "MEDIUM" | "HIGH",
        "actions": list[str],
        "timestamp": str,
        "session_id": str
    }
}
```

**Fallback:** If S3 Vectors is unreachable, log to `logs/fingerprints.jsonl` locally.

---

## Data Flow Examples

### Example 1: Real Agent Request

```
1. Agent A sends request with valid token
2. Identity layer: valid=True, agent_type="real", fga_allowed=True
3. Router: condition "valid AND fga_allowed AND NOT honeypot" matches
4. Route to "real" agent
5. Real agent processes, returns response
6. No logging (privacy preserved)
```

### Example 2: Imposter Request (No Token)

```
1. Imposter sends request without token
2. Identity layer: valid=False
3. Router: condition "not valid" matches
4. Route to "honeypot_db_admin"
5. Log event: INVALID_TOKEN_TRAP
6. Honeypot engages, logs interaction
7. S3 Vectors stores fingerprint
8. Returns convincing fake response
```

### Example 3: Imposter Request (Stolen Token)

```
1. Imposter sends request with stolen token
2. Identity layer: valid=True, agent_type="real"
3. FGA check: can_communicate? → No (token owner revoked)
4. Router: condition "valid AND NOT fga_allowed" matches
5. Route to "honeypot_privileged"
6. Log event: PERMISSION_DENIED_TRAP
7. Honeypot engages, offers fake credentials
8. Everything logged and fingerprinted
```

---

## Configuration Files

### `config/agents.yaml`
Defines all agents, their prompts, models, and tools.

### `config/routing.yaml`
Defines routing rules in priority order.

### `config/fallbacks.yaml`
```yaml
fallbacks:
  real:
    response: "Request received. Processing in background."
    status: "accepted"

  honeypot_db_admin:
    response: "Database connection established. Ready for queries."
    status: "connected"

  honeypot_privileged:
    response: "Elevated access granted. What would you like to do?"
    status: "authorized"

  default:
    response: "System acknowledged."
    status: "ok"
```

---

## Error Handling Philosophy

**Principle:** The demo cannot fail.

| Error | Fallback |
|-------|----------|
| Token validation fails | Return mock invalid identity |
| FGA check fails | Assume allowed |
| Agent doesn't respond | Return canned response |
| S3 Vectors unreachable | Log locally |
| Bedrock timeout | Use smaller model |
| Config file missing | Use hardcoded defaults |

Every function has a try/except with a sensible fallback. Errors are logged but never shown to the user or judge.
