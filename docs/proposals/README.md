# Phase amendment proposals

A proposal is non-authoritative. To propose a replacement for the current phase contract, create `docs/proposals/phase-NN-amend.md` containing the **complete replacement contents** of `docs/phases/phase-NN.md`.

Do not edit the phase source directly. While any non-README file remains anywhere under this directory, governance verification, the phase gate and Git pre-commit fail. The proposal does not alter the active read scope or acceptance criteria.

A human applies it from an interactive terminal with:

```bash
vibe amendment apply --phase NN
```

The command requires a private `VIBE_APPROVAL_KEY` of at least 32 UTF-8 bytes, a TTY, an exact digest confirmation and reviewer label. It archives the proposal under `docs/amendments/`, replaces the source file, creates a signed digest-bound record under `docs/approvals/` and stages only those related paths. The approval cannot be reused for different content.
