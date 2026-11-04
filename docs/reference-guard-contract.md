# V3 protected-write guard contract

## Claude Code adapter

The plugin registers a `PreToolUse` command hook for `Write`, `Edit` and `NotebookEdit`. Claude Code supplies JSON on stdin with `tool_name`, `tool_input`, and `cwd`; file tools provide an absolute `tool_input.file_path`. On Windows, file paths use backslashes, so the standalone guard canonicalizes separators and case before policy matching.

A denied call returns this shape:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "..."
  }
}
```

The guard is a no-op outside a project containing `docs/state.json`. Within a Vibe project, unreadable state, malformed write input, unsafe paths and malformed policy are denied. A subagent receives no exemption from governance write checks. The same adapter denies direct agent invocations of `vibe amendment apply`, `vibe governance approve-staged` and `vibe hooks uninstall`; a human must run those commands in a separate terminal. The guard does not implement phase read-scope restrictions in this phase.

## Path rules

- `docs/phases/phase-NN.md` is protected.
- `.context.md` and `.repair.md` phase artifacts are generated outputs and remain writable.
- `docs/proposals/phase-NN-amend.md` is writable but non-authoritative; its presence blocks verification/gate/pre-commit.
- Static defaults include state, invariants, decisions, governance policy, contracts, approval records, agent instructions, CI workflows, the gate, shipped guard/plugin implementation, approval CLI, and Phase 29 conformance tests.
- Relative traversal, paths outside the project root and symlink escapes are denied.

## Human maintenance

For a phase contract, propose the complete replacement at `docs/proposals/phase-NN-amend.md`, then have a human run `vibe amendment apply --phase NN` in an interactive terminal. For other protected staged files, a human reviews the staged contents and runs `vibe governance approve-staged`. Both workflows create HMAC-signed records over exact content hashes.

## Limitations

PreToolUse runs before supported tool calls. It does not intercept arbitrary Bash/PowerShell commands, Python scripts, external editors, file writes from unrelated processes, root/administrator actions, or hook disablement. Git hooks can be bypassed with `--no-verify` or by changing Git configuration. This is a workflow guardrail, not a security sandbox.
