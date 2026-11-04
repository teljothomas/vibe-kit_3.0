"""Environment and repository integrity checks."""
import importlib.util
import json
import sys
from pathlib import Path

from . import governance, state

REQUIRED_FILES = (
    "README.md", "AGENTS.md", "docs/invariants.md", "docs/state.json", "scripts/gate",
    "vibe/governance.py", "vibe/approvals.py", "vibe/githooks.py",
    "plugins/vibe-kit/scripts/guard.py", "plugins/vibe-kit/scripts/guard_core.py",
    "plugins/vibe-kit/templates/governance.json", "plugins/vibe-kit/hooks/hooks.json",
)


def run(strict=False):
    checks = [("python", sys.version_info >= (3, 9), "Python 3.9 or newer")]
    for name in REQUIRED_FILES:
        checks.append(("file:" + name, Path(name).is_file(), "required repository file"))
    try:
        state.load()
        state_ok, state_message = True, "valid V3 state"
    except state.StateError as exc:
        state_ok, state_message = False, str(exc)
    checks.append(("state", state_ok, state_message))
    try:
        governance.load_policy(Path.cwd())  # validate any project override, if present
        template_path = Path("plugins/vibe-kit/templates/governance.json")
        template = json.loads(template_path.read_text(encoding="utf-8"))
        guard_path = Path("plugins/vibe-kit/scripts/guard_core.py")
        spec = importlib.util.spec_from_file_location("vibe_guard_core_doctor", guard_path)
        guard_core = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(guard_core)
        parity_ok = template == governance.DEFAULT_POLICY and guard_core.DEFAULT_POLICY == governance.DEFAULT_POLICY
        parity_message = "loader defaults, plugin template and standalone guard have exact parity"
    except (OSError, json.JSONDecodeError, governance.GovernanceError) as exc:
        parity_ok, parity_message = False, "governance policy is invalid: " + str(exc)
    checks.append(("policy-parity", parity_ok, parity_message))
    ok, message = governance.check_governance(Path.cwd())
    checks.append(("amendments", ok, message or "no unresolved amendment proposals"))
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        deps_ok = "dependencies = []" in content
        checks.append(("runtime-dependencies", deps_ok, "runtime core must remain dependency-free"))
    failed = [row for row in checks if not row[1]]
    for name, passed, detail in checks:
        print(("PASS" if passed else "FAIL") + " " + name + " — " + (detail or ""))
    return 1 if failed else 0
