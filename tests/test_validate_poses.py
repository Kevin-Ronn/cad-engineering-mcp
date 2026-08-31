"""Tests for the Phase 2 ``validate_poses`` MCP tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_engineering_mcp.tools.validate_poses import validate_poses


def test_envelope_shape_present():
    env = validate_poses()
    for key in (
        "status",
        "tool",
        "started_at_iso",
        "duration_ms",
        "data",
        "warnings",
        "errors",
    ):
        assert key in env
    assert env["tool"] == "validate_poses"


def test_default_candidate_path_used():
    env = validate_poses()
    assert env["status"] in {"PASS", "FAIL", "INCOMPLETE", "ERROR"}, (
        env["errors"]
    )
    assert env["data"]["candidates_path"].endswith(
        "component-pose-candidates.json"
    )


def test_obstructed_optical_cone_returns_incomplete():
    env = validate_poses()
    # The on-disk candidate set has the camera cone obstructed; the
    # tool must downgrade to INCOMPLETE so callers cannot mistake it
    # for a production-ready PASS.
    assert env["status"] == "INCOMPLETE"
    assert env["data"]["engineering_readiness"] == "NOT_PRODUCTION_READY"
    labels = {
        a["component"]
        for a in env["data"]["aperture_required"]
    }
    assert "camthink_ov5640_8p5" in labels


def test_counts_summary_present():
    env = validate_poses()
    counts = env["data"]["counts"]
    for key in ("accepted", "rejected", "invalid"):
        assert key in counts
        assert isinstance(counts[key], int)


def test_rejection_reasons_list_present():
    env = validate_poses()
    assert "rejection_reasons" in env["data"]
    assert isinstance(env["data"]["rejection_reasons"], list)


def test_traversal_rejected():
    env = validate_poses(candidates_path="../../etc/passwd")
    assert env["status"] == "ERROR"


def test_malformed_candidate_json_returns_error(glasses, tmp_path):
    bad = glasses / "analysis" / "geometry" / "malformed.json"
    bad.write_text("{not json")
    try:
        env = validate_poses(candidates_path="analysis/geometry/malformed.json")
        assert env["status"] == "ERROR"
        assert "JSON parse error" in env["errors"][0]
    finally:
        bad.unlink()


def test_missing_required_keys_returns_error(glasses, tmp_path):
    bad = glasses / "analysis" / "geometry" / "incomplete.json"
    bad.write_text(json.dumps({"schema_version": 99}))
    try:
        env = validate_poses(candidates_path="analysis/geometry/incomplete.json")
        assert env["status"] == "ERROR"
        assert any(
            "missing top-level key" in e for e in env["errors"]
        )
    finally:
        bad.unlink()


def test_tolerance_override_below_policy_rejected():
    env = validate_poses(tolerance_overrides_mm={"camera_clearance_mm": 0.5})
    # The override is rejected, but the validator still runs with the
    # default clearance; the camera cone is obstructed so the summary
    # is INCOMPLETE regardless.
    assert env["status"] == "INCOMPLETE"
    assert env["data"]["applied_overrides"] == {}
    assert any(
        "below the mandatory policy floor" in e
        for e in env["data"]["override_errors"]
    )


def test_tolerance_override_negative_rejected():
    env = validate_poses(tolerance_overrides_mm={"led_clearance_mm": -1.0})
    assert env["status"] == "INCOMPLETE"
    assert any("negative" in e for e in env["data"]["override_errors"])


def test_tolerance_override_non_finite_rejected():
    env = validate_poses(
        tolerance_overrides_mm={"min_optical_axis_alignment": float("nan")}
    )
    assert env["status"] == "INCOMPLETE"
    assert any("finite" in e for e in env["data"]["override_errors"])


def test_tolerance_override_unknown_key_rejected():
    env = validate_poses(tolerance_overrides_mm={"not_a_real_key": 1.0})
    assert env["status"] == "INCOMPLETE"
    assert any(
        "unknown tolerance override key" in e
        for e in env["data"]["override_errors"]
    )


def test_tolerance_override_valid_recorded():
    env = validate_poses(tolerance_overrides_mm={"camera_clearance_mm": 1.5})
    assert env["data"]["applied_overrides"] == {"camera_clearance_mm": 1.5}
    assert env["data"]["override_errors"] == []


def test_no_mutation_of_existing_artifacts(repo_root):
    """``validate_poses`` must not write or rewrite the candidates file
    or the validation artifact."""
    cand = (
        repo_root
        / "projects/glasses/analysis/geometry/component-pose-candidates.json"
    )
    validation = (
        repo_root
        / "projects/glasses/analysis/geometry/component-pose-validation.json"
    )
    cand_before = cand.read_bytes()
    validation_before = (
        validation.read_bytes() if validation.exists() else None
    )
    validate_poses()
    validate_poses(tolerance_overrides_mm={"camera_clearance_mm": 1.5})
    validate_poses(tolerance_overrides_mm={"camera_clearance_mm": 0.1})
    cand_after = cand.read_bytes()
    assert cand_before == cand_after
    if validation_before is not None:
        assert validation_before == validation.read_bytes()


def test_complete_validation_report_included():
    env = validate_poses()
    assert "validation_report" in env["data"]
    report = env["data"]["validation_report"]
    for key in (
        "validation",
        "accepted",
        "rejected",
        "invalid",
        "summary",
    ):
        assert key in report