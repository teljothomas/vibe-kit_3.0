"""Minimal V3 state reader and validator. Durable event history lands in Phase 30."""
import json
from pathlib import Path

STATE_PATH = Path("docs/state.json")
REQUIRED = {"schema", "phase", "status", "last_gate", "next"}
STATUSES = {"not_started", "in_progress", "gated", "approved", "rejected"}

class StateError(ValueError):
    """Raised when the current state is absent or invalid."""

def load(path=STATE_PATH):
    path = Path(path)
    if not path.is_file():
        raise StateError("docs/state.json is missing — initialize the project first")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError("docs/state.json is unreadable or invalid JSON") from exc
    if not isinstance(data, dict) or REQUIRED - set(data):
        raise StateError("docs/state.json does not match the V3 state shape")
    if data.get("schema") != 1:
        raise StateError("unsupported V3 state schema")
    if data.get("status") not in STATUSES:
        raise StateError("docs/state.json has an invalid phase status")
    phase = data.get("phase")
    if not isinstance(phase, str) or len(phase) != 2 or not phase.isdigit():
        raise StateError("docs/state.json phase must be a two-digit string")
    gate = data.get("last_gate")
    if not isinstance(gate, dict) or gate.get("phase") != phase:
        raise StateError("docs/state.json last_gate must reference the current phase")
    return data
