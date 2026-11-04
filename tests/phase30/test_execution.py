import os
import json

import pytest

from vibe import approvals, execution, githooks
from tests.phase29.conftest import TTY, interactive_confirm, make_repo

KEY = "phase30-execution-test-key-0123456789abcdef"


def _confirm_mode(prompt):
    if "I reviewed this exact content" in prompt:
        return "I reviewed this exact content"
    if prompt.startswith("Reviewer name"):
        return "Teljo Test"
    if prompt.startswith("To change execution mode"):
        return prompt.split("type ", 1)[1].rstrip(": ")
    if prompt.startswith("To authorize this exact decision"):
        return prompt.split("type ", 1)[1].rstrip(": ")
    raise AssertionError("unexpected prompt: " + prompt)


def test_new_projects_default_to_supervised_mode(tmp_path):
    root = make_repo(tmp_path)
    assert execution.load_mode(root) == "supervised"
    result = execution.evaluate_decision(root, "architecture")
    assert result["decision"] == "human_required"
    assert result["actor"] == "human"


def test_autonomous_mode_is_owner_signed_and_protected(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setenv(approvals.KEY_ENV, KEY)
    result = execution.set_mode(root, "autonomous", environ={approvals.KEY_ENV: KEY},
                                stdin=TTY(), confirm=_confirm_mode)
    assert result["mode"] == "autonomous"
    assert execution.load_mode(root) == "autonomous"
    record = json.loads((root / result["approval"]).read_text(encoding="utf-8"))
    staged = approvals.staged_bytes(root, "docs/governance.json")
    valid, reason = approvals.verify_record(
        record, KEY.encode(), "docs/governance.json",
        __import__("hashlib").sha256(staged).hexdigest(), "29",
    )
    assert valid, reason
    ok, message = githooks.pre_commit_check(root)
    assert ok, message


def test_autonomous_mode_delegates_only_scoped_noncritical_decisions(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs/governance.json").write_text(json.dumps({
        "schema": 1, "protected_paths": [], "execution_mode": "autonomous"
    }), encoding="utf-8")
    assert execution.evaluate_decision(root, "architecture")["decision"] == "delegated"
    assert execution.evaluate_decision(root, "phase_advance", gate_passed=False)["decision"] == "human_required"
    assert execution.evaluate_decision(root, "phase_advance", gate_passed=True)["decision"] == "delegated"
    assert execution.evaluate_decision(root, "architecture", within_phase_scope=False)["decision"] == "human_required"
    assert execution.evaluate_decision(root, "credentials")["decision"] == "human_required"
    assert execution.evaluate_decision(root, "production_release")["decision"] == "human_required"


def test_supervised_routine_decisions_are_recorded_but_important_decisions_wait(tmp_path):
    root = make_repo(tmp_path)
    routine = execution.record_decision(root, "tests", "Run unit tests")
    assert routine["decision"] == "allowed"
    important = execution.record_decision(root, "architecture", "Choose module boundaries")
    assert important["decision"] == "human_required"
    history = execution.events.read_events(root)
    assert [x["event_type"] for x in history] == ["decision_allowed", "decision_waiting_for_human"]


def test_human_decision_approval_is_digest_bound(tmp_path):
    root = make_repo(tmp_path)
    result = execution.approve_decision(root, "architecture", "Use an append-only event journal",
                                        environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=_confirm_mode)
    event = execution.events.read_events(root)[0]
    record = event["details"]["approval_record"]
    payload = event["details"]["decision"]
    digest = __import__("hashlib").sha256(execution._canonical(payload)).hexdigest()
    valid, reason = approvals.verify_record(
        record, KEY.encode(), "decision:29:" + digest[:12], digest, "29"
    )
    assert valid, reason
    assert result["decision"] == "human_approved"


def test_mode_change_rejects_non_tty_and_agent_marker(tmp_path):
    root = make_repo(tmp_path)
    with pytest.raises(approvals.ApprovalError, match="TTY"):
        execution.set_mode(root, "autonomous", environ={approvals.KEY_ENV: KEY}, stdin=object())
    with pytest.raises(approvals.ApprovalError, match="agent marker"):
        execution.set_mode(root, "autonomous", environ={approvals.KEY_ENV: KEY, "CLAUDECODE": "1"}, stdin=TTY())
