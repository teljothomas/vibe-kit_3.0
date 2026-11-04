"""Human-approved bootstrap for the next phase contract and state transition."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from . import approvals, events, state


class PhaseStartError(ValueError):
    """Invalid or unauthorized phase transition."""


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "wb") as handle:
        handle.write(raw)
        handle.flush()
        import os
        os.fsync(handle.fileno())
    os.replace(temp, path)


def start_phase(root: str | Path, phase: str, *, environ=None, stdin=None, confirm=input) -> Dict[str, Any]:
    """Activate the proposed next phase only after owner review and digest-bound signatures."""
    root = Path(root).resolve()
    phase = str(phase)
    if len(phase) != 2 or not phase.isdigit():
        raise PhaseStartError("phase must be a two-digit number")
    current = state.load(root / "docs/state.json")
    previous = str(current["phase"])
    if current["status"] != "approved" or current["last_gate"].get("status") != "passed":
        raise PhaseStartError("the current phase must be approved and its gate must have passed")
    if int(phase) != int(previous) + 1:
        raise PhaseStartError("only the immediately following phase may be started")
    target_rel = "docs/phases/phase-" + phase + ".md"
    plan_rel = "docs/phase-plans/phase-" + phase + ".md"
    archive_rel = "docs/amendments/phase-" + phase + "-initial.md"
    if (root / target_rel).exists():
        raise PhaseStartError("phase contract already exists: " + target_rel)
    plan = root / plan_rel
    if not plan.is_file():
        raise PhaseStartError("proposed phase plan is missing: " + plan_rel)
    plan_bytes = plan.read_bytes()
    try:
        plan_text = plan_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise PhaseStartError("phase plan must be UTF-8") from exc
    marker = "**Status:** proposed"
    if plan_text.count(marker) != 1:
        raise PhaseStartError("phase plan must contain exactly one proposed status marker")
    active_bytes = plan_text.replace(marker, "**Status:** in progress", 1).encode("utf-8")
    target_digest = hashlib.sha256(active_bytes).hexdigest()

    key = approvals.approval_key(environ)
    reviewer = approvals.require_human(stdin=stdin, environ=environ, confirm=confirm)
    expected = "START PHASE " + phase + " " + target_digest[:12]
    if confirm("Review the phase scope, then type " + expected + ": ").strip() != expected:
        raise PhaseStartError("phase-start digest confirmation did not match")

    # Verify the immediately preceding phase has a signed, digest-bound approval.
    prior_target = "docs/phases/phase-" + previous + ".md"
    prior_path = root / "docs/approvals" / ("phase-" + previous + ".json")
    try:
        prior_record = json.loads(prior_path.read_text(encoding="utf-8"))
        prior_digest = hashlib.sha256((root / prior_target).read_bytes()).hexdigest()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PhaseStartError("previous phase approval record or contract is missing") from exc
    valid, reason = approvals.verify_record(prior_record, key, prior_target, prior_digest, previous)
    if not valid:
        raise PhaseStartError("previous phase signed approval is invalid: " + reason)

    target = root / target_rel
    archive = root / archive_rel
    _write(target, active_bytes)
    _write(archive, active_bytes)

    new_state = dict(current)
    new_state["previous_phase"] = {
        "phase": previous,
        "status": "approved",
        "gate_status": current["last_gate"].get("status"),
        "gate_commit": current["last_gate"].get("commit"),
        "approval_record": "docs/approvals/phase-" + previous + ".json",
    }
    new_state["phase"] = phase
    new_state["status"] = "in_progress"
    new_state["last_gate"] = {"phase": phase, "status": "not_run", "commit": None}
    new_state["next"] = "Complete Phase " + phase + " and record its gate evidence."
    new_state = events.write_snapshot(
        root, new_state, "phase_started", reviewer,
        {"from_phase": previous, "to_phase": phase, "contract_sha256": target_digest,
         "contract_source": plan_rel},
    )

    decisions_path = root / "docs/decisions.md"
    from datetime import datetime, timezone
    decision_entry = (
        "\n- " + datetime.now(timezone.utc).strftime("%Y-%m-%d")
        + " — Phase " + phase + " started by " + reviewer
        + " after signed approval of the exact phase contract and approved Phase " + previous + " closeout.\n"
    )
    with open(decisions_path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(decision_entry)

    paths = [target_rel, archive_rel, "docs/state.json", "docs/decisions.md", str(events.LEDGER)]
    staged = subprocess.run(["git", "add", "--", *paths], cwd=str(root), capture_output=True, text=True)
    if staged.returncode:
        raise PhaseStartError("phase files were written but could not be staged: " + staged.stderr.strip())

    target_index = approvals.staged_bytes(root, target_rel)
    archive_index = approvals.staged_bytes(root, archive_rel)
    target_digest_index = hashlib.sha256(target_index).hexdigest()
    archive_digest_index = hashlib.sha256(archive_index).hexdigest()
    if target_digest_index != archive_digest_index:
        raise PhaseStartError("staged phase contract and archive differ after Git normalization")
    phase_record = approvals.make_record(
        phase, target_rel, target_digest_index, "phase_amendment", reviewer, key,
        proposal_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        archive_path=archive_rel, archive_sha256=archive_digest_index,
    )
    state_digest = hashlib.sha256(approvals.staged_bytes(root, "docs/state.json")).hexdigest()
    state_record = approvals.make_record(phase, "docs/state.json", state_digest, "protected_path", reviewer, key)
    decisions_digest = hashlib.sha256(approvals.staged_bytes(root, "docs/decisions.md")).hexdigest()
    decisions_record = approvals.make_record(phase, "docs/decisions.md", decisions_digest, "protected_path", reviewer, key)
    records = {
        "docs/approvals/phase-" + phase + ".json": phase_record,
        approvals.approval_path_for(root, phase, "docs/state.json"): state_record,
        approvals.approval_path_for(root, phase, "docs/decisions.md"): decisions_record,
    }
    for relative, record in records.items():
        path = root / relative
        _write(path, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    staged = subprocess.run(["git", "add", "--", *records.keys()], cwd=str(root), capture_output=True, text=True)
    if staged.returncode:
        raise PhaseStartError("approval records were written but could not be staged: " + staged.stderr.strip())
    return {
        "phase": phase, "status": "in_progress", "contract": target_rel,
        "archive": archive_rel, "approval_records": list(records),
        "event_sequence": new_state["event_ledger"]["sequence"],
    }
