"""Phase 3 optical-window validation MCP tool: ``validate_optical_window_system``.

Validates the IR optical-window YAML files:

* ``mechanical/interfaces/ir-optical-window-system.yaml``
* ``mechanical/interfaces/ir-optical-window-geometry.yaml``

The required fields listed in the directive are:

    diameter
    thickness
    recess diameter
    recess depth
    retention lip
    adhesive / sealing specification

For each required field, the tool reports whether the value is
authoritatively defined or still the ``TBD`` sentinel. The current
project state is expected to return ``INCOMPLETE`` because the optical
window dimensions are ``TBD``.

This tool never invents window dimensions or material; if any required
field is ``TBD`` the tool records it as a finding and returns
``INCOMPLETE`` (it cannot manufacture a PASS where there is no
authoritative dimension).

The output schema mirrors the directive:

    {
      status,
      placements,
      fields,
      tbd_fields,
      findings
    }
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ._envelope import make_envelope, utcnow_iso
from ._paths import PathSecurityError, glasses_root, safe_resolve


SYSTEM_REL = Path("mechanical/interfaces/ir-optical-window-system.yaml")
GEOMETRY_REL = Path("mechanical/interfaces/ir-optical-window-geometry.yaml")


def _is_tbd(value: Any) -> bool:
    """True iff ``value`` is missing, None, or the literal string ``"TBD"``.

    A missing key in the YAML is just as much a TBD as the explicit
    string sentinel: either way the value is not authoritatively
    defined.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().upper() == "TBD"
    return False


def _collect_tbd_fields(node: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            findings.extend(_collect_tbd_fields(value, path=child_path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{path}[{index}]"
            findings.extend(_collect_tbd_fields(value, path=child_path))
    elif _is_tbd(node):
        findings.append({"path": path, "value": "TBD"})
    return findings


def validate_optical_window_system() -> dict[str, Any]:
    """Validate the IR optical-window YAML files.

    Returns a structured envelope with the placements defined in the
    system YAML, the status of every required field (diameter,
    thickness, recess diameter, recess depth, retention lip,
    adhesive / sealing), and a list of ``TBD`` findings.

    Status is ``INCOMPLETE`` whenever any required field is ``TBD`` or
    the YAML cannot be parsed; ``PASS`` is reserved for the case where
    every required field is authoritatively defined.
    """
    started = utcnow_iso()
    errors: list[str] = []
    warnings: list[str] = []

    # Resolve both files.
    try:
        system_path = safe_resolve(SYSTEM_REL)
    except PathSecurityError as exc:
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )
    try:
        geometry_path = safe_resolve(GEOMETRY_REL)
    except PathSecurityError as exc:
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # Parse.
    try:
        system_doc = yaml.safe_load(system_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={
                "system_path": str(system_path.relative_to(glasses_root())),
            },
            errors=[f"Optical-window system YAML unreadable: {exc}"],
        )
    try:
        geometry_doc = yaml.safe_load(
            geometry_path.read_text(encoding="utf-8")
        )
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={
                "geometry_path": str(
                    geometry_path.relative_to(glasses_root())
                ),
            },
            errors=[f"Optical-window geometry YAML unreadable: {exc}"],
        )

    if not isinstance(system_doc, dict):
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                "ir-optical-window-system.yaml root must be a mapping; "
                f"got {type(system_doc).__name__}."
            ],
        )
    if not isinstance(geometry_doc, dict):
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                "ir-optical-window-geometry.yaml root must be a mapping; "
                f"got {type(geometry_doc).__name__}."
            ],
        )

    interface = system_doc.get("interface", {}) or {}
    if not isinstance(interface, dict):
        return make_envelope(
            tool="validate_optical_window_system",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=["interface section must be a mapping."],
        )

    mechanical = interface.get("mechanical_interface", {}) or {}
    if not isinstance(mechanical, dict):
        mechanical = {}

    recess = mechanical.get("recess", {}) or {}
    if not isinstance(recess, dict):
        recess = {}

    manufacturing = interface.get("manufacturing", {}) or {}
    if not isinstance(manufacturing, dict):
        manufacturing = {}

    construction = geometry_doc.get("construction", {}) or {}
    if not isinstance(construction, dict):
        construction = {}
    parameters = construction.get("parameters", {}) or {}
    if not isinstance(parameters, dict):
        parameters = {}

    # Required fields.
    required_fields: dict[str, Any] = {
        "diameter_mm": mechanical.get("diameter_mm"),
        "thickness_mm": mechanical.get("thickness_mm"),
        "recess_diameter_mm": recess.get("diameter_mm"),
        "recess_depth_mm": recess.get("depth_mm"),
        "retention_lip_width_mm": parameters.get("retention_lip_width_mm"),
        "adhesive": manufacturing.get("adhesive"),
    }

    fields: list[dict[str, Any]] = []
    tbd_fields: list[dict[str, str]] = []
    for name, value in required_fields.items():
        defined = not _is_tbd(value)
        status_str = "DEFINED" if defined else "TBD"
        fields.append(
            {
                "name": name,
                "value": "TBD" if not defined else value,
                "status": status_str,
            }
        )
        if not defined:
            tbd_fields.append({"name": name, "value": "TBD"})

    # Placements.
    placements = interface.get("placements", {}) or {}
    placements_list: list[dict[str, Any]] = []
    if isinstance(placements, dict):
        for name, placement in placements.items():
            if isinstance(placement, dict):
                placements_list.append({"id": name, **placement})
    elif isinstance(placements, list):
        for index, placement in enumerate(placements):
            if isinstance(placement, dict):
                placements_list.append({"id": index, **placement})

    # Collect every TBD leaf in the YAMLs.
    all_tbds: list[dict[str, str]] = []
    all_tbds.extend(
        _collect_tbd_fields(system_doc, path="ir_optical_window_system")
    )
    all_tbds.extend(
        _collect_tbd_fields(geometry_doc, path="ir_optical_window_geometry")
    )

    findings: list[str] = []
    status = "PASS"

    if tbd_fields:
        status = "INCOMPLETE"
        tbd_names = ", ".join(t["name"] for t in tbd_fields)
        findings.append(
            f"Required optical-window field(s) are TBD: {tbd_names}. "
            "Window dimensions and adhesive/sealing spec must be "
            "authoritatively defined before this design can be PASS."
        )
    if len(placements_list) != 6:
        status = "INCOMPLETE"
        findings.append(
            f"Expected 6 optical-window placements, found "
            f"{len(placements_list)}."
        )

    if status == "PASS" and not all_tbds:
        # Sanity check: any leaf marked TBD anywhere in the YAMLs would
        # be caught by ``tbd_fields`` above; this branch only runs when
        # every required field is defined.
        pass

    return make_envelope(
        tool="validate_optical_window_system",
        started_at_iso=started,
        duration_ms=0,
        status=status,
        data={
            "system_path": str(system_path.relative_to(glasses_root())),
            "geometry_path": str(
                geometry_path.relative_to(glasses_root())
            ),
            "placements": placements_list,
            "placement_count": len(placements_list),
            "fields": fields,
            "tbd_fields": tbd_fields,
            "all_tbd_fields": all_tbds,
            "findings": findings,
        },
        warnings=warnings,
        errors=errors,
    )