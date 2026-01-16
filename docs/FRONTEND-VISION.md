# Frontend Vision: The Hive Dashboard

---

## Overview

A real-time visualization of the HoneyAgent network. The honeypot metaphor is literal: a hive with bees, where some are workers (real agents) and others are guard bees (honeypots) waiting to swarm invaders.

**Stack:** Astro + Svelte (minimal JS, fast, island architecture)

---

## Visual Metaphor: The Hive

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                        🍯 HONEYAGENT HIVE 🍯                         │
│                                                                     │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │                    SWARM VIEW                           │    │
│     │                                                         │    │
│     │         🐝          🐝                                  │    │
│     │           \        /                                    │    │
│     │            🐝────🐝                                     │    │
│     │           /        \        🔴 ← imposter               │    │
│     │         🐝          🐝      /                           │    │
│     │                      \    /                             │    │
│     │                       🐝                                │    │
│     │                                                         │    │
│     │  Legend: 🐝 = Agent (real or honeypot—you can't tell)   │    │
│     │          🔴 = Detected threat                           │    │
│     │          🟡 = Trap engaged                              │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │
│  │   THREAT INTEL      │  │   LIVE INTERACTION LOG              │  │
│  │                     │  │                                     │  │
│  │   Active Traps: 2   │  │   14:32:01 [TRAP] db-admin engaged  │  │
│  │   Fingerprints: 47  │  │   14:32:03 [LOG] credential request │  │
│  │   Blocked: 12       │  │   14:32:05 [TRAP] fake creds issued │  │
│  │                     │  │   14:32:08 [VECTOR] fingerprint saved│  │
│  │   Threat Level:     │  │                                     │  │
│  │   ████████░░ HIGH   │  │                                     │  │
│  └─────────────────────┘  └─────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pages

### 1. Swarm View (Main Dashboard)

**URL:** `/`

**Components:**
- Network graph (force-directed) showing all agents
- Nodes are unlabeled (can't tell real from honeypot)
- When threat detected: red node appears
- When trap engaged: yellow pulse animation
- Click node → shows agent stats (but not real/honeypot status)

**Data source:** `GET /api/swarm/status`

### 2. Threat Intel Panel

**URL:** `/threats` or sidebar panel

**Components:**
- List of recent fingerprints
- Similarity matches ("This attacker resembles...")
- Threat level indicator
- Action history for each attacker

**Data source:** `GET /api/threats`

### 3. Live Log Stream

**URL:** `/logs` or sidebar panel

**Components:**
- Real-time WebSocket stream of events
- Color-coded by type:
  - 🟢 Normal agent activity
  - 🟡 Trap engagement
  - 🔴 Threat detection
  - 🔵 Fingerprint stored

**Data source:** `WS /api/logs/stream`

### 4. Demo Mode

**URL:** `/?demo=true`

**Special behavior:**
- Pre-loaded scenario
- Step-by-step progression
- Annotations explaining each beat
- "Next" button to advance demo

---

## Components (Svelte)

### `SwarmGraph.svelte`

Force-directed graph using D3 or custom canvas.

```svelte
<script>
  export let agents = [];
  export let connections = [];
  export let threats = [];

  // D3 force simulation
</script>

<svg class="swarm-graph">
  {#each agents as agent}
    <circle
      class:honeypot={agent.engaged}
      class:threat={threats.includes(agent.id)}
    />
  {/each}
</svg>
```

### `ThreatCard.svelte`

Single threat fingerprint display.

```svelte
<script>
  export let threat;
</script>

<div class="threat-card">
  <h3>Threat #{threat.id}</h3>
  <div class="threat-level {threat.level}">
    {threat.level}
  </div>
  <ul>
    {#each threat.actions as action}
      <li>{action}</li>
    {/each}
  </ul>
</div>
```

### `LogStream.svelte`

Real-time scrolling log.

```svelte
<script>
  import { onMount } from 'svelte';

  let logs = [];

  onMount(() => {
    const ws = new WebSocket('ws://localhost:8000/api/logs/stream');
    ws.onmessage = (e) => {
      logs = [...logs, JSON.parse(e.data)].slice(-100);
    };
  });
</script>

<div class="log-stream">
  {#each logs as log}
    <div class="log-entry {log.type}">
      <span class="timestamp">{log.time}</span>
      <span class="message">{log.message}</span>
    </div>
  {/each}
</div>
```

---

## Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark honey | `#1a1408` |
| Primary (bee/agent) | Amber | `#f59e0b` |
| Real agent | (invisible) | Same as Primary |
| Honeypot engaged | Yellow glow | `#fbbf24` |
| Threat detected | Red | `#ef4444` |
| Safe/normal | Green | `#22c55e` |
| Log: trap | Yellow | `#eab308` |
| Log: threat | Red | `#dc2626` |
| Log: normal | Gray | `#6b7280` |
| Log: fingerprint | Blue | `#3b82f6` |

---

## API Endpoints (Backend Support Needed)

### `GET /api/swarm/status`

```json
{
  "agents": [
    {"id": "a1", "status": "active", "connections": ["a2", "a3"]},
    {"id": "a2", "status": "active", "connections": ["a1", "a4"]},
    // ... (no real/honeypot distinction exposed!)
  ],
  "active_traps": 2,
  "threats_detected": 1
}
```

### `GET /api/threats`

```json
{
  "threats": [
    {
      "id": "threat-001",
      "level": "HIGH",
      "first_seen": "2026-01-16T14:32:01Z",
      "actions": ["probed_network", "requested_credentials", "accepted_fake_creds"],
      "similar_to": ["threat-2024-001"]
    }
  ]
}
```

### `WS /api/logs/stream`

```json
{
  "type": "trap",
  "time": "14:32:01",
  "message": "db-admin-001 engaged by unknown agent",
  "agent_id": "db-admin-001",
  "threat_id": "threat-001"
}
```

---

## Implementation Priority

### MVP (Hour 5-6, if time)

1. Static Astro page with hardcoded swarm visualization
2. Manual refresh to show state changes
3. No WebSocket, just polling

### Nice-to-Have

1. Real-time WebSocket log stream
2. Force-directed graph with D3
3. Threat fingerprint cards
4. Demo mode with annotations

### Post-Hackathon

1. Historical threat playback
2. Attack pattern visualization
3. Export threat reports
4. Multi-swarm support

---

## File Structure

```
frontend/
├── astro.config.mjs
├── package.json
├── src/
│   ├── components/
│   │   ├── SwarmGraph.svelte
│   │   ├── ThreatCard.svelte
│   │   ├── LogStream.svelte
│   │   └── ThreatLevel.svelte
│   ├── layouts/
│   │   └── Layout.astro
│   ├── pages/
│   │   ├── index.astro        # Main dashboard
│   │   └── threats.astro      # Threat detail page
│   └── styles/
│       └── global.css         # Honey color scheme
└── public/
    └── favicon.svg            # 🍯 or 🐝
```

---

## Fallback UI

If frontend isn't ready for demo:

1. Use terminal output exclusively
2. ASCII art swarm diagram
3. JSON responses shown directly
4. Narrate what dashboard "would show"

The demo works without frontend. Frontend is polish, not core.
