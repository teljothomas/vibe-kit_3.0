# Independent V3 rebuild notes

This repository is a new implementation, not a Git fork/copy of `teljothomas/vibe-kit`. The V2 repository is the reference implementation and migration source. The original repository has not been modified.

## Phase 28 adaptation

The V2-specific Phase 28 defects could not be patched here because the corresponding V2 merge-check and test modules are not part of a clean V3 codebase. Instead, Phase 28 establishes equivalent new-repository guarantees: branch-default-independent Git fixtures, CI workflow dependency-order tests, a clean CLI/state baseline and a full OS/Python matrix. The remote matrix passed 9/9 on `main` and `phase/28-v3-foundation`; the strict gate also passed.

## Completed phases

- **Phase 28 — approved:** the final nine-job portability matrix and strict gate passed on 4 November 2026.
- **Phase 29 — approved:** governance integrity, protected phase contracts, standalone Claude Code guard, digest-bound owner approvals and Git pre-commit enforcement merged in PR #1. The signed Phase 29 closeout was merged in PR #2.

## Active implementation

- **Phase 30 — implementation in progress:** append-only hash-chained event ledger, lossless V2 schema-2 history import, bounded/recoverable state snapshots and owner-controlled supervised/autonomous execution modes. The verified V2 source has 22 log rows, including repeated entries for phases 16, 17 and 18 and three null historical timestamps. No legacy gate-off record is counted as a human approval.

## Remaining phases

- **Phase 31:** documentation generation, policy schema/audit and cache lifecycle.
- **Phase 32:** local deterministic SQLite project graph and graph-aware context packer.
- **Phase 33:** neutral guard decision API and verified platform adapters.
- **Phase 34:** opt-in local provider usage adapters, privacy-safe telemetry and controlled benchmark tooling.

## Source-of-truth order

1. Current V3 `AGENTS.md`, `docs/invariants.md` and active phase contract.
2. `docs/v3-technical-spec.md` for architecture and acceptance outcomes.
3. `docs/v3-phase-prompts.md` for execution prompts, interpreted with the V3 rebuild note.
4. V2 public source only when a phase explicitly needs compatibility/reference behavior.

Do not claim V2 compatibility until migration and conformance tests demonstrate it. Do not mark a phase approved solely because local unit tests pass; verify all required gates, including remote CI.
