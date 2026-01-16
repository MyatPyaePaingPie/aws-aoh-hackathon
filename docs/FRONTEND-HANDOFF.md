# Frontend Handoff: HoneyAgent Dashboard

## CONTEXT HANDOFF

**Summary**: Frontend research complete for 3D honeypot visualization; need to implement Threlte-based dashboard with honeycomb/swarm visuals.

**Goal**: Build an unforgettable visual dashboard that makes the honeypot metaphor visceral and wows hackathon judges.

**Current state**:
- Backend: Identity track complete (token validation, FGA, routing)
- Backend: Agents track in progress (agents.py, tools, tests exist)
- Frontend: Research complete, no implementation yet
- Research docs written to `frontend/_research/`

**Decisions made**:
- Stack: Recommend **SvelteKit + Threlte 8** (not Astro) for easier 3D integration
- Graphics: **Three.js via Threlte** for 3D, with bloom post-processing
- Metaphor: Hybrid approach - honeycomb structure with digital/glitch effects when threats appear
- Fallback: CSS grid honeycomb + Canvas 2D if WebGL fails

**Artifacts created**:
- `frontend/_research/hive-visualizations.md` - Creative direction, swarm/boids research, color palettes
- `frontend/_research/threlte-deep-dive.md` - Technical integration guide, gotchas, code examples

**Open threads**:
- Final decision on literal vs abstract vs hybrid visual style
- Whether to do 3D hexagonal tunnel or 2D top-down view
- Color palette confirmation (amber gold vs "corrupted gold" with glitch)

---

## Technical Decisions

### Recommended Stack

```json
{
  "framework": "SvelteKit",
  "3d": "@threlte/core + @threlte/extras",
  "three": "^0.160+",
  "animations": "useTask hook (Threlte 8)",
  "post-processing": "UnrealBloomPass for glow effects"
}
```

### Why NOT Astro

- Astro adds friction for 3D (islands, SSR conflicts, `client:load` everywhere)
- SvelteKit gives full control over rendering pipeline
- 3D is client-only anyway, Astro's static benefits don't help

### Core Visual Effects (Priority Order)

1. **Honeycomb Grid** - Hexagonal cells, each = one agent (1h)
2. **Bloom Glow** - Cells glow amber when active (30min)
3. **Swarm Boids** - Particles moving with emergent behavior (2-3h)
4. **Threat Visualization** - Red particles for attackers, visual corruption (1-2h)
5. **Real-time Data** - WebSocket connection to `/api/logs/stream` (1h)

### Color Palette

| Element | Hex | Use |
|---------|-----|-----|
| Background | `#1a1408` | Dark honey |
| Primary/Agent | `#f59e0b` | Amber |
| Engaged Trap | `#fbbf24` | Yellow glow |
| Threat | `#ef4444` | Red |
| Safe | `#22c55e` | Green |
| Fingerprint | `#3b82f6` | Blue |

---

## API Endpoints (Backend Provides)

### `GET /api/swarm/status`
```json
{
  "agents": [
    {"id": "a1", "status": "active", "connections": ["a2", "a3"]},
    {"id": "a2", "status": "active", "connections": ["a1", "a4"]}
  ],
  "active_traps": 2,
  "threats_detected": 1
}
```

### `GET /api/threats`
```json
{
  "threats": [{
    "id": "threat-001",
    "level": "HIGH",
    "first_seen": "2026-01-16T14:32:01Z",
    "actions": ["probed_network", "requested_credentials"],
    "similar_to": ["threat-2024-001"]
  }]
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

## Quick Start Implementation

### Minimal 5-Minute Scene

```svelte
<!-- src/lib/components/HiveScene.svelte -->
<script>
  import { Canvas, T } from '@threlte/core'
  import { OrbitControls } from '@threlte/extras'
</script>

<Canvas>
  <T.PerspectiveCamera position={[0, 10, 15]} />
  <OrbitControls />

  <T.AmbientLight intensity={0.3} />
  <T.PointLight position={[0, 5, 0]} color="#f59e0b" intensity={2} />

  <!-- Honeycomb grid goes here -->
  <T.GridHelper args={[20, 20]} />
</Canvas>

<style>
  :global(canvas) {
    width: 100%;
    height: 100vh;
    background: #1a1408;
  }
</style>
```

### Project Setup

```bash
# Create SvelteKit project
npm create svelte@latest frontend
cd frontend

# Install Threlte
npm install @threlte/core @threlte/extras three

# Install post-processing (for bloom)
npm install postprocessing

# Run dev server
npm run dev
```

---

## Creative Direction Options

### Option A: Top-Down Hive Map (Safer)
- 2D hexagonal grid viewed from above
- Agents as glowing hexagon cells
- Attacks as particles flowing between cells
- Simpler to implement, guaranteed to work

### Option B: 3D Hive Interior (Ambitious)
- Camera inside hexagonal tunnel
- Surrounded by honeycomb walls
- Attacks swarm through the tunnel
- More impressive, higher risk

### Option C: Hybrid (Recommended)
- Start with top-down view
- Add depth/layers to hexagons (3D extrusion)
- Particle systems for movement
- Bloom for glow effects

---

## Demo Requirements (from DEMO-SCRIPT.md)

The frontend must support the 9-beat demo:

1. **Beat 1**: Show 6 agent nodes in network
2. **Beat 2**: Reveal that 4 are honeypots (visual differentiation)
3. **Beat 3**: Red node appears (imposter)
4. **Beat 6**: Yellow "TRAP ENGAGED" indicator
5. **Beat 8**: Threat intelligence panel with fingerprint data

### Must-Have UI Elements

- [ ] Network graph showing agents
- [ ] Visual distinction for engaged traps (yellow glow)
- [ ] Threat indicator (red) for attackers
- [ ] Live log stream panel
- [ ] Threat level indicator

### Nice-to-Have

- [ ] Force-directed graph with D3/Three.js
- [ ] Real-time WebSocket updates
- [ ] Interactive hover states
- [ ] Demo mode with step-by-step progression

---

## Warnings

- **SSR will break 3D**: Always use `ssr: false` in SvelteKit routes with 3D
- **Threlte 7 examples are outdated**: Use `useTask` not `useFrame`
- **Large bundles**: Three.js adds ~200KB gzip - lazy load if needed
- **Performance**: Don't enable `interactive` prop on high-poly meshes without BVH

---

## File Paths to Read

- `frontend/_research/hive-visualizations.md` - Full creative research
- `frontend/_research/threlte-deep-dive.md` - Threlte 8 technical guide
- `docs/FRONTEND-VISION.md` - Original vision doc
- `docs/DEMO-SCRIPT.md` - Demo requirements
- `config/fallbacks.yaml` - Fallback responses if backend fails

---

## Continuation Prompt for New Session

> We're building the HoneyAgent frontend - a 3D honeypot visualization dashboard for a hackathon. Research is complete in `frontend/_research/`. Stack is SvelteKit + Threlte 8 + Three.js. Need to implement: honeycomb grid, bloom glow effects, swarm particles for agents/threats, and WebSocket connection to `/api/logs/stream`. Start by scaffolding the SvelteKit project and creating the basic Canvas scene. See `docs/FRONTEND-HANDOFF.md` for full context.

---

## Contact

- Backend/Agents Track: Aria
- Frontend: [Your Partner]

**Rule**: Coordinate before touching shared files (`backend/api/`, `config/fallbacks.yaml`).
