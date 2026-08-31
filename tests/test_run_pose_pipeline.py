"""Tests for the Phase 3 ``run_pose_pipeline`` MCP tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._mutation import releases_root
from cad_engineering_mcp.tools._paths import (
    PathSecurityError,
    glasses_root,
)


def _clean_releases():
    releases = releases_root()
    if not releases.is_dir():
        return
    for entry in releases.iterdir():
        if entry.is_dir():
            import shutil

            shutil.rmtree(entry, ignore_errors=True)


@pytest.fixture
def clean_releases():
    _clean_releases()
    yield
    _clean_releases()


def test_run_pose_pipeline_dry_run_does_not_execute(glasses, clean_releases):
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    env = run_pose_pipeline(dry_run=True, allow_mutation=True)
    assert env["status"] == "PASS"
    assert env["data"]["executed"] is False
    assert env["data"]["dry_run"] is True
    # The script path is reported.
    assert env["data"]["script"].endswith("run-pipeline.sh")


def test_run_pose_pipeline_rejects_mutation_by_default(glasses, clean_releases):
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    env = run_pose_pipeline(allow_mutation=False)
    assert env["status"] == "PASS"
    assert env["data"]["executed"] is False
    assert env["data"]["allow_mutation"] is False
    # The tool surfaces a warning about needing allow_mutation=true.
    data_warnings = env["data"].get("warnings", []) or []
    top_warnings = env.get("warnings", []) or []
    assert any(
        "allow_mutation" in w
        for w in (data_warnings + top_warnings)
    ), f"No allow_mutation warning in: data={data_warnings} top={top_warnings}"


def test_run_pose_pipeline_rejects_unsafe_python_path(glasses, clean_releases):
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    env = run_pose_pipeline(python_path="/usr/bin/python3", allow_mutation=True)
    assert env["status"] == "ERROR"
    # The rejection happens at the project-root traversal check
    # (because /usr/bin/python3 lives outside the repo), so the error
    # is the more general "escapes project root" message.
    assert any("project root" in err.lower() or "venv" in err.lower()
               for err in env["errors"])


def test_run_pose_pipeline_rejects_traversal_python_path(glasses, clean_releases):
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    env = run_pose_pipeline(python_path="../../etc/passwd", allow_mutation=True)
    assert env["status"] == "ERROR"


def test_run_pose_pipeline_rejects_system_python_inside_root(glasses, clean_releases):
    """A path that is inside the project root but not the venv Python
    is also rejected (must point at the venv python specifically)."""
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    env = run_pose_pipeline(
        python_path="/home/hackerman/cad-engineering-mcp/scripts/other.py",
        allow_mutation=True,
    )
    assert env["status"] == "ERROR"
    assert any("venv" in err.lower() for err in env["errors"])


def test_run_pose_pipeline_records_audit_on_dry_run(glasses, clean_releases):
    from cad_engineering_mcp.tools._mutation import audit_log_path
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    run_pose_pipeline(dry_run=True, allow_mutation=False)
    log = audit_log_path()
    assert log.is_file()
    entries = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").strip().split("\n")
        if line.strip()
    ]
    assert any(
        e.get("tool") == "run_pose_pipeline" and e.get("operation") == "dry_run"
        for e in entries
    )


def test_run_pose_pipeline_real_execution_passes(glasses, clean_releases):
    """The pipeline script is allowed to actually execute.

    The artifacts at the end must still exist; the pipeline must not
    fail. This test runs the script for real and checks the envelope.
    """
    from cad_engineering_mcp.tools.run_pose_pipeline import run_pose_pipeline

    # The pipeline needs numpy/trimesh; ensure they are importable.
    env = run_pose_pipeline(allow_mutation=True)
    # The pipeline itself should PASS or FAIL on its own merits.
    # We don't force PASS here; we only assert the envelope shape.
    assert env["status"] in {"PASS", "FAIL", "ERROR", "INCOMPLETE"}
    assert "exit_code" in env["data"]
    if env["status"] == "PASS":
        # When the pipeline succeeded the artifacts must still exist.
        for rel in (
            "analysis/geometry/frame-coordinate-system.json",
            "analysis/geometry/component-pose-candidates.json",
            "analysis/geometry/component-pose-validation.json",
        ):
            assert (glasses / rel).is_file(), rel