# Frontend Sponsor Enhancement Guide

Quick reference for adding sponsor attribution to the demo UI.

---

## Current State ✅

Your frontend already has:
- Tech stack tooltips with all 6 sponsors
- Activity log showing system events
- Routing decision panel  
- Stats metrics
- Demo controls

---

## Enhancement 1: Add Sponsor Attribution to Activity Log

**Goal:** Show which sponsor powers each event in real-time

### Current Activity Log
```
[FINGERPRINT CREATED] Captured from db-admin-001
[S3 VECTORS] Stored to honeyagent-fingerprints bucket
[BEDROCK] Embedding generated via amazon.titan-embed-text-v2:0
```

### Enhanced Activity Log (Add Icons/Colors)
```
🔐 [AUTH0 JWT] Token validation: INVALID → Routing to honeypot
🛡️  [AUTH0 FGA] Permission check: DENIED → Honeypot engaged
🤖 [AWS BEDROCK] Agent db-admin-001 responding...
🔍 [TINYFISH] Pattern extracted: intent=credential_theft, threat=HIGH
🎭 [TONIC] Generated synthetic credential: pg_f7a8c2e1b3d4...
📊 [S3 VECTORS] Fingerprint stored (key: interaction-a1b2c3)
```

### Implementation (add to your log message formatting):

```typescript
// In your activity log component
const sponsorIcons = {
  'AUTH0 JWT': '🔐',
  'AUTH0 FGA': '🛡️',
  'AWS BEDROCK': '🤖',
  'TINYFISH': '🔍',
  'TONIC': '🎭',
  'S3 VECTORS': '📊'
};

const sponsorColors = {
  'AUTH0 JWT': '#eb5424',     // Auth0 orange
  'AUTH0 FGA': '#eb5424',
  'AWS BEDROCK': '#ff9900',   // AWS orange
  'S3 VECTORS': '#ff9900',
  'TINYFISH': '#00d4ff',      // TinyFish blue
  'TONIC': '#9333ea'          // Tonic purple
};
```

---

## Enhancement 2: Sponsor Stats Bar

**Goal:** Show real-time sponsor usage metrics

### Add Below Existing Stats Bar

```svelte
<!-- Sponsor Activity Bar -->
<div class="sponsor-stats">
  <div class="sponsor-stat">
    <span class="sponsor-icon">🔐</span>
    <span class="sponsor-label">Auth0</span>
    <span class="sponsor-value">{auth0Checks}</span>
  </div>
  <div class="sponsor-stat">
    <span class="sponsor-icon">🤖</span>
    <span class="sponsor-label">Bedrock</span>
    <span class="sponsor-value">{bedrockCalls}</span>
  </div>
  <div class="sponsor-stat">
    <span class="sponsor-icon">🔍</span>
    <span class="sponsor-label">TinyFish</span>
    <span class="sponsor-value">{tinyfishPatterns}</span>
  </div>
  <div class="sponsor-stat">
    <span class="sponsor-icon">🎭</span>
    <span class="sponsor-label">Tonic</span>
    <span class="sponsor-value">{tonicCreds}</span>
  </div>
  <div class="sponsor-stat">
    <span class="sponsor-icon">📊</span>
    <span class="sponsor-label">S3 Vectors</span>
    <span class="sponsor-value">{s3Fingerprints}</span>
  </div>
</div>
```

### CSS
```css
.sponsor-stats {
  display: flex;
  gap: 1.5rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  margin: 1rem 0;
}

.sponsor-stat {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.sponsor-icon {
  font-size: 1.2rem;
}

.sponsor-label {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
}

.sponsor-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #00ff88;
}
```

---

## Enhancement 3: Routing Decision Panel - Add Sponsor Labels

**Current:**
```
✓ Auth0 JWT Present
✗ Auth0 FGA Allowed
→ Route: honeypot_db_admin
```

