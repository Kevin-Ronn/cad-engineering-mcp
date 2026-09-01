"""Phase 4 MCP tools: DFM/DFA, PCB reconciliation, and manufacturing readiness.

This module is the MCP surface for the Phase 4 engineering-data
layer. It exposes three tools:

* :func:`validate_dfm_dfa` — runs the DFM and DFA checks against
  the project YAML manifests and returns a structured report.
* :func:`reconcile_pcb` — runs the PCB architecture reconciliation
  and returns the derived outline plus a list of UNKNOWN/TBD
  fields.
* :func:`manufacturing_release_report` — aggregates the upstream
  validators into a single release-readiness report.

All three tools are read-only; they never mutate the workspace.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..engineering.dfm_dfa import DfmDfaError, run_dfm_dfa_validation
from ..engineering.manufacturing_readiness import (
    run_manufacturing_release_report,
)
from ..engineering.pcb_reconcile import PcbReconcileError, run_pcb_reconciliation
from ._envelope import make_envelope, utcnow_iso
from ._mutation import (
    MutationError,
    audit,
    safe_destination,
    utc_timestamp_fs,
)
from ._paths import PathSecurityError, glasses_root


def validate_dfm_dfa() -> dict[str, Any]:
    """Run the DFM/DFA checks across the project YAML manifests.

    Read-only. Returns a structured envelope with the per-rule
    findings, the combined DFM/DFA status, and the TBD field scan.
    """
    started = utcnow_iso()
    try:
        result = run_dfm_dfa_validation(glasses_root=glasses_root())
    except (DfmDfaError, OSError) as exc:
        return make_envelope(
            tool="validate_dfm_dfa",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="validate_dfm_dfa",
        started_at_iso=started,
        duration_ms=0,
        status=result.get("status", "INCOMPLETE"),
        data=result,
    )


def reconcile_pcb() -> dict[str, Any]:
    """Reconcile the PCB architecture against the mechanical envelope.

    Read-only. Returns the derived outline, the existing outline
    (when defined), the fitted-in-frame verdict, the component
    envelopes, and a list of UNKNOWN/TBD findings that block a
    production-ready release.
    """
    started = utcnow_iso()
    try:
        result = run_pcb_reconciliation(glasses_root=glasses_root())
    except (PcbReconcileError, OSError) as exc:
        return make_envelope(
            tool="reconcile_pcb",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="reconcile_pcb",
        started_at_iso=started,
        duration_ms=0,
        status=result.get("status", "INCOMPLETE"),
        data=result,
    )


def manufacturing_release_report() -> dict[str, Any]:
    """Build the Phase 4 manufacturing-readiness release report.

    Combines reference integrity, DFM/DFA, PCB reconciliation, and
    component-data UNKNOWN/TBD coverage. Read-only. The status is
    ``RELEASE_READY`` only when every upstream validator has
    PASSed AND every required component field is authoritative.
    """
    started = utcnow_iso()
    try:
        result = run_manufacturing_release_report(glasses_root=glasses_root())
    except (OSError, ValueError) as exc:
        return make_envelope(
            tool="manufacturing_release_report",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="manufacturing_release_report",
        started_at_iso=started,
        duration_ms=0,
        status=result.get("status", "INCOMPLETE"),
        data=result,
    )


def save_manufacturing_release_report(
    destination: str = "manufacturing/releases/manufacturing-readiness.json",
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Persist the manufacturing-readiness report under ``manufacturing/releases/``.

    Dry-run by default. The tool refuses to mutate unless
    ``allow_mutation=true``. Every write is backed up under
    ``manufacturing/releases/<UTC>/`` and audit-logged.
    """
    started = utcnow_iso()
    timestamp = utc_timestamp_fs()
    try:
        report = run_manufacturing_release_report(glasses_root=glasses_root())
    except (OSError, ValueError) as exc:
        return make_envelope(
            tool="save_manufacturing_release_report",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    payload = json.dumps(report, indent=2, sort_keys=False, default=str)

    if not allow_mutation:
        audit(
            timestamp=timestamp,
            tool="save_manufacturing_release_report",
            operation="no_mutation_dry_run",
            affected_paths=[destination],
            success=True,
            metadata={
                "would_write_bytes": len(payload),
                "allow_mutation": False,
                "status": report.get("status"),
            },
        )
        return make_envelope(
            tool="save_manufacturing_release_report",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "allow_mutation": False,
                "path": destination,
                "would_write_bytes": len(payload),
                "report_status": report.get("status"),
            },
            warnings=[
                "allow_mutation=False; report was not written. "
                "Pass allow_mutation=true to commit."
            ],
        )

    # allow_mutation=True path.
    try:
        dest_path = safe_destination(destination)
    except MutationError as exc:
        return make_envelope(
            tool="save_manufacturing_release_report",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    from ._mutation import (
        audit as _audit,
        atomic_write_text,
        backup_existing,
        file_metadata,
    )

    backup = backup_existing(timestamp, source=dest_path)
    backup_rel = (
        str(backup.relative_to(glasses_root())) if backup else None
    )

    try:
        atomic_write_text(dest_path, payload)
    except Exception as exc:  # noqa: BLE001
        _audit(
            timestamp=timestamp,
            tool="save_manufacturing_release_report",
            operation="add",
            affected_paths=[destination],
            success=False,
            metadata={"backup": backup_rel},
            errors=[f"Write failed: {type(exc).__name__}: {exc}"],
        )
        return make_envelope(
            tool="save_manufacturing_release_report",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"Write failed: {type(exc).__name__}: {exc}"],
        )

    after_meta = file_metadata(dest_path)
    _audit(
        timestamp=timestamp,
        tool="save_manufacturing_release_report",
        operation="add",
        affected_paths=[destination],
        success=True,
        metadata={
            "report_status": report.get("status"),
            "backup": backup_rel,
            "after_sha256": after_meta.get("sha256"),
            "bytes": after_meta.get("bytes"),
        },
    )
    return make_envelope(
        tool="save_manufacturing_release_report",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "executed": True,
            "allow_mutation": True,
            "path": str(dest_path.relative_to(glasses_root())),
            "report_status": report.get("status"),
            "backup": backup_rel,
            "after_sha256": after_meta.get("sha256"),
            "bytes": after_meta.get("bytes"),
        },
    )
