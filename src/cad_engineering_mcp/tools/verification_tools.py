"""Verification MCP tools: SHA-256 integrity, mesh measurement, distance.

These three tools are read-only. They wrap the engineering modules
already shipped in this repository:

* :func:`verify_reference_integrity` -- reference_geometry.verify_reference_integrity
* :func:`measure_mesh` -- component_geometry.measure_mesh
* :func:`minimum_surface_distance` -- component_geometry.minimum_surface_distance

They never mutate anything and never execute arbitrary code.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import trimesh

from ..engineering.component_geometry import (
    ComponentGeometryError,
    SUPPORTED_MESH_EXTENSIONS,
    load_mesh,
)
from ..engineering.reference_geometry import (
    ReferenceGeometryError,
    load_manifest,
    verify_reference_integrity as _verify_reference_integrity,
)
from ._envelope import make_envelope, utcnow_iso
from ._paths import (
    PathSecurityError,
    glasses_root,
    safe_resolve,
)


def _sha256(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_reference_integrity(name: str | None = None) -> dict[str, Any]:
    """Verify SHA-256 of every entry (or one entry) in the reference manifest.

    Returns a list of per-reference results plus an overall ``verified``
    flag. If any single reference fails verification the tool status is
    ``FAIL`` (not ``ERROR``); only manifest or path-resolution failures
    produce ``ERROR``.
    """
    try:
        manifest = load_manifest()
    except ReferenceGeometryError as exc:
        return make_envelope(
            tool="verify_reference_integrity",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    references = manifest.get("references", {}) or {}
    if not references:
        return make_envelope(
            tool="verify_reference_integrity",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="INCOMPLETE",
            data={"verified": [], "failed": [], "missing_manifest_field": True},
            errors=["Manifest has no 'references' entries"],
        )

    targets = [name] if name else list(references.keys())
    unknown = [t for t in targets if t not in references]
    if unknown:
        return make_envelope(
            tool="verify_reference_integrity",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={"unknown": unknown},
            errors=[f"Unknown reference(s): {', '.join(unknown)}"],
        )

    verified: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    errors: list[str] = []
    for ref_name in targets:
        try:
            result = _verify_reference_integrity(ref_name)
        except ReferenceGeometryError as exc:
            failed.append({"name": ref_name, "reason": str(exc)})
            errors.append(f"{ref_name}: {exc}")
            continue
        if result.get("verified"):
            verified.append(result)
        else:
            failed.append(result)

    status = "PASS" if not failed else "FAIL"
    return make_envelope(
        tool="verify_reference_integrity",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status=status,
        data={
            "manifest_path": "references/reference-manifest.yaml",
            "checked": len(targets),
            "verified": verified,
            "failed": failed,
            "all_verified": len(failed) == 0,
        },
        errors=errors,
    )


def measure_mesh(path: str) -> dict[str, Any]:
    """Measure an STL/STEP/3MF/OBJ/PLY/OFF mesh.

    Returns bounding box, dimensions, centroid, volume, surface area,
    watertight and winding-consistent flags, and the file SHA-256.
    """
    try:
        resolved = safe_resolve(path)
    except PathSecurityError as exc:
        return make_envelope(
            tool="measure_mesh",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    suffix = resolved.suffix.lower()
    if suffix not in SUPPORTED_MESH_EXTENSIONS:
        return make_envelope(
            tool="measure_mesh",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
                "suffix": suffix,
            },
            errors=[
                f"Unsupported mesh extension {suffix!r}; "
                f"expected one of: {sorted(SUPPORTED_MESH_EXTENSIONS)}"
            ],
        )

    try:
        mesh = load_mesh(resolved)
    except ComponentGeometryError as exc:
        return make_envelope(
            tool="measure_mesh",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    bounds = mesh.bounds
    minimum = bounds[0]
    maximum = bounds[1]
    size = maximum - minimum
    bbox_center = (minimum + maximum) / 2.0

    return make_envelope(
        tool="measure_mesh",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status="PASS",
        data={
            "path": str(resolved.relative_to(glasses_root())),
            "sha256": _sha256(resolved),
            "vertices": int(len(mesh.vertices)),
            "triangles": int(len(mesh.faces)),
            "bounds_mm": {
                "min": [float(v) for v in minimum],
                "max": [float(v) for v in maximum],
            },
            "dimensions_mm": {
                "x": float(size[0]),
                "y": float(size[1]),
                "z": float(size[2]),
            },
            "bbox_center_mm": {
                "x": float(bbox_center[0]),
                "y": float(bbox_center[1]),
                "z": float(bbox_center[2]),
            },
            "volume_mm3": float(abs(mesh.volume)),
            "surface_area_mm2": float(mesh.area),
            "watertight": bool(mesh.is_watertight),
            "winding_consistent": bool(mesh.is_winding_consistent),
        },
    )


def minimum_surface_distance(
    path_a: str,
    path_b: str,
) -> dict[str, Any]:
    """Compute the minimum surface-to-surface distance between two meshes.

    Both paths must resolve under ``projects/glasses``. The tool returns
    the per-mesh minimum vertex-to-surface distance (so callers can
    detect asymmetric gaps) plus the symmetric minimum.
    """
    errors: list[str] = []
    try:
        a = safe_resolve(path_a)
    except PathSecurityError as exc:
        errors.append(f"path_a: {exc}")
    try:
        b = safe_resolve(path_b)
    except PathSecurityError as exc:
        errors.append(f"path_b: {exc}")
    if errors:
        return make_envelope(
            tool="minimum_surface_distance",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=errors,
        )

    try:
        mesh_a = load_mesh(a)
        mesh_b = load_mesh(b)
        d_a, _, _ = trimesh.proximity.closest_point(mesh_b, mesh_a.vertices)
        d_b, _, _ = trimesh.proximity.closest_point(mesh_a, mesh_b.vertices)
        sym_min = float(min(float(d_a.min()), float(d_b.min())))
    except ComponentGeometryError as exc:
        return make_envelope(
            tool="minimum_surface_distance",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )
    except Exception as exc:  # noqa: BLE001 -- defensive: surface as ERROR
        return make_envelope(
            tool="minimum_surface_distance",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    return make_envelope(
        tool="minimum_surface_distance",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status="PASS",
        data={
            "path_a": str(a.relative_to(glasses_root())),
            "path_b": str(b.relative_to(glasses_root())),
            "units": "mm",
            "min_vertex_to_surface_a_to_b_mm": float(d_a.min()),
            "min_vertex_to_surface_b_to_a_mm": float(d_b.min()),
            "min_surface_distance_mm": sym_min,
        },
    )