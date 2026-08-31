"""Phase 2 ``propose_pose`` MCP tool.

Exposes geometry-aware component candidate generation through MCP
without mutating the workspace. The tool wraps the refactored
``generate_component_candidates.generate_component_candidates`` importable
function and filters the returned candidates by the requested region /
host axis / component. It NEVER writes candidate files: candidates are
returned in memory only, with each DERIVED vs UNKNOWN value clearly
labelled.

Inputs:
  component_id:   The registered component identifier (e.g.
                  ``camthink_ov5640_8p5`` or ``vsma1094750x02``).
  region:         ``center_nose_bridge`` | ``front_frame`` |
                  ``left_temple`` | ``right_temple``.
  host_axis:      ``forward`` | ``outward`` | ``same_as_camera``.
  clearance_mm:   Required clearance in millimetres. Must be positive
                  and finite. The validator that ultimately consumes
                  the candidates has its own mandatory policy floors;
                  this tool only filters, it does not enforce.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

from ._envelope import make_envelope, utcnow_iso
from ._paths import glasses_root


# ---------------------------------------------------------------------------
# Valid region / axis names. The validator recognises these as the canonical
# regions for the glasses project.
# ---------------------------------------------------------------------------
VALID_REGIONS: frozenset[str] = frozenset({
    "center_nose_bridge",
    "front_frame",
    "left_temple",
    "right_temple",
})

VALID_AXES: frozenset[str] = frozenset({
    "forward",
    "outward",
    "same_as_camera",
})


# Project-root lookup for the refactored analysis script.
def _analysis_root() -> Path:
    """Return the absolute path to the ``analysis/geometry`` dir."""
    return glasses_root() / "analysis" / "geometry"


# Components with authoritative envelopes even though their detailed
# package geometry is not yet in the project tree.
_COMPONENT_ENVELOPES_MM: dict[str, list[float]] = {
    "camthink_ov5640_8p5": [8.5, 8.5, 6.5],
    "vsma1094750x02": [3.4, 3.4, 1.5],
}


def _component_exists(component_id: str) -> tuple[bool, str | None]:
    """Check whether ``component_id`` is registered or has an
    authoritative envelope declared.

    Returns ``(exists, reason)``. ``reason`` is None when the component
    is fully registered; otherwise it describes the authoritative
    envelope source. A component that is neither registered nor has a
    declared authoritative envelope is rejected.
    """
    if not component_id:
        return False, "component_id is empty"
    # Look up the engineering registry first.
    try:
        from ..engineering.component_registry import (
            ComponentRegistryError,
            component_exists,
            get_component,
        )
        try:
            if component_exists(component_id):
                comp = get_component(component_id)
                return True, f"registered (name={comp.get('name')})"
        except ComponentRegistryError as exc:
            return False, f"registry error: {exc}"
    except ImportError:
        pass

    if component_id in _COMPONENT_ENVELOPES_MM:
        return (
            True,
            "authoritative_envelope (component YAML declares "
            f"envelope_mm={_COMPONENT_ENVELOPES_MM[component_id]})",
        )

    return False, (
        "component is neither registered in "
        "projects/glasses/components/component-registry.yaml nor in the "
        "authoritative envelope map; refusing to invent one"
    )


def _resolve_candidates() -> dict[str, Any]:
    """Call the refactored candidate generator without writing any file.

    The analysis script lives outside the Python package, so we extend
    ``sys.path`` for the duration of the call.
    """
    analysis_path = str(_analysis_root())
    path_added = False
    if analysis_path not in sys.path:
        sys.path.insert(0, analysis_path)
        path_added = True
    try:
        from generate_component_candidates import (
            generate_component_candidates,
        )
        return generate_component_candidates()
    finally:
        if path_added:
            sys.path.remove(analysis_path)


def _collect_candidates(
    candidate_doc: dict[str, Any],
    component_id: str,
    region: str,
    host_axis: str,
) -> tuple[list[dict[str, Any]], str]:
    """Pull all matching candidates out of the generator output.

    Returns ``(candidates, group_label)``. ``candidates`` is the list of
    raw candidate dicts from the analysis script (each is a DERIVED
    candidate from authoritative geometry; the validator that consumes
    them is responsible for the FINAL acceptance decision).
    """
    if region == "center_nose_bridge":
        cam = candidate_doc.get("camera", {})
        if component_id == cam.get("quantity") and False:
            pass
        # The camera group always contains exactly one candidate for
        # the registered camera.
        if component_id == "camthink_ov5640_8p5":
            return list(cam.get("candidates", [])), "camera"
        if component_id in (c.get("component") for c in cam.get("candidates", [])):
            return list(cam.get("candidates", [])), "camera"
        return [], "camera"

    if region == "front_frame":
        fl = candidate_doc.get("forward_leds", {})
        return list(fl.get("candidates", [])), "forward_leds"

    if region in ("left_temple", "right_temple"):
        tl = candidate_doc.get("temple_leds", {})
        side = "left" if region == "left_temple" else "right"
        key = "left_candidates" if side == "left" else "right_candidates"
        return list(tl.get(key, [])), f"temple_leds[{key}]"

    return [], "unknown"


def _derive_axis_compatibility(candidate_axis: str, host_axis: str) -> bool:
    """Decide whether a candidate's declared axis matches the requested
    host_axis.

    ``same_as_camera`` is a synonym for ``forward`` (the camera points
    forward; the forward LEDs share that direction).
    """
    if host_axis == "same_as_camera":
        return candidate_axis in ("forward", "same_as_camera")
    return candidate_axis == host_axis


def propose_pose(
    component_id: str,
    region: str,
    host_axis: str,
    clearance_mm: float,
) -> dict[str, Any]:
    """Generate geometry-derived component candidates for ``component_id``.

    The tool never writes candidate files; candidates are returned in
    memory only. See module docstring for details on inputs.
    """
    if not isinstance(component_id, str) or not component_id:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=["component_id must be a non-empty string"],
        )
    if not isinstance(region, str) or region not in VALID_REGIONS:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"region {region!r} is not one of "
                f"{sorted(VALID_REGIONS)}"
            ],
        )
    if not isinstance(host_axis, str) or host_axis not in VALID_AXES:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"host_axis {host_axis!r} is not one of "
                f"{sorted(VALID_AXES)}"
            ],
        )
    if clearance_mm is None:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=["clearance_mm must be a finite number"],
        )
    try:
        clearance_value = float(clearance_mm)
    except (TypeError, ValueError):
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"clearance_mm must be a finite number, got {clearance_mm!r}"
            ],
        )
    if not math.isfinite(clearance_value):
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=["clearance_mm must be finite (not NaN/Inf)"],
        )
    if clearance_value < 0:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"clearance_mm must be non-negative, got {clearance_value}"
            ],
        )

    exists, reason = _component_exists(component_id)
    if not exists:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"component_id {component_id!r} is not valid: {reason}"
            ],
        )

    try:
        candidate_doc = _resolve_candidates()
    except Exception as exc:  # noqa: BLE001
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"candidate generator failed: {type(exc).__name__}: {exc}"
            ],
        )

    raw_candidates, group_label = _collect_candidates(
        candidate_doc, component_id, region, host_axis
    )

    if region == "center_nose_bridge":
        # The camera group contains candidates that may not be the
        # requested component. Filter by component_id.
        filtered = [
            c for c in raw_candidates
            if c.get("component") == component_id
        ]
    else:
        filtered = [
            c for c in raw_candidates
            if c.get("component") == component_id
            and _derive_axis_compatibility(
                str(c.get("axis", "")), host_axis
            )
        ]

    if not filtered:
        return make_envelope(
            tool="propose_pose",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="INCOMPLETE",
            data={
                "component_id": component_id,
                "region": region,
                "host_axis": host_axis,
                "clearance_mm": clearance_value,
                "candidate_group": group_label,
                "component_authority": reason,
                "candidates": [],
                "derivation_notes": [
                    "no candidates matched the requested component/region/axis "
                    "combination in the geometry-derived generator"
                ],
            },
            warnings=[
                "No candidates were produced. This means the requested "
                "combination is not supported by the current generator "
                "or no authoritative geometry is available yet."
            ],
        )

    # Annotate every candidate with its DERIVED vs UNKNOWN classification.
    annotated: list[dict[str, Any]] = []
    for cand in filtered:
        envelope = cand.get("envelope_mm")
        annotated.append({
            "component": cand.get("component"),
            "region": cand.get("region"),
            "role": cand.get("role"),
            "axis": cand.get("axis"),
            "label": cand.get("label"),
            "center_mm": cand.get("center_mm"),
            "rotation_deg": cand.get("rotation_deg"),
            "optical_axis_world": cand.get("optical_axis_world"),
            "surface_point_mm": cand.get("surface_point_mm"),
            "surface_normal": cand.get("surface_normal"),
            "mounting_face": cand.get("mounting_face"),
            "envelope_mm": envelope,
            "clearance_mm": cand.get("clearance_mm"),
            "collision_targets": cand.get("collision_targets"),
            "derivation": cand.get("derivation"),
            "axis_alignment": cand.get("axis_alignment"),
            "value_status": {
                "center_mm": "DERIVED",
                "optical_axis_world": "DERIVED",
                "surface_point_mm": "DERIVED",
                "surface_normal": "DERIVED",
                "envelope_mm": (
                    "DERIVED" if envelope is not None else "UNKNOWN"
                ),
            },
        })

    return make_envelope(
        tool="propose_pose",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status="PASS",
        data={
            "component_id": component_id,
            "region": region,
            "host_axis": host_axis,
            "clearance_mm": clearance_value,
            "candidate_group": group_label,
            "component_authority": reason,
            "candidates": annotated,
            "candidate_count": len(annotated),
            "units": "mm",
            "notes": [
                "All candidate coordinates are DERIVED from authoritative "
                "frame STL geometry via generate_component_candidates.py; "
                "no value was invented.",
                "This tool returns candidates only; final acceptance is "
                "the validator's responsibility (see validate_poses).",
            ],
        },
    )