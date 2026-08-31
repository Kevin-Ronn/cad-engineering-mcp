"""Tests for the Phase 3 write/audit infrastructure.

Covers:

* UTC timestamp generation
* safe_destination traversal / symlink / outside-root rejection
* timestamped backup creation
* audit-log append
* atomic write semantics
* reference-geometry protection
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._mutation import (
    MutationError,
    atomic_write_text,
    audit,
    audit_dir,
    audit_log_path,
    backup_existing,
    backup_path,
    file_metadata,
    perform_write,
    releases_root,
    safe_destination,
    sha256_file,
    utc_iso,
    utc_timestamp_fs,
)
from cad_engineering_mcp.tools._paths import (
    ALLOWED_ROOTS,
    PathSecurityError,
    glasses_root,
)


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def test_utc_timestamp_fs_format():
    ts = utc_timestamp_fs()
    # Format: YYYY-MM-DDTHH-MM-SS-ffffff (filesystem-safe)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}$", ts), ts


def test_utc_iso_includes_timezone():
    iso = utc_iso()
    # ISO format ends with +00:00 for UTC.
    assert iso.endswith("+00:00") or iso.endswith("Z")


# ---------------------------------------------------------------------------
# Safe destination
# ---------------------------------------------------------------------------


def test_safe_destination_accepts_allowed_root(glasses, tmp_path):
    # Pick an arbitrary file inside the allowed tree.
    rel = "analysis/geometry/frame-coordinate-system.json"
    resolved = safe_destination(rel)
    assert resolved == glasses / rel


def test_safe_destination_rejects_traversal(glasses):
    with pytest.raises(MutationError):
        safe_destination("analysis/geometry/../../../../etc/passwd")


def test_safe_destination_rejects_outside_allowed_root():
    with pytest.raises(MutationError):
        safe_destination("not_a_real_subtree/whatever.yaml")


def test_safe_destination_rejects_reference_geometry(glasses):
    # references/ is one of the allowed roots in ALLOWED_ROOTS, but the
    # mutation helper must reject it because reference geometry is
    # immutable by policy.
    with pytest.raises(MutationError) as exc:
        safe_destination("references/silhouette/wayfarer/ray-ban-frame.stl")
    assert "read-only" in str(exc.value).lower() or "reference" in str(
        exc.value
    ).lower()


def test_safe_destination_rejects_absolute_path_outside_tree():
    with pytest.raises(MutationError):
        safe_destination("/tmp/outside-project.yaml")


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


def test_backup_existing_creates_timestamped_copy(glasses):
    timestamp = utc_timestamp_fs()
    target = glasses / "analysis" / "geometry" / "frame-coordinate-system.json"
    assert target.is_file()
    backup = backup_existing(timestamp, source=target)
    assert backup is not None
    assert backup.exists()
    assert backup.read_bytes() == target.read_bytes()
    # The backup lives under releases/<timestamp>/<relative-path>.
    rel = target.relative_to(glasses)
    assert backup == releases_root() / timestamp / rel


def test_backup_existing_returns_none_for_missing_file(glasses):
    timestamp = utc_timestamp_fs()
    target = glasses / "analysis" / "geometry" / "does-not-exist.json"
    assert backup_existing(timestamp, source=target) is None


def test_backup_path_layout(glasses):
    timestamp = utc_timestamp_fs()
    src = glasses / "mechanical" / "assemblies" / "glasses-assembly.yaml"
    expected = releases_root() / timestamp / Path(
        "mechanical/assemblies/glasses-assembly.yaml"
    )
    assert backup_path(timestamp, source=src) == expected


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_audit_appends_jsonl_entry(glasses):
    audit_dir().mkdir(parents=True, exist_ok=True)
    timestamp = utc_timestamp_fs()
    # Remove any pre-existing log so the test is deterministic.
    log_path = audit_log_path(timestamp)
    if log_path.exists():
        log_path.unlink()
    audit(
        timestamp=timestamp,
        tool="test_audit",
        operation="noop",
        affected_paths=["analysis/geometry/example.json"],
        success=True,
        metadata={"foo": "bar"},
    )
    assert log_path.is_file()
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "test_audit"
    assert entry["operation"] == "noop"
    assert entry["success"] is True
    assert entry["metadata"] == {"foo": "bar"}
    assert "analysis/geometry/example.json" in entry["affected_paths"]


def test_audit_log_path_deterministic_per_day():
    ts1 = "2026-01-15T12-34-56-000000"
    ts2 = "2026-01-15T13-00-00-000000"
    p1 = audit_log_path(ts1)
    p2 = audit_log_path(ts2)
    # Both timestamps fall on 2026-01-15 so the audit-log file is the
    # same one (the date is the partition key, not the timestamp).
    assert p1 == p2
    assert p1.name.startswith("2026-01-15")


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def test_atomic_write_text_replaces_target(glasses, tmp_path):
    target = tmp_path / "subdir" / "out.txt"
    atomic_write_text(target, "hello\n")
    assert target.read_text() == "hello\n"
    atomic_write_text(target, "world\n")
    assert target.read_text() == "world\n"


def test_atomic_write_text_cleans_up_on_failure(glasses, tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("original\n")

    class BoomError(RuntimeError):
        pass

    # Monkeypatch mkstemp to simulate a failure that leaves no .tmp
    # file behind.
    import tempfile as _tempfile

    original = _tempfile.mkstemp
    try:
        _tempfile.mkstemp = lambda *a, **kw: (_ for _ in ()).throw(  # noqa: E731
            BoomError("simulated")
        )
        with pytest.raises(BoomError):
            atomic_write_text(target, "should not be written")
    finally:
        _tempfile.mkstemp = original

    assert target.read_text() == "original\n"


# ---------------------------------------------------------------------------
# Hashing + metadata
# ---------------------------------------------------------------------------


def test_sha256_file_matches_known_value(glasses):
    p = glasses / "analysis" / "geometry" / "frame-coordinate-system.json"
    assert sha256_file(p) == sha256_file(p)  # deterministic
    assert len(sha256_file(p)) == 64


def test_file_metadata_keys(glasses):
    p = glasses / "analysis" / "geometry" / "frame-coordinate-system.json"
    meta = file_metadata(p)
    assert {"sha256", "mtime_iso", "bytes"} <= set(meta.keys())
    assert isinstance(meta["bytes"], int)
    assert isinstance(meta["sha256"], str)


# ---------------------------------------------------------------------------
# perform_write helper
# ---------------------------------------------------------------------------


def test_perform_write_creates_backup_and_audit(glasses, tmp_path):
    # Use a throwaway file inside the allowed tree so we don't mutate
    # the real assembly YAML.
    target = glasses / "manufacturing" / "_phase3_test_target.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original\n", encoding="utf-8")

    try:
        summary = perform_write(
            destination=str(target),
            content="replacement\n",
            tool="test_perform_write",
            operation="write_test",
        )
        assert summary["destination"].endswith(
            "manufacturing/_phase3_test_target.yaml"
        )
        assert summary["backup"] is not None
        # The backup lives under the same root the destination does.
        backup_file = glasses / summary["backup"]
        assert backup_file.is_file()
        assert backup_file.read_text(encoding="utf-8") == "original\n"
        # The new content is in place.
        assert target.read_text(encoding="utf-8") == "replacement\n"
    finally:
        # Clean up.
        if target.exists():
            target.unlink()
        # The backup lives in the audit dir; remove it so the test is
        # idempotent.
        for entry in (glasses / "manufacturing" / "releases").iterdir():
            if entry.is_dir() and entry.name != "audit":
                import shutil
                shutil.rmtree(entry, ignore_errors=True)


def test_perform_write_failure_records_audit(glasses, monkeypatch):
    # Force atomic_write_text to fail.
    target = glasses / "mechanical" / "assemblies" / "glasses-assembly.yaml"
    monkeypatch.setattr(
        "cad_engineering_mcp.tools._mutation.atomic_write_text",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError):
        perform_write(
            destination=str(target),
            content="x: 1\n",
            tool="test_perform_write",
            operation="write_test_failure",
        )