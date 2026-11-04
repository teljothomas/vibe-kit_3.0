"""Owner-controlled execution mode and signed human/autonomous decision records."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import approvals, events, governance, state

DEFAULT_MODE = "supervised"
ROUTINE = {"routine", "formatting", "tests", "bugfix", "implementation"}
DELEGABLE = {"architecture", "dependencies", "scope", "test_strategy", "documentation", "phase_advance"}
ALWAYS_HUMAN = {
    "credentials", "permissions", "security_boundary", "destructive",
    "external_communication", "spending", "production_release",
    "governance_mode_change", "contract_change",
}


class ExecutionPolicyError(ValueError):
    """Invalid mode, decision or delegated authority."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _safe_summary(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^ \t,;]+", r"\1=[REDACTED]", text)
    return text[:500]


def load_mode(root: str | Path = ".") -> str:
    policy = governance.load_policy(root)
    mode = policy.get("execution_mode", DEFAULT_MODE)
    if mode not in {"supervised", "autonomous"}:
        raise ExecutionPolicyError("docs/governance.json execution_mode must be supervised or autonomous")
    return mode


def evaluate_decision(
    root: str | Path, decision_class: str, *, gate_passed: bool = False,
    within_phase_scope: bool = True,
) -> Dict[str, Any]:
    """Return the actor/approval path permitted by the owner-selected mode.

    Autonomous delegation is not a human signature. High-risk actions remain human
    controlled in both modes. Phase advancement requires a passing gate.
    """
    mode = load_mode(root)
    category = str(decision_class).strip().casefold()
    if not category:
        raise ExecutionPolicyError("decision class is required")
    if category in ALWAYS_HUMAN:
        return {"decision": "human_required", "mode": mode, "actor": "human",
                "reason": "this action always requires explicit human authorization"}
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
            "reason": "important decisions require approval in supervised mode or are outside the delegated allowlist"}


def _append_and_stage(root: Path, event_type: str, phase: str, actor: str,
                      details: Dict[str, Any]) -> Dict[str, Any]:
    event = events.append_event(root, event_type, phase, actor, details, source="execution-governance")
    proc = subprocess.run(["git", "add", "--", str(events.LEDGER)], cwd=str(root),
                          capture_output=True, text=True)
    if proc.returncode:
        raise ExecutionPolicyError("decision event was appended but could not be staged: " + proc.stderr.strip())
    return event


def record_decision(
    root: str | Path, decision_class: str, summary: str, *, gate_passed: bool = False,
    within_phase_scope: bool = True,
) -> Dict[str, Any]:
    """Record a routine or delegated decision; supervised important decisions are blocked."""
    root = Path(root).resolve()
    result = evaluate_decision(root, decision_class, gate_passed=gate_passed,
                               within_phase_scope=within_phase_scope)
    current = state.load(root / "docs/state.json")
    if result["decision"] == "human_required":
        event = _append_and_stage(
            root, "decision_waiting_for_human", str(current["phase"]), "agent",
            {"class": decision_class, "summary": _safe_summary(summary), "mode": result["mode"],
             "reason": result["reason"], "gate_passed": bool(gate_passed),
             "within_phase_scope": bool(within_phase_scope)},
        )
        return dict(result, event_id=event["event_id"], event_seq=event["seq"])
    event = _append_and_stage(
        root, "decision_" + result["decision"], str(current["phase"]), result["actor"],
        {"class": decision_class, "summary": _safe_summary(summary), "mode": result["mode"],
         "reason": result["reason"], "gate_passed": bool(gate_passed),
         "within_phase_scope": bool(within_phase_scope)},
    )
    return dict(result, event_id=event["event_id"], event_seq=event["seq"])


