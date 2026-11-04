# Independent V3 rebuild notes

This repository is a new implementation, not a Git fork/copy of `teljothomas/vibe-kit`. The V2 repository is the reference implementation and migration source. The original repository has not been modified.

## Phase 28 adaptation

The V2-specific Phase 28 defects (the `master` hard-code in `tests/phase26/test_merge_check.py` and missing pytest installation in the gate workflow) could not be patched here because the corresponding V2 merge-check and test modules are not part of a clean V3 codebase. Instead, Phase 28 establishes the equivalent new-repository guarantees: branch-default-independent Git fixtures, CI workflow dependency-order tests, a clean CLI/state baseline, and a full OS/Python matrix. The remote matrix passed 9/9 on `main` and `phase/28-v3-foundation` at commit `a8bb5362ae028b4442867e054361787100d7f620`; the strict gate also passed. The repository owner explicitly authorized proceeding to Phase 29.

## Completed phases

- **Phase 28 — approved:** the final nine-job portability matrix and strict gate passed on 4 November 2026; the repository owner explicitly instructed proceeding to the next phase.
- **Phase 29 — implementation and remote validation in progress:** adds versioned governance defaults, protected phase contracts, a standalone Claude Code PreToolUse guard, non-authoritative proposals, HMAC digest-bound human approvals, and Git pre-commit enforcement. It must pass the full remote matrix and strict gate and then receive human review before being considered approved.

## Remaining phases

- **Phase 30:** create the V3 event ledger and bounded state lifecycle. Include a versioned importer for V2 `docs/state.json` schema 2. The V3 seed's schema 1 is temporary bootstrap state; its conversion must be explicit and lossless.
- **Phase 31:** create cache lifecycle and generated CLI/policy documentation from the V3 parser. Do not assume V2's cache module or full argparse tree is present.
- **Phase 32:** create the local deterministic SQLite project graph and graph-aware context packer.
- **Phase 33:** create the neutral guard decision API and platform adapters. Re-check official platform documentation at implementation time.
- **Phase 34:** create opt-in local provider usage adapters, privacy-safe telemetry, and controlled benchmark tooling.

## Source-of-truth order

1. Current V3 `AGENTS.md`, `docs/invariants.md`, and active phase contract.
2. `docs/v3-technical-spec.md` for architecture and acceptance outcomes.
3. `docs/v3-phase-prompts.md` for execution prompts, interpreted with this rebuild note.
4. V2 public source only when a phase explicitly needs compatibility/reference behavior.

Do not claim V2 compatibility until migration and conformance tests demonstrate it. Do not mark a phase approved solely because its local unit tests pass; verify all required gates, including remote CI where the phase requires it.
