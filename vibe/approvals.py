"""Human-controlled, content-digest-bound governance approvals.

HMAC keys are supplied outside the repository through VIBE_APPROVAL_KEY. This is
an integrity guardrail, not a defence against hostile code running as the same OS user.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .governance import GovernanceError, is_phase_source, normalize_relative_path
from . import state as state_module

SCHEMA = 1
KEY_ENV = "VIBE_APPROVAL_KEY"
AGENT_MARKERS = (
    "CLAUDECODE", "CLAUDE_CODE", "CURSOR_AGENT", "CODEX_THREAD_ID",
    "GEMINI_CLI", "AIDER_", "CODY_", "COPILOT_AGENT",
)


class ApprovalError(ValueError):
    """Raised for missing human confirmation or invalid approval evidence."""


def _canonical_json(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def approval_key(environ: Optional[Dict[str, str]] = None) -> bytes:
    environ = os.environ if environ is None else environ
    value = environ.get(KEY_ENV, "")
    if len(value.encode("utf-8")) < 32:
        raise ApprovalError(KEY_ENV + " must be configured with at least 32 UTF-8 bytes")
    return value.encode("utf-8")


def require_human(stdin=None, environ=None, confirm: Callable[[str], str] = input) -> str:
    """Require a TTY, reject common agent markers, and collect a reviewer label."""
    stdin = sys.stdin if stdin is None else stdin
    environ = os.environ if environ is None else environ
    marker = next((name for name in environ if name in AGENT_MARKERS or name.startswith(
        ("CLAUDE_", "CURSOR_", "CODEX_", "GEMINI_", "AIDER_", "COPILOT_"))), None)
    if marker:
        raise ApprovalError("refusing human-only approval because agent marker " + marker + " is present")
    if not bool(getattr(stdin, "isatty", lambda: False)()):
        raise ApprovalError("human-only approval requires an interactive TTY")
    typed = confirm('Type "I reviewed this exact content" to continue: ')
    if typed.strip() != "I reviewed this exact content":
        raise ApprovalError("human confirmation phrase did not match")
    reviewer = confirm("Reviewer name or identifier: ").strip()
    if not reviewer:
        raise ApprovalError("reviewer identity cannot be empty")
    return reviewer


def make_record(phase: str, target_path: str, target_sha256: str, mode: str,
                reviewer: str, key: bytes, proposal_sha256: Optional[str] = None,
                previous_sha256: Optional[str] = None, archive_path: Optional[str] = None,
                archive_sha256: Optional[str] = None,
                approved_at: Optional[str] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "schema": SCHEMA,
        "phase": phase,
        "target_path": target_path,
        "target_sha256": target_sha256,
        "mode": mode,
        "reviewer": reviewer,
        "approved_at": approved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    if proposal_sha256 is not None:
        body["proposal_sha256"] = proposal_sha256
    if previous_sha256 is not None:
        body["previous_sha256"] = previous_sha256
    if archive_path is not None:
        body["archive_path"] = archive_path
    if archive_sha256 is not None:
        body["archive_sha256"] = archive_sha256
    body["signature_hmac_sha256"] = hmac.new(key, _canonical_json(body), hashlib.sha256).hexdigest()
    return body


def verify_record(record: Dict[str, Any], key: bytes, target_path: str,
                  target_sha256: str, phase: Optional[str] = None) -> Tuple[bool, str]:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        return False, "approval record has an unsupported schema"
    if record.get("target_path") != target_path:
        return False, "approval is bound to a different target path"
    if record.get("target_sha256") != target_sha256:
        return False, "staged content digest does not match the approved digest"
    if phase is not None and record.get("phase") != phase:
        return False, "approval is bound to a different active phase"
    signature = record.get("signature_hmac_sha256")
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        return False, "approval signature is missing or malformed"
    body = dict(record)
    body.pop("signature_hmac_sha256", None)
    expected = hmac.new(key, _canonical_json(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False, "approval signature verification failed"
    return True, "content digest and signature verified"


def _git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True)
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ApprovalError("git " + " ".join(args) + " failed: " + (detail or "unknown error"))
    return proc.stdout


def staged_paths(root: str | Path) -> List[str]:
    root = Path(root).resolve()
    raw = _git(root, "diff", "--cached", "--name-only", "-z")
    return [p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\x00") if p]


def staged_bytes(root: str | Path, relative_path: str) -> bytes:
    root = Path(root).resolve()
    # `git show :path` reads the index, not the working-tree copy.
    return _git(root, "show", ":" + relative_path)


def committed_bytes(root: str | Path, relative_path: str) -> bytes:
    """Read the committed Git blob, independent of working-tree line endings.

    Approval records are created from staged blob bytes. Verifying a committed
    phase contract must therefore hash HEAD's blob rather than Path.read_bytes(),
    which may contain CRLF on Windows when Git stores LF.
    """
    root = Path(root).resolve()
    return _git(root, "show", "HEAD:" + relative_path)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def approval_path_for(root: str | Path, phase: str, target_path: str) -> str:
    if is_phase_source(target_path):
        return "docs/approvals/phase-" + phase + ".json"
    canonical = target_path.casefold().replace("\\", "/")
    slug = re.sub(r"[^a-z0-9]+", "-", canonical).strip("-")[:32] or "protected"
    suffix = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return "docs/approvals/phase-" + phase + "-" + slug + "-" + suffix + ".json"


def apply_amendment(root: str | Path, phase: str, *, environ=None, stdin=None,
                    confirm: Callable[[str], str] = input) -> Dict[str, str]:
    """Apply the exact proposal as a human-reviewed phase contract replacement."""
    root = Path(root).resolve()
    state_path = root / "docs" / "state.json"
    try:
        current_state = state_module.load(state_path)
    except state_module.StateError as exc:
        raise ApprovalError("cannot apply amendment: Vibe state is unreadable") from exc
    if str(current_state.get("phase")) != str(phase):
        raise ApprovalError("amendment phase must match the active Vibe phase")
    if not re.fullmatch(r"[0-9]{2}", str(phase)):
        raise ApprovalError("phase must be a two-digit number")

    target_rel = "docs/phases/phase-" + str(phase) + ".md"
    proposal_rel = "docs/proposals/phase-" + str(phase) + "-amend.md"
    target = root / target_rel
    proposal = root / proposal_rel
    try:
        normalize_relative_path(root, target_rel)
        normalize_relative_path(root, proposal_rel)
    except GovernanceError as exc:
        raise ApprovalError("amendment path is unsafe: " + str(exc)) from exc
    if not target.is_file():
        raise ApprovalError("active phase contract is missing: " + target_rel)
    if not proposal.is_file():
        raise ApprovalError("proposal is missing: " + proposal_rel)

    key = approval_key(environ)
    reviewer = require_human(stdin=stdin, environ=environ, confirm=confirm)
    proposed = proposal.read_bytes()
    if not proposed.strip():
        raise ApprovalError("amendment proposal is empty")
    proposal_sha = hashlib.sha256(proposed).hexdigest()
    expected = "APPLY " + str(phase) + " " + proposal_sha[:12]
    typed = confirm("Type " + expected + " to replace the phase contract: ").strip()
    if typed != expected:
        raise ApprovalError("amendment digest confirmation did not match")

    previous_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    archive_rel = "docs/amendments/phase-" + str(phase) + "-" + proposal_sha[:12] + ".md"
    archive = root / archive_rel
    approval_rel = approval_path_for(root, str(phase), target_rel)
    approval = root / approval_rel
    try:
        normalize_relative_path(root, archive_rel)
        normalize_relative_path(root, approval_rel)
    except GovernanceError as exc:
        raise ApprovalError("approval output path is unsafe: " + str(exc)) from exc

    # Git may normalize CRLF to LF when adding a file on Windows. Bind the
    # approval to the exact staged blob bytes, not the pre-clean working copy.
    # The raw proposal digest remains separately recorded for the human confirmation.
    _write_atomic(archive, proposed)
    _write_atomic(target, proposed)
    _git(root, "add", "--", target_rel, archive_rel)
    staged_target = staged_bytes(root, target_rel)
    staged_archive = staged_bytes(root, archive_rel)
    target_sha = hashlib.sha256(staged_target).hexdigest()
    archive_sha = hashlib.sha256(staged_archive).hexdigest()
    if staged_target != staged_archive:
        raise ApprovalError("staged phase contract and amendment archive differ after Git normalization")

    record = make_record(
        phase=str(phase), target_path=target_rel, target_sha256=target_sha,
        mode="phase_amendment", reviewer=reviewer, key=key,
        proposal_sha256=proposal_sha, previous_sha256=previous_sha,
        archive_path=archive_rel, archive_sha256=archive_sha,
    )
    _write_atomic(approval, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    proposal.unlink()
    # Stage only the reviewed contract transaction. This prevents the human command
    # from accidentally sweeping unrelated work into the commit.
    _git(root, "add", "--", approval_rel)
    tracked_proposal = subprocess.run(
        ["git", "ls-files", "--error-unmatch", proposal_rel],
        cwd=str(root), capture_output=True,
    )
    if tracked_proposal.returncode == 0:
        _git(root, "add", "-u", "--", proposal_rel)
    return {"target": target_rel, "target_sha256": target_sha, "archive": archive_rel,
            "approval": approval_rel, "proposal_sha256": proposal_sha}


def approve_staged_paths(root: str | Path, *, environ=None, stdin=None,
                          confirm: Callable[[str], str] = input) -> List[str]:
    """Approve staged protected non-phase files through an interactive human action."""
    from .governance import is_protected_path, load_policy

    root = Path(root).resolve()
    policy = load_policy(root)
    environ = os.environ if environ is None else environ
    paths = staged_paths(root)
    targets: List[Tuple[str, bytes, str]] = []
    for raw_path in paths:
        relative = normalize_relative_path(root, raw_path)
        if not is_protected_path(relative, policy):
            continue
        if relative.startswith("docs/approvals/") or relative.startswith(".vibe/approvals/"):
            continue
        if is_phase_source(relative):
            raise ApprovalError("phase contracts must be changed through a docs/proposals/phase-NN-amend.md proposal")
        data = staged_bytes(root, raw_path)
        targets.append((raw_path, data, hashlib.sha256(data).hexdigest()))
    if not targets:
        raise ApprovalError("no staged protected non-phase files require human approval")

    key = approval_key(environ)
    reviewer = require_human(stdin=stdin, environ=environ, confirm=confirm)
    digest_summary = hashlib.sha256("\n".join(p + ":" + d for p, _, d in targets).encode("utf-8")).hexdigest()
    expected = "APPROVE " + str(len(targets)) + " " + digest_summary[:12]
    typed = confirm("Review staged protected files, then type " + expected + ": ").strip()
    if typed != expected:
        raise ApprovalError("staged-content digest confirmation did not match")

    try:
        current_state = state_module.load(root / "docs/state.json")
        phase = str(current_state["phase"])
    except state_module.StateError as exc:
        raise ApprovalError("cannot approve protected files: Vibe state is unreadable") from exc

    written = []
    for target_path, _, digest in targets:
        relative = normalize_relative_path(root, target_path)
        record = make_record(phase, relative, digest, "protected_path", reviewer, key)
        approval_rel = approval_path_for(root, phase, relative)
        approval = root / approval_rel
        try:
            normalize_relative_path(root, approval_rel)
        except GovernanceError as exc:
            raise ApprovalError("approval output path is unsafe: " + str(exc)) from exc
        _write_atomic(approval, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        _git(root, "add", approval_rel)
        written.append(approval_rel)
    return written
