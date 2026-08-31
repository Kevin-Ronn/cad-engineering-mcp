"""Tests for the Phase 2 ``propose_pose`` MCP tool."""
from __future__ import annotations

import math

import pytest

from cad_engineering_mcp.tools.propose_pose import propose_pose


def test_envelope_shape_present():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", 1.0
    )
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
    assert env["tool"] == "propose_pose"


def test_valid_camera_request():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", 1.0
    )
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    assert data["candidate_count"] >= 1
    cam = data["candidates"][0]
    assert cam["component"] == "camthink_ov5640_8p5"
    assert cam["region"] == "center_nose_bridge"
    assert cam["envelope_mm"] == [8.5, 8.5, 6.5]
    assert cam["value_status"]["center_mm"] == "DERIVED"
    assert "derivation" in cam


def test_valid_forward_led_request():
    env = propose_pose(
        "vsma1094750x02", "front_frame", "same_as_camera", 0.5
    )
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    assert data["candidate_count"] == 2
    labels = {c["label"] for c in data["candidates"]}
    assert "forward_led_top" in labels
    assert "forward_led_bottom" in labels


def test_valid_temple_led_request():
    env = propose_pose(
        "vsma1094750x02", "left_temple", "outward", 0.5
    )
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    assert data["candidate_count"] == 2
    for c in data["candidates"]:
        assert c["component"] == "vsma1094750x02"
        assert c["region"] == "left_temple"
        assert c["axis"] == "outward"


def test_invalid_component_id():
    env = propose_pose("nope", "center_nose_bridge", "forward", 1.0)
    assert env["status"] == "ERROR"
    assert "nope" in env["errors"][0]


def test_invalid_region():
    env = propose_pose(
        "camthink_ov5640_8p5", "everywhere", "forward", 1.0
    )
    assert env["status"] == "ERROR"
    assert "region" in env["errors"][0]


def test_invalid_host_axis():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "upward", 1.0
    )
    assert env["status"] == "ERROR"
    assert "host_axis" in env["errors"][0]


def test_negative_clearance():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", -0.5
    )
    assert env["status"] == "ERROR"
    assert "clearance_mm" in env["errors"][0]


def test_non_finite_clearance():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", float("nan")
    )
    assert env["status"] == "ERROR"

    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", float("inf")
    )
    assert env["status"] == "ERROR"


def test_non_numeric_clearance():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", "one"
    )
    assert env["status"] == "ERROR"


def test_no_mutation_of_project_files(repo_root):
    """``propose_pose`` must not write any files."""
    candidates_path = (
        repo_root
        / "projects/glasses/analysis/geometry/component-pose-candidates.json"
    )
    before = candidates_path.read_bytes()
    # Run a series of requests including invalid ones.
    propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", 1.0
    )
    propose_pose(
        "vsma1094750x02", "front_frame", "same_as_camera", 0.5
    )
    propose_pose(
        "vsma1094750x02", "left_temple", "outward", 0.5
    )
    propose_pose("invalid", "center_nose_bridge", "forward", 1.0)
    after = candidates_path.read_bytes()
    assert before == after


def test_structured_output_data_keys():
    env = propose_pose(
        "camthink_ov5640_8p5", "center_nose_bridge", "forward", 1.0
    )
    data = env["data"]
    for key in (
        "component_id",
        "region",
        "host_axis",
        "clearance_mm",
        "candidates",
        "candidate_count",
        "units",
        "notes",
    ):
        assert key in data
    assert data["units"] == "mm"
    assert math.isfinite(data["clearance_mm"])