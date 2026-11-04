import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vibe import governance
from .conftest import make_repo

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "plugins/vibe-kit/scripts/guard.py"


@pytest.mark.parametrize("tool", ["Write", "Edit", "NotebookEdit"])
def test_direct_agent_write_edit_of_phase_source_is_denied(tmp_path, tool):
    root = make_repo(tmp_path)
    decision = governance.evaluate_write(root, str(root / "docs/phases/phase-29.md"), tool, agent_role="subagent")
    assert decision["decision"] == "deny"
    assert "protected" in decision["reason"]


@pytest.mark.parametrize("suffix", ["context", "repair"])
def test_generated_phase_packs_remain_writable(tmp_path, suffix):
    root = make_repo(tmp_path)
    target = root / "docs/phases" / ("phase-29." + suffix + ".md")
    decision = governance.evaluate_write(root, str(target), "Write")
    assert decision["decision"] == "allow"


def test_proposal_is_allowed_as_non_authoritative_but_does_not_change_phase_scope(tmp_path):
    root = make_repo(tmp_path)
    target = root / "docs/proposals/phase-29-amend.md"
    target.parent.mkdir(parents=True)
    target.write_text("Read: docs/secrets.md\n", encoding="utf-8")
    decision = governance.evaluate_write(root, str(target), "Write")
    assert decision["decision"] == "allow"
    assert not governance.is_protected_path("docs/secrets.md")
    assert governance.check_governance(root)[0] is False


def test_malformed_payload_fails_closed_only_inside_vibe_project(tmp_path):
    root = make_repo(tmp_path / "vibe")
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    proc = subprocess.run([sys.executable, str(GUARD)], input="{not-json", text=True, capture_output=True, env=env)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    outside = tmp_path / "other"
    outside.mkdir()
    env["CLAUDE_PROJECT_DIR"] = str(outside)
    proc = subprocess.run([sys.executable, str(GUARD)], input="{not-json", text=True, capture_output=True, env=env)
    assert proc.returncode == 0
    assert proc.stdout == ""


def test_real_claude_pretooluse_payload_returns_official_deny_shape(tmp_path):
    root = make_repo(tmp_path)
    payload = {
        "hook_event_name": "PreToolUse",
        "cwd": str(root),
        "tool_name": "Write",
        "tool_use_id": "test-use",
        "tool_input": {"file_path": str(root / "docs/phases/phase-29.md"), "content": "tamper"},
        "agent_type": "subagent",
    }
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    proc = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload), text=True, capture_output=True, env=env)
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "phase-29.md" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_missing_write_path_and_corrupt_state_fail_closed(tmp_path):
    root = make_repo(tmp_path)
    missing = governance.evaluate_write(root, None, "Write")
    assert missing["decision"] == "deny"
    (root / "docs/state.json").write_text("{bad", encoding="utf-8")
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    proc = subprocess.run([sys.executable, str(GUARD)], input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": "x"}}), text=True, capture_output=True, env=env)
    assert "unreadable" in json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def test_path_outside_root_and_symlink_escape_are_denied(tmp_path):
    root = make_repo(tmp_path / "repo")
    outside = tmp_path / "secrets.txt"
    outside.write_text("secret", encoding="utf-8")
    decision = governance.evaluate_write(root, str(outside), "Write")
    assert decision["decision"] == "deny"
    try:
        (root / "docs" / "outside-link").symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("file symlinks are unavailable on this runner: " + str(exc))
    decision = governance.evaluate_write(root, str(root / "docs/outside-link"), "Edit")
    assert decision["decision"] == "deny"


def test_non_write_tool_and_unrelated_project_are_not_blocked(tmp_path):
    root = make_repo(tmp_path / "repo")
    assert governance.evaluate_write(root, "docs/phases/phase-29.md", "Read")["decision"] == "allow"
    other = tmp_path / "other"
    other.mkdir()
    assert governance.evaluate_write(other, "docs/phases/phase-29.md", "Write")["decision"] == "allow"

@pytest.mark.parametrize("tool,command", [
    ("Bash", "vibe amendment apply --phase 29"),
    ("Bash", "python -m vibe governance approve-staged"),
    ("PowerShell", "vibe hooks uninstall"),
])
def test_agent_cannot_call_human_approval_or_uninstall_commands(tmp_path, tool, command):
    from importlib.util import spec_from_file_location, module_from_spec
    core_path = ROOT / "plugins/vibe-kit/scripts/guard_core.py"
    spec = spec_from_file_location("guard_core_human_cmd_test", core_path)
    core = module_from_spec(spec)
    spec.loader.exec_module(core)
    root = make_repo(tmp_path)
    payload = {"tool_name": tool, "tool_input": {"command": command}, "agent_type": "subagent"}
    decision = core.decide(payload, root)
    assert decision["decision"] == "deny"
    assert "human" in decision["reason"]


def test_regular_shell_commands_are_not_blocked_by_human_command_guard(tmp_path):
    from importlib.util import spec_from_file_location, module_from_spec
    core_path = ROOT / "plugins/vibe-kit/scripts/guard_core.py"
    spec = spec_from_file_location("guard_core_safe_cmd_test", core_path)
    core = module_from_spec(spec)
    spec.loader.exec_module(core)
    root = make_repo(tmp_path)
    decision = core.decide({"tool_name": "Bash", "tool_input": {"command": "vibe status"}}, root)
    assert decision["decision"] == "allow"


def test_missing_tool_name_and_missing_shell_command_fail_closed(tmp_path):
    from importlib.util import spec_from_file_location, module_from_spec
    core_path = ROOT / "plugins/vibe-kit/scripts/guard_core.py"
    spec = spec_from_file_location("guard_core_malformed_test", core_path)
    core = module_from_spec(spec)
    spec.loader.exec_module(core)
    root = make_repo(tmp_path)
    assert core.decide({}, root)["decision"] == "deny"
    assert core.decide({"tool_name": "Bash", "tool_input": {}}, root)["decision"] == "deny"


def test_guard_core_rejects_incomplete_state_but_noops_for_unrelated_repo(tmp_path):
    from importlib.util import spec_from_file_location, module_from_spec
    core_path = ROOT / "plugins/vibe-kit/scripts/guard_core.py"
    spec = spec_from_file_location("guard_core_state_validation_test", core_path)
    core = module_from_spec(spec)
    spec.loader.exec_module(core)
    root = make_repo(tmp_path / "repo")
    (root / "docs/state.json").write_text(json.dumps({"schema": 1, "phase": "29"}), encoding="utf-8")
    decision = core.decide({"tool_name": "Write", "tool_input": {"file_path": "README.md"}}, root)
    assert decision["decision"] == "deny"
    outside = tmp_path / "outside"
    outside.mkdir()
    decision = core.decide({"tool_name": "Write", "tool_input": {"file_path": "README.md"}}, outside)
    assert decision["decision"] == "allow"
