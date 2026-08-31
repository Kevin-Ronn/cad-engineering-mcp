"""Tests for list_analysis_artifacts, read_analysis_artifact, and
get_pose_validation_summary."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from cad_engineering_mcp.tools.read_tools import (
    get_pose_validation_summary,
    list_analysis_artifacts,
    read_analysis_artifact,
)


def test_list_analysis_artifacts_geometry_category(glasses):
    env = list_analysis_artifacts(category="geometry")
    assert env["status"] == "PASS"
    data = env["data"]
    assert data["category"] == "geometry"
    paths = [a["path"] for a in data["artifacts"]]
    assert any("component-pose-validation.json" in p for p in paths)


def test_list_analysis_artifacts_unknown_category():
    env = list_analysis_artifacts(category="nope")
    assert env["status"] == "ERROR"
    assert "Unknown category" in env["errors"][0]


def test_list_analysis_artifacts_all(glasses):
    env = list_analysis_artifacts(category="all")
    assert env["status"] == "PASS"
    paths = [a["path"] for a in env["data"]["artifacts"]]
    # Should include at least one mesh, one yaml, one json.
    kinds = {a["kind"] for a in env["data"]["artifacts"]}
    assert "json" in kinds or "yaml" in kinds


def test_list_analysis_artifacts_subdir(glasses):
    # category=mechanical -> roots=[<glasses>/mechanical]; subdir="interfaces".
    env = list_analysis_artifacts(category="mechanical", subdir="interfaces")
    assert env["status"] == "PASS", env["errors"]
    paths = [a["path"] for a in env["data"]["artifacts"]]
    assert any(p.startswith("mechanical/interfaces/") for p in paths)


def test_list_analysis_artifacts_rejects_traversal():
    env = list_analysis_artifacts(category="geometry", subdir="../../")
    assert env["status"] == "ERROR"


def test_read_analysis_artifact_json(glasses):
    env = read_analysis_artifact("analysis/geometry/frame-coordinate-system.json")
    assert env["status"] == "PASS", env["errors"]
    assert env["data"]["format"] == "json"
    assert isinstance(env["data"]["data"], dict)
    assert "coordinate_system" in env["data"]["data"]


def test_read_analysis_artifact_yaml(glasses):
    env = read_analysis_artifact("components/camera/camera-module.yaml")
    assert env["status"] == "PASS", env["errors"]
    assert env["data"]["format"] == "yaml"
    assert env["data"]["data"]["component"]["id"] == "camthink_ov5640_8p5"


def test_read_analysis_artifact_rejects_traversal():
    env = read_analysis_artifact("../../pyproject.toml")
    assert env["status"] == "ERROR"


def test_read_analysis_artifact_rejects_unsupported(glasses, tmp_path):
    bad = glasses / "analysis" / "geometry" / "junk.txt"
    bad.write_text("hello")
    try:
        env = read_analysis_artifact("analysis/geometry/junk.txt")
        assert env["status"] == "ERROR"
        assert "Unsupported format" in env["errors"][0]
    finally:
        bad.unlink()


def test_read_analysis_artifact_size_limit(glasses, tmp_path):
    big = glasses / "analysis" / "geometry" / "big.json"
    big.write_text("x" * (5 * 1024 * 1024))  # 5 MB > 4 MB
    try:
        env = read_analysis_artifact("analysis/geometry/big.json", max_bytes=4 * 1024 * 1024)
        assert env["status"] == "ERROR"
        assert "exceeds limit" in env["errors"][0]
    finally:
        big.unlink()


def test_read_analysis_artifact_json_parse_error(glasses, tmp_path):
    bad = glasses / "analysis" / "geometry" / "bad.json"
    bad.write_text("{not json")
    try:
        env = read_analysis_artifact("analysis/geometry/bad.json")
        assert env["status"] == "ERROR"
        assert "JSON parse error" in env["errors"][0]
    finally:
        bad.unlink()


def test_read_analysis_artifact_yaml_parse_error(glasses, tmp_path):
    bad = glasses / "analysis" / "geometry" / "bad.yaml"
    # Tab indentation can produce a yaml scanner error in some cases,
    # but a malformed mapping is more reliable across versions:
    bad.write_text("a: b\n  c: [unclosed\n")
    try:
        env = read_analysis_artifact("analysis/geometry/bad.yaml")
        assert env["status"] == "ERROR"
        assert "YAML parse error" in env["errors"][0]
    finally:
        bad.unlink()


def test_get_pose_validation_summary(glasses):
    env = get_pose_validation_summary()
    assert env["status"] in {"PASS", "INCOMPLETE", "FAIL", "ERROR"}, env["errors"]
    data = env["data"]
    # The current on-disk artifact has a camera whose optical cone is
    # obstructed, so the wrapper must downgrade to INCOMPLETE.
    assert data["summary_status"] == "INCOMPLETE"
    assert data["artifact_overall_status"] in {"PASS", "FAIL"}
    assert data["counts"]["accepted"] >= 1
    # At least the camera should be flagged with aperture_required=True.
    labels = {a["component"] for a in data["aperture_required"]}
    assert "camthink_ov5640_8p5" in labels
    # Notes should explicitly call out the camera obstruction.
    assert any("obstructed" in n.lower() for n in data["notes"])


def test_get_pose_validation_summary_default_artifact(glasses):
    env = get_pose_validation_summary()
    assert env["status"] != "ERROR", env["errors"]
    assert env["data"]["path"].endswith("component-pose-validation.json")


def test_get_pose_validation_summary_traversal():
    env = get_pose_validation_summary(artifact="../../etc/passwd")
    assert env["status"] == "ERROR"