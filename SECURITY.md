# Security boundary

Vibe Kit hooks and Git hooks are development guardrails, not a security sandbox. They cannot intercept arbitrary shell/Python file operations, unrelated processes, privileged users, `git -c core.hooksPath` overrides, or `git commit --no-verify`.

For stronger enforcement, combine them with OS/container sandboxing, restricted credentials, required GitHub reviews and protected branches. Do not put `VIBE_APPROVAL_KEY` in the repository or in agent-visible project configuration.

Report security issues privately to the repository owner before opening a public issue.
