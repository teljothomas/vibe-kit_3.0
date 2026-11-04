# Vibe Kit 3.0 — Technical Specification and Delivery Plan

**Status:** V3 implementation baseline for the independent repository  
**Repository:** `teljothomas/vibe-kit_3.0` (new independent repository)  
**Reference baseline:** V2.2 main at `27a0487e9e3d26ecb91888192950e537be0717b5`; this SHA is a reference only, not this repository's history  
**Specification date:** 3 November 2026  
**Target:** Vibe Kit 3.0, delivered through small, independently verifiable phases

> This document is a proposal. It does not authorize direct changes to `main`, changes to protected contracts, a release, or deployment. Implement one phase per branch/PR and preserve the existing Vibe Kit workflow.

---

## 1. Executive direction

Evolve Vibe Kit from a phase-and-governance toolkit into a **lightweight AI Engineering Operating System** while retaining its defining properties:

- local-first; no server, daemon, or required network service;
- standard-library-only core;
- deterministic scripts and hooks for rules that can be enforced mechanically;
- compact, phase-scoped context rather than repository-wide prompt loading;
- human-controlled governance and explicit evidence;
- provider- and IDE-specific integrations that do not contaminate the portable core;
- efficiency claims backed by actual measurements, or explicitly marked unmeasured.

Vibe Kit should not become an autonomous coding agent or a large orchestration framework. It should provide the discipline, context, policy, evidence, and evaluation layer around the coding agent the developer already uses.

### 1.1 V3 capability model

| Capability | Responsibility | Primary implementation |
|---|---|---|
| Project intelligence | Understand files, symbols, tests, dependencies, and change impact | Local deterministic project index and dependency graph |
| Context intelligence | Assemble the smallest useful context while preserving required phase inputs | Existing packer plus graph-ranked candidates |
| Agent interoperability | Translate a common policy decision into each agent's hook protocol | Shared guard core and thin platform adapters |
| Governance | Protect phase contracts, policies, approvals, evidence, and human decisions | CLI, pre-tool hooks, Git hooks, CI and branch rules |
| Quality intelligence | Identify relevant tests and require evidence before accepting work | Impact analysis, test selection and independent review evidence |
| Learning and optimization | Measure usage, quality, rework and cost per accepted change | Local telemetry, evidence ledger and reproducible benchmarks |

### 1.2 Non-goals

V3 must not introduce:

- a Vibe-hosted cloud service, daemon, required MCP server, or network dependency;
- automatic model switching or provider API calls from the core CLI;
- silent edits to a project's `policy.yaml`, `governance.json`, contracts, or phase acceptance criteria;
- a claim that local hooks are a security sandbox;
- required third-party graph libraries, tokenizers, databases, telemetry services, or AI APIs;
- automatic acceptance of generated code based only on a passing test command;
- automatic application of model, budget, or policy recommendations without explicit human action.

Optional external integrations can be explored later, but core Vibe must work offline with Python's standard library.

---

## 2. Repository baseline and verified findings

The following V2 observations were checked against the public reference repository and GitHub Actions records on 3 November 2026. They are historical input to the independent V3 build, not claims about this repository. The workflow failures listed below are old records from 13 August 2026; they must be rerun before describing the current branch as healthy or unhealthy.

### 2.1 Baseline snapshot

| Item | Observed |
|---|---|
| Default branch | `main` |
| Observed `main` SHA | `27a0487e9e3d26ecb91888192950e537be0717b5` |
| Repository visibility | Public |
| Main branch protection | Enabled |
| Vibe project state | Phase `27`, status `approved` |
| State history | 22 entries; file size 9,542 bytes |
| Open PRs at inspection | None |
| Latest returned workflow runs | 13 August 2026; both failed |
| Current CLI implementation | 17 top-level subcommands (including `checkpoint`, `rollback`, `context`, `cache`, `budget`, `route`, and `merge-check`) |
| CLI contract document | Still describes an older, 10-command interface and an obsolete `shims --tools` option |

Useful source files include `AGENTS.md`, `docs/invariants.md`, `docs/meta-improvement.md`, `docs/state.json`, `vibe/context.py`, `vibe/budget.py`, `vibe/efficiency.py`, `vibe/cache.py`, `plugins/vibe-kit/scripts/guard.py`, and the two GitHub Actions workflows.

### 2.2 Confirmed CI failures and direct fixes

**Finding A — five merge-check tests assume `master`.** The test workflow explicitly sets `git init.defaultBranch main`. `tests/phase26/test_merge_check.py::make_repo_with_branches` nevertheless checks out `master`. The 13 August test logs show five failures with `pathspec 'master' did not match any file(s) known to git`; the other 528 tests passed and two were skipped on the sampled Ubuntu Python 3.9 job.

**Required correction:** capture the initial branch name immediately after the seed commit (`git branch --show-current`) and return to that branch after creating the test branches. Do not hard-code either `main` or `master` in the fixture. Add a regression test that runs with both `init.defaultBranch=main` and `init.defaultBranch=master`.

**Finding B — the Vibe gate workflow does not install `pytest`.** `.github/workflows/vibe.yml` checks out the repository, sets up Python, runs `python -m vibe verify`, and then runs `scripts/gate --phase <current>`. The gate invokes pytest for Phase 27, but the workflow has no pytest installation step. Its 13 August log shows `No module named pytest`.

**Required correction:** install only the test runner needed by the repository gate (`python -m pip install pytest`) before running the gate. Pin the workflow Python version to a version covered by the portability matrix (initially 3.13) rather than selecting an unbounded `3.x` that can move independently of the matrix. Do not add pytest as a runtime dependency of the packaged `vibe` CLI.

