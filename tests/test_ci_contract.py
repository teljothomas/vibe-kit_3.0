from pathlib import Path


def test_gate_workflow_installs_pytest_before_running_gate():
    workflow = Path(".github/workflows/vibe.yml").read_text(encoding="utf-8")
    install = workflow.index('pip install -e \".[test]\"')
    gate = workflow.index("scripts/gate --phase")
    assert install < gate
    assert 'python-version: \"3.13\"' in workflow
    assert "scripts/gate --phase 28" in workflow


def test_test_matrix_covers_supported_os_and_python_versions():
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")
    for platform in ("ubuntu-24.04", "macos-latest", "windows-latest"):
        assert platform in workflow
    for version in ('\"3.9\"', '\"3.11\"', '\"3.13\"'):
        assert version in workflow
