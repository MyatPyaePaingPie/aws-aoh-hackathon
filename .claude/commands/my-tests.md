# Run Tests for Your Track

Run the tests that belong to your development track.

## Usage

```
/my-tests agents    # Run Aria's track tests
/my-tests identity  # Run Partner's track tests
/my-tests all       # Run all tests
```

## Execution

Based on the argument, run the appropriate tests:

### Agents Track (Aria)
```bash
pytest tests/unit/test_agents.py tests/unit/test_tools.py -v
```

### Identity Track (Partner)
```bash
pytest tests/unit/test_identity.py tests/unit/test_router.py -v
```

### All Tests
```bash
pytest tests/ -v
```

## After Running

1. Report pass/fail count
2. If failures, show which tests failed
3. Suggest fixes based on test names
