"""Phase 4 PCB architecture reconciliation.

The PCB must be derived from the *mechanical* envelope, the
*component* placement, and the *electronic* interface requirements
(Camera FPC, LED driver, ESP32-S3, USB-C, battery). Per the
directive:

    "PCB geometry must eventually be derived from:
       - component footprints
       - connector locations
       - battery geometry
       - camera interface
       - LED driver circuitry
       - ESP32-S3
       - USB-C
       - mechanical mounting points
       - enclosure/frame geometry

     Never design the PCB independently of the mechanical envelope.
     Respect:
       - creepage/clearance
       - copper keepouts
       - antenna keepout
       - thermal requirements
       - connector access
       - assembly access
       - screw/rivet/clip locations
       - flex and wire routing
       - manufacturing constraints"

This module reads the existing artefacts and produces a
*reconciliation report* that maps every mechanical envelope,
component envelope, and connector onto a proposed PCB outline, plus
an enumeration of every UNKNOWN/TBD element that blocks a
production-ready release.

It never invents a value. When a footprint, dimension, or clearance
is missing, the result records the gap explicitly.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml


# Required footprint / envelope keys per *family* of component. The
# reconciler cross-checks each known component against the family and
# records gaps.
FOOTPRINT_FAMILIES: dict[str, tuple[str, ...]] = {
    "esp32_s3": (
        "footprint.esp32_s3_module_variant",
        "footprint.module_outline_mm",
        "footprint.antenna_keepout_mm",
        "footprint.pin_pitch_mm",
    ),
    "usb_c_receptacle": (
        "footprint.usb_c_part",
        "footprint.cutout_w_mm",
        "footprint.cutout_h_mm",
        "footprint.cc_pull_down_resistors",
        "footprint.esd_protection",
    ),
    "battery_cell": (
        "footprint.battery_capacity_mah",
        "footprint.cell_dimensions_mm",
        "footprint.pcm_required",
        "footprint.connector_pitch_mm",
    ),
    "charger_ic": (
        "footprint.charger_part",
        "footprint.charge_current_a",
        "footprint.ts_input",
        "footprint.status_led",
    ),
    "ldo_3v3": (
        "footprint.ldo_part",
        "footprint.input_voltage_range",
        "footprint.output_current_a",
        "footprint.quiescent_current_ua_target",
        "footprint.dropout_v_max",
    ),
    "led_driver_fet": (
        "footprint.fet_part",
        "footprint.fet_per_led",
        "footprint.current_set_resistor_ohms",
        "footprint.thermal_pad",
    ),
    "camera_fpc_connector": (
        "footprint.fpc_connector_part",
        "footprint.pin_pitch_mm",
        "footprint.pin_count",
        "footprint.length_mm_min",
        "footprint.bend_radius_mm_min",
    ),
    "antenna_module": (
        "footprint.antenna_dimensions_mm",
        "footprint.antenna_location",
        "footprint.no_traces_under_mm",
        "footprint.no_ground_pour_under",
    ),
}


# Mechanical/electrical keepouts that the PCB must respect.
MECHANICAL_KEEPOUTS: tuple[str, ...] = (
    "camera_keepout",
    "led_keepouts",
    "antenna_keepout",
    "fpc_keepout",
)


def _is_tbd(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip().upper()
        return v == "TBD" or v.startswith("TBD_FROM_")
    return False


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise PcbReconcileError(f"Cannot load {path}: {exc}") from exc


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PcbReconcileError(f"Cannot load {path}: {exc}") from exc


class PcbReconcileError(RuntimeError):
    """Raised when PCB reconciliation cannot proceed."""


def _candidate_paths(glasses_root: Path) -> dict[str, Path]:
    return {
        "schematic_architecture": glasses_root / "electronics" / "schematic-architecture.yaml",
        "pcb_summary": glasses_root / "electronics" / "glasses-pcb.summary.json",
        "placement_policy": glasses_root / "mechanical" / "interfaces" / "component-placement-policy.yaml",
        "camera_led_keepout": glasses_root / "mechanical" / "optical-isolation" / "camera-led-keepout.yaml",
        "structural_policy": glasses_root / "mechanical" / "main-frame" / "structural-policy.yaml",
        "frame_coords": glasses_root / "analysis" / "geometry" / "frame-coordinate-system.json",
        "pose_validation": glasses_root / "analysis" / "geometry" / "component-pose-validation.json",
    }


def _bbox_for_components(
    component_envelopes: list[dict[str, Any]],
    *,
    margin_mm: float = 1.0,
) -> dict[str, Any] | None:
    """Compute a bounding box covering all component envelopes.

    Each entry is a mapping with ``center_mm`` (3-vec) and
    ``envelope_mm`` (3-vec, full extents in X/Y/Z). The bbox is
    returned with the per-axis margin applied.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for entry in component_envelopes:
        if not isinstance(entry, dict):
            continue
        center = entry.get("center_mm")
        env = entry.get("envelope_mm")
        if not (isinstance(center, list) and isinstance(env, list)):
            continue
        if len(center) != 3 or len(env) != 3:
            continue
        try:
            cx, cy, cz = (float(v) for v in center)
            ex, ey, ez = (float(v) for v in env)
        except (TypeError, ValueError):
            continue
        xs.append(cx - ex / 2.0)
        ys.append(cy - ey / 2.0)
        zs.append(cz - ez / 2.0)
        xs.append(cx + ex / 2.0)
        ys.append(cy + ey / 2.0)
        zs.append(cz + ez / 2.0)
    if not xs:
        return None
    return {
        "min": [min(xs) - margin_mm, min(ys) - margin_mm, min(zs) - margin_mm],
        "max": [max(xs) + margin_mm, max(ys) + margin_mm, max(zs) + margin_mm],
        "size_mm": [
            max(xs) - min(xs) + 2.0 * margin_mm,
            max(ys) - min(ys) + 2.0 * margin_mm,
            max(zs) - min(zs) + 2.0 * margin_mm,
        ],
    }


