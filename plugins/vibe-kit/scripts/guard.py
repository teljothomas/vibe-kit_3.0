#!/usr/bin/env python3
"""Claude Code PreToolUse adapter for the standalone V3 governance guard."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from guard_core import decide


def _project_root(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    candidate = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(candidate).resolve()


def _deny(reason: str) -> None:
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        root = _project_root()
        state_path = root / "docs" / "state.json"
        if state_path.exists():
            _deny("malformed PreToolUse JSON in a Vibe-governed project; write denied")
        return 0  # Unrelated projects are not affected by a global hook installation.
    root = _project_root(payload)
    decision = decide(payload, root)
    if decision["decision"] == "deny":
        _deny(decision["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
