# Vibe Kit 3.0 — Phase-by-Phase Implementation Prompts

Use these prompts with a coding agent working in the independent V3 repository `teljothomas/vibe-kit_3.0`. This repository is intentionally not a copy of V2: where a prompt names a V2 module that does not exist here, create the corresponding V3 implementation from scratch and use small V2 fixtures for migration tests. Preserve the technical specification, but do not assume the old source tree, CLI surface, hook scripts or 500+ test suite exists. Run **one prompt per session**, in numerical order. Do not paste all prompts into one session.

## Shared execution rules

These rules apply to every phase prompt below:

1. Work on a new feature branch from the current `main`; never commit directly to `main`, force-push, or deploy/publish a release.
2. Read the repository's current `AGENTS.md`, `docs/invariants.md`, `docs/state.json`, current phase/gate instructions and only the specific source/test files needed. Use `vibe status` and `vibe context` if the current repository protocol is scaffolded.
3. Treat `docs/contracts/` as byte-stable. Do not edit a frozen contract or invariant without a formal amendment and explicit human approval. The V3 technical specification is a proposal, not an override to repository governance.
4. First establish the real local baseline. Do not assume old test counts or GitHub Actions status are still current.
5. Use targeted diffs. Do not rewrite large files, rename unrelated modules, add dependencies, install optional tools into the runtime package, or expand scope.
6. Preserve Python 3.9 compatibility and the standard-library-only runtime unless the owner explicitly approves a separate protocol amendment.
7. Every phase needs a phase contract, focused tests, `scripts/gate` registration, evidence and one concise decision-log entry.
8. Do not read the raw historical build plan or the entire repository as a shortcut. Use bounded context and focused file inspection.
9. Do not claim a test or platform behavior was verified unless it was actually run. Report `unmeasured` when instrumentation is unavailable.
10. Finish with a short report: branch/commit, files changed, tests run and results, remaining risks, PR URL if created. Do not merge the PR.
11. This is an independent V3 implementation. Before each phase, compare the prompt's file map with the actual V3 tree. If a referenced V2 implementation file is absent, create the V3 module from scratch rather than importing/copying the entire V2 repository. Preserve V2 project compatibility through explicit migration fixtures and adapters.

---

## Prompt 28 — Stabilize the independent V3 foundation

```text
Implement and finish Vibe Kit 3.0 Phase 28 only. This is a clean repository, not a V2 working tree. Do not attempt to edit V2 paths such as tests/phase26/test_merge_check.py; the V3 repo starts with its own compact CLI, state validator, doctor, verify, test suite and gate.

First inspect AGENTS.md, docs/invariants.md, docs/phases/phase-28.md, pyproject.toml, vibe/, tests/, scripts/gate and both workflows. Establish the actual local baseline.

Scope:
- Keep runtime dependencies empty; pytest remains a test extra only.
- Keep a real CLI: --version, status, doctor --strict, verify.
- Ensure state validation rejects malformed/mismatched phase data.
- Keep Git fixture tests independent of the default branch name; test both main and master configuration.
- Ensure the dedicated gate workflow installs the project test extra (which installs pytest) before invoking the pytest-backed phase gate.
- Pin the gate workflow's Python version to 3.13, which is included in the portability matrix.
- Preserve the Ubuntu/macOS/Windows × Python 3.9/3.11/3.13 matrix.
- Use `python scripts/gate --phase 28` in workflow commands so Windows does not need to execute a shebang-only file directly.

Acceptance:
- `python -m pytest -q` passes.
- `python -m vibe --version`, `python -m vibe status`, `python -m vibe doctor --strict`, and `python -m vibe verify` work and return truthful results.
- `python scripts/gate --phase 28` passes and emits one concise summary line.
- Tests prove both main/master Git initialization paths and CI workflow dependency ordering.
- Runtime dependencies remain empty.
- Actual remote matrix results are green before Phase 28 is approved. Until then, leave docs/state.json status as in_progress and say remote CI is unverified.

Do not implement governance, event journaling, project graph, platform adapters or telemetry in this phase. Do not merge or release. Create a PR after the repository remote exists; report local checks and remote-check status separately.
```

## Prompt 29 — Protect phase contracts and governance

