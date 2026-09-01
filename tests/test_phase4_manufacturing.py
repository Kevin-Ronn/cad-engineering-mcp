"""Tests for the Phase 4 DFM/DFA, PCB-reconciliation, and
manufacturing-readiness tools."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._paths import glasses_root


SCHEMATIC_REL = Path("electronics/schematic-architecture.yaml")
STRUCTURAL_REL = Path("mechanical/main-frame/structural-policy.yaml")
COMPONENT_MOUNTS_REL = Path("mechanical/main-frame/component-mounts.yaml")
MOUNTING_INTERFACES_REL = Path("mechanical/interfaces/mounting-interfaces.yaml")
REMOVABLE_FRONT_REL = Path("mechanical/removable-front/interface.yaml")


@pytest.fixture
def snapshot_yaml():
    """Snapshot the YAMLs these tools read so tests can restore them."""
    glasses = glasses_root()
    paths = [
        glasses / SCHEMATIC_REL,
        glasses / STRUCTURAL_REL,
        glasses / COMPONENT_MOUNTS_REL,
        glasses / MOUNTING_INTERFACES_REL,
        glasses / REMOVABLE_FRONT_REL,
    ]
    snapshots = []
    for p in paths:
        snap = Path(f"/tmp/_phase4_snap_{p.name}")
        shutil.copy2(p, snap)
        snapshots.append((p, snap))
    yield snapshots
    for p, snap in snapshots:
        shutil.copy2(snap, p)
        snap.unlink()


# ---------------------------------------------------------------------------
# DFM/DFA
# ---------------------------------------------------------------------------


def test_validate_dfm_dfa_returns_envelope():
    from cad_engineering_mcp.tools.manufacturing_tools import (
        validate_dfm_dfa as tool,
    )

    env = tool()
    assert env["status"] in {"PASS", "INCOMPLETE", "FAIL", "ERROR"}
    data = env["data"]
    assert "dfm" in data
    assert "dfa" in data
    assert "tbd_fields" in data
    assert isinstance(data["dfm"]["findings"], list)
    assert isinstance(data["dfa"]["findings"], list)


def test_validate_dfm_dfa_current_state_incomplete():
    """The current project state is INCOMPLETE (DFM/DFA fields are TBD)."""
    from cad_engineering_mcp.tools.manufacturing_tools import (
        validate_dfm_dfa as tool,
    )

    env = tool()
    assert env["status"] == "INCOMPLETE"
    findings = env["data"]["findings"]
    # The schematic carries many TBD fields (battery.capacity_mah,
    # fet_part, etc.) that surface as findings.
    assert any("TBD" in f.get("value", "") for f in findings)


def test_validate_dfm_dfa_no_silent_pass(snapshot_yaml):
    """Even after multiple BLOCK findings, the tool must NOT silently
    upgrade the state to PASS."""
    from cad_engineering_mcp.tools.manufacturing_tools import (
        validate_dfm_dfa as tool,
    )

    # Corrupt the schematic to remove the TBD fields entirely so the
    # validator must fall back to its structural checks.
    glasses = glasses_root()
    target = glasses / SCHEMATIC_REL
    original = target.read_text(encoding="utf-8")
    import yaml
    data = yaml.safe_load(original)
    # Mark every TBD as defined (so we can check that the *policy*
    # rules still produce non-PASS findings).
    for k in (
        "connectors",
        "pcb_stackup",
        "tolerances",
        "board_outline",
        "manufacturing",
    ):
        if k in data:
            data[k] = "PROMOTED"
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    try:
        env = tool()
    finally:
        target.write_text(original, encoding="utf-8")

    # The tool refuses to silently upgrade to PASS because the
    # structural_policy / component_mounts / mounting_interfaces
    # are not the entire DFM/DFA source of truth.
    assert env["status"] in {"INCOMPLETE", "ERROR"}


# ---------------------------------------------------------------------------
# PCB reconciliation
# ---------------------------------------------------------------------------


def test_reconcile_pcb_returns_envelope():
    from cad_engineering_mcp.tools.manufacturing_tools import (
        reconcile_pcb as tool,
    )

    env = tool()
    assert env["status"] in {"PASS", "INCOMPLETE", "FAIL", "ERROR"}
    data = env["data"]
    assert "outline_reconciliation" in data
    assert "component_envelopes" in data
    assert "findings" in data
    assert isinstance(data["component_envelopes"], list)
    # Component envelopes always exist (they are derived from the
    # mechanical config, not from the PCB).
    assert len(data["component_envelopes"]) >= 1


def test_reconcile_pcb_outline_consistent():
    from cad_engineering_mcp.tools.manufacturing_tools import (
        reconcile_pcb as tool,
    )

    env = tool()
    outline = env["data"]["outline_reconciliation"]
    derived = outline["derived_outline_mm"]
    # Derived width / height must be > 0 and bounded by the frame
    # bbox; thickness is FR-4 (1.6 mm default).
    assert derived["thickness"] is not None
    if derived["width"] is not None and derived["height"] is not None:
        assert derived["width"] > 0
        assert derived["height"] > 0


def test_reconcile_pcb_reports_unknowns():
    """The current schematic carries several UNKNOWN/TBD fields that
    the reconciler must surface as findings."""
    from cad_engineering_mcp.tools.manufacturing_tools import (
        reconcile_pcb as tool,
    )

    env = tool()
    findings = env["data"]["findings"]
    # At least one BLOCK finding (footprint / keepout / stackup).
    assert any("BLOCK" == f.get("severity") for f in findings)


# ---------------------------------------------------------------------------
# Manufacturing-readiness
# ---------------------------------------------------------------------------


def test_manufacturing_release_report_envelope():
    from cad_engineering_mcp.tools.manufacturing_tools import (
        manufacturing_release_report as tool,
    )

    env = tool()
    assert env["status"] in {
        "RELEASE_READY",
        "INCOMPLETE",
        "RELEASE_BLOCKED",
        "ERROR",
    }
    data = env["data"]
    assert "summary" in data
    assert "reference_integrity" in data
    assert "dfm_dfa" in data
    assert "pcb_reconciliation" in data
    assert "required_fields_coverage" in data
    assert "unknown_required_fields" in data


def test_manufacturing_release_report_current_state_incomplete():
    """The current project state is INCOMPLETE: many required
    component fields are still TBD/UNKNOWN."""
    from cad_engineering_mcp.tools.manufacturing_tools import (
        manufacturing_release_report as tool,
    )

    env = tool()
    # Reference manifest is OK; DFM/DFA is INCOMPLETE; PCB is
    # INCOMPLETE; coverage shows many unknown fields.  The aggregated
    # status must be INCOMPLETE (not RELEASE_READY).
    assert env["status"] in {"INCOMPLETE", "RELEASE_BLOCKED"}
    assert env["data"]["summary"]["required_fields_total"] > 0
    assert env["data"]["summary"]["required_fields_unknown"] > 0


def test_manufacturing_release_report_reference_integrity():
    """Reference integrity is verified by the release report."""
    from cad_engineering_mcp.tools.manufacturing_tools import (
        manufacturing_release_report as tool,
    )

    env = tool()
    integrity = env["data"]["reference_integrity"]
    assert integrity["manifest_present"] is True
    assert integrity["ok"] is True
    entries = integrity["entries"]
    assert any(e["name"] == "wayfarer_frame" for e in entries)
    assert all(e.get("ok") for e in entries)


# ---------------------------------------------------------------------------
# save_manufacturing_release_report
# ---------------------------------------------------------------------------


def test_save_manufacturing_release_report_dry_run():
    from cad_engineering_mcp.tools.manufacturing_tools import (
        save_manufacturing_release_report as tool,
    )

    env = tool(
        destination="manufacturing/releases/manufacturing-readiness.json",
        allow_mutation=False,
    )
    assert env["status"] == "PASS"
    assert env["data"]["executed"] is False
    # The file must NOT have been written.
    glasses = glasses_root()
    target = glasses / "manufacturing" / "releases" / "manufacturing-readiness.json"
    assert not target.exists()


def test_save_manufacturing_release_report_mutation():
    from cad_engineering_mcp.tools.manufacturing_tools import (
        save_manufacturing_release_report as tool,
    )
    from cad_engineering_mcp.tools._paths import glasses_root

    env = tool(
        destination="manufacturing/releases/test-release.json",
        allow_mutation=True,
    )
    assert env["status"] == "PASS"
    assert env["data"]["executed"] is True
    assert env["data"]["after_sha256"] is not None
    # The file should exist now.
    target = glasses_root() / "manufacturing" / "releases" / "test-release.json"
    assert target.exists()
    # Cleanup.
    target.unlink()
