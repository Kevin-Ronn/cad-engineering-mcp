"""Mutation, backup, and audit infrastructure for the CAD Engineering MCP.

Phase 3 introduces the first controlled-write tools. Every write must:

* resolve the destination through :func:`safe_destination`, which reuses
  the path-security guarantees of :func:`cad_engineering_mcp.tools._paths.safe_resolve`
  (no traversal outside ``projects/glasses``, no symlink escape);
* create a timestamped backup of any existing file before overwriting it;
* append an audit-log entry to ``projects/glasses/manufacturing/releases/audit/``;
* refuse to mutate authoritative reference geometry;
* raise :class:`MutationError` (a :class:`PathSecurityError`) when the
  request violates policy.

Backups live under::

    projects/glasses/manufacturing/releases/<UTC_TIMESTAMP>/

The UTC timestamp has filesystem-safe characters only (digits, ``-``,
``T``, ``_``) so it can be used as a directory name on any platform.

Audit entries are appended to a single JSONL file per UTC day under::

    projects/glasses/manufacturing/releases/audit/<UTC_TIMESTAMP>.jsonl

Each entry is one self-contained JSON object. The ``Affected paths``
section of the directive is implemented by the :func:`audit` helper.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from ._paths import (
    ALLOWED_ROOTS,
    PathSecurityError,
    glasses_root,
    safe_resolve,
)


class MutationError(PathSecurityError):
    """Raised when a write attempt violates the mutation policy."""


# Reference geometry is immutable by policy (see CLAUDE.md). Even if a
# caller resolves a reference path through :func:`safe_destination`, the
# helpers below refuse to back it up or mutate it.
REFERENCE_ROOTS: tuple[str, ...] = (
    "references",
)


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def utc_timestamp_fs() -> str:
    """Return a UTC timestamp safe for use as a directory name.

    The format is ``YYYY-MM-DDTHH-MM-SS-ffffff`` (colons are replaced by
    dashes so the string can appear in paths on Windows/macOS/Linux
    without quoting).
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H-%M-%S-%f")


def utc_iso(ts: _dt.datetime | None = None) -> str:
    """Return an ISO-8601 UTC timestamp with timezone."""
    if ts is None:
        ts = _dt.datetime.now(_dt.timezone.utc)
    return ts.isoformat()


# ---------------------------------------------------------------------------
# Allowed mutation roots
# ---------------------------------------------------------------------------


# Phase 3 restricts writes to the same sub-trees that are already
# accessible to read tools, plus ``manufacturing`` (which is a release
# directory, not a reference). Writes to ``references`` are *still*
# rejected because reference geometry is authoritative and immutable;
# the rejection happens in :func:`_check_mutation_allowed`.
MUTATION_ALLOWED_ROOTS: tuple[str, ...] = ALLOWED_ROOTS


def _check_mutation_allowed(resolved: Path, glasses: Path) -> str:
    """Return the first path segment under ``glasses`` for ``resolved``.

    Raises :class:`MutationError` if the resolved path escapes an allowed
    root or lives under a reference sub-tree.
    """
    try:
        relative = resolved.relative_to(glasses)
    except ValueError as exc:
        raise MutationError(
            f"Path escapes the project root: {resolved} not under {glasses}"
        ) from exc
    parts = relative.parts
    if not parts:
        raise MutationError(f"Path has no segments: {resolved}")
    first = parts[0]
    if first in REFERENCE_ROOTS:
        raise MutationError(
            f"Reference geometry is read-only: {resolved}"
        )
    if first not in MUTATION_ALLOWED_ROOTS:
        raise MutationError(
            f"Path is outside an allowed sub-tree "
            f"({first!r} not in {sorted(MUTATION_ALLOWED_ROOTS)})"
        )
    return first