```text
Implement Vibe Kit 3.0 Phase 29 only: prevent an agent from editing the phase contract that defines its own allowed read scope or acceptance criteria.

First inspect the current governance defaults, project template, Claude guard, generated context/repair pack behavior, Git pre-commit implementation, approvals/signing format, and tests. Confirm the current real behavior before editing.

Core requirement:
- Protect phase source files such as docs/phases/phase-NN.md from direct agent Write/Edit operations.
- Do not block Vibe CLI generation of docs/phases/phase-NN.context.md or docs/phases/phase-NN.repair.md.
- Store agent-created change requests in a separate non-authoritative proposal location (for example docs/proposals/phase-NN-amend.md). A proposal is not permission to change the phase.
- Make the gate/pre-commit fail while an unresolved proposal exists.
- A human must apply/approve the actual contract change. Any signed approval must be bound to the exact diff/content digest and cannot authorize later edits to different content.

Inspect and reconcile these files:
- vibe/governance.py
- plugins/vibe-kit/templates/governance.json
- plugins/vibe-kit/scripts/guard.py
- vibe/githooks.py
- vibe/approvals.py and vibe/signing.py only if needed for digest-bound approval
- vibe/cli.py only if a dedicated human contract-approval command is necessary
- tests/phase29/
- docs/phases/phase-29.md, scripts/gate, docs/decisions.md

Important:
- Protected-path defaults must not silently diverge between governance loader, template, guard and Git hook.
- Review the current `pre_commit_check`: protected paths are only approval-gated under `human_gate == signed`. Ensure the two-layer protection claim is truthful. Implement an explicit human maintenance path rather than simply locking users out.
- Normalize Windows/POSIX paths, reject traversal/out-of-root paths, and test symlink escape behavior.
- A subagent read exemption must never exempt governance writes.
- If hook payload is malformed or state cannot be read in a project where Vibe is active, fail behavior must be explicit and conservative. Do not accidentally block every unrelated project on the machine.
- Clearly state that hooks/Git hooks are not an OS sandbox and cannot intercept every arbitrary shell/Python file operation.

Do not change docs/invariants.md or an existing frozen contract without first preparing a formal amendment and stopping for human approval. If the implementation needs that, report the exact amendment required; do not proceed around it.

Acceptance tests must include direct agent write denial, allowed generated packs, unresolved amendment blocking, digest mismatch rejection, human approval success, traversal, symlink, Windows separator/case behavior, and protected-path parity.

Create a PR, do not merge, and report actual conformance evidence and known limitations.
```

## Prompt 30 — Add bounded state and the event journal

```text
Implement Vibe Kit 3.0 Phase 30 only: preserve all V2 audit history in an append-only event journal and keep docs/state.json as a compact snapshot.

Begin by inspecting state.py, evidence.py, report.py, efficiency.py, approvals/rollback behavior, the frozen state schema, and all readers/writers of state['log']. Do not edit the frozen contract schema without an explicit protocol amendment.

Design:
- Add docs/events/ledger.jsonl as the durable append-only event history.
- Add vibe/events.py to append, validate, hash-chain, query and migrate events.
- Use deterministic IDs for imported legacy entries. Never invent original timestamps; use null for unknown event time and separately record import time.
- Migrate every existing state.log entry without loss or duplication.
- Make migration idempotent and provide a dry-run preview.
- Append/flush an event before atomically updating the compact state snapshot.
- Keep only a bounded recent history in the snapshot (initial target: five entries) after the event journal has been verified.
- Update report/efficiency/status/verify readers to use the journal where full history is required.
- Preserve evidence, approvals, signatures and rollback history.

Before changing docs/contracts/state.schema.json or the schema version, stop and request the formal amendment required by invariant 6. Do not hand-edit docs/state.json to simulate a migration.

Files likely involved:
- vibe/state.py, vibe/evidence.py, vibe/report.py, vibe/efficiency.py, vibe/cli.py
- new vibe/events.py
- new docs/contracts/event.schema.json (additive new contract)
- tests/phase30/
- docs/phases/phase-30.md, scripts/gate, docs/decisions.md

Acceptance:
- Import all current legacy log entries with exact phase/commit/evidence/approver values.
- Re-running migration creates no duplicates.
- Journal hash/sequence/schema verification detects altered records and broken links.
- Interrupted snapshot writes can be recovered by replay.
- 100 simulated phase completions stay under a documented state byte ceiling; label bytes as a proxy for tokens.
- Reports from pre-migration fixtures and migrated journal agree on historical phase facts.
- Rollback does not erase the journal.

Run the full suite and current phase gate. Create a PR; do not merge. Report migration preview and rollback evidence.
```

## Prompt 31 — Fix documentation drift and cache lifecycle

