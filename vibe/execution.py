"""Owner-controlled execution governance mode and decision classification."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import approvals, events, state

POLICY_PATH = Path("docs/execution-policy.json")
DEFAULT_MODE = "supervised"
ROUTINE = {"routine", "formatting", "tests", "bugfix", "implementation"}
DELEGABLE = {"architecture", "dependencies", "scope", "test_strategy", "documentation", "phase_advance"}
ALWAYS_HUMAN = {
    "credentials", "permissions", "security_boundary", "destructive",
    "external_communication", "spending", "production_release",
    "governance_mode_change", "contract_change",
}


class ExecutionPolicyError(ValueError):
    """Invalid execution mode or attempted decision outside delegated authority."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_policy(root: str | Path = ".") -> Dict[str, Any]:
    path = Path(root) / POLICY_PATH
    if not path.exists():
        return {"schema": 1, "mode": DEFAULT_MODE, "updated_at": None, "updated_by": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionPolicyError("execution policy is unreadable or invalid JSON") from exc
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("mode") not in {"supervised", "autonomous"}:
        raise ExecutionPolicyError("execution policy has an unsupported schema or mode")
    allowed = {"schema", "mode", "updated_at", "updated_by"}
    if set(data) - allowed:
        raise ExecutionPolicyError("execution policy contains unsupported keys")
    return data


def evaluate_decision(
    root: str | Path, decision_class: str, *, gate_passed: bool = False,
    within_phase_scope: bool = True,
) -> Dict[str, Any]:
    """Decide whether a coding agent may make a decision under the current owner mode.

    Autonomous mode is delegated authority, not a human signature. Critical actions
    and out-of-scope work remain human-controlled in both modes.
    """
    policy = load_policy(root)
    mode = policy["mode"]
    category = str(decision_class).strip().casefold()
    if not category:
        raise ExecutionPolicyError("decision class is required")
    if category in ALWAYS_HUMAN:
        return {"decision": "human_required", "mode": mode, "actor": "human",
                "reason": "this action is never delegated to an autonomous agent"}
    if not within_phase_scope:
        return {"decision": "human_required", "mode": mode, "actor": "human",
                "reason": "decision is outside the approved phase scope"}
    if category in ROUTINE:
        return {"decision": "allowed", "mode": mode, "actor": "agent",
                "reason": "routine implementation work is permitted"}
    if mode == "autonomous" and category in DELEGABLE:
        if category == "phase_advance" and not gate_passed:
            return {"decision": "human_required", "mode": mode, "actor": "human",
                    "reason": "phase advancement requires a passing phase gate"}
        return {"decision": "delegated", "mode": mode, "actor": "agent-autonomous",
                "reason": "owner delegated this decision class to autonomous execution"}
    return {"decision": "human_required", "mode": mode, "actor": "human",
            "reason": "important decisions require human approval in supervised mode or are not in the delegated allowlist"}


def record_decision(
    root: str | Path, decision_class: str, summary: str, *, gate_passed: bool = False,
    within_phase_scope: bool = True,
) -> Dict[str, Any]:
    """Evaluate and append a privacy-conscious decision record to the event ledger."""
    root = Path(root).resolve()
    result = evaluate_decision(root, decision_class, gate_passed=gate_passed,
                               within_phase_scope=within_phase_scope)
    current = state.load(root / "docs/state.json")
    safe_summary = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^ ]+", r"\1=[REDACTED]", str(summary))[:500]
    event = events.append_event(
        root,
        "decision_" + result["decision"],
        str(current["phase"]),
        result["actor"],
        {"class": decision_class, "summary": safe_summary, "mode": result["mode"],
         "reason": result["reason"], "gate_passed": bool(gate_passed),
         "within_phase_scope": bool(within_phase_scope)},
        source="execution-governance",
    )
    staged = subprocess.run(["git", "add", "--", str(events.LEDGER)], cwd=str(root),
                            capture_output=True, text=True)
    if staged.returncode:
        raise ExecutionPolicyError("decision recorded but event ledger could not be staged")
    return dict(result, event_id=event["event_id"], event_seq=event["seq"])


def set_mode(
    root: str | Path, mode: str, *, environ=None, stdin=None, confirm=input,
) -> Dict[str, Any]:
    """Change mode only through an interactive, HMAC-signed owner action."""
    root = Path(root).resolve()
    mode = str(mode).strip().casefold()
    if mode not in {"supervised", "autonomous"}:
        raise ExecutionPolicyError("mode must be supervised or autonomous")
    previous = load_policy(root)
    if previous["mode"] == mode:
        return {"mode": mode, "changed": False}
    reviewer = approvals.require_human(stdin=stdin, environ=environ, confirm=confirm)
    key = approvals.approval_key(environ)
    document = {"schema": 1, "mode": mode, "updated_at": _now(), "updated_by": reviewer}
    digest = hashlib.sha256(_canonical(document)).hexdigest()
    expected = "SET MODE " + mode + " " + digest[:12]
    typed = confirm("To change execution mode, type " + expected + ": ").strip()
    if typed != expected:
        raise ExecutionPolicyError("execution-mode digest confirmation did not match")
    target = POLICY_PATH.as_posix()
    approval_rel = approvals.approval_path_for(root, str(state.load(root / "docs/state.json")["phase"]), target)
    approvals_path = root / approval_rel
    policy_path = root / POLICY_PATH
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = approvals.make_record(
        str(state.load(root / "docs/state.json")["phase"]), target, digest,
        "protected_path", reviewer, key,
    )
    approvals_path.parent.mkdir(parents=True, exist_ok=True)
    approvals_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    current = state.load(root / "docs/state.json")
    event = events.append_event(
        root, "governance_mode_changed", str(current["phase"]), reviewer,
        {"previous_mode": previous["mode"], "new_mode": mode,
         "policy_sha256": digest, "approval_record": approval_rel},
        source="execution-governance",
    )
    proc = subprocess.run(
        ["git", "add", "--", target, approval_rel, str(events.LEDGER)],
        cwd=str(root), capture_output=True, text=True,
    )
    if proc.returncode:
        raise ExecutionPolicyError("mode updated and signed, but staging failed: " + proc.stderr.strip())
    return {"mode": mode, "changed": True, "reviewer": reviewer,
            "approval": approval_rel, "event_id": event["event_id"]}
