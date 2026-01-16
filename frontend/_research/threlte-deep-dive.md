# Threlte: Deep Dive

## Summary

Threlte 8 is the current stable release of a declarative, type-safe 3D framework for Svelte that wraps Three.js. The API is centered around the `<T>` component for composition, with hooks like `useTask` replacing `useFrame` for animation. Astro integration is theoretically possible but not officially documented; the framework provides extensive extras via `@threlte/extras` including OrbitControls, GLTF loading, and physics via Rapier. Performance depends on scene complexity and optimization practices.

---

## Mental Model

**How to think about Threlte:**

```
Threlte = Declarative UI Paradigm for 3D

Traditional Three.js:
  scene = new Scene()
  mesh = new Mesh(geom, material)
  scene.add(mesh)
  // imperative, sequential, hard to reason about

Threlte approach:
  <T.Scene>
    <T.Mesh geometry={geom} material={material} />
  </T.Scene>
  // declarative, reactive, familiar to Svelte devs
```

**Core principles:**

1. **Single `<T>` component** at the root—gateway to all Three.js objects
2. **Props mirror Three.js**—e.g., `<T.Mesh scale={2} position.x={10} />`
3. **Reactive by default**—changing props updates the scene automatically
4. **Hooks for frame logic**—`useTask` replaces per-frame callbacks
5. **Extras for common patterns**—don't reinvent OrbitControls; use `<OrbitControls />`