def approve_decision(
    root: str | Path, decision_class: str, summary: str, *, environ=None,
    stdin=None, confirm=input,
) -> Dict[str, Any]:
    """Create an HMAC-signed human authorization for one exact decision statement."""
    root = Path(root).resolve()
    reviewer = approvals.require_human(stdin=stdin, environ=environ, confirm=confirm)
    key = approvals.approval_key(environ)
    current = state.load(root / "docs/state.json")
    payload = {
        "schema": 1, "phase": str(current["phase"]), "decision_class": str(decision_class),
        "summary": _safe_summary(summary), "mode": load_mode(root), "reviewer": reviewer,
        "approved_at": _now(),
    }
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    expected = "APPROVE DECISION " + digest[:12]
    if confirm("To authorize this exact decision, type " + expected + ": ").strip() != expected:
        raise ExecutionPolicyError("decision digest confirmation did not match")
    target = "decision:" + str(current["phase"]) + ":" + digest[:12]
    record = approvals.make_record(str(current["phase"]), target, digest, "decision_approval", reviewer, key)
    event = _append_and_stage(
        root, "decision_human_approved", str(current["phase"]), reviewer,
        {"decision": payload, "decision_sha256": digest, "approval_record": record},
    )
    return {"decision": "human_approved", "reviewer": reviewer, "event_id": event["event_id"],
            "event_seq": event["seq"], "decision_sha256": digest}


def set_mode(
    root: str | Path, mode: str, *, environ=None, stdin=None, confirm=input,
) -> Dict[str, Any]:
    """Change mode only through an interactive owner action and signed protected config."""
    root = Path(root).resolve()
    mode = str(mode).strip().casefold()
    if mode not in {"supervised", "autonomous"}:
        raise ExecutionPolicyError("mode must be supervised or autonomous")
    previous = load_mode(root)
    if previous == mode:
        return {"mode": mode, "changed": False}
    key = approvals.approval_key(environ)
    reviewer = approvals.require_human(stdin=stdin, environ=environ, confirm=confirm)
    policy = governance.load_policy(root)
    policy_path = root / "docs" / "governance.json"
    existed_before = policy_path.exists()
    previous_bytes = policy_path.read_bytes() if existed_before else None
    staged_check = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", "docs/governance.json"],
        cwd=str(root), capture_output=True,
    )
    if staged_check.returncode not in (0,):
        raise ExecutionPolicyError("docs/governance.json already has staged changes; commit or unstage them before changing mode")
    document = dict(policy)
    document["execution_mode"] = mode
    document["mode_updated_at"] = _now()
    document["mode_updated_by"] = reviewer
    encoded = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_bytes(encoded)
    target = "docs/governance.json"
    staged = subprocess.run(["git", "add", "--", target], cwd=str(root), capture_output=True, text=True)
    if staged.returncode:
        if existed_before and previous_bytes is not None:
            policy_path.write_bytes(previous_bytes)
        else:
            policy_path.unlink(missing_ok=True)
        raise ExecutionPolicyError("mode setting was written but could not be staged")
    digest = hashlib.sha256(approvals.staged_bytes(root, target)).hexdigest()
    expected = "SET MODE " + mode + " " + digest[:12]
    if confirm("To change execution mode, type " + expected + ": ").strip() != expected:
        if existed_before and previous_bytes is not None:
            policy_path.write_bytes(previous_bytes)
        else:
            policy_path.unlink(missing_ok=True)
        subprocess.run(["git", "reset", "-q", "HEAD", "--", target], cwd=str(root),
                       capture_output=True, text=True)
        raise ExecutionPolicyError("execution-mode digest confirmation did not match; unapproved setting was reverted")
    phase = str(state.load(root / "docs/state.json")["phase"])
    record = approvals.make_record(phase, target, digest, "protected_path", reviewer, key)
    approval_rel = approvals.approval_path_for(root, phase, target)
    approval_path = root / approval_rel
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    event = events.append_event(
        root, "governance_mode_changed", phase, reviewer,
        {"previous_mode": previous, "new_mode": mode, "config_sha256": digest,
         "approval_record": approval_rel},
        source="execution-governance",
    )
    staged = subprocess.run(["git", "add", "--", approval_rel, str(events.LEDGER)],
                            cwd=str(root), capture_output=True, text=True)
    if staged.returncode:
        raise ExecutionPolicyError("mode and signature were created but could not be staged")
    return {"mode": mode, "changed": True, "reviewer": reviewer,
            "approval": approval_rel, "event_id": event["event_id"]}
