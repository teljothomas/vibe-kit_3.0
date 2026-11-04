# Decision Log

Append-only rationale. Each phase adds one concise entry; never rewrite past decisions.

- 2026-11-04 — Created Vibe Kit 3.0 as an independent repository rather than modifying V2; retain V2 as a compatibility/reference source while the V3 codebase is rebuilt and validated in controlled phases.
- 2026-11-04 — Keep runtime dependencies empty; pytest is an optional test extra and CI-only requirement, preserving the local-first standard-library core.
- 2026-11-04 — Keep Phase 28 open until the new repository's remote CI matrix is actually observed green; local verification alone cannot establish cross-platform CI success.