def safe_destination(path: str | Path) -> Path:
    """Resolve a write destination and verify mutation is allowed.

    Mirrors :func:`cad_engineering_mcp.tools._paths.safe_resolve` but
    additionally rejects paths under ``references/``. The resolved path
    is returned with symlinks collapsed and ``..`` segments normalised.
    """
    glasses = glasses_root()
    if not glasses.is_dir():
        raise MutationError(f"Glasses project root missing: {glasses}")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = glasses / candidate
    # The destination may not exist yet, so resolve without strict=True.
    # We still reject ``..`` traversal that escapes the project tree.
    try:
        candidate = candidate.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise MutationError(f"Could not resolve destination: {candidate}") from exc
    _check_mutation_allowed(candidate, glasses)
    return candidate


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def sha256_file(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    """Return the SHA-256 hex digest of ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    """Return ``{sha256, mtime_iso, bytes}`` for an existing file."""
    stat = path.stat()
    return {
        "sha256": sha256_file(path),
        "mtime_iso": _dt.datetime.fromtimestamp(
            stat.st_mtime, _dt.timezone.utc
        ).isoformat(),
        "bytes": stat.st_size,
    }


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


def releases_root() -> Path:
    """Return ``projects/glasses/manufacturing/releases``.

    The directory is created on demand by :func:`backup_path`.
    """
    return glasses_root() / "manufacturing" / "releases"


def backup_path(timestamp: str, *, source: Path) -> Path:
    """Return the backup destination path for ``source``.

    The layout is::

        <releases_root>/<timestamp>/<relative-source-path>

    so a single release directory contains the entire pre-mutation
    snapshot of the workspace.
    """
    rel = source.relative_to(glasses_root())
    backup_dir = releases_root() / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir / rel


def backup_existing(
    timestamp: str,
    *,
    source: Path,
) -> Path | None:
    """If ``source`` exists, copy it to the backup directory.

    Returns the backup destination path, or ``None`` if ``source`` did
    not exist (creating a brand-new file does not require a backup).
    """
    if not source.exists() or not source.is_file():
        return None
    dest = backup_path(timestamp, source=source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def audit_dir() -> Path:
    """Return the audit-log directory, creating it if necessary."""
    d = releases_root() / "audit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def audit_log_path(timestamp: str | None = None) -> Path:
    """Return the JSONL audit-log file for the given UTC day.

    The audit log file name is derived from the *date* portion of the
    timestamp (``YYYY-MM-DD``), so all entries written during a single
    calendar day share the same file. A timestamp is still required so
    callers can pre-compute and stash the path.
    """
    if timestamp is None:
        timestamp = utc_timestamp_fs()
    day = timestamp.split("T", 1)[0]
    return audit_dir() / f"{day}.jsonl"


def audit(
    *,
    tool: str,
    operation: str,
    affected_paths: Iterable[str],
    success: bool,
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
    errors: Iterable[str] | None = None,
    warnings: Iterable[str] | None = None,
) -> Path:
    """Append an entry to the JSONL audit log.

    Returns the path to the audit-log file the entry was appended to.
    The entry is written atomically: the JSONL file is opened with
    ``O_APPEND`` so concurrent appends do not interleave within a single
    line on POSIX. Each entry is one JSON object terminated by ``\\n``.
    """
    if timestamp is None:
        timestamp = utc_timestamp_fs()
    entry = {
        "timestamp": utc_iso(),
        "timestamp_fs": timestamp,
        "tool": tool,
        "operation": operation,
        "affected_paths": list(affected_paths),
        "success": bool(success),
    }
    if metadata:
        entry["metadata"] = metadata
    if errors:
        entry["errors"] = list(errors)
    if warnings:
        entry["warnings"] = list(warnings)
    log_path = audit_log_path(timestamp)
    line = json.dumps(entry, sort_keys=True) + "\n"
    # Append atomically by writing through a single O_APPEND handle.
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    fd = os.open(log_path, flags, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    return log_path


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def atomic_write_text(
    destination: Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Write ``content`` to ``destination`` atomically.

    The text is written to a sibling temporary file in the same
    directory and then ``os.replace``'d onto ``destination``. This
    guarantees that an interrupted write cannot leave a half-written
    file in place.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp-", suffix=destination.suffix, dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
        os.replace(tmp_path, destination)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def atomic_write_bytes(
    destination: Path,
    content: bytes,
) -> None:
    """Write ``content`` to ``destination`` atomically (binary)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp-", suffix=destination.suffix, dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.replace(tmp_path, destination)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


# ---------------------------------------------------------------------------
# High-level helper
# ---------------------------------------------------------------------------


def perform_write(
    *,
    destination: str | Path,
    content: str,
    tool: str,
    operation: str,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Perform a controlled text write with backup and audit logging.

    Returns a summary dict containing the resolved destination, the
    timestamp, the backup destination (if any), and the audit-log path.
    The caller is responsible for surfacing errors from :class:`MutationError`.
    """
    timestamp = utc_timestamp_fs()
    resolved = safe_destination(destination)
    backup = backup_existing(timestamp, source=resolved)
    try:
        atomic_write_text(resolved, content, encoding=encoding)
    except Exception:
        audit(
            timestamp=timestamp,
            tool=tool,
            operation=operation,
            affected_paths=[str(resolved.relative_to(glasses_root()))],
            success=False,
            metadata=metadata,
            errors=[f"Write failed for {resolved}"],
        )
        raise
    audit(
        timestamp=timestamp,
        tool=tool,
        operation=operation,
        affected_paths=[str(resolved.relative_to(glasses_root()))],
        success=True,
        metadata={
            **(metadata or {}),
            "backup": (
                str(backup.relative_to(glasses_root())) if backup else None
            ),
        },
    )
    return {
        "destination": str(resolved.relative_to(glasses_root())),
        "timestamp": timestamp,
        "backup": str(backup.relative_to(glasses_root())) if backup else None,
        "audit_log": str(audit_log_path(timestamp).relative_to(glasses_root())),
    }


def safe_resolve_read(path: str | Path) -> Path:
    """Compatibility wrapper around :func:`safe_resolve`.

    Mutation tools that need to *verify the current state* of a path
    before overwriting it can call this; it is otherwise identical to
    :func:`cad_engineering_mcp.tools._paths.safe_resolve`.
    """
    return safe_resolve(path)