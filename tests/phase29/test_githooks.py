import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vibe import approvals, githooks
from .conftest import TTY, interactive_confirm, make_repo

KEY = "phase29-test-approval-key-material-0123456789abcdef"


def test_precommit_blocks_unresolved_proposal_and_unapproved_protected_file(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setenv(approvals.KEY_ENV, KEY)
    proposal_dir = root / "docs/proposals"
    proposal_dir.mkdir()
    (proposal_dir / "phase-29-amend.md").write_text("# Proposal\n", encoding="utf-8")
    ok, message = githooks.pre_commit_check(root)
    assert not ok and "unresolved amendment proposal" in message
    (proposal_dir / "phase-29-amend.md").unlink()
    (root / "docs/invariants.md").write_text("# Changed\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/invariants.md"], cwd=root, check=True)
    ok, message = githooks.pre_commit_check(root)
    assert not ok and "without a staged human approval" in message


def test_human_approval_allows_exact_staged_protected_path(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setenv(approvals.KEY_ENV, KEY)
    (root / "docs/invariants.md").write_text("# Human-reviewed update\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/invariants.md"], cwd=root, check=True)
    written = approvals.approve_staged_paths(
        root, environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=interactive_confirm("Teljo"),
    )
    assert written
    ok, message = githooks.pre_commit_check(root)
    assert ok, message


def test_staged_change_after_approval_is_blocked_by_digest(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setenv(approvals.KEY_ENV, KEY)
    (root / "docs/invariants.md").write_text("# Approved state\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/invariants.md"], cwd=root, check=True)
    approvals.approve_staged_paths(root, environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=interactive_confirm())
    (root / "docs/invariants.md").write_text("# Changed after approval\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/invariants.md"], cwd=root, check=True)
    ok, message = githooks.pre_commit_check(root)
    assert not ok and "digest" in message


def test_phase_amendment_approval_is_required_and_then_validates(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setenv(approvals.KEY_ENV, KEY)
    directory = root / "docs/proposals"
    directory.mkdir()
    (directory / "phase-29-amend.md").write_text("# Updated contract\n", encoding="utf-8")
    ok, message = githooks.pre_commit_check(root)
    assert not ok and "unresolved amendment proposal" in message
    approvals.apply_amendment(root, "29", environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=interactive_confirm())
    subprocess.run(["git", "add", "docs/phases/phase-29.md", "docs/amendments", "docs/approvals"], cwd=root, check=True)
    ok, message = githooks.pre_commit_check(root)
    assert ok, message


def test_installed_git_hook_blocks_unapproved_commit_and_allows_approved_one(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setenv(approvals.KEY_ENV, KEY)
    hook = githooks.install(root)
    assert Path(hook).is_file()

    (root / "docs/invariants.md").write_text("# Unapproved update\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/invariants.md"], cwd=root, check=True)
    env = os.environ.copy()
    env[approvals.KEY_ENV] = KEY
    blocked = subprocess.run(["git", "commit", "-m", "should be blocked"], cwd=root, env=env, text=True, capture_output=True)
    assert blocked.returncode != 0
    assert "without a staged human approval" in blocked.stderr

    approvals.approve_staged_paths(root, environ=env, stdin=TTY(), confirm=interactive_confirm())
    accepted = subprocess.run(["git", "commit", "-m", "approved protected update"], cwd=root, env=env, text=True, capture_output=True)
    assert accepted.returncode == 0, accepted.stderr + accepted.stdout
    assert githooks.uninstall(root) is True
    assert not Path(hook).exists()
