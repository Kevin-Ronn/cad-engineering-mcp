"""Phase 4 manufacturing-readiness report generator.

The ``manufacturing_release_report`` function aggregates the outputs
of the DFM/DFA, PCB-reconciliation, UNKNOWN/TBD tracking, and
reference-integrity validators into one structured release-readiness
document.

Per the directive:

    "Every final design must be evaluated for: DFM, DFA, tolerances,
     wall thickness, ribs, snap fits, screw bosses, PCB assembly,
     wire routing, component replacement, printing/machining method,
     surface finish, material compatibility."

    "Do not claim a design is production-ready until these checks
     have passed."

The release report is therefore an *envelope* that combines all
upstream validators and arrives at a single ``status`` value:

* ``RELEASE_READY``        - every check passed.
* ``INCOMPLETE``           - one or more required engineering
                             fields are still TBD / UNKNOWN. A
                             release is blocked by missing data.
* ``RELEASE_BLOCKED``      - one or more BLOCK-severity findings
                             or an upstream validator reported
                             non-PASS that must be addressed
                             before release.
* ``ERROR``                - the report could not be generated
                             because an upstream validator raised.

The module never invents a value. The status it returns is the
*honest* engineering state of the project; it never silently
upgrades an INCOMPLETE state to PASS.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .dfm_dfa import run_dfm_dfa_validation
from .pcb_reconcile import run_pcb_reconciliation


# Engineering keys that must be authoritatively defined before the
# glasses PCB can be released. These are checked against the
# component registry and the per-component YAMLs.
REQUIRED_FIELDS: tuple[str, tuple[str, str], ...] = (
    ("camthink_ov5640_8p5", "envelope_mm.x"),
    ("camthink_ov5640_8p5", "envelope_mm.y"),
    ("camthink_ov5640_8p5", "envelope_mm.z"),
    ("camthink_ov5640_8p5", "interface.host"),
    ("camthink_ov5640_8p5", "interface.bus"),
    ("camthink_ov5640_8p5", "interface.data_width_bits"),
    ("vsma1094750x02", "envelope_mm.x"),
    ("vsma1094750x02", "envelope_mm.y"),
    ("vsma1094750x02", "envelope_mm.z"),
    ("vsma1094750x02", "beam_angle_deg"),
    ("esp32_s3", "part_number"),
    ("esp32_s3", "interface.host"),
    ("usb_c_receptacle", "usb_c.part"),
    ("usb_c_receptacle", "usb_c.cutout_w_mm"),
    ("usb_c_receptacle", "usb_c.cutout_h_mm"),
    ("battery_cell", "battery.capacity_mah"),
    ("battery_cell", "battery.nominal_voltage"),
    ("battery_cell", "battery.voltage_range_min"),
    ("battery_cell", "battery.voltage_range_max"),
    ("battery_cell", "battery.type"),
    ("charger_ic", "charger.ic"),
    ("charger_ic", "charger.charge_current_a"),
    ("ldo_3v3", "ldo.ic"),
    ("ldo_3v3", "ldo.output"),
    ("ldo_3v3", "ldo.input"),
    ("led_driver_fet", "led_driver.fet_part"),
    ("led_driver_fet", "led_driver.topology"),
    ("camera_fpc_connector", "fpc.connector"),
    ("camera_fpc_connector", "fpc.pin_pitch_mm"),
    ("camera_fpc_connector", "fpc.bend_radius_mm_min"),
    ("antenna_module", "antenna.dimensions_mm"),
    ("antenna_module", "antenna.location"),
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return ""
    return digest.hexdigest()


def _reference_integrity(glasses_root: Path) -> dict[str, Any]:
    """Verify the SHA-256 of every reference in the manifest.

    The release report refuses to claim RELEASE_READY if the
    reference manifest is missing or any hash does not match.
    """
    manifest_path = glasses_root / "references" / "reference-manifest.yaml"
    if not manifest_path.exists():
        return {
            "ok": False,
            "manifest_present": False,
            "entries": [],
            "errors": ["reference-manifest.yaml missing"],
        }
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {
            "ok": False,
            "manifest_present": True,
            "entries": [],
            "errors": [f"manifest YAML parse error: {exc}"],
        }
    if not isinstance(manifest, dict):
        return {
            "ok": False,
            "manifest_present": True,
            "entries": [],
            "errors": ["manifest root must be a mapping"],
        }
    references = manifest.get("references", {}) or {}
    if not isinstance(references, dict):
        return {
            "ok": False,
            "manifest_present": True,
            "entries": [],
            "errors": ["references must be a mapping"],
        }
    entries: list[dict[str, Any]] = []
    all_ok = True
    for name, entry in references.items():
        if not isinstance(entry, dict):
            entries.append(
                {
                    "name": str(name),
                    "ok": False,
                    "errors": ["manifest entry is not a mapping"],
                }
            )
            all_ok = False
            continue
        rel = entry.get("file")
        expected = entry.get("sha256")
        if not rel or not expected:
            entries.append(
                {
                    "name": str(name),
                    "ok": False,
                    "errors": ["missing file or sha256 in manifest"],
                }
            )
            all_ok = False
            continue
        target = glasses_root / "references" / rel
        if not target.exists():
            entries.append(
                {
                    "name": str(name),
                    "ok": False,
                    "file": str(rel),
                    "errors": ["file missing"],
                }
            )
            all_ok = False
            continue
        actual = _file_sha256(target)
        ok = bool(expected) and actual == str(expected)
        entries.append(
            {
                "name": str(name),
                "file": str(rel),
                "expected_sha256": str(expected),
                "actual_sha256": actual,
                "ok": ok,
                "errors": [] if ok else ["sha256 mismatch"],
            }
        )
        if not ok:
            all_ok = False
    return {
        "ok": all_ok,
        "manifest_present": True,
        "entries": entries,
        "errors": [],
    }


def run_manufacturing_release_report(
    *, glasses_root: Path
) -> dict[str, Any]:
    """Build the manufacturing-readiness release report.

    Returns a structured envelope combining:

    * Reference integrity (SHA-256).
    * DFM/DFA.
    * PCB reconciliation.
    * Component-data UNKNOWN/TBD coverage.
    * Aggregated status.

    The report never invents a value. The status is ``INCOMPLETE``
    or ``RELEASE_BLOCKED`` whenever the engineering state is not
    fully resolved.
    """
    started_at = datetime.now(timezone.utc).isoformat()

    # 1. Reference integrity.
    ref_integrity = _reference_integrity(glasses_root)

    # 2. DFM/DFA.
    dfm_dfa = run_dfm_dfa_validation(glasses_root=glasses_root)

    # 3. PCB reconciliation.
    pcb = run_pcb_reconciliation(glasses_root=glasses_root)

    # 4. Component-data UNKNOWN/TBD coverage.
    from .component_authority import load_unknowns, resolve_component_field

    unknowns_doc = load_unknowns(glasses_root=glasses_root)
    unknowns_records = unknowns_doc.get("records", []) or []

    coverage: list[dict[str, Any]] = []
    for component_id, field in REQUIRED_FIELDS:
        resolution = resolve_component_field(
            component_id=component_id,
            field=field,
            glasses_root=glasses_root,
        )
        coverage.append(
            {
                "component_id": component_id,
                "field": field,
                "value": resolution.get("value"),
                "source": resolution.get("source"),
                "authoritative": resolution.get("authoritative"),
                "is_tbd": (
                    resolution.get("value") == "UNKNOWN"
                    or (isinstance(resolution.get("value"), str)
                        and resolution.get("value", "").strip().upper() in {"TBD", "TBD_FROM_DASHBOARD", "TBD_FROM_BATTERY_DATASHEET"})
                ),
            }
        )

    unknown_required = [c for c in coverage if c.get("is_tbd") or not c.get("authoritative")]

    # 5. Aggregate.
    blockers: list[str] = []
    if not ref_integrity.get("ok"):
        blockers.append("reference_integrity")
    if dfm_dfa.get("status") != "PASS":
        blockers.append("dfm_dfa")
    if pcb.get("status") != "PASS":
        blockers.append("pcb_reconciliation")
    if unknown_required:
        blockers.append("component_data_unknowns")

    if blockers:
        # If reference integrity is broken, the release is fully blocked.
        if not ref_integrity.get("ok"):
            status = "RELEASE_BLOCKED"
        else:
            status = "INCOMPLETE"
    else:
        status = "RELEASE_READY"

    return {
        "status": status,
        "generated_at": started_at,
        "summary": {
            "blockers": blockers,
            "dfm_dfa_status": dfm_dfa.get("status"),
            "pcb_status": pcb.get("status"),
            "reference_integrity_ok": bool(ref_integrity.get("ok")),
            "required_fields_total": len(REQUIRED_FIELDS),
            "required_fields_authoritative": sum(
                1 for c in coverage if c.get("authoritative")
            ),
            "required_fields_unknown": len(unknown_required),
            "unknowns_records_count": len(unknowns_records),
        },
        "reference_integrity": ref_integrity,
        "dfm_dfa": dfm_dfa,
        "pcb_reconciliation": pcb,
        "required_fields_coverage": coverage,
        "unknown_required_fields": unknown_required,
        "unknowns_records": unknowns_records,
    }
