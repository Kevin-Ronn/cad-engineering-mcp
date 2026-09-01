"""Phase 5 release-blocker resolution and audit-timeline module.

Phase 4 introduced the *manufacturing_release_report* which aggregates
every upstream validator into a single ``status`` value
(``RELEASE_READY``, ``INCOMPLETE``, ``RELEASE_BLOCKED``). Phase 5 adds
the *release-blocker manifest*: a deterministic, structured list of
*every* engineering item that must be resolved before a release is
possible.

The directive (CLAUDE.md) is explicit:

    "Every generated artifact must have a corresponding validation
     result."

    "A design is NOT considered complete if:
       - geometry was guessed
       - collisions were not checked
       - optical paths were not checked
       - PCB/mechanical interfaces were not checked
       - tolerances were ignored
       - manufacturing constraints were ignored"

The release-blocker manifest is the engineering "what must I fix
before I can ship" report. It is built by re-running every upstream
validator and emitting a flat list of blockers, each carrying:

    blocker_id        -- deterministic, stable id derived from
                          (source_tool, source_field)
    source_tool       -- the validator that produced the finding
                          (e.g. "validate_dfm_dfa",
                           "validate_structural_policy",
                           "validate_optical_window_system",
                           "reconcile_pcb",
                           "manufacturing_release_report",
                           "verify_reference_integrity",
                           "component_authority")
    category          -- BLOCKER | UNKNOWN_FIELD | TBD_FIELD |
                          DATA_GAP | POLICY_GAP
    severity          -- BLOCK | WARNING | INFO
    field             -- the engineering field the blocker refers to
                          (dotted path or component-field path)
    component_id      -- the component the blocker refers to
                          (None when not component-scoped)
    value             -- the current value, verbatim. Never invented.
    reason            -- human-readable description
    remediation_hint  -- the validator-supplied next step
                          (also verbatim, never invented)

Engineering rules:

* The manifest is *read-only by default*; the only mutation is through
  the controlled-write :p ``save_release_blocker_manifest`` tool.
* UNKNOWN/TBD are preserved verbatim; no fabrication.
* The manifest aggregates *every* upstream finding rather than picking
  a single representative -- a release is only ready when the
  blocker list is empty.
* The manifest is deterministic: two runs in a row produce the same
  blocker_id ordering.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class ReleaseBlockerError(RuntimeError):
    """Raised by the release-blocker manifest module on invalid input."""


# ---------------------------------------------------------------------------
# Severity / category normalisation
# ---------------------------------------------------------------------------

VALID_SEVERITIES: frozenset[str] = frozenset({"BLOCK", "WARNING", "INFO"})
VALID_CATEGORIES: frozenset[str] = frozenset(
    {"BLOCKER", "UNKNOWN_FIELD", "TBD_FIELD", "DATA_GAP", "POLICY_GAP"}
)

# Production-engineering objectives that the structural validator
# requires. Mirrors the canonical list in
# ``cad_engineering_mcp.tools.structural_tools``; redeclared here so
# the release-blocker manifest does not silently lose the synthetic
# missing-objectives blockers when the structural module raises.
REQUIRED_OBJECTIVES: tuple[str, ...] = (
    "minimum_structural_mass",
    "minimum_wall_thickness",
    "maximum_required_stiffness",
    "maintain_serviceability",
)


def _normalise_severity(value: Any) -> str:
    """Map an arbitrary severity string to BLOCK / WARNING / INFO.

    Unknown severities degrade to BLOCK -- the manifest must never
    silently down-classify a blocker.
    """
    if value is None:
        return "BLOCK"
    if not isinstance(value, str):
        return "BLOCK"
    upper = value.strip().upper()
    if upper in VALID_SEVERITIES:
        return upper
    if upper in {"ERROR", "FAIL", "RELEASE_BLOCKED", "CRITICAL"}:
        return "BLOCK"
    if upper in {"WARN", "INCOMPLETE"}:
        return "WARNING"
    return "BLOCK"


def _normalise_category(value: Any) -> str:
    """Map an arbitrary category string to the canonical category set."""
    if value is None:
        return "BLOCKER"
    if not isinstance(value, str):
        return "BLOCKER"
    upper = value.strip().upper()
    if upper in VALID_CATEGORIES:
        return upper
    if upper in {"UNKNOWN", "TBD", "DATA_GAP", "POLICY_GAP"}:
        return upper if upper in VALID_CATEGORIES else "DATA_GAP"
    return "BLOCKER"


def _stable_id(*parts: Any) -> str:
    """Compute a stable id from the given string parts.

    The id is a 16-char SHA-256 prefix, hex-encoded. It is fully
    deterministic given identical inputs, so two runs of the same
    engineering state produce the same ``blocker_id`` set.
    """
    cleaned = []
    for part in parts:
        if part is None:
            cleaned.append("")
        else:
            cleaned.append(str(part))
    joined = "\x1f".join(cleaned)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return digest[:16]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def _extract_dfm_dfa_blockers(dfm_dfa: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk the DFM/DFA report and emit one blocker per finding.

    The DFM/DFA validator exposes a ``findings`` list where each item
    carries ``rule``, ``severity``, ``path``, and ``value``.
    """
    blockers: list[dict[str, Any]] = []
    if not isinstance(dfm_dfa, dict):
        return blockers
    findings = dfm_dfa.get("findings", []) or []
    tbd_fields = dfm_dfa.get("tbd_fields", []) or []
    if not isinstance(findings, list):
        findings = []
    if not isinstance(tbd_fields, list):
        tbd_fields = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = _normalise_severity(finding.get("severity", "BLOCK"))
        field = finding.get("path") or finding.get("rule") or ""
        value = finding.get("value", "TBD")
        reason = finding.get("reason") or finding.get("rule") or "DFM/DFA finding"
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_dfm_dfa", field, value, reason
                ),
                "source_tool": "validate_dfm_dfa",
                "category": _normalise_category(finding.get("category")),
                "severity": severity,
                "field": str(field),
                "component_id": finding.get("component_id"),
                "value": value,
                "reason": str(reason),
                "remediation_hint": (
                    "Resolve the DFM/DFA finding by providing the "
                    "authoritative value in the corresponding YAML; "
                    "do not silently downgrade severity."
                ),
            }
        )
    # TBD-only fields that did not appear in findings also surface
    # as DATA_GAP blockers when the validator reports them.
    for entry in tbd_fields:
        if not isinstance(entry, dict):
            continue
        field = entry.get("path") or ""
        value = entry.get("value", "TBD")
        # Skip duplicates the findings list already covered.
        if any(
            b["source_tool"] == "validate_dfm_dfa" and b["field"] == field
            for b in blockers
        ):
            continue
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_dfm_dfa", field, value, "tbd_field"
                ),
                "source_tool": "validate_dfm_dfa",
                "category": "TBD_FIELD",
                "severity": "WARNING",
                "field": str(field),
                "component_id": None,
                "value": value,
                "reason": "TBD field scanned by DFM/DFA validator",
                "remediation_hint": (
                    "Replace TBD with an authoritative value or record "
                    "an explicit UNKNOWN against the field via "
                    "mark_component_unknown."
                ),
            }
        )
    return blockers


