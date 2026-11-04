# Decision Log

Append-only rationale. Each phase adds one concise entry; never rewrite past decisions.

- 2026-11-04 — Created Vibe Kit 3.0 as an independent repository rather than modifying V2; retain V2 as a compatibility/reference source while the V3 codebase is rebuilt and validated in controlled phases.
- 2026-11-04 — Keep runtime dependencies empty; pytest is an optional test extra and CI-only requirement, preserving the local-first standard-library core.
- 2026-11-04 — Keep Phase 28 open until the new repository's remote CI matrix is actually observed green; local verification alone cannot establish cross-platform CI success.
- 2026-11-04 — Phase 28 was approved after the repository owner explicitly instructed proceeding; its final main/feature-branch CI matrix passed 9/9 and the strict gate passed.
- 2026-11-04 — Phase 29 keeps protected-path policy defaults in `vibe/governance.py`; the project template and standalone plugin guard are checked for exact parity. Phase source contracts are protected separately from generated context/repair artifacts.
- 2026-11-04 — Protected content approvals are HMAC-SHA256 signatures over canonical metadata including the exact target-content digest. The key remains outside the repository in `VIBE_APPROVAL_KEY`; interactive human confirmation is a workflow guardrail, not an OS security boundary.
