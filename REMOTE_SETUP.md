# Create the GitHub remote for this local V3 repository

The connected GitHub integration available in this session can inspect and write files to an existing repository, but it does not expose a repository-creation action. The V3 source has therefore been prepared as a local Git repository with independent commits and a Phase 28 feature branch; no remote repository has been created or pushed.

1. Open https://github.com/new
2. Owner: `teljothomas`
3. Repository name: `vibe-kit_3.0`
4. Choose Public or Private. Public is suitable for the planned open-source distribution.
5. **Leave all initialization options unchecked** (no README, `.gitignore`, or license). This lets the existing local `main` branch be pushed as the first commit without unrelated-history conflicts.
6. Create the repository.
7. From the unzipped local repository, run:

```bash
git remote add origin https://github.com/teljothomas/vibe-kit_3.0.git
git push -u origin main
git push -u origin phase/28-v3-foundation
```

Or run `scripts/push-to-github.sh` after creating the empty remote. The feature branch contains Phase 28; do not merge it until GitHub Actions has passed.
