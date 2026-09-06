"""Phase 4 MCP tools for component authority and UNKNOWN-field tracking.

Two tools:

  * ``mark_component_unknown`` records an explicit UNKNOWN/TBD entry
    for a component field. Uses the existing Phase 3 backup + audit
    infrastructure. Refuses to overwrite a known authoritative value
    and refuses to record against an unrecognised component or field.

  * ``resolve_component_field`` looks up a component field through the
    canonical source order (registry → per-component YAML → analysis
    JSON → policy YAML → measured reference geometry). Returns
    ``value``, ``source``, ``authoritative``, and ``sources_checked``.
    Never invents a value: when the field is unresolved, returns
    ``value="UNKNOWN"``.

Both tools use the existing structured envelope and never execute
arbitrary shell commands.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engineering.component_authority import (
    ComponentAuthorityError,
    KNOWN_COMPONENT_IDS,
    append_unknown_record,
    is_recognised_field,
    load_unknowns,
    mark_component_unknown,
    resolve_component_field as _resolve,
)
from ._envelope import make_envelope, utcnow_iso
from ._mutation import (
    MutationError,
    audit,
    safe_destination,
    utc_timestamp_fs,
)
from ._paths import PathSecurityError, glasses_root


UNKNOWN_REL = Path("components/component-unknowns.yaml")


def list_known_component_ids() -> dict[str, Any]:
    """Read-only helper used by tests and callers."""
    started = utcnow_iso()
    return make_envelope(
        tool="list_known_component_ids",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "component_ids": sorted(KNOWN_COMPONENT_IDS),
            "count": len(KNOWN_COMPONENT_IDS),
        },
    )


def list_component_unknowns() -> dict[str, Any]:
    """Return all UNKNOWN/TBD records currently on file."""
    started = utcnow_iso()
    try:
        glasses = glasses_root()
        doc = load_unknowns(glasses_root=glasses)
    except PathSecurityError as exc:
        return make_envelope(
            tool="list_component_unknowns",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )
    records = doc.get("records", []) or []
    return make_envelope(
        tool="list_component_unknowns",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "path": str(UNKNOWN_REL),
            "schema_version": doc.get("schema_version"),
            "count": len(records),
            "records": records,
        },
    )


def mark_component_unknown(
    component_id: str,
    field: str,
    *,
    reason: str,
    source: str | None = None,
    notes: str | None = None,
    status: str = "UNKNOWN",
    force: bool = False,
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Record an UNKNOWN entry for ``component_id.field``.

    Parameters
    ----------
    component_id:
        Known component id (must be in :data:`KNOWN_COMPONENT_IDS` or
        in a per-component YAML ``component.id``).
    field:
        Recognised component field path (see module docstring).
    reason:
        Free-text engineering reason for the gap (required).
    source:
        Optional provenance tag (where the gap was identified).
    notes:
        Optional free-text notes.
    status:
        Either ``"UNKNOWN"`` or ``"TBD"``. Default ``"UNKNOWN``.
    force:
        When ``True``, a duplicate ``(component_id, field)`` record is
        replaced instead of rejected. Force never bypasses the
        "authoritative value exists" check.
    allow_mutation:
        When ``False`` (the default), the tool runs in dry-run mode
        and records the proposed entry in the audit log without
        writing the file.

    Engineering rules:

    * Never overwrite an authoritative value with UNKNOWN.
    * Never record against an unrecognised component or field.
    * Duplicate records are rejected unless ``force=True``.
    * All writes are backed up and audit-logged.
    """
    started = utcnow_iso()
    timestamp = utc_timestamp_fs()
    errors: list[str] = []
    warnings: list[str] = []

    if not allow_mutation:
        try:
            record = mark_component_unknown(
                component_id=component_id,
                field=field,
                reason=reason,
                glasses_root=glasses_root(),
                source=source,
                notes=notes,
                status=status,
                timestamp=timestamp,
            )
        except ComponentAuthorityError as exc:
            return make_envelope(
                tool="mark_component_unknown",
                started_at_iso=started,
                duration_ms=0,
                status="ERROR",
                errors=[str(exc)],
            )
        audit(
            timestamp=timestamp,
            tool="mark_component_unknown",
            operation="no_mutation_dry_run",
            affected_paths=[UNKNOWN_REL.as_posix()],
            success=True,
            metadata={
                "would_record": record,
                "force": force,
                "allow_mutation": False,
            },
        )
        return make_envelope(
            tool="mark_component_unknown",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "allow_mutation": False,
                "force": force,
                "would_record": record,
                "path": str(UNKNOWN_REL),
            },
            warnings=[
                "allow_mutation=False; record was not written. "
                "Pass allow_mutation=true to commit."
            ],
        )

    # allow_mutation=True path
    glasses = glasses_root()
    try:
        record = mark_component_unknown(
            component_id=component_id,
            field=field,
            reason=reason,
            glasses_root=glasses,
            source=source,
            notes=notes,
            status=status,
            timestamp=timestamp,
        )
    except ComponentAuthorityError as exc:
        return make_envelope(
            tool="mark_component_unknown",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # Check for duplicate unless force=True.
    existing_doc = load_unknowns(glasses_root=glasses)
    duplicate_index: int | None = None
    for index, entry in enumerate(existing_doc.get("records", []) or []):
        if (
            isinstance(entry, dict)
            and entry.get("component_id") == record["component_id"]
            and entry.get("field") == record["field"]
        ):
            duplicate_index = index
            break
    if duplicate_index is not None and not force:
        return make_envelope(
            tool="mark_component_unknown",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"component_id": component_id, "field": record["field"]},
            errors=[
                f"UNKNOWN record already exists for "
                f"({component_id!r}, {record['field']!r}); pass "
                "force=true to overwrite."
            ],
        )

    # Resolve safe destination + atomic write + backup + audit.
    try:
        destination = safe_destination(UNKNOWN_REL)
    except MutationError as exc:
        return make_envelope(
            tool="mark_component_unknown",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # Build the doc.
    if duplicate_index is not None and force:
        records = list(existing_doc.get("records", []) or [])
        records[duplicate_index] = record
        warnings.append(
            "force=true replaced an existing UNKNOWN record."
        )
    else:
        records = list(existing_doc.get("records", []) or [])
        records.append(record)
    doc = {
        "schema_version": 1,
        "records": records,
    }

    # Backup the existing file (if any) via the standard infrastructure.
    from ._mutation import (
        audit as _audit,
        backup_existing,
        atomic_write_text,
        file_metadata,
    )

    backup = backup_existing(timestamp, source=destination)
    backup_rel = (
        str(backup.relative_to(glasses_root())) if backup else None
    )

    try:
        import yaml

        atomic_write_text(
            destination,
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        )
    except Exception as exc:  # noqa: BLE001
        _audit(
            timestamp=timestamp,
            tool="mark_component_unknown",
            operation="add",
            affected_paths=[UNKNOWN_REL.as_posix()],
            success=False,
            metadata={
                "component_id": component_id,
                "field": record["field"],
                "backup": backup_rel,
            },
            errors=[f"Write failed: {type(exc).__name__}: {exc}"],
        )
        return make_envelope(
            tool="mark_component_unknown",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"Write failed: {type(exc).__name__}: {exc}"],
        )

    after_meta = (
        file_metadata(destination) if destination.is_file() else None
    )

    _audit(
        timestamp=timestamp,
        tool="mark_component_unknown",
        operation="add" if duplicate_index is None else "replace",
        affected_paths=[UNKNOWN_REL.as_posix()],
        success=True,
        metadata={
            "component_id": component_id,
            "field": record["field"],
            "status": record["status"],
            "backup": backup_rel,
            "force": force,
            "after_sha256": (after_meta or {}).get("sha256"),
        },
    )

    return make_envelope(
        tool="mark_component_unknown",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "executed": True,
            "allow_mutation": True,
            "force": force,
            "record": record,
            "path": str(UNKNOWN_REL),
            "backup": backup_rel,
            "duplicate_replaced": duplicate_index is not None and force,
            "record_count": len(doc["records"]),
            "after_sha256": (after_meta or {}).get("sha256"),
        },
        warnings=warnings,
    )


def resolve_component_field(
    component_id: str,
    field: str,
) -> dict[str, Any]:
    """Look up a component field through the canonical source order.

    Returns a structured envelope with the resolved value, source,
    authoritative flag, and the list of sources that were inspected.
    When no source carries a concrete value the result has
    ``value="UNKNOWN"`` and ``source="UNKNOWN"``; the function never
    invents a value.
    """
    started = utcnow_iso()
    try:
        glasses = glasses_root()
        result = _resolve(
            component_id=component_id,
            field=field,
            glasses_root=glasses,
        )
    except ComponentAuthorityError as exc:
        return make_envelope(
            tool="resolve_component_field",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # ``authoritative`` is False for analysis-artifact provisional
    # values; callers can distinguish:
    status = "PASS"
    if result.get("value") == "UNKNOWN":
        status = "INCOMPLETE"
    return make_envelope(
        tool="resolve_component_field",
        started_at_iso=started,
        duration_ms=0,
        status=status,
        data={
            "component_id": result["component_id"],
            "field": result["field"],
            "value": result["value"],
            "source": result["source"],
            "authoritative": result["authoritative"],
            "sources_checked": result["sources_checked"],
        },
    )