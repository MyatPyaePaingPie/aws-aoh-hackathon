# Sync

Pull latest changes, run tests, push your work.

## Execution

```bash
# 1. Pull latest
git pull --rebase

# 2. Run all tests
pytest tests/ -v

# 3. If tests pass, commit and push
git add .
git commit -m "sync: [describe changes]"
git push
```

## When to Use

- Before starting a new work session
- At sync points (Hour 1, 2, 3, 4, 5)
- Before editing shared files
- When partner says "sync up"

## Conflict Resolution

If pull has conflicts:
1. Check which files conflict
2. If in your track: resolve and commit
3. If in partner's track: message them first
4. If shared file: coordinate resolution
