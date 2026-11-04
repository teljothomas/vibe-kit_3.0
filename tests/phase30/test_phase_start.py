import hashlib
import json
import shutil
from pathlib import Path

from vibe import approvals, events, githooks, phase, state
from tests.phase29.conftest import TTY, make_repo

KEY = "phase30-phase-start-test-key-0123456789abcdef"
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/phase30/fixtures/v2-state.schema2.json"
SCHEMA = ROOT / "docs/contracts/event.schema.json"


def _confirm(prompt):
    if "I reviewed this exact content" in prompt:
        return "I reviewed this exact content"
    if prompt.startswith("Reviewer name"):
        return "Teljo Test"
    if prompt.startswith("Review the phase scope"):
        return prompt.split("type ", 1)[1].rstrip(": ")
    raise AssertionError("unexpected prompt: " + prompt)


def test_phase_start_imports_history_and_signs_all_protected_outputs(tmp_path):
    root = make_repo(tmp_path)
    current = json.loads((root / "docs/state.json").read_text(encoding="utf-8"))
    current["status"] = "approved"
    current["last_gate"] = {"phase": "29", "status": "passed", "commit": "abc1234"}
    (root / "docs/state.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    (root / "docs/decisions.md").write_text("# Decision Log\n", encoding="utf-8")
    (root / "docs/contracts").mkdir()
    shutil.copyfile(SCHEMA, root / "docs/contracts/event.schema.json")
    (root / "docs/phase-plans").mkdir()
    plan = (
        "# Phase 30 — Event ledger\n\n**Status:** proposed\n\n"
        "## Purpose\nPreserve history and bound state.\n\n## Build\nImplement the V3 event ledger.\n"
    )
    (root / "docs/phase-plans/phase-30.md").write_text(plan, encoding="utf-8")
    (root / "tests/phase30/fixtures").mkdir(parents=True)
    shutil.copyfile(FIXTURE, root / "tests/phase30/fixtures/v2-state.schema2.json")

    prior_content = (root / "docs/phases/phase-29.md").read_bytes()
    prior_digest = hashlib.sha256(prior_content).hexdigest()
    prior_record = approvals.make_record("29", "docs/phases/phase-29.md", prior_digest,
                                         "phase_amendment", "Teljo Test", KEY.encode())
    (root / "docs/approvals").mkdir()
    (root / "docs/approvals/phase-29.json").write_text(
        json.dumps(prior_record, indent=2) + "\n", encoding="utf-8"
    )

    result = phase.start_phase(root, "30", environ={approvals.KEY_ENV: KEY}, stdin=TTY(), confirm=_confirm)
    assert result["phase"] == "30"
    active = (root / "docs/phases/phase-30.md").read_text(encoding="utf-8")
    assert "**Status:** in progress" in active
    schema_document = json.loads((root / "docs/contracts/event.schema.json").read_text(encoding="utf-8"))
    assert "Owner-approved additive Phase 30 event contract" in schema_document["$comment"]
    new_state = state.load(root / "docs/state.json")
    assert new_state["phase"] == "30" and new_state["status"] == "in_progress"
    assert new_state["legacy_history"]["imported_entries"] == 22
    assert events.verify_project(root)["events"] == 25
    assert execution_mode(root) == "supervised"
    ok, message = githooks.pre_commit_check(root)
    assert ok, message


def execution_mode(root):
    from vibe.execution import load_mode
    return load_mode(root)
