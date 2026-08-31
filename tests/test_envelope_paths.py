"""Tests for the structured envelope and path-security helpers."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cad_engineering_mcp.tools._envelope import (
    make_envelope,
    run_tool,
    utcnow_iso,
)
from cad_engineering_mcp.tools._paths import (
    PathSecurityError,
    glasses_root,
    project_root,
    resolve_project_root,
    safe_resolve,
)


def test_project_root_uses_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("CAD_ENGINEERING_ROOT", str(tmp_path))
    # Force re-evaluation by clearing the cache
    from cad_engineering_mcp.tools._paths import reset_project_root_cache
    reset_project_root_cache()
    assert project_root() == tmp_path.resolve()


def test_project_root_falls_back_to_repo_layout(monkeypatch):
    monkeypatch.delenv("CAD_ENGINEERING_ROOT", raising=False)
    from cad_engineering_mcp.tools._paths import reset_project_root_cache
    reset_project_root_cache()
    root = project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "cad_engineering_mcp" / "server.py").is_file()


def test_safe_resolve_relative_path(repo_root, glasses):
    rel = "analysis/geometry/frame-coordinate-system.json"
    resolved = safe_resolve(rel)
    assert resolved.is_file()
    assert resolved.relative_to(glasses) == Path(rel)


def test_safe_resolve_absolute_path(glasses):
    target = glasses / "analysis" / "geometry" / "frame-coordinate-system.json"
    resolved = safe_resolve(str(target))
    assert resolved == target


def test_safe_resolve_rejects_traversal():
    with pytest.raises(PathSecurityError):
        safe_resolve("../../pyproject.toml")


def test_safe_resolve_rejects_escape_absolute():
    with pytest.raises(PathSecurityError):
        safe_resolve("/etc/passwd")


def test_safe_resolve_rejects_disallowed_subtree(repo_root):
    # CLAUDE.md lives at <repo>/CLAUDE.md; not under any allowed sub-tree
    # even though it is in the repo.
    with pytest.raises(PathSecurityError):
        safe_resolve(str(repo_root / "CLAUDE.md"))


def test_safe_resolve_rejects_symlink_outside_tree(repo_root, tmp_path, monkeypatch):
    # Build a symlink under glasses that points outside the project.
    glasses = glasses_root()
    target = tmp_path / "outside.txt"
    target.write_text("nope")
    link = glasses / "analysis" / "_outside_link"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target)
    try:
        with pytest.raises(PathSecurityError):
            safe_resolve(str(link))
    finally:
        link.unlink()


def test_make_envelope_shape():
    env = make_envelope(
        tool="x",
        started_at_iso="2026-08-31T00:00:00+00:00",
        duration_ms=5,
        status="PASS",
        data={"a": 1},
        warnings=["w"],
        errors=[],
    )
    assert env["status"] == "PASS"
    assert env["tool"] == "x"
    assert env["started_at_iso"] == "2026-08-31T00:00:00+00:00"
    assert env["duration_ms"] == 5
    assert env["data"] == {"a": 1}
    assert env["warnings"] == ["w"]
    assert env["errors"] == []


def test_run_tool_captures_exception():
    def boom():
        raise RuntimeError("kaboom")

    env = run_tool("boom", boom)
    assert env["status"] == "ERROR"
    assert "RuntimeError" in env["errors"][0]
    assert "kaboom" in env["errors"][0]
    assert env["data"] is None


def test_run_tool_returns_envelope_passthrough():
    def nested():
        return {"data": 42, "status": "PASS"}

    env = run_tool("nested", nested)
    assert env["status"] == "PASS"
    assert env["data"] == 42


def test_utcnow_iso_is_timezone_aware():
    ts = utcnow_iso()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z") or "+" in ts or "-" in ts[-6:]