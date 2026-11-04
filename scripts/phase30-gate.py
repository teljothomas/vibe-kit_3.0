#!/usr/bin/env python3
"""Focused Phase 30 gate, kept separate from the frozen Phase 28/29 gate."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    commands = [
        [sys.executable, "-m", "pytest", "tests/phase30", "-q"],
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "-m", "vibe", "doctor", "--strict"],
        [sys.executable, "-m", "vibe", "verify"],
        [sys.executable, "-m", "vibe", "events", "verify"],
    ]
    for command in commands:
        proc = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
        if proc.returncode:
            output = (proc.stdout + "\n" + proc.stderr).strip().splitlines()
            detail = output[-1] if output else "no output"
            print("G-FAIL phase-30 — " + detail[:240])
            return 1
    print("G-PASS phase-30")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