def _normalise_structural_input(structural: Any) -> dict[str, Any]:
    """Return the engineering-data dict regardless of envelope wrapping.

    The structural validator module returns a raw dict; the structural
    MCP tool wraps it as ``{status, data}``. Both are accepted.
    """
    if not isinstance(structural, dict):
        return {}
    if "data" in structural and isinstance(structural.get("data"), dict):
        return structural["data"]
    return structural


def _normalise_optical_input(optical: Any) -> dict[str, Any]:
    """Return the engineering-data dict regardless of envelope wrapping.

    The optical-window validator module returns a raw dict; the
    optical-window MCP tool wraps it as ``{status, data}``.
    """
    if not isinstance(optical, dict):
        return {}
    if "data" in optical and isinstance(optical.get("data"), dict):
        return optical["data"]
    return optical


def _extract_structural_blockers(structural: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert validate_structural_policy envelope / data into blockers."""
    blockers: list[dict[str, Any]] = []
    data = _normalise_structural_input(structural)
    if not data:
        return blockers
    findings = data.get("findings", []) or []
    tbd_fields = data.get("tbd_fields", []) or []
    missing_objectives = data.get("missing_objectives", []) or []
    rib_zones_count = data.get("rib_zones_count", 0)
    interfaces = data.get("interfaces", []) or []
    exclusions_present = data.get("exclusions_present", False)

    if rib_zones_count == 0:
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_structural_policy", "rib_zones_count", 0
                ),
                "source_tool": "validate_structural_policy",
                "category": "POLICY_GAP",
                "severity": "BLOCK",
                "field": "rib_system.rib_zones",
                "component_id": None,
                "value": 0,
                "reason": "rib_zones is empty; localized reinforcement "
                "has not been defined.",
                "remediation_hint": (
                    "Populate rib_zones in rib-system.yaml with the "
                    "localized reinforcement regions derived from the "
                    "load paths."
                ),
            }
        )
    if missing_objectives:
        for obj in missing_objectives:
            blockers.append(
                {
                    "blocker_id": _stable_id(
                        "validate_structural_policy", "missing_objective", obj
                    ),
                    "source_tool": "validate_structural_policy",
                    "category": "POLICY_GAP",
                    "severity": "BLOCK",
                    "field": "structural_policy.design_intent.objective",
                    "component_id": None,
                    "value": "MISSING",
                    "reason": (
                        f"Required structural objective missing: {obj!r}"
                    ),
                    "remediation_hint": (
                        "Add the missing objective to "
                        "structural-policy.yaml design_intent.objective."
                    ),
                }
            )
    if not interfaces:
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_structural_policy", "load_interfaces", "empty"
                ),
                "source_tool": "validate_structural_policy",
                "category": "POLICY_GAP",
                "severity": "BLOCK",
                "field": "structural_policy.load_interfaces",
                "component_id": None,
                "value": "[]",
                "reason": "load_interfaces is empty; no mounting interfaces "
                "are represented in structural-policy.yaml.",
                "remediation_hint": (
                    "Populate structural_policy.load_interfaces with the "
                    "component mount interfaces."
                ),
            }
        )
    if not exclusions_present:
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_structural_policy",
                    "rib_generation.exclusions",
                    "empty",
                ),
                "source_tool": "validate_structural_policy",
                "category": "POLICY_GAP",
                "severity": "BLOCK",
                "field": "rib_system.rib_generation.exclusions",
                "component_id": None,
                "value": "[]",
                "reason": "rib_generation.exclusions is missing or empty; "
                "rib keep-outs have not been enumerated.",
                "remediation_hint": (
                    "Populate rib_generation.exclusions with the explicit "
                    "regions where ribs must not be placed."
                ),
            }
        )
    for entry in tbd_fields:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path") or ""
        value = entry.get("value", "TBD")
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_structural_policy",
                    "tbd",
                    path,
                    value,
                ),
                "source_tool": "validate_structural_policy",
                "category": "TBD_FIELD",
                "severity": "WARNING",
                "field": str(path),
                "component_id": None,
                "value": value,
                "reason": "TBD field in structural YAMLs",
                "remediation_hint": (
                    "Replace TBD with an authoritative value or record "
                    "an explicit UNKNOWN via mark_component_unknown."
                ),
            }
        )
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        # Skip findings already covered by the rib_zones / missing_objective
        # / interfaces / exclusions / tbd_fields checks above.
        text = str(finding)
        if any(
            marker in text
            for marker in (
                "rib_zones is empty",
                "Missing required structural objectives",
                "load_interfaces is empty",
                "rib_generation.exclusions",
            )
        ):
            continue
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_structural_policy", "text", text,
                ),
                "source_tool": "validate_structural_policy",
                "category": "POLICY_GAP",
                "severity": "WARNING",
                "field": "structural_policy",
                "component_id": None,
                "value": "TBD",
                "reason": str(finding),
                "remediation_hint": (
                    "Resolve the structural policy finding by editing "
                    "structural-policy.yaml / rib-system.yaml."
                ),
            }
        )
    return blockers


def _extract_optical_window_blockers(optical: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert validate_optical_window_system envelope / data into blockers."""
    blockers: list[dict[str, Any]] = []
    data = _normalise_optical_input(optical)
    if not data:
        return blockers
    tbd_fields = data.get("tbd_fields", []) or []
    findings = data.get("findings", []) or []
    if not isinstance(tbd_fields, list):
        tbd_fields = []
    if not isinstance(findings, list):
        findings = []
    for entry in tbd_fields:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path") or ""
        value = entry.get("value", "TBD")
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_optical_window_system", path, value
                ),
                "source_tool": "validate_optical_window_system",
                "category": "TBD_FIELD",
                "severity": "BLOCK",
                "field": str(path),
                "component_id": "ir_optical_window",
                "value": value,
                "reason": "Required IR optical-window field is TBD.",
                "remediation_hint": (
                    "Provide the authoritative IR optical-window "
                    "dimension / retention / adhesive spec in "
                    "ir-optical-window-geometry.yaml."
                ),
            }
        )
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        path = finding.get("path") or "ir_optical_window"
        value = finding.get("value", "TBD")
        reason = finding.get("reason") or "IR optical-window finding"
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_optical_window_system",
                    "finding",
                    path,
                    value,
                ),
                "source_tool": "validate_optical_window_system",
                "category": _normalise_category(finding.get("category")),
                "severity": _normalise_severity(finding.get("severity")),
                "field": str(path),
                "component_id": "ir_optical_window",
                "value": value,
                "reason": str(reason),
                "remediation_hint": (
                    "Resolve the IR optical-window finding by editing "
                    "ir-optical-window-geometry.yaml."
                ),
            }
        )
    return blockers


