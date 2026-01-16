# Demo Check

Verify the full demo flow works before rehearsal.

## Execution

Run the e2e tests that validate all 9 demo beats:

```bash
pytest tests/e2e/test_demo_flow.py -v
```

## What It Checks

1. **Beat 1-2**: Swarm structure (agents exist, honeypots indistinguishable)
2. **Beat 3-4**: Imposter can send requests
3. **Beat 5**: Real agents reject invalid tokens
4. **Beat 6**: Honeypots engage imposters
5. **Beat 7**: Honeypots have credential/logging tools
6. **Beat 8**: Fingerprint structure is correct
7. **Beat 9**: Killshot line exists in demo script

## After Running

1. Report overall status
2. If any beat fails, identify which and explain impact
3. Check that all fallbacks work (no error strings in responses)

## Critical Check

Run this additional verification:

```bash
# Verify no fallback mentions "error"
grep -r "error" config/fallbacks.yaml && echo "WARNING: Fallback contains 'error'" || echo "OK: No error strings"
```