```text
Implement Vibe Kit 3.0 Phase 31 only: make current documentation match the implementation and make cache clearing/garbage collection correct.

Start by enumerating the real argparse tree and checking the documented commands/options. The frozen docs/contracts/cli.md describes an older contract; do not edit it without formal amendment.

Implement:
1. scripts/generate-cli-reference.py that builds docs/reference/cli.md from the real argparse parser. Keep parser definitions as the source of truth; do not create a second hand-maintained command registry.
2. A deterministic --check mode used in CI.
3. docs/reference/policy.md and, only if accurate, docs/reference/policy.schema.json. Test the parser's actual accepted top-level/nested keys against the reference/schema. Unknown keys should fail with a one-line actionable error.
4. Fix vibe/cache.py::clear so its documented scope includes nested answer-cache entries. Add a bounded cache GC operation with deterministic max-age/max-entry behavior. Do not delete event history, evidence, approvals, active context packs or pack locks as an accidental side effect.
5. Fix the inaccurate plugin manifest wording that says six interview questions while the current skill asks eight.
6. Update README/INSTALL to link to the generated current CLI reference and distinguish it from the historical frozen contract. Remove or qualify the untrue ~300-token state claim until Phase 30's tested byte limit exists.

Likely files:
- vibe/cli.py (minimal parser metadata hook only)
- scripts/generate-cli-reference.py
- docs/reference/cli.md, docs/reference/policy.md, optional policy.schema.json
- vibe/policy.py, vibe/cache.py, vibe/doctor.py
- plugins/vibe-kit/.claude-plugin/plugin.json
- README.md, INSTALL.md, tests/phase31/
- docs/phases/phase-31.md, scripts/gate, docs/decisions.md

Acceptance:
- CLI reference includes all actual commands/options and deterministic output.
- CI fails on deliberate documentation drift.
- Policy docs/schema and parser keys agree; unsupported nested keys are rejected.
- cache clear removes nested answer entries and no non-cache audit file.
- cache GC respects configured bounds and never deletes active pack/evidence artifacts.
- plugin metadata and skill question count are consistent.

Do not refactor unrelated CLI code or change frozen contracts. Run full tests, doctor --strict, verify, shims --check and phase gate. Create a PR; do not merge.
```

## Prompt 32 — Build the local project graph and smarter context selection

```text
Implement Vibe Kit 3.0 Phase 32 only: deterministic, offline project indexing and optional graph-aware context enrichment.

Start with vibe/context.py and the current pack tests. Preserve the existing packer as the correctness fallback. Do not use an LLM, external service, required binary or third-party dependency to build the graph.

Implement a standard-library-only local index:
- sqlite3 storage under .vibe/index/project.sqlite3;
- versioned schema and indexer metadata;
- content hashes and deterministic normalized paths;
- Python AST adapter for modules/classes/functions/methods/imports;
- conservative JS/TS import/export adapter (mark unresolved edges instead of guessing);
- file, symbol, test, package/config and phase-contract nodes;
- imports/contains/test-covers/declared-by-phase edges only where provenance exists;
- incremental updates for changed/deleted/renamed files;
- commands/API for build/status/impact only if the current CLI design requires them; document parser and command changes through the Phase 31 generated-doc process.

Integrate with context.py:
- Never remove phase file, explicit Read paths, required contracts or Build targets.
- Add only graph-ranked candidates within remaining byte budget.
- Deterministic ranking/tie-break and max depth/file/byte limits.
- Exclude secrets, ignored/vendor/generated files and any path escaping repository root.
- Missing/stale/corrupt/unsupported index falls back to existing context behavior with one concise diagnostic.
- Keep graph mode opt-in until Phase 34 has benchmark evidence.

Files likely involved:
- new vibe/index.py, vibe/graph.py, vibe/lang_python.py, vibe/lang_js.py
- vibe/context.py and .gitignore
- docs/reference/project-index.md
- tests/phase32/ and tests/fixtures/graph/
- docs/phases/phase-32.md, scripts/gate, docs/decisions.md

Acceptance:
- Offline index build with no added dependencies.
- Same source tree + indexer version yields deterministic graph/query output.
- Incremental edit/delete/rename works.
- Python relationships are AST-backed; unresolved JS/TS relationships are labelled.
- Impact query can locate relevant tests/dependencies missed by direct-import-only lookup in at least one fixture.
- Required context is never dropped; pack byte budget remains enforced.
- Stale/corrupt index safely falls back.
- Local SQLite files are ignored by Git and contain no raw source snippets or secrets.

Run graph tests plus full suite and phase gate. Create a PR; do not merge. Report measured pack sizes and graph-index timings, or mark them unmeasured.
```

## Prompt 33 — Add verified platform guard adapters

