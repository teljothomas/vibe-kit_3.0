import json
import subprocess
from pathlib import Path


def make_repo(root: Path, phase="29") -> Path:
    (root / "docs" / "phases").mkdir(parents=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "state.json").write_text(json.dumps({
        "schema": 1,
        "phase": phase,
        "status": "in_progress",
        "last_gate": {"phase": phase, "status": "not_run", "commit": None},
        "next": "Implement current phase",
    }), encoding="utf-8")
    (root / "docs" / "phases" / ("phase-" + phase + ".md")).write_text(
        "# Phase " + phase + "\n\n**Status:** in progress\n", encoding="utf-8"
    )
    (root / "docs" / "invariants.md").write_text("# Invariants\n\nDo not weaken them.\n", encoding="utf-8")
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Vibe Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "vibe-test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "add", "docs", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=root, check=True)
    return root


class TTY:
    def isatty(self):
        return True


def interactive_confirm(expected_reviewer="Test Human"):
    def answer(prompt):
        if "I reviewed this exact content" in prompt:
            return "I reviewed this exact content"
        if prompt.startswith("Reviewer name"):
            return expected_reviewer
        if prompt.startswith("Type APPLY "):
            return prompt.split("Type ", 1)[1].split(" to replace", 1)[0]
        if prompt.startswith("Review staged protected files"):
            return prompt.split("type ", 1)[1].split(":", 1)[0]
        raise AssertionError("Unexpected confirmation prompt: " + prompt)
    return answer
