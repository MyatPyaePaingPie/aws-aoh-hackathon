# Fallback-First Rule

**The demo cannot fail.**

## Pattern

Every function that calls an external service must:

```python
async def call_external_service(params):
    try:
        result = await external_service(params)
        return result
    except Exception:
        return get_fallback("service_name")
```

## Fallback Sources

1. Check `config/fallbacks.yaml` for predefined responses
2. If not defined, create one that sounds plausible
3. Never return error messages to the user

## Fallback Response Rules

- Sounds like the system is working
- No words: "error", "fail", "exception", "crash", "broken"
- Status codes always 2xx
- Honeypot fallbacks sound inviting/helpful
- Real agent fallbacks sound like queued processing

## Examples

### Good Fallback
```python
except Exception:
    return {"status": "processing", "response": "Request acknowledged."}
```

### Bad Fallback
```python
except Exception as e:
    return {"error": str(e)}  # NEVER expose errors
```

## Verification

Before completing any implementation:
```bash
grep -r '"error"' backend/ config/ && echo "FAIL: Error strings found" || echo "OK"
```
