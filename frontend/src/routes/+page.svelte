<script lang="ts">
	import { onMount } from 'svelte';
	import {
		connectToDemo,
		stopDemo,
		type DemoAgent,
		type PhaseChangeEvent,
		type LogEvent,
		type EvolutionStats,
		type RoutingDecisionEvent
	} from '$lib/api';

	// ============================================================
	// STATE
	// ============================================================

	// Demo state
	let demoRunning = $state(false);
	let demoComplete = $state(false);
	let eventSource: EventSource | null = $state(null);
	let demoMode = $state<'live' | 'scripted' | null>(null);

	// Agents in the honeycomb
	interface VisualAgent extends DemoAgent {
		spawned: boolean;
		engaged: boolean;
		targeted: boolean;
		responding: boolean;
		x: number;
		y: number;
	}
	let agents = $state<VisualAgent[]>([]);

	// Attacker
	let attackerVisible = $state(false);
	let attackerPosition = $state({ x: 50, y: 0 });

	// Phase & threat
	let currentPhase = $state<PhaseChangeEvent | null>(null);
	let threatLevel = $state<string>('NONE');

	// Activity log - simplified types matching backend
	type LogType = 'system' | 'alert' | 'phase' | 'attacker' | 'honeypot' | 'captured' | 'routing' | 'legitimate' | 'success' | 'result' | 'tinyfish' | 'cline';
	interface LogEntry {
		id: number;
		type: LogType;
		message: string;
		detail?: string;
	}
	let logs = $state<LogEntry[]>([]);
	let logId = 0;

	// Legitimate agent indicator
	let legitimateVisible = $state(false);
	let legitimatePosition = $state({ x: 50, y: 0 });
	let currentActor = $state<'attacker' | 'legitimate' | null>(null);

	// Routing decision display
	let routingDecision = $state<RoutingDecisionEvent | null>(null);

	// Stats
	let fingerprintsCaptured = $state(0);

	// Evolution stats
	let evolutionStats = $state<EvolutionStats | null>(null);

	// ============================================================
	// HELPERS
	// ============================================================

	function addLog(type: LogType, message: string, detail?: string) {
		logs = [{ id: ++logId, type, message, detail }, ...logs].slice(0, 30);
	}

	function getHexPosition(index: number, total: number): { x: number; y: number } {
		// Arrange in a honeycomb pattern - centered
		const cols = 3;
		const row = Math.floor(index / cols);
		const col = index % cols;
		const offsetX = row % 2 === 1 ? 65 : 0; // Offset odd rows for honeycomb effect
		const cellWidth = 130;
		const cellHeight = 120;
		// Center the grid horizontally (using calc based on container)
		const gridWidth = cols * cellWidth;
		const containerWidth = 700; // approximate visible area
		const startX = (containerWidth - gridWidth) / 2 + 50;
		return {
			x: startX + col * cellWidth + offsetX,
			y: 60 + row * cellHeight
		};
	}

	function getThreatColor(level: string): string {
		switch (level) {
			case 'LOW':
				return '#22c55e';
			case 'MEDIUM':
				return '#eab308';
			case 'HIGH':
				return '#f97316';
			case 'CRITICAL':
				return '#ef4444';
			default:
				return '#6b7280';
		}
	}

	// ============================================================
	// DEMO CONTROL
	// ============================================================

	function startDemo() {
		// Reset state
		agents = [];
		logs = [];
		attackerVisible = false;
		legitimateVisible = false;
		currentPhase = null;
		threatLevel = 'NONE';
		demoComplete = false;
		fingerprintsCaptured = 0;
		evolutionStats = null;
		routingDecision = null;
		currentActor = null;
		demoRunning = true;
		demoMode = null; // Will be set when we detect the mode

		eventSource = connectToDemo({
			onStart: (data) => {
				// Detect mode from the start event
				const startData = data as { mode?: string };
				if (startData.mode === 'LIVE') {
					demoMode = 'live';
				} else {
					demoMode = 'scripted';
				}
			},

			onAgentSpawn: (data) => {
				const pos = getHexPosition(data.index, data.total);
				const newAgent: VisualAgent = {
					...data.agent,
					spawned: true,
					engaged: false,
					targeted: false,
					responding: false,
					x: pos.x,
					y: pos.y
				};
				agents = [...agents, newAgent];
			},

			onAttackerSpawn: () => {
				attackerVisible = true;
				attackerPosition = { x: 50, y: 20 };
			},

			onPhaseChange: (data) => {
				currentPhase = data;
				threatLevel = data.threat_level;
				// Track actor from phase (backend includes actor in phase_change)
				const phaseData = data as PhaseChangeEvent & { actor?: string };
				if (phaseData.actor === 'legitimate') {
					currentActor = 'legitimate';
					attackerVisible = false;
					legitimateVisible = true;
				} else if (phaseData.actor === 'attacker') {
					currentActor = 'attacker';
					attackerVisible = true;
					legitimateVisible = false;
				}
				routingDecision = null; // Reset routing decision for new phase
			},

			onAttackerMove: (data) => {
				const target = agents.find((a) => a.id === data.target_agent_id);
				if (target) {
					attackerPosition = { x: target.x - 30, y: target.y - 30 };
					agents = agents.map((a) => ({
						...a,
						targeted: a.id === data.target_agent_id
					}));
				}
			},

			onLog: (data) => {
				// All narrative logs come through here
				addLog(data.type, data.message, data.detail);
			},

			onHoneypotEngage: (data) => {
				agents = agents.map((a) => ({
					...a,
					engaged: a.id === data.agent_id ? true : a.engaged,
					targeted: false
				}));
			},

			onFingerprintCaptured: () => {
				fingerprintsCaptured++;
			},

			onEvolutionUpdate: (data) => {
				evolutionStats = data.stats;
			},

			onComplete: () => {
				demoRunning = false;
				demoComplete = true;
				routingDecision = null;
			},

			onRoutingDecision: (data) => {
				routingDecision = data;
			},

			onLegitimateRequest: (data) => {
				// Move legitimate agent indicator toward target
				const target = agents.find((a) => a.id === data.target_agent_id);
				if (target) {
					legitimatePosition = { x: target.x - 30, y: target.y - 30 };
					agents = agents.map((a) => ({
						...a,
						targeted: a.id === data.target_agent_id
					}));
				}
			},

			onRealAgentRespond: (data) => {
				// Mark real agent as responding (green glow)
				agents = agents.map((a) => ({
					...a,
					responding: a.id === data.agent_id,
					targeted: false
				}));
				// Clear responding state after animation
				setTimeout(() => {
					agents = agents.map((a) => ({
						...a,
						responding: false
					}));
				}, 2000);
			},

			onError: () => {
				demoRunning = false;
			}
		});
	}

	async function handleStopDemo() {
		await stopDemo();
		eventSource?.close();
		demoRunning = false;
		addLog('system', 'Demo stopped');
	}

	function resetDemo() {
		agents = [];
		logs = [];
		attackerVisible = false;
		legitimateVisible = false;
		currentPhase = null;
		threatLevel = 'NONE';
		demoComplete = false;
		fingerprintsCaptured = 0;
		evolutionStats = null;
		routingDecision = null;
		currentActor = null;
		demoMode = null;
	}

	// ============================================================
	// LIFECYCLE
	// ============================================================

	onMount(() => {
		return () => {
			eventSource?.close();
		};
	});

	// Computed
	let honeypotCount = $derived(agents.filter((a) => a.is_honeypot).length);
	let engagedCount = $derived(agents.filter((a) => a.engaged).length);