Sources: [test workflow run](https://github.com/teljothomas/vibe-kit/actions/runs/31655852310), [gate workflow run](https://github.com/teljothomas/vibe-kit/actions/runs/31655852316), [merge-check fixture](https://github.com/teljothomas/vibe-kit/blob/main/tests/phase26/test_merge_check.py), [test workflow](https://github.com/teljothomas/vibe-kit/blob/main/.github/workflows/test.yml), [gate workflow](https://github.com/teljothomas/vibe-kit/blob/main/.github/workflows/vibe.yml).

### 2.3 Additional confirmed design defects or gaps

1. **State is not bounded as advertised.** README describes `state.json` as roughly 300 tokens and capped by construction. The observed file is 9,542 bytes and has 22 history entries. `vibe/state.py::append_log` grows the list indefinitely. Do not discard history; move durable history to an append-only event journal and keep only a bounded recent summary in state.
2. **Phase contracts are not in the default protected-path list.** The active phase's `Read:` line is used to define the agent's read scope, yet the phase document itself is not included in `DEFAULT_PROTECTED_PATHS`. The agent must not be able to edit its own scope or acceptance contract. Protect phase source files separately from generated context/repair packs.
3. **The Git hook's protected-path behaviour is weaker than the README/invariant wording suggests.** `vibe/githooks.py::pre_commit_check` only requires an approval for `protected_paths` when `human_gate == "signed"`. This must be reconciled with the claim that two independent layers protect human-only governance artifacts. The fix must preserve an explicit, usable human change path; do not simply make protected files impossible to maintain.
4. **Cache clearing is incomplete.** `vibe/cache.py::clear()` deletes files directly under `docs/cache/` but does not recurse into `docs/cache/answers/`. A command named `cache clear` must either clear all cache entries or clearly document a narrower scope. V3 should make it complete and test nested paths.
5. **The efficiency metric can mislabel phases as approved.** `vibe/efficiency.py::_approved_phase_count` treats any non-empty `approved_by` as approval. The state history currently uses `(gate:off)` for phases where human approval was disabled. Those are not human approvals. Separate gate-passed work from human-approved work.
6. **Several efficiency metrics are explicitly unmeasured.** `context_selection_ratio`, `cache_hit_rate`, and `hook_block_rate` have no historical source yet. Add low-overhead local counters; retain `null` plus an explanatory source when measurement is unavailable.
7. **Efficiency sidecars have no formal schema.** `vibe/evidence.py::write_efficiency` writes the structure consumed by budget tuning and reports without schema validation. Add a versioned schema and validate before consuming it.
8. **CLI reference drift is known.** `docs/contracts/cli.md` is intentionally byte-stable and should not be patched casually. Create a generated current reference from the actual argparse tree, clearly label the frozen file as the original contract snapshot, and add a drift check.
9. **Plugin metadata conflicts with its actual interview.** `plugins/vibe-kit/.claude-plugin/plugin.json` says six questions, while `vibe-init/SKILL.md` asks eight. Correct the description and add a consistency test.
10. **State schema parity needs an explicit audit.** `vibe/state.py::new_state` includes a `rollbacks` field, while the frozen `docs/contracts/state.schema.json` uses `additionalProperties: false` and does not declare that field. Decide whether rollback history moves fully into the event journal or the schema receives an approved new version; do not leave code and schema describing different state shapes.
11. **Platform support must be based on observed capability, not marketing claims.** The current full blocking guard is Claude-specific. Other clients must not be called Tier 1 until the adapter can block the required tool classes and passes a conformance test against the installed client version.

---

## 3. Design principles and invariants

Retain the 13 current invariants as the foundation. Any change to invariants 1, 2, 5, or 6 requires a documented protocol amendment and explicit human approval before implementation.

V3 adds the following **design requirements**, which do not replace the existing invariants:

| ID | Requirement | Testable interpretation |
|---|---|---|
| V3-R1 | No self-authorized scope expansion | Agent tool writes to phase source files are blocked; Git/CI layers detect unauthorized changes |
| V3-R2 | Durable audit history | Every gate/approval/rejection/rollback transition is recorded before the compact snapshot is updated |
| V3-R3 | Bounded resident state | The compact state snapshot has a tested byte ceiling and bounded event summary |
| V3-R4 | Required context is never dropped | Graph ranking can add context but cannot remove phase-required inputs or contract content |
| V3-R5 | Deterministic indexing | Same repository tree and indexer version produce the same graph content and stable IDs |
| V3-R6 | Provider-neutral accounting | Raw input/output/cache counters remain separate; unknown units are never added together |
| V3-R7 | Privacy by default | Raw prompts, code snippets, transcript text, and secrets are never copied into telemetry |
| V3-R8 | Adapter honesty | A platform receives a Tier 1 label only after its real blocking capability is tested |
| V3-R9 | No hidden policy mutation | Recommendations are read-only until an explicit human command changes configuration |
| V3-R10 | Failure transparency | Unknown, stale, unsupported, or unmeasured conditions are reported explicitly, never silently treated as success |

### 3.1 Security boundary statement

Vibe hooks and Git hooks are engineering guardrails, not an operating-system sandbox. They can be disabled or bypassed by users with local control, and hooks cannot reliably intercept every possible way of reading or writing files (for example, arbitrary shell/Python code). The product must state this plainly. For genuinely hostile-code or high-assurance environments, users must additionally use OS/container sandboxing, restricted credentials, repository rules, required reviews, and protected branches.

---

## 4. Target architecture

### 4.1 Keep the portable core small

The existing CLI remains the entry point. The V3 additions are local libraries invoked by explicit commands or the existing context/gate/report paths. No background process is required.

```text
vibe CLI
  ├── state + event journal
  ├── policy + governance
  ├── context packer
  │     └── local project index / dependency graph
  ├── cache lifecycle
  ├── provider usage adapters (opt-in, local files only)
  ├── evidence + efficiency reports
  └── guard decision engine
          ├── Claude Code adapter
          ├── Cursor adapter
          ├── Gemini CLI adapter
          ├── GitHub Copilot adapter
          └── Codex adapter (experimental until conformance passes)

Git hooks + CI remain independent enforcement backstops.
```

### 4.2 Project index and dependency graph

Implement the first indexer as deterministic static analysis. Do not use an LLM to construct or maintain the graph.

**Initial node types**

- file;
- Python module, class, function and method;
- JavaScript/TypeScript module and exported symbol where parsable;
- test file and test function;
- package/configuration file;
- phase contract and declared Build target.

**Initial edge types**

- imports / depends-on;
- defines / contains;
- test-covers (only when grounded in imports, explicit mapping, or an observed trace);
- declared-by-phase;
- changed-with (observed Git diff only; not a permanent dependency claim).

Each node/edge must carry provenance and confidence. Do not invent call edges from names alone. Python AST extraction is authoritative for supported Python syntax. TypeScript/JavaScript import extraction can initially be conservative and regex/parser-light; unresolved imports must be marked unresolved, not guessed. Other languages return `unsupported` until an adapter exists.

**Storage**

- Use `sqlite3` from the Python standard library for the local index.
- Store the database under `.vibe/index/project.sqlite3` and ignore that directory in Git.
- Store a schema version, indexer version, repository tree/commit fingerprint, file hashes, nodes, edges and diagnostics.
- Update incrementally when source hashes change; remove nodes for deleted files.
- Never place raw source snippets or prompt text into the index.
- Never commit the index database.

**Graph-aware context rules**

1. The phase file, its explicitly declared `Read:` files, and required contracts remain mandatory.
2. Existing `Build:` targets and directly relevant tests keep their current priority.
3. Graph candidates may be added only from the remaining context budget.
4. Candidate ranking is deterministic: direct import/dependency, test coverage evidence, changed-file relationship, then configured module roots. Tie-break lexicographically by normalized path.
5. Enforce maximum graph depth, candidate count and bytes; expose the truncation reason in pack metadata.
6. Skip secrets, ignored paths, vendored dependencies, generated output and files outside the repository root.
7. A stale or missing index falls back to the current packer and emits one concise diagnostic. It must never block ordinary context generation.
8. The graph may recommend a file for a future phase amendment, but it cannot expand the active phase's allowed `Read:` list itself.

### 4.3 State and event journal

Introduce an append-only event ledger as the durable history and retain `docs/state.json` as a compact, machine-readable current snapshot.

**Suggested event file:** `docs/events/ledger.jsonl`  
**Suggested schema:** `docs/contracts/event.schema.json` (new schema; existing contracts remain byte-stable unless a formal amendment approves otherwise)

Minimum event types:

- `gate.started`;
- `gate.completed`;
- `phase.approved`;
- `phase.rejected`;
- `phase.advanced`;
- `rollback.created`;
- `rollback.restored`;
- `contract.change.proposed`;
- `contract.change.approved`.

Each event includes `schema`, `seq`, `event_id`, `type`, `phase`, `occurred_at`, `actor`, `commit`, `evidence_ref`, `source`, `details`, `prev_hash`, and `event_hash`. Optional data must be explicit `null`/absent, not fabricated. Hashes provide tamper evidence, not proof of identity; signed approvals remain the identity mechanism.

**Write ordering:** append and flush the event first; then atomically replace the compact `state.json` snapshot. If snapshot writing fails, the event remains durable and `vibe doctor`/`vibe repair-state` can rebuild the snapshot. Never advance state before the corresponding evidence/event has been safely written.

**Legacy migration:**

1. Back up `docs/state.json` before migration.
2. Convert every existing `state.log` entry to a deterministic imported event ID derived from canonical JSON plus phase/type.
3. Mark legacy entries with `source: "state-v2-log"`; do not invent an original event timestamp. Set `occurred_at: null` when the historical timestamp is genuinely unavailable and record `imported_at` separately.
4. Make migration idempotent. Re-running it must not duplicate events.
5. Compare old and new history counts, phase IDs, commit references, evidence references, approvals and rollback information.
6. Run `vibe verify` against the migrated ledger before compacting the state file.
7. Only after successful comparison, retain a bounded recent log (initial default: five entries) in state. All historic entries remain in the event ledger.
8. Add a documented rollback command/path that restores the backup and leaves the journal untouched.

Because `docs/contracts/state.schema.json` is frozen under the existing invariant, any new state schema version or altered state shape requires a formal amendment, a new schema version, migration tests and a human-approved decision record. Do not silently mutate the frozen schema.

### 4.4 Guard engine and platform adapters

Define a neutral internal request:

```text
GuardRequest:
  platform
  event
  tool_name
  operation            # read | write | shell | other
  target_paths[]
  cwd
  project_root
  agent_role           # main | subagent | unknown
  payload_valid
```

And a neutral result:

```text
GuardDecision:
  decision             # allow | deny | ask/unsupported
  policy_id
  reason                # one line
  severity
```

The decision engine is shared. Each adapter owns only:

- parsing its platform's stdin/event schema;
- mapping native tool names and paths into `GuardRequest`;
- serializing the decision in the platform's required JSON/exit-code format;
- platform/version metadata and test fixtures.

The adapter must not silently allow a malformed governance write request. If the hook is configured as fail-closed by the platform, use that setting for governance checks. If the platform has a timeout/failure mode that can allow a tool to proceed, disclose it and do not claim equivalent enforcement. Unknown tools and unsupported events must be treated conservatively and documented.

**Phase source protection:**

- protect phase source documents (for example `docs/phases/phase-NN.md`) from direct agent `Write`/`Edit` tools;
- do not accidentally block generated `phase-NN.context.md` and `phase-NN.repair.md` artifacts created by the Vibe CLI;
- route proposed changes to a separate, explicitly non-authoritative proposal location such as `docs/proposals/phase-NN-amend.md`;
- a proposal is not permission. The gate/pre-commit check must block completion/commit while an unresolved proposal exists;
- only a human-controlled action may apply the change to the actual phase contract and record the decision;
- normalize paths safely, handle Windows separators/case, reject traversal/out-of-root paths, and test symlink edge cases.

Protected-path parity must be tested across `vibe/governance.py`, the project template `plugins/vibe-kit/templates/governance.json`, the shipped guard, and Git hook enforcement. Do not maintain silently diverging default lists.

### 4.5 Usage telemetry and token economics

Usage collection is opt-in and local. V3 should introduce an adapter interface with provider/source metadata rather than assuming every agent stores Claude-shaped JSONL.

**Raw dimensions**

- input tokens;
- output tokens;
- cache-read tokens;
- cache-write/creation tokens;
- provider-reported cost (when available);
- provider/model/client;
- task/phase/stage;
- timestamp and source reliability.

Keep raw dimensions separate. Do not sum token types equally and label the result as cost. Do not apply Anthropic weights to OpenAI, Gemini, or other provider usage data. Cost-equivalent units may be computed only under an explicitly versioned provider pricing/weight table and must include the table version/date. Prefer provider-reported USD when it is available and trustworthy.

**Privacy rules**

- parse local transcript metadata only;
- never upload telemetry;
- never persist prompt bodies, assistant responses, source code, secrets, or raw tool outputs;
- write aggregates to ignored local storage such as `.vibe/telemetry/`;
- export only aggregate measurements into committed evidence sidecars after the user enables that option;
- clearly distinguish measured, estimated, proxy and unmeasured values.

**Primary product metric:** measured cost per human-accepted change, with quality outcomes reported beside it. A cheap session that produces rejected or defective output is not an efficiency gain.

### 4.6 Quality and verification

V3 should add evidence-based verification, not claim that a green test command proves correctness.

- Map each requirement/acceptance item to tests or an explicitly documented manual check.
- Use graph impact analysis to recommend tests; the phase gate remains authoritative.
- Never omit mandatory tests because an index is missing or incomplete.
- Record selected tests, skipped tests and the reason for each skip.
- Add independent review evidence for risk-sensitive changes.
- Preserve known defects and deviations in the report; do not turn them into passing criteria automatically.

### 4.7 Cache lifecycle

- Make `vibe cache clear` recursively clear all defined cache artifacts, with an explicit dry-run option if destructive scope is broad.
- Add a bounded `vibe cache gc` (or equivalent) for age/count limits on answer-cache entries.
- Do not evict current phase packs, event history, evidence, approval records or pack locks as a side effect of ordinary cache GC.
- Cache keys must include every factor affecting the result (file hash, question normalization, schema/indexer version and relevant policy version).
- Report cache hit/miss/stale/eviction counters without exposing the cached prompt or source content.

---

## 5. File-by-file implementation map

This is the intended change surface. The implementation agent must re-check the current tree before editing and may add files where tests prove they are required. It must not rewrite unrelated files or make speculative cleanups.

### Phase 28 — CI and portability baseline

| Path | Action | Reason |
|---|---|---|
| `tests/phase26/test_merge_check.py` | Edit | Remove hard-coded `master`; test both default branch names |
| `.github/workflows/vibe.yml` | Edit | Install pytest for the gate; pin Python to a tested matrix version |
| `.github/workflows/test.yml` | Review/edit only if needed | Preserve matrix coverage and ensure branch default test is explicit |
| `tests/phase28/` | Add | Regression tests for both CI defects and gate setup contract |
| `docs/phases/phase-28.md` | Add | Phase contract |
| `scripts/gate` | Edit only to register Phase 28 tests | Keep gate native, simple and one-line |
| `docs/decisions.md` | Append | Record why branch fixtures and gate dependencies were corrected |

### Phase 29 — governance and phase-contract integrity

| Path | Action | Reason |
|---|---|---|
| `vibe/governance.py` | Edit | Centralize/default protected path policy and phase-source rules |
| `plugins/vibe-kit/templates/governance.json` | Edit | Ensure new projects inherit the same policy |
| `plugins/vibe-kit/scripts/guard.py` | Refactor | Apply common path canonicalization and phase-source protection |
| `plugins/vibe-kit/scripts/guard_core.py` | Add if needed | Shared, standalone decision logic packaged with the plugin |
| `vibe/githooks.py` | Edit | Make Git enforcement parity explicit; require human approval for protected contract changes using a digest-bound path |
| `vibe/approvals.py`, `vibe/signing.py` | Edit only if required | Bind human approval to exact protected-file content/diff, not merely a phase number |
| `vibe/cli.py` | Edit only if a human contract-approval action is needed | Keep the approval route explicit and human-controlled |
| `docs/proposals/` | Add convention | Store non-authoritative amendment proposals separate from phase source |
| `tests/phase29/` | Add | Tool-write block, pre-commit block, signed human approval, path traversal, symlink and generated-pack exemptions |
| `docs/phases/phase-29.md`, `scripts/gate`, `docs/decisions.md` | Add/edit | Phase contract, gate registration, decision record |

### Phase 30 — bounded state and append-only event journal

| Path | Action | Reason |
|---|---|---|
| `vibe/state.py` | Refactor | Separate compact snapshot from durable history; add safe migration/atomic write |
| `vibe/events.py` | Add | Append, verify, query and migrate event journal |
| `vibe/evidence.py` | Edit | Link gate evidence to corresponding event IDs |
| `vibe/report.py` | Edit | Read durable event history rather than relying on an ever-growing state log |
| `vibe/efficiency.py` | Edit | Use journal data; distinguish gate pass from human acceptance |
| `vibe/cli.py` | Edit | Add read-only event/status diagnostics and safe repair/migration entry points only where needed |
| `docs/contracts/event.schema.json` | Add | New versioned event contract |
| `docs/contracts/state.schema.json` | **Amendment required before edit** | New state schema version only if the design changes the existing state shape |
| `docs/state.json` | Migrate through code, never hand-edit history | Preserve all 22 existing entries and any rollback data |
| `docs/events/ledger.jsonl` | Generate/migrate | Durable journal, append-only |
| `tests/phase30/` | Add | Idempotent migration, interrupted write, hash-chain verification, compactness, report parity and rollback |
| `docs/phases/phase-30.md`, `scripts/gate`, `docs/decisions.md` | Add/edit | Phase contract, gate registration, decision record |

### Phase 31 — documentation parity and cache correctness

| Path | Action | Reason |
|---|---|---|
| `vibe/cli.py` | Edit minimally | Expose parser metadata to a documentation generator without duplicating command definitions |
| `scripts/generate-cli-reference.py` | Add | Generate current CLI reference from argparse |
| `docs/reference/cli.md` | Generate/add | Canonical current command reference; do not overwrite frozen `docs/contracts/cli.md` |
| `docs/reference/policy.md` | Add | Document supported policy keys and precedence |
| `docs/reference/policy.schema.json` | Add if it can accurately describe the accepted subset | Machine-check the supported policy shape |
| `vibe/policy.py` | Edit only if parser/schema parity tests require it | Make accepted keys discoverable and reject unknown nested keys |
| `vibe/cache.py` | Edit | Recursive clear and bounded answer-cache garbage collection |
| `vibe/doctor.py` | Edit | Detect generated-doc drift, policy/schema drift and stale cache index metadata |
| `plugins/vibe-kit/.claude-plugin/plugin.json` | Edit | Remove incorrect question count and synchronize plugin description |
| `tests/phase31/` | Add | CLI reference determinism, stale-doc check, policy parser/schema parity, recursive cache-clear and GC safety |
| `README.md`, `INSTALL.md` | Edit | Point readers to current generated docs and clarify frozen historical contract |
| `docs/phases/phase-31.md`, `scripts/gate`, `docs/decisions.md` | Add/edit | Phase contract, gate registration, decision record |

### Phase 32 — deterministic project graph and context intelligence

| Path | Action | Reason |
|---|---|---|
| `vibe/index.py` | Add | Index lifecycle, versioning, file hashes, diagnostics |
| `vibe/graph.py` | Add | Nodes, edges, deterministic ranking and impact queries |
| `vibe/lang_python.py` | Add | Python AST symbols/import relationships |
| `vibe/lang_js.py` | Add | Conservative JavaScript/TypeScript import/export extraction |
| `vibe/context.py` | Edit | Add graph-ranked context candidates without dropping required context |
| `vibe/cache.py` | Edit only if index cache shares lifecycle primitives | Avoid duplicating cache expiry/metadata logic |
| `.gitignore` | Edit | Ignore `.vibe/index/` and generated index artifacts without ignoring signer files |
| `docs/reference/project-index.md` | Add | Index format, supported languages, limitations and rebuild procedure |
| `tests/phase32/` | Add | Graph determinism, incremental update, delete/rename, unresolved import, path escape, ranking, budgets and stale-index fallback |
| `tests/fixtures/graph/` | Add | Small cross-language sample repositories |
| `docs/phases/phase-32.md`, `scripts/gate`, `docs/decisions.md` | Add/edit | Phase contract, gate registration, decision record |

### Phase 33 — multi-agent guard adapters

| Path | Action | Reason |
|---|---|---|
| `plugins/vibe-kit/scripts/guard_core.py` | Add/refine | Platform-neutral policy decision engine, standalone at install time |
| `plugins/vibe-kit/scripts/guard.py` | Refactor | Preserve Claude compatibility through an adapter |
| `plugins/vibe-kit/adapters/claude.py` | Add if separation is useful | Claude event payload/decision translation |
| `plugins/vibe-kit/adapters/cursor.py` | Add | Cursor beforeReadFile/beforeShellExecution adapter |
| `plugins/vibe-kit/adapters/gemini.py` | Add | Gemini CLI BeforeTool adapter |
| `plugins/vibe-kit/adapters/copilot.py` | Add | Copilot preToolUse adapter |
| `plugins/vibe-kit/adapters/codex.py` | Add as experimental | Codex hook/plugin adapter, gated on install/trust conformance |
| `plugins/vibe-kit/templates/` | Add per-platform configs | Generate only verified configuration for the chosen platform |
| `docs/platforms/*.md` | Add | Version/date checked capability matrices and setup/troubleshooting |
| `docs/reference/guard-contract.md` | Add | Neutral input/output schema and adapter conformance contract |
| `tests/phase33/fixtures/` | Add | Recorded, sanitized event payloads for every supported platform |
| `tests/phase33/` | Add | Allow/deny, malformed input, unknown tool, read/write, subagent, timeout and fail-closed contract tests |
| `README.md`, `INSTALL.md`, `SECURITY.md` | Edit | Publish only verified capability levels and explicit limitations |
| `docs/phases/phase-33.md`, `scripts/gate`, `docs/decisions.md` | Add/edit | Phase contract, gate registration, decision record |

### Phase 34 — provider usage telemetry, benchmark and release evidence

| Path | Action | Reason |
|---|---|---|
| `vibe/usage.py` | Add | Provider-neutral usage record and adapter interface |
| `vibe/usage_claude.py` | Extract/refactor from `vibe/budget.py` | Preserve known Claude transcript parsing |
| `vibe/usage_codex.py` | Add only after format is verified | Parse supported local Codex usage metadata |
| `vibe/usage_gemini.py` | Add only after format is verified | Parse supported local Gemini usage metadata |
| `vibe/budget.py` | Refactor | Keep raw token types separate and apply provider-specific accounting only when justified |
| `vibe/efficiency.py` | Refactor | Correct accepted-change semantics; calculate measured cache/context/hook metrics |
| `vibe/evidence.py` | Edit | Validate efficiency sidecar against a versioned schema |
| `docs/contracts/efficiency.schema.json` | Add | Versioned efficiency record schema |
| `scripts/benchmark.py` | Add | Reproducible paired benchmark runner or report collector |
| `benchmarks/README.md` and `benchmarks/tasks/` | Add | Task protocol, controls and task definitions |
| `.gitignore` | Edit | Ignore `.vibe/telemetry/` and local benchmark raw data |
| `tests/phase34/` | Add | Adapter parsing, missing usage, malformed records, privacy/redaction, measurement semantics, benchmark data validation |
| `docs/reference/metrics.md` | Add | Metric definitions, units, sources and caveats |
| `README.md`, `CHANGELOG.md`, `pyproject.toml`, plugin manifest | Edit at release only | Version and public claims after evidence is accepted |
| `docs/phases/phase-34.md`, `scripts/gate`, `docs/decisions.md` | Add/edit | Phase contract, gate registration, decision record |

---

## 6. Phase delivery plan and acceptance criteria

All phases follow the repository's existing one-phase-per-session protocol. Each phase must have its own contract, gate registration, tests, evidence, one-line decision record and PR. Do not combine these phases into one broad PR.

### Phase 28 — restore trustworthy CI

**Scope:** the two confirmed CI defects and a clean baseline.  
**Acceptance criteria:**

- The merge-check fixture passes when Git's initial branch is `main` and when it is `master`.
- The `vibe-kit gate` workflow installs pytest before executing a pytest-backed project gate.
- The gate workflow uses a Python version covered by the test matrix.
- All test matrix jobs pass on Ubuntu, macOS and Windows for Python 3.9, 3.11 and 3.13 (or explicitly documented support changes approved separately).
- `python -m vibe doctor --strict`, `python -m vibe verify`, `python -m vibe shims --check`, and the current `scripts/gate --phase 28` pass.
- No runtime dependency is added to Vibe Kit; pytest remains a development/CI dependency only.

**Tests:** run existing suite; add parameterized/default-branch regression; run both workflows; install/uninstall Git hooks on all supported OS runners; run strict doctor after hook installation.

**Exit:** all checks green on a feature branch and PR. No merge to main as part of this phase.

### Phase 29 — prevent self-authorized contract changes

**Scope:** active phase-source protection, consistent protected paths, a human-controlled amendment path and fail-closed handling for malformed governance inputs where the platform supports it.

**Acceptance criteria:**

- Direct agent Write/Edit of the active `docs/phases/phase-NN.md` is denied by the supported guard.
- Generated context/repair pack writes by the Vibe CLI still work.
- An amendment proposal is non-authoritative and cannot itself widen the active read scope.
- Gate and pre-commit fail while an unresolved amendment proposal exists.
- Applying a phase-contract change requires a human-controlled, digest-bound approval action; approval cannot be reused for a different file content/diff.
- Protected path defaults match across governance loader, project template, guard and Git hook tests.
- Relative traversal, absolute outside-root paths, Windows path case/separator variants and symlink escape attempts are handled consistently.
- Documentation clearly states that shell-level and OS-level bypasses remain possible; do not call this a sandbox.

**Tests:** neutral guard unit tests; real subprocess hook tests; staged protected-file tests with approval absent/present; changed-after-approval digest test; generated-pack exemption; malformed JSON and unreadable state behavior; path normalization tests on Windows and POSIX.

**Protocol amendment:** required before changing any frozen contract schema or the rule in `docs/invariants.md`.

### Phase 30 — bounded state with preserved audit history

**Scope:** event journal, safe v2 state migration, bounded current snapshot, report/verify updates.

**Acceptance criteria:**

- All 22 observed legacy entries are represented in the journal with unchanged phase/commit/evidence/approval data.
- Migration is idempotent and does not fabricate missing historical timestamps.
- Every new gate, approval, rejection, advance and rollback transition is journaled before the compact state write.
- An interrupted state write can be recovered by replaying/validating the journal.
- The compact state snapshot stays within a documented byte ceiling after 100 simulated phase completions. The byte ceiling is a proxy, not a measured token count.
- The bounded `log` in state remains useful for `vibe status`, but all historic reports derive from the journal.
- `vibe verify` validates event schema, sequence/hash chain, referenced evidence and approval consistency.
- A dry-run migration report shows exactly what would change before mutation.
- Rollback restores the previous state snapshot without deleting journal or evidence history.

**Tests:** migration on current fixture; repeated migration; truncated last JSONL line; duplicate IDs; altered event hash; wrong `prev_hash`; failed disk write; 100+ phase events; report parity; rollback and recovery.

### Phase 31 — documentation and cache integrity

**Scope:** keep current docs aligned with code, make policy accepted-key surface auditable, fix cache clear/GC.

**Acceptance criteria:**

- Generated `docs/reference/cli.md` lists all current top-level commands and options from the real argparse parser.
- Regeneration is deterministic; `--check` fails on drift and CI runs it.
- Frozen `docs/contracts/cli.md` is not rewritten; README clearly points to the generated current reference.
- Policy docs and optional JSON schema match accepted top-level and nested parser keys; unknown nested keys fail with a one-line diagnostic.
- `vibe cache clear` removes every cache artifact in its documented scope, including nested answer entries, while leaving evidence, events and approvals untouched.
- Cache GC has explicit age/count bounds and deterministic behavior; default operation cannot delete active phase pack/lock files.
- Plugin manifest no longer claims six questions when the skill asks eight.
- The README's 300-token state claim is removed or replaced with the tested state byte ceiling and clear proxy label.

**Tests:** parser-to-reference generation test; output golden test; drift test; nested policy key rejection; cache clear with nested answer files; cache GC ordering and safety; metadata consistency tests.

### Phase 32 — deterministic project graph and graph-aware context

**Scope:** standard-library local index, Python and conservative JS/TS adapters, deterministic graph ranking integrated as optional context enrichment.

**Acceptance criteria:**

- The index builds offline and without new dependencies.
- Index records content hashes and schema/indexer versions; changes, deletions and renames are detected.
- Rebuilding against the same source tree yields deterministic graph output and stable query ordering.
- Python imports/symbols are AST-backed. JS/TS unresolved imports remain unresolved rather than being guessed.
- Impact queries return source-grounded dependency/test relationships with provenance.
- Graph context only adds candidate files after mandatory phase inputs and Build targets are included.
- Pack size limits are always enforced; truncation is explicit and deterministic.
- Missing, stale, corrupt or unsupported index falls back to the current context builder.
- Index and temporary files are ignored by Git; no raw code snippets or secrets are copied into graph metadata.
- At least one fixture demonstrates a task whose relevant test and dependency files are found through the graph but not by the original direct-import-only heuristic.

**Tests:** same-tree determinism; incremental update; deleted file; renamed file; cycle; ambiguous import; unresolved import; cross-platform path; symlink/outside-root; graph depth and byte limits; stale/corrupt fallback; required-context preservation; security exclusion.

### Phase 33 — platform guard adapters

**Scope:** a shared neutral guard decision engine, Claude refactor and adapters for platforms with verified blocking hooks.

**Initial target order:** Claude regression-safe refactor, Cursor, Gemini CLI, GitHub Copilot, then Codex experimental. This is an implementation order, not a claim that every platform is equally enforceable.

**Acceptance criteria for each claimed Tier 1 adapter:**

- Official platform hook contract is re-checked and recorded with URL and date immediately before implementation.
- The adapter blocks a disallowed read, a protected write and a prohibited governance action using the actual client event format.
- Allowed operations still work.
- Malformed payload, missing path, path traversal and unknown-tool cases follow documented conservative behavior.
- The platform's fail-open/fail-closed behavior and timeout behavior are explicitly tested or disclosed.
- Subagent behavior is tested; a subagent read exemption never grants governance-write exemption.
- Installation/configuration is tested on a clean project and does not require a running Vibe service.
- A platform that cannot block all required operations is labelled Tier 2/3 only, not Tier 1.

**Tests:** sanitized payload fixtures per client, adapter unit tests, subprocess integration tests, install validation, and a small manual client conformance checklist. Do not state that an adapter is verified solely because its JSON fixture passes.

### Phase 34 — truthful usage telemetry and V3 benchmark

**Scope:** opt-in local usage adapters, correct cost semantics, quality-adjusted metrics and controlled benchmark evidence.

**Acceptance criteria:**

- Existing Claude usage parsing remains regression-tested.
- Each provider adapter records raw counters and source/version; unknown formats return `unmeasured` without crashing.
- Provider-specific weights/prices are never applied to another provider.
- The metric `tokens_per_approved_change` counts only explicit human acceptance, not `(gate:off)` or a gate pass.
- `cache_hit_rate`, `hook_block_rate` and context selection metrics are measured only from recorded counters; otherwise remain null/unmeasured.
- No raw prompt, response, code, secret or tool output appears in telemetry files.
- Telemetry is opt-in, local and ignored by Git by default.
- Benchmark report describes task set, project snapshot, agent/model/version, prompt settings, order/randomization, acceptance rubric, failures, cost source and sample size.
- Main metric is cost per accepted change, with regression/defect rate and gate pass rate beside it.
- The first benchmark is labelled a pilot; no percentage-saving or universal performance claim is published without sufficient matched trials and uncertainty reporting.

**Tests:** provider adapter fixtures; missing usage; duplicate records; provider weights; cost rounding; opt-in/off; privacy scan; gate-off not approved; unmeasured semantics; benchmark data schema; reproducibility of task assignment and summary.

---

## 7. Migration and compatibility strategy

### 7.1 Release sequence

1. Stabilize current 2.2 code and CI before any data format change.
2. Keep the V2 state reader available while the event journal is introduced.
3. Perform a read-only migration preview on a copy of a real project.
4. Back up state and verify existing evidence before migration.
5. Migrate legacy log entries deterministically; leave missing historical dates unknown.
6. Run old and new reports side by side and compare phase/approval/evidence counts.
7. Enable bounded snapshot writes only after the comparison passes.
8. Add V3 graph/index files as optional generated local data; old projects without an index remain fully supported.
9. Install platform adapters only when the user explicitly selects that platform; do not silently overwrite existing hook configs.
10. Introduce usage telemetry opt-in and keep it off by default.
11. Publish a V3 release only after all supported matrices and migration tests pass.

### 7.2 Backward compatibility

- Existing `docs/state.json` schema 2 projects must be readable and migratable.
- Existing phase files remain valid; new optional metadata must not be required for old projects.
- Existing three context tiers continue to work. Graph enrichment is opt-in until benchmark results justify a safe default.
- Existing `vibe context`, `vibe gate`, `vibe status`, `vibe verify`, `vibe report`, `vibe cache`, and budget commands retain their established semantics unless a deliberate deprecation is documented.
- Existing Claude plugin config remains installable during the adapter refactor.
- Existing evidence files are never rewritten merely to normalize optional fields.
- Existing `docs/contracts/` files are byte-stable unless a specific amendment is approved.

### 7.3 Rollback

- Every phase is a separate commit/PR and must be revertible independently.
- State migration must preserve a pre-migration backup and an append-only journal.
- Graph/index data can be deleted and rebuilt; it is not the audit source of truth.
- Platform adapter installation must back up pre-existing config and support uninstall/restore.
- Telemetry opt-out must stop collection and must not delete the user's pre-existing provider transcripts.
- Never force-push or rewrite `main` as part of this plan.

---

## 8. CI, quality and release gates

### 8.1 Required CI checks

- `python -m pytest -q` on Ubuntu/macOS/Windows and supported Python versions.
- `python -m vibe doctor --strict` after installing test dependencies and Git hooks.
- `python -m vibe verify`.
- `python -m vibe shims --check`.
- Current phase `scripts/gate --phase NN`.
- Generated CLI documentation drift check.
- Policy parser/schema parity check.
- Platform adapter conformance fixtures (no installed third-party client required for unit tests).
- Secret/privacy scan for committed files and telemetry fixtures.

Keep the required branch-protection check short and stable. The full portability matrix can remain a separate required check, but release readiness must include both.

### 8.2 Release checklist

A release candidate is eligible only when:

- all required checks are green on the exact release commit;
- `vibe doctor --strict`, `vibe verify`, `vibe shims --check` and the release phase gate pass;
- migration tests pass against a copy of a V2 project and preserve the audit trail;
- every published platform capability is backed by a tested adapter and a current official-documentation record;
- no unsupported platform is described as Tier 1;
- README claims match measured evidence;
- plugin manifest, Python package version and changelog are synchronized;
- release notes describe limitations and migration/rollback instructions.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope expands into a framework | Keep local CLI and standard-library core; reject daemon/server/MCP requirements |
| State migration loses audit evidence | Append journal first, preserve backup, compare legacy/new reports before compaction |
| Hooks provide false confidence | Explicitly state they are not a sandbox; require external controls for high-assurance environments |
| Platform hook schemas change | Pin tested capability records to versions/dates; adapter fixtures; mark stale adapters unverified |
| Graph adds irrelevant files | Required-context precedence, deterministic ranking, strict budgets, opt-in rollout and fallback |
| Token numbers become misleading | Preserve raw counters and provider/source metadata; use null when unknown; report actual USD only with a source |
| Telemetry exposes private data | Local-only, aggregate-only, opt-in, privacy tests and ignore rules |
| Frozen contracts conflict with V3 | Formal amendment before changing existing contract files; use additive new schemas where possible |
| More docs become duplicated | Generated current CLI reference, one canonical rule location and automated drift checks |
| One huge PR is hard to review | Seven independently gated phases and separate PRs |

---

## 10. Explicit decisions required before implementation

The implementation prompts in the companion file assume these defaults unless the repository owner changes them:

1. **Branching:** one feature branch and one PR per phase; never commit directly to `main`.
2. **Python support:** preserve 3.9, 3.11 and 3.13 until CI demonstrates that support should change.
3. **State journal:** append-only tracked `docs/events/ledger.jsonl`; compact state remains tracked.
4. **Graph:** standard-library-only SQLite local index under `.vibe/index/`; graph enrichment initially opt-in.
5. **Telemetry:** off by default; local-only; no raw prompts/responses/source text.
6. **Approval:** contract changes require explicit human approval bound to the exact change; the current `human_gate` mode for ordinary phase completion remains configurable.
7. **Platform scope:** Claude first, then Cursor, Gemini CLI and Copilot; Codex experimental until installed-client conformance is proven.
8. **Benchmark:** report a pilot honestly; do not publish a savings percentage without matched, repeatable evidence.

---

## 11. Official platform documentation to re-check before Phase 33

These are starting points checked on 3 November 2026. The phase implementation must re-open the pages and record the exact behavior/version at implementation time; hook schemas and defaults can change.

- Claude Code hooks: https://code.claude.com/docs/en/hooks
- Cursor hooks: https://prod.cursor.com/docs/hooks
- Gemini CLI hooks reference: https://geminicli.com/docs/hooks/reference/
- GitHub Copilot hooks reference: https://docs.github.com/en/copilot/reference/hooks-reference
- OpenAI/Codex plugin packaging and hooks: https://developers.openai.com/plugins/build/plugins
- OpenAI/Codex hooks overview: https://learn.chatgpt.com/docs/hooks

Do not treat a platform's existence of a `PreToolUse`/`preToolUse`-style event as proof of full Vibe compatibility. Confirm the required event coverage, path fields, blocking output, failure/timeout behavior, project-level installation, and subagent identity on the target client.

---

## 12. Definition of Vibe Kit 3.0 done

V3 is done when it is demonstrably better, not merely larger:

- CI is green and portable;
- phase specifications cannot be expanded by the agent that is governed by them;
- state remains compact while complete audit history is preserved;
- current CLI/policy documentation cannot silently drift from the implementation;
- context packs can use a deterministic project graph without losing required inputs;
- platform claims match real conformance tests;
- provider usage is captured privately and measured honestly;
- cost per accepted change and quality outcomes can be compared through a reproducible benchmark;
- V2 projects can migrate and roll back without losing approvals, evidence or history;
- no existing invariant has been silently weakened.

**Recommended execution order: Phase 28 → 29 → 30 → 31 → 32 → 33 → 34.** Do not begin Phase 32 or later while the baseline and governance integrity phases are incomplete.