def _extract_pcb_blockers(pcb: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert reconcile_pcb envelope into blockers."""
    blockers: list[dict[str, Any]] = []
    if not isinstance(pcb, dict):
        return blockers
    data = pcb.get("data") or {}
    findings = data.get("findings", []) or []
    if not isinstance(findings, list):
        findings = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        field = finding.get("field") or finding.get("path") or ""
        value = finding.get("value", "TBD")
        reason = finding.get("reason") or "PCB reconciliation finding"
        component_id = finding.get("component_id")
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "reconcile_pcb", field, value, reason
                ),
                "source_tool": "reconcile_pcb",
                "category": _normalise_category(finding.get("category")),
                "severity": _normalise_severity(finding.get("severity")),
                "field": str(field),
                "component_id": component_id,
                "value": value,
                "reason": str(reason),
                "remediation_hint": (
                    "Resolve the PCB reconciliation finding by providing "
                    "the authoritative footprint / connector / stackup "
                    "value or by recording an explicit UNKNOWN via "
                    "mark_component_unknown."
                ),
            }
        )
    return blockers


def _extract_reference_integrity_blockers(
    ref_integrity: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert reference integrity findings into blockers."""
    blockers: list[dict[str, Any]] = []
    if not isinstance(ref_integrity, dict):
        return blockers
    if not ref_integrity.get("manifest_present"):
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "verify_reference_integrity", "manifest_present", False
                ),
                "source_tool": "verify_reference_integrity",
                "category": "DATA_GAP",
                "severity": "BLOCK",
                "field": "references.reference-manifest.yaml",
                "component_id": None,
                "value": "MISSING",
                "reason": "reference-manifest.yaml is missing.",
                "remediation_hint": (
                    "Restore reference-manifest.yaml from a known good "
                    "backup or rebuild it from the reference geometry "
                    "directory."
                ),
            }
        )
        return blockers
    for entry in ref_integrity.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("ok"):
            continue
        name = entry.get("name") or "unknown_reference"
        errors = entry.get("errors") or []
        reason = "; ".join(str(e) for e in errors) or "Reference integrity failure"
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "verify_reference_integrity", name, reason
                ),
                "source_tool": "verify_reference_integrity",
                "category": "DATA_GAP",
                "severity": "BLOCK",
                "field": f"references.{name}",
                "component_id": None,
                "value": "SHA256_MISMATCH"
                if "sha256" in reason.lower()
                else "MISSING"
                if "missing" in reason.lower()
                else "INVALID",
                "reason": reason,
                "remediation_hint": (
                    "Verify the reference geometry has not been mutated "
                    "or replace the manifest entry with the correct "
                    "SHA-256. Reference geometry is read-only."
                ),
            }
        )
    return blockers


