# Vibe Kit governance guard plugin

This plugin provides a standalone Claude Code `PreToolUse` guard. Its `Write`, `Edit` and `NotebookEdit` matcher delegates to `scripts/guard.py`; the decision core does not import the machine-level `vibe` Python package.

The guard protects phase source contracts and governance paths. Generated phase `.context.md` and `.repair.md` files remain writable. Proposals under `docs/proposals/` are non-authoritative and block the gate until a human applies them.

Human phase amendment workflow:

1. Create the complete proposed replacement as `docs/proposals/phase-NN-amend.md`.
2. Set `VIBE_APPROVAL_KEY` in the human's shell to a private random value of at least 32 UTF-8 bytes. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. Do not put the value in the repository or an agent instruction file.
3. In an interactive human terminal, run `vibe amendment apply --phase NN`.
4. The command stages the phase contract, its archived proposal under `docs/amendments/` and the signed record under `docs/approvals/`; it leaves unrelated work unstaged. The pre-commit hook verifies the exact staged content digest.

For other protected files, stage the reviewed content and run `vibe governance approve-staged` from a human terminal. Hooks are not an OS sandbox; see the root `SECURITY.md`.
