from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh


class ComponentGeometryError(RuntimeError):
    pass


SUPPORTED_MESH_EXTENSIONS = {
    ".stl",
    ".obj",
    ".ply",
    ".off",
    ".3mf",
}


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    path = Path(path)

    if not path.exists():
        raise ComponentGeometryError(
            f"Geometry file does not exist: {path}"
        )

    if path.suffix.lower() not in SUPPORTED_MESH_EXTENSIONS:
        raise ComponentGeometryError(
            f"Unsupported mesh format: {path.suffix}"
        )

    loaded = trimesh.load(path, process=False)

    if isinstance(loaded, trimesh.Scene):
        geometries = list(loaded.geometry.values())

        if not geometries:
            raise ComponentGeometryError(
                f"Scene contains no geometry: {path}"
            )

        mesh = trimesh.util.concatenate(geometries)

    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded

    else:
        raise ComponentGeometryError(
            f"Unsupported geometry object: {type(loaded)}"
        )

    return mesh


def measure_mesh(path: str | Path) -> dict[str, Any]:
    mesh = load_mesh(path)

    bounds = mesh.bounds
    minimum = bounds[0]
    maximum = bounds[1]

    size = maximum - minimum

    center = mesh.bounding_box.centroid

    result = {
        "file": str(Path(path).resolve()),
        "vertices": int(len(mesh.vertices)),
        "triangles": int(len(mesh.faces)),
        "bounds": {
            "min": [float(v) for v in minimum],
            "max": [float(v) for v in maximum],
        },
        "dimensions_mm": {
            "x": float(size[0]),
            "y": float(size[1]),
            "z": float(size[2]),
        },
        "center_mm": {
            "x": float(center[0]),
            "y": float(center[1]),
            "z": float(center[2]),
        },
        "volume_mm3": float(abs(mesh.volume)),
        "surface_area_mm2": float(mesh.area),
        "watertight": bool(mesh.is_watertight),
        "winding_valid": bool(mesh.is_winding_consistent),
        "extents_mm": [float(v) for v in size],
    }

    return result


def mesh_contains_point(
    path: str | Path,
    point: list[float],
) -> bool:
    mesh = load_mesh(path)

    if len(point) != 3:
        raise ComponentGeometryError(
            "Point must contain exactly three coordinates."
        )

    return bool(mesh.contains(np.asarray(point, dtype=float))[0])


def minimum_surface_distance(
    path_a: str | Path,
    path_b: str | Path,
) -> float:
    mesh_a = load_mesh(path_a)
    mesh_b = load_mesh(path_b)

    distances_a, _, _ = trimesh.proximity.closest_point(
        mesh_a,
        mesh_b.vertices,
    )

    distances_b, _, _ = trimesh.proximity.closest_point(
        mesh_b,
        mesh_a.vertices,
    )

    return float(
        min(
            np.min(distances_a),
            np.min(distances_b),
        )
    )
