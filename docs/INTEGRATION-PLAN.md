# Integration Plan: Dual-Dev Parallel Development

---

## Overview

Two developers working in parallel, merging at defined integration points.

| Track | Owner | Scope |
|-------|-------|-------|
| **Agents Track** | Aria | Strands agents, prompts, tools, S3 Vectors |
| **Identity Track** | Partner | Auth0 tokens, FGA, routing logic |

**Golden Rule:** Never touch the other person's files without syncing first.

---

## File Ownership

### Aria (Agents Track)

```
OWNS:
backend/core/agents.py          # Agent factory
backend/tools/log_interaction.py
backend/tools/fake_credential.py
backend/tools/query_patterns.py
prompts/real-agent.md
prompts/honeypot-db-admin.md
prompts/honeypot-privileged.md
config/agents.yaml
tests/unit/test_agents.py
tests/unit/test_tools.py

READS (don't edit):
backend/core/identity.py        # Partner's code
backend/core/router.py          # Partner's code
config/routing.yaml             # Partner's config
```

### Partner (Identity Track)

```
OWNS:
backend/core/identity.py        # Token validation
backend/core/router.py          # Routing logic
config/routing.yaml             # Routing rules
config/auth0.yaml               # Auth0 config
tests/unit/test_identity.py
tests/unit/test_router.py

READS (don't edit):
backend/core/agents.py          # Aria's code
config/agents.yaml              # Aria's config
```

### Shared (Both Edit)

```
backend/api/main.py             # Gateway (coordinate edits)
config/fallbacks.yaml           # Fallback responses
tests/integration/              # Integration tests
tests/e2e/                      # End-to-end tests
frontend/                       # UI (after MVP)
```

---

## Timeline

### Hour 0-1: Setup (Parallel)

**Aria:**
- [ ] Set up Python environment
- [ ] Install Strands SDK: `pip install strands-agents strands-agents-tools`
- [ ] Create `prompts/real-agent.md` (basic)
- [ ] Create `prompts/honeypot-db-admin.md` (basic)
- [ ] Test agent spawns locally

**Partner:**
- [ ] Set up Auth0 tenant (if not done)
- [ ] Create 2 M2M apps: `honeyagent-real`, `honeyagent-honeypot`
- [ ] Add custom claims via Auth0 Action
- [ ] Test token generation with curl
- [ ] Set up FGA store and model

**Sync Point:** Both can generate tokens and spawn agents independently.

---

### Hour 1-2: Core Logic (Parallel)

**Aria:**
- [ ] Implement `backend/core/agents.py`:
  - `load_agent_config()` - read from `config/agents.yaml`
  - `load_prompt()` - read from `prompts/`
  - `get_agent()` - spawn Strands agent
  - `execute_agent()` - run agent with request
- [ ] Implement `backend/tools/log_interaction.py`
- [ ] Write `tests/unit/test_agents.py`

**Partner:**
- [ ] Implement `backend/core/identity.py`:
  - `validate_token()` - JWT validation against Auth0 JWKS
  - `extract_claims()` - get custom claims
  - `check_fga()` - FGA permission check
- [ ] Implement `backend/core/router.py`:
  - `load_routing_rules()` - read from `config/routing.yaml`
  - `evaluate_condition()` - match rule conditions
  - `route_request()` - return agent name
- [ ] Write `tests/unit/test_identity.py`
- [ ] Write `tests/unit/test_router.py`

**Sync Point:** Both tracks have passing unit tests.

---

### Hour 2-3: Integration (Together)

**Both:**
- [ ] Wire `router.route_request()` → `agents.execute_agent()`
- [ ] Implement `backend/api/main.py`:
  ```python
  @app.post("/agent/request")
  async def agent_request(request, authorization):
      identity = await validate_token(authorization)
      agent_name = route_request(identity, request)
      response = await execute_agent(agent_name, request)
      return response
  ```
- [ ] Write `tests/integration/test_flow.py`
- [ ] Test full flow: token → identity → routing → agent → response

**Sync Point:** `POST /agent/request` works end-to-end.

---

### Hour 3-4: S3 Vectors + Polish (Parallel)

**Aria:**
- [ ] Implement S3 Vectors integration in `log_interaction.py`
- [ ] Implement `backend/tools/query_patterns.py`
- [ ] Add embedding generation (Bedrock Titan or Claude)
- [ ] Write `tests/unit/test_s3_vectors.py`

**Partner:**
- [ ] Add FGA Logging API integration
- [ ] Polish routing rules in `config/routing.yaml`
- [ ] Add edge case handling in `identity.py`
- [ ] Write `tests/integration/test_fga_routing.py`