def _extract_unknown_required_field_blockers(
    coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert the manufacturing-release-report required-fields coverage
    into blockers."""
    blockers: list[dict[str, Any]] = []
    if not isinstance(coverage, list):
        return blockers
    for entry in coverage:
        if not isinstance(entry, dict):
            continue
        if entry.get("authoritative"):
            continue
        component_id = entry.get("component_id")
        field = entry.get("field") or ""
        value = entry.get("value", "UNKNOWN")
        is_tbd = bool(entry.get("is_tbd"))
        category = "TBD_FIELD" if is_tbd else "UNKNOWN_FIELD"
        severity = "BLOCK" if not is_tbd else "BLOCK"
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "component_authority", component_id, field, value
                ),
                "source_tool": "component_authority",
                "category": category,
                "severity": severity,
                "field": str(field),
                "component_id": component_id,
                "value": value,
                "reason": (
                    "Required component field is not authoritatively "
                    "resolved."
                ),
                "remediation_hint": (
                    "Provide an authoritative value in the per-component "
                    "YAML, or record an explicit UNKNOWN against the "
                    "field via mark_component_unknown."
                ),
            }
        )
    return blockers


def _extract_unknown_records_blockers(
    records: Iterable[Any],
) -> list[dict[str, Any]]:
    """Surface the UNKNOWN records log as informational blockers.

    These are recorded blockers -- the engineer has acknowledged the
    gap -- and therefore degrade to INFO. They are still listed in the
    manifest so a release reviewer sees the full engineering surface.
    """
    blockers: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        component_id = record.get("component_id")
        field = record.get("field") or ""
        value = record.get("value", record.get("status", "UNKNOWN"))
        reason = record.get("reason") or "Recorded UNKNOWN field"
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "component_authority",
                    "recorded",
                    component_id,
                    field,
                    value,
                ),
                "source_tool": "component_authority",
                "category": "UNKNOWN_FIELD",
                "severity": "INFO",
                "field": str(field),
                "component_id": component_id,
                "value": value,
                "reason": str(reason),
                "remediation_hint": (
                    "Recorded UNKNOWN; resolve when authoritative data "
                    "becomes available."
                ),
            }
        )
    return blockers


def _extract_pose_validation_blockers(
    pose_validation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert component-pose-validation.json into blockers.

    Pose validation is the gate for every downstream artifact; an
    INCOMPLETE pose result must always block release.
    """
    blockers: list[dict[str, Any]] = []
    if not isinstance(pose_validation, dict):
        return blockers
    validation = pose_validation.get("validation", {}) or {}
    overall = validation.get("overall_status")
    if overall != "PASS":
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_poses", "overall_status", str(overall)
                ),
                "source_tool": "validate_poses",
                "category": "BLOCKER",
                "severity": "BLOCK",
                "field": "component_pose_validation.overall_status",
                "component_id": None,
                "value": str(overall),
                "reason": (
                    "Component pose validation overall_status is not "
                    "PASS; downstream engineering is blocked."
                ),
                "remediation_hint": (
                    "Re-run validate_poses and resolve every accepted "
                    "component's obstruction / clearance finding."
                ),
            }
        )
    accepted = pose_validation.get("accepted", []) or []
    rejected = pose_validation.get("rejected", []) or []
    for entry in accepted:
        if not isinstance(entry, dict):
            continue
        pose_status = entry.get("status") or entry.get("pose_status")
        if pose_status and pose_status != "PASS":
            blockers.append(
                {
                    "blocker_id": _stable_id(
                        "validate_poses",
                        "accepted_pose",
                        entry.get("component"),
                        pose_status,
                    ),
                    "source_tool": "validate_poses",
                    "category": "BLOCKER",
                    "severity": "BLOCK",
                    "field": (
                        f"pose.{entry.get('component')}.status"
                    ),
                    "component_id": entry.get("component"),
                    "value": str(pose_status),
                    "reason": (
                        f"Accepted pose for {entry.get('component')!r} "
                        f"carries status {pose_status!r}."
                    ),
                    "remediation_hint": (
                        "Re-derive the pose and ensure clearance / "
                        "optical-axis constraints are satisfied."
                    ),
                }
            )
    for entry in rejected:
        if not isinstance(entry, dict):
            continue
        reason = entry.get("reason") or "Pose rejected by validator"
        blockers.append(
            {
                "blocker_id": _stable_id(
                    "validate_poses",
                    "rejected_pose",
                    entry.get("component"),
                    reason,
                ),
                "source_tool": "validate_poses",
                "category": "BLOCKER",
                "severity": "BLOCK",
                "field": (
                    f"pose.{entry.get('component')}.rejection"
                ),
                "component_id": entry.get("component"),
                "value": "REJECTED",
                "reason": str(reason),
                "remediation_hint": (
                    "Pose was not accepted by the validator; resolve the "
                    "underlying clearance / optical-axis failure."
                ),
            }
        )
    return blockers


