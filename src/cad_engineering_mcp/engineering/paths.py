"""Portable project-root resolution for the CAD Engineering MCP.

This module is the authoritative source for locating the repository
root on every supported platform. It is intentionally dependency-free
(no imports from :mod:`engineering.component_geometry` or
:mod:`tools._paths`) so that any package module can import it without
risking a circular import.

Resolution order:

1. ``CAD_ENGINEERING_ROOT`` environment variable, if it points at an
   existing directory.
2. The repository root that contains ``pyproject.toml`` and
   ``src/cad_engineering_mcp/server.py``, derived from this file's
   location via :data:`pathlib.Path.parents`.
3. The historical ``~/cad-engineering-mcp`` default for back-compat.

The hard-coded ``~/cad-engineering-mcp`` default and the username-based
home directory assumption have been preserved as a *fallback only* so
that older clones still work, but no module is allowed to compute its
own copy of the path any more.
"""
from __future__ import annotations

import os
from pathlib import Path


def _historical_default() -> Path:
    """Return the legacy ``~/cad-engineering-mcp`` location, if any.

    This default is used only as a last-resort fallback. Production code
    must rely on :func:`resolve_project_root`, not on this function.
    """
    return Path.home() / "cad-engineering-mcp"


def resolve_project_root() -> Path:
    """Return the absolute CAD Engineering repository root.

    Raises :class:`ProjectRootNotFoundError` if no source resolves to an
    existing directory. The returned path is fully resolved and
    absolute.
    """
    env_root = os.environ.get("CAD_ENGINEERING_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.is_dir():
            return candidate

    # Walk up from this file to find the repo root that contains
    # src/cad_engineering_mcp/server.py and pyproject.toml.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (
            parent / "src" / "cad_engineering_mcp" / "server.py"
        ).is_file():
            return parent

    fallback = _historical_default()
    if fallback.is_dir():
        return fallback.resolve()

    raise ProjectRootNotFoundError(
        "Could not locate the CAD Engineering repository root. "
        "Set CAD_ENGINEERING_ROOT or run from the repo directory."
    )


class ProjectRootNotFoundError(RuntimeError):
    """Raised when the repository root cannot be located."""


#: Module-level cached project root. Tests can clear it via
#: :func:`reset_project_root_cache` so fixtures can re-point
#: ``CAD_ENGINEERING_ROOT`` between cases.
_PROJECT_ROOT: Path | None = None


def project_root() -> Path:
    """Return the cached repository root.

    Computing the root repeatedly inside hot paths is wasteful; cache it
    on first use. The cache is module-level so test fixtures can reset
    it by calling :func:`reset_project_root_cache`.
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = resolve_project_root()
    return _PROJECT_ROOT


def reset_project_root_cache() -> None:
    """Clear the cached project root.

    Tests that mutate ``CAD_ENGINEERING_ROOT`` between cases must call
    this so the next :func:`project_root` call re-resolves.
    """
    global _PROJECT_ROOT
    _PROJECT_ROOT = None


def glasses_root() -> Path:
    """Return ``<project_root>/projects/glasses``."""
    return project_root() / "projects" / "glasses"