**Enhanced with sponsor tags:**
```
🔐 [AUTH0 M2M]
✓ JWT Signature Valid
✓ Claims Extracted: agent_id=attacker-001

🛡️ [AUTH0 FGA]  
✗ Permission Denied: agent:attacker-001 can_communicate swarm:alpha
→ HONEYPOT TRAP TRIGGERED

🤖 [AWS STRANDS]
✓ Routing to: honeypot_db_admin
✓ Agent spawned: db-admin-001
```

---

## Enhancement 4: Demo Flow with Sponsor Callouts

**Add sponsor callout badges when hovering over events**

```svelte
{#if event.type === 'fingerprint_captured'}
  <div class="activity-item captured">
    <div class="activity-sponsors">
      <span class="mini-badge">🤖 Bedrock</span>
      <span class="mini-badge">🔍 TinyFish</span>
      <span class="mini-badge">📊 S3 Vectors</span>
    </div>
    <div class="activity-content">
      {event.message}
    </div>
  </div>
{/if}
```

---

## Enhancement 5: Add "Powered By" Section to Bottom

```svelte
<footer class="sponsor-footer">
  <h4>Powered By:</h4>
  <div class="sponsor-logos">
    <div class="sponsor-logo-item">
      <img src="/logos/aws.svg" alt="AWS" />
      <span>Bedrock + S3 Vectors + Strands SDK</span>
    </div>
    <div class="sponsor-logo-item">
      <img src="/logos/auth0.svg" alt="Auth0" />
      <span>M2M JWT + FGA</span>
    </div>
    <div class="sponsor-logo-item">
      <span class="logo-text">TinyFish</span>
      <span>AgentQL Pattern Extraction</span>
    </div>
    <div class="sponsor-logo-item">
      <span class="logo-text">Tonic</span>
      <span>Fabricate Synthetic Data</span>
    </div>
  </div>
</footer>
```

---

## Enhancement 6: Fingerprint Panel - Show Sponsor Pipeline

**When displaying a captured fingerprint:**

```svelte
<div class="fingerprint-card">
  <div class="fingerprint-header">
    <h4>Attacker Fingerprint Captured</h4>
    <span class="threat-badge high">HIGH THREAT</span>
  </div>
  
  <div class="fingerprint-pipeline">
    <div class="pipeline-step complete">
      <span class="step-icon">🔍</span>
      <div class="step-content">
        <strong>TinyFish Extraction</strong>
        <div class="step-detail">Intent: credential_theft</div>
        <div class="step-detail">Techniques: social_engineering</div>
      </div>
    </div>
    
    <div class="pipeline-step complete">
      <span class="step-icon">🤖</span>
      <div class="step-content">
        <strong>Bedrock Embedding</strong>
        <div class="step-detail">1024 dimensions generated</div>
        <div class="step-detail">Model: amazon.titan-embed-text-v2:0</div>
      </div>
    </div>
    
    <div class="pipeline-step complete">
      <span class="step-icon">📊</span>
      <div class="step-content">
        <strong>S3 Vectors Storage</strong>
        <div class="step-detail">Bucket: honeyagent-fingerprints</div>
        <div class="step-detail">Key: interaction-{id}</div>
      </div>
    </div>
  </div>
</div>
```

---

## Quick Implementation Priority

### Must Have (5 min):
1. ✅ Add sponsor icons to activity log messages
2. ✅ Add sponsor stats bar showing usage counts

### Nice to Have (15 min):
3. ✅ Enhanced routing panel with sponsor labels
4. ✅ Fingerprint pipeline visualization
5. ✅ Powered by footer

### Optional (30 min):
6. ⭕ Animated sponsor badges on hover
7. ⭕ Sponsor "spotlight" when their tech activates
8. ⭕ Real-time sponsor usage graph

---

## Code Locations

**Files to modify:**
- `frontend/src/routes/+page.svelte` - Main demo page
- Add counters for tracking sponsor usage
- Add sponsor attribution to SSE event handlers

**Event handler updates:**

