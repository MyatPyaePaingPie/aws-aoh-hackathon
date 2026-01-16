<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getAgentsStatus,
		getFingerprints,
		sendAgentRequest,
		ATTACK_PRESETS,
		type Agent,
		type Fingerprint,
		type AttackPresetKey
	} from '$lib/api';

	// State
	let agents = $state<Agent[]>([]);
	let fingerprints = $state<Fingerprint[]>([]);
	let selectedAgent = $state<Agent | null>(null);
	let isConnected = $state(false);
	let lastAttackResponse = $state<string | null>(null);
	let isAttacking = $state(false);

	// Demo fallback data
	const DEMO_AGENTS: Agent[] = [
		{ name: 'processor-001', type: 'real', description: 'Data processor', is_honeypot: false },
		{ name: 'processor-002', type: 'real', description: 'Data processor', is_honeypot: false },
		{ name: 'db-admin-001', type: 'honeypot', description: 'Database admin (trap)', is_honeypot: true },
		{ name: 'privileged-proc-001', type: 'honeypot', description: 'High-privilege processor (trap)', is_honeypot: true },
		{ name: 'api-gateway-001', type: 'honeypot', description: 'API gateway (trap)', is_honeypot: true },
		{ name: 'cred-manager-001', type: 'honeypot', description: 'Credential manager (trap)', is_honeypot: true }
	];

	// Computed
	let totalAgents = $derived(agents.length);
	let honeypotCount = $derived(agents.filter((a) => a.is_honeypot).length);
	let threatDetected = $derived(fingerprints.length > 0);

	// Fetch agents from API
	async function fetchAgents() {
		try {
			const data = await getAgentsStatus();
			agents = data.agents;
			isConnected = true;
		} catch {
			// Fallback to demo data
			agents = DEMO_AGENTS;
			isConnected = false;
		}
	}

	// Fetch fingerprints/logs from API
	async function fetchFingerprints() {
		try {
			const data = await getFingerprints();
			fingerprints = data.fingerprints;
		} catch {
			// Keep existing fingerprints on error
		}
	}

	// Send attack simulation
	async function simulateAttack(preset: AttackPresetKey) {
		isAttacking = true;
		lastAttackResponse = null;

		try {
			const attack = ATTACK_PRESETS[preset];
			const response = await sendAgentRequest(attack.message, attack.context);
			lastAttackResponse = response.response;

			// Refresh fingerprints after attack
			await fetchFingerprints();
		} catch {
			lastAttackResponse = 'Request acknowledged. Processing in background.';
		} finally {
			isAttacking = false;
		}
	}

	// Select agent for details
	function selectAgent(agent: Agent) {
		selectedAgent = selectedAgent?.name === agent.name ? null : agent;
	}

	// Format timestamp for display
	function formatTime(timestamp: string): string {
		try {
			const date = new Date(timestamp);
			return date.toLocaleTimeString('en-US', { hour12: false });
		} catch {
			return timestamp;
		}
	}

	// Lifecycle
	onMount(() => {
		// Initial fetch
		fetchAgents();
		fetchFingerprints();

		// Auto-poll fingerprints every 5 seconds
		const interval = setInterval(fetchFingerprints, 5000);

		return () => clearInterval(interval);
	});
</script>

