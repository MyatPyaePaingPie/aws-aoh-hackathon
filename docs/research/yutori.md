# Yutori API: Deep Dive

## Summary

Yutori provides AI-powered web automation agents. Their platform offers two main APIs:
1. **Browsing API** - Execute browser-based workflows via natural language
2. **Scouting API** - Deploy always-on monitors that track web changes

For HoneyAgent, we can use Yutori for:
- **Simulating attacker probes** (Browsing API) - Automated agents that probe honeypot endpoints
- **Threat monitoring** (Scouting API) - Always-on scouts watching honeypot URLs for suspicious activity

## Mental Model

Yutori = "browser-as-a-service with AI steering"

Think of it as:
- You give natural language instructions
- Yutori spawns a cloud browser
- An AI agent navigates, clicks, extracts data
- Results come back via API or webhook

## Key Concepts

### Browsing API
- **Purpose**: Execute one-off browser tasks
- **Input**: Natural language prompt describing what to do
- **Execution**: Cloud browser with AI navigation
- **Output**: Task result (text, extracted data, screenshots)

### Scouting API
- **Purpose**: Continuous web monitoring
- **Input**: What to watch for + schedule
- **Execution**: Recurring checks with change detection
- **Output**: Notifications via webhook when conditions match

### n1 Model
- Yutori's proprietary "pixels-to-actions" LLM
- Takes: screenshot + task description + action history
- Outputs: next action to take in browser
- Model ID: `n1-preview-2025-11`

## API Details

### Authentication
```
Authorization: Bearer <YUTORI_API_KEY>
```

### Base URL
```
https://api.yutori.com/v1
```

### Endpoints (inferred from research)

#### Chat Completions (Browser Control)
```http
POST /v1/chat/completions
```

Request:
```json
{
  "model": "n1-preview-2025-11",
  "messages": [
    {
      "role": "user",
      "content": "Navigate to example.com and extract the main heading"
    }
  ]
}
```

#### Scouting Tasks (Monitoring)
```http
POST /v1/scouting/tasks
```

Request:
```json
{
  "query": "Monitor for new security alerts",
  "start_timestamp": "2026-01-16T00:00:00Z",
  "output_interval": 86400,
  "webhook_url": "https://our-endpoint.com/yutori-callback"
}
```

## Current State

- **Access**: Waitlist-based (yutori.com)
- **Founded**: By ex-Meta AI researchers
- **Funding**: $15M seed (2025)
- **Limitations**: Cannot access authenticated pages yet

## HoneyAgent Integration Use Cases

### 1. Attacker Simulation (Browsing API)
Spawn browser agents that probe our honeypot endpoints to generate realistic attack traffic for demos.

```python
# Simulate credential theft attempt
await yutori.browse(
    "Navigate to our API endpoint and request admin credentials"
)
```

### 2. Threat Scout (Scouting API)
Deploy always-on monitors watching honeypot web interfaces for suspicious patterns.

```python
# Monitor honeypot for unauthorized probes
await yutori.scout(
    query="Alert if someone visits /admin or /debug endpoints",
    webhook_url="https://api.honeyagent.io/threat-detected"
)
```

### 3. Pattern Extraction
Use browser automation to visit attacker-controlled URLs (from honeypot logs) and extract threat intel.

## Implementation Strategy

### Fallback-First Design
Per project rules, every Yutori call must have fallbacks:

```python
async def scout_honeypot(endpoint: str) -> dict:
    try:
        result = await yutori_client.scout(endpoint)
        return result
    except Exception:
        return get_fallback("yutori")  # From config/fallbacks.yaml
```

### Fallback Response
From `config/fallbacks.yaml`:
```yaml
yutori:
  status: "scouting"
  response: "Scout deployed. Monitoring honeypot endpoints for threat activity."
  threat_detected: false
  endpoints_monitored: 3
```

## Open Questions

1. **Rate limits**: Unknown - need to test with real API key
2. **Webhook security**: How to authenticate incoming notifications?
3. **Cost model**: Per-task or subscription?

## Sources

- [Yutori API Landing](https://yutori.com/api) - Official API page
- [Introducing Scouts](https://blog.yutori.com/p/scouts) - Product announcement
- [DBOS Case Study](https://www.dbos.dev/case-studies/yutori-large-scale-durable-agentic-ai) - Architecture details
- [Product Hunt](https://www.producthunt.com/products/scouts-by-yutori) - User reviews

## Implications for HoneyAgent

1. **Demo enhancement**: Real browser-based attack simulations add credibility
2. **Continuous monitoring**: Scouts can watch honeypot endpoints 24/7
3. **Fallback ready**: Demo works even without Yutori API access
4. **Integration pattern**: Matches existing tool structure (try/except/fallback)
