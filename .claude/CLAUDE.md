# HoneyAgent

**Deception-as-a-Service for Agent Networks** — Honeypot agents that trap, study, and neutralize attackers.

---

## Project Context

**Tier**: 1 (Hackathon) — 5.5 hour build window, demo must not fail
**Stack**: Python 3.11+, FastAPI, Strands SDK, Auth0 (M2M + FGA), AWS (S3 Vectors, Bedrock)
**Domain**: Multi-agent security system with parallel development tracks

**Critical constraint**: Every component has a fallback. The demo cannot crash.

---

## Development Tracks

| Track | Owner | Files |
|-------|-------|-------|
| **Agents** | Aria | `backend/core/agents.py`, `prompts/`, `backend/tools/`, `config/agents.yaml`, `tests/unit/test_agents.py`, `tests/unit/test_tools.py` |
| **Identity** | Partner | `backend/core/identity.py`, `backend/core/router.py`, `config/routing.yaml`, `tests/unit/test_identity.py`, `tests/unit/test_router.py` |
| **Shared** | Both | `backend/api/`, `config/fallbacks.yaml`, `tests/integration/`, `tests/e2e/`, `frontend/` |

**Rule**: Never edit another track's files without syncing first.

---

## Coding Rules

### Fallback-First Design
- Every function that calls an external service MUST have a try/except with fallback
- Fallbacks return plausible responses, NEVER error messages
- Check `config/fallbacks.yaml` for predefined responses
- API endpoints return 2xx even on internal failures

### Config-Driven Architecture
- Agent definitions: `config/agents.yaml`
- Routing rules: `config/routing.yaml`
- Fallback responses: `config/fallbacks.yaml`
- Prompts: `prompts/*.md`
- Code reads config, doesn't hardcode behavior

### Integration Contracts
```python
# Identity → Router
@dataclass
class Identity:
    valid: bool
    agent_id: Optional[str]
    agent_type: Optional[str]  # "real" | "honeypot" | None
    is_honeypot: bool
    fga_allowed: bool

# Router → Agents
agent_name: str  # Key from config/agents.yaml

# API Response
{"status": "success" | "accepted", "response": str}
```

### Testing
- Unit tests: Run independently per track
- Integration tests: Run after sync points
- E2E tests: Run before every demo rehearsal
- All tests use mocks from `tests/conftest.py`

---

## Commands

| Command | Purpose |
|---------|---------|
| `/my-tests` | Run tests for your track |
| `/demo-check` | Run e2e tests to verify demo works |
| `/sync` | Pull, run all tests, push |

---

## Key Files

| File | Purpose |
|------|---------|
| `config/fallbacks.yaml` | All fallback responses (check before implementing) |
| `config/agents.yaml` | Agent definitions and tool assignments |
| `config/routing.yaml` | Identity → agent routing rules |
| `docs/DEMO-SCRIPT.md` | The 9-beat demo flow |
| `docs/ARCHITECTURE.md` | System design and data flow |

---

## Default Behaviors

### When Implementing Features
1. Check if fallback exists in `config/fallbacks.yaml`
2. Wrap external calls in try/except
3. Return fallback response on any error
4. Log errors locally but don't expose them

### When Debugging
1. Check if the failure mode has a fallback
2. If fallback works, the demo is safe — debug later
3. If fallback fails, fix fallback first

### Before Completing Any Task
1. Run your track's tests: `pytest tests/unit/test_{your_track}.py -v`
2. Check no error strings in responses
3. Verify fallback path works

---

## KERNEL Reference

**Banks** (auto-applied):
- `PLANNING-BANK.md` — Interface-first, mental simulation
- `DEBUGGING-BANK.md` — Fallback-first for hackathon
- `REVIEW-BANK.md` — Check fallbacks, contracts, tests

**Explicit commands**:
- `/build` — Full pipeline
- `/ship` — Commit, push, PR
- `/validate` — Types + lint + tests