```typescript
// Track sponsor usage
let sponsorStats = $state({
  auth0_checks: 0,
  bedrock_calls: 0,
  tinyfish_patterns: 0,
  tonic_credentials: 0,
  s3_fingerprints: 0
});

// In your SSE handlers:
eventSource.addEventListener('fingerprint_captured', (e) => {
  const data = JSON.parse(e.data);
  
  // Increment sponsor counters
  sponsorStats.bedrock_calls++;
  sponsorStats.tinyfish_patterns++;
  sponsorStats.s3_fingerprints++;
  
  // Add sponsor attribution to log
  activityLog.push({
    type: 'sponsor',
    sponsor: 'TINYFISH',
    message: `Pattern extracted: ${data.intel.technique}`
  });
  
  activityLog.push({
    type: 'sponsor',
    sponsor: 'S3 VECTORS',
    message: `Fingerprint stored: ${data.intel.embedding.substring(0, 20)}...`
  });
});
```

---

## Visual Mock-up

```
┌─────────────────────────────────────────────────────────┐
│  HoneyAgent Demo                                        │
│  Deception-as-a-Service for AI Agent Networks          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔐 Auth0: 47  🤖 Bedrock: 23  🔍 TinyFish: 12        │
│  🎭 Tonic: 8   📊 S3 Vectors: 15                      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Activity Log:                                          │
│                                                         │
│  🔐 [AUTH0 JWT] Token validation: INVALID              │
│  🛡️  [AUTH0 FGA] Permission check: DENIED              │
│  🤖 [AWS BEDROCK] Honeypot engaged: db-admin-001       │
│  🔍 [TINYFISH] Extracted: credential_theft (HIGH)      │
│  🎭 [TONIC] Generated fake cred: pg_a1b2c3d4...        │
│  📊 [S3 VECTORS] Fingerprint stored                    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Routing Decision:                                      │
│                                                         │
│  🔐 [AUTH0 M2M]                                        │
│   ✓ JWT Valid                                          │
│   ✗ FGA Denied                                         │
│                                                         │
│  → HONEYPOT TRAP: db-admin-001                         │
│                                                         │
└─────────────────────────────────────────────────────────┘

Powered by: AWS (Bedrock + S3 Vectors + Strands) | 
           Auth0 (M2M + FGA) | TinyFish | Tonic
```

---

## Testing Your Changes

**Before demo:**
1. Run a test attack flow
2. Verify all 6 sponsors appear in logs
3. Check that counters increment correctly
4. Ensure tooltips still work
5. Screenshot the "all sponsors active" state for backup

**During demo:**
- Point to sponsor stats bar and say: "Watch how all 6 sponsors activate"
- As log events appear, call them out: "There's TinyFish extracting patterns..."
- End by showing final stats: "15 fingerprints in S3 Vectors, 8 fake credentials from Tonic..."

---

## Bonus: Judge-Friendly Summary Panel

Add a "System Overview" that shows all sponsors at a glance:

```svelte
<div class="system-overview">
  <h3>Sponsor Integration Map</h3>
  
  <div class="integration-flow">
    <div class="flow-step">
      <strong>1. Identity</strong>
      <span>Auth0 M2M JWT</span>
      <span class="file-ref">identity.py</span>
    </div>
    →
    <div class="flow-step">
      <strong>2. Authorization</strong>
      <span>Auth0 FGA</span>
      <span class="file-ref">router.py</span>
    </div>
    →
    <div class="flow-step">
      <strong>3. Agent</strong>
      <span>AWS Strands + Bedrock</span>
      <span class="file-ref">agents.py</span>
    </div>
    ↓
    <div class="flow-step">
      <strong>4. Pattern Extract</strong>
      <span>TinyFish AgentQL</span>
      <span class="file-ref">tinyfish.py</span>
    </div>
    +
    <div class="flow-step">
      <strong>5. Fake Data</strong>
      <span>Tonic Fabricate</span>
      <span class="file-ref">tonic_fabricate.py</span>
    </div>
    +
    <div class="flow-step">
      <strong>6. Storage</strong>
      <span>S3 Vectors</span>
      <span class="file-ref">log_interaction.py</span>
    </div>
  </div>
</div>
```

This gives judges an instant visual of how all 6 sponsors fit together.

---

Good luck with the demo! 🚀
