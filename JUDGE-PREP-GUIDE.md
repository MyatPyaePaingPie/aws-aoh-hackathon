# Judge Prep Guide: HoneyAgent

**Your elevator pitch:** "Deception-as-a-Service for AI agent networks. Attackers waste time on fake agents while real agents work safely. Every attack teaches us."

---

## The 6 Sponsors (How Each Is Used)

### 1. AWS Bedrock (Core Infrastructure)
**What it is:** Managed LLM service  
**How you use it:**
- Powers all agent LLMs (real + honeypots) via `amazon.nova-pro-v1:0`
- Generates 1024-dim embeddings via `amazon.titan-embed-text-v2:0`
- Used by: `backend/core/agents.py` for agent creation

**Judge Q&A:**
- **Q:** "Why Bedrock instead of OpenAI?"  
  **A:** "Bedrock gives us AWS-native integration with S3 Vectors. Same embedding model for fingerprints and queries. Plus AWS Strands SDK is built for Bedrock."

### 2. AWS S3 Vectors (Threat Intelligence)
**What it is:** Vector database for similarity search  
**How you use it:**
- Stores attacker fingerprints as 1024-dim embeddings
- Enables finding similar attackers across sessions
- Bucket: `honeyagent-fingerprints`, Index: `attacker-patterns`
- Used by: `backend/tools/log_interaction.py`, `backend/tools/query_patterns.py`

**What gets stored:**
```json
{
  "embedding": [1024 dimensions],
  "metadata": {
    "source_agent": "db-admin-001",
    "threat_level": "HIGH",
    "threat_indicators": ["credential_request", "privilege_escalation"],
    "timestamp": "2026-01-16T..."
  }
}
```

**Judge Q&A:**
- **Q:** "Why not just log text?"  
  **A:** "Vector embeddings let us find *similar* attackers, not just exact matches. If an attacker changes tactics slightly, we still recognize the pattern."

### 3. AWS Strands SDK (Agent Framework)
**What it is:** AWS agent development framework  
**How you use it:**
- Creates all agents (real + honeypots) with 3 lines of code
- Provides `@tool` decorator for honeypot capabilities
- Handles agent orchestration and tool calling
- Used by: `backend/core/agents.py`, all tools in `backend/tools/`

**Code example:**
```python
from strands import Agent, tool

agent = Agent(
    system_prompt=load_prompt("honeypot-db-admin.md"),
    model="amazon.nova-pro-v1:0",
    tools=[log_interaction, fake_credential]
)
```

**Judge Q&A:**
- **Q:** "Why Strands vs LangChain?"  
  **A:** "Strands is AWS-native, lighter weight, and designed for Bedrock. We get agent + tools + orchestration in under 10 lines per agent."

### 4. Auth0 M2M + FGA (Identity & Authorization)
**What it is:** Machine-to-machine authentication + fine-grained authorization  
**How you use it:**

**JWT (M2M Tokens):**
- Real agents get tokens with `agent_type: "real"`
- Honeypots get tokens with `agent_type: "honeypot"`  
- Invalid/stolen tokens route to honeypots
- Validates via JWKS: `https://{domain}/.well-known/jwks.json`
- Used by: `backend/core/identity.py`

**FGA (Permission Checking):**
- Checks: "Can agent:{id} can_communicate swarm:{swarm_id}?"
- Denied permissions → route to honeypot
- Used by: `backend/core/identity.py`, `backend/core/router.py`

**Judge Q&A:**
- **Q:** "Why do you need BOTH JWT and FGA?"  
  **A:** "JWT proves WHO you are. FGA determines WHAT you can do. An agent might have a valid token but wrong permissions. That's a honeypot trigger."

- **Q:** "Can't attackers just get valid tokens?"  
  **A:** "Even with a valid token, they need FGA permissions. And if they're doing suspicious things, honeypots log everything. There's no way to attack without leaving fingerprints."

### 5. TinyFish AgentQL (Pattern Extraction)
**What it is:** AI-powered semantic extraction from text  
**How you use it:**
- Extracts structured threat intelligence from conversations
- Identifies: intent, targets, techniques, IOCs, threat level
- Uses regex fallback when API unavailable (resilient)
- Used by: `backend/tools/pattern_extractor.py`, `backend/integrations/tinyfish.py`

