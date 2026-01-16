# Fingerprint Logging Improvements

**Date:** 2026-01-16
**Updated files:** `backend/tools/log_interaction.py`, `backend/tools/log_attack.py`

## Overview

Enhanced logging to make fingerprint capture and storage crystal clear in logs. Each step now explicitly identifies:
- When fingerprints are **CREATED**
- When they are **STORED** to each service
- Which AWS services are being used (Bedrock, S3 Vectors)
- Fallback behavior when services fail

## Logging Structure

### Fingerprint Capture (`log_interaction.py`)

```
[FINGERPRINT CREATED] 2026-01-16T12:34:56.789Z
  Agent: db-admin-001
  Threat Level: HIGH
  Indicators: credential_request, privilege_escalation
  Session ID: abc123def456
```

### Storage Pipeline

**Stage 1: Local JSONL Storage (Always)**
```
[LOCAL_STORAGE] ✓ Fingerprint stored to local JSONL (path=/logs/fingerprints.jsonl)
```

**Stage 2: Bedrock Embedding**
```
[EMBEDDING] Starting embedding generation via AWS Bedrock (amazon.titan-embed-text-v2:0)
[EMBEDDING] ✓ Embedding generated successfully via Bedrock (1024 dimensions)
```

**Stage 3: S3 Vectors Storage**
```
[S3_VECTORS] Starting storage to AWS S3 Vectors (bucket=honeyagent-fingerprints, index=attacker-patterns)
[S3_VECTORS] Prepared metadata: threat_level=HIGH, agent=db-admin-001
[S3_VECTORS] ✓ Fingerprint stored in S3 Vectors (key=interaction-a1b2c3d4e5f6)
```

**Fallback (if S3 fails)**
```
[S3_VECTORS] Failed to store in S3 Vectors: ConnectionError - falling back to local storage
[S3_VECTORS] Vector storage did not complete, local JSONL copy retained for fallback
```

### Attack Logging (`log_attack.py`)

```
[ATTACK LOGGED] 2026-01-16T12:34:57.123Z
  Phase: recon
  Tactic: reconnaissance
  Target: db-admin-001
  Session ID: abc123def456

[LOCAL_STORAGE] ✓ Attack logged to local JSONL (path=/logs/attacks.jsonl)
```

## Log Levels

| Level | Purpose | Examples |
|-------|---------|----------|
| `DEBUG` | Detailed pipeline steps | Embedding start, S3 connection init, vector_key generation |
| `INFO` | Major events | Fingerprint CREATED, storage SUCCESS, complete |
| `WARNING` | Degradation events | S3 Vector storage fallback, invalid embedding dimensions |
| `ERROR` | Failures | Bedrock API errors, file write failures |

## Service Attribution

Each log message now includes the AWS service being used:

| Service | Tag | Used For |
|---------|-----|----------|
| AWS Bedrock (Titan) | `[EMBEDDING]` | Vector embedding generation |
| AWS S3 Vectors | `[S3_VECTORS]` | Vector storage and metadata |
| Local JSONL | `[LOCAL_STORAGE]` | Persistent fallback storage |
| Fingerprint Pipeline | `[FINGERPRINT_PIPELINE]` | Overall orchestration |
| Attack Pipeline | `[ATTACK LOGGED]` | Attack event recording |

## Log Parsing

### Find all fingerprints created:
```bash
grep "\[FINGERPRINT CREATED\]" logs/*.log
```

### Find S3 Vectors storage:
```bash
grep "\[S3_VECTORS\]" logs/*.log
```

### Find Bedrock embedding calls:
```bash
grep "\[EMBEDDING\]" logs/*.log
```

### Find fallback activations:
```bash
grep "falling back\|did not complete" logs/*.log
```

### Find failures:
```bash
grep "\[ERROR\]\|\[WARNING\]" logs/*.log
```

## Guarantees

1. **Local JSONL always succeeds** — every fingerprint gets written locally
2. **S3 failures are silent** — no crashes, logs show fallback activation
3. **All services are attributed** — logs show exactly which AWS service is doing what
4. **Pipeline is visible** — follow timestamp to see complete flow

## For Demo

When running `demo-check`, look for:
- `[FINGERPRINT CREATED]` entries showing attacks were captured
- `[S3_VECTORS]` entries showing intelligent vector storage
- No `[ERROR]` entries (or if present, followed by successful fallback)
- Clear separation between attack phases
