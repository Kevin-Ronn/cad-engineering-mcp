"""Tests for the Phase 3 assembly MCP tools.

Covers:

* list_assembly_components (read-only, structured)
* add_assembly_component mutation, backup, audit
* duplicate-component rejection
* out-of-bounds rejection
* invalid numeric values (NaN, infinity, wrong length)
* coordinate-system validation
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._mutation import releases_root
from cad_engineering_mcp.tools._paths import glasses_root


ASSEMBLY_REL = Path("mechanical/assemblies/glasses-assembly.yaml")


def _snapshot_assembly(glasses: Path) -> Path:
    """Copy the assembly YAML to a tmp path so tests can restore it."""
    src = glasses / ASSEMBLY_REL
    snap = Path("/tmp/_assembly_snapshot_test.yaml")
    shutil.copy2(src, snap)
    return snap


def _restore_assembly(glasses: Path, snapshot: Path) -> None:
    target = glasses / ASSEMBLY_REL
    shutil.copy2(snapshot, target)
    snapshot.unlink()


# ---------------------------------------------------------------------------
# list_assembly_components
# ---------------------------------------------------------------------------


def test_list_assembly_components_returns_structured_envelope(glasses):
    from cad_engineering_mcp.tools.assembly_tools import (
        list_assembly_components,
    )

    snap = _snapshot_assembly(glasses)
    try:
        envelope = list_assembly_components()
    finally:
        _restore_assembly(glasses, snap)

    assert envelope["status"] == "PASS"
    assert envelope["tool"] == "list_assembly_components"
    assert "started_at_iso" in envelope
    assert "duration_ms" in envelope
    assert envelope["data"]["units"] == "mm"
    assert isinstance(envelope["data"]["components"], list)
    assert envelope["data"]["component_count"] == len(
        envelope["data"]["components"]
    )


def test_list_assembly_components_does_not_mutate(glasses):
    from cad_engineering_mcp.tools.assembly_tools import (
        list_assembly_components,
    )

    snap = _snapshot_assembly(glasses)
    try:
        before = (glasses / ASSEMBLY_REL).read_bytes()
        list_assembly_components()
        list_assembly_components()
        list_assembly_components()
        after = (glasses / ASSEMBLY_REL).read_bytes()
        assert before == after
    finally:
        _restore_assembly(glasses, snap)


# ---------------------------------------------------------------------------
# add_assembly_component
# ---------------------------------------------------------------------------


def _clean_releases_dir():
    """Clear any releases/<ts>/ files created during the test session.

    Keeps the directory itself around (other tests may rely on its
    existence) but removes any timestamped sub-directories that
    resulted from test mutations.
    """
    releases = releases_root()
    if not releases.is_dir():
        return
    for entry in releases.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)


@pytest.fixture
def clean_releases():
    _clean_releases_dir()
    yield
    _clean_releases_dir()


def test_add_assembly_component_success(glasses, clean_releases):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
        list_assembly_components,
    )

    snap = _snapshot_assembly(glasses)
    try:
        envelope = add_assembly_component(
            component_id="phase3_test_unit",
            position_mm=[167.1, 100.0, 25.5],
            rotation_deg=[0.0, 0.0, 0.0],
        )
    finally:
        # Roll back so other tests see the original assembly.
        _restore_assembly(glasses, snap)

    assert envelope["status"] == "PASS"
    assert envelope["tool"] == "add_assembly_component"
    data = envelope["data"]
    assert data["component_id"] == "phase3_test_unit"
    assert data["position_mm"] == [167.1, 100.0, 25.5]
    assert data["backup"] is not None
    # Confirm a backup exists on disk under releases/<ts>/.
    assert (glasses / data["backup"]).is_file()


def test_add_assembly_component_records_audit(glasses, clean_releases):
    from cad_engineering_mcp.tools._mutation import audit_log_path
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        env = add_assembly_component(
            component_id="phase3_audit_unit",
            position_mm=[160.0, 110.0, 10.0],
        )
    finally:
        _restore_assembly(glasses, snap)

    assert env["status"] == "PASS"
    audit_path = glasses / env["data"]["backup"]
    # Find the audit log for today's date.
    log_path = audit_log_path()
    assert log_path.is_file()
    entries = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").strip().split("\n")
        if line.strip()
    ]
    add_entries = [
        e
        for e in entries
        if e.get("tool") == "add_assembly_component"
        and e.get("metadata", {}).get("component_id") == "phase3_audit_unit"
    ]
    assert add_entries, "No audit entry for add_assembly_component"
    entry = add_entries[-1]
    assert entry["operation"] == "add"
    assert entry["success"] is True
    assert "mechanical/assemblies/glasses-assembly.yaml" in entry[
        "affected_paths"
    ]


def test_add_assembly_component_rejects_duplicate(glasses, clean_releases):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        first = add_assembly_component(
            component_id="phase3_dup_unit",
            position_mm=[167.0, 105.0, 20.0],
        )
        assert first["status"] == "PASS"

        second = add_assembly_component(
            component_id="phase3_dup_unit",
            position_mm=[167.0, 105.0, 20.0],
        )
    finally:
        _restore_assembly(glasses, snap)

    assert second["status"] == "ERROR"
    assert any(
        "already" in err.lower() for err in second["errors"]
    ), second["errors"]


def test_add_assembly_component_rejects_out_of_bounds(glasses, clean_releases):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        env = add_assembly_component(
            component_id="phase3_oob_unit",
            position_mm=[1.0, 1.0, 1.0],  # far outside the frame bbox
        )
    finally:
        _restore_assembly(glasses, snap)

    assert env["status"] == "ERROR"
    assert any(
        "outside" in err.lower() or "bounding box" in err.lower()
        for err in env["errors"]
    ), env["errors"]
    assert env["data"].get("frame_bbox_mm") is not None


def test_add_assembly_component_out_of_bounds_override(glasses, clean_releases):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        env = add_assembly_component(
            component_id="phase3_oob_override_unit",
            position_mm=[1.0, 1.0, 1.0],
            confirm_out_of_bounds=True,
        )
    finally:
        _restore_assembly(glasses, snap)

    assert env["status"] == "PASS"
    assert env["data"]["out_of_bounds"] is True
    assert any(
        "outside" in w.lower() for w in env.get("warnings", [])
    ) or any(
        "outside" in w.lower() for w in env.get("warnings", []) or []
    )


@pytest.mark.parametrize(
    "bad_position",
    [
        [math.nan, 1.0, 2.0],
        [math.inf, 1.0, 2.0],
        [-math.inf, 1.0, 2.0],
        [1.0, 2.0],                # too short
        [1.0, 2.0, 3.0, 4.0],      # too long
        "not a list",
        [True, 1.0, 2.0],          # bool rejected
        ["x", 1.0, 2.0],           # string not allowed
    ],
)
def test_add_assembly_component_rejects_invalid_position(
    bad_position, glasses, clean_releases
):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        env = add_assembly_component(
            component_id=f"phase3_invalid_pos_{id(bad_position)}",
            position_mm=bad_position,  # type: ignore[arg-type]
        )
    finally:
        _restore_assembly(glasses, snap)

    assert env["status"] == "ERROR"


@pytest.mark.parametrize(
    "bad_rotation",
    [
        [math.nan, 0.0, 0.0],
        [math.inf, 0.0, 0.0],
        [0.0, 0.0],                # too short
        [0.0, 0.0, 0.0, 0.0],      # too long
        [True, False, True],
    ],
)
def test_add_assembly_component_rejects_invalid_rotation(
    bad_rotation, glasses, clean_releases
):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        env = add_assembly_component(
            component_id=f"phase3_invalid_rot_{id(bad_rotation)}",
            position_mm=[167.0, 110.0, 22.0],
            rotation_deg=bad_rotation,  # type: ignore[arg-type]
        )
    finally:
        _restore_assembly(glasses, snap)

    assert env["status"] == "ERROR"


def test_add_assembly_component_rejects_empty_component_id(
    glasses, clean_releases
):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    env = add_assembly_component(
        component_id="",
        position_mm=[167.0, 110.0, 22.0],
    )
    assert env["status"] == "ERROR"


def test_add_assembly_component_rejects_bad_coordinate_system(
    glasses, clean_releases
):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        env = add_assembly_component(
            component_id="phase3_bad_cs",
            position_mm=[167.0, 110.0, 22.0],
            coordinate_system="",
        )
    finally:
        _restore_assembly(glasses, snap)

    assert env["status"] == "ERROR"


def test_add_assembly_component_writes_valid_yaml(glasses, clean_releases):
    from cad_engineering_mcp.tools.assembly_tools import (
        add_assembly_component,
    )

    snap = _snapshot_assembly(glasses)
    try:
        add_assembly_component(
            component_id="phase3_yaml_validity",
            position_mm=[167.0, 120.0, 22.0],
            rotation_deg=[0.0, 0.0, 0.0],
        )
        # Re-read the YAML through the read path and confirm it is
        # still parseable and contains the new component.
        import yaml
        text = (glasses / ASSEMBLY_REL).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert "phase3_yaml_validity" in data["components"]
        comp = data["components"]["phase3_yaml_validity"]
        assert comp["position_mm"] == [167.0, 120.0, 22.0]
        assert comp["coordinate_system"] == "glasses_master"
    finally:
        _restore_assembly(glasses, snap)