**Sync Point:** Honeypots log to S3 Vectors, FGA denials are captured.

---

### Hour 4-5: Demo Polish (Together)

**Both:**
- [ ] Write `tests/e2e/test_demo_flow.py` (the 9 beats)
- [ ] Verify all fallbacks work
- [ ] Run full demo locally
- [ ] Fix any integration issues

**Sync Point:** Demo runs start to finish without errors.

---

### Hour 5+: Frontend (Optional)

**Both:**
- [ ] Set up Astro + Svelte frontend
- [ ] Build dashboard showing:
  - Agent network visualization
  - Real-time interaction log
  - Attacker fingerprint display
- [ ] Connect to backend API

---

## Integration Contracts

### Contract 1: Identity → Router

**From:** `backend/core/identity.py`
**To:** `backend/core/router.py`

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

### Contract 2: Router → Agents

**From:** `backend/core/router.py`
**To:** `backend/core/agents.py`

```python
# Router returns:
agent_name: str  # Key from config/agents.yaml: "real", "honeypot_db_admin", etc.

# Agents expects:
def execute_agent(agent_name: str, request: AgentRequest) -> dict
```

### Contract 3: API Request/Response

**Input:**
```python
class AgentRequest(BaseModel):
    message: str
    context: Optional[dict] = None
```

**Output:**
```python
{
    "status": "success" | "accepted" | "error",
    "response": str,
    "metadata": Optional[dict]
}
```

---

## Testing Strategy

### Unit Tests (Run Independently)

| File | Owner | What it Tests |
|------|-------|---------------|
| `tests/unit/test_agents.py` | Aria | Agent spawning, prompt loading |
| `tests/unit/test_tools.py` | Aria | log_interaction, fake_credential |
| `tests/unit/test_identity.py` | Partner | Token validation, claim extraction |
| `tests/unit/test_router.py` | Partner | Routing rule evaluation |

**Run your tests:**
```bash
# Aria
pytest tests/unit/test_agents.py tests/unit/test_tools.py -v

# Partner
pytest tests/unit/test_identity.py tests/unit/test_router.py -v
```

### Integration Tests (Run Together)

| File | What it Tests |
|------|---------------|
| `tests/integration/test_flow.py` | Token → Identity → Router → Agent |
| `tests/integration/test_fga_routing.py` | FGA denials route to honeypots |
| `tests/integration/test_s3_vectors.py` | Honeypot logs stored correctly |

```bash
pytest tests/integration/ -v
```

### E2E Tests (Full Demo)

| File | What it Tests |
|------|---------------|
| `tests/e2e/test_demo_flow.py` | All 9 beats of the demo |

```bash
pytest tests/e2e/ -v
```

---

## Communication Protocol

### During Development

1. **Before starting work:** `git pull`
2. **Every 15 minutes:** Commit and push your track
3. **Before editing shared files:** Message partner
4. **When blocked:** Immediately tell partner

### Sync Points (Mandatory)

| Time | Action |
|------|--------|
| Hour 1 | Both verify tokens work, agents spawn |
| Hour 2 | Run each other's unit tests |
| Hour 3 | Wire together, run integration tests |
| Hour 4 | Run full e2e tests |
| Hour 5 | Demo rehearsal |

### Conflict Resolution

If you both need to edit the same file:
1. One person edits, commits, pushes
2. Other person pulls, then edits
3. Never both edit simultaneously

---

## Fallback Strategy by Track

### Aria (Agents Track)

| Component | Fallback |
|-----------|----------|
| Strands SDK fails | Return canned responses from `config/fallbacks.yaml` |
| Prompt file missing | Use hardcoded minimal prompt |
| S3 Vectors unreachable | Log to `logs/fingerprints.jsonl` |
| Bedrock timeout | Use smaller model or mock response |

### Partner (Identity Track)

| Component | Fallback |
|-----------|----------|
| Auth0 JWKS fetch fails | Use cached JWKS (load on startup) |
| Token decode fails | Return `Identity(valid=False)` |
| FGA check fails | Assume `fga_allowed=True` (fail open) |
| FGA API timeout | Skip check, log warning |

---

## Definition of Done

### MVP (Hour 3)

- [ ] `POST /agent/request` with valid token → real agent responds
- [ ] `POST /agent/request` without token → honeypot responds
- [ ] Both paths have fallbacks that work
- [ ] Integration tests pass

### Full Demo (Hour 5)

- [ ] All 9 demo beats work
- [ ] S3 Vectors stores fingerprints
- [ ] FGA denials route correctly
- [ ] E2E tests pass
- [ ] Demo runs 3 times without failure
