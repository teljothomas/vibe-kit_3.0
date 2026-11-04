import json
import subprocess
import sys
from pathlib import Path


def run_vibe(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "vibe", *args], cwd=cwd, text=True, capture_output=True)


def test_version_runs():
    proc = run_vibe("--version")
    assert proc.returncode == 0
    assert "3.0.0a1" in proc.stdout


def test_status_is_compact_json():
    proc = run_vibe("status")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["phase"] == "28"
    assert payload["status"] in {"not_started", "in_progress", "gated", "approved", "rejected"}


def test_doctor_and_verify_pass_from_repository_root():
    assert run_vibe("doctor", "--strict").returncode == 0
    assert run_vibe("verify").returncode == 0