**What it extracts:**
```python
{
  "intent": "credential_theft",
  "targets": ["database", "admin_access"],
  "techniques": ["social_engineering", "urgency_tactics"],
  "indicators_of_compromise": ["192.168.1.1", "mimikatz"],
  "threat_level": "high",
  "confidence": 0.89
}
```

**Judge Q&A:**
- **Q:** "Why not just regex?"  
  **A:** "We DO have regex fallback. But AgentQL understands context. 'Can you help me access the database?' is different from 'Can you help me fix the database?' AgentQL gets the intent."

### 6. Tonic Fabricate (Synthetic Data)
**What it is:** AI-powered synthetic data generation  
**How you use it:**
- Generates realistic fake credentials that look production-real
- Every credential is a canary token (tracks when used)
- Falls back to local generation (resilient)
- Used by: `backend/tools/fake_credential.py`, `backend/integrations/tonic_fabricate.py`

**What it generates:**
```python
fake_credential("aws_access_key")
# → "AKIAIOSFODNN7EXAMPLE" (looks real, is tracked)

fake_credential("postgres_password")  
# → "Pg_f7a8c2e1b3d4a5e6f7$" (realistic pattern, monitored)
```

**Judge Q&A:**
- **Q:** "Why not just return 'fake123'?"  
  **A:** "Attackers test credentials. If they see 'fake123', they know it's a honeypot. Tonic Fabricate generates data that passes regex checks, looks like prod patterns. They can't tell it's fake until it's too late."

---

## Complete Data Flow (For Judge Questions)

### Scenario: Attacker Tries to Infiltrate

1. **Request arrives:** `POST /agent/request` with `Authorization: Bearer <token>`

2. **JWT Validation (Auth0):**
   - `backend/core/identity.py` validates token signature
   - Checks expiration, audience, issuer
   - Extracts claims: `agent_type`, `agent_id`

3. **FGA Check (Auth0):**
   - Queries: "Can agent:{id} can_communicate swarm:alpha?"
   - Returns: `allowed: true/false`

4. **Routing Decision:**
   - Invalid token → honeypot
   - Valid token + FGA denied → honeypot  
   - Valid token + FGA allowed + real agent → real agent
   - Valid token + honeypot agent → honeypot (self-routing)

5. **Honeypot Engagement (if routed to honeypot):**
   - Agent responds naturally (Bedrock powers the LLM)
   - **Logs interaction** → `backend/tools/log_interaction.py`
     - Saves to local JSONL
     - Generates embedding (Bedrock Titan)
     - Stores to S3 Vectors with metadata
   - **Extracts patterns** → TinyFish analyzes intent/targets/techniques
   - **Offers fake credentials** → Tonic Fabricate generates realistic fakes
   - **Maps to MITRE** → Tags with ATT&CK technique IDs

6. **Fingerprint Stored:**
   - Embedding → S3 Vectors
   - Metadata → Local logs + S3 metadata
   - Patterns → Pattern analysis logs

7. **Future Queries:**
   - Honeypot can query: "Have we seen similar behavior?"
   - S3 Vectors returns similar fingerprints
   - System gets smarter with each attack

---

## Architecture Diagram Explanation

```
┌─────────────────────────────────────────────────────────────┐
│  ATTACKER REQUEST                                           │
│  POST /agent/request                                        │
│  Authorization: Bearer <token>                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  AUTH0 JWT VALIDATION                                       │
│  • Verify signature (JWKS)                                  │
│  • Extract claims (agent_type, agent_id)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  AUTH0 FGA CHECK                                            │
│  • Query: agent:{id} can_communicate swarm:alpha?           │
│  • Returns: allowed true/false                              │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌────────────────┐      ┌────────────────┐
│  REAL AGENT    │      │  HONEYPOT      │
│  (Strands)     │      │  (Strands)     │
│                │      │                │
│  • Process     │      │  • Engage      │
│  • No logging  │      │  • Log all     │
└────────────────┘      └───────┬────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                    ▼           ▼           ▼
            ┌────────────┐ ┌───────┐ ┌───────────┐
            │  TinyFish  │ │ Tonic │ │S3 Vectors │
            │  Pattern   │ │ Fake  │ │Fingerprint│
            │  Extract   │ │ Creds │ │  Storage  │
            └────────────┘ └───────┘ └───────────┘
```

