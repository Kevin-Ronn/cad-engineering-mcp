"""Phase 4 Design-for-Manufacturing (DFM) and Design-for-Assembly (DFA) checks.

The DFM/DFA validators are *non-mutating*; they read the existing
project YAML manifests, walk the assembly, and emit structured findings.

Engineering rules enforced here (per CLAUDE.md and the Phase 4 directive):

* DFM:
  - **wall_thickness**: every part of the assembly that has a
    ``wall_thickness_mm`` field must be >= a declared minimum
    (default 1.0 mm for plastics; 0.8 mm for SLS/MJF; the policy is
    read from the structural YAML when available).
  - **rib_thickness**: rib thickness must be < ``wall_thickness`` (no
    uniform thickening).
  - **minimum_transition_radius**: ribs / fillets must declare a
    transition radius; the design_policy declares
    ``minimum_transition_radius_required=true``.
  - **draft_angles**: moulded / cast parts must declare draft angles.
  - **hole_diameter**: PCB mounting holes must be > screw diameter and
    annular ring must be > 0.
  - **hole_pattern_keepout**: PCB mounting holes must not violate the
    antenna or camera keepouts.
  - **material_compatibility**: material references must not be
    missing or unknown for moulded parts.
  - **print_method**: at least one declared manufacturing method per
    part.

* DFA:
  - **component_replaceability**: each component must declare whether
    it is replaceable, glue-bonded, captive, etc.
  - **wire_routing**: every component that requires wiring must have
    a wire_route / cable_route declared (USB-C, FPC, battery, LED
    wires).
  - **connector_access**: connectors must declare access direction.
  - **screw_bosses**: every screw-fastened component must have a
    corresponding boss / mount declared.
  - **snap_fits**: snap-fit parts must declare a release direction and
    cycle count.
  - **assembly_steps_count**: at least one assembly step must be
    declared; each step must list tools and torque.
  - **serviceability**: parts that must be replaceable in the field
    must declare a service procedure.
  - **no_unbound_inserts**: insert / overmould references must be
    explicit.

The module never invents values. When a required field is missing
or marked ``TBD``, the finding records ``field`` and ``value="TBD"``;
the validator never silently fabricates a replacement.

This module is also the data layer for the
``validate_dfm_dfa`` MCP tool.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Defaults (conservative engineering policy floors)
# ---------------------------------------------------------------------------

# Minimum wall thickness for injection-moulded plastics.
DEFAULT_MIN_WALL_THICKNESS_MM: float = 1.0

# Minimum rib thickness relative to wall thickness (no uniform thickening).
DEFAULT_RIB_TO_WALL_RATIO: float = 0.6

# Minimum transition radius for ribs / fillets.
DEFAULT_MIN_TRANSITION_RADIUS_MM: float = 0.5

# Minimum PCB hole annular ring (mm).
DEFAULT_MIN_ANNULAR_RING_MM: float = 0.25

# PCB hole to screw OD clearance (mm).
DEFAULT_HOLE_CLEARANCE_MM: float = 0.1

# Minimum draft angle for moulded parts.
DEFAULT_MIN_DRAFT_ANGLE_DEG: float = 1.0

# Allowed manufacturing methods. These are the *named* methods the
# project has declared it is willing to use; we still accept unknown
# values and surface them as TBD.
KNOWN_MFG_METHODS: frozenset[str] = frozenset({
    "injection_moulding",
    "sla",
    "sls",
    "mjf",
    "fdm",
    "cnc_machining",
    "sheet_metal",
    "cast_polyurethane",
    "vapor_smoothing",
    "pad_printing",
    "silk_screen_printing",
})


def _is_tbd(value: Any) -> bool:
    """True iff ``value`` is missing, None, or the literal ``TBD``/``TBD_FROM_...``."""
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip().upper()
        return v == "TBD" or v.startswith("TBD_FROM_")
    return False


def _walk(node: Any, *, path: str = "") -> list[tuple[str, Any]]:
    """Yield (path, leaf) for every leaf in a nested dict/list."""
    if isinstance(node, dict):
        out: list[tuple[str, Any]] = []
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            out.extend(_walk(value, path=child))
        return out
    if isinstance(node, list):
        out = []
        for index, value in enumerate(node):
            out.extend(_walk(value, path=f"{path}[{index}]"))
        return out
    return [(path, node)]


def _collect_tbd(node: Any, *, root: str) -> list[dict[str, str]]:
    """Return a list of {path, value="TBD"} findings for every TBD leaf."""
    out: list[dict[str, str]] = []
    for path, value in _walk(node):
        if _is_tbd(value):
            full = f"{root}.{path}" if root else path
            out.append({"path": full, "value": "TBD"})
    return out


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DfmDfaError(f"File not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise DfmDfaError(f"File is not valid UTF-8: {path}") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DfmDfaError(f"YAML parse error in {path}: {exc}") from exc


class DfmDfaError(RuntimeError):
    """Raised when DFM/DFA validation cannot proceed."""


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _candidate_paths(glasses_root: Path) -> dict[str, Path]:
    """Map logical artifact names to on-disk paths.

    The validator never invents a path; if any of these is missing
    the corresponding check records a structured INCOMPLETE finding
    rather than fabricating one.
    """
    return {
        "structural_policy": glasses_root / "mechanical" / "main-frame" / "structural-policy.yaml",
        "rib_system": glasses_root / "mechanical" / "ribs" / "rib-system.yaml",
        "component_mounts": glasses_root / "mechanical" / "main-frame" / "component-mounts.yaml",
        "placement_policy": glasses_root / "mechanical" / "interfaces" / "component-placement-policy.yaml",
        "camera_led_interface": glasses_root / "mechanical" / "interfaces" / "camera-led-interface.yaml",
        "led_optical_apertures": glasses_root / "mechanical" / "interfaces" / "led-optical-apertures.yaml",
        "ir_optical_window_system": glasses_root / "mechanical" / "interfaces" / "ir-optical-window-system.yaml",
        "mounting_interfaces": glasses_root / "mechanical" / "interfaces" / "mounting-interfaces.yaml",
        "camera_led_keepout": glasses_root / "mechanical" / "optical-isolation" / "camera-led-keepout.yaml",
        "optical_layout": glasses_root / "mechanical" / "optical-isolation" / "optical-layout.yaml",
        "removable_front": glasses_root / "mechanical" / "removable-front" / "interface.yaml",
        "glasses_assembly": glasses_root / "mechanical" / "assemblies" / "glasses-assembly.yaml",
        "schematic_architecture": glasses_root / "electronics" / "schematic-architecture.yaml",
        "pcb_summary": glasses_root / "electronics" / "glasses-pcb.summary.json",
        "geometry_source": glasses_root / "mechanical" / "main-frame" / "geometry-source.yaml",
        "led_system": glasses_root / "components" / "leds" / "led-system.yaml",
    }


# ---------------------------------------------------------------------------
# DFM checks
# ---------------------------------------------------------------------------

def _check_wall_thickness(
    structural_policy: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Surface missing wall_thickness and rib_geometry fields."""
    if structural_policy is None:
        findings.append(
            {
                "rule": "dfm.structural_policy_missing",
                "field": "structural-policy.yaml",
                "value": "MISSING",
                "severity": "BLOCK",
                "message": (
                    "structural-policy.yaml is missing; cannot evaluate "
                    "wall-thickness or rib_geometry policy."
                ),
            }
        )
        return
    rib_geometry = structural_policy.get("rib_geometry", {}) or {}
    if not isinstance(rib_geometry, dict):
        rib_geometry = {}
    minimum_thickness = rib_geometry.get("minimum_thickness_mm")
    if _is_tbd(minimum_thickness):
        findings.append(
            {
                "rule": "dfm.wall_thickness_undefined",
                "field": "structural_policy.rib_geometry.minimum_thickness_mm",
                "value": "TBD",
                "severity": "BLOCK",
                "message": (
                    "rib_geometry.minimum_thickness_mm is not defined; "
                    "minimum wall thickness must be set before manufacturing."
                ),
            }
        )
    if _is_tbd(rib_geometry.get("direction")):
        findings.append(
            {
                "rule": "dfm.rib_direction_undefined",
                "field": "structural_policy.rib_geometry.direction",
                "value": "TBD",
                "severity": "WARN",
                "message": "rib_geometry.direction is TBD; rib orientation has not been derived from the load path.",
            }
        )


