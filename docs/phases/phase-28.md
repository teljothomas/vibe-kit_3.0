# Phase 28 — V3 foundation and portability baseline

**Status:** approved — repository owner explicitly authorized proceeding to Phase 29 on 4 November 2026  
**Purpose:** establish an independently buildable V3 repository with a real CI/test contract before adding governance or intelligence features.

Read: `AGENTS.md`, `docs/invariants.md`, `pyproject.toml`, `vibe/`, `tests/`, `.github/workflows/`, `scripts/gate`
Build: V3 package/CLI foundation; deterministic state validation; strict doctor/verify; branch-default-independent Git regression fixture; portable CI matrix; focused phase gate.
Gate: `scripts/gate --phase 28` and full `python -m pytest -q`

## Acceptance

- Runtime dependencies are empty; pytest remains a development/test dependency.
- CLI starts and reports a version; status, doctor and verify provide real checks (no placeholder success).
- Git fixture tests pass with both `main` and `master` as the configured initial branch; tests return to the actual initial branch, never a hard-coded name.
- CI tests Ubuntu, macOS and Windows on Python 3.9, 3.11 and 3.13.
- The repository gate workflow installs pytest before executing the pytest-backed gate and pins Python to a matrix-supported version.
- `python -m vibe doctor --strict`, `python -m vibe verify`, `scripts/gate --phase 28` pass locally.
- The complete remote CI matrix passed 9/9 on both `main` and `phase/28-v3-foundation` at commit `a8bb5362ae028b4442867e054361787100d7f620`; the strict gate also passed. The repository owner then explicitly instructed proceeding to Phase 29.

## Out of scope

No phase-contract guard, event journal, graph index, platform adapter, telemetry collector, automatic model routing, release or merge. Those remain later phases.
