from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import trimesh
import yaml


PROJECT_ROOT = Path.home() / "cad-engineering-mcp"
REFERENCE_ROOT = PROJECT_ROOT / "projects" / "glasses" / "references"
MANIFEST_PATH = REFERENCE_ROOT / "reference-manifest.yaml"


class ReferenceGeometryError(RuntimeError):
    pass


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise ReferenceGeometryError(
            f"Reference manifest not found: {MANIFEST_PATH}"
        )

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ReferenceGeometryError("Reference manifest is not a mapping.")

    if data.get("units") != "mm":
        raise ReferenceGeometryError(
            "Reference manifest must use millimetres."
        )

    return data


def get_reference(name: str) -> dict[str, Any]:
    manifest = load_manifest()
    references = manifest.get("references", {})

    if name not in references:
        available = ", ".join(sorted(references))
        raise ReferenceGeometryError(
            f"Unknown reference '{name}'. Available: {available}"
        )

    return references[name]


def resolve_reference_path(name: str) -> Path:
    ref = get_reference(name)

    relative_path = ref.get("file")
    if not relative_path:
        raise ReferenceGeometryError(
            f"Reference '{name}' has no file path."
        )

    path = (REFERENCE_ROOT / relative_path).resolve()

    # Prevent references from escaping the reference directory.
    if REFERENCE_ROOT.resolve() not in path.parents:
        raise ReferenceGeometryError(
            f"Reference path escapes reference directory: {path}"
        )

    if not path.exists():
        raise ReferenceGeometryError(
            f"Reference file does not exist: {path}"
        )

    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def verify_reference_integrity(name: str) -> dict[str, Any]:
    ref = get_reference(name)
    path = resolve_reference_path(name)

    actual_hash = sha256_file(path)
    expected_hash = ref.get("sha256")

    return {
        "name": name,
        "file": str(path),
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "verified": (
            expected_hash is not None
            and actual_hash == expected_hash
        ),
    }


def load_reference_mesh(name: str) -> trimesh.Trimesh:
    integrity = verify_reference_integrity(name)

    if not integrity["verified"]:
        raise ReferenceGeometryError(
            f"SHA-256 verification failed for reference '{name}'."
        )

    path = Path(integrity["file"])

    loaded = trimesh.load_mesh(
        path,
        process=False,
    )

    if isinstance(loaded, trimesh.Scene):
        meshes = [
            geometry
            for geometry in loaded.geometry.values()
            if isinstance(geometry, trimesh.Trimesh)
        ]

        if not meshes:
            raise ReferenceGeometryError(
                f"No mesh geometry found in {path}"
            )

        loaded = trimesh.util.concatenate(meshes)

    if not isinstance(loaded, trimesh.Trimesh):
        raise ReferenceGeometryError(
            f"Unsupported geometry in {path}"
        )

    return loaded


def mesh_summary(name: str) -> dict[str, Any]:
    mesh = load_reference_mesh(name)
    ref = get_reference(name)

    bounds = mesh.bounds
    extents = mesh.extents

    return {
        "name": name,
        "file": ref["file"],
        "units": "mm",
        "vertices": int(len(mesh.vertices)),
        "triangles": int(len(mesh.faces)),
        "bounds": {
            "min": [float(v) for v in bounds[0]],
            "max": [float(v) for v in bounds[1]],
        },
        "dimensions_mm": {
            "x": float(extents[0]),
            "y": float(extents[1]),
            "z": float(extents[2]),
        },
        "watertight": bool(mesh.is_watertight),
        "winding_valid": bool(mesh.is_winding_consistent),
    }


def list_references() -> list[dict[str, Any]]:
    manifest = load_manifest()

    result = []

    for name, ref in manifest.get("references", {}).items():
        result.append(
            {
                "name": name,
                "file": ref.get("file"),
                "type": ref.get("type"),
                "role": ref.get("role", []),
                "units": ref.get("units", manifest.get("units")),
            }
        )

    return result


def measure_reference(name: str) -> dict[str, Any]:
    return mesh_summary(name)


def measure_distance(
    reference_a: str,
    reference_b: str,
) -> dict[str, Any]:
    mesh_a = load_reference_mesh(reference_a)
    mesh_b = load_reference_mesh(reference_b)

    distance_a_to_b = trimesh.proximity.closest_point(
        mesh_b,
        mesh_a.vertices,
    )[1]

    distance_b_to_a = trimesh.proximity.closest_point(
        mesh_a,
        mesh_b.vertices,
    )[1]

    return {
        "reference_a": reference_a,
        "reference_b": reference_b,
        "units": "mm",
        "minimum_vertex_to_surface_distance_a_to_b": float(
            distance_a_to_b.min()
        ),
        "minimum_vertex_to_surface_distance_b_to_a": float(
            distance_b_to_a.min()
        ),
    }
