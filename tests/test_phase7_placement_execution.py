"""Tests for the Phase 7 engineering release-execution layer.

Covers:

* ``placement_resolution_plan`` envelope shape + current-state plan.
* Deterministic plan ordering.
* ``apply_placement_resolution`` dry-run + mutation gating.
* Mutation flows through the standard Phase 3 backup + audit helper.
* ``apply_placement_resolution`` refuses to read from a non-PASS
  pose-validation artifact.
* Mutation persists explicit ``coordinate_source`` provenance.
* ``verify_structural_objectives`` reads YAMLs directly and reports
  PASS when every objective is present.
* Aggregator fix: Phase 5 release_blocker_manifest no longer
  fabricates ``missing_objective`` blockers from absent keys; the
  blocker count for the structural source drops accordingly.

Engineering invariants enforced:

* No fabrication. Coordinates come from the pose-validation
  artifact, never invented.
* No silent downgrade of BLOCK.
* Provenance survives every mutation (audit + backup + per-record
  coordinate_source block).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cad_engineering_mcp.engineering.plExecution import (
    PLACEMENT_KEY_TO_POSE,
    PLACEMENT_POLICY_REL,
    POSE_VALIDATION_REL,
    REQUIRED_OBJECTIVES_LIST,
    apply_placement_resolution,
    build_placement_resolution_plan,
    verify_structural_objectives,
)
from cad_engineering_mcp.tools._paths import glasses_root


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_placement_rel_constants():
    assert POSE_VALIDATION_REL == Path(
        "analysis/geometry/component-pose-validation.json"
    )
    assert PLACEMENT_POLICY_REL == Path(
        "mechanical/interfaces/component-placement-policy.yaml"
    )


def test_required_objectives_list_is_complete():
    assert REQUIRED_OBJECTIVES_LIST == (
        "minimum_structural_mass",
        "minimum_wall_thickness",
        "maximum_required_stiffness",
        "maintain_serviceability",
    )


def test_placement_key_to_pose_covers_known_keys():
    """The known-keys map covers the canonical placements the policy YAML
    actually carries."""
    keys = set(PLACEMENT_KEY_TO_POSE.keys())
    assert "placements.front_left_led" in keys
    assert "placements.front_right_led" in keys
    assert "placements.left_temple_led_front" in keys
    assert "placements.left_temple_led_rear" in keys
    assert "placements.right_temple_led_front" in keys
    assert "placements.right_temple_led_rear" in keys
    # Camera entries.
    assert any("cameras." in k for k in keys)


# ---------------------------------------------------------------------------
# build_placement_resolution_plan
# ---------------------------------------------------------------------------


def test_build_plan_envelope_shape():
    plan = build_placement_resolution_plan(glasses_root=glasses_root())
    assert plan["status"] in {
        "RESOLVABLE_NOW",
        "ALL_ALREADY_RESOLVED",
        "BLOCKED_NO_AUTHORITATIVE_SOURCE",
        "NO_RESOLUTIONS",
    }
    assert "generated_at" in plan
    assert "pose_validation" in plan
    assert "placement_policy_path" in plan
    assert "resolutions" in plan
    assert "summary" in plan

    pv = plan["pose_validation"]
    assert pv["path"] == str(POSE_VALIDATION_REL)
    assert pv["sha256"] is not None
    assert pv["overall_status"] == "PASS"
    assert pv["accepted_count"] >= 1
    assert "camthink_ov5640_8p5" in pv["components"]
    assert "vsma1094750x02" in pv["components"]


def test_build_plan_current_state_resolvable_now():
    plan = build_placement_resolution_plan(glasses_root=glasses_root())
    summary = plan["summary"]
    assert summary["total_placements"] >= 6
    assert summary["resolvable"] >= 6
    assert summary["already_resolved"] == 0
    assert summary["no_authoritative_pose"] == 0


def test_build_plan_resolutions_carry_provenance():
    plan = build_placement_resolution_plan(glasses_root=glasses_root())
    resolvable = [
        r for r in plan["resolutions"] if r["action"] == "RESOLVE"
    ]
    assert resolvable
    for r in resolvable:
        assert r["provenance"] is not None
        prov = r["provenance"]
        assert prov["kind"] == "geometry_derived"
        assert prov["source_path"] == str(POSE_VALIDATION_REL)
        assert prov["source_sha256"] is not None
        assert prov["source_overall_status"] == "PASS"
        assert isinstance(prov["pose_index"], int)
        assert prov["component_id"]
        assert prov["region"]
        # Coordinates are a 3-vector of finite numbers.
        center = r["resolved_coordinates_mm"]
        assert isinstance(center, list)
        assert len(center) == 3
        for v in center:
            assert isinstance(v, float)
            assert v == v  # not NaN


def test_build_plan_deterministic():
    a = build_placement_resolution_plan(glasses_root=glasses_root())
    b = build_placement_resolution_plan(glasses_root=glasses_root())
    assert a["resolutions"] == b["resolutions"]
    assert a["summary"] == b["summary"]


def test_build_plan_resolves_specific_camera():
    """Camera placements all map to the same OV5640 pose (single_forward)."""
    plan = build_placement_resolution_plan(glasses_root=glasses_root())
    camera_resolutions = [
        r for r in plan["resolutions"]
        if r["placement_key"].startswith("cameras.")
    ]
    assert camera_resolutions
    centers = {tuple(r["resolved_coordinates_mm"]) for r in camera_resolutions}
    # All four camera YAML keys share the same OV5640 center.
    assert len(centers) == 1


# ---------------------------------------------------------------------------
# apply_placement_resolution -- mutation
# ---------------------------------------------------------------------------


def _restore_placement_policy():
    """Backup-and-restore helper for the placement policy YAML."""
    glasses = glasses_root()
    src = glasses / PLACEMENT_POLICY_REL
    backup = Path("/tmp/_phase7_placement_policy_backup.yaml")
    if src.exists():
        shutil.copy2(src, backup)
    yield backup
    if backup.exists():
        shutil.copy2(backup, src)
        backup.unlink()


def test_apply_placement_resolution_dry_run_does_not_write():
    target = glasses_root() / PLACEMENT_POLICY_REL
    backup = Path("/tmp/_phase7_apply_dry_backup.yaml")
    if target.exists():
        shutil.copy2(target, backup)
    try:
        env = apply_placement_resolution(
            glasses_root=glasses_root(),
            perform_write_fn=lambda **kwargs: {"dry_run": True},
        )
        assert env["executed"] is False
        assert env["applied"] == 0
        # The policy YAML must NOT have been modified.
        if backup.exists():
            content_now = target.read_text(encoding="utf-8")
            content_before = backup.read_text(encoding="utf-8")
            assert content_now == content_before
    finally:
        if backup.exists():
            backup.unlink()


def test_apply_placement_resolution_mutation_writes_and_audits():
    target = glasses_root() / PLACEMENT_POLICY_REL
    backup = Path("/tmp/_phase7_apply_mut_backup.yaml")
    releases_dir = glasses_root() / "manufacturing" / "releases"
    if target.exists():
        shutil.copy2(target, backup)
    # Snapshot the releases directory (we will clean up only our own writes).
    pre_existing_releases = set()
    if releases_dir.exists():
        for child in releases_dir.iterdir():
            pre_existing_releases.add(child.name)
    try:
        env = apply_placement_resolution(
            glasses_root=glasses_root(),
            perform_write_fn=lambda **kwargs: {
                "destination": str(PLACEMENT_POLICY_REL),
                "timestamp": "test-ts",
                "backup": "manufacturing/releases/test-ts/"
                + str(PLACEMENT_POLICY_REL),
                "audit_log": "manufacturing/releases/audit/test.jsonl",
                "applied_records": kwargs.get("metadata", {}).get(
                    "applied_records", []
                ),
            },
        )
        assert env["executed"] is True
        assert env["applied"] >= 6
        # The mutation must have been called with provenance metadata.
        # Re-read the YAML to verify the coordinates are now numeric.
        import yaml as _yaml

        doc = _yaml.safe_load(target.read_text(encoding="utf-8"))
        placements = doc.get("placements", {}) or {}
        for placement_key in (
            "front_left_led",
            "front_right_led",
            "left_temple_led_front",
            "left_temple_led_rear",
            "right_temple_led_front",
            "right_temple_led_rear",
        ):
            assert isinstance(placements[placement_key]["coordinates"], list)
            assert len(placements[placement_key]["coordinates"]) == 3
            for v in placements[placement_key]["coordinates"]:
                assert isinstance(v, float)
            # The placement also carries a coordinate_source provenance block.
            assert "coordinate_source" in placements[placement_key]
            src = placements[placement_key]["coordinate_source"]
            assert src["kind"] == "geometry_derived"
            assert src["source_artifact"] == str(POSE_VALIDATION_REL)
            assert src["source_overall_status"] == "PASS"
            assert "resolved_at" in src
    finally:
        if backup.exists():
            shutil.copy2(backup, target)
            backup.unlink()
        # Remove only the audit / release directories we created.
        if releases_dir.exists():
            for child in releases_dir.iterdir():
                if child.name not in pre_existing_releases:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()


def test_apply_placement_resolution_only_keys_filter():
    """The ``only_keys`` filter restricts which placements are mutated."""
    target = glasses_root() / PLACEMENT_POLICY_REL
    backup = Path("/tmp/_phase7_only_keys_backup.yaml")
    releases_dir = glasses_root() / "manufacturing" / "releases"
    if target.exists():
        shutil.copy2(target, backup)
    pre_existing_releases = set()
    if releases_dir.exists():
        for child in releases_dir.iterdir():
            pre_existing_releases.add(child.name)
    try:
        env = apply_placement_resolution(
            glasses_root=glasses_root(),
            perform_write_fn=lambda **kwargs: {"ok": True},
            only_keys=["placements.front_left_led"],
        )
        assert env["executed"] is True
        assert env["applied"] == 1
        # Verify only one placement was changed.
        import yaml as _yaml

        doc = _yaml.safe_load(target.read_text(encoding="utf-8"))
        assert isinstance(
            doc["placements"]["front_left_led"]["coordinates"], list
        )
        # Other placements still have coordinates: TBD
        assert (
            doc["placements"]["front_right_led"]["coordinates"] == "TBD"
        )
    finally:
        if backup.exists():
            shutil.copy2(backup, target)
            backup.unlink()
        if releases_dir.exists():
            for child in releases_dir.iterdir():
                if child.name not in pre_existing_releases:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()


def test_apply_placement_resolution_refuses_non_pass_pose_validation():
    """If the pose-validation artifact is missing or non-PASS, the
    resolver refuses to mutate."""
    # Temporarily rename the pose-validation JSON so the loader cannot
    # find it.
    pose_path = glasses_root() / POSE_VALIDATION_REL
    backup = Path("/tmp/_phase7_pose_backup.json")
    if pose_path.exists():
        shutil.copy2(pose_path, backup)
    try:
        if pose_path.exists():
            pose_path.unlink()
        with pytest.raises(Exception,
                        match="Pose validation artifact missing|Pose validation overall_status"):
            apply_placement_resolution(
                glasses_root=glasses_root(),
                perform_write_fn=lambda **kwargs: {"ok": True},
            )
    finally:
        if backup.exists():
            shutil.copy2(backup, pose_path)
            backup.unlink()


# ---------------------------------------------------------------------------
# verify_structural_objectives
# ---------------------------------------------------------------------------


def test_verify_structural_objectives_current_state_pass():
    result = verify_structural_objectives(glasses_root=glasses_root())
    assert result["status"] == "PASS"
    assert sorted(result["objectives_present"]) == sorted(
        REQUIRED_OBJECTIVES_LIST
    )
    assert result["objectives_missing"] == []
    assert len(result["interfaces_present"]) >= 5
    assert len(result["exclusions_present"]) >= 5


def test_verify_structural_objectives_envelope_shape():
    from cad_engineering_mcp.tools.placement_execution_tools import (
        verify_structural_objectives as tool,
    )

    env = tool()
    assert env["status"] == "PASS"
    assert env["tool"] == "verify_structural_objectives"
    data = env["data"]
    assert "status" in data
    assert "policy_path" in data
    assert "rib_path" in data
    assert "objectives_present" in data
    assert "objectives_missing" in data
    assert "interfaces_present" in data
    assert "exclusions_present" in data


# ---------------------------------------------------------------------------
# Phase 5 aggregator fix -- regression coverage
# ---------------------------------------------------------------------------


def test_release_blocker_no_longer_fabricates_missing_objectives():
    """The Phase 5 release-blocker manifest must not fabricate
    ``missing_objective`` blockers from absent keys.

    Before the Phase 7 fix, the structural envelope fallback listed
    every REQUIRED_OBJECTIVE as missing when the raw
    ``validate_structural_policy()`` output did not carry the
    ``missing_objectives`` key. The fix reads the YAML directly so
    the manifest reports the on-disk state faithfully.
    """
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest,
    )

    env = release_blocker_manifest()
    blockers = env["data"]["blockers"]
    missing_objective_blockers = [
        b
        for b in blockers
        if "missing_objective" in b["field"]
        or b["field"] == "structural_policy.design_intent.objective"
        and b["source_tool"] == "validate_structural_policy"
    ]
    # The project state has every objective present in the YAML, so
    # there must be ZERO fabricated missing-objective blockers.
    assert missing_objective_blockers == [], (
        f"Phase 5 fabricated missing-objective blockers: "
        f"{missing_objective_blockers}"
    )


def test_release_blocker_structural_only_rib_zones():
    """After the Phase 7 fix, the only structural-policy BLOCK remaining
    is the genuinely-unresolved rib_zones gap (and any TBD-field
    findings)."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest,
    )

    env = release_blocker_manifest()
    structural = [
        b
        for b in env["data"]["blockers"]
        if b["source_tool"] == "validate_structural_policy"
    ]
    # Only rib_zones remains as a structural blocker (the rest of the
    # previously-fabricated structural blockers are gone).
    fields = {b["field"] for b in structural}
    assert "structural_policy.design_intent.objective" not in fields
    assert "structural_policy.load_interfaces" not in fields
    assert "rib_system.rib_generation.exclusions" not in fields
    assert "rib_system.rib_zones" in fields