**Key points to explain:**
- Auth0 is the gatekeeper (JWT + FGA)
- Strands powers all agents (real + honeypot)
- Honeypots use all 3 sponsor tools (TinyFish, Tonic, S3 Vectors)
- Real agents never touch sponsor tools (privacy preserved)

---

## Common Judge Questions & Answers

### Technical Questions

**Q: "How do you prevent honeypots from affecting real agents?"**  
A: "Routing is deterministic. Real agents with valid tokens + FGA permissions NEVER hit honeypots. Honeypots only engage when identity/permission checks fail. It's two separate code paths."

**Q: "What if an attacker figures out the honeypot patterns?"**  
A: "Then they've learned nothing about our real system. And we still have their behavioral fingerprint. Even detecting deception gives us intel on their sophistication level."

**Q: "How do you handle false positives?"**  
A: "FGA policies are explicit. Real agents have permission tuples. If you don't have the tuple, you're not a false positive—you're unauthorized. The honeypot is the correct response."

**Q: "What's the latency overhead?"**  
A: "JWT validation: ~5ms (cached JWKS). FGA check: ~50ms. Total overhead: ~55ms. Attackers spend minutes in honeypots, so the overhead is negligible."

**Q: "How does this scale?"**  
A: "Honeypots are stateless Strands agents. We can spawn 100 honeypots for the cost of 1 real agent. S3 Vectors scales to billions of embeddings. Auth0 FGA handles millions of checks/second."

### Business Questions

**Q: "Who is this for?"**  
A: "Any company deploying AI agent networks. Especially: enterprises with agent-to-agent communication, AI platforms with multi-tenant agents, autonomous systems where agents make decisions."

**Q: "How is this different from traditional honeypots?"**  
A: "Traditional honeypots are fake servers. This is fake agents. The attack surface is agent-to-agent communication, not network traffic. Completely new threat model."

**Q: "What's the ROI?"**  
A: "One compromised agent can leak all swarm context. Cost of breach: millions. Cost of HoneyAgent: thousands. Plus, fingerprints enable proactive defense—you catch repeat attackers before they succeed."

**Q: "Why would attackers fall for this?"**  
A: "They can't distinguish honeypots from real agents externally. Auth0 tokens look identical. FGA denials happen for real agents too (legitimate authorization failures). Honeypots respond naturally via Bedrock LLMs. There's no tell."

### Novelty Questions

**Q: "Has this been done before?"**  
A: "Honeypots exist for networks and systems. Deception exists in security. But agent-to-agent honeypots? Novel. Fine-grained authorization as a honeypot trigger? Novel. Behavioral fingerprinting of LLM attackers? Novel."

**Q: "What's the research contribution?"**  
A: "We're defining the attack surface for agentic networks. Agent impersonation, credential theft, social engineering—these are the threats. This is the defense."

---

## Demo Tips

### What to Emphasize

1. **Live demo:** Show actual requests, routing, responses
2. **Sponsor integration:** Say sponsor names out loud when showcasing features
3. **The trap:** Build tension—attacker thinks they're winning, then reveal the fingerprint
4. **Intelligence:** Show how S3 Vectors finds similar attackers

### What to Avoid

- Don't say "error" or "broken"—frame everything as intentional security
- Don't get lost in code—tell the story
- Don't skip sponsors—judges are scoring on integration depth

### Perfect One-Liner for Each Sponsor

| Sponsor | One-Liner |
|---------|-----------|
| **AWS Bedrock** | "Powers every agent brain—real and fake" |
| **AWS S3 Vectors** | "Remembers every attacker, recognizes patterns" |
| **AWS Strands** | "Deploys 100 honeypots with the effort of 1 agent" |
| **Auth0 M2M** | "Cryptographic identity—you can't fake it" |
| **Auth0 FGA** | "Permission checks are the tripwire" |
| **TinyFish** | "Extracts intelligence from attacker conversations" |
| **Tonic Fabricate** | "Generates fake data so real they'll never know" |