**Constraint to internalize:**
- Threlte is optimized for Svelte's reactivity model; it doesn't play well with mutation-heavy frameworks
- Props must be type-stable (can't change a prop from array to number during lifetime)
- Astro integration requires wrapping in Svelte components with special config

---

## Key Concepts

### The `<T>` Component

The fundamental building block. Maps directly to Three.js constructors:

```svelte
<T.Mesh
  position.x={1}
  position.y={2}
  scale={1.5}
  on:pointerenter={handleHover}
>
  <T.BoxGeometry args={[1, 2, 3]} />
  <T.MeshStandardMaterial color="hotpink" />
</T.Mesh>
```

**Key differences from vanilla Three.js:**

- No manual `scene.add(mesh)` needed—declarative hierarchy handles it
- Props update reactively (if `scale` changes, the mesh updates)
- Events are Svelte events (`on:click`, `on:pointerenter`)
- Geometry and material are children, not arguments

### useTask Hook (Threlte 8)

Replaces `useFrame` from Threlte 7. Used for per-frame logic:

```svelte
<script>
  import { useTask } from '@threlte/core'

  let { useTask } = $props()

  useTask((delta) => {
    // delta is time since last frame in seconds
    mesh.rotation.y += delta * 0.5
  })
</script>
```

**Migration from v7:**

- Old: `useFrame((state, delta) => { ... })`
- New: `useTask((delta) => { ... })` + `useThrelte()` for context
- `useTask` has better dependency tracking and render stage support

### Reactive Props

Threlte automatically syncs prop changes to Three.js objects:

```svelte
<script>
  let scale = $state(1)
  let color = $state('red')
</script>

<!-- Scale and color update automatically when reactive values change -->
<T.Mesh scale={scale}>
  <T.MeshStandardMaterial {color} />
</T.Mesh>

<button on:click={() => scale = 2}>Double Scale</button>
```

**Performance consideration:** Use "pierced props" (dot notation) for partial updates:
```svelte
<!-- Good: only position.x updates -->
<T.Mesh position.x={x} position.y={y} position.z={z} />

<!-- Less efficient: whole position vector compared -->
<T.Mesh position={{ x, y, z }} />
```

### Plugin System

Extend Threlte with custom props and hooks:

```svelte
<!-- Custom prop added by plugin -->
<T.Mesh useMyPlugin={{ option: true }} />
```

Used by `@threlte/rapier` (physics), `@threlte/theatre` (animation studio), `@threlte/xr` (VR/AR).

---

## Threlte 7 vs. 8: Major Changes

| Feature | Threlte 7 | Threlte 8 |
|---------|-----------|-----------|
| **Frame Hook** | `useFrame(state, delta)` | `useTask(delta)` + `useThrelte()` |
| **Context Access** | Built into `useFrame` | Via `useThrelte()` hook |
| **Render Pipeline** | `useRender()` callback | `useTask()` with `renderStage` |
| **Task Dependencies** | `order` prop | `dependencies` array |
| **Documentation** | Legacy at v7.threlte.xyz | Current at threlte.xyz |
| **API Stability** | Stable but pre-emptive | Refined, breaking changes resolved |

**Recommendation:** Use Threlte 8 for new projects. Threlte 7 still works but is in legacy mode.

---

## Current State: Latest Releases (Jan 2025)

**Current versions:**
- `@threlte/core`: Latest stable
- `@threlte/extras`: v9.7.1 (2 months ago)
- `@threlte/rapier`: Physics engine integration
- `@threlte/theatre`: Theatre.js animation studio
- `@threlte/gltf`: CLI for GLTF → Threlte components
- `@threlte/xr`: WebXR (VR/AR) support
- `@threlte/flex`: Yoga layout engine integration

**Hacker News attention (Jan 2025):** Threlte 8 discussed on HN with positive reception for API improvements.

---

## @threlte/extras: Pre-Built Components

### Content Components
- **`<GLTF>` / `useGltf`**—Load and render 3D models from glTF files
- **`<Text>` / `<Text3DGeometry>`**—2D and 3D text rendering
- **`<SVG>`**—Display SVG in 3D space
- **`<Decal>`**—Apply decals to surfaces
- **`<HTML>`**—Embed HTML content into 3D scenes
- **`<RoundedBoxGeometry>`**—Boxes with rounded edges
- **`useTexture`**—Texture loading helper

### Interaction Components
- **`<OrbitControls>`**—Arcball camera manipulation (most used)
- **`<CameraControls>` / `<TrackballControls>`**—Alternative control schemes
- **`<TransformControls>`**—Translate/rotate/scale objects
- **`<Gizmo>`**—Visual transform widget
- **`interactivity` plugin**—Click detection, event handling
- **`useCursor` / `useGamepad`**—Input device support
- **`bvh`**—Optimized raycasting for collision detection

### Environment & Staging
- **`<Environment>` / `<CubeEnvironment>`**—HDRI lighting and backgrounds
- **`<Sky>`**—Atmospheric sky rendering
- **`<Grid>` / `<Stars>`**—Scene utility meshes
- **`<Float>` / `<Billboard>`**—Auto-positioning behaviors
- **`<ContactShadows>` / `<SoftShadows>`**—Shadow effects
- **`<Suspense>` / `onReveal` / `onSuspend`**—Asset loading management
- **`useProgress`**—Loading progress tracking

### Audio
- **`<Audio>` / `<PositionalAudio>`**—Sound with spatial support

---

## Astro + Threlte Integration

**Current State:** Not officially documented, but possible with constraints.

### Why It's Tricky

1. **Threlte is Svelte-first**—requires Svelte preprocessor
2. **Astro uses Svelte as an island framework**—components are isolated, not full-page control
3. **Three.js needs canvas**—requires careful SSR handling

### Integration Path (Theoretical)

```bash
# 1. Install Astro Svelte integration
npm install --save-dev astro @astrojs/svelte

# 2. Install Threlte
npm install @threlte/core @threlte/extras three

# 3. Configure astro.config.mjs
export default defineConfig({
  integrations: [svelte()],
  vite: {
    ssr: {
      noExternal: ['three']  // Critical: prevent three.js externalization
    }
  }
})
```

### Best Practice: Svelte Component Wrapper

```svelte
<!-- src/components/MyScene.svelte (island component) -->
<script>
  import { Canvas } from '@threlte/core'
  import { OrbitControls } from '@threlte/extras'

  export let modelUrl = '/model.gltf'
</script>

<Canvas>
  <T.PerspectiveCamera position={[0, 0, 10]} />
  <OrbitControls />

  {#await loadModel(modelUrl) then model}
    <T.Group>
      {@html model}
    </T.Group>
  {/await}
</Canvas>

<style>
  :global(canvas) {
    width: 100%;
    height: 100%;
  }
</style>
```

```astro
<!-- src/pages/index.astro -->
---
import MyScene from '../components/MyScene.svelte'
---

<html>
  <body>
    <MyScene client:load modelUrl="/my-model.gltf" />
  </body>
</html>
```

**Key:** Use `client:load` directive to ensure component hydrates on the client where Three.js runs.

### Astro Constraints

- Canvas must render client-side only (`client:*` directive required)
- SSR will fail silently if Three.js code runs on server
- Large models may cause network overhead on page load
- Build-time optimizations (pre-baking, LOD) become more important

**Recommendation:** Astro + Threlte is viable for small interactive 3D elements, not full-page 3D experiences. Use SvelteKit for 3D-heavy projects.

---

## Impressive Examples & Demos

### Community Showcase

1. **Procedural Hexagonal Planet**—Real-time generated terrain
2. **3D Motion Graphics**—Shape-based animated compositions
3. **Threlte Live**—VRM avatar streaming with real-time chat, ElevenLabs TTS lip-sync, Mixamo animations, Cloudflare edge deployment
4. **RGB Color Matching Game**—3D space-based color learning
5. **Warhammer 40k Galaxy Timeline**—Complex 3D data visualization

### Official Examples
- `threlte.xyz/docs/examples/examples`—Curated gallery
- Tutorials: animating spaceships, loading GLTF models, physics
- Interactive playground for experimenting with `<T>` components

### Performance Showcase
- Real-time planet generation without stuttering
- Physics-enabled objects with Rapier
- VRM avatar streaming at 60fps with streaming video + audio

---

## Limitations & Gotchas

### Performance Constraints

**Raytracing overhead:** The `interactive` property (for click detection) raycasts every frame, even if only detecting `on:click`. Workaround: use `bvh` component for optimized raycasting.

```svelte
<!-- Slow: raycasts on every frame -->
<T.Mesh interactive on:click={handleClick} />

<!-- Fast: uses BVH acceleration structure -->
<T.Mesh>
  <T.BVHGeometry ... />
</T.Mesh>
```

**Scene complexity:** Three.js performance degrades with:
- 1000+ objects without instancing
- High-resolution textures (use compression, resize)
- Unoptimized geometries (use LOD, culling)

### Type Stability Requirement

Props must have **constant types** for their lifetime:

```svelte
<!-- NOT ALLOWED: type changes array → number -->
<script>
  let data = $state([1, 2, 3])
  // Later:
  data = 5  // ERROR: type changed from array to number
</script>

<T.Mesh args={data} />
```

Workaround: Always ensure prop types remain constant.

### SSR Limitations

Three.js and canvas rendering are inherently client-side:

```svelte
<!-- Must use +page.svelte (CSR only) or client:load in Astro -->
<!-- +page.server.ts will NOT work -->
```

### Known Issues (GitHub)

- **Issue #24**: `interactive` property causes slowdown during cursor hover
- **Magic-string version conflict**: Older Astro + Threlte combinations failed (mostly resolved in recent versions)
- **GLTF loading**: Large models need preloading or Suspense wrapper

### What to Avoid

| ❌ Don't | ✅ Do |
|---------|--------|
| Mutate Three.js objects directly | Use reactive props |
| Use `useFrame`; it's deprecated | Use `useTask` in Threlte 8 |
| Render thousands of static objects | Use instancing or LOD |
| Enable `interactive` on high-poly meshes | Use `bvh` for raycasting |
| Load large models without Suspense | Use `<Suspense>` or preload |
| Mix Astro SSR with 3D components | Use `client:load` on 3D islands |

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── routes/
│   ├── +page.svelte          # 3D-heavy page (SvelteKit)
│   └── components/
│       ├── Scene.svelte      # Main Canvas wrapper
│       ├── Model.svelte      # GLTF loader with Suspense
│       ├── Environment.svelte # Lighting, sky, shadows
│       └── Controls.svelte    # OrbitControls, input
├── prompts/                  # Store shader code here
├── config/
│   └── scene.yaml            # Scene config (lights, camera)
└── lib/
    └── threlte/
        ├── hooks.ts          # Custom useTask wrappers
        └── materials.ts      # Material factories
```

### Performance Best Practices

1. **Lazy-load models** with `<Suspense>`
2. **Use environment maps** instead of multiple lights
3. **Implement LOD** (level-of-detail) for complex geometry
4. **Preload textures** via `useTexture`
5. **Batch static geometry** with instancing
6. **Profile with Chrome DevTools** (GPU profiler)

---

## Integration Checklist

### For SvelteKit Projects

- [x] Install: `npm i @threlte/core @threlte/extras three`
- [x] Add `noExternal: ['three']` to vite config
- [x] Wrap scenes in `<Canvas>` from `@threlte/core`
- [x] Use `useTask` for animation loops
- [x] Load models with `<GLTF>` + `<Suspense>`
- [x] Add `<OrbitControls>` for interaction

### For Astro Projects

- [x] Install Astro Svelte integration: `npm i @astrojs/svelte`
- [x] Configure `noExternal: ['three']` in vite
- [x] Wrap 3D components in Svelte files
- [x] Use `client:load` directive on island components
- [x] Test SSR: ensure no canvas code runs on server
- [x] Measure bundle size (Three.js adds ~200KB gzip)

---

## Migration Path: Threlte 7 → 8

### Breaking Changes

```typescript
// Threlte 7
useFrame((state, delta) => {
  mesh.rotation.y += delta
})

// Threlte 8
const { scene, camera } = useThrelte()
useTask((delta) => {
  mesh.rotation.y += delta
})
```

### Updated Hooks

| Threlte 7 | Threlte 8 | Notes |
|-----------|-----------|-------|
| `useFrame` | `useTask` | Context via `useThrelte()` |
| `useRender` | `useTask(..., { stage: renderStage })` | Explicit stage selection |
| `useContext` | `useThrelte` | Same purpose, new name |

### Process

1. Update package: `npm i @threlte/core@latest`
2. Replace `useFrame` → `useTask` + `useThrelte`
3. Check task dependencies (order → dependencies)
4. Run tests, verify animations smooth
5. Deploy with confidence (v8 is stable)

---

## Recommended Stack for HoneyAgent

**Recommendation: SvelteKit + Threlte 8 + @threlte/extras**

**Why:**
- Full control over rendering pipeline
- No SSR conflicts (3D is client-only anyway)
- `useTask` integrates seamlessly
- Extras provide 90% of common needs
- Community support is strong

**Stack:**
```json
{
  "@threlte/core": "latest",
  "@threlte/extras": "latest",
  "@threlte/rapier": "^0.x",
  "three": "^r128+",
  "svelte": "^5",
  "sveltekit": "^2"
}
```

**If Astro is required:**
- Use Svelte island components with `client:load`
- Separate 3D UI into isolated components
- Test early: canvas + SSR has edge cases

---

## Open Questions

- **Threlte 8 performance at scale:** Does reactive prop tracking degrade with 10K+ objects? (Likely needs instancing regardless)
- **WebXR maturity:** Is `@threlte/xr` production-ready for VR experiences?
- **Theatre.js integration:** Does animation studio workflow justify the bundle cost?
- **Astro hybrid rendering:** Can Threlte work in mixed SSR/CSR pages, or is full isolation required?
- **Three.js version pinning:** How often does Threlte update Three.js peer dependency?

---

## Controversies & Trade-offs

### Controversy: Reactivity Overhead vs. Performance

**Tension:** Threlte's reactivity model (reactive props) is elegant for UI devs but adds overhead compared to raw Three.js imperative mutations.

**Reality check:**
- For scenes with <1000 objects: negligible overhead
- For complex scenes: manual imperative mutations may be faster
- **Mitigate:** Use pierced props, avoid unnecessary updates, profile

### Trade-off: Convenience vs. Control

**Threlte extras** provide pre-built components (OrbitControls, Environment) but may not fit all use cases.

**Reality check:**
- 80% of projects use standard components
- 20% need custom shaders or performance tweaks
- **Mitigate:** Extras are composable; build custom variants

### Trade-off: Bundle Size

Three.js + Threlte + extras = ~200-300KB gzip for a basic scene.

**Reality check:**
- For 3D-focused sites: acceptable
- For mostly-static sites: consider vanilla Three.js or Babylon.js
- **Mitigate:** Tree-shake unused extras, lazy-load models

---

## Practical Recommendations for HoneyAgent

### If Building 3D Honeypot Agent Visualization

1. **Use SvelteKit** as host framework (no Astro conflicts)
2. **Start with `@threlte/extras`**—use OrbitControls, HTML overlay, Environment
3. **Load agent GLTF models** with `<GLTF>` + `<Suspense>`
4. **Animate with `useTask`** (Threlte 8 only)
5. **Add physics if needed**—use `@threlte/rapier` for agent movement
6. **Profile early**—measure frame time, GPU load with DevTools

### If Astro Integration Required

1. **Wrap 3D in Svelte island component** (`src/components/AgentVisualizer.svelte`)
2. **Render as `client:load`** in Astro pages
3. **Optimize model loading**—preload gltf, compress textures
4. **Test SSR before deploying**—ensure no canvas code on server
5. **Monitor bundle size**—Three.js should not block page load

### Fast Demo Path

```svelte
<!-- Minimal working scene in <5 mins -->
<script>
  import { Canvas } from '@threlte/core'
  import { OrbitControls, GLTF } from '@threlte/extras'
</script>

<Canvas>
  <T.PerspectiveCamera position={[10, 10, 10]} />
  <OrbitControls />

  <T.AmbientLight intensity={0.5} />
  <T.DirectionalLight position={[10, 10, 10]} intensity={1} />

  <GLTF url="/honeypot-agent.gltf" />

  <T.GridHelper args={[10, 10]} />
</Canvas>

<style>
  :global(canvas) {
    width: 100%;
    height: 100vh;
  }
</style>
```

This gives you:
- Interactive 3D model
- Proper lighting
- Ground reference (grid)
- Free camera controls

---

## Sources

- [Threlte Official Docs](https://threlte.xyz/) — Current v8 documentation
- [Threlte v7 Legacy Docs](https://v7.threlte.xyz/) — Reference for older projects
- [Threlte on GitHub](https://github.com/threlte/threlte) — Source code, issues, examples
- [Threlte Examples Gallery](https://threlte.xyz/docs/examples/examples) — Community showcase
- [Migration Guide: Threlte 7 → 8](https://threlte.xyz/docs/learn/advanced/migration-guides) — Breaking changes
- [useTask Hook Reference](https://threlte.xyz/docs/reference/core/use-task) — Animation API
- [Threlte Extras Reference](https://threlte.xyz/docs/reference/extras/getting-started) — Components library
- [Hacker News: Threlte 8](https://news.ycombinator.com/item?id=42813264) — Recent community discussion (Jan 2025)
- [This Dot Labs: Harnessing Threlte](https://www.thisdot.co/blog/harnessing-the-power-of-threlte-building-reactive-three-js-scenes-in-svelte) — Deep dive article
- [Subvisual: Smooth Motion with Threlte](https://subvisual.com/blog/posts/smooth_motion_with_threejs_and_threlte/) — Animation best practices
- [Astro Svelte Integration](https://docs.astro.build/en/guides/integrations-guide/svelte/) — Island component setup
