"""Human-approved bootstrap for the next phase contract and state transition."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from . import approvals, events, governance, state


class PhaseStartError(ValueError):
    """Invalid or unauthorized phase transition."""


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _approval_for(root: Path, phase: str, target: str, mode: str,
                  reviewer: str, key: bytes, digest: str, **extra) -> Dict[str, Any]:
    return approvals.make_record(phase, target, digest, mode, reviewer, key, **extra)


def start_phase(root: str | Path, phase: str, *, environ=None, stdin=None, confirm=input) -> Dict[str, Any]:
    """Activate the proposed next phase after exact-content owner approval.

    This is the only supported bootstrap path for a new phase source contract. The
    proposed plan is inert until this command creates and signs the active contract.
    """
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

    plan_rel = "docs/phase-plans/phase-" + phase + ".md"
    target_rel = "docs/phases/phase-" + phase + ".md"
    archive_rel = "docs/amendments/phase-" + phase + "-initial.md"
    schema_rel = "docs/contracts/event.schema.json"
    governance_rel = "docs/governance.json"
    target = root / target_rel
    if target.exists():
        raise PhaseStartError("phase contract already exists: " + target_rel)
    plan = root / plan_rel
    if not plan.is_file():
        raise PhaseStartError("proposed phase plan is missing: " + plan_rel)
    plan_bytes = plan.read_bytes()
    try:
        plan_text = plan_bytes.decode("utf-8")
        schema_bytes = (root / schema_rel).read_bytes()
    except (UnicodeError, OSError) as exc:
        raise PhaseStartError("phase plan or event schema is missing or unreadable") from exc
    marker = "**Status:** proposed"
    if plan_text.count(marker) != 1:
        raise PhaseStartError("phase plan must contain exactly one proposed status marker")
    active_bytes = plan_text.replace(marker, "**Status:** in progress", 1).encode("utf-8")
    contract_digest = hashlib.sha256(active_bytes).hexdigest()

    key = approvals.approval_key(environ)
    reviewer = approvals.require_human(stdin=stdin, environ=environ, confirm=confirm)
    expected = "START PHASE " + phase + " " + contract_digest[:12]
    if confirm("Review the phase scope, then type " + expected + ": ").strip() != expected:
        raise PhaseStartError("phase-start digest confirmation did not match")

    # Verify the preceding phase's signed contract before accepting a transition.
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

    # Import the canonical V2 schema-2 history once, before creating the Phase 30
    # transition. The source fixture is the actual V2 docs/state.json snapshot.
    legacy_path = root / "tests/phase30/fixtures/v2-state.schema2.json"
    try:
        current_raw = json.loads((root / "docs/state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PhaseStartError("current V3 state is unreadable") from exc
    if not (isinstance(current_raw.get("legacy_history"), dict)
            and current_raw["legacy_history"].get("source_sha256")):
        if not legacy_path.is_file():
            raise PhaseStartError("V2 migration fixture is missing: tests/phase30/fixtures/v2-state.schema2.json")
        events.migrate_legacy_state(root, legacy_path, dry_run=False)
    current = state.load(root / "docs/state.json")
    if str(current["phase"]) != previous or current["status"] != "approved":
        raise PhaseStartError("state changed while preparing phase activation")

    # Create the active contract and an exact archive copy.
    archive = root / archive_rel
    _write(target, active_bytes)
    _write(archive, active_bytes)

    # The supervised default is installed in the existing protected governance file.
    # Custom paths keep Phase 30's implementation, tests and gate from agent edits.
    config = dict(governance.DEFAULT_POLICY)
    governance_path = root / governance_rel
    if governance_path.exists():
        try:
            config = json.loads(governance_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PhaseStartError("existing docs/governance.json is invalid") from exc
    if not isinstance(config, dict) or config.get("schema") != governance.SCHEMA:
        raise PhaseStartError("existing governance policy has an unsupported schema")
    protected = list(config.get("protected_paths", []))
    for extra_path in (
        "vibe/events.py", "vibe/execution.py", "vibe/phase.py",
        "tests/phase30/**", "scripts/phase30-gate.py", "docs/phase-plans/**",
    ):
        if extra_path not in protected:
            protected.append(extra_path)
    config["protected_paths"] = protected
    config["execution_mode"] = "supervised"
    config["mode_updated_at"] = None
    config["mode_updated_by"] = None
    _write(governance_path, (json.dumps(config, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    new_state = dict(current)
    new_state["previous_phase"] = {
        "phase": previous, "status": "approved",
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
        {"from_phase": previous, "to_phase": phase, "contract_sha256": contract_digest,
         "contract_source": plan_rel, "execution_mode": "supervised"},
    )

    decisions_path = root / "docs/decisions.md"
    decision_entry = (
        "\n- " + datetime.now(timezone.utc).strftime("%Y-%m-%d")
        + " — Phase " + phase + " started by " + reviewer
        + " after signed approval of the exact phase contract and approved Phase " + previous + " closeout. "
        + "Execution mode defaults to supervised.\n"
    )
    with open(decisions_path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(decision_entry)

    stage_paths = [target_rel, archive_rel, schema_rel, governance_rel,
                   "docs/state.json", "docs/decisions.md", str(events.LEDGER)]
    staged = subprocess.run(["git", "add", "--", *stage_paths], cwd=str(root),
                            capture_output=True, text=True)
    if staged.returncode:
        raise PhaseStartError("phase files were written but could not be staged: " + staged.stderr.strip())

    target_index = approvals.staged_bytes(root, target_rel)
    archive_index = approvals.staged_bytes(root, archive_rel)
    target_digest = hashlib.sha256(target_index).hexdigest()
    archive_digest = hashlib.sha256(archive_index).hexdigest()
    if target_digest != archive_digest:
        raise PhaseStartError("staged phase contract and archive differ after Git normalization")

    signatures: Dict[str, Dict[str, Any]] = {}
    signatures["docs/approvals/phase-" + phase + ".json"] = _approval_for(
        root, phase, target_rel, "phase_amendment", reviewer, key, target_digest,
        proposal_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        archive_path=archive_rel, archive_sha256=archive_digest,
    )
    for target_path in ("docs/state.json", "docs/decisions.md", schema_rel, governance_rel):
        digest = hashlib.sha256(approvals.staged_bytes(root, target_path)).hexdigest()
        approval_rel = approvals.approval_path_for(root, phase, target_path)
        signatures[approval_rel] = _approval_for(
            root, phase, target_path, "protected_path", reviewer, key, digest,
        )
    for relative, record in signatures.items():
        _write(root / relative, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    staged = subprocess.run(["git", "add", "--", *signatures.keys()], cwd=str(root),
                            capture_output=True, text=True)
    if staged.returncode:
        raise PhaseStartError("signed approval records were created but could not be staged")
    return {
        "phase": phase, "status": "in_progress", "contract": target_rel,
        "archive": archive_rel, "approval_records": list(signatures),
        "event_sequence": new_state["event_ledger"]["sequence"],
        "execution_mode": config["execution_mode"],
    }
