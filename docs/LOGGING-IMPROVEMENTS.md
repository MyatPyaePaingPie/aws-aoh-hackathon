# Fingerprint Logging Improvements

**Date:** 2026-01-16
**Updated files:**
- `backend/tools/log_interaction.py` - Backend fingerprint logging with MITRE mappings
- `backend/tools/log_attack.py` - Backend attack logging with MITRE mappings
- `backend/api/main.py` - Frontend Activity Log fingerprint events

## Overview

Three-layer logging system for complete fingerprint visibility:

1. **Backend Logs** — Console output showing internal pipeline (creation → storage)
2. **MITRE ATT&CK Mappings** — Technique IDs on all fingerprints and attacks
3. **Frontend Activity Log** — Real-time display of fingerprint capture and storage

## Backend Console Logging

### Fingerprint Creation + Storage Pipeline

```
================================================================================
[FINGERPRINT CREATED] 2026-01-16T12:34:56.789Z
  Agent: db-admin-001
  Threat Level: HIGH
  INTEL: Privilege Escalation [T1078.003]
  INTEL: Credential Dumping [T1110.004]
  Session ID: abc123def456
================================================================================

[LOCAL_STORAGE] ✓ Fingerprint stored to local JSONL (path=/logs/fingerprints.jsonl)
[EMBEDDING] Starting embedding generation via AWS Bedrock (amazon.titan-embed-text-v2:0)
[EMBEDDING] ✓ Embedding generated successfully via Bedrock (1024 dimensions)
[S3_VECTORS] Starting storage to AWS S3 Vectors (bucket=honeyagent-fingerprints, index=attacker-patterns)
[S3_VECTORS] Prepared metadata: threat_level=HIGH, agent=db-admin-001, techniques=['T1078.003', 'T1110.004']
[S3_VECTORS] ✓ Fingerprint stored in S3 Vectors (key=interaction-a1b2c3d4e5)
[FINGERPRINT_COMPLETE] Fingerprint storage pipeline complete
```

### Attack Logging with MITRE

```
================================================================================
[ATTACK LOGGED] 2026-01-16T12:34:57.123Z
  Phase: privilege_escalation
  INTEL: Privilege Escalation [T1078.003]
  Target: db-admin-001
  Session ID: abc123def456
================================================================================

[LOCAL_STORAGE] ✓ Attack logged to local JSONL (path=/logs/attacks.jsonl)
```

### Fallback Behavior (S3 Failure)

```
[S3_VECTORS] Failed to store in S3 Vectors: ConnectionError - falling back to local storage
[S3_VECTORS] Vector storage did not complete, local JSONL copy retained for fallback
[FINGERPRINT_PIPELINE] Exception during S3 storage: ServiceError - local JSONL is authoritative backup
```

## Frontend Activity Log Display

The demo Activity Log shows the **complete fingerprint storage pipeline**:

```
[FINGERPRINT CREATED] db-admin-001
Threat: HIGH | INTEL: Privilege Escalation [T1078.003]

[LOCAL_STORAGE] ✓ Fingerprint stored to local JSONL

[EMBEDDING] ✓ Vector generated via AWS Bedrock (amazon.titan-embed-text-v2:0)

[S3_VECTORS] ✓ Fingerprint stored to S3 Vectors (honeyagent-fingerprints)
Embedding: vec_9b2c7e3d... stored to S3 Vectors
```

Each event appears in **green/amber "captured" styling** for clear visual distinction.

## MITRE ATT&CK Mappings

### Fingerprint Techniques (Threat Indicators)

| Indicator | Technique | ID |
|-----------|-----------|-----|
| credential_request | Credential Dumping | T1110.004 |
| privilege_escalation | Privilege Escalation | T1078.003 |
| data_exfiltration | Exfiltration Over Network | T1041 |
| reconnaissance | Reconnaissance | T1592 |
| probing | System Network Configuration Discovery | T1016 |
| suspicious_query | Data Staged | T1213.002 |

### Attack Tactics (Phases)

All attack phases mapped to MITRE tactics:
- reconnaissance → T1592
- privilege_escalation → T1078.003
- credential_access → T1110
- discovery → T1526
- And 10+ others

## Log Levels

| Level | Purpose | Visible In |
|-------|---------|-----------|
| `DEBUG` | Detailed pipeline steps | Backend console only |
| `INFO` | Major events | Backend console + relevant frontend logs |
| `WARNING` | Degradation events | Backend console + alert logs |
| `ERROR` | Failures | Backend console + error logs |

## Service Attribution

Every log explicitly names the AWS service:

| Service | Backend Tag | Frontend Display |
|---------|-------------|-----------------|
| AWS Bedrock (Titan v2) | `[EMBEDDING]` | `AWS Bedrock (amazon.titan-embed-text-v2:0)` |
| AWS S3 Vectors | `[S3_VECTORS]` | `S3 Vectors (honeyagent-fingerprints)` |
| Local JSONL | `[LOCAL_STORAGE]` | `local JSONL` |
| CloudWatch | (metrics) | Shown in stats bar |

## Demo Flow

When running PLAY DEMO in the frontend, you see:

1. **Attack Phase Begins** → Phase banner appears (RECON, PROBE, TRUST, EXPLOIT)
2. **Threat Detected** → Threat level updates (LOW → MEDIUM → HIGH)
3. **Routing Decision** → Auth0 Identity Gateway panel shows JWT/FGA checks
4. **Honeypot Engaged** → Agent turns red, engaged badge appears
5. **Fingerprint Created** → Activity Log shows:
   - `[FINGERPRINT CREATED]` with MITRE technique
   - `[LOCAL_STORAGE]` confirmation
   - `[EMBEDDING]` confirmation
   - `[S3_VECTORS]` confirmation
6. **Evolution Updated** → Defense effectiveness % updates in stats bar

## Debugging

### Backend Console (Terminal)

```bash
# See complete pipeline execution
docker logs honeyagent-backend | grep -E "\[FINGERPRINT|EMBEDDING|S3_VECTORS"

# Find specific technique
docker logs honeyagent-backend | grep "T1078.003"

# Follow all fingerprints
docker logs honeyagent-backend -f | grep "FINGERPRINT CREATED"
```

### Frontend Activity Log (Browser)

Right-click → Inspect Element on any log entry to see:
- Event type (captured, alert, phase, etc.)
- Message and detail fields
- MITRE technique + ID

### Local Files

```bash
# Raw fingerprint data
cat logs/fingerprints.jsonl | jq '.threat_indicators'

# Attack timeline
cat logs/attacks.jsonl | jq '.tactic, .phase'
```

## Guarantees

✓ **Local JSONL always succeeds** — every fingerprint persists
✓ **S3 failures are silent** — no crashes, logs show fallback
✓ **All services attributed** — exact AWS service named in each event
✓ **MITRE mappings everywhere** — technique IDs on fingerprints + attacks
✓ **Frontend visibility** — complete pipeline visible in Activity Log
✓ **Demo-ready** — no errors in console, clean narrative flow
