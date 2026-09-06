"""Regression tests for the Phase 7 canonical engineering status + multi-instance
pose identity fixes (P0-2 + P0-3).

These tests verify that:

  * A pose-validation artifact whose raw ``overall_status`` is
    ``PASS`` but whose engineering-aware status is ``INCOMPLETE``
    (because of optical-cone obstruction or missing-mesh-collision
    backend) is rejected by Phase 7. This is the canonical-engineering
    status fix (P0-2).
  * A genuinely valid PASS artifact is accepted by Phase 7 and the
    placements resolve.
  * Multiple physical instances of the same component and region
    remain distinct in the pose index (P0-3). Two forward LEDs
    labelled ``forward_led_bottom`` / ``forward_led_top`` must NOT
    collapse to the same coordinates.
  * Ambiguous or missing pose identity fails safely rather than
    selecting the first occurrence.

These tests do NOT modify the existing on-disk artifact or any
CAD / FCStd / STL geometry. They build synthetic artifacts in a
temporary directory.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_engineering_mcp.engineering.plExecution import (
    PLACEMENT_KEY_TO_POSE,
    POSE_VALIDATION_REL,
    PLACEMENT_POLICY_REL,
    build_placement_resolution_plan,
    _index_pose_validation,
    _resolve_pose_validation_status,
)


def _write_artifact(
    base: Path,
    *,
    accepted: list[dict],
    overall_status: str = "PASS",
    extra_top_level: dict | None = None,
) -> Path:
    """Write a synthetic pose-validation artifact under ``base``."""
    artifact_path = base / POSE_VALIDATION_REL
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict = {
        "schema_version": 3,
        "validation": {
            "overall_status": overall_status,
            "validation_method": "test",
        },
        "accepted": accepted,
        "rejected": [],
        "invalid": [],
        "summary": {},
    }
    if extra_top_level:
        doc.update(extra_top_level)
    artifact_path.write_text(
        json.dumps(doc, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return artifact_path


def _write_policy(base: Path) -> Path:
    """Write a minimal placement policy YAML covering every key in
    ``PLACEMENT_KEY_TO_POSE``."""
    policy_path = base / PLACEMENT_POLICY_REL
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_text = (
        "schema_version: 1\n\n"
        "placements:\n\n"
        "  front_left_led:\n    region: front_frame\n    coordinates: TBD\n\n"
        "  front_right_led:\n    region: front_frame\n    coordinates: TBD\n\n"
        "  left_temple_led_front:\n    region: left_temple\n    coordinates: TBD\n\n"
        "  left_temple_led_rear:\n    region: left_temple\n    coordinates: TBD\n\n"
        "  right_temple_led_front:\n    region: right_temple\n    coordinates: TBD\n\n"
        "  right_temple_led_rear:\n    region: right_temple\n    coordinates: TBD\n\n"
        "cameras:\n\n"
        "  left_camera_front:\n    region: center_nose_bridge\n    coordinates: TBD\n\n"
        "  left_camera_rear:\n    region: center_nose_bridge\n    coordinates: TBD\n\n"
        "  right_camera_front:\n    region: center_nose_bridge\n    coordinates: TBD\n\n"
        "  right_camera_rear:\n    region: center_nose_bridge\n    coordinates: TBD\n"
    )
    policy_path.write_text(policy_text, encoding="utf-8")
    return policy_path


@pytest.fixture
def synthetic_glasses_root(tmp_path, monkeypatch):
    """Create a synthetic ``glasses/`` root containing only the
    artifact and the policy YAML. Point the resolver at it."""
    root = tmp_path
    from cad_engineering_mcp.tools import _paths

    monkeypatch.setenv("CAD_ENGINEERING_ROOT", str(root))
    _paths.reset_project_root_cache()
    _write_policy(root)
    return root


def _accepted_two_front_leds() -> list[dict]:
    return [
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_bottom",
            "center_mm": [1.0, 2.0, 3.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_top",
            "center_mm": [1.0, 2.0, 4.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "left_temple",
            "label": "left_temple_led_front",
            "center_mm": [10.0, 20.0, 30.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "left_temple",
            "label": "left_temple_led_rear",
            "center_mm": [11.0, 21.0, 31.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "right_temple",
            "label": "right_temple_led_front",
            "center_mm": [12.0, 22.0, 32.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "right_temple",
            "label": "right_temple_led_rear",
            "center_mm": [13.0, 23.0, 33.0],
        },
        {
            "component": "camthink_ov5640_8p5",
            "region": "center_nose_bridge",
            "label": None,
            "center_mm": [50.0, 60.0, 70.0],
        },
    ]


# ---------------------------------------------------------------------------
# P0-2: MCP registration path uses the engineering-aware wrapper
# ---------------------------------------------------------------------------


def test_mcp_validate_poses_uses_engineering_aware_wrapper():
    """P0-2 fix: the registered MCP ``validate_poses`` tool MUST call
    ``validate_poses_tool`` (which persists engineering_status to
    the artifact), not the raw ``validate_poses`` function. The raw
    validator alone would leave the artifact with only
    ``validation.overall_status`` and Phase 7 would fall back to
    trusting that raw PASS -- the original audit finding.
    """
    import inspect

    from cad_engineering_mcp import server
    import sys as _sys
    vp_mod = _sys.modules["cad_engineering_mcp.tools.validate_poses"]

    # The MCP wrapper's source must reference the engineering-aware
    # wrapper, NOT the raw validator function.
    src = inspect.getsource(server.validate_poses)
    assert "validate_poses_tool" in src, (
        "MCP validate_poses must call validate_poses_tool "
        "(engineering-aware), not the raw validate_poses."
    )
    assert "from .tools.validate_poses import validate_poses as _impl" not in src

    # The engineering-aware wrapper must call _persist_engineering_status.
    wrapper_src = inspect.getsource(vp_mod.validate_poses_tool)
    assert "_persist_engineering_status" in wrapper_src

    # The wrapper MUST default to persisting (persist_to_artifact=True).
    sig = inspect.signature(vp_mod.validate_poses_tool)
    assert sig.parameters["persist_to_artifact"].default is True


def test_mcp_validate_poses_persistence_gate():
    """P0-2 end-to-end: the engineering-aware wrapper only persists
    the canonical engineering status fields when the validator
    returns a verdict (status != 'ERROR'). If the validator itself
    fails (e.g. missing dependency), the wrapper does NOT inject a
    verdict -- this is the correct fail-closed behavior. We verify
    the gate by inspecting the wrapper source code directly to
    avoid running the actual validator (which depends on the
    on-disk validator module)."""
    import inspect

    from cad_engineering_mcp.tools import validate_poses as vp_mod
    import sys as _sys
    vp_mod = _sys.modules["cad_engineering_mcp.tools.validate_poses"]

    src = inspect.getsource(vp_mod.validate_poses_tool)
    # The gate is the ``status not in {"ERROR"}`` check.
    assert 'envelope.get("status") not in {"ERROR"}' in src, (
        "validate_poses_tool must skip persistence when the "
        "validator returns ERROR. This is the fail-closed behaviour."
    )
    # The persisted fields are explicitly the canonical ones.
    assert "_persist_engineering_status" in src
    assert "engineering_status" in src
    assert "release_status" in src
    assert "validator_status" in src


# ---------------------------------------------------------------------------
# P0-2: canonical engineering status
# ---------------------------------------------------------------------------


def test_phase7_rejects_raw_pass_when_engineering_status_incomplete(
    synthetic_glasses_root,
):
    """P0-2 fix: a raw PASS with engineering_status=INCOMPLETE must
    be rejected. This is the canonical engineering-status bypass
    that was the original P0-2 audit finding."""
    _write_artifact(
        synthetic_glasses_root,
        accepted=_accepted_two_front_leds(),
        overall_status="PASS",
        extra_top_level={
            "validator_status": "PASS",
            "engineering_status": "INCOMPLETE",
            "release_status": "NOT_PRODUCTION_READY",
        },
    )
    from cad_engineering_mcp.engineering import plExecution

    with pytest.raises(
        plExecution.PlExecutionError,
        match="engineering_status",
    ):
        build_placement_resolution_plan(
            glasses_root=synthetic_glasses_root
        )


def test_phase7_accepts_engineering_pass(synthetic_glasses_root):
    """A genuinely valid artifact with engineering_status=PASS is
    accepted and resolves all six LED placements plus the four
    camera placements (which all share the camera pose)."""
    _write_artifact(
        synthetic_glasses_root,
        accepted=_accepted_two_front_leds(),
        overall_status="PASS",
        extra_top_level={
            "validator_status": "PASS",
            "engineering_status": "PASS",
            "release_status": "PRODUCTION_READY",
        },
    )
    plan = build_placement_resolution_plan(
        glasses_root=synthetic_glasses_root
    )
    assert plan["status"] == "RESOLVABLE_NOW"
    summary = plan["summary"]
    assert summary["total_placements"] == 10
    assert summary["resolvable"] == 10
    assert summary["no_authoritative_pose"] == 0
    assert plan["pose_validation"]["overall_status"] == "PASS"


def test_phase7_legacy_raw_pass_is_REJECTED(synthetic_glasses_root):
    """P0-2 audit: a legacy artifact containing only raw
    ``validation.overall_status = PASS`` and NO
    ``engineering_status`` field must NOT be accepted by Phase 7.
    Legacy raw PASS is the exact unsafe bypass the audit flagged.
    Phase 7 must fail closed and require re-running the
    engineering-aware ``validate_poses`` tool."""
    _write_artifact(
        synthetic_glasses_root,
        accepted=_accepted_two_front_leds(),
        overall_status="PASS",
        # NB: no ``engineering_status`` field. This is a legacy
        # artifact.
    )
    from cad_engineering_mcp.engineering import plExecution

    with pytest.raises(
        plExecution.PlExecutionError,
        match="legacy",
    ):
        build_placement_resolution_plan(
            glasses_root=synthetic_glasses_root
        )


def test_resolve_status_precedence_chain():
    """The status resolver must follow the documented precedence:

      * ``engineering_status`` -> canonical engineering verdict.
      * missing ``engineering_status`` -> ``LEGACY_NO_ENGINEERING_STATUS``
        (Phase 7 fails closed; legacy raw PASS is explicitly NOT a
        fallback).
      * No fallback to ``validator_status`` or
        ``validation.overall_status`` for Phase 7.

    The raw validator + engineering_status + release_status are
    distinct concepts; release_status is NOT consulted by Phase 7.
    """
    # engineering_status wins when present.
    s, k = _resolve_pose_validation_status(
        {
            "validation": {"overall_status": "PASS"},
            "validator_status": "PASS",
            "engineering_status": "PASS",
            "release_status": "NOT_PRODUCTION_READY",
        }
    )
    assert (s, k) == ("PASS", "engineering_status")
    # engineering_status INCOMPLETE -> rejected even if raw PASS.
    s, k = _resolve_pose_validation_status(
        {
            "validation": {"overall_status": "PASS"},
            "validator_status": "PASS",
            "engineering_status": "INCOMPLETE",
        }
    )
    assert (s, k) == ("INCOMPLETE", "engineering_status")
    # Legacy artifact: NO engineering_status -> fail closed; do NOT
    # fall back to validator_status or validation.overall_status.
    s, k = _resolve_pose_validation_status(
        {
            "validation": {"overall_status": "PASS"},
            "validator_status": "PASS",
        }
    )
    assert (s, k) == ("LEGACY_NO_ENGINEERING_STATUS", "legacy")
    s, k = _resolve_pose_validation_status(
        {"validation": {"overall_status": "PASS"}}
    )
    assert (s, k) == ("LEGACY_NO_ENGINEERING_STATUS", "legacy")
    s, k = _resolve_pose_validation_status({})
    assert (s, k) == ("LEGACY_NO_ENGINEERING_STATUS", "legacy")
    # release_status must not influence the canonical verdict.
    s, k = _resolve_pose_validation_status(
        {
            "validation": {"overall_status": "PASS"},
            "release_status": "NOT_PRODUCTION_READY",
        }
    )
    assert (s, k) == ("LEGACY_NO_ENGINEERING_STATUS", "legacy")


# ---------------------------------------------------------------------------
# P0-3: multi-instance pose identity
# ---------------------------------------------------------------------------


def test_pose_index_distinguishes_two_front_leds():
    """P0-3: ``_index_pose_validation`` must produce two distinct keys
    for ``forward_led_bottom`` and ``forward_led_top`` -- they MUST
    NOT collapse onto ``component::region``."""
    accepted = _accepted_two_front_leds()
    doc = {"accepted": accepted}
    index = _index_pose_validation(doc)
    assert "vsma1094750x02::front_frame::forward_led_bottom" in index
    assert "vsma1094750x02::front_frame::forward_led_top" in index
    a = index["vsma1094750x02::front_frame::forward_led_bottom"]
    b = index["vsma1094750x02::front_frame::forward_led_top"]
    assert a["center_mm"] == [1.0, 2.0, 3.0]
    assert b["center_mm"] == [1.0, 2.0, 4.0]
    assert a is not b


def test_pose_index_null_label_uses_no_label_sentinel():
    """The camera has ``label: null``. The index must use the
    ``_no_label`` sentinel so the camera has a stable identity
    without collapsing multiple cameras into the same key."""
    accepted = [
        {
            "component": "camthink_ov5640_8p5",
            "region": "center_nose_bridge",
            "label": None,
            "center_mm": [50.0, 60.0, 70.0],
        },
    ]
    index = _index_pose_validation({"accepted": accepted})
    assert "camthink_ov5640_8p5::center_nose_bridge::_no_label" in index


def test_pose_index_detects_duplicate_triples_and_marks_ambiguous():
    """If the artifact contains two accepted entries with the same
    ``(component, region, label)`` triple, the index must mark
    the key as AMBIGUOUS (removed from the index) and surface the
    duplicate in the ``_duplicates`` sidecar. Fail-closed: the
    conflicting identity must NOT be resolvable via ``_pose_at``."""
    accepted = [
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_bottom",
            "center_mm": [1.0, 2.0, 3.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_bottom",  # DUPLICATE
            "center_mm": [9.0, 9.0, 9.0],
        },
    ]
    index = _index_pose_validation({"accepted": accepted})
    # The conflicting key is REMOVED from the index. Neither
    # occurrence can be resolved.
    assert (
        "vsma1094750x02::front_frame::forward_led_bottom" not in index
    )
    # The duplicate is reported for diagnostics.
    assert "_duplicates" in index
    items = index["_duplicates"]["items"]
    assert any(
        d["component"] == "vsma1094750x02"
        and d["region"] == "front_frame"
        and d["label"] == "forward_led_bottom"
        for d in items
    )


def test_duplicate_identity_cannot_resolve_placement(synthetic_glasses_root):
    """End-to-end P0-3 fail-closed: a duplicate identity in the
    artifact means the corresponding YAML placement key resolves to
    ``SKIP_NO_AUTHORITATIVE_POSE`` -- never to fabricated
    coordinates."""
    accepted = [
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_bottom",
            "center_mm": [1.0, 2.0, 3.0],
        },
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_bottom",  # DUPLICATE
            "center_mm": [9.0, 9.0, 9.0],
        },
    ]
    _write_artifact(
        synthetic_glasses_root,
        accepted=accepted,
        overall_status="PASS",
        extra_top_level={
            "validator_status": "PASS",
            "engineering_status": "PASS",
            "release_status": "PRODUCTION_READY",
        },
    )
    plan = build_placement_resolution_plan(
        glasses_root=synthetic_glasses_root
    )
    by_key = {
        r["placement_key"]: r for r in plan["resolutions"]
    }
    # The duplicate-affected placements must NOT resolve. Neither
    # occurrence may win; no fabrication.
    for k in (
        "placements.front_left_led",
        "placements.front_right_led",
    ):
        assert by_key[k]["action"] == "SKIP_NO_AUTHORITATIVE_POSE"
        assert by_key[k]["resolved_coordinates_mm"] is None


def test_phase7_resolves_two_front_leds_to_distinct_coordinates(
    synthetic_glasses_root,
):
    """End-to-end P0-3 test: build a synthetic artifact with two
    front LEDs sharing ``(component, region)`` but differing by
    ``label``, then verify the plan returns two distinct
    ``resolved_coordinates_mm`` values (one per LED)."""
    _write_artifact(
        synthetic_glasses_root,
        accepted=_accepted_two_front_leds(),
        overall_status="PASS",
        extra_top_level={
            "validator_status": "PASS",
            "engineering_status": "PASS",
            "release_status": "PRODUCTION_READY",
        },
    )
    plan = build_placement_resolution_plan(
        glasses_root=synthetic_glasses_root
    )
    by_key = {
        r["placement_key"]: r for r in plan["resolutions"]
    }
    fl = by_key["placements.front_left_led"]["resolved_coordinates_mm"]
    fr = by_key["placements.front_right_led"]["resolved_coordinates_mm"]
    assert fl == [1.0, 2.0, 3.0]
    assert fr == [1.0, 2.0, 4.0]
    assert fl != fr


def test_phase7_resolves_null_label_camera_uniquely(
    synthetic_glasses_root,
):
    """The four ``cameras.*`` YAML keys all map to the same single
    camera pose (label=null in the artifact). The resolver must
    return the same coordinates for all four without duplication."""
    _write_artifact(
        synthetic_glasses_root,
        accepted=_accepted_two_front_leds(),
        overall_status="PASS",
        extra_top_level={
            "validator_status": "PASS",
            "engineering_status": "PASS",
            "release_status": "PRODUCTION_READY",
        },
    )
    plan = build_placement_resolution_plan(
        glasses_root=synthetic_glasses_root
    )
    by_key = {
        r["placement_key"]: r for r in plan["resolutions"]
    }
    cam_centers = {
        key: tuple(by_key[key]["resolved_coordinates_mm"])
        for key in by_key
        if key.startswith("cameras.")
    }
    assert set(cam_centers) == {
        "cameras.left_camera_front",
        "cameras.left_camera_rear",
        "cameras.right_camera_front",
        "cameras.right_camera_rear",
    }
    assert len(set(cam_centers.values())) == 1
    assert tuple([50.0, 60.0, 70.0]) in cam_centers.values()


def test_phase7_placement_keys_use_unique_triple_identity():
    """Every entry in ``PLACEMENT_KEY_TO_POSE`` must be a triple of
    (component, region, identity) where identity is either a label
    string or the ``_no_label`` sentinel. Two keys that map to the
    same component+region must have distinct identities."""
    keys = list(PLACEMENT_KEY_TO_POSE.keys())
    triples = [PLACEMENT_KEY_TO_POSE[k] for k in keys]
    for triple in triples:
        assert len(triple) == 3
        component, region, identity = triple
        assert component
        assert region
        assert identity  # non-empty
    fl_triple = PLACEMENT_KEY_TO_POSE["placements.front_left_led"]
    fr_triple = PLACEMENT_KEY_TO_POSE["placements.front_right_led"]
    assert fl_triple != fr_triple
    assert fl_triple[0] == fr_triple[0]
    assert fl_triple[1] == fr_triple[1]
    assert fl_triple[2] != fr_triple[2]


def test_phase7_missing_label_entry_fails_safely():
    """If a YAML placement key maps to a triple whose identity does
    NOT exist in the index (e.g. an authoring error), the resolver
    must surface ``SKIP_NO_AUTHORITATIVE_POSE`` rather than silently
    picking the first occurrence."""
    accepted = [
        {
            "component": "vsma1094750x02",
            "region": "front_frame",
            "label": "forward_led_bottom",
            "center_mm": [1.0, 2.0, 3.0],
        },
        # forward_led_top is INTENTIONALLY missing.
    ]
    doc = {"accepted": accepted}
    index = _index_pose_validation(doc)
    # The mapping asks for forward_led_top, which is absent.
    from cad_engineering_mcp.engineering.plExecution import _pose_at

    # The first front LED (bottom) is present and indexed under the
    # triple key.
    triple = PLACEMENT_KEY_TO_POSE["placements.front_right_led"]
    key = f"{triple[0]}::{triple[1]}::{triple[2]}"
    assert key not in index
    # ``_pose_at`` must return None for an absent identity (fail-closed).
    pose = _pose_at(index, "placements.front_right_led")
    assert pose is None
