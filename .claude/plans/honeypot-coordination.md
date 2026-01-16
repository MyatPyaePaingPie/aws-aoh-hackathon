# Plan: Honeypot Agent Coordination

## Goal
Enable honeypot agents to coordinate by sharing session context automatically.

## Done-When
- [x] Agents see what attacker did with other honeypots
- [x] Context is injected automatically (no agent action needed)
- [x] Session_id tracks attacker across multiple requests

## Solution
**Chosen:** Context Injection at Execution
**Why:** Simplest (~30 lines), no new tools, agents naturally adapt
**Code:** ~40 lines modification to agents.py
**Deps:** None (uses existing log_interaction data)

## Steps
1. [x] Add session_id to AgentRequest model
2. [x] Add helper to fetch prior interactions by session_id
3. [x] Modify execute_agent to inject context into message
4. [x] Update log_interaction to store session_id

## Validate
- [x] Multiple requests with same session_id show context
- [x] Fallback works when no prior interactions exist (returns empty string)

---
Created: 2026-01-16
Completed: 2026-01-16
Status: COMPLETED
