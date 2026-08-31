"""Tests for verify_reference_integrity, measure_mesh, and
minimum_surface_distance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._paths import PathSecurityError
from cad_engineering_mcp.tools.verification_tools import (
    measure_mesh,
    minimum_surface_distance,
    verify_reference_integrity,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_verify_reference_integrity_all(glasses):
    env = verify_reference_integrity()
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    assert data["checked"] >= 4  # three wayfarer STLs + meta reference
    assert data["all_verified"]
    for entry in data["verified"]:
        assert entry["verified"]
        # The hash present in the manifest must match the actual file.
        assert entry["actual_sha256"] == entry["expected_sha256"]


def test_verify_reference_integrity_one_name(glasses):
    env = verify_reference_integrity(name="wayfarer_frame")
    assert env["status"] == "PASS"
    assert env["data"]["checked"] == 1
    assert env["data"]["verified"][0]["name"] == "wayfarer_frame"


def test_verify_reference_integrity_unknown_name():
    env = verify_reference_integrity(name="not_a_reference")
    assert env["status"] == "ERROR"
    assert "Unknown reference" in env["errors"][0]


def test_measure_mesh_frame(glasses):
    env = measure_mesh("references/silhouette/wayfarer/ray-ban-frame.stl")
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    assert data["triangles"] > 0
    assert data["vertices"] > 0
    # Sanity bounds: a wayfarer frame is roughly 17.7 x 143 x 42.85 mm.
    assert 10 < data["dimensions_mm"]["x"] < 30
    assert 100 < data["dimensions_mm"]["y"] < 200
    assert 30 < data["dimensions_mm"]["z"] < 60
    assert data["sha256"] == _sha256(
        glasses / "references" / "silhouette" / "wayfarer" / "ray-ban-frame.stl"
    )
    # The engineering load path uses trimesh.process=False to preserve
    # the authored mesh exactly, so vertex-level watertight checks may
    # report False even when the surface is closed. The validator that
    # uses the default trimesh loader reports watertight=True; we surface
    # the loader-faithful flag here so callers can tell which mode they
    # got.
    assert "watertight" in data
    assert "winding_consistent" in data


def test_measure_mesh_left_temple(glasses):
    env = measure_mesh("references/silhouette/wayfarer/ray-ban-frame-side-left.stl")
    assert env["status"] == "PASS"
    assert env["data"]["triangles"] == 4032


def test_measure_mesh_rejects_traversal():
    env = measure_mesh("../../etc/passwd")
    assert env["status"] == "ERROR"


def test_measure_mesh_rejects_unsupported_extension(glasses, tmp_path):
    fake = glasses / "analysis" / "geometry" / "fake.mmx"
    fake.write_text("not a mesh")
    try:
        env = measure_mesh("analysis/geometry/fake.mmx")
        assert env["status"] == "ERROR"
        assert "Unsupported mesh extension" in env["errors"][0]
    finally:
        fake.unlink()


def test_minimum_surface_distance_two_temples(glasses):
    env = minimum_surface_distance(
        "references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
        "references/silhouette/wayfarer/ray-ban-frameside-right.stl",
    )
    assert env["status"] == "PASS", env["errors"]
    data = env["data"]
    # The two temples are independent meshes; their closest surface
    # distance must be strictly positive.
    assert data["min_surface_distance_mm"] > 0.0
    assert data["min_vertex_to_surface_a_to_b_mm"] > 0.0
    assert data["min_vertex_to_surface_b_to_a_mm"] > 0.0
    # Symmetric minimum must equal min(directional).
    expected = min(
        data["min_vertex_to_surface_a_to_b_mm"],
        data["min_vertex_to_surface_b_to_a_mm"],
    )
    assert abs(data["min_surface_distance_mm"] - expected) < 1e-6


def test_minimum_surface_distance_rejects_traversal():
    env = minimum_surface_distance(
        "references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
        "../../etc/passwd",
    )
    assert env["status"] == "ERROR"


def test_minimum_surface_distance_handles_missing(glasses):
    env = minimum_surface_distance(
        "references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
        "analysis/geometry/does_not_exist.stl",
    )
    assert env["status"] == "ERROR"