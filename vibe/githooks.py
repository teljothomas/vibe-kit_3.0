"""Portable V3 Git pre-commit enforcement for protected governance artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import approvals, governance, state

SENTINEL = "# vibe-managed"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)


def repository_root(start: str | Path = ".") -> Path:
    proc = _git(Path(start).resolve(), "rev-parse", "--show-toplevel")
    if proc.returncode:
        raise governance.GovernanceError("not inside a Git repository")
    return Path(proc.stdout.strip()).resolve()


def _staged_paths(root: Path) -> List[str]:
    proc = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=str(root), capture_output=True)
    if proc.returncode:
        raise governance.GovernanceError("could not inspect Git index")
    return [p.decode("utf-8", errors="surrogateescape") for p in proc.stdout.split(b"\x00") if p]


def _staged_bytes(root: Path, path: str) -> bytes:
    proc = subprocess.run(["git", "show", ":" + path], cwd=str(root), capture_output=True)
    if proc.returncode:
        raise governance.GovernanceError("could not read staged content for " + path)
    return proc.stdout


def _active_state(root: Path) -> Dict[str, object]:
    state_path = root / "docs" / "state.json"
    if not state_path.exists():
        return {}
    try:
        return state.load(state_path)
    except state.StateError as exc:
        raise governance.GovernanceError("Vibe state is present but unreadable: " + str(exc)) from exc


def _approval_records(root: Path, staged: List[str], phase: str) -> Dict[str, Dict[str, object]]:
    records: Dict[str, Dict[str, object]] = {}
    for path in staged:
        normalized = governance.normalize_relative_path(root, path)
        if not normalized.startswith("docs/approvals/") or not normalized.endswith(".json"):
            continue
        try:
            record = json.loads(_staged_bytes(root, path).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise governance.GovernanceError("staged approval record is invalid JSON: " + path) from exc
        target = record.get("target_path") if isinstance(record, dict) else None
        if not isinstance(target, str):
            raise governance.GovernanceError("staged approval record has no target_path: " + path)
        target = target.replace("\\", "/").casefold().strip("/")
        if target in records:
            raise governance.GovernanceError("multiple staged approvals target " + target)
        records[target] = record
    return records


def _verify_target_approval(root: Path, phase: str, target: str, data: bytes,
                            record: Dict[str, object], key: bytes, staged: List[str]) -> Optional[str]:
    digest = hashlib.sha256(data).hexdigest()
    ok, message = approvals.verify_record(record, key, target, digest, phase)
    if not ok:
        return message
    mode = record.get("mode")
    if governance.is_phase_source(target):
        if mode != "phase_amendment":
            return "phase source changes require a proposal-based amendment approval"
        archive_path = record.get("archive_path")
        proposal_sha = record.get("proposal_sha256")
        if not isinstance(archive_path, str) or archive_path not in staged:
            return "approved amendment archive must be staged with the phase contract"
        if not isinstance(proposal_sha, str) or hashlib.sha256(_staged_bytes(root, archive_path)).hexdigest() != proposal_sha:
            return "amendment archive digest does not match the signed proposal digest"
    elif mode != "protected_path":
        return "protected non-phase files require an explicit protected_path approval"
    return None


def pre_commit_check(root: str | Path = ".") -> Tuple[bool, Optional[str]]:
    """Check unresolved proposals and signed approvals for every protected staged file."""
    try:
        root = repository_root(root)
    except governance.GovernanceError as exc:
        return False, str(exc)
    if not (root / "docs" / "state.json").exists():
        return True, None  # no-op in unrelated repositories

    try:
        current = _active_state(root)
        phase = str(current["phase"])
        ok, reason = governance.check_governance(root)
        if not ok:
            return False, "pre-commit: " + str(reason)
        policy = governance.load_policy(root)
        staged = _staged_paths(root)
        records = _approval_records(root, staged, phase)
        approval_files = [p for p in staged if governance.normalize_relative_path(root, p).startswith("docs/approvals/")]
        protected_targets = []
        for path in staged:
            normalized = governance.normalize_relative_path(root, path)
            if normalized.startswith("docs/approvals/"):
                continue
            if governance.is_protected_path(normalized, policy):
                protected_targets.append((path, normalized))
        if approval_files and not protected_targets:
            return False, "pre-commit: an approval record cannot be committed without its protected target content"
        if not protected_targets:
            return True, None
        key = approvals.approval_key()
        expected_approval_files = set()
        for raw_path, normalized in protected_targets:
            record = records.get(normalized)
            if record is None:
                return False, "pre-commit: protected path " + normalized + " changed without a staged human approval"
            error = _verify_target_approval(root, phase, normalized, _staged_bytes(root, raw_path), record, key, staged)
            if error:
                return False, "pre-commit: " + normalized + " — " + error
            expected_approval_files.add(approvals.approval_path_for(root, phase, normalized))
        if not expected_approval_files.issubset(set(staged)):
            missing = sorted(expected_approval_files - set(staged))[0]
            return False, "pre-commit: signed approval must be staged with the protected file: " + missing
        return True, None
    except (governance.GovernanceError, approvals.ApprovalError, state.StateError, OSError) as exc:
        return False, "pre-commit: governance check failed closed — " + str(exc)


def _hook_source() -> str:
    return '''#!/usr/bin/env python\n# vibe-managed\nimport pathlib, subprocess, sys\nroot = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()\ncheck = subprocess.run([sys.executable, "-m", "vibe.githooks", "pre-commit"], cwd=root)\nif check.returncode:\n    sys.exit(check.returncode)\nprevious = pathlib.Path(__file__).with_name("pre-commit.pre-vibe")\nif previous.exists():\n    sys.exit(subprocess.run([str(previous)], cwd=root).returncode)\nsys.exit(0)\n'''


def install(repo_root: str | Path = ".") -> str:
    root = repository_root(repo_root)
    git_hooks = _git(root, "rev-parse", "--git-path", "hooks")
    if git_hooks.returncode:
        raise governance.GovernanceError("could not locate Git hooks directory")
    hooks_dir = Path(git_hooks.stdout.strip())
    if not hooks_dir.is_absolute():
        hooks_dir = (root / hooks_dir).resolve()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    backup = hooks_dir / "pre-commit.pre-vibe"
    if hook.exists() and SENTINEL not in hook.read_text(encoding="utf-8", errors="replace"):
        if backup.exists():
            raise governance.GovernanceError("pre-existing hook and .pre-vibe backup both exist; refusing to overwrite")
        hook.replace(backup)
    hook.write_text(_hook_source(), encoding="utf-8")
    try:
        hook.chmod(hook.stat().st_mode | 0o111)
    except OSError:
        pass
    return str(hook)


def uninstall(repo_root: str | Path = ".") -> bool:
    root = repository_root(repo_root)
    git_hooks = _git(root, "rev-parse", "--git-path", "hooks")
    if git_hooks.returncode:
        raise governance.GovernanceError("could not locate Git hooks directory")
    hooks_dir = Path(git_hooks.stdout.strip())
    if not hooks_dir.is_absolute():
        hooks_dir = (root / hooks_dir).resolve()
    hook = hooks_dir / "pre-commit"
    backup = hooks_dir / "pre-commit.pre-vibe"
    if not hook.exists() or SENTINEL not in hook.read_text(encoding="utf-8", errors="replace"):
        return False
    hook.unlink()
    if backup.exists():
        backup.replace(hook)
    return True


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    hook_name = args[0] if args else "pre-commit"
    if hook_name != "pre-commit":
        print("unsupported hook: " + hook_name, file=sys.stderr)
        return 2
    ok, message = pre_commit_check(Path.cwd())
    if not ok:
        print(message or "pre-commit: blocked", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
