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

	// View mode - attacker sees uniform, we see reality
	let viewMode = $state<'attacker' | 'reality'>('reality');

	// Agents in the honeycomb
	interface VisualAgent extends DemoAgent {
		spawned: boolean;
		engaged: boolean;
		targeted: boolean;
		responding: boolean;
		x: number;
		y: number;
		lure?: string | null;
		description?: string;
	}
	let agents = $state<VisualAgent[]>([]);

	// Attacker
	let attackerVisible = $state(false);
	let attackerPosition = $state({ x: 50, y: 0 });

	// Phase & threat
	let currentPhase = $state<PhaseChangeEvent | null>(null);
	let threatLevel = $state<string>('NONE');

	// Freepik image modal state
	let showImageModal = $state<boolean>(false);
	let modalImageUrl = $state<string>('');
	let modalImageTitle = $state<string>('');

	// Activity log - simplified types matching backend
	type LogType = 'system' | 'alert' | 'phase' | 'attacker' | 'honeypot' | 'captured' | 'routing' | 'legitimate' | 'success' | 'result' | 'tinyfish' | 'cline' | 'tonic' | 'freepik';
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

	// Selected agent for detail view
	let selectedAgent = $state<VisualAgent | null>(null);

	function selectAgent(agent: VisualAgent) {
		selectedAgent = selectedAgent?.id === agent.id ? null : agent;
	}

	function closeAgentDetail() {
		selectedAgent = null;
	}

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
	// FREEPIK VISUAL HONEYTOKEN
	// ============================================================

	let generatingImage = $state(false);

	async function generateVisualHoneytoken() {
		generatingImage = true;
		try {
			const response = await fetch('/api/visual-honeytoken', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ asset_type: 'architecture_diagram' })
			});
			const result = await response.json();
			if (result.success && result.data) {
				modalImageUrl = result.data.url;
				modalImageTitle = `Visual Honeytoken: ${result.data.asset_type} (${result.data.canary_id})`;
				showImageModal = true;
				// Add log entry
				logs = [...logs, {
					id: Date.now(),
					type: 'freepik' as LogType,
					message: `Generated visual honeytoken: ${result.data.asset_type} [Canary: ${result.data.canary_id}]`,
					timestamp: new Date().toISOString()
				}];
			}
		} catch (e) {
			console.error('Failed to generate visual honeytoken:', e);
		} finally {
			generatingImage = false;
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
					y: pos.y,
					lure: data.agent.lure,
					description: data.agent.description
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

		<!-- View Mode Toggle -->
		<div class="view-toggle">
			<button
				class="view-btn"
				class:active={viewMode === 'attacker'}
				onclick={() => viewMode = 'attacker'}
			>
				ATTACKER VIEW
			</button>
			<button
				class="view-btn"
				class:active={viewMode === 'reality'}
				onclick={() => viewMode = 'reality'}
			>
				REALITY
			</button>
		</div>

		<!-- Freepik Demo Button -->
		<button
			class="demo-btn freepik-demo"
			onclick={generateVisualHoneytoken}
			disabled={generatingImage}
		>
			{generatingImage ? '🎨 GENERATING...' : '🎨 GENERATE VISUAL TRAP'}
		</button>
	</div>


	<!-- Tech Stack Banner -->
	<div class="tech-banner">
		<div class="tech-section">
			<img src="https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg" alt="AWS" class="tech-logo" />
			<div class="tech-item has-tooltip">
				<span class="tech-badge strands">Strands</span>
				<span class="tech-desc">Agents SDK</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">AWS Strands Agents SDK</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/core/agents.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Import:</span>
						<code>from strands import Agent, tool</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Powers all agents in the swarm. Creates Agent() instances with custom system prompts loaded from prompts/*.md and tools from backend/tools/.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Agent types:</span>
						<span>real (processor-001), honeypot_db_admin (db-admin-001), honeypot_privileged (privileged-proc-001)</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Model:</span>
						<code>amazon.nova-pro-v1:0</code> via Bedrock
					</div>
				</div>
			</div>
			<div class="tech-item has-tooltip">
				<span class="tech-badge s3">S3 Vectors</span>
				<span class="tech-desc">Fingerprints</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">S3 Vectors - Attacker Fingerprints</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/tools/intel_query.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Stores and queries attacker behavioral fingerprints using S3 vector embeddings. Enables pattern recognition across attack sessions.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Captures:</span>
						<span>Query patterns, timing signatures, linguistic fingerprints, tactic sequences</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Used for:</span>
						<span>Identifying repeat attackers, correlating attack campaigns, improving honeypot responses based on learned patterns</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Logging:</span>
						<code>logs/canary_credentials.jsonl</code>
					</div>
				</div>
			</div>
			<div class="tech-item has-tooltip">
				<span class="tech-badge cloudwatch">CloudWatch</span>
				<span class="tech-desc">Metrics</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">CloudWatch - System Metrics & Evolution</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Namespace:</span>
						<code>HoneyAgent</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/api/main.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Publishes real-time metrics from honeypot system evolution. Tracks defense effectiveness and learning improvements across attack campaigns.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Metrics tracked:</span>
						<span>defense_effectiveness (%), improvement_since_start (%), honeypot_engagement_rate, fingerprints_captured</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Dashboard:</span>
						<span>Live metrics visible in stats bar above. Updates every evolution cycle.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Used for:</span>
						<span>Monitoring system performance, detecting evolution patterns, alerting on anomalies</span>
					</div>
				</div>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section">
			<img src="https://cdn.auth0.com/website/bob/press/logo-light.png" alt="Auth0" class="tech-logo auth0-logo" />
			<div class="tech-item has-tooltip">
				<span class="tech-badge jwt">JWT</span>
				<span class="tech-desc">Identity</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Auth0 M2M JWT Identity</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/core/identity.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Validates Machine-to-Machine JWT tokens on every agent request. Determines if caller is a legitimate agent or potential attacker.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Returns:</span>
						<span>Identity object with: valid, agent_id, agent_type ("real" | "honeypot"), is_honeypot, fga_allowed</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Invalid token →</span>
						<span>Request routed to honeypot (attacker detected)</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Valid token →</span>
						<span>Request proceeds to FGA check</span>
					</div>
				</div>
			</div>
			<div class="tech-item has-tooltip">
				<span class="tech-badge fga">FGA</span>
				<span class="tech-desc">Routing</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Auth0 Fine-Grained Authorization</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/core/router.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Config:</span>
						<code>config/routing.yaml</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Controls which agents can access which resources. Routes unauthorized/suspicious requests to honeypots instead of real agents.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Decision flow:</span>
						<span>Identity check → FGA permission check → Route to real agent OR honeypot</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Honeypot strategy:</span>
						<span>Honeypots advertise high-value lures (DB ACCESS, ROOT, SECRETS) to attract attackers away from real agents</span>
					</div>
				</div>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section">
			<span class="tech-logo-text tinyfish-text">TinyFish</span>
			<div class="tech-item has-tooltip">
				<span class="tech-badge agentql">AgentQL</span>
				<span class="tech-desc">Semantic</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">TinyFish AgentQL - Semantic Matching</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/integrations/tinyfish.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Used by:</span>
						<span>honeypot_db_admin, honeypot_privileged agents</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Inspired by AgentQL's get_by_prompt() API. Analyzes what an agent is asking about (configuration, workflow, architecture, access, data, troubleshooting) and generates natural conversational responses that sound like a helpful colleague.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">How it works:</span>
						<span>Pattern matching detects intent categories, then returns plausible fake info. All queries logged to logs/semantic_queries.jsonl for behavioral analysis.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Config:</span>
						<code>config/agents.yaml</code> → tools: [semantic_match]
					</div>
				</div>
			</div>
			<div class="tech-item has-tooltip">
				<span class="tech-badge tinyfish-pattern">Patterns</span>
				<span class="tech-desc">Fingerprints</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">TinyFish Pattern Extractor</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/tools/pattern_extractor.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Extracts behavioral fingerprints from attacker interactions using TinyFish AI. Analyzes query patterns, timing signatures, and linguistic markers to identify repeat attackers.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Captures:</span>
						<span>Intent categories, query complexity, timing patterns, vocabulary fingerprints, session behaviors</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Risk scoring:</span>
						<span>Assigns 0-10 risk score based on pattern analysis. High scores trigger enhanced honeypot engagement.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Output:</span>
						<code>logs/pattern_analysis.jsonl</code>
					</div>
				</div>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section">
			<span class="tech-logo-text tonic-text">Tonic</span>
			<div class="tech-item has-tooltip">
				<span class="tech-badge tonic-badge">Fabricate</span>
				<span class="tech-desc">Synthetic</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Tonic Fabricate - Synthetic Data</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/integrations/tonic_fabricate.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Generates realistic fake credentials and sensitive data using Tonic Fabricate. Creates believable honeytokens that attract attackers while being completely synthetic and trackable.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Data types:</span>
						<span>AWS keys, database credentials, API tokens, SSH keys, JWT secrets, personal data (PII)</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Key feature:</span>
						<span>Referential integrity - generated data looks real because it follows proper formats, checksums, and relationships.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Tracking:</span>
						<span>Every credential embeds a unique fingerprint. When used, we know exactly which honeypot leaked it.</span>
					</div>
				</div>
			</div>
			<div class="tech-item has-tooltip">
				<span class="tech-badge tonic-creds">Canary</span>
				<span class="tech-desc">Credentials</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Canary Credential Generator</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/tools/fake_credential.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Strands tool that generates honeytokens on-demand. Honeypots call this to create fake credentials that look enticing to attackers.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Credential types:</span>
						<span>aws_key, db_password, api_token, ssh_key, jwt_secret</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Tracking:</span>
						<span>All generated credentials logged to logs/canary_credentials.jsonl with session context for attribution.</span>
					</div>
				</div>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section">
			<span class="tech-logo-text cline-text">Cline</span>
			<div class="tech-item has-tooltip">
				<span class="tech-badge cline-badge">CLI</span>
				<span class="tech-desc">Variation</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Cline Variation Pipeline</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>scripts/cline_pipeline.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Purpose:</span>
						<span>Generates diverse honeypot code variations using Cline CLI. Different models + personas = unique code fingerprints that are harder for attackers to detect as honeypots.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Honeypot types:</span>
						<span>ssh, api, database, form, filesystem</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Personas:</span>
						<span>aggressive (oversharing), minimal (legacy), enterprise (corporate), developer (debug mode)</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Usage:</span>
						<code>python scripts/cline_pipeline.py --type api --personas aggressive,minimal</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Output:</span>
						<code>generated/honeypots/</code>
					</div>
				</div>
			</div>
		</div>
		<div class="tech-divider"></div>
		<div class="tech-section">
			<span class="tech-logo-text freepik-text">Freepik</span>
			<div class="tech-item has-tooltip">
				<span class="tech-badge freepik-badge">Mystic AI</span>
				<span class="tech-desc">Images</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Freepik Visual Honeytokens</div>
					<div class="tooltip-section">
						<span class="tooltip-label">File:</span>
						<code>backend/tools/visual_honeytoken.py</code>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Function:</span>
						<span>Generates fake "sensitive" images (architecture diagrams, admin screenshots) using Freepik's Mystic AI. Each image is a trackable honeytoken - if exfiltrated, we know which attacker took it.</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Asset types:</span>
						<span>Architecture diagrams, Admin screenshots, Database schemas, Network topology</span>
					</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Tracking:</span>
						<span>Each image has a unique canary_id. If it appears elsewhere, we trace it back to the attacker session.</span>
					</div>
				</div>
			</div>
			<div class="tech-item has-tooltip">
				<span class="tech-badge freepik-canary">Canary</span>
				<span class="tech-desc">Track</span>
				<div class="tech-tooltip">
					<div class="tooltip-title">Visual Canary Tokens</div>
					<div class="tooltip-section">
						<span class="tooltip-label">Purpose:</span>
						<span>Images served to attackers contain invisible watermarks. When leaked, they identify the source and timeline of the breach.</span>
					</div>
				</div>
			</div>
		</div>
	</div>

	<div class="main-content">
		<!-- Honeycomb Visualization -->
		<div class="hive-container">
			<h2>Swarm View</h2>
			{#if agents.length === 0}
				<p class="hint">Press PLAY DEMO to begin...</p>
			{:else if viewMode === 'attacker'}
				<p class="hint">Attacker's perspective: All agents look identical - which ones are traps?</p>
			{:else}
				<p class="hint">Reality: Blue = Real Agents | Amber with badges = Honeypots (traps)</p>
			{/if}

			<div class="honeycomb-area">
				<!-- Agents -->
				{#each agents as agent (agent.id)}
					<button
						class="hex-cell"
						class:spawning={agent.spawned}
						class:engaged={agent.engaged}
						class:targeted={agent.targeted}
						class:honeypot={agent.is_honeypot && viewMode === 'reality'}
						class:real-agent={!agent.is_honeypot && viewMode === 'reality'}
						class:uniform={viewMode === 'attacker'}
						class:responding={agent.responding}
						class:selected={selectedAgent?.id === agent.id}
						style="left: {agent.x}px; top: {agent.y}px;"
						title={agent.description || agent.name}
						onclick={() => selectAgent(agent)}
					>
						<div class="hex-inner">
							{#if viewMode === 'reality'}
								<span class="hex-icon">{agent.is_honeypot ? '!' : 'A'}</span>
							{:else}
								<span class="hex-icon">A</span>
							{/if}
							{#if agent.engaged}
								<span class="engaged-badge">!</span>
							{/if}
						</div>
						<span class="agent-label">{agent.name.split('-')[0]}</span>
						{#if viewMode === 'reality' && agent.lure}
							<span class="lure-badge">{agent.lure}</span>
						{/if}
					</button>
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
					{#if routingDecision.decision.includes('HONEYPOT')}
						<div class="routing-strategy">
							Honeypots advertise high-value access (DB, ROOT, SECRETS) to attract attackers.
							Invalid credentials = automatic trap routing.
						</div>
					{:else}
						<div class="routing-strategy success">
							Valid credentials bypass honeypots entirely.
							Real work continues uninterrupted.
						</div>
					{/if}
				</div>
			{/if}

			<!-- Agent Detail Panel -->
			{#if selectedAgent}
				<div class="agent-detail-panel" class:honeypot={selectedAgent.is_honeypot} class:real={!selectedAgent.is_honeypot}>
					<div class="agent-detail-header">
						<span class="agent-detail-type" class:honeypot={selectedAgent.is_honeypot}>
							{selectedAgent.is_honeypot ? 'HONEYPOT' : 'REAL AGENT'}
						</span>
						<button class="agent-detail-close" onclick={closeAgentDetail}>×</button>
					</div>
					<div class="agent-detail-name">{selectedAgent.name}</div>
					<div class="agent-detail-id">ID: {selectedAgent.id}</div>
					{#if selectedAgent.description}
						<div class="agent-detail-desc">{selectedAgent.description}</div>
					{/if}
					{#if selectedAgent.is_honeypot}
						<div class="agent-detail-section">
							<div class="agent-detail-label">Lure (Bait)</div>
							<div class="agent-detail-lure">{selectedAgent.lure || 'HIGH VALUE TARGET'}</div>
						</div>
						<div class="agent-detail-section">
							<div class="agent-detail-label">Purpose</div>
							<div class="agent-detail-value">Attracts attackers with fake high-value access. Captures fingerprints and delays threats.</div>
						</div>
						<div class="agent-detail-section">
							<div class="agent-detail-label">Status</div>
							<div class="agent-detail-status" class:engaged={selectedAgent.engaged}>
								{selectedAgent.engaged ? 'ENGAGED - Trapping attacker' : 'READY - Awaiting contact'}
							</div>
						</div>
					{:else}
						<div class="agent-detail-section">
							<div class="agent-detail-label">Purpose</div>
							<div class="agent-detail-value">Legitimate production agent. Processes real workloads from authorized clients.</div>
						</div>
						<div class="agent-detail-section">
							<div class="agent-detail-label">Protection</div>
							<div class="agent-detail-value">Shielded by honeypot network. Attackers are routed away before reaching this agent.</div>
						</div>
						<div class="agent-detail-section">
							<div class="agent-detail-label">Status</div>
							<div class="agent-detail-status success">
								{selectedAgent.responding ? 'PROCESSING - Handling request' : 'OPERATIONAL - Ready for work'}
							</div>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Legend -->
			<div class="legend">
				{#if viewMode === 'reality'}
					<div class="legend-item">
						<div class="legend-hex real-agent"></div>
						<span>Real Agent</span>
					</div>
					<div class="legend-item">
						<div class="legend-hex honeypot"></div>
						<span>Honeypot (Trap)</span>
					</div>
					<div class="legend-item">
						<div class="legend-hex with-lure"></div>
						<span class="lure-example">DB ACCESS</span>
						<span>= Bait</span>
					</div>
				{:else}
					<div class="legend-item">
						<div class="legend-hex uniform"></div>
						<span>All agents look identical to attacker</span>
					</div>
				{/if}
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

			<!-- Compact Stats Row -->
			<div class="compact-stats">
				<div class="compact-stat">
					<span class="compact-value">{agents.length}</span>
					<span class="compact-label">Agents</span>
				</div>
				<div class="compact-stat">
					<span class="compact-value">{honeypotCount}</span>
					<span class="compact-label">Honeypots</span>
				</div>
				<div class="compact-stat">
					<span class="compact-value">{engagedCount}</span>
					<span class="compact-label">Engaged</span>
				</div>
				<div class="compact-stat">
					<span class="compact-value">{fingerprintsCaptured}</span>
					<span class="compact-label">Fingerprints</span>
				</div>
				<div class="compact-divider"></div>
				<div class="compact-stat cloudwatch has-tooltip">
					<img src="https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg" alt="AWS" class="compact-aws-logo" />
					<span class="compact-value green">{evolutionStats?.defense_effectiveness ?? '0%'}</span>
					<span class="compact-label">Defense</span>
					<div class="tech-tooltip compact-tooltip">
						<div class="tooltip-title">CloudWatch Metrics</div>
						<div class="tooltip-section">
							<span class="tooltip-label">Namespace:</span>
							<code>HoneyAgent</code>
						</div>
						<div class="tooltip-section">
							<span>Live from honeypot system evolution</span>
						</div>
					</div>
				</div>
				<div class="compact-stat cloudwatch">
					<span class="compact-value green">{evolutionStats?.improvement_since_start ?? '+0%'}</span>
					<span class="compact-label">Learned</span>
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

	<!-- Freepik Image Modal -->
	{#if showImageModal}
		<div class="image-modal-overlay" onclick={() => showImageModal = false}>
			<div class="image-modal" onclick={(e) => e.stopPropagation()}>
				<div class="modal-header">
					<span class="modal-title">{modalImageTitle}</span>
					<button class="modal-close" onclick={() => showImageModal = false}>×</button>
				</div>
				<img src={modalImageUrl} alt={modalImageTitle} class="modal-image" />
				<div class="modal-footer">
					<span class="modal-badge">Generated by Freepik Mystic AI</span>
				</div>
			</div>
		</div>
	{/if}
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

	.demo-btn.freepik-demo {
		background: linear-gradient(135deg, #ff6b35, #f7931e);
		color: white;
		box-shadow: 0 4px 16px rgba(255, 107, 53, 0.3);
	}

	.demo-btn.freepik-demo:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 24px rgba(255, 107, 53, 0.4);
	}

	.demo-btn.freepik-demo:disabled {
		opacity: 0.7;
		cursor: wait;
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

	/* View Mode Toggle */
	.view-toggle {
		margin-left: auto;
		display: flex;
		gap: 0;
		background: var(--bg-elevated);
		border-radius: var(--radius-md);
		padding: 4px;
		border: 1px solid var(--glass-border);
	}

	.view-btn {
		padding: 0.5rem 1rem;
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.05em;
		cursor: pointer;
		border-radius: var(--radius-sm);
		transition: all 0.2s ease;
	}

	.view-btn:hover {
		color: var(--text-primary);
	}

	.view-btn.active {
		background: linear-gradient(135deg, var(--honey-500), var(--honey-600));
		color: var(--bg-deep);
		box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
	}

	/* Tech Stack Banner */
	.tech-banner {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem; /* Reduced from 2rem */
		padding: 0.75rem 1rem; /* Reduced padding */
		background: linear-gradient(135deg, rgba(0, 0, 0, 0.4), rgba(20, 20, 20, 0.6));
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: var(--radius-md);
		margin-bottom: 1.5rem;
		position: relative;
		max-width: 100%; /* Ensure it doesn't overflow */
		overflow: visible; /* Changed from overflow-x: auto to allow tooltips */
	}

	.tech-section {
		display: flex;
		align-items: center;
		gap: 0.5rem; /* Reduced from 0.75rem */
		overflow: visible; /* Ensure tooltips aren't clipped */
	}

	.tech-logo {
		height: 20px; /* Reduced from 24px */
		width: auto;
		filter: brightness(1.1);
	}

	.tech-logo.auth0-logo {
		height: 18px; /* Reduced from 20px */
	}

	.tech-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		overflow: visible; /* Ensure tooltips aren't clipped */
	}

	.tech-badge {
		padding: 0.25rem 0.5rem; /* Slightly reduced */
		font-size: 0.65rem; /* Slightly reduced */
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

	.tech-badge.cloudwatch {
		background: linear-gradient(135deg, #ff9900, #ffb84d);
		color: #232f3e;
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


	.tech-badge.tonic-badge {
		background: linear-gradient(135deg, #8b5cf6, #a78bfa);
		color: #fff;
	}

	.tech-badge.tonic-creds {
		background: linear-gradient(135deg, #7c3aed, #8b5cf6);
		color: #fff;
	}

	.tech-badge.tinyfish-pattern {
		background: linear-gradient(135deg, #0891b2, #06b6d4);
		color: #fff;
	}

	.tech-logo-text {
		font-size: 0.8rem; /* Reduced from 0.9rem */
		font-weight: 700;
		letter-spacing: 0.02em;
	}

	.tinyfish-text {
		color: #22d3ee;
	}

	.cline-text {
		color: #34d399;
	}


	.tonic-text {
		color: #a78bfa;
	}


	.tech-desc {
		color: var(--text-muted);
		font-size: 0.6rem; /* Reduced from 0.65rem */
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}

	.tech-divider {
		width: 1px;
		height: 32px; /* Reduced from 40px */
		background: rgba(255, 255, 255, 0.15);
	}

	/* Tech Tooltips */
	.tech-item.has-tooltip {
		position: relative;
		cursor: help;
	}

	.tech-tooltip {
		position: absolute;
		top: calc(100% + 12px); /* Changed to appear below */
		left: 50%;
		transform: translateX(-50%);
		width: 340px;
		max-width: 90vw; /* Prevent overflow on small screens */
		background: rgba(15, 13, 10, 0.98);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 12px;
		padding: 1rem;
		opacity: 0;
		visibility: hidden;
		transition: all 0.2s ease;
		z-index: 10000; /* Higher z-index to ensure it's always on top */
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.05);
		pointer-events: none;
	}

	.tech-item.has-tooltip:hover .tech-tooltip {
		opacity: 1;
		visibility: visible;
	}

	.tech-tooltip::after {
		content: '';
		position: absolute;
		top: -8px; /* Flipped to point upward */
		left: 50%;
		transform: translateX(-50%);
		border-width: 0 8px 8px 8px; /* Flipped border to point upward */
		border-style: solid;
		border-color: transparent transparent rgba(15, 13, 10, 0.98) transparent; /* Flipped colors */
	}

	.tooltip-title {
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--honey-400);
		margin-bottom: 0.75rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	.tooltip-section {
		margin-bottom: 0.5rem;
		font-size: 0.75rem;
		line-height: 1.4;
	}

	.tooltip-section:last-child {
		margin-bottom: 0;
	}

	.tooltip-label {
		color: var(--text-muted);
		font-weight: 600;
		display: block;
		margin-bottom: 0.15rem;
	}

	.tooltip-section span {
		color: var(--text-secondary);
	}

	.tooltip-section code {
		background: rgba(255, 255, 255, 0.1);
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		font-family: 'Fira Code', monospace;
		font-size: 0.7rem;
		color: var(--honey-300);
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
		/* Reset button styles */
		border: none;
		background: transparent;
		padding: 0;
		cursor: pointer;
		outline: none;
	}

	.hex-cell:hover {
		transform: scale(1.1);
		z-index: 10;
	}

	.hex-cell:focus-visible {
		outline: 2px solid var(--honey-400);
		outline-offset: 4px;
	}

	.hex-cell.selected {
		transform: scale(1.15);
		z-index: 20;
	}

	.hex-cell.selected .hex-inner {
		box-shadow: 0 0 30px rgba(255, 255, 255, 0.5), 0 0 60px rgba(245, 158, 11, 0.4);
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

	/* Honeypot = Amber/Gold (enticing bait) */
	.hex-cell.honeypot .hex-inner {
		background: linear-gradient(135deg, #f59e0b, #d97706);
		box-shadow: 0 0 20px rgba(245, 158, 11, 0.4);
	}

	/* Real Agent = Blue/Teal (trustworthy, legitimate) */
	.hex-cell.real-agent .hex-inner {
		background: linear-gradient(135deg, #3b82f6, #2563eb);
		box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
	}

	/* Uniform view = All agents look the same (gray/neutral) */
	.hex-cell.uniform .hex-inner {
		background: linear-gradient(135deg, #6b7280, #4b5563);
		box-shadow: none;
	}

	/* Lure badge - shows what bait the honeypot offers */
	.lure-badge {
		position: absolute;
		top: -12px;
		left: 50%;
		transform: translateX(-50%);
		background: linear-gradient(135deg, #ef4444, #dc2626);
		color: white;
		font-size: 0.6rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		padding: 2px 6px;
		border-radius: 4px;
		white-space: nowrap;
		box-shadow: 0 2px 8px rgba(239, 68, 68, 0.4);
		animation: lurePulse 2s ease-in-out infinite;
	}

	@keyframes lurePulse {
		0%, 100% {
			box-shadow: 0 2px 8px rgba(239, 68, 68, 0.4);
			transform: translateX(-50%) scale(1);
		}
		50% {
			box-shadow: 0 2px 16px rgba(239, 68, 68, 0.6);
			transform: translateX(-50%) scale(1.05);
		}
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
	.legend-hex.real-agent {
		background: linear-gradient(135deg, #3b82f6, #2563eb);
	}
	.legend-hex.honeypot {
		background: linear-gradient(135deg, #f59e0b, #d97706);
	}
	.legend-hex.uniform {
		background: linear-gradient(135deg, #6b7280, #4b5563);
	}
	.legend-hex.with-lure {
		background: linear-gradient(135deg, #f59e0b, #d97706);
		position: relative;
	}
	.legend-hex.engaged {
		background: #ef4444;
	}
	.legend-hex.attacker {
		background: #ef4444;
		border-radius: 50%;
		clip-path: none;
	}
	.lure-example {
		background: linear-gradient(135deg, #ef4444, #dc2626);
		color: white;
		font-size: 0.65rem;
		font-weight: 700;
		padding: 2px 6px;
		border-radius: 4px;
		margin-left: 0.5rem;
	}

	/* ============================================================
	   COMPACT STATS ROW - Below swarm view
	   ============================================================ */

	.compact-stats {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		padding: 0.5rem 1rem;
		background: rgba(0, 0, 0, 0.4);
		border-radius: 6px;
		margin-top: 0.5rem;
	}

	.compact-stat {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		position: relative;
	}

	.compact-value {
		font-size: 1rem;
		font-weight: 700;
		color: var(--honey-400);
	}

	.compact-value.green {
		color: #4ade80;
	}

	.compact-label {
		font-size: 0.65rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}

	.compact-divider {
		width: 1px;
		height: 20px;
		background: rgba(255, 255, 255, 0.2);
		margin: 0 0.25rem;
	}

	.compact-stat.cloudwatch {
		cursor: help;
	}

	.compact-aws-logo {
		height: 12px;
		width: auto;
		margin-right: 0.2rem;
	}

	.compact-stat.has-tooltip .compact-tooltip {
		position: absolute;
		bottom: calc(100% + 8px);
		left: 50%;
		transform: translateX(-50%);
		width: 200px;
		background: rgba(15, 13, 10, 0.98);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 8px;
		padding: 0.75rem;
		opacity: 0;
		visibility: hidden;
		transition: all 0.2s ease;
		z-index: 1000;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
		pointer-events: none;
	}

	.compact-stat.has-tooltip:hover .compact-tooltip {
		opacity: 1;
		visibility: visible;
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
		top: 8px;
		right: 8px;
		background: rgba(0, 0, 0, 0.9);
		border: 1px solid #ef4444;
		border-radius: 8px;
		padding: 0.5rem 0.6rem;
		min-width: 160px;
		max-width: 180px;
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
		gap: 0.35rem;
		margin-bottom: 0.4rem;
		padding-bottom: 0.3rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	.routing-logo {
		height: 12px;
		width: auto;
	}

	.routing-title {
		font-size: 0.55rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: #eb5424;
	}

	.routing-checks {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		margin-bottom: 0.4rem;
	}

	.routing-check {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.6rem;
		padding: 0.15rem 0.3rem;
		border-radius: 3px;
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
		width: 0.9rem;
		text-align: center;
		font-size: 0.65rem;
	}

	.routing-decision-text {
		font-size: 0.65rem;
		font-weight: 700;
		text-align: center;
		padding: 0.3rem;
		border-radius: 4px;
		margin-bottom: 0.3rem;
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
		font-size: 0.55rem;
		color: #9ca3af;
		text-align: center;
		font-style: italic;
		line-height: 1.3;
		display: none;
	}

	.routing-strategy {
		margin-top: 0.35rem;
		padding: 0.3rem;
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 4px;
		font-size: 0.5rem;
		color: #fca5a5;
		text-align: center;
		line-height: 1.3;
		display: none;
	}

	.routing-strategy.success {
		background: rgba(34, 197, 94, 0.1);
		border-color: rgba(34, 197, 94, 0.3);
		color: #86efac;
	}

	/* ============================================================
	   AGENT DETAIL PANEL
	   ============================================================ */

	.agent-detail-panel {
		position: absolute;
		bottom: 10px;
		left: 10px;
		background: rgba(0, 0, 0, 0.9);
		border: 2px solid var(--honey-500);
		border-radius: 12px;
		padding: 1rem;
		min-width: 280px;
		max-width: 320px;
		animation: slideUp 0.3s ease-out;
		z-index: 200;
	}

	.agent-detail-panel.honeypot {
		border-color: #f59e0b;
	}

	.agent-detail-panel.real {
		border-color: #3b82f6;
	}

	@keyframes slideUp {
		from {
			opacity: 0;
			transform: translateY(20px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.agent-detail-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}

	.agent-detail-type {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		background: linear-gradient(135deg, #3b82f6, #2563eb);
		color: white;
	}

	.agent-detail-type.honeypot {
		background: linear-gradient(135deg, #f59e0b, #d97706);
		color: #1a1408;
	}

	.agent-detail-close {
		background: transparent;
		border: none;
		color: var(--text-muted);
		font-size: 1.5rem;
		cursor: pointer;
		padding: 0;
		line-height: 1;
		transition: color 0.2s ease;
	}

	.agent-detail-close:hover {
		color: var(--text-primary);
	}

	.agent-detail-name {
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--text-primary);
		margin-bottom: 0.25rem;
	}

	.agent-detail-id {
		font-size: 0.75rem;
		color: var(--text-muted);
		font-family: 'Fira Code', monospace;
		margin-bottom: 0.5rem;
	}

	.agent-detail-desc {
		font-size: 0.85rem;
		color: var(--text-secondary);
		margin-bottom: 0.75rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	.agent-detail-section {
		margin-bottom: 0.75rem;
	}

	.agent-detail-label {
		font-size: 0.65rem;
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--text-muted);
		margin-bottom: 0.25rem;
	}

	.agent-detail-value {
		font-size: 0.8rem;
		color: var(--text-secondary);
		line-height: 1.4;
	}

	.agent-detail-lure {
		display: inline-block;
		background: linear-gradient(135deg, #ef4444, #dc2626);
		color: white;
		font-size: 0.8rem;
		font-weight: 700;
		padding: 0.35rem 0.75rem;
		border-radius: 6px;
		box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
	}

	.agent-detail-status {
		font-size: 0.8rem;
		font-weight: 600;
		color: #fbbf24;
	}

	.agent-detail-status.engaged {
		color: #ef4444;
		animation: statusPulse 1s ease-in-out infinite;
	}

	.agent-detail-status.success {
		color: #4ade80;
	}

	@keyframes statusPulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.6; }
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
	   SPONSOR: Tonic Fabricate Log Entries
	   ============================================================ */

	.log-entry.tonic {
		background: rgba(139, 92, 246, 0.15);
		border-left-color: #8b5cf6;
	}
	.log-entry.tonic .log-message {
		color: #c4b5fd;
		font-weight: 600;
	}
	.log-entry.tonic .log-message::before {
		content: '[Tonic] ';
		color: #a78bfa;
		font-weight: 700;
	}

	/* ============================================================
	   SPONSOR: Freepik Log Entries
	   ============================================================ */

	.log-entry.freepik {
		background: rgba(255, 107, 53, 0.15);
		border-left-color: #ff6b35;
	}
	.log-entry.freepik .log-message {
		color: #ffa07a;
		font-weight: 600;
	}
	.log-entry.freepik .log-message::before {
		content: '[Freepik] ';
		color: #ff6b35;
		font-weight: 700;
	}

	.freepik-text {
		color: #ff6b35;
	}

	.tech-badge.freepik-badge {
		background: linear-gradient(135deg, #ff6b35, #f7931e);
		color: #fff;
	}

	.tech-badge.freepik-canary {
		background: linear-gradient(135deg, #f7931e, #ffcc00);
		color: #1a1a2e;
	}

	/* ============================================================
	   Freepik Image Modal
	   ============================================================ */

	.image-modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.85);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	.image-modal {
		background: #1a1a2e;
		border: 1px solid #ff6b35;
		border-radius: 8px;
		max-width: 90vw;
		max-height: 90vh;
		overflow: hidden;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 16px;
		border-bottom: 1px solid #2d2d44;
	}

	.modal-title {
		color: #ff6b35;
		font-weight: 600;
	}

	.modal-close {
		background: none;
		border: none;
		color: #888;
		font-size: 24px;
		cursor: pointer;
	}

	.modal-close:hover {
		color: #ff6b35;
	}

	.modal-image {
		max-width: 100%;
		max-height: 70vh;
		display: block;
	}

	.modal-footer {
		padding: 12px 16px;
		border-top: 1px solid #2d2d44;
		text-align: center;
	}

	.modal-badge {
		color: #ff6b35;
		font-size: 0.85rem;
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
