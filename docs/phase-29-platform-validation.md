# Phase 29 — Platform validation notes

**Correction commit:** `541c30a1865e96f1f31d278fce2edf5bf42ca50d`  
**Branch:** `phase/29-governance-integrity`  
**Status:** local validation passed; corrected-head remote matrix still requires GitHub Actions execution.

## Windows defects found by the first pull-request matrix

1. **Git line-ending normalization:** on Windows with `core.autocrlf=true`, the amendment file was converted before entering the Git index. The approval signature had been calculated over the working-tree proposal bytes, while pre-commit checked the staged blob bytes. Phase amendment application now stages the target contract and its archive first, calculates both digests from `git show :path`, requires those staged blobs to match, and signs the staged digest. The raw proposal digest remains bound to the human's confirmation and is retained separately.
2. **Drive-qualified symlink escape:** the Windows drive-path branch previously used a lexical repository-prefix test. That could accept a path inside the repository which resolved through a symlink outside it. The path normalizer now resolves the drive-qualified path and checks the resolved location against the resolved repository root before returning a relative path.

## Corrected local evidence

- `python -m pytest -q`: 56 passed.
- `python -m vibe doctor --strict`: passed.
- `python -m vibe verify`: passed.
- `python scripts/gate --phase 29`: passed.
- A regression test sets Git `core.autocrlf=true` and verifies the signed target and archive digests against staged index bytes.

## Remote status

The first remote matrix identified the two Windows defects above. The corrective commit was then pushed to the PR branch. GitHub returned `action_required` for both pull-request workflows on that corrected head, without creating jobs. Therefore the nine-job cross-platform matrix for the corrective commit has not yet been observed and must not be marked as passed until those workflows run successfully.
