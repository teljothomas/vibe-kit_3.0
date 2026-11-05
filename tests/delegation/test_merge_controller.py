"""Merge-controller decision tests; evaluate() is pure, so no network or gh is used."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "merge_controller.py"
spec = importlib.util.spec_from_file_location("merge_controller", SCRIPT)
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)

HEAD = "a" * 40
HEAD_TIME = "2026-11-05T10:00:00Z"
REVIEW_TIME = "2026-11-05T10:30:00Z"


def verdict(**overrides):
    body = {
        "schema": 1, "head_sha": HEAD, "verdict": "approve", "critical": 0, "high": 0,
        "reviewer_session": "reviewer-1", "implementer_session": "impl-1",
        "gate_result": "G-PASS phase-31",
    }
    body.update(overrides)
    return {"createdAt": REVIEW_TIME, "body": "review\n```vibe-review-verdict\n" + json.dumps(body) + "\n```\n"}


def make_pr(**overrides):
    pr = {
        "state": "OPEN", "isDraft": False, "baseRefName": "main", "headRefName": "phase/31-docs-policy-cache",
        "headRefOid": HEAD, "mergeable": "MERGEABLE", "files": [{"path": "vibe/docs_gen.py"}],
        "statusCheckRollup": [
            {"__typename": "CheckRun", "name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
            for name in sorted(mc.REQUIRED_CHECKS)
        ],
    }
    pr.update(overrides)
    return pr


def run(pr=None, comments=None, threads=(), protected=lambda p: False, phase="31"):
    return mc.evaluate(pr or make_pr(), [verdict()] if comments is None else comments,
                       list(threads), HEAD_TIME, protected, phase)


def test_all_preconditions_met_yields_no_failures():
    assert run() == []


@pytest.mark.parametrize("override,fragment", [
    ({"baseRefName": "develop"}, "does not target main"),
    ({"headRefName": "feature/x"}, "not a delegated"),
    ({"headRefName": "phase/32-graph"}, "does not match expected phase"),
    ({"state": "CLOSED"}, "not open"),
    ({"isDraft": True}, "not open"),
    ({"mergeable": "CONFLICTING"}, "mergeable"),
])
def test_pr_shape_failures(override, fragment):
    assert any(fragment in item for item in run(pr=make_pr(**override)))


def test_missing_or_failing_required_check_blocks():
    checks = make_pr()["statusCheckRollup"]
    remaining = [c for c in checks if c["name"] != "windows-latest / py3.9"]
    assert any("required check windows-latest / py3.9 is missing" in f for f in run(pr=make_pr(statusCheckRollup=remaining)))
    failing = [dict(c, conclusion="FAILURE") if c["name"] == "gate" else c for c in checks]
    assert any("check gate is FAILURE" in f for f in run(pr=make_pr(statusCheckRollup=failing)))
    pending = [dict(c, status="IN_PROGRESS", conclusion="") if c["name"] == "gate" else c for c in checks]
    assert any("gate is PENDING" in f for f in run(pr=make_pr(statusCheckRollup=pending)))


def test_unresolved_review_thread_blocks():
    assert any("unresolved review thread" in f for f in run(threads=[{"isResolved": True}, {"isResolved": False}]))


def test_protected_path_change_routes_to_owner():
    pr = make_pr(files=[{"path": "vibe/docs_gen.py"}, {"path": "scripts/gate"}])
    failures = run(pr=pr, protected=lambda p: p == "scripts/gate")
    assert any("human owner must merge" in f and "scripts/gate" in f for f in failures)


def test_missing_verdict_blocks():
    assert any("no independent review verdict" in f for f in run(comments=[]))


def test_verdict_for_other_head_is_ignored():
    assert any("no independent review verdict" in f for f in run(comments=[verdict(head_sha="b" * 40)]))


@pytest.mark.parametrize("override,fragment", [
    ({"verdict": "changes_requested"}, "latest verdict"),
    ({"critical": 1}, "Critical or High"),
    ({"high": 2}, "Critical or High"),
    ({"reviewer_session": "impl-1"}, "distinct reviewer"),
    ({"reviewer_session": ""}, "distinct reviewer"),
    ({"gate_result": "G-FAIL phase-31"}, "passing gate"),
    ({"gate_result": "G-PASS phase-30"}, "passing gate"),
    ({"gate_result": None}, "passing gate"),
])
def test_verdict_content_failures(override, fragment):
    assert any(fragment in f for f in run(comments=[verdict(**override)]))


def test_latest_verdict_wins_so_a_later_rejection_blocks():
    later = verdict(verdict="changes_requested")
    later["createdAt"] = "2026-11-05T11:00:00Z"
    assert any("latest verdict" in f for f in run(comments=[verdict(), later]))


def test_verdict_older_than_head_commit_blocks():
    stale = verdict()
    stale["createdAt"] = "2026-11-05T09:00:00Z"
    assert any("predates the head commit" in f for f in run(comments=[stale]))


def test_malformed_verdict_json_is_ignored():
    comment = {"createdAt": REVIEW_TIME, "body": "```vibe-review-verdict\n{not json\n```"}
    assert any("no independent review verdict" in f for f in run(comments=[comment]))


def test_required_checks_cover_the_ci_matrix():
    text = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    for name in sorted(mc.REQUIRED_CHECKS - {"gate"}):
        os_name, py = name.split(" / py")
        assert os_name in text and '"' + py + '"' in text
