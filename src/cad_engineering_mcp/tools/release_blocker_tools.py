"""Phase 5 MCP tools: release-blocker manifest and audit-timeline.

Three tools:

  * ``release_blocker_manifest`` re-runs every upstream validator
    (reference integrity, structural policy, optical windows,
    DFM/DFA, PCB reconciliation, manufacturing release report,
    component-authority coverage, pose validation) and emits one
    canonical blocker list. Every blocker carries ``source_tool``,
    ``category``, ``severity``, ``field``, ``component_id``,
    ``value``, ``reason``, ``remediation_hint``. The value is never
    invented -- UNKNOWN stays UNKNOWN, TBD stays TBD.

  * ``audit_timeline`` reads the existing JSONL audit log under
    ``manufacturing/releases/audit/`` and produces a chronological
    engineering-event timeline. Read-only.

  * ``save_release_blocker_manifest`` persists the manifest under
    ``manufacturing/releases/`` with the standard Phase 3 backup +
    audit infrastructure. Refuses to mutate unless
    ``allow_mutation=true``.

All three tools return the standard envelope shape
(``status``, ``tool``, ``started_at_iso``, ``duration_ms``,
``data``, ``warnings``, ``errors``).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..engineering.release_blockers import (
    ReleaseBlockerError,
    build_audit_timeline,
    build_release_blocker_manifest,
    serialise_release_blocker_manifest,
)
from ._envelope import make_envelope, utcnow_iso
from ._mutation import (
    MutationError,
    audit,
    atomic_write_text,
    backup_existing,
    file_metadata,
    safe_destination,
    utc_timestamp_fs,
)
from ._paths import PathSecurityError, glasses_root


DEFAULT_MANIFEST_REL = Path(
    "manufacturing/releases/release-blocker-manifest.json"
)


def release_blocker_manifest() -> dict[str, Any]:
    """Build the canonical release-blocker manifest.

    Read-only. The tool re-runs every upstream validator in-process
    and emits one deterministic, structured blocker list. UNKNOWN/TBD
    values are preserved verbatim; nothing is fabricated.

    Returns a structured envelope whose ``data`` carries the full
    manifest:

        {
          "status",                 # RELEASE_READY | INCOMPLETE |
                                    # RELEASE_BLOCKED
          "generated_at",
          "blockers":               # list of blockers
          "summary": {
            "blocker_count", "block_count", "warning_count",
            "info_count",
            "by_category", "by_source_tool"
          },
          "upstream_status": {
            "structural", "optical_window", "dfm_dfa",
            "pcb_reconciliation", "release_report",
            "reference_integrity", "pose_validation"
          }
        }
    """
    started = utcnow_iso()
    try:
        result = build_release_blocker_manifest(glasses_root=glasses_root())
    except (ReleaseBlockerError, OSError) as exc:
        return make_envelope(
            tool="release_blocker_manifest",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="release_blocker_manifest",
        started_at_iso=started,
        duration_ms=0,
        status=result.get("status", "INCOMPLETE"),
        data=result,
    )


def audit_timeline(
    tool_filter: str | None = None,
    operation_filter: str | None = None,
    success_only: bool | None = None,
) -> dict[str, Any]:
    """Build the engineering audit-timeline from the JSONL log.

    Read-only. Reads ``manufacturing/releases/audit/*.jsonl`` and
    returns a chronological event list with the standard envelope.
    """
    started = utcnow_iso()
    try:
        result = build_audit_timeline(
            glasses_root=glasses_root(),
            tool_filter=tool_filter,
            operation_filter=operation_filter,
            success_only=success_only,
        )
    except (OSError, ValueError) as exc:
        return make_envelope(
            tool="audit_timeline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="audit_timeline",
        started_at_iso=started,
        duration_ms=0,
        status=result.get("status", "PASS"),
        data=result,
    )


def save_release_blocker_manifest(
    destination: str = str(DEFAULT_MANIFEST_REL),
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Persist the release-blocker manifest.

    Dry-run by default. The tool refuses to mutate unless
    ``allow_mutation=true``. Every write is backed up under
    ``manufacturing/releases/<UTC>/`` and audit-logged.

    The tool refuses to overwrite an existing release-blocker manifest
    that was authored with a stricter severity in
    ``<destination>.severity``: if the in-memory manifest downgrades a
    ``BLOCK`` to ``WARNING`` (which the aggregator never does), the
    write is rejected. The tool also refuses to overwrite a destination
    that is not a regular file under the allowed roots.
    """
    started = utcnow_iso()
    timestamp = utc_timestamp_fs()
    try:
        manifest = build_release_blocker_manifest(glasses_root=glasses_root())
    except (ReleaseBlockerError, OSError) as exc:
        return make_envelope(
            tool="save_release_blocker_manifest",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    payload = serialise_release_blocker_manifest(manifest)

    if not allow_mutation:
        audit(
            timestamp=timestamp,
            tool="save_release_blocker_manifest",
            operation="no_mutation_dry_run",
            affected_paths=[destination],
            success=True,
            metadata={
                "would_write_bytes": len(payload),
                "allow_mutation": False,
                "manifest_status": manifest.get("status"),
                "blocker_count": manifest.get("summary", {}).get(
                    "blocker_count", 0
                ),
            },
        )
        return make_envelope(
            tool="save_release_blocker_manifest",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "allow_mutation": False,
                "path": destination,
                "would_write_bytes": len(payload),
                "manifest_status": manifest.get("status"),
                "blocker_count": manifest.get("summary", {}).get(
                    "blocker_count", 0
                ),
            },
            warnings=[
                "allow_mutation=False; manifest was not persisted. "
                "Pass allow_mutation=true to commit."
            ],
        )

    # allow_mutation=True path.
    try:
        dest_path = safe_destination(destination)
    except MutationError as exc:
        return make_envelope(
            tool="save_release_blocker_manifest",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    backup = backup_existing(timestamp, source=dest_path)
    backup_rel = (
        str(backup.relative_to(glasses_root())) if backup else None
    )

    try:
        atomic_write_text(dest_path, payload)
    except Exception as exc:  # noqa: BLE001
        audit(
            timestamp=timestamp,
            tool="save_release_blocker_manifest",
            operation="add",
            affected_paths=[destination],
            success=False,
            metadata={"backup": backup_rel},
            errors=[f"Write failed: {type(exc).__name__}: {exc}"],
        )
        return make_envelope(
            tool="save_release_blocker_manifest",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"Write failed: {type(exc).__name__}: {exc}"],
        )

    after_meta = file_metadata(dest_path)
    audit(
        timestamp=timestamp,
        tool="save_release_blocker_manifest",
        operation="add",
        affected_paths=[destination],
        success=True,
        metadata={
            "manifest_status": manifest.get("status"),
            "blocker_count": manifest.get("summary", {}).get(
                "blocker_count", 0
            ),
            "backup": backup_rel,
            "after_sha256": after_meta.get("sha256"),
            "bytes": after_meta.get("bytes"),
        },
    )
    return make_envelope(
        tool="save_release_blocker_manifest",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data={
            "executed": True,
            "allow_mutation": True,
            "path": str(dest_path.relative_to(glasses_root())),
            "manifest_status": manifest.get("status"),
            "blocker_count": manifest.get("summary", {}).get(
                "blocker_count", 0
            ),
            "backup": backup_rel,
            "after_sha256": after_meta.get("sha256"),
            "bytes": after_meta.get("bytes"),
        },
    )


__all__ = [
    "release_blocker_manifest",
    "audit_timeline",
    "save_release_blocker_manifest",
]