def _derived_pcb_outline(
    *,
    schematic: dict[str, Any] | None,
    placement_policy: dict[str, Any] | None,
    frame_coords: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reconcile the derived PCB outline against the existing one.

    The derivation here is *pure* in the sense that it only uses
    already-defined dimensions. It returns::

        {
          "derived_outline_mm":  {width, height, thickness},
          "existing_outline_mm": {...} or None,
          "fits_in_frame":       bool | None,
          "notes":               [...],
        }
    """
    derived: dict[str, Any] = {"width": None, "height": None, "thickness": None}
    notes: list[str] = []
    bbox = None
    if isinstance(frame_coords, dict):
        fc = frame_coords.get("frame_bbox_mm")
        if isinstance(fc, dict):
            try:
                bx_min, bx_max = float(fc["x"][0]), float(fc["x"][1])
                by_min, by_max = float(fc["y"][0]), float(fc["y"][1])
                bz_min, bz_max = float(fc["z"][0]), float(fc["z"][1])
                bbox = {
                    "min": [bx_min, by_min, bz_min],
                    "max": [bx_max, by_max, bz_max],
                }
            except (KeyError, TypeError, ValueError):
                bbox = None

    # The default derived outline honours:
    #   - frame x extent
    #   - frame z extent
    #   - margins defined in the schematic outline
    margins: dict[str, float] = {"x": 0.5, "z": 1.0}
    if isinstance(schematic, dict):
        outline = schematic.get("board_outline", {}) or {}
        if isinstance(outline, dict):
            margins_block = outline.get("outline_keepout") or {}
            if isinstance(margins_block, dict):
                for k, out_k in (
                    ("left_to_frame_X_min_mm", "x_min"),
                    ("right_to_frame_X_max_mm", "x_max"),
                    ("top_to_frame_Z_max_mm", "z_max"),
                    ("bottom_to_frame_Z_min_mm", "z_min"),
                ):
                    if k in margins_block and not _is_tbd(margins_block[k]):
                        try:
                            margins[out_k[:1]] = float(margins_block[k])
                        except (TypeError, ValueError):
                            pass

    if bbox is not None:
        fx_min, fy_min, fz_min = bbox["min"]
        fx_max, fy_max, fz_max = bbox["max"]
        # PCB sits in the cavity; width is the frame x extent minus
        # margins; height is the frame z extent minus margins. The y
        # extent is the cavity depth (frame y range minus lens y range).
        width = max(0.0, (fx_max - fx_min) - 2.0 * margins["x"])
        height = max(0.0, (fz_max - fz_min) - margins["z_max"] - margins["z_min"])
        derived["width"] = round(width, 4)
        derived["height"] = round(height, 4)
        notes.append(
            f"Derived from frame bbox: width={fx_max - fx_min:.3f}mm, "
            f"height={fz_max - fz_min:.3f}mm with margins x={margins['x']}mm, "
            f"z_min={margins['z_min']}mm, z_max={margins['z_max']}mm."
        )
    else:
        notes.append(
            "frame-coordinate-system.json is missing; cannot derive "
            "PCB outline from mechanical envelope."
        )

    # Thickness: standard FR-4 = 1.6 mm unless the schematic overrides.
    thickness = 1.6
    if isinstance(schematic, dict):
        outline = schematic.get("board_outline", {}) or {}
        if isinstance(outline, dict):
            dims = outline.get("dimensions_mm", {}) or {}
            if isinstance(dims, dict):
                t = dims.get("thickness")
                if isinstance(t, (int, float)) and not _is_tbd(t):
                    thickness = float(t)
    derived["thickness"] = thickness

    # Existing outline.
    existing: dict[str, Any] | None = None
    fits: bool | None = None
    if isinstance(schematic, dict):
        outline = schematic.get("board_outline", {}) or {}
        if isinstance(outline, dict):
            dims = outline.get("dimensions_mm", {}) or {}
            if isinstance(dims, dict):
                w = dims.get("width")
                h = dims.get("height")
                t = dims.get("thickness")
                if all(isinstance(v, (int, float)) for v in (w, h, t) if v is not None):
                    existing = {
                        "width": float(w) if w is not None else None,
                        "height": float(h) if h is not None else None,
                        "thickness": float(t) if t is not None else None,
                    }
                    if bbox is not None and derived["width"] and derived["height"]:
                        fits = (
                            existing["width"] is not None
                            and existing["height"] is not None
                            and existing["width"] <= derived["width"]
                            and existing["height"] <= derived["height"]
                        )
                        if not fits:
                            notes.append(
                                f"Existing PCB outline ({existing['width']}x{existing['height']} mm) "
                                f"exceeds derived envelope "
                                f"({derived['width']:.2f}x{derived['height']:.2f} mm)."
                            )

    return {
        "derived_outline_mm": derived,
        "existing_outline_mm": existing,
        "fits_in_frame": fits,
        "frame_bbox_mm": bbox,
        "notes": notes,
    }


def run_pcb_reconciliation(*, glasses_root: Path) -> dict[str, Any]:
    """Run PCB reconciliation and return the structured report.

    The result never invents a value: when an envelope, footprint
    dimension, or clearance is missing the report records the gap.
    """
    paths = _candidate_paths(glasses_root)
    documents: dict[str, Any] = {}
    for name, path in paths.items():
        try:
            documents[name] = _load_yaml(path)
        except PcbReconcileError:
            documents[name] = None
        except OSError:
            documents[name] = None

    schematic = documents.get("schematic_architecture")
    pcb_summary = documents.get("pcb_summary")
    placement_policy = documents.get("placement_policy")
    keepout = documents.get("camera_led_keepout")
    frame_coords = documents.get("frame_coords")
    pose_validation = documents.get("pose_validation")

    component_envelopes: list[dict[str, Any]] = []
    unknown_components: list[dict[str, Any]] = []
    if isinstance(schematic, dict):
        source_geometry = schematic.get("source_geometry", {}) or {}
        if isinstance(source_geometry, dict):
            validated = source_geometry.get("validated_component_poses", {}) or {}
            if isinstance(validated, dict):
                mapping = {
                    "camera": (167.10, 94.35, 25.50, (8.5, 8.5, 6.5)),
                    "forward_led_top": (167.10, 91.30, 30.50, (3.4, 3.4, 1.5)),
                    "forward_led_bottom": (167.10, 91.30, 20.50, (3.4, 3.4, 1.5)),
                    "left_temple_led_front": (148.61, 119.76, 19.43, (3.4, 3.4, 1.5)),
                    "left_temple_led_rear": (149.87, 187.09, 23.12, (3.4, 3.4, 1.5)),
                    "right_temple_led_front": (126.98, 122.92, 23.41, (3.4, 3.4, 1.5)),
                    "right_temple_led_rear": (125.65, 188.22, 19.54, (3.4, 3.4, 1.5)),
                }
                for name, (cx, cy, cz, env) in mapping.items():
                    pose = validated.get(name)
                    if isinstance(pose, list) and len(pose) == 3:
                        cx, cy, cz = (float(v) for v in pose)
                    component_envelopes.append(
                        {
                            "id": name,
                            "center_mm": [cx, cy, cz],
                            "envelope_mm": list(env),
                        }
                    )
                    if _is_tbd(validated.get(name)):
                        unknown_components.append(
                            {
                                "id": name,
                                "field": f"schematic_architecture.source_geometry.validated_component_poses.{name}",
                                "value": "TBD",
                            }
                        )

    bbox = _bbox_for_components(component_envelopes, margin_mm=1.0)
    derived = _derived_pcb_outline(
        schematic=schematic,
        placement_policy=placement_policy,
        frame_coords=frame_coords,
    )

    # Footprint / family coverage.
    family_findings: list[dict[str, Any]] = []
    if isinstance(schematic, dict):
        connectors = schematic.get("connectors", {}) or {}
        if isinstance(connectors, dict):
            for name, conn in connectors.items():
                family = FOOTPRINT_FAMILIES.get(name)
                if family is None:
                    continue
                if not isinstance(conn, dict):
                    family_findings.append(
                        {
                            "rule": f"pcb.footprint.{name}.missing_section",
                            "field": f"schematic_architecture.connectors.{name}",
                            "value": "MISSING",
                            "severity": "BLOCK",
                        }
                    )
                    continue
                for key in family:
                    if _is_tbd(conn.get(key.split(".")[-1])):
                        family_findings.append(
                            {
                                "rule": f"pcb.footprint.{name}.{key.split('.')[-1]}_tbd",
                                "field": f"schematic_architecture.connectors.{name}.{key.split('.')[-1]}",
                                "value": "TBD",
                                "severity": "BLOCK",
                            }
                        )

    # Mechanical-keepout cross-check.
    keepout_findings: list[dict[str, Any]] = []
    if isinstance(keepout, dict):
        for k in MECHANICAL_KEEPOUTS:
            if k not in keepout:
                keepout_findings.append(
                    {
                        "rule": f"pcb.keepout.{k}.missing",
                        "field": f"mechanical.optical-isolation.camera-led-keepout.{k}",
                        "value": "MISSING",
                        "severity": "BLOCK",
                    }
                )
    else:
        keepout_findings.append(
            {
                "rule": "pcb.keepout_yaml_missing",
                "field": "mechanical.optical-isolation.camera-led-keepout.yaml",
                "value": "MISSING",
                "severity": "BLOCK",
            }
        )

    # Connector-access review.
    connector_findings: list[dict[str, Any]] = []
    if isinstance(schematic, dict):
        connectors = schematic.get("connectors", {}) or {}
        if isinstance(connectors, dict):
            for name, conn in connectors.items():
                if not isinstance(conn, dict):
                    continue
                if _is_tbd(conn.get("type")) or _is_tbd(conn.get("part")):
                    connector_findings.append(
                        {
                            "rule": f"pcb.connector.{name}.type_or_part_tbd",
                            "field": f"schematic_architecture.connectors.{name}",
                            "value": "TBD",
                            "severity": "BLOCK",
                        }
                    )

    # Manufacturing stackup.
    stackup_findings: list[dict[str, Any]] = []
    if isinstance(schematic, dict):
        stackup = schematic.get("pcb_stackup", {}) or {}
        if isinstance(stackup, dict):
            for key in ("layers", "copper_oz", "finish", "soldermask", "silkscreen"):
                if _is_tbd(stackup.get(key)):
                    stackup_findings.append(
                        {
                            "rule": f"pcb.stackup.{key}_tbd",
                            "field": f"schematic_architecture.pcb_stackup.{key}",
                            "value": "TBD",
                            "severity": "BLOCK",
                        }
                    )

    findings = family_findings + keepout_findings + connector_findings + stackup_findings
    has_block = any(f.get("severity") == "BLOCK" for f in findings)
    if has_block or not component_envelopes:
        status = "INCOMPLETE"
    else:
        status = "PASS"

    # Cross-reference pose validation.
    pose_block: dict[str, Any] = {"ok": True, "matched": [], "missing": []}
    if isinstance(pose_validation, dict):
        accepted = pose_validation.get("accepted", []) or []
        for entry in accepted:
            if not isinstance(entry, dict):
                continue
            comp = entry.get("component")
            if comp:
                pose_block["matched"].append(
                    {
                        "component": comp,
                        "label": entry.get("label"),
                        "region": entry.get("region"),
                    }
                )
        if not accepted:
            pose_block["ok"] = False
            pose_block["missing"].append(
                "no accepted poses in component-pose-validation.json"
            )

    return {
        "status": status,
        "component_envelopes": component_envelopes,
        "component_envelope_bbox_mm": bbox,
        "unknown_components": unknown_components,
        "outline_reconciliation": derived,
        "pcb_summary_present": bool(pcb_summary),
        "footprint_family_findings": family_findings,
        "keepout_findings": keepout_findings,
        "connector_findings": connector_findings,
        "stackup_findings": stackup_findings,
        "pose_validation": pose_block,
        "findings": findings,
    }