<div class="dashboard">
	<header>
		<h1>HONEYAGENT HIVE</h1>
		<div class="header-right">
			<span class="connection-status" class:connected={isConnected}>
				{isConnected ? 'LIVE' : 'DEMO'}
			</span>
			<div class="status-badge" class:threat={threatDetected}>
				{threatDetected ? 'THREAT DETECTED' : 'ALL CLEAR'}
			</div>
		</div>
	</header>

	<div class="stats-bar">
		<div class="stat">
			<span class="stat-value">{totalAgents}</span>
			<span class="stat-label">Total Agents</span>
		</div>
		<div class="stat">
			<span class="stat-value">{honeypotCount}</span>
			<span class="stat-label">Honeypots</span>
		</div>
		<div class="stat">
			<span class="stat-value">{fingerprints.length}</span>
			<span class="stat-label">Attacks Logged</span>
		</div>
	</div>

	<!-- Attack Simulation Panel -->
	<div class="attack-panel">
		<h3>Attack Simulation</h3>
		<div class="attack-buttons">
			{#each Object.entries(ATTACK_PRESETS) as [key, preset]}
				<button
					class="attack-btn"
					onclick={() => simulateAttack(key as AttackPresetKey)}
					disabled={isAttacking}
				>
					{preset.label}
				</button>
			{/each}
		</div>
		{#if lastAttackResponse}
			<div class="attack-response">
				<strong>Agent Response:</strong>
				<p>{lastAttackResponse}</p>
			</div>
		{/if}
	</div>

	<div class="main-content">
		<div class="hive-container">
			<h2>Swarm View</h2>
			<p class="hint">You can't tell which are real and which are honeypots...</p>
			<div class="honeycomb">
				{#each agents as agent}
					<button
						class="hex-cell"
						class:selected={selectedAgent?.name === agent.name}
						onclick={() => selectAgent(agent)}
						title={agent.name}
					>
						<div class="hex-inner">
							<span class="hex-icon">B</span>
						</div>
					</button>
				{/each}
			</div>

			<!-- Agent Detail Panel -->
			{#if selectedAgent}
				<div class="agent-detail">
					<h3>{selectedAgent.name}</h3>
					<div class="detail-row">
						<span class="detail-label">Type:</span>
						<span class="detail-value" class:honeypot={selectedAgent.is_honeypot}>
							{selectedAgent.is_honeypot ? 'HONEYPOT' : 'REAL AGENT'}
						</span>
					</div>
					<div class="detail-row">
						<span class="detail-label">Description:</span>
						<span class="detail-value">{selectedAgent.description || 'No description'}</span>
					</div>
					<div class="detail-row">
						<span class="detail-label">Category:</span>
						<span class="detail-value">{selectedAgent.type}</span>
					</div>
				</div>
			{/if}
		</div>

		<div class="log-panel">
			<h2>Activity Log <span class="log-count">({fingerprints.length})</span></h2>
			<div class="log-stream">
				{#if fingerprints.length === 0}
					<div class="log-empty">No attacks logged yet. Try simulating one!</div>
				{:else}
					{#each [...fingerprints].reverse() as fp}
						<div class="log-entry fingerprint">
							<span class="log-time">{formatTime(fp.timestamp)}</span>
							<span class="log-type">[TRAP]</span>
							<span class="log-message">
								{fp.agent_id}: "{fp.attacker_message?.slice(0, 50)}..."
							</span>
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
		background: #1a1408;
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

	.connection-status {
		padding: 0.25rem 0.75rem;
		border-radius: 4px;
		font-size: 0.8rem;
		font-weight: bold;
		background: #6b7280;
		color: white;
	}

	.connection-status.connected {
		background: #22c55e;
	}

	.status-badge {
		padding: 0.5rem 1rem;
		border-radius: 20px;
		background: #22c55e;
		font-weight: bold;
	}

	.status-badge.threat {
		background: #ef4444;
		animation: pulse 1s infinite;
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

	/* Attack Panel */
	.attack-panel {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid #ef4444;
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1rem;
	}

	.attack-panel h3 {
		margin: 0 0 0.75rem 0;
		color: #ef4444;
		font-size: 1rem;
	}

	.attack-buttons {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.attack-btn {
		padding: 0.5rem 1rem;
		background: #ef4444;
		color: white;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		font-weight: bold;
		transition: all 0.2s;
	}

	.attack-btn:hover:not(:disabled) {
		background: #dc2626;
		transform: translateY(-1px);
	}

	.attack-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.attack-response {
		margin-top: 1rem;
		padding: 0.75rem;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 4px;
		font-size: 0.9rem;
	}

	.attack-response strong {
		color: #f59e0b;
	}

	.attack-response p {
		margin: 0.5rem 0 0 0;
		color: #ccc;
	}

	.main-content {
		display: grid;
		grid-template-columns: 1fr 350px;
		gap: 1rem;
		height: calc(100vh - 320px);
	}

	.hive-container {
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		padding: 1rem;
		overflow-y: auto;
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

	.honeycomb {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 10px;
		padding: 2rem;
	}

	.hex-cell {
		width: 80px;
		height: 92px;
		background: #f59e0b;
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.3s ease;
		cursor: pointer;
		border: none;
		padding: 0;
	}

	.hex-cell:hover {
		transform: scale(1.1);
		box-shadow: 0 0 30px rgba(245, 158, 11, 0.8);
	}

	.hex-cell.selected {
		background: #3b82f6;
		animation: glow 1s infinite alternate;
	}

	@keyframes glow {
		from {
			box-shadow: 0 0 10px #3b82f6;
		}
		to {
			box-shadow: 0 0 30px #3b82f6, 0 0 50px #2563eb;
		}
	}

	.hex-inner {
		width: 70px;
		height: 80px;
		background: #1a1408;
		clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.hex-icon {
		font-size: 1.5rem;
		font-weight: bold;
		color: #f59e0b;
	}

	/* Agent Detail Panel */
	.agent-detail {
		margin-top: 1rem;
		padding: 1rem;
		background: rgba(59, 130, 246, 0.1);
		border: 1px solid #3b82f6;
		border-radius: 8px;
	}

	.agent-detail h3 {
		margin: 0 0 0.75rem 0;
		color: #3b82f6;
	}

	.detail-row {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.detail-label {
		color: #888;
		min-width: 80px;
	}

	.detail-value {
		color: #ccc;
	}

	.detail-value.honeypot {
		color: #ef4444;
		font-weight: bold;
	}

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

	.log-count {
		font-size: 0.8rem;
		color: #888;
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
	}

	.log-time {
		color: #666;
		margin-right: 0.5rem;
	}

	.log-type {
		font-weight: bold;
		margin-right: 0.5rem;
		color: #eab308;
	}

	.log-message {
		color: #ccc;
	}
</style>
