# HoneyAgent

**Deception-as-a-Service for Agent Networks**

Deploy fake agents that look real but exist only to trap, study, and neutralize bad actors. Attackers waste resources on decoys while real agents work uninterrupted.

---

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Fill in Auth0 + AWS creds
pytest tests/         # Verify everything works
uvicorn api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## Architecture

```
Request → FastAPI → Token Validation → Routing Decision → Agent Response
                         ↓                    ↓
                    Auth0 M2M            Real Agent OR Honeypot
                         ↓                    ↓
                    FGA Check            S3 Vectors (if honeypot)
```

**Core principle:** Invalid/suspicious tokens get routed to honeypots that look like high-value targets. Everything is logged. Attackers become data.

---

## Project Structure

```
aws-aoh-hackathon/
├── backend/
│   ├── api/              # FastAPI endpoints
│   │   └── main.py       # Entry point
│   ├── core/             # Business logic
│   │   ├── identity.py   # Token validation (Dev 2: Partner)
│   │   ├── router.py     # Routing logic (Dev 2: Partner)
│   │   └── agents.py     # Agent factory (Dev 1: Aria)
│   └── tools/            # Strands tools
│       ├── log_interaction.py
│       └── fake_credential.py
├── config/
│   ├── agents.yaml       # Agent definitions
│   ├── routing.yaml      # Routing rules
│   └── fallbacks.yaml    # Demo fallback responses
├── prompts/
│   ├── real-agent.md
│   ├── honeypot-db-admin.md
│   └── honeypot-privileged.md
├── frontend/
│   └── src/              # Astro + Svelte dashboard
├── tests/
│   ├── unit/             # Per-function tests
│   ├── integration/      # Cross-module tests
│   └── e2e/              # Full flow tests
└── docs/
    ├── VISION.md
    ├── ARCHITECTURE.md
    ├── INTEGRATION-PLAN.md
    ├── DEMO-SCRIPT.md
    └── FRONTEND-VISION.md
```

---

## Development Tracks

| Track | Owner | Files |
|-------|-------|-------|
| **Agents** | Aria | `backend/core/agents.py`, `prompts/`, `backend/tools/`, `config/agents.yaml` |
| **Identity** | Partner | `backend/core/identity.py`, `backend/core/router.py`, `config/routing.yaml` |
| **Shared** | Both | `backend/api/`, `tests/`, `config/fallbacks.yaml` |

**Rule:** Never touch the other person's files without syncing first.

---

## Demo Flow (9 Beats)

1. Show swarm of 6 agents (only 2 are real)
2. Imposter agent enters network
3. Real agents reject (Auth0 FGA)
4. Honeypots engage and play along
5. Imposter "trusts" honeypot
6. Profile generated from interaction
7. S3 Vectors stores attacker fingerprint
8. Dashboard shows threat intelligence
9. **Killshot:** "Every fake agent they send teaches us."

---

## Key Commands

```bash
# Run all tests
pytest tests/ -v

# Run only your track
pytest tests/unit/test_agents.py -v      # Aria
pytest tests/unit/test_identity.py -v    # Partner

# Validate full flow
pytest tests/e2e/test_demo_flow.py -v

# Start dev server
uvicorn backend.api.main:app --reload
```

---

## Environment Variables

```env
# Auth0
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://honeyagent-swarm.api
AUTH0_REAL_CLIENT_ID=xxx
AUTH0_REAL_CLIENT_SECRET=xxx
AUTH0_HONEYPOT_CLIENT_ID=xxx
AUTH0_HONEYPOT_CLIENT_SECRET=xxx
AUTH0_FGA_STORE_ID=xxx
AUTH0_FGA_API_TOKEN=xxx

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
S3_VECTORS_BUCKET=honeyagent-fingerprints
```

---

## Fallback Strategy

**Design principle:** The demo cannot fail.

Every component has a hardcoded fallback:
- Token validation fails → return mock valid identity
- Agent doesn't respond → return canned response
- S3 Vectors unreachable → log locally
- FGA timeout → assume allowed

See `config/fallbacks.yaml` for all fallback definitions.

---

## Sponsors

| Sponsor | Integration |
|---------|-------------|
| AWS Strands SDK | Agent framework |
| Auth0 FGA | Permission honeypots |
| Auth0 M2M | Agent identity tokens |
| S3 Vectors | Attacker fingerprinting |

---

## Docs

- [Vision](docs/VISION.md) - Why we're building this
- [Architecture](docs/ARCHITECTURE.md) - How it works
- [Integration Plan](docs/INTEGRATION-PLAN.md) - Parallel dev strategy
- [Demo Script](docs/DEMO-SCRIPT.md) - 9-beat presentation flow
- [Frontend Vision](docs/FRONTEND-VISION.md) - UI/UX design
