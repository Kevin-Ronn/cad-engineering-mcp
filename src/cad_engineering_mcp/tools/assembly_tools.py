"""Phase 3 assembly MCP tools: ``list_assembly_components`` and ``add_assembly_component``.

These tools wrap :mod:`cad_engineering_mcp.engineering.assembly` and add
the Phase 3 mandatory envelopes, safety checks, backups, and audit
logging. The two tools together represent the only mutation surface for
the assembly manifest ``projects/glasses/mechanical/assemblies/glasses-assembly.yaml``.

Engineering rules (mirrors of the directive):

* Component IDs must be unique within the assembly. Duplicate IDs are
  rejected with ``status = "ERROR"``.
* Positions must be finite 3-vectors of floats. NaN / infinity is rejected.
* Rotations must be finite 3-vectors of floats, in degrees, applied in
  the XYZ intrinsic order.
* Positions outside the frame bounding box are rejected unless the
  caller explicitly passes ``confirm_out_of_bounds=true``. The frame
  bounding box is taken from the *latest* pose-coordinate system
  (``analysis/geometry/frame-coordinate-system.json``) so the bounds
  check is consistent with the rest of the engineering pipeline.
* A backup of the previous assembly YAML is written before any mutation.
* The mutation is recorded in the audit log.

Coordinate-system name default is ``glasses_master`` (matches the
manifest).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml

from ..engineering.assembly import (
    ASSEMBLY_PATH,
    AssemblyError,
    add_component as _add_component_engineering,
    list_assembly_components as _list_components_engineering,
    load_assembly,
    save_assembly,
)
from ._envelope import make_envelope, utcnow_iso
from ._mutation import (
    MutationError,
    audit,
    backup_existing,
    safe_destination,
    utc_timestamp_fs,
)
from ._paths import (
    PathSecurityError,
    glasses_root,
    project_root,
    safe_resolve,
)


ASSEMBLY_REL = Path("mechanical/assemblies/glasses-assembly.yaml")
FRAME_COORDS_REL = Path("analysis/geometry/frame-coordinate-system.json")


def _resolve_assembly_path() -> Path:
    """Resolve the assembly YAML via ``safe_resolve``."""
    return safe_resolve(ASSEMBLY_REL)


def _load_frame_bbox() -> dict[str, Any] | None:
    """Return the frame bbox, or ``None`` if not available.

    Used to bound-check candidate positions.
    """
    try:
        coords = safe_resolve(FRAME_COORDS_REL)
    except PathSecurityError:
        return None
    if not coords.is_file():
        return None
    try:
        data = json.loads(coords.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    bbox = data.get("frame_bbox_mm")
    if not bbox:
        return None
    try:
        minimum = list(bbox["min"])
        maximum = list(bbox["max"])
    except (KeyError, TypeError):
        return None
    if len(minimum) != 3 or len(maximum) != 3:
        return None
    return {"min": minimum, "max": maximum}


def _is_finite_vector(values: list[float], *, length: int) -> bool:
    """True iff ``values`` is a finite float vector of length ``length``."""
    if not isinstance(values, list):
        return False
    if len(values) != length:
        return False
    for v in values:
        if isinstance(v, bool):  # bool is an int subclass; reject it
            return False
        if not isinstance(v, (int, float)):
            return False
        f = float(v)
        if not math.isfinite(f):
            return False
    return True


def _position_out_of_bounds(
    position: list[float], bbox: dict[str, Any] | None
) -> bool:
    """True iff ``position`` is outside ``bbox`` in any axis."""
    if bbox is None:
        return False
    minimum = bbox["min"]
    maximum = bbox["max"]
    for axis, (lo, hi, v) in enumerate(zip(minimum, maximum, position)):
        if v < lo or v > hi:
            return True
    return False


def list_assembly_components() -> dict[str, Any]:
    """Return structured component records from ``glasses-assembly.yaml``.

    Read-only. Returns a ``PASS`` envelope with the manifest path and a
    list of components (id, coordinate system, position_mm,
    rotation_deg, transform summary). An empty assembly returns
    ``PASS`` with an empty list.
    """
    started = utcnow_iso()
    try:
        resolved = _resolve_assembly_path()
    except PathSecurityError as exc:
        return make_envelope(
            tool="list_assembly_components",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    if not resolved.is_file():
        return make_envelope(
            tool="list_assembly_components",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"path": str(resolved.relative_to(glasses_root()))},
            errors=[f"Assembly manifest does not exist: {resolved}"],
        )

    try:
        data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return make_envelope(
            tool="list_assembly_components",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"path": str(resolved.relative_to(glasses_root()))},
            errors=[f"YAML parse error: {exc}"],
        )

    if not isinstance(data, dict):
        return make_envelope(
            tool="list_assembly_components",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"path": str(resolved.relative_to(glasses_root()))},
            errors=["Assembly manifest must contain a YAML mapping."],
        )

    components = data.get("components", {}) or {}
    if not isinstance(components, dict):
        return make_envelope(
            tool="list_assembly_components",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"path": str(resolved.relative_to(glasses_root()))},
            errors=["'components' field must be a mapping."],
        )

    components_out: list[dict[str, Any]] = []
    for cid, comp in components.items():
        if not isinstance(comp, dict):
            continue
        components_out.append(
            {
                "id": cid,
                "coordinate_system": comp.get("coordinate_system"),
                "position_mm": comp.get("position_mm"),
                "rotation_deg": comp.get("rotation_deg"),
                "interfaces": comp.get("interfaces", []),
                "constraints": comp.get("constraints", []),
            }
        )

    return make_envelope(
        tool="list_assembly_components",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "path": str(resolved.relative_to(glasses_root())),
            "units": data.get("units"),
            "assembly": data.get("assembly"),
            "component_count": len(components_out),
            "components": components_out,
        },
    )


def add_assembly_component(
    component_id: str,
    position_mm: list[float],
    rotation_deg: list[float] | None = None,
    coordinate_system: str = "glasses_master",
    confirm_out_of_bounds: bool = False,
) -> dict[str, Any]:
    """Add a new component to ``glasses-assembly.yaml``.

    Parameters
    ----------
    component_id:
        Unique component identifier. Must not already be present in the
        assembly.
    position_mm:
        3-vector ``[x, y, z]`` in millimetres.
    rotation_deg:
        Optional 3-vector ``[rx, ry, rz]`` in degrees; defaults to
        ``[0.0, 0.0, 0.0]``.
    coordinate_system:
        Optional coordinate-system name; defaults to ``"glasses_master"``.
    confirm_out_of_bounds:
        When ``False`` (the default), the position is rejected if it
        lies outside the frame bounding box from the latest
        ``frame-coordinate-system.json``. Pass ``True`` to bypass the
        check (e.g. for camera/LED placement where the natural
        coordinate space extends beyond the frame bbox).
    """
    started = utcnow_iso()
    timestamp = utc_timestamp_fs()
    errors: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if not isinstance(component_id, str) or not component_id:
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=["component_id must be a non-empty string."],
        )

    if rotation_deg is None:
        rotation_deg = [0.0, 0.0, 0.0]

    if not _is_finite_vector(position_mm, length=3):
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                "position_mm must be a finite 3-vector of numbers "
                f"(got {position_mm!r})."
            ],
        )

    if not _is_finite_vector(rotation_deg, length=3):
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                "rotation_deg must be a finite 3-vector of numbers "
                f"(got {rotation_deg!r})."
            ],
        )

    if not isinstance(coordinate_system, str) or not coordinate_system:
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=["coordinate_system must be a non-empty string."],
        )

    # Resolve destination; if not safe, abort.
    try:
        destination = _resolve_assembly_path()
    except PathSecurityError as exc:
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # Bounds check.
    bbox = _load_frame_bbox()
    position_float = [float(v) for v in position_mm]
    oob = _position_out_of_bounds(position_float, bbox)
    if oob and not confirm_out_of_bounds:
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={
                "frame_bbox_mm": bbox,
                "position_mm": position_float,
            },
            errors=[
                f"position_mm={position_float} lies outside the frame "
                "bounding box. Re-run with confirm_out_of_bounds=true to "
                "override."
            ],
        )

    if oob and confirm_out_of_bounds:
        warnings.append(
            f"position_mm={position_float} is outside the frame bbox; "
            "confirm_out_of_bounds=true was used."
        )

    # Load existing assembly.
    if not destination.is_file():
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                f"Assembly manifest does not exist: {destination}. "
                "Run the engineering pipeline first to create it."
            ],
        )

    try:
        assembly = load_assembly()
    except AssemblyError as exc:
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"Failed to load assembly: {exc}"],
        )

    if component_id in assembly.get("components", {}):
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"component_id": component_id},
            errors=[
                f"Component '{component_id}' is already in the assembly."
            ],
        )

    # ------------------------------------------------------------------
    # Mutation with backup + audit
    # ------------------------------------------------------------------
    backup = backup_existing(timestamp, source=destination)
    try:
        result = _add_component_engineering(
            component_id=component_id,
            position=position_float,
            rotation_deg=[float(v) for v in rotation_deg],
            coordinate_system=coordinate_system,
        )
    except AssemblyError as exc:
        audit(
            timestamp=timestamp,
            tool="add_assembly_component",
            operation="add",
            affected_paths=[str(destination.relative_to(glasses_root()))],
            success=False,
            metadata={"component_id": component_id},
            errors=[str(exc)],
        )
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"component_id": component_id},
            errors=[f"Engineering module rejected component: {exc}"],
        )

    # Validate the resulting YAML by re-loading it.
    try:
        reloaded = yaml.safe_load(destination.read_text(encoding="utf-8"))
        if not isinstance(reloaded, dict):
            raise AssemblyError("Resulting YAML is not a mapping.")
        if component_id not in reloaded.get("components", {}):
            raise AssemblyError(
                f"Component '{component_id}' missing from reloaded YAML."
            )
    except (yaml.YAMLError, AssemblyError, UnicodeDecodeError) as exc:
        # Roll back from the backup so the workspace is left consistent.
        if backup is not None and backup.is_file():
            try:
                # Replace current file with backup.
                backup_bytes = backup.read_bytes()
                tmp = destination.with_suffix(destination.suffix + ".rollback")
                tmp.write_bytes(backup_bytes)
                tmp.replace(destination)
            except OSError:
                pass
        audit(
            timestamp=timestamp,
            tool="add_assembly_component",
            operation="add",
            affected_paths=[str(destination.relative_to(glasses_root()))],
            success=False,
            metadata={
                "component_id": component_id,
                "backup": str(backup.relative_to(glasses_root())) if backup else None,
            },
            errors=[f"Post-write validation failed: {exc}"],
        )
        return make_envelope(
            tool="add_assembly_component",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"component_id": component_id},
            errors=[f"Post-write YAML validation failed: {exc}"],
        )

    audit(
        timestamp=timestamp,
        tool="add_assembly_component",
        operation="add",
        affected_paths=[str(destination.relative_to(glasses_root()))],
        success=True,
        metadata={
            "component_id": component_id,
            "coordinate_system": coordinate_system,
            "position_mm": position_float,
            "rotation_deg": [float(v) for v in rotation_deg],
            "backup": str(backup.relative_to(glasses_root())) if backup else None,
        },
    )

    return make_envelope(
        tool="add_assembly_component",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "component_id": component_id,
            "coordinate_system": coordinate_system,
            "position_mm": position_float,
            "rotation_deg": [float(v) for v in rotation_deg],
            "backup": (
                str(backup.relative_to(glasses_root())) if backup else None
            ),
            "frame_bbox_mm": bbox,
            "out_of_bounds": oob,
        },
        warnings=warnings,
    )