import hashlib
import json
import subprocess

import pytest

from vibe import approvals, governance
from .conftest import TTY, interactive_confirm, make_repo

KEY = "phase29-test-approval-key-material-0123456789abcdef"


def test_human_amendment_applies_exact_proposal_and_signs_digest(tmp_path):
    root = make_repo(tmp_path)
    proposal_dir = root / "docs/proposals"
    proposal_dir.mkdir()
    proposal_content = b"# Phase 29 revised\n\n**Status:** in progress\n"
    (proposal_dir / "phase-29-amend.md").write_bytes(proposal_content)
    env = {approvals.KEY_ENV: KEY}
    result = approvals.apply_amendment(
        root, "29", environ=env, stdin=TTY(), confirm=interactive_confirm("Teljo"),
    )
    assert (root / result["target"]).read_bytes() == proposal_content
    assert (root / result["archive"]).read_bytes() == proposal_content
    assert not (root / "docs/proposals/phase-29-amend.md").exists()
    record = json.loads((root / result["approval"]).read_text(encoding="utf-8"))
    staged_target = approvals.staged_bytes(root, result["target"])
    staged_archive = approvals.staged_bytes(root, result["archive"])
    assert staged_target == staged_archive
    valid, message = approvals.verify_record(
        record, KEY.encode(), "docs/phases/phase-29.md", hashlib.sha256(staged_target).hexdigest(), "29"
    )
    assert valid, message
    assert record["archive_sha256"] == hashlib.sha256(staged_archive).hexdigest()
    assert record["proposal_sha256"] == result["proposal_sha256"]
    assert governance.check_governance(root) == (True, None)


def test_digest_mismatch_rejects_reuse_of_signed_approval(tmp_path):
    root = make_repo(tmp_path)
    content = b"# Exact approved contract\n"
    digest = hashlib.sha256(content).hexdigest()
    record = approvals.make_record("29", "docs/phases/phase-29.md", digest,
                                   "phase_amendment", "Teljo", KEY.encode(),
                                   proposal_sha256=digest, archive_path="docs/amendments/a.md")
    valid, _ = approvals.verify_record(record, KEY.encode(), "docs/phases/phase-29.md", digest, "29")
    assert valid
    changed = hashlib.sha256(content + b"changed\n").hexdigest()
    valid, message = approvals.verify_record(record, KEY.encode(), "docs/phases/phase-29.md", changed, "29")
    assert not valid
    assert "digest" in message


def test_agent_environment_and_non_tty_cannot_create_approval():
    with pytest.raises(approvals.ApprovalError, match="TTY"):
        approvals.require_human(stdin=object(), environ={}, confirm=interactive_confirm())
    with pytest.raises(approvals.ApprovalError, match="agent marker"):
        approvals.require_human(stdin=TTY(), environ={"CLAUDECODE": "1"}, confirm=interactive_confirm())


def test_wrong_digest_confirmation_does_not_apply_proposal(tmp_path):
    root = make_repo(tmp_path)
    directory = root / "docs/proposals"
    directory.mkdir()
    proposal = directory / "phase-29-amend.md"
    proposal.write_text("# Proposed\n", encoding="utf-8")
    prompts = iter(["I reviewed this exact content", "Teljo", "APPLY 29 000000000000"])
    with pytest.raises(approvals.ApprovalError, match="digest confirmation"):
        approvals.apply_amendment(root, "29", environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=lambda _: next(prompts))
    assert proposal.exists()
    assert "Proposed" not in (root / "docs/phases/phase-29.md").read_text(encoding="utf-8")


def test_amendment_apply_stages_only_the_reviewed_transaction(tmp_path):
    root = make_repo(tmp_path)
    proposal_dir = root / "docs/proposals"
    proposal_dir.mkdir()
    proposal = proposal_dir / "phase-29-amend.md"
    proposal.write_text("# Human revised phase\n", encoding="utf-8")
    (root / "README.md").write_text("unrelated work remains unstaged\n", encoding="utf-8")
    result = approvals.apply_amendment(
        root, "29", environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=interactive_confirm("Teljo"),
    )
    staged = approvals.staged_paths(root)
    assert result["target"] in staged
    assert result["archive"] in staged
    assert result["approval"] in staged
    assert "docs/proposals/phase-29-amend.md" not in staged
    assert "README.md" not in staged


def test_amendment_digest_tracks_git_normalized_bytes(tmp_path):
    root = make_repo(tmp_path)
    subprocess.run(["git", "config", "core.autocrlf", "true"], cwd=root, check=True)
    proposal_dir = root / "docs/proposals"
    proposal_dir.mkdir()
    proposal = proposal_dir / "phase-29-amend.md"
    proposal.write_bytes(b"# Windows line endings\r\n\r\n**Status:** reviewed\r\n")
    result = approvals.apply_amendment(
        root, "29", environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=interactive_confirm("Teljo"),
    )
    staged_target = approvals.staged_bytes(root, result["target"])
    staged_archive = approvals.staged_bytes(root, result["archive"])
    record = json.loads((root / result["approval"]).read_text(encoding="utf-8"))
    assert staged_target == staged_archive
    assert record["target_sha256"] == hashlib.sha256(staged_target).hexdigest()
    assert record["archive_sha256"] == hashlib.sha256(staged_archive).hexdigest()
    valid, message = approvals.verify_record(
        record, KEY.encode(), result["target"], hashlib.sha256(staged_target).hexdigest(), "29"
    )
    assert valid, message