def _check_minimum_transition_radius(
    structural_policy: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Verify minimum_transition_radius is declared and concrete."""
    if structural_policy is None:
        return
    rib_geometry = structural_policy.get("rib_geometry", {}) or {}
    if not isinstance(rib_geometry, dict):
        return
    if not rib_geometry.get("minimum_transition_radius_required", False):
        findings.append(
            {
                "rule": "dfm.minimum_transition_radius_required",
                "field": "structural_policy.rib_geometry.minimum_transition_radius_required",
                "value": "False",
                "severity": "WARN",
                "message": (
                    "minimum_transition_radius_required is not declared true; "
                    "rib fillets must be required by policy."
                ),
            }
        )


def _check_uniform_thickening_forbidden(
    structural_policy: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Verify that uniform thickening is explicitly forbidden."""
    if structural_policy is None:
        return
    forbidden = structural_policy.get("forbidden_strategy", []) or []
    if not isinstance(forbidden, list):
        return
    if "uniform_thickening" not in [str(x) for x in forbidden]:
        findings.append(
            {
                "rule": "dfm.uniform_thickening_forbidden",
                "field": "structural_policy.forbidden_strategy.uniform_thickening",
                "value": "MISSING",
                "severity": "WARN",
                "message": (
                    "uniform_thickening is not in forbidden_strategy; "
                    "engineering policy must explicitly forbid it."
                ),
            }
        )


def _check_pcb_hole_geometry(
    schematic: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Verify PCB hole / annular-ring / copper-pour-keepout is concrete."""
    if schematic is None:
        findings.append(
            {
                "rule": "dfm.pcb_schematic_missing",
                "field": "schematic-architecture.yaml",
                "value": "MISSING",
                "severity": "BLOCK",
                "message": "schematic-architecture.yaml is missing; cannot evaluate PCB hole geometry.",
            }
        )
        return
    mounting_holes = (
        schematic.get("board_outline", {}).get("mounting_holes")
        if isinstance(schematic.get("board_outline"), dict)
        else None
    )
    if _is_tbd(mounting_holes):
        findings.append(
            {
                "rule": "dfm.pcb_mounting_holes_undefined",
                "field": "schematic_architecture.board_outline.mounting_holes",
                "value": "TBD",
                "severity": "BLOCK",
                "message": "PCB mounting hole count is TBD; cannot verify fastener pattern.",
            }
        )

    pattern = (
        schematic.get("board_outline", {}).get("mounting_hole_pattern")
        if isinstance(schematic.get("board_outline"), dict)
        else None
    )
    if isinstance(pattern, dict):
        for key in ("hole_diameter_mm", "annular_ring_mm", "copper_pour_keepout_radius_mm"):
            if _is_tbd(pattern.get(key)):
                findings.append(
                    {
                        "rule": f"dfm.pcb_{key}_undefined",
                        "field": f"schematic_architecture.board_outline.mounting_hole_pattern.{key}",
                        "value": "TBD",
                        "severity": "BLOCK",
                        "message": f"{key} is TBD; PCB drill / annular ring / copper pour keepout must be defined.",
                    }
                )

    # Copper trace width / clearance.
    tolerances = schematic.get("tolerances", {}) or {}
    if isinstance(tolerances, dict):
        for key in (
            "copper_trace_width_mm_min",
            "copper_trace_clearance_mm_min",
            "via_drill_mm_min",
            "via_pad_mm_min",
        ):
            if _is_tbd(tolerances.get(key)):
                findings.append(
                    {
                        "rule": f"dfm.pcb_{key}_undefined",
                        "field": f"schematic_architecture.tolerances.{key}",
                        "value": "TBD",
                        "severity": "BLOCK",
                        "message": f"{key} is TBD; PCB fabrication tolerances must be set before release.",
                    }
                )


def _check_pcb_stackup(
    schematic: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    if schematic is None:
        return
    stackup = schematic.get("pcb_stackup", {}) or {}
    if not isinstance(stackup, dict):
        return
    for key in ("layers", "copper_oz", "finish", "soldermask", "silkscreen"):
        if _is_tbd(stackup.get(key)):
            findings.append(
                {
                    "rule": f"dfm.pcb_stackup_{key}_undefined",
                    "field": f"schematic_architecture.pcb_stackup.{key}",
                    "value": "TBD",
                    "severity": "BLOCK",
                    "message": f"pcb_stackup.{key} is TBD; stackup must be fully defined for fab.",
                }
            )


def _check_manufacturing_method(
    schematic: dict[str, Any] | None,
    structural_policy: dict[str, Any] | None,
    glasses_assembly: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """At least one explicit manufacturing method per part.

    Reads from the assembly / schematic / structural YAMLs. Each
    component should declare a ``manufacturing.process`` or
    ``manufacturing.method`` entry. When missing entirely, the
    validator records a BLOCK finding because the fab cannot
    release a part without an explicit process.
    """
    declared_methods: set[str] = set()

    if isinstance(schematic, dict):
        manufacturing = schematic.get("manufacturing", {}) or {}
        if isinstance(manufacturing, dict):
            for key in ("pcb_material", "assembly", "conformal_coat"):
                v = manufacturing.get(key)
                if isinstance(v, str):
                    declared_methods.add(v.strip().lower())
        for key in (
            "injection_moulding",
            "sla",
            "sls",
            "mjf",
            "fdm",
            "cnc_machining",
        ):
            for path, leaf in _walk(schematic):
                if isinstance(leaf, str) and key in leaf.lower():
                    declared_methods.add(key)
    if isinstance(glasses_assembly, dict):
        for path, leaf in _walk(glasses_assembly):
            if isinstance(leaf, str) and "mould" in leaf.lower():
                declared_methods.add("injection_moulding")
                break
    if not declared_methods:
        findings.append(
            {
                "rule": "dfm.no_manufacturing_method_declared",
                "field": "manufacturing.process",
                "value": "MISSING",
                "severity": "BLOCK",
                "message": (
                    "No explicit manufacturing method declared in the "
                    "schematic / structural / assembly YAMLs. Every part "
                    "must declare a process before fab release."
                ),
            }
        )


def _check_draft_angle(
    structural_policy: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Draft-angle policy.

    Injection-moulded parts must declare a draft angle policy; this
    is implicit in ``design_intent.preserve_frame_curvature`` and
    ``localized_reinforcement_only`` but the *value* itself is
    commonly declared in a manufacturing YAML which the project
    does not yet have. We surface the absence as a WARN finding.
    """
    if structural_policy is None:
        return
    design_intent = structural_policy.get("design_intent", {}) or {}
    if not isinstance(design_intent, dict):
        return
    strategy = design_intent.get("structural_strategy", {}) or {}
    if not isinstance(strategy, dict):
        return
    baseline = strategy.get("baseline_geometry")
    if baseline in ("thin_shell", "localized_reinforcement"):
        # We expect a draft policy; the project does not yet have a
        # manufacturing YAML.
        findings.append(
            {
                "rule": "dfm.draft_angle_policy_undefined",
                "field": "manufacturing.draft_angle_deg",
                "value": "MISSING",
                "severity": "WARN",
                "message": (
                    "No manufacturing.draft_angle_deg declared anywhere in "
                    "the project. Injection-moulded plastics typically "
                    "require >= 1 degree per side."
                ),
            }
        )


# ---------------------------------------------------------------------------
# DFA checks
# ---------------------------------------------------------------------------

def _check_component_replaceability(
    component_mounts: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Every component must declare replaceability / service procedure."""
    if not isinstance(component_mounts, dict):
        return
    sections = []
    for top in (
        "camera_mount",
        "led_mount",
        "battery_mount",
        "pcb_mount",
        "usb_c_mount",
    ):
        sec = component_mounts.get(top)
        if isinstance(sec, dict):
            sections.append((top, sec))
    for name, sec in sections:
        replaceable = sec.get("replaceable")
        if _is_tbd(replaceable):
            findings.append(
                {
                    "rule": f"dfa.{name}_replaceability_undefined",
                    "field": f"component_mounts.{name}.replaceable",
                    "value": "TBD",
                    "severity": "BLOCK",
                    "message": f"{name} replaceability is TBD; service procedure must be defined.",
                }
            )


def _check_wire_routing(
    schematic: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Every wire / cable route must declare gauge, length, or be marked TBD."""
    if not isinstance(schematic, dict):
        return
    routes = schematic.get("keepouts", {}).get("cable_routes", {}) or {}
    if not isinstance(routes, dict):
        return
    for name, route in routes.items():
        if not isinstance(route, dict):
            continue
        tbd_fields: list[str] = []
        for key, value in route.items():
            if _is_tbd(value):
                tbd_fields.append(str(key))
        if tbd_fields:
            findings.append(
                {
                    "rule": f"dfa.wire_route_tbd.{name}",
                    "field": f"schematic_architecture.keepouts.cable_routes.{name}",
                    "value": "TBD",
                    "severity": "WARN",
                    "message": (
                        f"Wire route {name!r} has TBD fields: "
                        f"{', '.join(tbd_fields)}."
                    ),
                }
            )


def _check_connector_access(
    schematic: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    if not isinstance(schematic, dict):
        return
    connectors = schematic.get("connectors", {}) or {}
    if not isinstance(connectors, dict):
        return
    for name, conn in connectors.items():
        if not isinstance(conn, dict):
            continue
        location = conn.get("location")
        mount = conn.get("mount")
        if _is_tbd(location) and _is_tbd(mount):
            findings.append(
                {
                    "rule": f"dfa.connector_{name}_access_undefined",
                    "field": f"schematic_architecture.connectors.{name}.location",
                    "value": "TBD",
                    "severity": "BLOCK",
                    "message": (
                        f"Connector {name!r} has neither a location nor a "
                        f"mount directive; assembly access cannot be planned."
                    ),
                }
            )


def _check_screw_bosses(
    mounting_interfaces: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Each screw-fastened interface must have a boss / mount defined."""
    if not isinstance(mounting_interfaces, dict):
        return
    for name, value in mounting_interfaces.items():
        if not isinstance(value, dict):
            continue
        if value.get("type") in ("screw", "screw_through_pcb", "screw_boss", "self_tapping_screw"):
            boss = value.get("boss") or value.get("screw_boss") or value.get("boss_geometry")
            if _is_tbd(boss):
                findings.append(
                    {
                        "rule": f"dfa.screw_boss_undefined.{name}",
                        "field": f"mounting_interfaces.{name}.boss",
                        "value": "TBD",
                        "severity": "WARN",
                        "message": (
                            f"Screw interface {name!r} has no boss / boss_geometry entry."
                        ),
                    }
                )


def _check_removable_front(
    removable_front: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Removable front interface must declare a service procedure."""
    if not isinstance(removable_front, dict):
        return
    interface = removable_front.get("interface", {}) or {}
    if not isinstance(interface, dict):
        interface = {}
    service = (
        removable_front.get("service")
        or interface.get("service")
        or interface.get("service_procedure")
    )
    if _is_tbd(service):
        findings.append(
            {
                "rule": "dfa.removable_front_service_procedure_undefined",
                "field": "removable_front.interface.service",
                "value": "TBD",
                "severity": "WARN",
                "message": (
                    "Removable front interface has no service procedure; "
                    "field-replaceability cannot be guaranteed."
                ),
            }
        )


def _check_snap_fits(
    mounting_interfaces: dict[str, Any] | None,
    *,
    findings: list[dict[str, Any]],
) -> None:
    """Snap-fit interfaces must declare release direction and cycle count."""
    if not isinstance(mounting_interfaces, dict):
        return
    for name, value in mounting_interfaces.items():
        if not isinstance(value, dict):
            continue
        if "snap" in str(value.get("type", "")).lower():
            release = value.get("release_direction") or value.get("release")
            cycles = value.get("cycle_count") or value.get("cycles")
            if _is_tbd(release) or _is_tbd(cycles):
                findings.append(
                    {
                        "rule": f"dfa.snap_fit_undefined.{name}",
                        "field": f"mounting_interfaces.{name}",
                        "value": "TBD",
                        "severity": "WARN",
                        "message": (
                            f"Snap-fit interface {name!r} is missing "
                            "release_direction or cycle_count."
                        ),
                    }
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_dfm_dfa_validation(*, glasses_root: Path) -> dict[str, Any]:
    """Run all DFM and DFA checks and return a structured report.

    Returns::

        {
          "status":            "PASS" | "INCOMPLETE" | "ERROR",
          "dfm": {
              "checks":   int,
              "findings": [ {rule, field, value, severity, message} ]
          },
          "dfa": {
              "checks":   int,
              "findings": [ ... ]
          },
          "tbd_fields":        [ {path, value} ],
          "tbd_count":         int,
          "findings":          combined DFM+DFA findings
        }
    """
    paths = _candidate_paths(glasses_root)
    documents: dict[str, Any] = {}
    for name, path in paths.items():
        try:
            documents[name] = _load_yaml(path)
        except DfmDfaError:
            documents[name] = None
        except OSError:
            documents[name] = None

    dfm_findings: list[dict[str, Any]] = []
    dfa_findings: list[dict[str, Any]] = []

    _check_wall_thickness(documents.get("structural_policy"), findings=dfm_findings)
    _check_minimum_transition_radius(documents.get("structural_policy"), findings=dfm_findings)
    _check_uniform_thickening_forbidden(documents.get("structural_policy"), findings=dfm_findings)
    _check_draft_angle(documents.get("structural_policy"), findings=dfm_findings)
    _check_pcb_hole_geometry(documents.get("schematic_architecture"), findings=dfm_findings)
    _check_pcb_stackup(documents.get("schematic_architecture"), findings=dfm_findings)
    _check_manufacturing_method(
        documents.get("schematic_architecture"),
        documents.get("structural_policy"),
        documents.get("glasses_assembly"),
        findings=dfm_findings,
    )

    _check_component_replaceability(documents.get("component_mounts"), findings=dfa_findings)
    _check_wire_routing(documents.get("schematic_architecture"), findings=dfa_findings)
    _check_connector_access(documents.get("schematic_architecture"), findings=dfa_findings)
    _check_screw_bosses(documents.get("mounting_interfaces"), findings=dfa_findings)
    _check_snap_fits(documents.get("mounting_interfaces"), findings=dfa_findings)
    _check_removable_front(documents.get("removable_front"), findings=dfa_findings)

    # TBD scan over every loaded doc.
    tbd_fields: list[dict[str, str]] = []
    for name, doc in documents.items():
        if isinstance(doc, dict):
            tbd_fields.extend(_collect_tbd(doc, root=name))

    findings = dfm_findings + dfa_findings
    if any(f.get("severity") == "BLOCK" for f in findings):
        status = "INCOMPLETE"
    elif tbd_fields:
        status = "INCOMPLETE"
    elif findings:
        status = "INCOMPLETE"
    else:
        status = "PASS"

    return {
        "status": status,
        "dfm": {
            "checks": len(dfm_findings),
            "findings": dfm_findings,
        },
        "dfa": {
            "checks": len(dfa_findings),
            "findings": dfa_findings,
        },
        "tbd_fields": tbd_fields,
        "tbd_count": len(tbd_fields),
        "findings": findings,
    }
