# Execution governance modes

Vibe Kit has two owner-controlled modes. A fresh V3 project defaults to **supervised**.

## Supervised — Human Approval ON

Routine implementation, tests, formatting and bug fixes can proceed. Important decisions are recorded as waiting for a human decision. The owner authorizes the exact decision using an interactive TTY confirmation and a digest-bound HMAC approval.

## Autonomous — Human Approval OFF

After the owner changes the mode through the signed CLI command, the agent may make delegated technical decisions inside the current approved phase. Every autonomous decision is recorded with actor `agent-autonomous`; it is never represented as human approval.

Delegated decision classes:
- Architecture choices within the active phase.
- Dependency selection within repository and runtime constraints.
- In-scope implementation and refactoring decisions.
- Test strategy and documentation choices.
- Phase advancement only after the required gate passes and the next phase is within an owner-approved roadmap.

Always human-controlled in both modes:
- Secrets, credentials and key rotation.
- Permission or security-boundary changes.
- Destructive actions and data deletion.
- External communications.
- Spending and financial commitments.
- Production releases.
- Changes to governance mode or protected contracts.

The mode cannot be changed by an agent. `vibe mode set` requires a human TTY, rejects common agent environment markers, asks for exact digest confirmation and writes an HMAC-signed approval record. The setting lives in the existing protected `docs/governance.json`; absence of the file means supervised mode.

## CLI

```powershell
python -m vibe mode show
python -m vibe mode set --mode supervised
python -m vibe mode set --mode autonomous

python -m vibe decision evaluate --class architecture --summary "Select module boundaries"
python -m vibe decision approve --class architecture --summary "Select module boundaries"

python -m vibe events verify
python -m vibe events migrate-v2 --input .\legacy-state.json --dry-run
python -m vibe events migrate-v2 --input .\legacy-state.json --apply
python -m vibe events replay
python -m vibe events rollback --reason "restore previous good snapshot"

python -m vibe phase start 30
```

The V3 core remains local-first and does not call GitHub or an external model. Autonomous mode delegates decision authority to the coding agent already running the workflow; it does not provide a remote agent runtime.

Autonomous mode does not override repository branch protection, required CI, the AGENTS.md merge boundary or human production-release controls. Merging is governed solely by the owner-signed delegation in `docs/reference/delegated-delivery.md`; any change to those boundaries requires a separate explicit owner decision.

Rollback is always human-controlled and requires an exact-content HMAC approval, regardless of the selected execution mode.