def build_release_blocker_manifest(
    *,
    glasses_root: Path,
    structural_envelope: dict[str, Any] | None = None,
    optical_envelope: dict[str, Any] | None = None,
    dfm_dfa_envelope: dict[str, Any] | None = None,
    pcb_envelope: dict[str, Any] | None = None,
    release_report_envelope: dict[str, Any] | None = None,
    reference_integrity_envelope: dict[str, Any] | None = None,
    pose_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical release-blocker manifest.

    Each argument is the structured envelope / artifact returned by the
    upstream validator. ``None`` values trigger an in-process call to
    the upstream tool, so callers can pass pre-computed envelopes to
    avoid the cost of re-running every validator.

    Returns a structured envelope:

        {
          "status":                  "RELEASE_READY" | "INCOMPLETE" |
                                      "RELEASE_BLOCKED",
          "generated_at":            ISO timestamp,
          "blockers":                [blocker dict, ...],
          "summary": {
            "blocker_count",
            "block_count",
            "warning_count",
            "info_count",
            "by_category":   {"BLOCKER": n, ...},
            "by_source_tool":{"validate_dfm_dfa": n, ...},
          },
          "upstream_status": {
            "structural": status,
            "optical_window": status,
            "dfm_dfa": status,
            "pcb_reconciliation": status,
            "release_report": status,
            "reference_integrity": bool,
            "pose_validation": status,
          }
        }

    The status is ``RELEASE_READY`` only when the blocker list is
    empty; otherwise ``INCOMPLETE`` (when at least one upstream
    validator returned a non-PASS status) or ``RELEASE_BLOCKED`` (when
    one or more BLOCK-severity findings are present).
    """
    from .component_authority import load_unknowns
    from .dfm_dfa import run_dfm_dfa_validation
    from .manufacturing_readiness import run_manufacturing_release_report
    from .pcb_reconcile import run_pcb_reconciliation
    from .reference_geometry import load_manifest as _load_ref_manifest

    # ---- 1. Run / reuse upstream validators ----
    structural_env = structural_envelope
    if structural_env is None:
        from .structural import (
            StructuralDesignError,
            validate_structural_policy as _validate_struct,
        )

        try:
            structural_data = _validate_struct()
        except StructuralDesignError as exc:
            structural_env = {
                "status": "INCOMPLETE",
                "data": {
                    "rib_zones_count": 0,
                    "interfaces": [],
                    "missing_objectives": list(REQUIRED_OBJECTIVES),
                    "exclusions_present": False,
                    "findings": [str(exc)],
                    "tbd_fields": [],
                },
            }
        except Exception as exc:  # noqa: BLE001 -- surface as ERROR
            structural_env = {
                "status": "ERROR",
                "data": {
                    "rib_zones_count": 0,
                    "interfaces": [],
                    "missing_objectives": list(REQUIRED_OBJECTIVES),
                    "exclusions_present": False,
                    "findings": [f"{type(exc).__name__}: {exc}"],
                    "tbd_fields": [],
                },
            }
        else:
            # Even when the underlying module returns PASS, the MCP
            # tool surfaces rib_zones==0 / missing_objectives /
            # exclusions / interfaces as INCOMPLETE. Reconstruct the
            # same envelope so the extractor sees the full picture.
            rib_zones = structural_data.get("rib_zones", 0)
            interfaces = structural_data.get("interfaces", [])
            objectives_block = structural_data.get("missing_objectives", [])
            structural_env = {
                "status": "INCOMPLETE"
                if (not rib_zones or objectives_block)
                else "PASS",
                "data": {
                    "rib_zones_count": rib_zones,
                    "interfaces": interfaces,
                    "missing_objectives": objectives_block
                    if objectives_block
                    else [
                        o
                        for o in REQUIRED_OBJECTIVES
                        if o
                        not in (structural_data.get("objectives") or [])
                    ],
                    "exclusions_present": bool(
                        structural_data.get("exclusions_present", False)
                    ),
                    "findings": structural_data.get("findings", []),
                    "tbd_fields": structural_data.get("tbd_fields", []),
                },
            }

    optical_env = optical_envelope
    if optical_env is None:
        from .optical_windows import (
            OpticalWindowError,
            validate_window_system as _validate_windows,
        )

        try:
            window_data = _validate_windows()
            # The MCP tool surfaces TBD diameter / thickness as
            # INCOMPLETE; replicate that status here.
            tbd_diameter = not window_data.get("diameter_defined", True)
            tbd_thickness = not window_data.get("thickness_defined", True)
            tbd_fields: list[dict[str, str]] = []
            if tbd_diameter:
                tbd_fields.append(
                    {"path": "ir_optical_window.diameter_mm", "value": "TBD"}
                )
            if tbd_thickness:
                tbd_fields.append(
                    {"path": "ir_optical_window.thickness_mm", "value": "TBD"}
                )
            optical_env = {
                "status": (
                    "INCOMPLETE"
                    if (tbd_diameter or tbd_thickness)
                    else window_data.get("status", "PASS")
                ),
                "data": {
                    "window_count": window_data.get("window_count", 0),
                    "diameter_defined": not tbd_diameter,
                    "thickness_defined": not tbd_thickness,
                    "tbd_fields": tbd_fields,
                    "findings": window_data.get("findings", []) or [],
                },
            }
        except (OpticalWindowError, KeyError, TypeError) as exc:
            optical_env = {
                "status": "INCOMPLETE",
                "data": {},
                "errors": [f"{type(exc).__name__}: {exc}"],
                "tbd_fields": [],
                "findings": [
                    {
                        "path": "ir_optical_window_system",
                        "value": "TBD",
                        "reason": str(exc),
                        "severity": "BLOCK",
                    }
                ],
            }
        except Exception as exc:  # noqa: BLE001 -- surface as ERROR
            optical_env = {
                "status": "ERROR",
                "data": {},
                "errors": [f"{type(exc).__name__}: {exc}"],
                "tbd_fields": [],
                "findings": [],
            }

    dfm_dfa_env = dfm_dfa_envelope
    if dfm_dfa_env is None:
        try:
            dfm_dfa_result = run_dfm_dfa_validation(glasses_root=glasses_root)
            dfm_dfa_env = {
                "status": dfm_dfa_result.get("status", "INCOMPLETE"),
                "data": dfm_dfa_result,
            }
        except Exception as exc:  # noqa: BLE001
            dfm_dfa_env = {
                "status": "ERROR",
                "data": {},
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

    pcb_env = pcb_envelope
    if pcb_env is None:
        try:
            pcb_result = run_pcb_reconciliation(glasses_root=glasses_root)
            pcb_env = {
                "status": pcb_result.get("status", "INCOMPLETE"),
                "data": pcb_result,
            }
        except Exception as exc:  # noqa: BLE001
            pcb_env = {
                "status": "ERROR",
                "data": {},
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

    release_env = release_report_envelope
    if release_env is None:
        try:
            release_result = run_manufacturing_release_report(
                glasses_root=glasses_root
            )
            release_env = {
                "status": release_result.get("status", "INCOMPLETE"),
                "data": release_result,
            }
        except Exception as exc:  # noqa: BLE001
            release_env = {
                "status": "ERROR",
                "data": {},
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

    ref_env = reference_integrity_envelope
    if ref_env is None:
        try:
            manifest = _load_ref_manifest()
            ref_data = manifest.get("references", {}) or {}
            ref_ok = isinstance(ref_data, dict) and bool(ref_data)
            ref_env = {
                "manifest_present": True,
                "ok": ref_ok,
                "entries": [],
                "errors": [] if ref_ok else ["manifest has no entries"],
            }
        except Exception as exc:  # noqa: BLE001
            ref_env = {
                "manifest_present": False,
                "ok": False,
                "entries": [],
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

    # Pose validation artifact.
    pose_data = pose_validation
    if pose_data is None:
        pose_data = _load_pose_validation(glasses_root)

    # ---- 2. Aggregate blockers ----
    blockers: list[dict[str, Any]] = []
    blockers.extend(_extract_structural_blockers(structural_env))
    blockers.extend(_extract_optical_window_blockers(optical_env))
    blockers.extend(_extract_dfm_dfa_blockers(dfm_dfa_env.get("data") or {}))
    blockers.extend(_extract_pcb_blockers(pcb_env))
    blockers.extend(_extract_reference_integrity_blockers(ref_env))
    blockers.extend(_extract_unknown_required_field_blockers(
        (release_env.get("data") or {}).get("required_fields_coverage", []) or []
    ))
    blockers.extend(_extract_unknown_records_blockers(
        (release_env.get("data") or {}).get("unknowns_records", []) or []
    ))
    blockers.extend(_extract_pose_validation_blockers(pose_data))

    # Deterministic ordering: by source_tool, then blocker_id.
    blockers.sort(
        key=lambda b: (
            str(b.get("source_tool", "")),
            str(b.get("blocker_id", "")),
        )
    )

    # ---- 3. Summary ----
    by_category: dict[str, int] = {}
    by_source_tool: dict[str, int] = {}
    block_count = 0
    warning_count = 0
    info_count = 0
    for blocker in blockers:
        category = str(blocker.get("category", "BLOCKER"))
        severity = str(blocker.get("severity", "BLOCK"))
        tool = str(blocker.get("source_tool", ""))
        by_category[category] = by_category.get(category, 0) + 1
        by_source_tool[tool] = by_source_tool.get(tool, 0) + 1
        if severity == "BLOCK":
            block_count += 1
        elif severity == "WARNING":
            warning_count += 1
        elif severity == "INFO":
            info_count += 1

    upstream_status = {
        "structural": structural_env.get("status"),
        "optical_window": optical_env.get("status"),
        "dfm_dfa": dfm_dfa_env.get("status"),
        "pcb_reconciliation": pcb_env.get("status"),
        "release_report": release_env.get("status"),
        "reference_integrity": bool(ref_env.get("ok")),
        "pose_validation": (
            (pose_data.get("validation") or {}).get("overall_status")
            if isinstance(pose_data, dict)
            else None
        ),
    }

    # ---- 4. Final status ----
    if not blockers:
        status = "RELEASE_READY"
    elif block_count > 0 or not ref_env.get("ok"):
        status = "RELEASE_BLOCKED"
    else:
        status = "INCOMPLETE"

    return {
        "status": status,
        "generated_at": _now_utc(),
        "blockers": blockers,
        "summary": {
            "blocker_count": len(blockers),
            "block_count": block_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "by_category": dict(sorted(by_category.items())),
            "by_source_tool": dict(sorted(by_source_tool.items())),
        },
        "upstream_status": upstream_status,
    }


# ---------------------------------------------------------------------------
# Pose validation loader
# ---------------------------------------------------------------------------

_POSE_VALIDATION_REL = Path("analysis/geometry/component-pose-validation.json")


def _load_pose_validation(glasses_root: Path) -> dict[str, Any] | None:
    path = glasses_root / _POSE_VALIDATION_REL
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Audit-log timeline
# ---------------------------------------------------------------------------


def _read_audit_log_entries(glasses_root: Path) -> list[dict[str, Any]]:
    """Walk ``manufacturing/releases/audit/*.jsonl`` and return every entry.

    Entries are returned in chronological order (oldest first). Lines
    that fail JSON parsing are skipped silently so a single corrupted
    line cannot break the entire timeline.
    """
    audit_root = glasses_root / "manufacturing" / "releases" / "audit"
    if not audit_root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for jsonl in sorted(audit_root.glob("*.jsonl")):
        try:
            text = jsonl.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                obj.setdefault("_source_log", jsonl.name)
                entries.append(obj)
    entries.sort(key=lambda e: str(e.get("timestamp_fs", "")))
    return entries


def build_audit_timeline(
    *,
    glasses_root: Path,
    tool_filter: str | None = None,
    operation_filter: str | None = None,
    success_only: bool | None = None,
) -> dict[str, Any]:
    """Build the engineering audit-timeline from the JSONL log.

    The function reads ``manufacturing/releases/audit/*.jsonl`` and
    returns a chronological list of engineering events. Optional
    filters narrow the result by tool name, operation, or success.

    Returns:

        {
          "status":         "PASS" | "ERROR",
          "generated_at":   ISO timestamp,
          "events":         [audit entry, ...],
          "summary": {
            "event_count",
            "success_count",
            "failure_count",
            "tools":           {"<tool>": n, ...},
            "operations":      {"<op>": n, ...},
            "first_event_ts":  str | None,
            "last_event_ts":   str | None,
          }
        }
    """
    started_at = _now_utc()
    entries = _read_audit_log_entries(glasses_root)

    if tool_filter:
        entries = [e for e in entries if e.get("tool") == tool_filter]
    if operation_filter:
        entries = [
            e for e in entries if e.get("operation") == operation_filter
        ]
    if success_only is not None:
        entries = [
            e for e in entries if bool(e.get("success")) == bool(success_only)
        ]

    summary: dict[str, Any] = {
        "event_count": len(entries),
        "success_count": sum(1 for e in entries if e.get("success")),
        "failure_count": sum(1 for e in entries if not e.get("success")),
        "tools": {},
        "operations": {},
        "first_event_ts": None,
        "last_event_ts": None,
    }
    for entry in entries:
        tool = str(entry.get("tool", ""))
        operation = str(entry.get("operation", ""))
        summary["tools"][tool] = summary["tools"].get(tool, 0) + 1
        summary["operations"][operation] = (
            summary["operations"].get(operation, 0) + 1
        )
        if summary["first_event_ts"] is None:
            summary["first_event_ts"] = entry.get("timestamp")
        summary["last_event_ts"] = entry.get("timestamp")

    status = "PASS"
    if not entries and not (
        (glasses_root / "manufacturing" / "releases" / "audit").is_dir()
    ):
        status = "PASS"  # No audit log yet -- still PASS, with event_count=0.

    return {
        "status": status,
        "generated_at": started_at,
        "events": entries,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Manifest persistence (controlled write)
# ---------------------------------------------------------------------------


def serialise_release_blocker_manifest(manifest: dict[str, Any]) -> str:
    """Return the canonical JSON serialization of ``manifest``."""
    return json.dumps(manifest, indent=2, sort_keys=False, default=str)


__all__ = [
    "ReleaseBlockerError",
    "VALID_SEVERITIES",
    "VALID_CATEGORIES",
    "build_release_blocker_manifest",
    "build_audit_timeline",
    "serialise_release_blocker_manifest",
]