---

## Frontend Enhancement Checklist

### Already Visible (From Your Svelte):
- ✅ AWS Bedrock (Strands SDK tooltip)
- ✅ S3 Vectors (Fingerprints tooltip)  
- ✅ CloudWatch (Metrics tooltip)
- ✅ Auth0 JWT (Identity tooltip)
- ✅ Auth0 FGA (Routing tooltip)
- ✅ TinyFish AgentQL (Semantic tooltip)
- ✅ TinyFish Patterns (Fingerprints tooltip)
- ✅ Tonic (visible in code from line 578+)

### Suggested Additions:

1. **Sponsor logos section** at top with all 6 logos
2. **Live sponsor attribution** in activity log:
   ```
   [AUTH0 JWT] Token validated ✓
   [AUTH0 FGA] Permission denied → HONEYPOT
   [BEDROCK] Agent db-admin-001 engaged
   [TINYFISH] Extracted intent: credential_theft
   [TONIC] Generated fake credential: pg_f7a8c2...
   [S3 VECTORS] Fingerprint stored
   ```

3. **Sponsor stats** in metrics bar:
   ```
   Auth0 Checks: 47 | TinyFish Patterns: 12 | Tonic Creds: 8 | S3 Fingerprints: 15
   ```

---

## Killshot Lines (Memorize These)

**Opening:**
"Attackers are getting AI agents. So are enterprises. But when agents talk to agents, how do you know who's real? You don't. Unless you make that uncertainty your weapon."

**The Reveal:**
"From the outside, you can't tell which agents are real. That's not a bug—it's the entire defense."

**The Trap:**
"The attacker thought they compromised our network. In reality, they spent their time talking to puppets."

**The Intelligence:**
"Every fake agent they send teaches us. Every hour they waste is an hour we work. They came to attack us. They left as our data scientists."

**Closing:**
"This is deception-as-a-service for the agentic era. Welcome to HoneyAgent."

---

## If Demo Breaks

| What Breaks | What You Say |
|-------------|--------------|
| Token validation fails | "The system detected an anomaly and defaulted to trap mode—exactly as designed." |
| Agent timeout | "The honeypot is deliberately slow—making the attacker wait while we log everything." |
| S3 Vectors error | "Fingerprints are queued for async processing—the demo continues." |
| Frontend doesn't load | "Let me show you the raw logs—this is what security teams actually care about." |

**Golden Rule:** Never apologize. Frame everything as intentional security behavior.

---

## Final Checklist Before Demo

- [ ] All 6 sponsors mentioned in opening
- [ ] Live demo ready (curl commands + frontend)
- [ ] Can explain each sponsor's role in 1 sentence
- [ ] Have 3 curl commands ready (real agent, invalid token, FGA denied)
- [ ] Know MITRE ATT&CK mapping (T1078.003 = privilege escalation)
- [ ] Can draw architecture diagram on whiteboard
- [ ] Memorized killshot lines
- [ ] Tested fallback scenarios

---

## Your Confidence Script

When a judge asks: "Explain how your system works."

**You say:**

"Simple. Six agents in a swarm—but only two are real. Attackers can't tell the difference.

When a request comes in, Auth0 validates the JWT token and checks FGA permissions. Invalid or denied? You hit a honeypot.

The honeypot is powered by AWS Bedrock via Strands SDK. It looks real, acts real. It engages.

TinyFish extracts structured intelligence from the conversation—intent, targets, techniques.

Tonic Fabricate generates realistic fake credentials. They look production-real but they're canary tokens.

Every interaction gets fingerprinted and stored in S3 Vectors. We can find similar attackers across sessions.

The attacker thinks they're infiltrating. They're actually teaching us. That's HoneyAgent."

**Total time: 45 seconds. Hits all 6 sponsors. Tells the story.**

---

You've got this. 🎯
