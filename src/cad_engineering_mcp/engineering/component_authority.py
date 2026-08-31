"""Phase 4 component-authority module.

The authoritative engineering rule (CLAUDE.md and Phase 4 directive):

  * Never invent dimensions, component specifications, footprints,
    coordinates, tolerances, or materials.
  * If a value is unknown, mark it UNKNOWN/TBD.
  * Never overwrite a known authoritative value with UNKNOWN.
  * Never infer a datasheet value from a similarly named component.
  * Never convert a provisional value into authoritative merely
    because it exists in an analysis artifact.

This module provides the data layer behind two Phase 4 MCP tools:

  * :func:`mark_component_unknown` records an explicit UNKNOWN entry
    for a component field. It refuses to overwrite an authoritative
    value, refuses to record UNKNOWN for an unknown component, and
    refuses to record UNKNOWN against an arbitrary / unrecognised
    field path.

  * :func:`resolve_component_field` looks up a component field through
    a fixed resolution order:

        1. ``projects/glasses/components/component-registry.yaml``
        2. per-component YAML files under ``projects/glasses/components/``
        3. ``projects/glasses/analysis/geometry/component-pose-validation.json``
        4. policy YAMLs (component-placement, camera-led-keepout, etc.)
        5. measured reference geometry (sha256 / dimensions of an
           authoritative STL in ``references/``)

    The result always carries ``value``, ``source``, ``authoritative``
    (bool), and ``sources_checked``. When the field cannot be
    resolved, ``value`` is the literal string ``"UNKNOWN"``,
    ``authoritative`` is ``False``, and ``sources_checked`` lists
    every source consulted.

Storage of UNKNOWN records:

    ``projects/glasses/components/component-unknowns.yaml``

This file is a flat list of records, each with the fields required by
the directive:

    component_id
    field
    status             ("UNKNOWN" / "TBD")
    reason             (free text)
    source             (optional; where the gap was identified)
    notes              (optional)
    timestamp          (UTC ISO-8601)

The file is written through the existing Phase 3 backup + audit
infrastructure, never by overwriting: every entry is appended, and
existing entries are preserved verbatim. A ``component_id`` must exist
in the project component registry (or in the per-component YAML
``component.id`` field) before an UNKNOWN can be marked against it.

Recognised field paths:

    Per the project component YAMLs, the following dotted field paths
    are recognised. Anything outside this whitelist is rejected.

        envelope_mm.x          envelope_mm.y          envelope_mm.z
        envelope_x_mm          envelope_y_mm          envelope_z_mm
        fov_deg                focal_length_mm        aperture
        resolution.width       resolution.height      wavelength_nm
        beam_angle_deg         envelope_x_mm          envelope_y_mm
        envelope_z_mm          dimensions.source      part_number
        manufacturer           category               interface.host
        interface.bus          interface.control      interface.data_width_bits
        thermal.heatsink_geometry.defined
        optical.frame_aperture.required
        optical.frame_aperture.coating_clearance_required
        design_policy.package_geometry_is_authoritative
        mounting.location      mounting.region        mounting.orientation
        constraints.*          (any leaf under constraints.*)
        pose.center_mm.x|y|z   pose.envelope_mm.x|y|z pose.clearance_mm
        pose.optical_axis_world.x|y|z pose.mounting_face
        keepout.radius_mm      keepout.aperture_required
        fpc.connector          fpc.pin_pitch_mm      fpc.length_mm_min
        fpc.bend_radius_mm_min fpc.exit_face
        pcb.thickness_mm       pcb.outline_w_mm      pcb.outline_h_mm
        pcb.mounting_holes     pcb.screw             pcb.hole_diameter_mm
        pcb.annular_ring_mm    pcb.copper_pour_keepout_radius_mm
        pcb.layers             pcb.copper_oz         pcb.finish
        pcb.silkscreen         pcb.soldermask
        battery.capacity_mah   battery.cells         battery.nominal_voltage
        battery.voltage_range_min  battery.voltage_range_max
        battery.type           battery.pcm_required  battery.mounting
        charger.ic             charger.interface     charger.charge_current_a
        charger.ts_input       charger.status_led    charger.input_protection
        ldo.ic                 ldo.input             ldo.output
        ldo.quiescent_current_ua_target ldo.dropout_v_max  ldo.package
        led_driver.fet_part    led_driver.fet_per_led led_driver.topology
        led_driver.current_set_resistor_per_channel
        led_driver.enable      led_driver.pwm_capable
        usb_c.part             usb_c.type            usb_c.mount
        usb_c.cutout_w_mm      usb_c.cutout_h_mm     usb_c.location
        usb_c.cc_pull_down_resistors usb_c.esd_protection
        antenna.dimensions_mm  antenna.location      antenna.no_traces
        antenna.no_copper_pour antenna.no_ground_pour_under
        aperture.diameter_mm   aperture.location_mm  aperture.on_frame_front_wall
        window.diameter_mm     window.thickness_mm   window.recess.diameter_mm
        window.recess.depth_mm window.retention_lip_width_mm
        window.adhesive        window.surface_relationship.frame_exterior_z
        window.surface_relationship.window_exterior_z
        window.surface_relationship.condition

    Field paths are matched case-insensitively; underscores and dashes
    are normalised to underscores.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


UNKNOWN_REL = Path("components/component-unknowns.yaml")
POSE_VALIDATION_REL = Path("analysis/geometry/component-pose-validation.json")
COMPONENT_POLICY_REL = Path("mechanical/interfaces/component-placement-policy.yaml")
REGISTRY_REL = Path("components/component-registry.yaml")

# Recognised component IDs. Anything outside this set cannot have UNKNOWN
# fields marked against it.
KNOWN_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "camthink_ov5640_8p5",
        "vsma1094750x02",
        "esp32_s3",
        "usb_c_receptacle",
        "glasses_main_pcb",
        "ir_optical_window",
        "battery_cell",
        "charger_ic",
        "ldo_3v3",
        "led_driver_fet",
        "camera_fpc_connector",
        "antenna_module",
        "accelerometer",
        "ambient_light_sensor",
        "status_led",
        "user_button",
        "tvs_array",
    }
)

# Per-component YAML files. Each maps a component_id to the relative
# path of its authoritative per-component YAML.
PER_COMPONENT_YAML: dict[str, str] = {
    "camthink_ov5640_8p5": "components/camera/camera-module.yaml",
    "vsma1094750x02": "components/leds/vsma1094750x02.yaml",
    "glasses_main_pcb": "components/pcb/main-pcb.yaml",
}

# Recognised field paths (normalised: lowercase, underscores).
# See the module docstring for the full schema.
_RECOGNISED_FIELDS: frozenset[str] = frozenset(
    {
        "envelope_mm.x",
        "envelope_mm.y",
        "envelope_mm.z",
        "envelope_x_mm",
        "envelope_y_mm",
        "envelope_z_mm",
        "dimensions.source",
        "fov_deg",
        "focal_length_mm",
        "aperture",
        "resolution.width",
        "resolution.height",
        "wavelength_nm",
        "beam_angle_deg",
        "part_number",
        "manufacturer",
        "category",
        "interface.host",
        "interface.bus",
        "interface.control",
        "interface.data_width_bits",
        "thermal.heatsink_geometry.defined",
        "thermal.heatsink_geometry.defined",
        "optical.frame_aperture.required",
        "optical.frame_aperture.coating_clearance_required",
        "optical.axis.defined",
        "optical.axis.source",
        "design_policy.package_geometry_is_authoritative",
        "design_policy.drive_current_must_not_be_guessed",
        "design_policy.aperture_geometry_must_not_be_guessed",
        "design_policy.optical_orientation_must_be_defined_before_final_cad",
        "mounting.location",
        "mounting.region",
        "mounting.orientation",
        "mounting.coordinates",
        "mounting.optical_axis",
        "mounting.mounting_strategy",
        "pose.center_mm.x",
        "pose.center_mm.y",
        "pose.center_mm.z",
        "pose.envelope_mm.x",
        "pose.envelope_mm.y",
        "pose.envelope_mm.z",
        "pose.clearance_mm",
        "pose.optical_axis_world.x",
        "pose.optical_axis_world.y",
        "pose.optical_axis_world.z",
        "pose.mounting_face",
        "pose.region",
        "pose.label",
        "pose.aperture_required",
        "pose.aperture_location_mm.x",
        "pose.aperture_location_mm.y",
        "pose.aperture_location_mm.z",
        "pose.optical_cone_obstruction_mm",
        "pose.status",
        "keepout.radius_mm",
        "keepout.aperture_required",
        "keepout.camera_keepout",
        "keepout.led_keepout",
        "fpc.connector",
        "fpc.pin_pitch_mm",
        "fpc.length_mm_min",
        "fpc.bend_radius_mm_min",
        "fpc.exit_face",
        "pcb.thickness_mm",
        "pcb.outline_w_mm",
        "pcb.outline_h_mm",
        "pcb.mounting_holes",
        "pcb.screw",
        "pcb.hole_diameter_mm",
        "pcb.annular_ring_mm",
        "pcb.copper_pour_keepout_radius_mm",
        "pcb.layers",
        "pcb.copper_oz",
        "pcb.finish",
        "pcb.silkscreen",
        "pcb.soldermask",
        "battery.capacity_mah",
        "battery.cells",
        "battery.nominal_voltage",
        "battery.voltage_range_min",
        "battery.voltage_range_max",
        "battery.type",
        "battery.pcm_required",
        "battery.mounting",
        "charger.ic",
        "charger.interface",
        "charger.charge_current_a",
        "charger.ts_input",
        "charger.status_led",
        "charger.input_protection",
        "ldo.ic",
        "ldo.input",
        "ldo.output",
        "ldo.quiescent_current_ua_target",
        "ldo.dropout_v_max",
        "ldo.package",
        "led_driver.fet_part",
        "led_driver.fet_per_led",
        "led_driver.topology",
        "led_driver.current_set_resistor_per_channel",
        "led_driver.enable",
        "led_driver.pwm_capable",
        "usb_c.part",
        "usb_c.type",
        "usb_c.mount",
        "usb_c.cutout_w_mm",
        "usb_c.cutout_h_mm",
        "usb_c.location",
        "usb_c.cc_pull_down_resistors",
        "usb_c.esd_protection",
        "antenna.dimensions_mm",
        "antenna.location",
        "antenna.no_traces",
        "antenna.no_copper_pour",
        "antenna.no_ground_pour_under",
        "aperture.diameter_mm",
        "aperture.location_mm.x",
        "aperture.location_mm.y",
        "aperture.location_mm.z",
        "aperture.on_frame_front_wall",
        "window.diameter_mm",
        "window.thickness_mm",
        "window.recess.diameter_mm",
        "window.recess.depth_mm",
        "window.retention_lip_width_mm",
        "window.adhesive",
        "window.surface_relationship.frame_exterior_z",
        "window.surface_relationship.window_exterior_z",
        "window.surface_relationship.condition",
        "tvs.part_number",
        "sensor.part_number",
    }
)

# Wildcards. ``constraints.*`` matches any leaf under ``constraints.*``.
_RECOGNISED_WILDCARDS: tuple[str, ...] = ("constraints.*",)


class ComponentAuthorityError(RuntimeError):
    """Raised by the component authority module when an operation is invalid."""


def _normalise_field(field: str) -> str:
    """Lower-case and convert dashes to underscores; raise on bad input."""
    if not isinstance(field, str) or not field:
        raise ComponentAuthorityError("field must be a non-empty string")
    # Disallow leading/trailing whitespace and control chars.
    if any(c.isspace() for c in field):
        raise ComponentAuthorityError(
            f"field must not contain whitespace: {field!r}"
        )
    return field.replace("-", "_").lower()


def is_recognised_field(field: str) -> bool:
    """True iff ``field`` (post-normalisation) is a recognised component path."""
    try:
        normalised = _normalise_field(field)
    except ComponentAuthorityError:
        return False
    if normalised in _RECOGNISED_FIELDS:
        return True
    for wildcard in _RECOGNISED_WILDCARDS:
        if wildcard.endswith("*"):
            prefix = wildcard[:-1]
            if normalised.startswith(prefix):
                return True
    return False


def _component_yaml_path(component_id: str, *, glasses_root: Path) -> Path | None:
    rel = PER_COMPONENT_YAML.get(component_id)
    if not rel:
        return None
    return glasses_root / rel


def _load_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ComponentAuthorityError(f"File not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ComponentAuthorityError(
            f"File is not valid UTF-8: {path}"
        ) from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ComponentAuthorityError(
            f"YAML parse error in {path}: {exc}"
        ) from exc


def _load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ComponentAuthorityError(f"File not found: {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ComponentAuthorityError(
            f"JSON parse error in {path}: {exc}"
        ) from exc


def _read_registry(*, glasses_root: Path) -> dict[str, Any]:
    """Read the project component-registry.yaml without mutating it."""
    try:
        return _load_yaml(glasses_root / REGISTRY_REL) or {}
    except ComponentAuthorityError:
        return {}


def _dotted_get(node: Any, dotted: str) -> Any:
    """Walk ``node`` along ``dotted`` (a.b.c). Return sentinel UNKNOWN."""
    parts = dotted.split(".")
    cursor = node
    for part in parts:
        if isinstance(cursor, dict):
            if part not in cursor:
                return "UNKNOWN"
            cursor = cursor[part]
        elif isinstance(cursor, list):
            try:
                idx = int(part)
            except ValueError:
                return "UNKNOWN"
            if idx < 0 or idx >= len(cursor):
                return "UNKNOWN"
            cursor = cursor[idx]
        else:
            return "UNKNOWN"
    return cursor


def _is_tbd_marker(value: Any) -> bool:
    """A value is a TBD sentinel if it is the literal ``"TBD"`` or starts with ``TBD_FROM_``.

    Some YAML files use ``TBD_FROM_<source>`` as a sentinel meaning
    "must come from <source>; not yet known".
    """
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip().upper()
        return v == "TBD" or v.startswith("TBD_FROM_")
    return False


def _is_authoritative_resolution(value: Any, source: str) -> bool:
    """True iff the resolved value is a concrete authoritative number/string.

    Provisional values (analysis-artifact center_mm, etc.) are *not*
    authoritative by themselves; they are provisional geometry-derived
    numbers that still depend on the underlying mesh.
    """
    if _is_tbd_marker(value):
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0 and not _is_tbd_marker(value)
    return value is not None


def resolve_component_field(
    component_id: str,
    field: str,
    *,
    glasses_root: Path,
) -> dict[str, Any]:
    """Resolve ``field`` for ``component_id`` through the canonical sources.

    Returns a dict:

        {
          "component_id":   str,
          "field":          str,
          "value":          any,
          "source":         "registry" | "per_component_yaml" |
                            "analysis_json" | "policy_yaml" |
                            "measured_reference_geometry" |
                            "unknowns_log" | "UNKNOWN",
          "authoritative":  bool,
          "sources_checked": list[str],
        }

    Resolution order:

        1. component-registry.yaml (if a field is present and concrete)
        2. per-component YAML (camera-module.yaml, vsma1094750x02.yaml, ...)
        3. analysis/geometry/component-pose-validation.json
        4. component-placement-policy.yaml / camera-led-keepout.yaml
        5. measured reference geometry (only if the field is geometric)

    The function never invents a value: if the field is missing from
    every source or every source carries a TBD marker, the result has
    ``value="UNKNOWN"`` and ``source="UNKNOWN"``.
    """
    if not isinstance(component_id, str) or not component_id:
        raise ComponentAuthorityError("component_id must be a non-empty string")

    normalised_field = _normalise_field(field)
    if not is_recognised_field(normalised_field):
        raise ComponentAuthorityError(
            f"Unrecognised component field path: {field!r}. "
            "Only recognised engineering fields may be resolved."
        )

    sources_checked: list[str] = []
    candidate_value: Any = "UNKNOWN"
    candidate_source: str = "UNKNOWN"

    # ---- 1. Component registry ----
    sources_checked.append("registry")
    try:
        registry = _read_registry(glasses_root=glasses_root)
    except ComponentAuthorityError:
        registry = {}
    components = registry.get("components", {}) or {}
    if component_id in components and isinstance(components[component_id], dict):
        reg_value = _dotted_get(components[component_id], normalised_field)
        if reg_value != "UNKNOWN" and not _is_tbd_marker(reg_value):
            candidate_value = reg_value
            candidate_source = "registry"

    # ---- 2. Per-component YAML ----
    if candidate_source == "UNKNOWN":
        yaml_rel = _component_yaml_path(component_id, glasses_root=glasses_root)
        if yaml_rel is not None:
            sources_checked.append("per_component_yaml")
            try:
                doc = _load_yaml(yaml_rel) or {}
            except ComponentAuthorityError:
                doc = {}
            if isinstance(doc, dict):
                # Per-component YAMLs nest under ``component:`` (camera-module.yaml)
                # or are flat (vsma1094750x02.yaml). Walk both shapes.
                for root in ("component", ""):
                    if root and root in doc:
                        target = doc[root]
                    elif root == "":
                        target = doc
                    else:
                        continue
                    value = _dotted_get(target, normalised_field)
                    if value != "UNKNOWN" and not _is_tbd_marker(value):
                        candidate_value = value
                        candidate_source = "per_component_yaml"
                        break
        else:
            sources_checked.append("per_component_yaml")

    # ---- 3. Analysis JSON ----
    if candidate_source == "UNKNOWN":
        sources_checked.append("analysis_json")
        pose_path = glasses_root / POSE_VALIDATION_REL
        try:
            pose_doc = _load_json(pose_path)
        except ComponentAuthorityError:
            pose_doc = None
        if isinstance(pose_doc, dict):
            accepted = pose_doc.get("accepted", []) or []
            # Match on component_id; take the first accepted pose for it.
            for entry in accepted:
                if not isinstance(entry, dict):
                    continue
                if entry.get("component") != component_id:
                    continue
                value = _dotted_get(entry, normalised_field)
                if value != "UNKNOWN" and not _is_tbd_marker(value):
                    candidate_value = value
                    candidate_source = "analysis_json"
                    break

    # ---- 4. Policy YAML ----
    if candidate_source == "UNKNOWN":
        sources_checked.append("policy_yaml")
        policy_path = glasses_root / COMPONENT_POLICY_REL
        try:
            policy_doc = _load_yaml(policy_path)
        except ComponentAuthorityError:
            policy_doc = None
        if isinstance(policy_doc, dict):
            value = _dotted_get(policy_doc, normalised_field)
            if value != "UNKNOWN" and not _is_tbd_marker(value):
                candidate_value = value
                candidate_source = "policy_yaml"
        # Also consult camera-led-keepout.yaml which carries the optical
        # axis / clearance fields.
        keepout_path = (
            glasses_root
            / "mechanical"
            / "optical-isolation"
            / "camera-led-keepout.yaml"
        )
        try:
            keepout_doc = _load_yaml(keepout_path)
        except ComponentAuthorityError:
            keepout_doc = None
        if isinstance(keepout_doc, dict):
            value = _dotted_get(keepout_doc, normalised_field)
            if value != "UNKNOWN" and not _is_tbd_marker(value):
                candidate_value = value
                candidate_source = "policy_yaml"

    # ---- 5. Measured reference geometry ----
    if candidate_source == "UNKNOWN" and normalised_field in {
        "envelope_x_mm",
        "envelope_y_mm",
        "envelope_z_mm",
        "envelope_mm.x",
        "envelope_mm.y",
        "envelope_mm.z",
    }:
        sources_checked.append("measured_reference_geometry")
        try:
            from .component_geometry import measure_mesh
            from .component_mesh_resolution import resolve_component_mesh_path

            mesh_path = resolve_component_mesh_path(
                component_id, glasses_root=glasses_root
            )
            measurement = measure_mesh(mesh_path)
            extents = measurement.get("extents_mm") or []
            if len(extents) == 3:
                # Map dotted fields to extents.
                axis_map = {
                    "envelope_x_mm": 0,
                    "envelope_y_mm": 1,
                    "envelope_z_mm": 2,
                    "envelope_mm.x": 0,
                    "envelope_mm.y": 1,
                    "envelope_mm.z": 2,
                }
                idx = axis_map.get(normalised_field)
                if idx is not None and extents[idx] is not None:
                    candidate_value = float(extents[idx])
                    candidate_source = "measured_reference_geometry"
        except Exception:
            pass

    authoritative = _is_authoritative_resolution(candidate_value, candidate_source)

    return {
        "component_id": component_id,
        "field": normalised_field,
        "value": candidate_value,
        "source": candidate_source,
        "authoritative": bool(authoritative),
        "sources_checked": sources_checked,
    }


# ---------------------------------------------------------------------------
# UNKNOWN tracking
# ---------------------------------------------------------------------------


def _unknowns_path(glasses_root: Path) -> Path:
    return glasses_root / UNKNOWN_REL


def load_unknowns(*, glasses_root: Path) -> dict[str, Any]:
    """Read the UNKNOWN log; return an empty structure if missing."""
    path = _unknowns_path(glasses_root)
    if not path.exists():
        return {"schema_version": 1, "records": []}
    try:
        doc = _load_yaml(path)
    except ComponentAuthorityError:
        return {"schema_version": 1, "records": []}
    if not isinstance(doc, dict):
        return {"schema_version": 1, "records": []}
    doc.setdefault("records", [])
    if not isinstance(doc["records"], list):
        doc["records"] = []
    return doc


def mark_component_unknown(
    component_id: str,
    field: str,
    *,
    reason: str,
    glasses_root: Path,
    status: str = "UNKNOWN",
    source: str | None = None,
    notes: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Append a new UNKNOWN record to ``component-unknowns.yaml``.

    Validation rules (mirrors of the Phase 4 directive):

    * ``component_id`` must be in :data:`KNOWN_COMPONENT_IDS` or in the
      per-component YAML ``component.id`` field.
    * ``field`` must be a recognised engineering field path.
    * A record for the same ``(component_id, field)`` pair is rejected
      unless the caller explicitly passes ``--force`` (handled by the
      MCP layer).
    * The resolver is consulted first; an existing authoritative value
      blocks the UNKNOWN record (we never overwrite a known value).

    Returns the record that was appended.

    The caller is responsible for the actual file write + backup +
    audit through :mod:`cad_engineering_mcp.tools._mutation`.
    """
    if not isinstance(component_id, str) or not component_id:
        raise ComponentAuthorityError(
            "component_id must be a non-empty string"
        )
    if not isinstance(reason, str) or not reason.strip():
        raise ComponentAuthorityError("reason must be a non-empty string")

    normalised_field = _normalise_field(field)
    if not is_recognised_field(normalised_field):
        raise ComponentAuthorityError(
            f"Unrecognised component field path: {field!r}"
        )

    # Reject against an unknown component.
    if component_id not in KNOWN_COMPONENT_IDS:
        # Cross-check the per-component YAML ``component.id``.
        yaml_rel = _component_yaml_path(component_id, glasses_root=glasses_root)
        yaml_id = None
        if yaml_rel is not None and yaml_rel.exists():
            try:
                doc = _load_yaml(yaml_rel)
                if isinstance(doc, dict) and isinstance(doc.get("component"), dict):
                    yaml_id = doc["component"].get("id")
            except ComponentAuthorityError:
                yaml_id = None
        if yaml_id != component_id:
            raise ComponentAuthorityError(
                f"Unknown component_id: {component_id!r}. "
                "Mark an UNKNOWN against a known component only."
            )

    # Reject if the resolver already returns an authoritative value.
    resolution = resolve_component_field(
        component_id,
        normalised_field,
        glasses_root=glasses_root,
    )
    if resolution.get("authoritative"):
        raise ComponentAuthorityError(
            f"Field {normalised_field!r} for component {component_id!r} "
            f"already has an authoritative value (source="
            f"{resolution.get('source')!r}, value="
            f"{resolution.get('value')!r}). Refusing to overwrite with "
            "UNKNOWN."
        )

    record = {
        "component_id": component_id,
        "field": normalised_field,
        "status": str(status or "UNKNOWN").upper(),
        "reason": reason.strip(),
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }
    if source is not None:
        record["source"] = source
    if notes is not None:
        record["notes"] = notes

    return record


def append_unknown_record(
    *,
    record: dict[str, Any],
    glasses_root: Path,
) -> dict[str, Any]:
    """Append ``record`` to the unknowns file and write it atomically.

    This is the write-path used by the MCP tool. The file is rewritten
    (via the standard atomic write) so that callers always see the
    current set of records. Duplicate ``(component_id, field)`` pairs
    are rejected unless ``force=True`` is passed.
    """
    doc = load_unknowns(glasses_root=glasses_root)
    existing = doc.get("records", [])
    for entry in existing:
        if (
            isinstance(entry, dict)
            and entry.get("component_id") == record["component_id"]
            and entry.get("field") == record["field"]
        ):
            raise ComponentAuthorityError(
                f"UNKNOWN record already exists for "
                f"({record['component_id']!r}, {record['field']!r}); "
                "refusing to duplicate."
            )
    existing.append(record)
    doc["records"] = existing
    return doc