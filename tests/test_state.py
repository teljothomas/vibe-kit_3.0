import json
import pytest
from vibe.state import StateError, load


def test_current_state_is_valid():
    state = load()
    assert state["phase"] == "28"


def test_invalid_state_fails_closed(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"schema": 999}), encoding="utf-8")
    with pytest.raises(StateError, match="does not match|unsupported"):
        load(p)
