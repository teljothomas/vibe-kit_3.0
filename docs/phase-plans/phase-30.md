# Phase 30 — Bounded state and append-only event ledger

**Status:** proposed

**Purpose:** preserve the full audit trail in an append-only, verifiable event ledger while keeping the working state compact, and establish owner-controlled supervised/autonomous execution.

## Read

AGENTS.md, docs/invariants.md, docs/state.json, docs/decisions.md, docs/v3-technical-spec.md, docs/v3-phase-prompts.md, vibe/state.py, vibe/approvals.py, vibe/governance.py, vibe/githooks.py, vibe/verify.py, vibe/cli.py, scripts/gate.

## Build

- Add docs/events/ledger.jsonl as the append-only, hash-chained audit journal and vibe/events.py as its standard-library-only writer, verifier, migrator and snapshot-recovery layer.
- Import the actual V2 state schema-2 log without dropping repeated phase entries, null values, evidence references, commit references, deviations or historical approver labels.
- Use deterministic event IDs for imported entries so interrupted/repeated migration is idempotent. Preserve original timestamps exactly; use null where absent and separately record import time.
- Append and fsync a transition event before atomically replacing docs/state.json.
- Keep only a compact recent event summary in docs/state.json; maximum snapshot size is 4,096 bytes, measured as bytes rather than tokens.
- Recover an interrupted snapshot write by replaying the most recent validated snapshot event.
- Add an owner-controlled execution mode: supervised (Human Approval ON) by default and autonomous (Human Approval OFF) only after interactive, HMAC-signed owner action.
- In supervised mode, important decisions require explicit human approval. In autonomous mode, the agent may decide within the active approved phase and delegated action allowlist, record agent-autonomous decisions, and advance only after passing required gates.
- Always require a human for credential/secret handling, permission changes, security-boundary changes, destructive actions, external communications, spending, production releases, governance-mode changes and contract amendments.
- Record every decision with its class, actor, selected mode, outcome and evidence in the event ledger. Autonomous acceptance must never be labelled as human approval.
- Add a signed human phase-start command that activates this proposed Phase 30 contract, advances state from the signed approved Phase 29, and records the transition.
- Keep the core offline and standard-library-only. Do not add a daemon, required MCP service or external runtime dependency.

## Gate

Run python -m pytest tests/phase30 -q, python -m pytest -q, python -m vibe doctor --strict, python -m vibe verify, python -m vibe events verify, and python scripts/phase30-gate.py.

## Acceptance

- The actual V2 schema-2 source fixture contains 22 log records. All 22 become distinct ledger events; duplicate entries for phases 16, 17 and 18 remain distinct.
- All source fields are preserved in event details. The three missing historical timestamps remain null. No legacy (gate:off) record is reported as human-approved.
- Dry-run migration makes no writes; applied migration is repeatable with zero duplicates.
- Ledger verification detects invalid JSON, truncated tail, duplicate IDs, sequence gaps, modified event content and broken previous-hash links.
- Interrupted state replacement is recoverable from the last durable snapshot event.
- 100 simulated transitions keep docs/state.json at or below 4,096 bytes.
- Human Approval defaults ON. Changing it requires a human TTY, reviewer identity, exact-content confirmation and an HMAC signature using the external VIBE_APPROVAL_KEY.
- Agent markers/non-TTY calls cannot change the mode. An agent cannot edit the protected mode config directly.
- Supervised mode blocks important unapproved decisions. Autonomous mode delegates only the documented decision classes within phase scope. Critical actions remain human-gated in both modes.
- Phase advancement in autonomous mode requires a passing phase gate and an approved next-phase contract.
- Every human or autonomous decision is distinguishable in the event history.
- No existing V2 state file or V3 state snapshot is rewritten during dry-run.

## Out of scope

No graph index, cache lifecycle, cross-platform hook adapters or provider telemetry; those remain Phases 31–34. No claim that a local hook or hash chain is an OS security sandbox.
