<script lang="ts">
	import { onMount } from 'svelte';
	import {
		connectToDemo,
		stopDemo,
		type DemoAgent,
		type PhaseChangeEvent,
		type LogEvent,
		type EvolutionStats
	} from '$lib/api';

	// ============================================================
	// STATE
	// ============================================================

	// Demo state
	let demoRunning = $state(false);
	let demoComplete = $state(false);
	let eventSource: EventSource | null = $state(null);

	// Agents in the honeycomb
	interface VisualAgent extends DemoAgent {
		spawned: boolean;
		engaged: boolean;
		targeted: boolean;
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
	type LogType = 'system' | 'alert' | 'phase' | 'attacker' | 'honeypot' | 'captured';
	interface LogEntry {
		id: number;
		type: LogType;
		message: string;
		detail?: string;
	}
	let logs = $state<LogEntry[]>([]);
	let logId = 0;

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
		currentPhase = null;
		threatLevel = 'NONE';
		demoComplete = false;
		fingerprintsCaptured = 0;
		evolutionStats = null;
		demoRunning = true;

		eventSource = connectToDemo({
			onStart: () => {
				// Just visual feedback, log comes separately
			},

			onAgentSpawn: (data) => {
				const pos = getHexPosition(data.index, data.total);
				const newAgent: VisualAgent = {
					...data.agent,
					spawned: true,
					engaged: false,
					targeted: false,
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
		currentPhase = null;
		threatLevel = 'NONE';
		demoComplete = false;
		fingerprintsCaptured = 0;
		evolutionStats = null;
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
			<span class="demo-status">Demo running...</span>
		{:else}
			<button class="demo-btn play" onclick={startDemo}>REPLAY</button>
			<button class="demo-btn reset" onclick={resetDemo}>RESET</button>
			<span class="demo-status complete">Demo complete!</span>
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

	<!-- AWS Integration Banner -->
	<div class="aws-banner">
		<span class="aws-badge">AWS CloudWatch</span>
		<span class="aws-info">Metrics streaming to namespace: <code>HoneyAgent</code></span>
		<span class="aws-badge bedrock">Bedrock Intel</span>
		<span class="aws-info">Attack patterns indexed for semantic search</span>
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
			</div>

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

	/* AWS Integration Banner */
	.aws-banner {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1.5rem;
		background: linear-gradient(135deg, rgba(255, 153, 0, 0.1), rgba(35, 47, 62, 0.3));
		border: 1px solid rgba(255, 153, 0, 0.2);
		border-radius: var(--radius-md);
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
	}

	.aws-badge {
		padding: 0.35rem 0.75rem;
		background: linear-gradient(135deg, #ff9900, #ffb84d);
		color: #232f3e;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.03em;
		border-radius: 4px;
		text-transform: uppercase;
	}

	.aws-badge.bedrock {
		background: linear-gradient(135deg, #00a4ef, #4dc3ff);
	}

	.aws-info {
		color: var(--text-secondary);
		font-size: 0.85rem;
	}

	.aws-info code {
		background: rgba(255, 153, 0, 0.15);
		padding: 0.15rem 0.4rem;
		border-radius: 3px;
		font-family: 'Fira Code', monospace;
		color: #ffb84d;
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
</style>
