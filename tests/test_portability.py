"""Regression: Git fixtures must follow the configured initial branch, not assume master."""
import subprocess
import pytest


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.mark.parametrize("default_branch", ["main", "master"])
def test_fixture_returns_to_actual_initial_branch(tmp_path, default_branch):
    git(["-c", "init.defaultBranch=" + default_branch, "init", "-q"], tmp_path)
    git(["config", "user.name", "Vibe Test"], tmp_path)
    git(["config", "user.email", "vibe-test@example.invalid"], tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(["add", "seed.txt"], tmp_path)
    git(["commit", "-m", "seed", "-q"], tmp_path)
    initial_branch = git(["branch", "--show-current"], tmp_path).stdout.strip()
    assert initial_branch == default_branch
    git(["switch", "-c", "temporary"], tmp_path)
    git(["switch", initial_branch], tmp_path)
    assert git(["branch", "--show-current"], tmp_path).stdout.strip() == initial_branch