</script>

<div class="dashboard">
	<header>
		<h1>HONEYAGENT HIVE</h1>
		<div class="header-right">
			{#if currentPhase}
				<div class="phase-badge" style="background: {getThreatColor(threatLevel)}">
					{currentPhase.phase_title}
				</div>
			{/if}
			<div class="threat-indicator" style="background: {getThreatColor(threatLevel)}">
				{threatLevel === 'NONE' ? 'STANDBY' : `THREAT: ${threatLevel}`}
			</div>
		</div>
	</header>

	<!-- Demo Controls -->
	<div class="demo-controls">
		{#if !demoRunning && !demoComplete}
			<button class="demo-btn play" onclick={startDemo}>PLAY DEMO</button>
		{:else if demoRunning}
			<button class="demo-btn stop" onclick={handleStopDemo}>STOP</button>
			{#if demoMode === 'live'}
				<span class="demo-mode live">LIVE</span>
				<span class="demo-status">Real agent-to-agent combat</span>
			{:else if demoMode === 'scripted'}
				<span class="demo-mode scripted">SCRIPTED</span>
				<span class="demo-status">Fallback mode</span>
			{:else}
				<span class="demo-status">Connecting...</span>
			{/if}
		{:else}
			<button class="demo-btn play" onclick={startDemo}>REPLAY</button>
			<button class="demo-btn reset" onclick={resetDemo}>RESET</button>
			<span class="demo-status complete">Demo complete!</span>
			{#if demoMode === 'live'}
				<span class="demo-mode live">LIVE</span>
			{/if}
		{/if}
	</div>

	<div class="stats-bar">
		<div class="stat">
			<span class="stat-value">{agents.length}</span>
			<span class="stat-label">Agents</span>
		</div>
		<div class="stat">
			<span class="stat-value">{honeypotCount}</span>
			<span class="stat-label">Honeypots</span>
		</div>
		<div class="stat">
			<span class="stat-value">{engagedCount}</span>
			<span class="stat-label">Engaged</span>
		</div>
		<div class="stat">
			<span class="stat-value">{fingerprintsCaptured}</span>
			<span class="stat-label">Fingerprints</span>
		</div>
		<div class="stat evolution">
			<span class="stat-value">{evolutionStats?.defense_effectiveness ?? '60%'}</span>
			<span class="stat-label">Defense</span>
		</div>
		<div class="stat evolution">
			<span class="stat-value">{evolutionStats?.improvement_since_start ?? '+0%'}</span>
			<span class="stat-label">Learned</span>
		</div>
	</div>

	<!-- Tech Stack Banner -->
	<div class="tech-banner">
		<div class="tech-section aws">
			<img src="https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg" alt="AWS" class="tech-logo" />
			<div class="tech-items">
				<span class="tech-badge strands">Strands</span>
				<span class="tech-desc">Agents</span>
				<span class="tech-badge s3">S3 Vectors</span>
				<span class="tech-desc">Fingerprints</span>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section auth0">
			<img src="https://cdn.auth0.com/website/bob/press/logo-light.png" alt="Auth0" class="tech-logo auth0-logo" />
			<div class="tech-items">
				<span class="tech-badge jwt">JWT</span>
				<span class="tech-desc">Identity</span>
				<span class="tech-badge fga">FGA</span>
				<span class="tech-desc">Routing</span>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section tinyfish">
			<span class="tech-logo-text tinyfish-text">TinyFish</span>
			<div class="tech-items">
				<span class="tech-badge agentql">AgentQL</span>
				<span class="tech-desc">Semantic detection</span>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section cline">
			<span class="tech-logo-text cline-text">Cline</span>
			<div class="tech-items">
				<span class="tech-badge cline-badge">CLI</span>
				<span class="tech-desc">Code variation</span>
			</div>
		</div>
	</div>

	<div class="main-content">
		<!-- Honeycomb Visualization -->
		<div class="hive-container">
			<h2>Swarm View</h2>
			{#if agents.length === 0}
				<p class="hint">Press PLAY DEMO to begin...</p>
			{:else}
				<p class="hint">Attackers can't tell which are real and which are honeypots</p>
			{/if}

			<div class="honeycomb-area">
				<!-- Agents -->
				{#each agents as agent (agent.id)}
					<div
						class="hex-cell"
						class:spawning={agent.spawned}
						class:engaged={agent.engaged}
						class:targeted={agent.targeted}
						class:honeypot={agent.is_honeypot}
						class:responding={agent.responding}
						style="left: {agent.x}px; top: {agent.y}px;"
						title={agent.name}
					>
						<div class="hex-inner">
							<span class="hex-icon">{agent.is_honeypot ? 'H' : 'A'}</span>
							{#if agent.engaged}
								<span class="engaged-badge">!</span>
							{/if}
						</div>
						<span class="agent-label">{agent.name.split('-')[0]}</span>
					</div>
				{/each}

				<!-- Attacker -->
				{#if attackerVisible}
					<div
						class="attacker-node"
						style="left: {attackerPosition.x}px; top: {attackerPosition.y}px;"
					>
						<div class="attacker-inner">
							<span class="attacker-icon">X</span>
						</div>
						<span class="attacker-label">ATTACKER</span>
					</div>
				{/if}

				<!-- Legitimate Agent -->
				{#if legitimateVisible}
					<div
						class="legitimate-node"
						style="left: {legitimatePosition.x}px; top: {legitimatePosition.y}px;"
					>
						<div class="legitimate-inner">
							<span class="legitimate-icon">✓</span>
						</div>
						<span class="legitimate-label">AGENT</span>
					</div>
				{/if}
			</div>

			<!-- Routing Decision Panel -->
			{#if routingDecision}
				<div class="routing-panel" class:legitimate={routingDecision.actor === 'legitimate'}>
					<div class="routing-header">
						<img src="https://cdn.auth0.com/website/bob/press/logo-light.png" alt="Auth0" class="routing-logo" />
						<span class="routing-title">IDENTITY GATEWAY</span>
					</div>
					<div class="routing-checks">
						<div class="routing-check" class:pass={routingDecision.has_token} class:fail={!routingDecision.has_token}>
							<span class="check-icon">{routingDecision.has_token ? '✓' : '✗'}</span>
							<span>Auth0 JWT Present</span>
						</div>
						<div class="routing-check" class:pass={routingDecision.token_valid} class:fail={!routingDecision.token_valid}>
							<span class="check-icon">{routingDecision.token_valid ? '✓' : '✗'}</span>
							<span>M2M Token Valid</span>
						</div>
						<div class="routing-check" class:pass={routingDecision.fga_allowed} class:fail={!routingDecision.fga_allowed}>
							<span class="check-icon">{routingDecision.fga_allowed ? '✓' : '✗'}</span>
							<span>Auth0 FGA Allowed</span>
						</div>
					</div>
					<div class="routing-decision-text" class:honeypot={routingDecision.decision.includes('HONEYPOT')} class:real={routingDecision.decision.includes('REAL')}>
						{routingDecision.decision}
					</div>
					<div class="routing-reason">{routingDecision.reason}</div>
				</div>
			{/if}

			<!-- Legend -->
			<div class="legend">
				<div class="legend-item">
					<div class="legend-hex agent"></div>
					<span>Real Agent</span>
				</div>
				<div class="legend-item">
					<div class="legend-hex honeypot"></div>
					<span>Honeypot</span>
				</div>
				<div class="legend-item">
					<div class="legend-hex engaged"></div>
					<span>Engaged</span>
				</div>
				<div class="legend-item">
					<div class="legend-hex attacker"></div>
					<span>Attacker</span>
				</div>
				<div class="legend-item">
					<div class="legend-hex legitimate"></div>
					<span>Legitimate</span>
				</div>
			</div>
		</div>

		<!-- Activity Log -->
		<div class="log-panel">
			<h2>Activity Log</h2>
			<div class="log-stream">
				{#if logs.length === 0}
					<div class="log-empty">Waiting for demo to start...</div>
				{:else}
					{#each logs as log (log.id)}
						<div class="log-entry {log.type}">
							<span class="log-message">{log.message}</span>
							{#if log.detail}
								<div class="log-detail">{log.detail}</div>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	/* ============================================================
	   DESIGN SYSTEM: Warm Glassmorphism + Organic Honeycomb
	   Theme: "Protective Elegance" - security that feels safe
	   ============================================================ */

	:root {
		/* Warm Dark Base - charcoal with brown undertones */
		--bg-deep: #0f0d0a;
		--bg-surface: #1a1714;
		--bg-elevated: #242019;
		--bg-overlay: rgba(26, 23, 20, 0.85);

		/* Honey Amber Palette */
		--honey-50: #fffbeb;
		--honey-100: #fef3c7;
		--honey-200: #fde68a;
		--honey-300: #fcd34d;
		--honey-400: #fbbf24;
		--honey-500: #f59e0b;
		--honey-600: #d97706;
		--honey-700: #b45309;
		--honey-800: #92400e;
		--honey-900: #78350f;

		/* Semantic Colors */
		--safe: #4ade80;
		--safe-glow: rgba(74, 222, 128, 0.3);
		--warning: #fbbf24;
		--warning-glow: rgba(251, 191, 36, 0.4);
		--danger: #f87171;
		--danger-glow: rgba(248, 113, 113, 0.4);
		--info: #60a5fa;
		--info-glow: rgba(96, 165, 250, 0.3);

		/* Text */
		--text-primary: #faf5ef;
		--text-secondary: #c4b8a8;
		--text-muted: #8b7e6e;

		/* Glassmorphism */
		--glass-bg: rgba(26, 23, 20, 0.6);
		--glass-border: rgba(245, 158, 11, 0.15);
		--glass-highlight: rgba(253, 230, 138, 0.08);
		--glass-blur: 16px;

		/* Shadows - warm tinted */
		--shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
		--shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
		--shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
		--shadow-glow: 0 0 40px rgba(245, 158, 11, 0.15);

		/* Transitions */
		--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
		--ease-out-back: cubic-bezier(0.34, 1.56, 0.64, 1);

		/* Spacing */
		--radius-sm: 8px;
		--radius-md: 12px;
		--radius-lg: 20px;
		--radius-xl: 28px;
	}

	:global(body) {
		margin: 0;
		padding: 0;
		background: var(--bg-deep);
		color: var(--text-primary);
		font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif;
		-webkit-font-smoothing: antialiased;
		overflow-x: hidden;
	}

	/* Animated honeycomb background */
	:global(body)::before {
		content: '';
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100'%3E%3Cpath d='M28 66L0 50L0 16L28 0L56 16L56 50L28 66L28 100' fill='none' stroke='%23f59e0b' stroke-opacity='0.04' stroke-width='1'/%3E%3Cpath d='M28 0L28 34L0 50L0 84L28 100L56 84L56 50L28 34' fill='none' stroke='%23f59e0b' stroke-opacity='0.02' stroke-width='1'/%3E%3C/svg%3E");
		background-size: 56px 100px;
		pointer-events: none;
		z-index: 0;
		animation: bgFloat 60s linear infinite;
	}

	@keyframes bgFloat {
		0% { background-position: 0 0; }
		100% { background-position: 56px 100px; }
	}

	/* Warm radial glow overlay */
	:global(body)::after {
		content: '';
		position: fixed;
		top: 50%;
		left: 50%;
		width: 150vw;
		height: 150vh;
		transform: translate(-50%, -50%);
		background: radial-gradient(ellipse at center, rgba(245, 158, 11, 0.06) 0%, transparent 50%);
		pointer-events: none;
		z-index: 0;
	}

	.dashboard {
		position: relative;
		z-index: 1;
		min-height: 100vh;
		padding: 1.5rem 2rem;
	}

	/* ============================================================
	   HEADER - Glassmorphism with warm glow
	   ============================================================ */

	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1.25rem 2rem;
		background: var(--glass-bg);
		backdrop-filter: blur(var(--glass-blur));
		-webkit-backdrop-filter: blur(var(--glass-blur));
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-lg);
		margin-bottom: 1.5rem;
		box-shadow: var(--shadow-md), var(--shadow-glow);
		position: relative;
		overflow: hidden;
	}

	/* Subtle top highlight */
	header::before {
		content: '';
		position: absolute;
		top: 0;
		left: 10%;
		right: 10%;
		height: 1px;
		background: linear-gradient(90deg, transparent, var(--honey-400), transparent);
		opacity: 0.5;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	h1 {
		margin: 0;
		font-size: 1.75rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		background: linear-gradient(135deg, var(--honey-300), var(--honey-500), var(--honey-600));
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
		filter: drop-shadow(0 2px 8px rgba(245, 158, 11, 0.3));
	}

	.phase-badge {
		padding: 0.5rem 1rem;
		border-radius: var(--radius-md);
		font-size: 0.8rem;
		font-weight: 600;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--bg-deep);
		box-shadow: var(--shadow-sm);
		transition: all 0.3s var(--ease-out-expo);
	}

	.threat-indicator {
		padding: 0.6rem 1.25rem;
		border-radius: var(--radius-xl);
		font-size: 0.85rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		color: var(--bg-deep);
		box-shadow: var(--shadow-sm);
		animation: gentlePulse 3s ease-in-out infinite;
	}

	@keyframes gentlePulse {
		0%, 100% {
			opacity: 1;
			transform: scale(1);
		}
		50% {
			opacity: 0.85;
			transform: scale(1.02);
		}
	}

	/* ============================================================
	   DEMO CONTROLS - Elevated glass card
	   ============================================================ */

	.demo-controls {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		padding: 1.25rem 1.5rem;
		background: var(--glass-bg);
		backdrop-filter: blur(var(--glass-blur));
		-webkit-backdrop-filter: blur(var(--glass-blur));
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-md);
		margin-bottom: 1.5rem;
		box-shadow: var(--shadow-sm);
	}

	.demo-btn {
		padding: 0.875rem 2.25rem;
		border: none;
		border-radius: var(--radius-md);
		font-size: 1rem;
		font-weight: 600;
		letter-spacing: 0.03em;
		cursor: pointer;
		transition: all 0.3s var(--ease-out-expo);
		position: relative;
		overflow: hidden;
	}

	.demo-btn::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 50%;
		background: linear-gradient(to bottom, rgba(255,255,255,0.15), transparent);
		pointer-events: none;
	}

	.demo-btn.play {
		background: linear-gradient(135deg, var(--safe), #22c55e);
		color: white;
		box-shadow: 0 4px 16px var(--safe-glow);
	}

	.demo-btn.play:hover {
		transform: translateY(-2px) scale(1.02);
		box-shadow: 0 8px 24px var(--safe-glow);
	}

	.demo-btn.play:active {
		transform: translateY(0) scale(0.98);
	}

	.demo-btn.stop {
		background: linear-gradient(135deg, var(--danger), #ef4444);
		color: white;
		box-shadow: 0 4px 16px var(--danger-glow);
	}

	.demo-btn.stop:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 24px var(--danger-glow);
	}

	.demo-btn.reset {
		background: var(--bg-elevated);
		color: var(--text-secondary);
		border: 1px solid var(--glass-border);
	}

	.demo-btn.reset:hover {
		background: var(--bg-surface);
		color: var(--text-primary);
		border-color: var(--honey-600);
	}

	.demo-status {
		color: var(--text-muted);
		font-size: 0.9rem;
		font-style: italic;
	}

	.demo-status.complete {
		color: var(--safe);
		font-weight: 600;
		font-style: normal;
	}

	.demo-mode {
		padding: 0.4rem 0.8rem;
		border-radius: var(--radius-sm);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.demo-mode.live {
		background: linear-gradient(135deg, #22c55e, #16a34a);
		color: white;
		box-shadow: 0 0 12px rgba(34, 197, 94, 0.5);
		animation: livePulse 1.5s ease-in-out infinite;
	}

	@keyframes livePulse {
		0%, 100% {
			box-shadow: 0 0 12px rgba(34, 197, 94, 0.5);
		}
		50% {
			box-shadow: 0 0 20px rgba(34, 197, 94, 0.8);
		}
	}

	.demo-mode.scripted {
		background: var(--bg-elevated);
		color: var(--text-muted);
		border: 1px solid var(--glass-border);
	}

	/* ============================================================
	   STATS BAR - Floating glass cards
	   ============================================================ */

	.stats-bar {
		display: flex;
		gap: 1rem;
		justify-content: center;
		padding: 0;
		background: transparent;
		margin-bottom: 1.5rem;
	}

	.stat {
		flex: 1;
		max-width: 180px;
		text-align: center;
		padding: 1.25rem 1rem;
		background: var(--glass-bg);
		backdrop-filter: blur(var(--glass-blur));
		-webkit-backdrop-filter: blur(var(--glass-blur));
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-md);
		box-shadow: var(--shadow-sm);
		transition: all 0.3s var(--ease-out-expo);
	}

	.stat:hover {
		transform: translateY(-4px);
		box-shadow: var(--shadow-md), 0 0 20px rgba(245, 158, 11, 0.1);
		border-color: rgba(245, 158, 11, 0.3);
	}

	.stat-value {
		display: block;
		font-size: 2.25rem;
		font-weight: 700;
		background: linear-gradient(135deg, var(--honey-400), var(--honey-600));
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
		line-height: 1.2;
	}

	.stat-label {
		font-size: 0.8rem;
		font-weight: 500;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--text-muted);
		margin-top: 0.25rem;
	}

	/* Evolution stats - green theme */
	.stat.evolution {
		border-color: rgba(74, 222, 128, 0.3);
		animation: evolutionPulse 2s ease-in-out infinite;
	}

	.stat.evolution .stat-value {
		background: linear-gradient(135deg, #4ade80, #22c55e);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	@keyframes evolutionPulse {
		0%, 100% {
			box-shadow: var(--shadow-sm), 0 0 10px rgba(74, 222, 128, 0.1);
		}
		50% {
			box-shadow: var(--shadow-sm), 0 0 20px rgba(74, 222, 128, 0.2);
		}
	}

	/* Tech Stack Banner */
	.tech-banner {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 2rem;
		padding: 1rem 2rem;
		background: linear-gradient(135deg, rgba(0, 0, 0, 0.4), rgba(20, 20, 20, 0.6));
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: var(--radius-md);
		margin-bottom: 1.5rem;
	}

	.tech-section {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.tech-logo {
		height: 28px;
		width: auto;
		filter: brightness(1.1);
	}

	.tech-logo.auth0-logo {
		height: 24px;
	}

	.tech-items {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.tech-badge {
		padding: 0.3rem 0.6rem;
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		border-radius: 4px;
		text-transform: uppercase;
	}

	.tech-badge.strands {
		background: linear-gradient(135deg, #ff9900, #ffb84d);
		color: #232f3e;
	}

	.tech-badge.s3 {
		background: linear-gradient(135deg, #3b82f6, #60a5fa);
		color: #fff;
	}

	.tech-badge.jwt {
		background: linear-gradient(135deg, #eb5424, #ff7043);
		color: #fff;
	}

	.tech-badge.fga {
		background: linear-gradient(135deg, #635bff, #8b7fff);
		color: #fff;
	}

	.tech-badge.agentql {
		background: linear-gradient(135deg, #06b6d4, #22d3ee);
		color: #0e1111;
	}

	.tech-badge.cline-badge {
		background: linear-gradient(135deg, #10b981, #34d399);
		color: #0e1111;
	}

	.tech-logo-text {
		font-size: 0.9rem;
		font-weight: 700;
		letter-spacing: 0.02em;
	}

	.tinyfish-text {
		color: #22d3ee;
	}

	.cline-text {
		color: #34d399;
	}

	.tech-desc {
		color: var(--text-muted);
		font-size: 0.75rem;
	}

	.tech-divider {
		width: 1px;
		height: 40px;
		background: rgba(255, 255, 255, 0.15);
	}

	/* Main Content */
	.main-content {
		display: grid;
		grid-template-columns: 1fr 450px;
		gap: 1.5rem;
		height: calc(100vh - 280px);
	}

	/* Honeycomb */
	.hive-container {
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		padding: 1.5rem;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.hive-container h2 {
		margin: 0 0 0.5rem 0;
		color: #f59e0b;
		font-size: 1.3rem;
		text-align: center;
	}

	.hint {
		color: #777;
		font-style: italic;
		margin: 0 0 1rem 0;
		text-align: center;
	}

	.honeycomb-area {
		position: relative;
		height: 450px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: radial-gradient(circle at center, rgba(245, 158, 11, 0.08) 0%, transparent 70%);
	}

	.hex-cell {
		position: absolute;
		width: 90px;
		height: 100px;
		transition: all 0.5s ease;
		animation: spawnIn 0.5s ease-out;
	}

	@keyframes spawnIn {
		from {
			transform: scale(0);
			opacity: 0;
		}
		to {
			transform: scale(1);
			opacity: 1;
		}
	}

	.hex-inner {
		width: 100%;
		height: 100%;
		background: #f59e0b;
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		position: relative;
	}

	.hex-cell.honeypot .hex-inner {
		background: #f59e0b;
	}

	.hex-cell.targeted .hex-inner {
		background: #eab308;
		animation: targetPulse 0.5s infinite;
	}

	@keyframes targetPulse {
		0%,
		100% {
			box-shadow: 0 0 10px #eab308;
		}
		50% {
			box-shadow: 0 0 30px #eab308, 0 0 50px #f59e0b;
		}
	}

	.hex-cell.engaged .hex-inner {
		background: #ef4444;
		animation: engagedGlow 1s infinite alternate;
	}

	@keyframes engagedGlow {
		from {
			box-shadow: 0 0 10px #ef4444;
		}
		to {
			box-shadow: 0 0 30px #ef4444, 0 0 50px #dc2626;
		}
	}

	.hex-icon {
		font-size: 1.5rem;
		font-weight: bold;
		color: #1a1408;
	}

	.engaged-badge {
		position: absolute;
		top: -5px;
		right: -5px;
		width: 20px;
		height: 20px;
		background: #ef4444;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.8rem;
		font-weight: bold;
		color: white;
		animation: bounce 0.5s infinite alternate;
	}

	@keyframes bounce {
		from {
			transform: scale(1);
		}
		to {
			transform: scale(1.2);
		}
	}

	.agent-label {
		position: absolute;
		bottom: -22px;
		left: 50%;
		transform: translateX(-50%);
		font-size: 0.8rem;
		color: #aaa;
		white-space: nowrap;
	}

	/* Attacker */
	.attacker-node {
		position: absolute;
		width: 60px;
		height: 60px;
		transition: all 1s ease;
		z-index: 100;
	}

	.attacker-inner {
		width: 100%;
		height: 100%;
		background: #ef4444;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		animation: attackerPulse 0.5s infinite;
		box-shadow: 0 0 20px #ef4444;
	}

	@keyframes attackerPulse {
		0%,
		100% {
			transform: scale(1);
			box-shadow: 0 0 20px #ef4444;
		}
		50% {
			transform: scale(1.1);
			box-shadow: 0 0 40px #ef4444, 0 0 60px #dc2626;
		}
	}

	.attacker-icon {
		font-size: 1.5rem;
		font-weight: bold;
		color: white;
	}

	.attacker-label {
		position: absolute;
		bottom: -20px;
		left: 50%;
		transform: translateX(-50%);
		font-size: 0.7rem;
		color: #ef4444;
		font-weight: bold;
		white-space: nowrap;
	}

	/* Legend */
	.legend {
		display: flex;
		gap: 2rem;
		margin-top: 1rem;
		padding: 1rem;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 4px;
		justify-content: center;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.95rem;
		color: #aaa;
	}

	.legend-hex {
		width: 24px;
		height: 28px;
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
	}

	.legend-hex.agent {
		background: #f59e0b;
	}
	.legend-hex.honeypot {
		background: #f59e0b;
	}
	.legend-hex.engaged {
		background: #ef4444;
	}
	.legend-hex.attacker {
		background: #ef4444;
		border-radius: 50%;
		clip-path: none;
	}

	/* Log Panel */
	.log-panel {
		background: rgba(0, 0, 0, 0.5);
		border-radius: 8px;
		padding: 1.25rem;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.log-panel h2 {
		margin: 0 0 1rem 0;
		color: #f59e0b;
		font-size: 1.3rem;
	}

	.log-stream {
		flex: 1;
		overflow-y: auto;
		font-family: 'Fira Code', 'Consolas', monospace;
		font-size: 1rem;
		line-height: 1.5;
	}

	.log-empty {
		color: #666;
		text-align: center;
		padding: 2rem;
		font-size: 1.1rem;
	}

	.log-entry {
		padding: 1rem;
		margin-bottom: 0.5rem;
		border-radius: 8px;
		animation: fadeIn 0.3s ease;
		border-left: 4px solid;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateX(-10px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	/* Log type styles - cleaner narrative look */
	.log-entry.system {
		background: rgba(107, 114, 128, 0.15);
		border-left-color: #6b7280;
	}
	.log-entry.system .log-message {
		color: #9ca3af;
	}

	.log-entry.alert {
		background: rgba(239, 68, 68, 0.15);
		border-left-color: #ef4444;
	}
	.log-entry.alert .log-message {
		color: #fca5a5;
		font-weight: 600;
	}

	.log-entry.phase {
		background: rgba(139, 92, 246, 0.15);
		border-left-color: #8b5cf6;
	}
	.log-entry.phase .log-message {
		color: #c4b5fd;
		font-weight: 600;
		font-size: 1.1rem;
	}

	.log-entry.attacker {
		background: rgba(239, 68, 68, 0.1);
		border-left-color: #f87171;
	}
	.log-entry.attacker .log-message {
		color: #fecaca;
		font-style: italic;
	}

	.log-entry.honeypot {
		background: rgba(251, 191, 36, 0.1);
		border-left-color: #fbbf24;
	}
	.log-entry.honeypot .log-message {
		color: #fde68a;
	}

	.log-entry.captured {
		background: rgba(34, 197, 94, 0.15);
		border-left-color: #22c55e;
	}
	.log-entry.captured .log-message {
		color: #86efac;
		font-weight: 600;
	}

	.log-message {
		color: #e5e5e5;
		font-size: 1rem;
		line-height: 1.5;
	}

	.log-detail {
		margin-top: 0.5rem;
		padding-top: 0.5rem;
		color: #a3a3a3;
		font-size: 0.9rem;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
		line-height: 1.4;
	}

	/* ============================================================
	   NEW: Legitimate Agent Node
	   ============================================================ */

	.legitimate-node {
		position: absolute;
		width: 60px;
		height: 60px;
		transition: all 1s ease;
		z-index: 100;
	}

	.legitimate-inner {
		width: 100%;
		height: 100%;
		background: #22c55e;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		animation: legitimatePulse 1.5s infinite;
		box-shadow: 0 0 20px #22c55e;
	}

	@keyframes legitimatePulse {
		0%, 100% {
			transform: scale(1);
			box-shadow: 0 0 20px #22c55e;
		}
		50% {
			transform: scale(1.05);
			box-shadow: 0 0 30px #22c55e, 0 0 50px #16a34a;
		}
	}

	.legitimate-icon {
		font-size: 1.5rem;
		font-weight: bold;
		color: white;
	}

	.legitimate-label {
		position: absolute;
		bottom: -20px;
		left: 50%;
		transform: translateX(-50%);
		font-size: 0.7rem;
		color: #22c55e;
		font-weight: bold;
		white-space: nowrap;
	}

	/* ============================================================
	   NEW: Responding Agent (real agent processing legitimate request)
	   ============================================================ */

	.hex-cell.responding .hex-inner {
		background: #22c55e;
		animation: respondingGlow 0.8s infinite alternate;
	}

	@keyframes respondingGlow {
		from {
			box-shadow: 0 0 15px #22c55e;
		}
		to {
			box-shadow: 0 0 35px #22c55e, 0 0 55px #16a34a;
		}
	}

	/* ============================================================
	   NEW: Routing Decision Panel
	   ============================================================ */

	.routing-panel {
		position: absolute;
		top: 10px;
		right: 10px;
		background: rgba(0, 0, 0, 0.85);
		border: 2px solid #ef4444;
		border-radius: 12px;
		padding: 1rem;
		min-width: 200px;
		animation: slideIn 0.3s ease-out;
		z-index: 200;
	}

	.routing-panel.legitimate {
		border-color: #22c55e;
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateX(20px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	.routing-header {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	.routing-logo {
		height: 18px;
		width: auto;
	}

	.routing-title {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		color: #eb5424;
	}

	.routing-checks {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}

	.routing-check {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		background: rgba(255, 255, 255, 0.05);
	}

	.routing-check.pass {
		color: #86efac;
	}

	.routing-check.fail {
		color: #fca5a5;
	}

	.check-icon {
		font-weight: bold;
		width: 1.2rem;
		text-align: center;
	}

	.routing-decision-text {
		font-size: 1rem;
		font-weight: 700;
		text-align: center;
		padding: 0.5rem;
		border-radius: 6px;
		margin-bottom: 0.5rem;
	}

	.routing-decision-text.honeypot {
		background: rgba(251, 191, 36, 0.2);
		color: #fde68a;
	}

	.routing-decision-text.real {
		background: rgba(34, 197, 94, 0.2);
		color: #86efac;
	}

	.routing-reason {
		font-size: 0.75rem;
		color: #9ca3af;
		text-align: center;
		font-style: italic;
	}

	/* ============================================================
	   NEW: Additional Log Entry Styles
	   ============================================================ */

	.log-entry.routing {
		background: rgba(96, 165, 250, 0.15);
		border-left-color: #60a5fa;
	}
	.log-entry.routing .log-message {
		color: #93c5fd;
		font-weight: 600;
	}

	.log-entry.legitimate {
		background: rgba(34, 197, 94, 0.1);
		border-left-color: #22c55e;
	}
	.log-entry.legitimate .log-message {
		color: #86efac;
		font-style: italic;
	}

	.log-entry.success {
		background: rgba(34, 197, 94, 0.15);
		border-left-color: #22c55e;
	}
	.log-entry.success .log-message {
		color: #86efac;
	}

	.log-entry.result {
		background: rgba(139, 92, 246, 0.1);
		border-left-color: #a78bfa;
	}
	.log-entry.result .log-message {
		color: #c4b5fd;
		font-weight: 600;
	}

	/* ============================================================
	   SPONSOR: TinyFish Log Entries
	   ============================================================ */

	.log-entry.tinyfish {
		background: rgba(6, 182, 212, 0.15);
		border-left-color: #06b6d4;
	}
	.log-entry.tinyfish .log-message {
		color: #22d3ee;
		font-weight: 600;
	}
	.log-entry.tinyfish .log-message::before {
		content: '[TinyFish] ';
		color: #67e8f9;
		font-weight: 700;
	}

	/* ============================================================
	   SPONSOR: Cline Log Entries
	   ============================================================ */

	.log-entry.cline {
		background: rgba(16, 185, 129, 0.15);
		border-left-color: #10b981;
	}
	.log-entry.cline .log-message {
		color: #34d399;
		font-weight: 600;
	}
	.log-entry.cline .log-message::before {
		content: '[Cline] ';
		color: #6ee7b7;
		font-weight: 700;
	}

	/* ============================================================
	   NEW: Legend Item for Legitimate
	   ============================================================ */

	.legend-hex.legitimate {
		background: #22c55e;
		border-radius: 50%;
		clip-path: none;
	}
</style>
