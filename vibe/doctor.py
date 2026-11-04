"""Environment and repository integrity checks."""
import sys
from pathlib import Path

from . import state

REQUIRED_FILES = ("README.md", "AGENTS.md", "docs/invariants.md", "docs/state.json", "scripts/gate")

def run(strict=False):
    checks = []
    checks.append(("python", sys.version_info >= (3, 9), "Python 3.9 or newer"))
    for name in REQUIRED_FILES:
        p = Path(name)
        checks.append(("file:" + name, p.is_file(), "required repository file"))
    try:
        state.load()
        state_ok, state_message = True, "valid V3 state"
    except state.StateError as exc:
        state_ok, state_message = False, str(exc)
    checks.append(("state", state_ok, state_message))
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        deps_ok = "dependencies = []" in content
        checks.append(("runtime-dependencies", deps_ok, "runtime core must remain dependency-free"))
    failed = [row for row in checks if not row[1]]
    for name, ok, detail in checks:
        print(("PASS" if ok else "FAIL") + " " + name + " — " + detail)
    return 1 if failed else 0
