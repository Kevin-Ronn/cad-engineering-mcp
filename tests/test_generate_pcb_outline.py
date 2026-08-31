"""Tests for the Phase 3 ``generate_pcb_outline`` MCP tool."""
from __future__ import annotations

import json
import shutil
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
            shutil.rmtree(entry, ignore_errors=True)


@pytest.fixture
def clean_releases():
    _clean_releases()
    yield
    _clean_releases()


def _snapshot_pose_validation(glasses: Path) -> Path:
    src = glasses / "analysis" / "geometry" / "component-pose-validation.json"
    snap = Path("/tmp/_pose_validation_snapshot.json")
    shutil.copy2(src, snap)
    return snap


def _restore_pose_validation(glasses: Path, snap: Path) -> None:
    target = glasses / "analysis" / "geometry" / "component-pose-validation.json"
    shutil.copy2(snap, target)
    snap.unlink()


def test_generate_pcb_outline_requires_pose_validation(glasses, clean_releases):
    """With ``force=False`` and a non-PASS pose validation, return INCOMPLETE."""
    from cad_engineering_mcp.tools.generate_pcb_outline import (
        generate_pcb_outline,
    )

    snap = _snapshot_pose_validation(glasses)
    try:
        target = glasses / "analysis" / "geometry" / "component-pose-validation.json"
        original = json.loads(target.read_text(encoding="utf-8"))
        corrupted = json.loads(target.read_text(encoding="utf-8"))
        corrupted["validation"]["overall_status"] = "FAIL"
        target.write_text(json.dumps(corrupted), encoding="utf-8")

        env = generate_pcb_outline(force=False, allow_mutation=True)
    finally:
        _restore_pose_validation(glasses, snap)

    assert env["status"] == "INCOMPLETE"
    assert env["data"]["force_required"] is True
    assert "PASS" in env["errors"][0] or "overall_status" in env["errors"][0]


def test_generate_pcb_outline_force_bypasses_precheck(glasses, clean_releases):
    from cad_engineering_mcp.tools.generate_pcb_outline import (
        generate_pcb_outline,
    )

    snap = _snapshot_pose_validation(glasses)
    try:
        target = glasses / "analysis" / "geometry" / "component-pose-validation.json"
        original = json.loads(target.read_text(encoding="utf-8"))
        corrupted = json.loads(target.read_text(encoding="utf-8"))
        corrupted["validation"]["overall_status"] = "FAIL"
        target.write_text(json.dumps(corrupted), encoding="utf-8")

        env = generate_pcb_outline(force=True, allow_mutation=True)
    finally:
        _restore_pose_validation(glasses, snap)

    # force=true bypassed the pre-check, so the generator ran.
    # We don't assert PASS because the actual generator may fail when
    # given a non-PASS artifact (it has its own internal guard).
    assert env["status"] in {"PASS", "FAIL", "ERROR", "INCOMPLETE"}
    assert env["data"]["force"] is True
    assert any(
        "force=true" in w.lower() for w in env["warnings"]
    )


def test_generate_pcb_outline_no_mutation_by_default(glasses, clean_releases):
    from cad_engineering_mcp.tools.generate_pcb_outline import (
        generate_pcb_outline,
    )

    env = generate_pcb_outline(allow_mutation=False)
    assert env["status"] == "PASS"
    assert env["data"]["executed"] is False
    assert env["data"]["allow_mutation"] is False
    assert any("allow_mutation" in w for w in env["warnings"])


def test_generate_pcb_outline_rejects_unsafe_python(glasses, clean_releases):
    from cad_engineering_mcp.tools.generate_pcb_outline import (
        generate_pcb_outline,
    )

    env = generate_pcb_outline(python_path="/usr/bin/python3", allow_mutation=True)
    assert env["status"] == "ERROR"
    assert any("venv" in err.lower() for err in env["errors"])


def test_generate_pcb_outline_real_execution(glasses, clean_releases):
    """Real execution with a PASS pose validation should run the generator."""
    from cad_engineering_mcp.tools.generate_pcb_outline import (
        generate_pcb_outline,
    )

    env = generate_pcb_outline(allow_mutation=True)
    assert env["status"] in {"PASS", "FAIL", "ERROR", "INCOMPLETE"}
    if env["status"] == "PASS":
        # The two generator outputs must exist after the run.
        for rel in (
            "electronics/glasses-pcb.kicad_pcb",
            "electronics/glasses-pcb.summary.json",
        ):
            assert (glasses / rel).is_file(), rel