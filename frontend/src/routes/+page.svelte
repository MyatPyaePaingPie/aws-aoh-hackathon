<script>
	// Demo data - hardcoded for reliability
	let agents = $state([
		{ id: 'agent-001', type: 'real', status: 'active' },
		{ id: 'agent-002', type: 'real', status: 'active' },
		{ id: 'honeypot-001', type: 'honeypot', status: 'active' },
		{ id: 'honeypot-002', type: 'honeypot', status: 'engaged' },
		{ id: 'honeypot-003', type: 'honeypot', status: 'active' },
		{ id: 'honeypot-004', type: 'honeypot', status: 'active' }
	]);

	let logs = $state([
		{ time: '14:32:01', type: 'trap', message: 'honeypot-002 engaged by unknown agent' },
		{ time: '14:32:03', type: 'log', message: 'Credential request intercepted' },
		{ time: '14:32:05', type: 'trap', message: 'Fake credentials issued' },
		{ time: '14:32:08', type: 'fingerprint', message: 'Attack vector fingerprint saved' }
	]);

	let threatDetected = $state(true);

	// Computed stats
	let totalAgents = $derived(agents.length);
	let honeypotCount = $derived(agents.filter(a => a.type === 'honeypot').length);
	let engagedCount = $derived(agents.filter(a => a.status === 'engaged').length);
</script>

<div class="dashboard">
	<header>
		<h1>🍯 HONEYAGENT HIVE</h1>
		<div class="status-badge" class:threat={threatDetected}>
			{threatDetected ? '🔴 THREAT DETECTED' : '🟢 ALL CLEAR'}
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
			<span class="stat-value">{engagedCount}</span>
			<span class="stat-label">Traps Engaged</span>
		</div>
	</div>

	<div class="main-content">
		<div class="hive-container">
			<h2>Swarm View</h2>
			<p class="hint">You can't tell which are real and which are honeypots...</p>
			<div class="honeycomb">
				{#each agents as agent}
					<div
						class="hex-cell"
						class:engaged={agent.status === 'engaged'}
						class:threat={agent.status === 'threat'}
					>
						<div class="hex-inner">
							<span class="hex-icon">🐝</span>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<div class="log-panel">
			<h2>Activity Log</h2>
			<div class="log-stream">
				{#each logs as log}
					<div class="log-entry {log.type}">
						<span class="log-time">{log.time}</span>
						<span class="log-type">[{log.type.toUpperCase()}]</span>
						<span class="log-message">{log.message}</span>
					</div>
				{/each}
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

	h1 {
		margin: 0;
		color: #f59e0b;
		font-size: 1.8rem;
		text-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
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
		0%, 100% { opacity: 1; }
		50% { opacity: 0.7; }
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

	.main-content {
		display: grid;
		grid-template-columns: 1fr 350px;
		gap: 1rem;
		height: calc(100vh - 200px);
	}

	.hive-container {
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
		padding: 1rem;
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
	}

	.hex-cell:hover {
		transform: scale(1.1);
		box-shadow: 0 0 30px rgba(245, 158, 11, 0.8);
	}

	.hex-cell.engaged {
		background: #fbbf24;
		animation: glow 1s infinite alternate;
	}

	.hex-cell.threat {
		background: #ef4444;
	}

	@keyframes glow {
		from { box-shadow: 0 0 10px #fbbf24; }
		to { box-shadow: 0 0 30px #fbbf24, 0 0 50px #f59e0b; }
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

	.log-stream {
		flex: 1;
		overflow-y: auto;
		font-family: 'Fira Code', monospace;
		font-size: 0.85rem;
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
	}

	.log-entry.trap .log-type { color: #eab308; }
	.log-entry.log .log-type { color: #6b7280; }
	.log-entry.threat .log-type { color: #ef4444; }
	.log-entry.fingerprint .log-type { color: #3b82f6; }

	.log-message {
		color: #ccc;
	}
</style>