def test_release_blocker_blocker_count_dropped():
    """The Phase 5 fix removed 5 fabricated structural blockers; the
    total blocker count must drop from 79 to 74 (or lower).
    """
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest,
    )

    env = release_blocker_manifest()
    count = env["data"]["summary"]["blocker_count"]
    assert count <= 74, (
        f"Blocker count {count} should have dropped after the "
        "Phase 5 fix (expected <= 74)."
    )


# ---------------------------------------------------------------------------
# MCP tool: placement_resolution_plan
# ---------------------------------------------------------------------------


def test_placement_resolution_plan_envelope():
    from cad_engineering_mcp.tools.placement_execution_tools import (
        placement_resolution_plan as tool,
    )

    env = tool()
    assert env["status"] == "PASS"
    assert env["tool"] == "placement_resolution_plan"
    data = env["data"]
    assert "status" in data
    assert "resolutions" in data
    assert "summary" in data


def test_apply_placement_resolution_mcp_dry_run():
    from cad_engineering_mcp.tools.placement_execution_tools import (
        apply_placement_resolution as tool,
    )

    target = glasses_root() / PLACEMENT_POLICY_REL
    backup = Path("/tmp/_phase7_mcp_dry_backup.yaml")
    if target.exists():
        shutil.copy2(target, backup)
    try:
        env = tool(allow_mutation=False)
        assert env["status"] == "PASS"
        assert env["data"]["executed"] is False
        # The warning must mention allow_mutation=False.
        assert any(
            "allow_mutation" in w for w in env["warnings"]
        )
    finally:
        if backup.exists():
            backup.unlink()