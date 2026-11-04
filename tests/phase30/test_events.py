import json
import shutil
from pathlib import Path

import pytest

from vibe import events

FIXTURE = Path(__file__).parent / "fixtures" / "v2-state.schema2.json"


def _project(root: Path):
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "state.json").write_text(json.dumps({
        "schema": 1,
        "phase": "29",
        "status": "approved",
        "last_gate": {"phase": "29", "status": "passed", "commit": "02f3a5f"},
        "next": "Start Phase 30",
    }), encoding="utf-8")
    return root


def test_real_v2_fixture_has_22_losslessly_importable_entries():
    legacy = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert legacy["schema"] == 2
    assert len(legacy["log"]) == 22
    assert sum(item.get("approved_at") is None for item in legacy["log"]) == 3
    assert all(item.get("signature") is None for item in legacy["log"])


def test_migration_preview_is_read_only_and_reports_exact_legacy_facts(tmp_path):
    root = _project(tmp_path)
    preview = events.preview_legacy_migration(root, FIXTURE)
    assert preview["legacy_entries"] == 22
    assert preview["would_import"] == 22
    assert preview["null_original_timestamps"] == 3
    assert not (root / "docs/events/ledger.jsonl").exists()
    assert len(preview["legacy_top_level"]["active_deviations"]) > 0


def test_migration_preserves_all_records_and_is_idempotent(tmp_path):
    root = _project(tmp_path)
    legacy = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = events.migrate_legacy_state(root, FIXTURE, dry_run=False, imported_at="2026-11-04T00:00:00Z")
    history = events.read_events(root)
    imported = [item for item in history if item["event_type"] == "legacy_phase_recorded"]
    assert result["legacy_entries"] == 22
    assert result["imported_now"] == 22
    assert len(imported) == 22
    assert [item["details"]["legacy_entry"] for item in imported] == legacy["log"]
    assert [item["details"]["legacy_index"] for item in imported] == list(range(22))
    assert sum(item["occurred_at"] is None for item in imported) == 3
    assert all(item["details"]["human_approved"] is False for item in imported)
    # Duplicate phase rows are distinct legacy events, never collapsed.
    assert len([item for item in imported if item["phase"] == "16"]) == 2
    assert len([item for item in imported if item["phase"] == "17"]) == 2
    assert len([item for item in imported if item["phase"] == "18"]) == 2
    assert result["state_bytes"] <= events.MAX_STATE_BYTES
    before = len(history)
    again = events.migrate_legacy_state(root, FIXTURE, dry_run=False, imported_at="2026-11-05T00:00:00Z")
    assert again["already_migrated"] is True
    assert again["imported_now"] == 0
    assert len(events.read_events(root)) == before


def test_hash_chain_detects_alteration_and_truncated_tail(tmp_path):
    root = _project(tmp_path)
    events.append_event(root, "phase_started", "30", "human", {"decision": "start"})
    raw = (root / "docs/events/ledger.jsonl").read_bytes()
    altered = raw.replace(b'"decision":"start"', b'"decision":"other"')
    with pytest.raises(events.EventError, match="hash mismatch"):
        events.verify_bytes(altered)
    with pytest.raises(events.EventError, match="truncated"):
        events.verify_bytes(raw[:-2])


def test_duplicate_supplied_event_id_is_idempotent(tmp_path):
    root = _project(tmp_path)
    first = events.append_event(root, "decision_recorded", "30", "agent-autonomous",
                                {"class": "architecture"}, event_id="decision-fixed-1")
    second = events.append_event(root, "decision_recorded", "30", "agent-autonomous",
                                 {"class": "architecture"}, event_id="decision-fixed-1")
    assert first == second
    assert len(events.read_events(root)) == 1


def test_snapshot_replay_recovers_after_interrupted_state_write(tmp_path):
    root = _project(tmp_path)
    snapshot = json.loads((root / "docs/state.json").read_text(encoding="utf-8"))
    snapshot["phase"] = "30"
    snapshot["status"] = "in_progress"
    events.write_snapshot(root, snapshot, "phase_started", "human", {"phase": "30"})
    (root / "docs/state.json").write_text("{truncated", encoding="utf-8")
    recovered = events.replay_snapshot(root)
    assert recovered["phase"] == "30"
    assert recovered["status"] == "in_progress"
    assert events.verify_project(root)["events"] == 1


def test_compact_snapshot_remains_bounded_after_100_transitions(tmp_path):
    root = _project(tmp_path)
    snapshot = json.loads((root / "docs/state.json").read_text(encoding="utf-8"))
    for number in range(100):
        snapshot = dict(snapshot)
        snapshot["phase"] = "30"
        snapshot["status"] = "gated" if number % 2 else "in_progress"
        snapshot["next"] = "Transition " + str(number)
        snapshot = events.write_snapshot(
            root, snapshot, "phase_transition_recorded", "agent-autonomous",
            {"transition": number},
        )
        assert (root / "docs/state.json").stat().st_size <= events.MAX_STATE_BYTES
    report = events.verify_project(root)
    assert report["events"] == 100
    assert report["state_bytes"] <= 4096
    assert len(snapshot["event_ledger"]["recent"]) == 5


def test_reusing_event_id_with_different_data_is_rejected(tmp_path):
    root = _project(tmp_path)
    events.append_event(root, "decision_recorded", "30", "agent-autonomous",
                        {"class": "architecture"}, event_id="fixed-id")
    with pytest.raises(events.EventError, match="different details"):
        events.append_event(root, "decision_recorded", "30", "agent-autonomous",
                            {"class": "security"}, event_id="fixed-id")


def test_event_schema_has_exact_runtime_fields():
    schema_path = Path(__file__).resolve().parents[2] / "docs/contracts/event.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = {
        "schema", "seq", "event_id", "event_type", "phase", "occurred_at",
        "imported_at", "actor", "commit", "evidence_ref", "source", "details",
        "prev_hash", "event_hash",
    }
    assert set(schema["required"]) == required
    assert schema["additionalProperties"] is False
