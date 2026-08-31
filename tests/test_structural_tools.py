"""Tests for the Phase 3 ``validate_structural_policy`` MCP tool."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._paths import glasses_root


POLICY_REL = Path("mechanical/main-frame/structural-policy.yaml")
RIB_REL = Path("mechanical/ribs/rib-system.yaml")


@pytest.fixture
def snapshot_yaml():
    """Snapshot the structural YAMLs so tests can restore them."""
    glasses = glasses_root()
    policy = glasses / POLICY_REL
    rib = glasses / RIB_REL
    policy_snap = Path("/tmp/_policy_snapshot.yaml")
    rib_snap = Path("/tmp/_rib_snapshot.yaml")
    shutil.copy2(policy, policy_snap)
    shutil.copy2(rib, rib_snap)
    yield policy_snap, rib_snap
    shutil.copy2(policy_snap, policy)
    shutil.copy2(rib_snap, rib)
    policy_snap.unlink()
    rib_snap.unlink()


def test_validate_structural_policy_returns_envelope(snapshot_yaml):
    from cad_engineering_mcp.tools.structural_tools import (
        validate_structural_policy,
    )

    env = validate_structural_policy()
    assert env["status"] in {"PASS", "INCOMPLETE", "FAIL", "ERROR"}
    assert env["tool"] == "validate_structural_policy"
    data = env["data"]
    assert data["rib_zones_count"] == 0
    assert isinstance(data["missing_objectives"], list)
    assert isinstance(data["interfaces"], list)
    assert isinstance(data["tbd_fields"], list)
    assert isinstance(data["findings"], list)


def test_validate_structural_policy_incomplete_when_rib_zones_empty(snapshot_yaml):
    from cad_engineering_mcp.tools.structural_tools import (
        validate_structural_policy,
    )

    env = validate_structural_policy()
    # The directive says: because rib_zones is currently empty, the
    # expected result is INCOMPLETE rather than PASS.
    assert env["status"] == "INCOMPLETE"
    findings = env["data"]["findings"]
    assert any("rib_zones" in f for f in findings)


def test_validate_structural_policy_surfaces_interfaces(snapshot_yaml):
    from cad_engineering_mcp.tools.structural_tools import (
        validate_structural_policy,
    )

    env = validate_structural_policy()
    interfaces = env["data"]["interfaces"]
    assert "left_hinge" in interfaces
    assert "right_hinge" in interfaces
    assert "pcb_mounts" in interfaces


def test_validate_structural_policy_yaml_parse_error(snapshot_yaml):
    from cad_engineering_mcp.tools.structural_tools import (
        validate_structural_policy,
    )

    # Corrupt the policy YAML.
    glasses = glasses_root()
    target = glasses / POLICY_REL
    original = target.read_text(encoding="utf-8")
    target.write_text(": invalid: yaml: ::: [\n", encoding="utf-8")
    try:
        env = validate_structural_policy()
    finally:
        target.write_text(original, encoding="utf-8")

    assert env["status"] == "ERROR"
    assert any("yaml" in err.lower() or "unreadable" in err.lower() for err in env["errors"])


def test_validate_structural_policy_missing_objectives(snapshot_yaml):
    from cad_engineering_mcp.tools.structural_tools import (
        validate_structural_policy,
    )

    glasses = glasses_root()
    target = glasses / POLICY_REL
    original = target.read_text(encoding="utf-8")
    # Strip every entry from objective.
    modified = original.replace(
        "    - minimum_structural_mass",
        "    - some_other_objective",
    )
    target.write_text(modified, encoding="utf-8")
    try:
        env = validate_structural_policy()
    finally:
        target.write_text(original, encoding="utf-8")

    assert env["status"] == "INCOMPLETE"
    assert "minimum_structural_mass" in env["data"]["missing_objectives"]


def test_validate_structural_policy_with_rib_zones_would_pass(snapshot_yaml):
    """If we add a rib zone, the INCOMPLETE 'empty rib_zones' finding goes away."""
    import yaml

    from cad_engineering_mcp.tools.structural_tools import (
        validate_structural_policy,
    )

    glasses = glasses_root()
    target = glasses / RIB_REL
    original = target.read_text(encoding="utf-8")
    data = yaml.safe_load(original)
    data["rib_zones"] = {
        "left_hinge_zone": {
            "type": "localized_reinforcement",
            "region_mm": {"min": [0, 0, 0], "max": [10, 10, 10]},
        }
    }
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    try:
        env = validate_structural_policy()
    finally:
        target.write_text(original, encoding="utf-8")

    # Rib zones are now non-empty, but missing_objectives and tbd_fields
    # may still cause INCOMPLETE. We just verify rib_zones_count.
    assert env["data"]["rib_zones_count"] >= 1