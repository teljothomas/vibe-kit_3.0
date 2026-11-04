# Vibe Kit 3.0

**A local-first engineering operating system for AI-assisted software development.**

Vibe Kit gives coding agents a disciplined project workflow: explicit phase contracts, bounded context, mechanically checked policies, verifiable evidence, and honest efficiency measurements. It does not replace Claude Code, Codex, Cursor, Gemini CLI, or the developer.

This is a **new, independent V3 codebase**. The original `teljothomas/vibe-kit` repository is the V2 reference and remains untouched. V3 uses the V2 implementation and its V3 technical specification as design references, but does not share Git history or modify the original repository.

## Design commitments

- Local-first; no required server, daemon, MCP service, or network access at runtime.
- Python standard-library-only runtime; test tools are development/CI dependencies only.
- Deterministic code for rules a script, schema, hook, or test can enforce.
- Compact, phase-scoped context; no automatic repository-wide prompt loading.
- Human-controlled governance and evidence-backed acceptance.
- Provider and IDE integrations remain isolated behind adapters.
- Efficiency claims are measured, or explicitly marked unmeasured.
- Hooks are guardrails, not an operating-system security sandbox.

## Current build status

The initial V3 foundation and Phase 28 portability scaffold are present. Phase 28 is **in progress** until its GitHub Actions matrix has run successfully on the new remote repository. Do not treat a local test run as proof of remote cross-platform conformance.

See:
- [`docs/v3-technical-spec.md`](docs/v3-technical-spec.md) — architecture, file map, acceptance criteria, migration and release strategy.
- [`docs/v3-phase-prompts.md`](docs/v3-phase-prompts.md) — one copy-ready implementation prompt per phase.
- [`AGENTS.md`](AGENTS.md) — compact contributor/agent protocol.
- [`docs/invariants.md`](docs/invariants.md) — canonical engineering invariants.
- [`docs/phases/phase-28.md`](docs/phases/phase-28.md) — current phase contract.

## Local setup

```bash
python -m venv .venv
# Activate the environment, then:
python -m pip install -e ".[test]"
python -m pytest -q
python -m vibe --version
python -m vibe doctor --strict
python -m vibe verify
scripts/gate --phase 28
```

Python 3.9+ is the current compatibility target. CI exercises Python 3.9, 3.11 and 3.13 on Ubuntu, macOS and Windows.

## Current commands

```bash
vibe --version
vibe status
vibe doctor [--strict]
vibe verify
```

The CLI surface will grow only with the phases in the V3 plan. Commands that are not implemented yet are intentionally not represented as working features.

## Development rules

One feature branch and one pull request per phase. Never commit directly to `main`, force-push, or publish a release from a phase implementation. Establish the real baseline before changing code, keep diffs focused, and do not claim an unrun test or platform capability is verified.
