# TinyFish/AgentQL: Deep Dive

## Summary

AgentQL is a REST API by TinyFish that extracts structured data from web pages and HTML using natural language queries or a custom query language. For HoneyAgent, we use the `query-data` endpoint with raw HTML input to extract attacker patterns from honeypot session transcripts. The API is stateless, requires an API key, and returns JSON matching the query schema.

## Mental Model

Think of AgentQL as a **semantic JSON extractor**. You give it:
1. **Source**: URL or raw HTML
2. **Schema**: Either an AgentQL query (structured) or natural language prompt
3. **Output**: JSON data matching your schema

For HoneyAgent, we feed attacker conversation transcripts as HTML and define a schema for threat indicators. AgentQL uses AI to understand the content semantically and extract matching data.

## Key Concepts

### AgentQL Query Language
A schema definition language that specifies what data to extract and its structure.

```
{
  intent
  targets[]
  techniques[]
  indicators_of_compromise[]
}
```

The query defines the JSON shape. AgentQL fills in values by analyzing the content.

### Natural Language Prompts
Alternative to query language. Describe what you want in plain English:

```
"Extract the attacker's intent, any targets mentioned, attack techniques used, and indicators of compromise"
```

Less precise but faster to prototype.

### REST API Endpoint
```
POST https://api.agentql.com/v1/query-data
Headers:
  X-API-Key: <your_api_key>
  Content-Type: application/json

Body:
{
  "html": "<content to analyze>",
  "query": "{ schema }" | "prompt": "natural language"
}
```

## API Reference

### Query Data Endpoint

**URL**: `https://api.agentql.com/v1/query-data`
**Method**: POST

**Request Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Either url or html | Web page URL to scrape |
| `html` | string | Either url or html | Raw HTML content to analyze |
| `query` | string | Either query or prompt | AgentQL schema query |
| `prompt` | string | Either query or prompt | Natural language description |
| `params` | object | No | Additional settings |

**Response**:
```json
{
  "data": {
    // Extracted data matching query schema
  },
  "metadata": {
    "request_id": "uuid"
  }
}
```

### Authentication
All requests require `X-API-Key` header. Generate keys at [dev.agentql.com](https://dev.agentql.com).

## History

- **2023**: TinyFish launches AgentQL as web scraping tool
- **2024**: REST API added for non-browser use cases
- **2025**: Natural language prompts added, HTML input support expanded
- **2026**: MCP integration for AI agents, enhanced structured extraction

## Current State

AgentQL is mature for web scraping but novel for our use case (text analysis). Key limitations:
1. Designed for HTML structure, not free-form text
2. No batch processing API
3. Rate limits apply (check dev portal)

**Our adaptation**: Wrap conversation transcripts in minimal HTML to leverage the extraction engine.

## Open Questions

- What are the rate limits for the API?
- How does it handle malformed/minimal HTML?
- Performance on long conversation transcripts?
- Cost per API call?

## Controversies

- **Privacy**: AgentQL processes content on TinyFish servers. For production, consider on-premise alternatives.
- **Determinism**: AI-based extraction may vary between calls. Important for consistent threat classification.

## HoneyAgent Integration Design

### Use Case
Extract structured threat indicators from attacker-honeypot conversation transcripts:
- **Intent**: credential_theft, reconnaissance, lateral_movement, privilege_escalation
- **Targets**: specific systems, data, or access mentioned
- **Techniques**: social_engineering, pretexting, authority_impersonation
- **IOCs**: domains, IPs, tool names mentioned

### Implementation

```python
# backend/integrations/tinyfish.py

AGENTQL_ENDPOINT = "https://api.agentql.com/v1/query-data"

# Our extraction query
PATTERN_QUERY = """
{
  attacker_intent
  targets[]
  techniques[]
  indicators_of_compromise[]
  threat_level
  mitre_attack_id
}
"""
```

### Fallback Strategy
When AgentQL is unavailable:
1. Regex-based extraction using keyword patterns
2. Return hardcoded fallback from `config/fallbacks.yaml`

Fallback matches this schema from config:
```yaml
tinyfish:
  status: "extracted"
  patterns:
    intent: "credential_theft"
    techniques: ["social_engineering", "authority_impersonation"]
    targets: ["database", "admin_access"]
    threat_level: "high"
```

## Sources

- [AgentQL Official Documentation](https://docs.agentql.com/) - Primary reference
- [REST API Reference](https://docs.agentql.com/rest-api/api-reference) - Endpoint details
- [Scraping Data API Guide](https://docs.agentql.com/scraping/scraping-data-api) - Usage examples
- [Getting Data from HTML](https://docs.agentql.com/scraping/getting-data-from-html-api) - HTML input method
- [GitHub Repository](https://github.com/tinyfish-io/agentql) - SDK and examples
- [TinyFish Website](https://www.tinyfish.ai/) - Company info

## Implications

1. **Immediate**: Can enhance fingerprinting with semantic extraction
2. **Demo**: Always fallback to regex if API fails - demo cannot crash
3. **Future**: Consider local LLM extraction for sensitive deployments
