# Canonical Invariants

These principles govern the Vibe Kit core. A rule should have one canonical home; enforcement belongs in code where deterministic enforcement is possible.

1. No required server, daemon, MCP service, or runtime network calls.
2. An agent cannot approve its own work or disable the mechanism that rejects it.
3. `vibe` is a machine-level tool, not a governed project's runtime dependency.
4. A project gate is language-native, deterministic, and has a simple pass/fail contract.
5. The runtime core uses only the Python standard library.
6. Published contracts are versioned and immutable without a formal, human-approved amendment.
7. Zero resident context at rest beyond the explicitly installed short instructions and invoked skills.
8. Every refusal explains the reason in one concise, actionable message.
9. Never spend model tokens on a decision a script, hook, schema, or test can settle deterministically.
10. Resident instruction budgets are bounded and checked automatically.
11. One rule, one canonical home; generated views must not become a second source of truth.
12. Context is packed and bounded; raw repository history/logs are not pasted into the main agent session.
13. Efficiency claims are measured or labelled unmeasured; byte/file proxies are never called token measurements.

## V3 requirements

- V3-R1: phase scope cannot be expanded by the agent governed by that scope.
- V3-R2: audit history is durable and append-only.
- V3-R3: current state is bounded while audit history is preserved.
- V3-R4: graph ranking may add context but cannot drop required context.
- V3-R5: indexing is deterministic for the same tree and indexer version.
- V3-R6: provider usage counters retain their distinct units and meanings.
- V3-R7: telemetry is private by default; raw prompts, code and secrets are excluded.
- V3-R8: platform enforcement claims require tested blocking behavior.
- V3-R9: recommendations never silently mutate policy.
- V3-R10: unknown, stale, unsupported and unmeasured states are explicit.

## Security boundary

Hooks, Git hooks, CI and branch rules are engineering guardrails, not an OS sandbox. A local user or arbitrary shell/Python process may bypass them. High-assurance use additionally requires OS/container sandboxing, restricted credentials, required reviews and protected branches.
