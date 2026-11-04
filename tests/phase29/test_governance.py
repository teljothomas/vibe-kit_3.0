import importlib.util
import json
import sys
from pathlib import Path

import pytest

from vibe import governance

ROOT = Path(__file__).resolve().parents[2]


def load_guard_core():
    path = ROOT / "plugins" / "vibe-kit" / "scripts" / "guard_core.py"
    spec = importlib.util.spec_from_file_location("vibe_guard_core_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_loader_template_and_standalone_guard_defaults_have_exact_parity():
    template = json.loads((ROOT / "plugins/vibe-kit/templates/governance.json").read_text(encoding="utf-8"))
    core = load_guard_core()
    assert template == governance.DEFAULT_POLICY
    assert core.DEFAULT_POLICY == governance.DEFAULT_POLICY
    assert governance.load_policy(ROOT) == governance.DEFAULT_POLICY


@pytest.mark.parametrize("target", [
    "docs/phases/phase-29.md",
    "docs\\phases\\PHASE-29.MD",
    "docs/phases/phase-00.md",
    "docs/invariants.md",
    "docs/state.json",
    "docs/contracts/cli.json",
])
def test_protected_defaults_match_path_variants(target, tmp_path):
    relative = governance.normalize_relative_path(tmp_path, target)
    assert governance.is_protected_path(relative)


@pytest.mark.parametrize("target", [
    "docs/phases/phase-29.context.md",
    "docs/phases/phase-29.repair.md",
    "docs/proposals/phase-29-amend.md",
    "src/app.py",
])
def test_generated_and_non_authoritative_paths_are_not_protected(target):
    assert not governance.is_protected_path(target)


def test_path_traversal_is_rejected(tmp_path):
    with pytest.raises(governance.GovernanceError, match="traversal"):
        governance.normalize_relative_path(tmp_path, "docs/../secrets.txt")


def test_absolute_path_outside_project_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(governance.GovernanceError, match="outside"):
        governance.normalize_relative_path(tmp_path, outside)


def test_symlink_escape_is_rejected(tmp_path):
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    try:
        (root / "docs").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip("directory symlinks are unavailable on this runner: " + str(exc))
    with pytest.raises(governance.GovernanceError, match="outside"):
        governance.normalize_relative_path(root, "docs/secret.txt")


def test_unresolved_proposal_blocks_gate_but_does_not_become_policy():
    from .conftest import make_repo
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = make_repo(Path(temp))
        proposal_dir = root / "docs/proposals"
        proposal_dir.mkdir()
        proposal = proposal_dir / "phase-29-amend.md"
        proposal.write_text("# A proposal only\n", encoding="utf-8")
        assert not governance.check_governance(root)[0]
        assert not governance.is_protected_path("docs/proposals/phase-29-amend.md")
        assert "phase-29-amend.md" in governance.check_governance(root)[1]


def test_custom_policy_cannot_remove_baseline_protected_paths(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "governance.json").write_text(
        json.dumps({"schema": 1, "protected_paths": ["src/private/**"]}),
        encoding="utf-8",
    )
    loaded = governance.load_policy(root)
    assert governance.is_protected_path("docs/state.json", loaded)
    assert governance.is_protected_path("docs/invariants.md", loaded)
    assert governance.is_protected_path("src/private/data.json", loaded)


def test_generated_suffix_does_not_exempt_other_protected_paths():
    assert governance.is_protected_path("docs/contracts/important.context.md")
    assert governance.is_protected_path("docs/contracts/important.repair.md")
    assert not governance.is_protected_path("docs/phases/phase-29.context.md")
    assert not governance.is_protected_path("docs/phases/phase-29.repair.md")


def test_any_non_readme_proposal_artifact_blocks_gate(tmp_path):
    from .conftest import make_repo
    root = make_repo(tmp_path)
    (root / "docs" / "proposals").mkdir(parents=True)
    (root / "docs" / "proposals" / "unexpected-name.txt").write_text("change request", encoding="utf-8")
    ok, message = governance.check_governance(root)
    assert not ok
    assert "unexpected-name.txt" in message


def test_guard_mechanism_and_ci_entrypoints_are_protected():
    for target in (
        "AGENTS.md",
        ".github/workflows/test.yml",
        "plugins/vibe-kit/hooks/hooks.json",
        "plugins/vibe-kit/scripts/guard_core.py",
        "scripts/gate",
        "tests/phase29/test_guard.py",
        "tests/test_ci_contract.py",
        "vibe/approvals.py",
        "vibe/cli.py",
        "vibe/doctor.py",
        "vibe/githooks.py",
        "vibe/governance.py",
        "vibe/verify.py",
    ):
        assert governance.is_protected_path(target), target
