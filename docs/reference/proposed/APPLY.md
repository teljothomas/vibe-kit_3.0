# Applying the delegated-delivery amendment (owner only)

Transient instructions; delete this directory in the same commit. Run in an interactive PowerShell session where `VIBE_APPROVAL_KEY` is set and no agent is running. Do not paste the key anywhere.

```powershell
git fetch origin
git switch governance/delegated-delivery
Copy-Item docs\reference\proposed\AGENTS.md AGENTS.md -Force
Copy-Item docs\reference\proposed\CLAUDE.md CLAUDE.md -Force
Copy-Item docs\reference\proposed\governance.json docs\governance.json -Force
git rm -r -q docs/reference/proposed
git add AGENTS.md CLAUDE.md docs/governance.json scripts/merge_controller.py tests/delegation docs/reference/delegated-delivery.md
python -m vibe governance approve-staged
git commit -m "chore(governance): delegate independent review and merge of phase PRs"
git push origin governance/delegated-delivery
```

`approve-staged` shows a digest to type; review the staged diff first (`git diff --cached`). Then merge the PR yourself; this amendment is not self-delegating. Verify afterwards with `python -m vibe governance check`, `python -m vibe doctor --strict` and `python -m pytest tests/delegation -q`.

If `git rm -r` of the proposed directory is rejected by the pre-commit guard, run `git rm` after `approve-staged` and amend the commit.
