"""Append-only V3 event ledger, V2 state importer and bounded snapshot recovery."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = 1
LEDGER = Path("docs/events/ledger.jsonl")
LOCK = Path(".vibe/locks/events.lock")
GENESIS = "0" * 64
MAX_STATE_BYTES = 4096
RECENT_LIMIT = 5
_PROCESS_LOCK = threading.RLock()


class EventError(ValueError):
    """Invalid event history or unsafe snapshot operation."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Dict[str, Any]) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EventError("event contains a non-JSON value") from exc


def _hash(value: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@contextlib.contextmanager
def _lock(root: Path):
    path = root / LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    with _PROCESS_LOCK:
        handle = open(path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                if not handle.read(1):
                    handle.seek(0)
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def verify_bytes(raw: bytes) -> List[Dict[str, Any]]:
    """Validate line completeness, schema, sequence, unique IDs and hash chain."""
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise EventError("ledger has a truncated final line")
    result: List[Dict[str, Any]] = []
    ids: set[str] = set()
    previous = GENESIS
    required = {
        "schema", "seq", "event_id", "event_type", "phase", "occurred_at",
        "imported_at", "actor", "commit", "evidence_ref", "source",
        "details", "prev_hash", "event_hash",
    }
    for seq, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise EventError("ledger contains a blank line at sequence " + str(seq))
        try:
            item = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise EventError("ledger contains invalid JSON at sequence " + str(seq)) from exc
        if not isinstance(item, dict) or required - set(item) or set(item) != required:
            raise EventError("ledger event has missing or unsupported fields")
        if item["schema"] != SCHEMA or isinstance(item["seq"], bool) or not isinstance(item["seq"], int) or item["seq"] != seq:
            raise EventError("ledger schema or sequence mismatch at " + str(seq))
        event_id = item["event_id"]
        if not isinstance(event_id, str) or not event_id or event_id in ids:
            raise EventError("ledger event ID is missing or duplicated")
        if not isinstance(item["event_type"], str) or not item["event_type"] or len(item["event_type"]) > 80:
            raise EventError("ledger event_type must be a non-empty string of at most 80 characters")
        phase = item["phase"]
        if phase is not None and (not isinstance(phase, str) or len(phase) != 2 or not phase.isdigit()):
            raise EventError("ledger phase must be null or a two-digit string")
        if not isinstance(item["actor"], str) or not item["actor"] or len(item["actor"]) > 128:
            raise EventError("ledger actor must be a non-empty string of at most 128 characters")
        if not isinstance(item["imported_at"], str):
            raise EventError("ledger imported_at must be a timestamp string")
        if item["occurred_at"] is not None and not isinstance(item["occurred_at"], str):
            raise EventError("ledger occurred_at must be null or a timestamp string")
        if not isinstance(item["source"], str) or not isinstance(item["details"], dict):
            raise EventError("ledger source or details has an invalid type")
        if item["prev_hash"] != previous:
            raise EventError("ledger previous hash mismatch at sequence " + str(seq))
        body = dict(item)
        supplied = body.pop("event_hash")
        calculated = _hash(body)
        if supplied != calculated:
            raise EventError("ledger event hash mismatch at sequence " + str(seq))
        ids.add(event_id)
        previous = calculated
        result.append(item)
    return result


def _read_events_unlocked(root: Path) -> List[Dict[str, Any]]:
    path = root / LEDGER
    if not path.exists():
        return []
    try:
        return verify_bytes(path.read_bytes())
    except OSError as exc:
        raise EventError("event ledger cannot be read") from exc


def read_events(root: str | Path = ".") -> List[Dict[str, Any]]:
    root = Path(root).resolve()
    with _lock(root):
        return _read_events_unlocked(root)


def append_event(
    root: str | Path, event_type: str, phase: Optional[str], actor: str,
    details: Optional[Dict[str, Any]] = None, *, commit: Optional[str] = None,
    evidence_ref: Optional[str] = None, source: str = "vibe",
    occurred_at: Optional[str] = None, imported_at: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append and fsync one event. Repeating a supplied event_id is idempotent."""
    root = Path(root).resolve()
    path = root / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    details = {} if details is None else details
    if not isinstance(details, dict):
        raise EventError("event details must be an object")
    with _lock(root):
        old = _read_events_unlocked(root)
        if event_id:
            existing = next((x for x in old if x["event_id"] == event_id), None)
            if existing:
                expected = {
                    "event_type": event_type, "phase": phase, "actor": actor,
                    "commit": commit, "evidence_ref": evidence_ref, "source": source,
                    "details": details, "occurred_at": occurred_at,
                }
                for field, value in expected.items():
                    if existing.get(field) != value:
                        raise EventError("event ID " + event_id + " was already used for different " + field)
                return existing
        body = {
            "schema": SCHEMA,
            "seq": len(old) + 1,
            "event_id": event_id or "evt-" + uuid.uuid4().hex,
            "event_type": event_type,
            "phase": phase,
            "occurred_at": occurred_at,
            "imported_at": imported_at or _now(),
            "actor": actor,
            "commit": commit,
            "evidence_ref": evidence_ref,
            "source": source,
            "details": details,
            "prev_hash": old[-1]["event_hash"] if old else GENESIS,
        }
        body["event_hash"] = _hash(body)
        with open(path, "ab") as handle:
            handle.write(_canonical(body) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        return body


def _legacy_event(index: int, entry: Dict[str, Any]) -> Dict[str, Any]:
    fingerprint = _hash({"index": index, "entry": entry})
    approved_by = entry.get("approved_by")
    if approved_by == "(gate:off)":
        actor = "legacy-gate-off"
    elif isinstance(approved_by, str) and approved_by.strip():
        actor = approved_by
    else:
        actor = "legacy-unknown"
    phase = entry.get("phase")
    if not isinstance(phase, str) or len(phase) != 2 or not phase.isdigit():
        raise EventError("legacy log entry " + str(index + 1) + " has an invalid phase")
    # Preserve every raw field. Legacy timestamps remain null when absent; gate-off
    # and unsigned records are never silently converted into human approvals.
    return {
        "event_id": "legacy-v2-" + str(index + 1).zfill(4) + "-" + fingerprint[:12],
        "event_type": "legacy_phase_recorded",
        "phase": phase,
        "occurred_at": entry.get("approved_at"),
        "actor": actor,
        "commit": entry.get("commit"),
        "evidence_ref": entry.get("evidence"),
        "source": "v2-state-schema-2",
        "details": {
            "legacy_index": index,
            "legacy_schema": 2,
            "legacy_entry": entry,
            "human_approved": bool(entry.get("signature") and approved_by not in (None, "(gate:off)")),
        },
    }


def preview_legacy_migration(root: str | Path, source_path: str | Path) -> Dict[str, Any]:
    try:
        raw = Path(source_path).read_bytes()
        source = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EventError("legacy V2 state must be readable UTF-8 JSON") from exc
    if not isinstance(source, dict) or source.get("schema") != 2 or not isinstance(source.get("log"), list):
        raise EventError("legacy input must have schema 2 and a log array")
    converted = [_legacy_event(i, entry) for i, entry in enumerate(source["log"]) if isinstance(entry, dict)]
    if len(converted) != len(source["log"]):
        raise EventError("legacy log contains a non-object entry")
    existing = {x["event_id"] for x in read_events(root)}
    missing = [x for x in converted if x["event_id"] not in existing]
    canonical_source = json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "source_schema": 2,
        # Canonical semantic hash is stable across Windows CRLF/LF checkout settings.
        "source_sha256": hashlib.sha256(canonical_source).hexdigest(),
        "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "legacy_entries": len(converted),
        "already_imported": len(converted) - len(missing),
        "would_import": len(missing),
        "null_original_timestamps": sum(x["occurred_at"] is None for x in converted),
        "events": converted,
        "legacy_top_level": {k: v for k, v in source.items() if k != "log"},
    }


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def write_snapshot(
    root: str | Path, snapshot: Dict[str, Any], event_type: str, actor: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append durable snapshot event first; atomically write the compact snapshot second."""
    root = Path(root).resolve()
    candidate = dict(snapshot)
    candidate.pop("event_ledger", None)
    event_details = dict(details or {})
    event_details["snapshot_after"] = candidate
    # Preflight the size with worst-case recent-summary placeholders before
    # appending the event, so a size failure never occurs after a durable append.
    estimated = dict(candidate)
    estimated["event_ledger"] = {
        "schema": SCHEMA, "sequence": 99999999, "last_event_id": "evt-" + ("0" * 32),
        "last_event_hash": "0" * 64,
        "recent": [
            {"event_id": "legacy-v2-9999-" + ("0" * 12), "event_type": "x" * 80,
             "phase": "99", "occurred_at": "2000-01-01T00:00:00Z", "actor": "x" * 128}
            for _ in range(RECENT_LIMIT)
        ],
    }
    if len((json.dumps(estimated, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")) > MAX_STATE_BYTES:
        raise EventError("compact state would exceed " + str(MAX_STATE_BYTES) + " bytes")
    event = append_event(root, event_type, str(candidate.get("phase")), actor, event_details)
    history = read_events(root)
    committed_history = history[:event["seq"]]
    recent = [
        {"event_id": x["event_id"], "event_type": x["event_type"], "phase": x["phase"],
         "occurred_at": x["occurred_at"], "actor": x["actor"]}
        for x in committed_history[-RECENT_LIMIT:]
    ]
    candidate["event_ledger"] = {
        "schema": SCHEMA, "sequence": event["seq"], "last_event_id": event["event_id"],
        "last_event_hash": event["event_hash"], "recent": recent,
    }
    raw = (json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(raw) > MAX_STATE_BYTES:
        raise EventError("compact state exceeds " + str(MAX_STATE_BYTES) + " bytes")
    _atomic_write(root / "docs/state.json", raw)
    return candidate


def replay_snapshot(root: str | Path = ".") -> Dict[str, Any]:
    """Recover a snapshot after a crash between durable event append and state replace."""
    root = Path(root).resolve()
    history = read_events(root)
    selected = next((x for x in reversed(history) if isinstance(x["details"].get("snapshot_after"), dict)), None)
    if selected is None:
        raise EventError("ledger contains no recoverable snapshot event")
    candidate = dict(selected["details"]["snapshot_after"])
    prior = [x for x in history if x["seq"] <= selected["seq"]]
    candidate["event_ledger"] = {
        "schema": SCHEMA, "sequence": selected["seq"], "last_event_id": selected["event_id"],
        "last_event_hash": selected["event_hash"],
        "recent": [
            {"event_id": x["event_id"], "event_type": x["event_type"], "phase": x["phase"],
             "occurred_at": x["occurred_at"], "actor": x["actor"]}
            for x in prior[-RECENT_LIMIT:]
        ],
    }
    raw = (json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(raw) > MAX_STATE_BYTES:
        raise EventError("replayed state exceeds " + str(MAX_STATE_BYTES) + " bytes")
    _atomic_write(root / "docs/state.json", raw)
    return candidate


def migrate_legacy_state(
    root: str | Path, source_path: str | Path, *, dry_run: bool = True,
    imported_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a V2 schema-2 log losslessly. The operation is idempotent by source hash and event ID."""
    root = Path(root).resolve()
    preview = preview_legacy_migration(root, source_path)
    if dry_run:
        return {k: v for k, v in preview.items() if k not in {"events", "legacy_top_level"}}
    state_path = root / "docs/state.json"
    try:
        current = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EventError("current V3 state is unreadable; legacy events were not imported") from exc
    previous = current.get("legacy_history")
    if isinstance(previous, dict) and previous.get("source_sha256") == preview["source_sha256"]:
        return {"legacy_entries": preview["legacy_entries"], "already_migrated": True,
                "imported_now": 0, "final_sequence": len(read_events(root)),
                "state_bytes": len(state_path.read_bytes())}
    timestamp = imported_at or _now()
    imported_ids = []
    for item in preview["events"]:
        event = append_event(
            root, item["event_type"], item["phase"], item["actor"], item["details"],
            commit=item["commit"], evidence_ref=item["evidence_ref"], source=item["source"],
            occurred_at=item["occurred_at"], imported_at=timestamp, event_id=item["event_id"],
        )
        imported_ids.append(event["event_id"])
    summary_id = "legacy-import-summary-" + preview["source_sha256"][:16]
    summary = append_event(
        root, "legacy_state_imported", None, "vibe-migration",
        {"source_schema": 2, "source_sha256": preview["source_sha256"],
         "entries": preview["legacy_entries"], "imported_event_ids": imported_ids,
         "legacy_top_level": preview["legacy_top_level"]},
        source="v2-state-schema-2", imported_at=timestamp, event_id=summary_id,
    )
    current["legacy_history"] = {
        "source_schema": 2, "source_sha256": preview["source_sha256"],
        "imported_entries": preview["legacy_entries"], "summary_event_id": summary["event_id"],
    }
    written = write_snapshot(root, current, "legacy_migration_snapshot_written", "vibe-migration",
                             {"source_sha256": preview["source_sha256"]})
    return {
        "legacy_entries": preview["legacy_entries"], "already_imported": preview["already_imported"],
        "imported_now": preview["would_import"], "final_sequence": written["event_ledger"]["sequence"],
        "state_bytes": len((root / "docs/state.json").read_bytes()),
    }


def verify_project(root: str | Path = ".") -> Dict[str, Any]:
    root = Path(root).resolve()
    history = read_events(root)
    state_path = root / "docs/state.json"
    try:
        raw = state_path.read_bytes()
        state = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EventError("current state is unreadable") from exc
    if len(raw) > MAX_STATE_BYTES:
        raise EventError("state exceeds " + str(MAX_STATE_BYTES) + " bytes")
    pointer = state.get("event_ledger") if isinstance(state, dict) else None
    snapshot_events = [item for item in history if isinstance(item["details"].get("snapshot_after"), dict)]
    if history and not isinstance(pointer, dict):
        raise EventError("ledger has events but state has no event_ledger pointer")
    if pointer is not None:
        if not isinstance(pointer, dict) or isinstance(pointer.get("sequence"), bool) or not isinstance(pointer.get("sequence"), int):
            raise EventError("state event_ledger pointer is invalid")
        seq = pointer["sequence"]
        if seq < 1 or seq > len(history):
            raise EventError("state event_ledger sequence is outside the ledger")
        if not snapshot_events or snapshot_events[-1]["seq"] != seq:
            raise EventError("state event_ledger pointer does not reference the latest snapshot event")
        referenced = history[seq - 1]
        if pointer.get("last_event_id") != referenced["event_id"] or pointer.get("last_event_hash") != referenced["event_hash"]:
            raise EventError("state event_ledger hash pointer does not match")
    legacy = state.get("legacy_history") if isinstance(state, dict) else None
    if legacy is not None:
        if not isinstance(legacy, dict) or not isinstance(legacy.get("summary_event_id"), str):
            raise EventError("legacy history summary pointer is invalid")
        summary = next((item for item in history if item["event_id"] == legacy["summary_event_id"]), None)
        if summary is None or summary["event_type"] != "legacy_state_imported":
            raise EventError("legacy history summary event is missing")
        details = summary["details"]
        ids = details.get("imported_event_ids")
        if details.get("source_sha256") != legacy.get("source_sha256") or details.get("entries") != legacy.get("imported_entries"):
            raise EventError("legacy history summary does not match the state marker")
        if not isinstance(ids, list) or len(ids) != legacy.get("imported_entries"):
            raise EventError("legacy history imported event list is incomplete")
        indexed = {item["event_id"]: item for item in history}
        for event_id in ids:
            item = indexed.get(event_id)
            if item is None or item["event_type"] != "legacy_phase_recorded" or item["source"] != "v2-state-schema-2":
                raise EventError("legacy history references a missing or invalid imported event")
    return {
        "events": len(history),
        "last_hash": history[-1]["event_hash"] if history else GENESIS,
        "state_bytes": len(raw),
        "state_limit_bytes": MAX_STATE_BYTES,
    }
