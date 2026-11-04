# Phase 29 — Governance and phase-contract integrity

**Status:** approved  
**Purpose:** stop an agent from editing the phase contract that defines its own read scope or acceptance criteria, while preserving an explicit human maintenance path.

## Read

`AGENTS.md`, `docs/invariants.md`, `docs/decisions.md`, `docs/state.json`, `vibe/governance.py`, `vibe/approvals.py`, `vibe/githooks.py`, `vibe/cli.py`, `plugins/vibe-kit/templates/governance.json`, `plugins/vibe-kit/scripts/guard_core.py`, `plugins/vibe-kit/scripts/guard.py`, `plugins/vibe-kit/hooks/hooks.json`, `scripts/gate`, `tests/phase29/`.

## Build

- Canonical, versioned protected-path defaults and safe repository-relative path handling.
- Standalone Claude Code `PreToolUse` guard that denies `Write`, `Edit` and `NotebookEdit` to protected governance files and phase source contracts.
- Explicit generated-pack exemptions for `docs/phases/phase-NN.context.md` and `docs/phases/phase-NN.repair.md`.
- Non-authoritative full-replacement amendment proposals at `docs/proposals/phase-NN-amend.md`.
- Gate and pre-commit refusal while any unresolved phase amendment proposal exists.
- Interactive human amendment application with HMAC-SHA256 approval bound to the exact proposed/installed content digest.
- Interactive human approval for staged changes to other protected governance files.
- Git pre-commit install/uninstall that preserves and chains any pre-existing hook.
- Consistent path/protected-policy behavior across loader, plugin template, standalone guard and Git hook.
- Protect the agent protocol, guard/plugin implementation, CLI approval surface, strict doctor/verify, phase gate, Phase 29 conformance tests and CI workflows from agent modification.

## Gate

`python -m pytest tests/phase29 -q`, full `python -m pytest -q`, `python -m vibe doctor --strict`, `python -m vibe verify`, and `python scripts/gate --phase 29`.

## Acceptance

- Direct agent Write/Edit/NotebookEdit of a phase source or protected governance file is denied, including from a subagent.
- Generated context/repair artifacts remain writable.
- A proposal cannot change the active phase's effective contract or read scope.
- Unresolved proposals block governance verification, the phase gate and Git pre-commit.
- Human amendment application requires a TTY, an explicit confirmation, reviewer label and `VIBE_APPROVAL_KEY` (at least 32 bytes); the signed record binds the exact SHA-256 digest, target path and phase.
- Reusing approval after target content changes is rejected.
- Staged protected non-phase files have an explicit human approval path.
- Loader defaults, template and standalone guard defaults are byte-for-byte/structure-equal under parity tests.
- The agent protocol, phase gate, CI workflows, shipped guard and approval implementation are themselves protected from direct agent writes.
- Traversal, absolute outside-root paths, Windows separators/case and symlink escapes are rejected.
- Malformed hook input or unreadable state fails closed only when `docs/state.json` identifies a Vibe-governed project; unrelated projects are unaffected.
- Documentation states hooks are guardrails, not a sandbox.

## Out of scope

No change to `docs/invariants.md` or an existing frozen contract schema; no cross-platform adapter beyond the current Claude Code `PreToolUse` integration; no OS sandbox claim. If a future phase requires an invariant/schema amendment, prepare the formal proposal and stop for human approval before changing it.
