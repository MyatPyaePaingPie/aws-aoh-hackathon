<script lang="ts">
	import { onMount } from 'svelte';
	import {
		connectToDemo,
		stopDemo,
		type DemoAgent,
		type PhaseChangeEvent
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
	let attackerTargetId = $state<string | null>(null);

	// Phase & threat
	let currentPhase = $state<PhaseChangeEvent | null>(null);
	let threatLevel = $state<string>('NONE');

	// Activity log
	interface LogEntry {
		id: number;
		time: string;
		type: 'info' | 'attack' | 'engage' | 'fingerprint' | 'phase';
		message: string;
		detail?: string;
	}
	let logs = $state<LogEntry[]>([]);
	let logId = 0;

	// Stats
	let fingerprintsCapturered = $state(0);

	// ============================================================
	// HELPERS
	// ============================================================

	function addLog(type: LogEntry['type'], message: string, detail?: string) {
		const time = new Date().toLocaleTimeString('en-US', { hour12: false });
		logs = [{ id: ++logId, time, type, message, detail }, ...logs].slice(0, 50);
	}

	function getHexPosition(index: number, total: number): { x: number; y: number } {
		// Arrange in a honeycomb pattern
		const cols = 3;
		const row = Math.floor(index / cols);
		const col = index % cols;
		const offsetX = row % 2 === 1 ? 50 : 0; // Offset odd rows
		return {
			x: 100 + col * 100 + offsetX,
			y: 100 + row * 90
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
		fingerprintsCapturered = 0;
		demoRunning = true;

		addLog('info', 'Demo starting...');

		eventSource = connectToDemo({
			onStart: (data) => {
				addLog('info', `Initializing ${data.total_agents} agents...`);
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
				addLog('info', `Agent spawned: ${data.agent.name}`);
			},

			onAttackerSpawn: () => {
				attackerVisible = true;
				attackerPosition = { x: 50, y: 20 };
				addLog('attack', 'ATTACKER DETECTED', 'Unknown agent entering the network');
			},

			onPhaseChange: (data) => {
				currentPhase = data;
				threatLevel = data.threat_level;
				addLog('phase', `Phase: ${data.phase_name}`, `Threat level: ${data.threat_level}`);
			},

			onAttackerMove: (data) => {
				attackerTargetId = data.target_agent_id;
				// Find target agent position
				const target = agents.find((a) => a.id === data.target_agent_id);
				if (target) {
					attackerPosition = { x: target.x - 30, y: target.y - 30 };
					// Mark target
					agents = agents.map((a) => ({
						...a,
						targeted: a.id === data.target_agent_id
					}));
				}
				addLog('attack', `Attacker approaching ${data.target_name}`);
			},

			onAttackStart: (data) => {
				addLog('attack', data.attack_name, `"${data.prompt.slice(0, 60)}..."`);
			},

			onHoneypotEngage: (data) => {
				// Mark agent as engaged
				agents = agents.map((a) => ({
					...a,
					engaged: a.id === data.agent_id ? true : a.engaged,
					targeted: false
				}));
				addLog('engage', `HONEYPOT ENGAGED: ${data.agent_name}`, data.response.slice(0, 100));
			},

			onFingerprintCaptured: (data) => {
				fingerprintsCapturered++;
				addLog(
					'fingerprint',
					`Fingerprint captured: ${data.attack_name}`,
					`Techniques: ${data.techniques.join(', ')}`
				);
			},

			onComplete: (data) => {
				demoRunning = false;
				demoComplete = true;
				addLog(
					'info',
					'DEMO COMPLETE',
					`${data.attacks_executed} attacks, ${data.fingerprints_captured} fingerprints`
				);
			},

			onError: () => {
				addLog('info', 'Connection lost. Demo may have ended.');
				demoRunning = false;
			}
		});
	}

	async function handleStopDemo() {
		await stopDemo();
		eventSource?.close();
		demoRunning = false;
		addLog('info', 'Demo stopped');
	}

	function resetDemo() {
		agents = [];
		logs = [];
		attackerVisible = false;
		currentPhase = null;
		threatLevel = 'NONE';
		demoComplete = false;
		fingerprintsCapturered = 0;
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
					{currentPhase.phase_name}
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
			<span class="stat-value">{fingerprintsCapturered}</span>
			<span class="stat-label">Fingerprints</span>
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
							<span class="log-time">{log.time}</span>
							<span class="log-type">[{log.type.toUpperCase()}]</span>
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
	:global(body) {
		margin: 0;
		padding: 0;
		background: #0d0d0d;
		color: #f5f5f5;
		font-family: 'Segoe UI', system-ui, sans-serif;
	}

	.dashboard {
		min-height: 100vh;
		padding: 1rem;
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 2rem;
		background: rgba(245, 158, 11, 0.1);
		border-bottom: 2px solid #f59e0b;
		margin-bottom: 1rem;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	h1 {
		margin: 0;
		color: #f59e0b;
		font-size: 1.8rem;
		text-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
	}

	.phase-badge {
		padding: 0.4rem 0.8rem;
		border-radius: 4px;
		font-size: 0.85rem;
		font-weight: bold;
		color: #000;
	}

	.threat-indicator {
		padding: 0.5rem 1rem;
		border-radius: 20px;
		font-weight: bold;
		color: #000;
		animation: pulse 2s infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}

	/* Demo Controls */
	.demo-controls {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1rem;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		margin-bottom: 1rem;
	}

	.demo-btn {
		padding: 0.75rem 2rem;
		border: none;
		border-radius: 8px;
		font-size: 1.1rem;
		font-weight: bold;
		cursor: pointer;
		transition: all 0.2s;
	}

	.demo-btn.play {
		background: linear-gradient(135deg, #22c55e, #16a34a);
		color: white;
	}

	.demo-btn.play:hover {
		transform: scale(1.05);
		box-shadow: 0 0 20px rgba(34, 197, 94, 0.5);
	}

	.demo-btn.stop {
		background: #ef4444;
		color: white;
	}

	.demo-btn.reset {
		background: #6b7280;
		color: white;
	}

	.demo-status {
		color: #888;
		font-style: italic;
	}

	.demo-status.complete {
		color: #22c55e;
		font-weight: bold;
	}

	/* Stats */
	.stats-bar {
		display: flex;
		gap: 2rem;
		justify-content: center;
		padding: 1rem;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		margin-bottom: 1rem;
	}

	.stat {
		text-align: center;
	}

	.stat-value {
		display: block;
		font-size: 2rem;
		font-weight: bold;
		color: #f59e0b;
	}

	.stat-label {
		font-size: 0.9rem;
		color: #888;
	}

	/* Main Content */
	.main-content {
		display: grid;
		grid-template-columns: 1fr 400px;
		gap: 1rem;
		height: calc(100vh - 280px);
	}

	/* Honeycomb */
	.hive-container {
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		padding: 1rem;
		overflow: hidden;
	}

	.hive-container h2 {
		margin: 0 0 0.5rem 0;
		color: #f59e0b;
	}

	.hint {
		color: #666;
		font-style: italic;
		margin: 0 0 1rem 0;
	}

	.honeycomb-area {
		position: relative;
		height: 400px;
		background: radial-gradient(circle at center, rgba(245, 158, 11, 0.05) 0%, transparent 70%);
	}

	.hex-cell {
		position: absolute;
		width: 70px;
		height: 80px;
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
		font-size: 1.2rem;
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
		bottom: -20px;
		left: 50%;
		transform: translateX(-50%);
		font-size: 0.7rem;
		color: #888;
		white-space: nowrap;
	}

	/* Attacker */
	.attacker-node {
		position: absolute;
		width: 50px;
		height: 50px;
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
		gap: 1.5rem;
		margin-top: 1rem;
		padding: 0.75rem;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 4px;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		color: #888;
	}

	.legend-hex {
		width: 20px;
		height: 23px;
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
		padding: 1rem;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.log-panel h2 {
		margin: 0 0 1rem 0;
		color: #f59e0b;
	}

	.log-stream {
		flex: 1;
		overflow-y: auto;
		font-family: 'Fira Code', 'Consolas', monospace;
		font-size: 0.85rem;
	}

	.log-empty {
		color: #666;
		text-align: center;
		padding: 2rem;
	}

	.log-entry {
		padding: 0.5rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		animation: fadeIn 0.3s ease;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(-10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.log-time {
		color: #666;
		margin-right: 0.5rem;
	}

	.log-type {
		font-weight: bold;
		margin-right: 0.5rem;
	}

	.log-entry.info .log-type {
		color: #6b7280;
	}
	.log-entry.attack .log-type {
		color: #ef4444;
	}
	.log-entry.engage .log-type {
		color: #f59e0b;
	}
	.log-entry.fingerprint .log-type {
		color: #3b82f6;
	}
	.log-entry.phase .log-type {
		color: #8b5cf6;
	}

	.log-message {
		color: #ccc;
	}

	.log-detail {
		margin-top: 0.25rem;
		padding-left: 1rem;
		color: #888;
		font-size: 0.8rem;
		border-left: 2px solid rgba(255, 255, 255, 0.1);
	}
</style>
