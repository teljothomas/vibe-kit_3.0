"""Read-only structural and governance verification."""
from pathlib import Path
from . import governance, state


def run():
    try:
        current = state.load()
    except state.StateError as exc:
        print("VERIFY-FAIL " + str(exc))
        return 1
    phase_file = Path("docs/phases") / ("phase-" + current["phase"] + ".md")
    if not phase_file.is_file():
        print("VERIFY-FAIL active phase contract is missing: " + str(phase_file))
        return 1
    if not Path("docs/invariants.md").is_file():
        print("VERIFY-FAIL canonical invariants are missing")
        return 1
    ok, message = governance.check_governance(Path.cwd())
    if not ok:
        print("VERIFY-FAIL " + (message or "governance check failed"))
        return 1
    print("VERIFY-OK phase-" + current["phase"] + " state-contract-and-governance-valid")
    return 0