```text
Implement Vibe Kit 3.0 Phase 33 only: refactor the existing Claude guard behind a neutral decision engine and add platform adapters only where real pre-tool blocking is supported and tested.

Before coding, re-open each platform's official hook docs and record the exact URL, access date, event name, input schema, output schema, tool coverage, timeout behavior, fail-open/fail-closed semantics, project-level config support and subagent identity support. Do not rely on old examples or third-party summaries.

Target order:
1. Preserve Claude Code behavior through a thin adapter and shared core.
2. Cursor adapter.
3. Gemini CLI adapter.
4. GitHub Copilot adapter.
5. Codex adapter as experimental until a clean install/trust/conformance test passes.

Use one shared policy decision function. Platform adapters must only parse inputs, normalize tool/path/event names, call the shared decision logic and serialize platform decisions. Keep the guard distributable and standalone; governed projects must not need the Vibe Kit source tree on PYTHONPATH or a Vibe daemon.

Test at minimum:
- allowed read, denied out-of-scope read;
- protected phase source write denied;
- protected governance write denied even from a subagent;
- allowed generated context/repair pack behavior;
- prohibited approval/uninstall command;
- malformed payload and missing required path;
- traversal/out-of-root/symlink paths;
- unknown tool/event;
- hook crash and timeout behavior;
- clean install/uninstall and preservation of pre-existing configuration.

Only label an adapter Tier 1 if it blocks all required operation classes in the actual client runtime. If it only blocks shell or only supports observation, label it Tier 2/3 or unsupported. Disclose platform timeout/failure modes that can allow actions through. Hooks are not an OS sandbox.

Likely files:
- plugins/vibe-kit/scripts/guard_core.py and guard.py
- platform adapter modules/config under plugins/vibe-kit/
- docs/platforms/*.md and docs/reference/guard-contract.md
- tests/phase33/fixtures and conformance tests
- README.md, INSTALL.md, SECURITY.md
- docs/phases/phase-33.md, scripts/gate, docs/decisions.md

Do not add an MCP server, daemon, network dependency, or platform-specific dependency to the Vibe core. Create a PR; do not merge. Include exact client versions used for manual conformance and list any platform left experimental.
```

## Prompt 34 — Add local usage telemetry and a controlled V3 benchmark

```text
Implement Vibe Kit 3.0 Phase 34 only: privacy-preserving local usage accounting, correct quality-adjusted efficiency metrics and a reproducible pilot benchmark.

Begin by reviewing vibe/budget.py, vibe/efficiency.py, evidence sidecars, transcript parsing, current report output and the Phase 30 event journal. Preserve existing Claude parsing through regression fixtures.

Usage design:
- Add a provider-neutral usage record and adapter interface.
- Keep raw input, output, cache-read and cache-write token counters separate.
- Add provider-specific adapters only for transcript formats that are actually verified. Unknown/malformed formats return unmeasured; do not guess.
- Never apply Anthropic weights to another provider. Any cost-equivalent or USD calculation must include provider, model, pricing/weight table version and date; prefer provider-reported cost when available.
- Collect locally and opt-in. Do not save/upload raw prompts, completions, source, secrets or tool output. Write to ignored .vibe/telemetry storage.
- `tokens_per_approved_change` must count explicit human acceptance only; `(gate:off)` is not approval.
- Measure context selection/cache/hook metrics only from real counters. Otherwise keep null/source unmeasured.
- Add a versioned schema for efficiency sidecars before consuming them.

Benchmark design:
- Use matched project snapshots and identical tasks across a baseline arm, current Vibe arm, and Vibe+graph arm.
- Randomize/rotate run order to reduce first-run/learning bias.
- Keep model/provider/version, reasoning settings, task brief and acceptance rubric fixed within comparisons; record all deviations.
- Score accepted changes with tests plus an independent review rubric. Report defect/regression rates beside cost.
- Primary metric: measured USD per human-accepted change. If cost is unavailable, report raw provider token dimensions separately; do not fabricate a common cost unit.
- Label the first run a pilot. Do not claim a savings percentage or general performance improvement without adequate repeated matched trials and uncertainty reporting.

Likely files:
- vibe/usage.py and provider parsers such as vibe/usage_claude.py
- vibe/budget.py, vibe/efficiency.py, vibe/evidence.py, vibe/report.py
- docs/contracts/efficiency.schema.json and docs/reference/metrics.md
- scripts/benchmark.py, benchmarks/README.md, benchmarks/tasks/
- .gitignore and tests/phase34/
- docs/phases/phase-34.md, scripts/gate, docs/decisions.md

Acceptance:
- Existing Claude parser remains correct under fixtures.
- Unknown provider/format never crashes the CLI or invents spend.
- Provider-specific weighting/cost semantics are correct and versioned.
- Gate-off is not counted as human approval.
- Telemetry is opt-in and privacy tests prove raw prompt/response/code/secret data is not persisted.
- Efficiency sidecar validation rejects invalid shapes with a one-line message.
- Benchmark output can be reproduced from recorded metadata and reports uncertainty/limitations honestly.
- No percentage-saving claim is added to README unless the evidence supports it.

Run the complete suite, all conformance tests, doctor --strict, verify, shims --check and the Phase 34 gate. Create a PR; do not merge or publish V3. Report all measured and unmeasured metrics separately.
```

---

## Final execution instruction

Start with **Prompt 28 only**. Do not ask the coding agent to implement Phases 28–34 together. Review each phase's diff and evidence before starting the next prompt. A passing prompt response is not acceptance; the actual tests, CI and human review are the acceptance evidence.
