# Tonic Fabricate: Deep Dive

## Summary

Tonic Fabricate is an AI-powered synthetic data generation platform that creates realistic fake data from scratch. It offers a REST API at `https://fabricate.tonic.ai/api/v1` with Bearer token authentication, a Python SDK (`tonic-fabricate`), and supports multiple output formats (CSV, SQL, JSON, JSONL, XML). For HoneyAgent, we integrate it to generate realistic fake credentials that are more convincing than static templates.

## Mental Model

Fabricate is designed for bulk data generation (databases, tables, rows) rather than single-value generation. The workflow is:
1. Define a schema (database/table structure with column generators)
2. Request data generation (async process)
3. Download or stream results

For our use case (generating single fake credentials on-demand), we need to either:
- Use the API to generate small batches and cache them
- Use the Python SDK with minimal schema definitions
- Fall back to local generation when API is slow/unavailable

## Key Concepts

### Authentication
- **Method**: Bearer token in Authorization header
- **Header format**: `Authorization: Bearer <TONIC_API_KEY>`
- **Environment variable**: `FABRICATE_API_KEY` (SDK) or `TONIC_API_KEY` (our convention)
- **Base URL**: `https://fabricate.tonic.ai/api/v1`

### Python SDK
```bash
pip install tonic-fabricate
```

**Key function**: `generate()`
- `workspace`: Target workspace name (default: 'Default')
- `database`: Database name to generate from
- `format`: Output format (sql, sqlite, csv, jsonl, xml)
- `dest`: Local destination path
- `on_progress`: Callback for progress tracking

**Environment variables read by SDK**:
- `FABRICATE_API_KEY`: Required API authentication
- `FABRICATE_API_URL`: Optional, defaults to `https://fabricate.tonic.ai/api/v1`

### Data Generators

Fabricate supports extensive field generators:

| Category | Examples |
|----------|----------|
| Identity | Names, SSN, identifying info |
| Communication | Email, phone numbers |
| Location | Addresses, cities, countries |
| Professional | Job titles, company names |
| Financial | Credit cards, bank accounts |
| Security | Passwords, tokens (custom) |

### Generator Types
- **Single Value**: Insert same value in all rows
- **Blank**: Insert null
- **Boolean**: Random true/false
- **Numeric**: Various distributions (uniform, normal, etc.)
- **Character Sequence**: Pattern-based generation
- **AI Generator**: LLM-powered contextual generation

## History

- **Origins**: Fabricate was originally Mockaroo, acquired by Tonic.ai
- **November 2025**: Launched "Fabricate Data Agent" - natural language chat interface
- **AWS re:Invent 2025**: Demonstrated relational database, JSON, PDF, DOCX generation

## Current State

- **Pricing**: Free tier available
- **Speed**: Can generate "hyper-realistic datasets in under 5 minutes"
- **Outputs**: CSV, SQL, JSON, JSONL, XML, PDF, DOCX, EML
- **Databases**: PostgreSQL, MySQL, Databricks, Oracle, MongoDB
- **Integration**: CI/CD pipelines, mock API endpoints

## Open Questions

1. **Single-value generation latency**: Is the API fast enough for on-demand credential generation?
2. **Rate limits**: What are the API rate limits for the free tier?
3. **Custom generators**: Can we define custom credential patterns (API keys, JWT tokens)?
4. **Caching strategy**: Should we pre-generate batches or generate on-demand?

## Controversies

- **Latency vs. realism tradeoff**: API provides more realistic data but adds latency. For honeypots, latency might be acceptable since attackers expect some delay.
- **Dependency risk**: External API dependency for security tool. Mitigated with comprehensive fallbacks.

## Implementation for HoneyAgent

### Strategy
1. **Primary**: Use Tonic Fabricate API for realistic credentials
2. **Fallback**: Use existing local template generation (current fake_credential.py logic)
3. **Caching**: Pre-generate common credential types on startup

### Credential Mapping

| Our Type | Fabricate Generator |
|----------|---------------------|
| `api_key` | Character Sequence with pattern |
| `db_password` | Password generator |
| `email` | Email generator |
| `name` | Full Name generator |
| `address` | Full Address generator |
| `phone` | Phone Number generator |
| `credit_card` | Credit Card generator |
| `ssn` | SSN generator |

### API Approach

Since Fabricate is designed for bulk generation, our approach:

1. **Direct API call** for simple types (if available)
2. **Pre-generated cache** for common credential types
3. **Local fallback** always available

### Code Structure

```
backend/integrations/tonic_fabricate.py
  - TonicFabricateClient class
  - generate_credential(type) -> str
  - Fallback to local templates

backend/tools/fake_credential.py
  - Uses TonicFabricateClient
  - Falls back to existing templates
```

## Sources

- [Tonic Fabricate Product Page](https://www.tonic.ai/products/fabricate) - Overview and features
- [Tonic Fabricate Documentation](https://docs.tonic.ai/fabricate) - API reference
- [Python SDK](https://github.com/TonicAI/tonic-fabricate-python) - Installation and usage
- [API Examples](https://github.com/mockaroo/fabricate-api-examples) - Code samples
- [Data Type Generators](https://docs.tonic.ai/fabricate/table-columns/generator-reference/data-type-and-specific-values) - Available generators
- [Tonic.ai October 2025 Updates](https://securityboulevard.com/2025/10/tonic-ai-product-updates-october-2025/) - Recent features

## Implications for HoneyAgent

1. **More convincing honeypots**: Realistic credentials increase attacker engagement time
2. **Reduced pattern detection**: Varied credentials make honeypot detection harder
3. **Analytics potential**: Track which credential types attract most attackers
4. **Fallback safety**: Never breaks - always has local generation available
