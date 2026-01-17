# Sponsor Integration Plan

**Target: 6 sponsors for Best Overall + individual prizes**

---

## Current Stack (2 sponsors)

### AWS (multiple services)
- **Bedrock** - Agent LLM
- **S3 Vectors** - Attacker fingerprints
- **Status:** Integrated

### Auth0
- **M2M tokens** - Agent identity
- **FGA** - Permission checking
- **Status:** Integrated

---

## Adding: Tonic Fabricate ($1,000)

**What it does:** AI-powered synthetic data generation

**Integration point:** `backend/tools/fake_credential.py`

**Current behavior:**
```python
def fake_credential(credential_type: str) -> str:
    # Returns hardcoded fake credentials
```

**With Tonic Fabricate:**
```python
def fake_credential(credential_type: str) -> str:
    # Use Fabricate API to generate realistic synthetic data
    # - Database credentials with realistic patterns
    # - API keys that look like real service keys
    # - Config files with plausible values
    # - Documents (contracts, invoices, PII)
```

**Why it fits:** Honeypots need realistic-looking fake data to be convincing. Fabricate generates production-quality synthetic data that attackers can't distinguish from real data.

**API endpoint:** `https://api.tonic.ai/fabricate/v1/generate`

**Fallback:** Return hardcoded templates if API fails.

---

## Adding: Yutori ($3,500)

**What it does:** AI agents for web tasks, Scouts for monitoring

**Integration point:** Demo + `backend/tools/threat_scout.py`

**Option A - Attacker Simulation (for demo):**
Use Yutori Browsing API to simulate an attacker probing the swarm
```python
# Yutori agent visits honeypot endpoints
# Shows autonomous threat behavior in demo
```

**Option B - Threat Monitoring (production value):**
Use Yutori Scouts to monitor honeypot web endpoints
```python
@tool
def deploy_scout(honeypot_url: str, watch_for: list[str]) -> str:
    # Create Yutori Scout to monitor honeypot
    # Alert when attacker interacts with honeypot web interface
```

**Why it fits:**
- Demo: Shows autonomous attacker behavior
- Product: Scouts can monitor honeypot bait in real-time

**API endpoints:**
- `https://api.yutori.com/v1/browsing/tasks` (Browsing)
- `https://api.yutori.com/v1/scouting/tasks` (Scouts)

**Fallback:** Skip automated simulation, use manual curl for demo.

---

## Adding: TinyFish ($2,250)

**What it does:** Web automation, AgentQL for structured extraction

**Integration point:** `backend/tools/pattern_extractor.py`

**Use case:** Extract structured threat patterns from attacker sessions

```python
@tool
def extract_attack_pattern(session_log: str) -> dict:
    # Use AgentQL to parse unstructured attack logs
    # Extract: intent, targets, techniques, indicators
    # Returns structured threat intelligence
```

**Why it fits:** Attacker behavior comes in as unstructured text. AgentQL can extract structured patterns for fingerprinting.

**API:** AgentQL REST API or Python SDK

**Fallback:** Use regex-based extraction.

---

## Adding: Retool ($1,000)

**What it does:** Low-code dashboards

**Integration point:** Replace/augment frontend

**Dashboard panels:**
1. **Swarm View** - Network graph of agents (real vs honeypot)
2. **Attack Feed** - Real-time log of trapped interactions
3. **Fingerprint DB** - Query attacker profiles
4. **Threat Metrics** - Graphs of attack patterns over time

**Why it fits:** Judges need to SEE the honeypot working. Retool gives us a polished dashboard fast.

**Fallback:** Use existing terminal output + basic HTML page.

---

## Integration Priority

| Priority | Sponsor | Effort | Prize | ROI |
|----------|---------|--------|-------|-----|
| 1 | Tonic Fabricate | Low | $1,000 | High - drops into existing tool |
| 2 | Retool | Medium | $1,000 | High - visual demo impact |
| 3 | Yutori | Medium | $3,500 | Highest - biggest prize |
| 4 | TinyFish | Medium | $2,250 | High - pattern extraction |

**Total potential:** $7,750 in sponsor prizes + Best Overall

---

## Demo Script Updates

### Beat 7 Enhancement (Tonic Fabricate)

**Current:** "The honeypot offers fake credentials."

**Enhanced:** "The honeypot uses Tonic Fabricate to generate realistic synthetic credentials on the fly. Every credential looks different, follows real patterns, but leads to monitored traps."

### Beat 8 Enhancement (TinyFish)

**Current:** Show fingerprint JSON

**Enhanced:** "TinyFish AgentQL extracts structured threat intelligence from raw attacker sessions. Intent, techniques, targets - all parsed automatically."

### New Beat (Yutori)

**Add after Beat 3:** "Watch - a Yutori Scout is autonomously probing our network, simulating attacker reconnaissance. It doesn't know which agents are real."

### Dashboard (Retool)

**Visual throughout:** Retool dashboard showing real-time attack flow

---

## API Keys Needed

| Sponsor | Env Var | Status |
|---------|---------|--------|
| Tonic Fabricate | `TONIC_API_KEY` | Need |
| Yutori | `YUTORI_API_KEY` | Need |
| TinyFish | `TINYFISH_API_KEY` | Need |
| Retool | (OAuth) | Need |

---

## Files to Create/Modify

### New files:
- `backend/tools/fabricate_credential.py` - Tonic integration
- `backend/tools/threat_scout.py` - Yutori integration
- `backend/tools/pattern_extractor.py` - TinyFish integration
- `frontend/retool/` - Retool dashboard config

### Modify:
- `backend/tools/fake_credential.py` - Use Fabricate
- `config/agents.yaml` - Add new tools to honeypots
- `config/fallbacks.yaml` - Add fallbacks for new tools
- `docs/DEMO-SCRIPT.md` - Add sponsor mentions
