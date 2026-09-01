"""Phase 6 MCP tools: provenance overrides + resolution plan.

Three tools:

  * ``authoritative_value_override`` -- records an explicit
    authoritative value with structured :class:`ProvenanceRecord`
    metadata under
    ``projects/glasses/components/component-authority-overrides.yaml``.
    Refuses to record UNKNOWN/TBD values; refuses to silently
    overwrite an existing authoritative resolution; uses the
    standard Phase 3 backup + audit infrastructure.

  * ``list_authoritative_overrides`` -- read-only inspection of the
    override file.

  * ``resolution_plan`` -- consumes the Phase 5 release-blocker
    manifest and partitions every blocker into one of
    ``OVERRIDE``, ``POLICY_YAML``, ``GEOMETRY_DERIVED``,
    ``EXTERNAL_DATASHEET`` so the release engineer knows which
    blockers can be resolved without external data.

The override file is the *only* legitimate way to resolve an
UNKNOWN/TBD blocker without weakening validation: each override
carries explicit provenance (kind / evidence_path / evidence_sha256
/ confidence / recorded_at / recorded_by), so the resolution is
auditable end-to-end.

The tools never fabricate values. ``UNKNOWN`` / ``TBD`` /
``TBD_FROM_*`` override values are rejected. Override writes that
would silently overwrite an existing authoritative resolution
require ``force=True``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engineering.component_authority import (
    ComponentAuthorityError,
    is_recognised_field,
)
from ..engineering.provenance import (
    ProvenanceError,
    ProvenanceRecord,
    VALID_PROVENANCE_KINDS,
    add_override as _add_override_engineering,
    build_resolution_plan as _build_resolution_plan_engineering,
    list_overrides as _list_overrides_engineering,
    resolve_with_provenance as _resolve_with_provenance_engineering,
)
from ..engineering.release_blockers import (
    build_release_blocker_manifest,
)
from ._envelope import make_envelope, utcnow_iso
from ._mutation import (
    MutationError,
    perform_write,
)
from ._paths import (
    PathSecurityError,
    glasses_root,
    safe_resolve,
)


OVERRIDE_REL = Path("components/component-authority-overrides.yaml")


# ---------------------------------------------------------------------------
# list_authoritative_overrides (read-only)
# ---------------------------------------------------------------------------


def list_authoritative_overrides() -> dict[str, Any]:
    """Read the override file and return its records.

    Read-only. Returns a structured envelope whose ``data`` carries
    the override records, the schema version, and the on-disk path.
    """
    started = utcnow_iso()
    try:
        glasses = glasses_root()
        # Use safe_resolve so symlink escapes are rejected before the
        # file is even read.
        try:
            resolved = safe_resolve(OVERRIDE_REL)
        except PathSecurityError:
            resolved = None
        records = _list_overrides_engineering(glasses_root=glasses)
    except (ProvenanceError, OSError) as exc:
        return make_envelope(
            tool="list_authoritative_overrides",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    return make_envelope(
        tool="list_authoritative_overrides",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "path": str(OVERRIDE_REL),
            "resolved_path": str(resolved) if resolved else None,
            "schema_version": 1,
            "count": len(records),
            "records": [r.to_dict() for r in records],
        },
    )


# ---------------------------------------------------------------------------
# authoritative_value_override (controlled write)
# ---------------------------------------------------------------------------


def authoritative_value_override(
    component_id: str,
    field: str,
    value: Any,
    kind: str,
    *,
    evidence_path: str | None = None,
    evidence_sha256: str | None = None,
    confidence: str = "authoritative",
    recorded_by: str = "engineering_agent",
    notes: str | None = None,
    force: bool = False,
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Record an authoritative override with explicit provenance.

    The override is persisted under
    ``projects/glasses/components/component-authority-overrides.yaml``
    with the standard Phase 3 backup + audit infrastructure.

    Args:
        component_id: must be in :data:`KNOWN_COMPONENT_IDS` or in a
            per-component YAML ``component.id`` field.
        field: a recognised component field path
            (see :func:`is_recognised_field`).
        value: the authoritative value. Must not be the literal
            ``UNKNOWN`` / ``TBD`` / ``TBD_FROM_*``.
        kind: one of ``manufacturer_datasheet``, ``measured_geometry``,
            ``project_policy``, ``generated_derivation``,
            ``external_user_input``.
        evidence_path: relative path under ``projects/glasses`` for
            in-project evidence; free text for external datasheets.
        evidence_sha256: optional SHA-256 fingerprint of the evidence
            file; automatically computed for in-project paths when
            ``evidence_path`` is supplied and the file exists.
        confidence: ``authoritative`` (default), ``provisional``, or
            ``recorded``.
        recorded_by: who recorded the override.
        notes: optional human-readable notes.
        force: overwrite an existing override (or an existing
            authoritative resolution).
        allow_mutation: must be ``True`` to actually write; dry-run by
            default.

    Returns a structured envelope. When ``allow_mutation=False`` the
    tool performs a dry-run that audit-logs the intent and returns
    the would-write summary without touching the file.
    """
    started = utcnow_iso()

    # ---- Validation ----
    try:
        if kind not in VALID_PROVENANCE_KINDS:
            return make_envelope(
                tool="authoritative_value_override",
                started_at_iso=started,
                duration_ms=0,
                status="ERROR",
                errors=[
                    f"Invalid kind: {kind!r}. "
                    f"Must be one of {sorted(VALID_PROVENANCE_KINDS)}."
                ],
            )
        # Recognise the field path against the Phase 4 whitelist.
        try:
            if not is_recognised_field(field):
                return make_envelope(
                    tool="authoritative_value_override",
                    started_at_iso=started,
                    duration_ms=0,
                    status="ERROR",
                    errors=[
                        f"Unrecognised component field path: {field!r}. "
                        "Only recognised engineering fields may be "
                        "overridden."
                    ],
                )
        except ComponentAuthorityError as exc:
            return make_envelope(
                tool="authoritative_value_override",
                started_at_iso=started,
                duration_ms=0,
                status="ERROR",
                errors=[str(exc)],
            )

        # Auto-compute evidence_sha256 for in-project evidence paths.
        computed_sha: str | None = evidence_sha256
        if computed_sha is None and evidence_path:
            candidate = glasses_root() / evidence_path
            if candidate.exists() and candidate.is_file():
                from ..engineering.provenance import _file_sha256

                computed_sha = _file_sha256(candidate)

        try:
            provenance = ProvenanceRecord(
                component_id=component_id,
                field=field,
                value=value,
                kind=kind,
                evidence_path=evidence_path,
                evidence_sha256=computed_sha,
                confidence=confidence,
                recorded_by=recorded_by,
                notes=notes,
            )
        except ProvenanceError as exc:
            return make_envelope(
                tool="authoritative_value_override",
                started_at_iso=started,
                duration_ms=0,
                status="ERROR",
                errors=[str(exc)],
            )
    except Exception as exc:  # noqa: BLE001 -- envelope ERROR
        return make_envelope(
            tool="authoritative_value_override",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    # ---- Dry-run / mutation ----
    record_dict = provenance.to_dict()
    if not allow_mutation:
        from ._mutation import audit as _audit, utc_timestamp_fs

        _audit(
            timestamp=utc_timestamp_fs(),
            tool="authoritative_value_override",
            operation="no_mutation_dry_run",
            affected_paths=[str(OVERRIDE_REL)],
            success=True,
            metadata={
                "would_write_record": record_dict,
                "allow_mutation": False,
                "force": force,
            },
        )
        return make_envelope(
            tool="authoritative_value_override",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "allow_mutation": False,
                "would_write_record": record_dict,
                "path": str(OVERRIDE_REL),
            },
            warnings=[
                "allow_mutation=False; override was not recorded. "
                "Pass allow_mutation=true to commit."
            ],
        )

    try:
        summary = _add_override_engineering(
            record=provenance,
            glasses_root=glasses_root(),
            force=force,
            perform_write_fn=perform_write,
        )
    except (ProvenanceError, MutationError, OSError) as exc:
        return make_envelope(
            tool="authoritative_value_override",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    return make_envelope(
        tool="authoritative_value_override",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "executed": True,
            "allow_mutation": True,
            "path": str(OVERRIDE_REL),
            "record": record_dict,
            "write_summary": summary,
        },
    )


# ---------------------------------------------------------------------------
# resolution_plan
# ---------------------------------------------------------------------------


def resolution_plan() -> dict[str, Any]:
    """Build the engineering-data resolution plan.

    Reads the Phase 5 release-blocker manifest and partitions every
    blocker into one of four resolution strategies:
    ``OVERRIDE``, ``POLICY_YAML``, ``GEOMETRY_DERIVED``,
    ``EXTERNAL_DATASHEET``.

    Read-only. Returns a structured envelope whose ``data`` carries
    the full plan plus per-blocker strategy / rationale / next_action.
    """
    started = utcnow_iso()
    try:
        blocker_manifest = build_release_blocker_manifest(
            glasses_root=glasses_root()
        )
        plan = _build_resolution_plan_engineering(
            blocker_manifest=blocker_manifest
        )
    except (ProvenanceError, OSError) as exc:
        return make_envelope(
            tool="resolution_plan",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="resolution_plan",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data=plan,
    )


__all__ = [
    "authoritative_value_override",
    "list_authoritative_overrides",
    "resolution_plan",
]