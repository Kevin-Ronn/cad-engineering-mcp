from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from .assembly import get_component_transform
from .component_geometry import load_mesh
from .component_registry import get_component


class AssemblyAnalysisError(RuntimeError):
    pass


def transformed_mesh(component_id: str) -> trimesh.Trimesh:
    component = get_component(component_id)

    if component is None:
        raise AssemblyAnalysisError(
            f"Component not registered: {component_id}"
        )

    geometry = component.get("geometry")

    if not geometry:
        raise AssemblyAnalysisError(
            f"Component has no geometry: {component_id}"
        )

    mesh = load_mesh(
        Path(geometry["file"])
    )

    transform = np.asarray(
        get_component_transform(component_id),
        dtype=float,
    )

    mesh = mesh.copy()
    mesh.apply_transform(transform)

    return mesh


def component_envelope(
    component_id: str,
) -> dict[str, Any]:

    mesh = transformed_mesh(component_id)

    bounds = mesh.bounds

    minimum = bounds[0]
    maximum = bounds[1]

    dimensions = maximum - minimum
    center = (minimum + maximum) / 2.0

    return {
        "component_id": component_id,
        "min": minimum.tolist(),
        "max": maximum.tolist(),
        "dimensions_mm": {
            "x": float(dimensions[0]),
            "y": float(dimensions[1]),
            "z": float(dimensions[2]),
        },
        "center_mm": {
            "x": float(center[0]),
            "y": float(center[1]),
            "z": float(center[2]),
        },
    }


def envelope_intersects(
    component_a: str,
    component_b: str,
) -> bool:

    a = component_envelope(component_a)
    b = component_envelope(component_b)

    a_min = np.asarray(a["min"])
    a_max = np.asarray(a["max"])

    b_min = np.asarray(b["min"])
    b_max = np.asarray(b["max"])

    return bool(
        np.all(a_min <= b_max)
        and np.all(b_min <= a_max)
    )


def minimum_envelope_clearance(
    component_a: str,
    component_b: str,
) -> float:

    a = component_envelope(component_a)
    b = component_envelope(component_b)

    a_min = np.asarray(a["min"], dtype=float)
    a_max = np.asarray(a["max"], dtype=float)

    b_min = np.asarray(b["min"], dtype=float)
    b_max = np.asarray(b["max"], dtype=float)

    gaps = np.maximum(
        np.maximum(a_min - b_max, b_min - a_max),
        0.0,
    )

    return float(np.linalg.norm(gaps))


def mesh_interference(
    component_a: str,
    component_b: str,
) -> dict[str, Any]:

    mesh_a = transformed_mesh(component_a)
    mesh_b = transformed_mesh(component_b)

    envelope_overlap = envelope_intersects(
        component_a,
        component_b,
    )

    if not envelope_overlap:
        return {
            "component_a": component_a,
            "component_b": component_b,
            "intersects": False,
            "envelope_overlap": False,
            "clearance_mm": minimum_envelope_clearance(
                component_a,
                component_b,
            ),
        }

    # A conservative collision test.  If the meshes themselves
    # intersect, this is a confirmed geometric interference.
    try:
        collision = trimesh.collision.CollisionManager()

        collision.add_object(
            component_a,
            mesh_a,
        )

        collision.add_object(
            component_b,
            mesh_b,
        )

        intersects = collision.in_collision_internal()

    except Exception:
        # Some trimesh collision backends require optional
        # dependencies. Envelope overlap remains useful even
        # when exact collision detection is unavailable.
        intersects = None

    return {
        "component_a": component_a,
        "component_b": component_b,
        "intersects": intersects,
        "envelope_overlap": True,
        "clearance_mm": 0.0,
    }
