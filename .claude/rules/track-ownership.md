# Track Ownership Rule

**Never edit another track's files without syncing first.**

## File Ownership

### Agents Track (Aria)
```
OWNS:
backend/core/agents.py
backend/tools/*.py
prompts/*.md
config/agents.yaml
tests/unit/test_agents.py
tests/unit/test_tools.py
```

### Identity Track (Partner)
```
OWNS:
backend/core/identity.py
backend/core/router.py
config/routing.yaml
config/auth0.yaml
tests/unit/test_identity.py
tests/unit/test_router.py
```

### Shared (Both)
```
backend/api/main.py
config/fallbacks.yaml
tests/integration/*
tests/e2e/*
frontend/*
```

## Before Editing

1. Check ownership above
2. If your file: edit freely
3. If partner's file: message them first
4. If shared file: coordinate timing

## Conflict Prevention

- One person edits at a time
- Commit and push frequently (every 15 min)
- Pull before starting new work
