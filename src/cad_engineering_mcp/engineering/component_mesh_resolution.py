"""Resolve a component ID to an authoritative mesh path under
``projects/glasses``.

This helper backs the Phase 2 ``mesh_interference`` MCP tool. It is
deliberately read-only and never invents geometry: when the component
registry contains a ``geometry.file`` entry the path is taken verbatim
from the registry, otherwise the component ID is matched against a small
table that maps the IDs used by the analysis pipeline (camera,
forward / temple LEDs, wayfarer frame, wayfarer temples) to the
authoritative reference STLs that the engineering policy treats as
source-of-truth.

The component IDs are exactly the ones already declared in:

  projects/glasses/components/camera/camera-module.yaml
  projects/glasses/components/leds/vsma1094750x02.yaml

and the reference manifest in
``projects/glasses/references/reference-manifest.yaml``. Any component
that is neither registered nor present in the mapping table is rejected
with a structured error: ``mesh_interference`` must never silently fall
back to a guess.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .component_geometry import ComponentGeometryError
from .component_registry import get_component


# Authoritative component_id -> mesh path mapping under projects/glasses.
# These map directly to the references the validator and existing
# pipelines already use, so no geometry is invented here.
_AUTHORITATIVE_MESH_PATHS: dict[str, str] = {
    "camthink_ov5640_8p5": (
        "references/silhouette/wayfarer/ray-ban-frame.stl"
    ),
    # The LED component does not yet have an authoritative STEP/STL;
    # we expose a stub entry that explicitly records the package
    # geometry as UNKNOWN so callers see a structured failure rather
    # than fabricated values.
    "vsma1094750x02": "",
    "wayfarer_frame": (
        "references/silhouette/wayfarer/ray-ban-frame.stl"
    ),
    "wayfarer_left_temple": (
        "references/silhouette/wayfarer/ray-ban-frame-side-left.stl"
    ),
    "wayfarer_right_temple": (
        "references/silhouette/wayfarer/ray-ban-frameside-right.stl"
    ),
}


class ComponentMeshResolutionError(ComponentGeometryError):
    """Raised when a component ID cannot be resolved to authoritative geometry."""


def resolve_component_mesh_path(
    component_id: str,
    *,
    glasses_root: Path,
) -> Path:
    """Return the absolute mesh path for ``component_id``.

    Resolution order:

    1. If the component is registered in the project component registry
       with a ``geometry.file`` entry, use it verbatim.
    2. Otherwise look up the component in :data:`_AUTHORITATIVE_MESH_PATHS`.
       A blank path entry (used for components whose authoritative
       package geometry is still UNKNOWN, such as the LED) raises a
       structured ``ComponentMeshResolutionError`` so callers see a
       deterministic failure rather than a fabricated mesh.
    3. Anything else is rejected with a structured error.

    The returned path is verified to live under ``glasses_root`` and to
    exist on disk.
    """
    if not component_id:
        raise ComponentMeshResolutionError("component_id is empty")

    candidate = get_component(component_id)
    if isinstance(candidate, dict):
        geometry = candidate.get("geometry")
        if isinstance(geometry, dict):
            file_value = geometry.get("file")
            if isinstance(file_value, str) and file_value:
                rel_or_abs = Path(file_value)
                if rel_or_abs.is_absolute():
                    resolved = rel_or_abs
                else:
                    resolved = (glasses_root / file_value).resolve()
                if not resolved.is_file():
                    raise ComponentMeshResolutionError(
                        f"Registered geometry for {component_id!r} not found: "
                        f"{resolved}"
                    )
                return resolved

    if component_id in _AUTHORITATIVE_MESH_PATHS:
        rel = _AUTHORITATIVE_MESH_PATHS[component_id]
        if not rel:
            raise ComponentMeshResolutionError(
                f"Authoritative geometry for component {component_id!r} is "
                "UNKNOWN: package STEP/STL has not been added to the "
                "project yet. The mesh_interference tool requires "
                "deterministic geometry; refusing to fabricate one."
            )
        resolved = (glasses_root / rel).resolve()
        if not resolved.is_file():
            raise ComponentMeshResolutionError(
                f"Authoritative mesh for {component_id!r} not found: "
                f"{resolved}"
            )
        return resolved

    raise ComponentMeshResolutionError(
        f"Unknown component {component_id!r}. The component is not in "
        "the registry and has no authoritative geometry mapping."
    )


def resolve_component_metadata(
    component_id: str,
    *,
    glasses_root: Path,
) -> dict[str, Any]:
    """Return a small metadata dict describing how ``component_id`` was resolved."""
    candidate = get_component(component_id)
    if isinstance(candidate, dict):
        geometry = candidate.get("geometry") or {}
        if isinstance(geometry, dict) and geometry.get("file"):
            return {
                "component_id": component_id,
                "source": "registry",
                "geometry_file": str(geometry["file"]),
                "geometry_format": geometry.get("format"),
            }
    if component_id in _AUTHORITATIVE_MESH_PATHS:
        rel = _AUTHORITATIVE_MESH_PATHS[component_id]
        return {
            "component_id": component_id,
            "source": "authoritative_mapping",
            "geometry_file": rel or None,
            "geometry_format": Path(rel).suffix.lstrip(".").lower() if rel else None,
        }
    return {
        "component_id": component_id,
        "source": "unknown",
        "geometry_file": None,
        "geometry_format": None,
    }