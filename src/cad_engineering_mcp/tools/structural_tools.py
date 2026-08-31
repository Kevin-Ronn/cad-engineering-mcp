"""Phase 3 structural-policy MCP tool: ``validate_structural_policy``.

Wraps :mod:`cad_engineering_mcp.engineering.structural` to produce a
Phase-3 envelope with the structured findings required by the
directive:

    {
      status,
      missing_objectives,
      rib_zones_count,
      interfaces,
      tbd_fields,
      findings
    }

This tool never mutates the workspace; it is a read-only validator.

Engineering rule (from the directive):

    "Because rib_zones is currently empty, the expected result should
     be INCOMPLETE rather than PASS."

So the tool's default outcome is ``INCOMPLETE`` whenever the rib
system has zero ``rib_zones`` entries, regardless of whether the YAML
parses successfully.

The required structural objectives are taken from
``design_intent.objective`` in ``structural-policy.yaml``. Any objective
that the production engineering team has not yet defined (or has marked
``TBD``) is reported as a ``tbd_field`` finding.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..engineering.structural import (
    StructuralDesignError,
    load_rib_system,
    load_structural_policy,
)
from ._envelope import make_envelope, utcnow_iso
from ._paths import PathSecurityError, glasses_root, safe_resolve


# Production-engineering objectives that the directive requires us to
# verify. These are the same set :func:`structural.validate_structural_policy`
# checks; we redeclare them here so the Phase-3 tool can compute
# ``missing_objectives`` even when the underlying engineering module
# raises early.
REQUIRED_OBJECTIVES: tuple[str, ...] = (
    "minimum_structural_mass",
    "minimum_wall_thickness",
    "maximum_required_stiffness",
    "maintain_serviceability",
)


def _is_tbd(value: Any) -> bool:
    """True iff ``value`` is the literal string ``"TBD"`` (case-insensitive).

    YAML commonly uses ``TBD`` as a sentinel for not-yet-defined
    values; the directive explicitly requires us to surface these.
    """
    if isinstance(value, str):
        return value.strip().upper() == "TBD"
    return False


def _collect_tbd_fields(node: Any, *, path: str = "") -> list[dict[str, str]]:
    """Walk ``node`` and collect every leaf whose value is the ``TBD`` sentinel."""
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


def validate_structural_policy() -> dict[str, Any]:
    """Validate the structural-policy and rib-system YAML manifests.

    Returns a structured envelope with:

    * ``status``               ``PASS`` | ``INCOMPLETE`` | ``FAIL`` | ``ERROR``
    * ``missing_objectives``   list of required objectives not present in the
                               ``design_intent.objective`` array
    * ``rib_zones_count``      number of rib zones defined in
                               ``rib-system.yaml``
    * ``interfaces``           list of load-interface names from
                               ``structural-policy.yaml``
    * ``tbd_fields``           every leaf in the structural YAML whose value
                               is the literal ``TBD`` sentinel
    * ``findings``             human-readable list of findings, including
                               empty rib zones and other INCOMPLETE markers
    """
    started = utcnow_iso()

    # Resolve the two YAML paths through safe_resolve so symlink escapes
    # are rejected before we even try to read them.
    try:
        policy_path = safe_resolve(
            Path("mechanical/main-frame/structural-policy.yaml")
        )
    except PathSecurityError as exc:
        return make_envelope(
            tool="validate_structural_policy",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )
    try:
        rib_path = safe_resolve(Path("mechanical/ribs/rib-system.yaml"))
    except PathSecurityError as exc:
        return make_envelope(
            tool="validate_structural_policy",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # Parse both files; YAML parse errors are surfaced as ERROR.
    try:
        policy_text = policy_path.read_text(encoding="utf-8")
        policy_doc = yaml.safe_load(policy_text)
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        return make_envelope(
            tool="validate_structural_policy",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={
                "policy_path": str(policy_path.relative_to(glasses_root())),
            },
            errors=[f"Structural policy YAML unreadable: {exc}"],
        )
    try:
        rib_text = rib_path.read_text(encoding="utf-8")
        rib_doc = yaml.safe_load(rib_text)
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        return make_envelope(
            tool="validate_structural_policy",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"rib_path": str(rib_path.relative_to(glasses_root()))},
            errors=[f"Rib-system YAML unreadable: {exc}"],
        )

    if not isinstance(policy_doc, dict):
        return make_envelope(
            tool="validate_structural_policy",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                "structural-policy.yaml root must be a mapping; "
                f"got {type(policy_doc).__name__}."
            ],
        )
    if not isinstance(rib_doc, dict):
        return make_envelope(
            tool="validate_structural_policy",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[
                "rib-system.yaml root must be a mapping; "
                f"got {type(rib_doc).__name__}."
            ],
        )

    # Required production-engineering objectives.
    objectives: list[str] = []
    design_intent = policy_doc.get("design_intent", {}) or {}
    if isinstance(design_intent, dict):
        raw_objectives = design_intent.get("objective", [])
        if isinstance(raw_objectives, list):
            objectives = [str(o) for o in raw_objectives if isinstance(o, str)]
    missing_objectives = [o for o in REQUIRED_OBJECTIVES if o not in objectives]

    # Load interfaces (mounting interfaces represented).
    interfaces_raw = policy_doc.get("load_interfaces", []) or []
    interfaces: list[str] = []
    if isinstance(interfaces_raw, list):
        interfaces = [str(i) for i in interfaces_raw if isinstance(i, str)]

    # Rib zones.
    rib_zones = rib_doc.get("rib_zones", {}) or {}
    rib_zones_count = (
        len(rib_zones) if isinstance(rib_zones, dict) else 0
    )

    # TBD fields: walk both YAMLs.
    tbd_fields = _collect_tbd_fields(policy_doc, path="structural_policy")
    tbd_fields.extend(_collect_tbd_fields(rib_doc, path="rib_system"))

    # Required exclusions in rib_generation must be present and non-empty.
    rib_generation = rib_doc.get("rib_generation", {}) or {}
    exclusions = rib_generation.get("exclusions") if isinstance(
        rib_generation, dict
    ) else None
    exclusions_ok = isinstance(exclusions, list) and len(exclusions) > 0

    findings: list[str] = []
    status = "PASS"

    if missing_objectives:
        status = "INCOMPLETE"
        findings.append(
            "Missing required structural objectives: "
            + ", ".join(missing_objectives)
        )
    if rib_zones_count == 0:
        status = "INCOMPLETE"
        findings.append(
            "rib_zones is empty; localized reinforcement has not been "
            "defined. Structural design is INCOMPLETE."
        )
    if not interfaces:
        status = "INCOMPLETE"
        findings.append(
            "load_interfaces is empty; no mounting interfaces are "
            "represented in structural-policy.yaml."
        )
    if not exclusions_ok:
        status = "INCOMPLETE"
        findings.append(
            "rib_generation.exclusions is missing or empty; rib "
            "keep-outs have not been enumerated."
        )
    if tbd_fields:
        # TBD values do not by themselves cause INCOMPLETE if every other
        # check passed; we surface them as findings regardless.
        findings.append(
            f"Found {len(tbd_fields)} TBD field(s) across the structural "
            "YAMLs."
        )

    return make_envelope(
        tool="validate_structural_policy",
        started_at_iso=started,
        duration_ms=0,
        status=status,
        data={
            "policy_path": str(policy_path.relative_to(glasses_root())),
            "rib_path": str(rib_path.relative_to(glasses_root())),
            "missing_objectives": missing_objectives,
            "rib_zones_count": rib_zones_count,
            "interfaces": interfaces,
            "tbd_fields": tbd_fields,
            "findings": findings,
            "exclusions_present": exclusions_ok,
        },
    )