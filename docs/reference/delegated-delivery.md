# Delegated delivery

Canonical procedure for reviewing and merging `phase/NN-*` implementation PRs without a human click per PR. It is a narrow, owner-signed delegation; `AGENTS.md` carries the summary and this file the detail.

## Roles

| Role | May | May not |
|---|---|---|
| Implementing agent | Write code and tests in the phase scope, run gates, open the PR, fix review findings | Review, approve or merge its own PR; edit protected paths; hold `VIBE_APPROVAL_KEY` |
| Independent reviewer | Read the PR, contract, invariants and CI; run tests in a throwaway worktree; post one verdict comment | Edit the implementation; merge; reuse the implementer's session or context |
| Merge controller | Run `scripts/merge_controller.py merge` | Merge without a passing precondition set; override the script by calling `gh pr merge` directly |
| Human owner | Everything signed: governance, phase activation, protected-path approvals, releases, secrets | — |

The reviewer must be a separate Claude session or subagent started with fresh context and read-only tools. Its verdict is a PR comment containing one fenced block:

````
```vibe-review-verdict
{"schema":1,"head_sha":"<40-hex>","verdict":"approve","critical":0,"high":0,
 "reviewer_session":"<id>","implementer_session":"<id>","gate_result":"G-PASS phase-NN"}
```
````

`verdict` is `approve` or `changes_requested`. The reviewer produces `gate_result` by running the phase gate on that exact SHA. Medium and Low findings are listed in the comment body and either fixed or documented with rationale. Any new push changes the head SHA and voids earlier verdicts; the latest verdict for the head wins.

## Merge preconditions (enforced by `scripts/merge_controller.py`)

1. PR is open, not a draft, and targets `main`.
2. Branch matches `phase/3N-*` and the expected phase.
3. All ten required checks (`gate` plus the nine OS/Python matrix jobs) succeeded on the head SHA; no other check is failing or pending.
4. GitHub reports `mergeable == MERGEABLE`.
5. No unresolved review threads.
6. No file in the PR diff is a protected path under the policy loaded from current `origin/main`.
7. A verdict for the exact head SHA exists, is `approve`, reports zero Critical and zero High findings, names distinct reviewer and implementer sessions, carries `G-PASS phase-NN` for the PR's phase and post-dates the head commit.
8. The controller itself runs from a clean checkout of current `origin/main`, so a PR cannot change the rules that judge it.

On success it runs `gh pr merge --squash --match-head-commit <sha>`, confirms `MERGED`, confirms the merge commit is an ancestor of `origin/main`, and prints the evidence as JSON. `post-merge --sha` then waits for CI on the merge commit. Merge evidence is copied to the PR and to the completion report.

## Why Invariant #2 holds

- The implementer cannot approve: only a separate session can post a verdict that the controller accepts, and the verdict binds one SHA, so any later edit invalidates it.
- The mechanism that rejects work cannot be disabled by the agent it governs: the controller, its tests, this procedure, `AGENTS.md` and `CLAUDE.md` are protected paths, changeable only by owner-signed approval. A PR touching them is refused by the controller and merged by the owner.
- Phase scope, signed activation, protected-path approvals, the no-force-push rule and the release prohibition are unchanged.

## What the owner still does

- Signs this amendment, each phase activation, each protected-path approval and each phase closeout. These need `VIBE_APPROVAL_KEY`, which no agent holds.
- Merges any PR the controller refuses because it changes a protected path. A phase PR that adds a gate to `scripts/gate`, edits `vibe/cli.py` or touches a workflow is such a PR.
- Approves releases and any credential, security-boundary or destructive action.

## Residual risks

- Reviewer independence is procedural, not cryptographic. A single GitHub account authors the PR, the verdict and the merge, and verdict fields are self-asserted. The controller verifies binding, freshness, CI and shape; it cannot prove a separate mind produced the verdict. Hardening: a second GitHub identity as reviewer plus branch protection that requires its approval, configured by the owner.
- Approval-record HMACs are not verifiable in CI without placing `VIBE_APPROVAL_KEY` where PR code could reach it, so protected-path PRs are routed to the owner rather than trusted on digest alone. An opt-in design using a `pull_request_target` workflow that verifies records from base-branch code is possible; it needs an owner credential operation and is not part of this amendment.
- `main` currently has no branch protection. The controller is a guardrail like the hooks, not a sandbox (Security boundary in `docs/invariants.md`).
- The required-check list is fixed to the Phase 28 CI matrix; changing the matrix requires changing the controller through a signed amendment.
