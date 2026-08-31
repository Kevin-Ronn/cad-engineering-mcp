"""Tests for the Phase 2 ``mesh_interference`` MCP tool."""
from __future__ import annotations

import json

import pytest

from cad_engineering_mcp.tools.mesh_interference import mesh_interference


def test_envelope_shape_present():
    env = mesh_interference("wayfarer_left_temple", "wayfarer_right_temple")
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
    assert env["tool"] == "mesh_interference"
    assert isinstance(env["errors"], list)


def test_non_intersecting_meshes_report_pass():
    env = mesh_interference("wayfarer_left_temple", "wayfarer_right_temple")
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    assert data["intersects"] is False
    assert data["envelope_overlap"] is False
    assert data["clearance_classification"] == "NOMINAL"
    assert data["min_surface_distance_mm"] > 0.0
    assert data["collision_engine"] is not None


def test_intersecting_meshes_report_fail():
    # A mesh tested against itself is the canonical "intersects" case.
    env = mesh_interference("wayfarer_left_temple", "wayfarer_left_temple")
    assert env["status"] == "FAIL", env["errors"]
    data = env["data"]
    assert data["intersects"] is True
    assert data["clearance_classification"] == "INTERFERENCE"


def test_unknown_component_returns_error():
    env = mesh_interference("does_not_exist", "wayfarer_left_temple")
    assert env["status"] == "ERROR"
    assert "does_not_exist" in env["errors"][0]


def test_missing_geometry_returns_error():
    # The LED has no authoritative STEP/STL yet — that must surface as
    # a structured error rather than be fabricated.
    env = mesh_interference("vsma1094750x02", "wayfarer_left_temple")
    assert env["status"] == "ERROR"
    assert "UNKNOWN" in env["errors"][0] or "not yet" in env["errors"][0]


def test_empty_inputs_return_error():
    env = mesh_interference("", "wayfarer_left_temple")
    assert env["status"] == "ERROR"
    assert "component_a_id" in env["errors"][0]

    env = mesh_interference("wayfarer_left_temple", "")
    assert env["status"] == "ERROR"
    assert "component_b_id" in env["errors"][0]


def test_path_security_traversal_rejected():
    # The mesh_interference tool must not honour untrusted filesystem
    # paths from the caller; only component IDs are accepted.
    env = mesh_interference(
        "../../etc/passwd", "wayfarer_left_temple"
    )
    assert env["status"] == "ERROR"


def test_structured_output_includes_provenance():
    env = mesh_interference("wayfarer_left_temple", "wayfarer_right_temple")
    data = env["data"]
    assert "component_a_metadata" in data
    assert "component_b_metadata" in data
    assert data["component_a_metadata"]["component_id"] == (
        "wayfarer_left_temple"
    )
    assert data["component_b_metadata"]["component_id"] == (
        "wayfarer_right_temple"
    )


def test_engine_notes_are_present():
    env = mesh_interference("wayfarer_left_temple", "wayfarer_right_temple")
    data = env["data"]
    assert "engine_notes" in data
    assert data["engine_notes"]  # non-empty list


def test_bbox_gap_is_reported():
    env = mesh_interference("wayfarer_left_temple", "wayfarer_right_temple")
    data = env["data"]
    assert "bbox_gap_mm" in data
    assert "envelope_gap_per_axis_mm" in data
    assert len(data["envelope_gap_per_axis_mm"]) == 3