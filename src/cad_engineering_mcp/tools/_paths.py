"""Path resolution and security helpers for the CAD Engineering MCP.

Phase 1 only exposes read/verification tools. Every tool that takes a path
must resolve it through :func:`safe_resolve` so that:

* the path lives under the project's ``projects/glasses`` tree
* symlinks that escape the project root are rejected
* missing files raise a structured error rather than crashing

The project root is portable: it honours the ``CAD_ENGINEERING_ROOT``
environment variable, falls back to the repository root that contains
``src/cad_engineering_mcp/server.py`` (resolved via ``__file__``), and
finally to the historical ``~/cad-engineering-mcp`` default for back-
compatibility. The hard-coded home-directory assumption in earlier
modules is preserved as a last-resort fallback only.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ..engineering.component_geometry import ComponentGeometryError


# Sub-tree of the project that read/verification tools are allowed to
# touch. PCB geometry and write targets will be added in a later phase.
# ``agent/`` holds the engineering mission and run-engineering.sh script;
# both are read-only artifacts and safe to expose to inspection.
ALLOWED_ROOTS: tuple[str, ...] = (
    "agent",
    "analysis",
    "components",
    "electronics",
    "exports",
    "manufacturing",
    "mechanical",
    "references",
)

# Maximum artifact size accepted by read_analysis_artifact (4 MB).
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024


class PathSecurityError(ComponentGeometryError):
    """Raised when a requested path is outside the allowed project tree."""


def _historical_default() -> Path:
    return Path.home() / "cad-engineering-mcp"


def resolve_project_root() -> Path:
    """Return the CAD Engineering repository root.

    Resolution order:

    1. ``CAD_ENGINEERING_ROOT`` environment variable, if set and existing.
    2. Repository root derived from this file's location
       (``<repo>/src/cad_engineering_mcp/tools/_paths.py`` -> ``<repo>``).
    3. The historical ``~/cad-engineering-mcp`` default for back-compat.

    The returned path is resolved to an absolute path and verified to
    exist. If neither source is usable, ``PathSecurityError`` is raised.
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

    raise PathSecurityError(
        "Could not locate the CAD Engineering repository root. "
        "Set CAD_ENGINEERING_ROOT or run from the repo directory."
    )


def project_root() -> Path:
    """Cached project root accessor.

    Computing the root repeatedly inside hot paths is wasteful; cache it
    on first use. The cache is module-level so test fixtures can reset it
    by calling :func:`reset_project_root_cache`.
    """
    cached = globals().get("_PROJECT_ROOT")
    if cached is not None:
        return cached
    root = resolve_project_root()
    globals()["_PROJECT_ROOT"] = root
    return root


def reset_project_root_cache() -> None:
    globals().pop("_PROJECT_ROOT", None)


def glasses_root() -> Path:
    """Return ``<project_root>/projects/glasses``."""
    return project_root() / "projects" / "glasses"


def _normalize(path: Path, *, must_be_under: Path) -> Path:
    """Resolve ``path`` to an absolute, real path and verify it stays
    inside ``must_be_under``.

    Symbolic links are resolved (so an attacker cannot smuggle a path
    that points outside the tree) and ``..`` segments are collapsed. The
    final path must live inside ``must_be_under``; if not,
    :class:`PathSecurityError` is raised.
    """
    try:
        # strict=True raises if the path does not exist; we want that.
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathSecurityError(f"Path does not exist: {path}") from exc

    try:
        resolved.relative_to(must_be_under.resolve())
    except ValueError as exc:
        raise PathSecurityError(
            f"Path escapes the allowed root: {resolved} not under {must_be_under}"
        ) from exc

    return resolved


def safe_resolve(path: str | Path, *, allowed_roots: Iterable[str] = ALLOWED_ROOTS) -> Path:
    """Resolve ``path`` against :func:`glasses_root` and reject escapes.

    ``path`` may be absolute or relative to :func:`glasses_root`. The
    final resolved path must live inside the ``glasses`` tree and under
    one of the ``allowed_roots`` sub-directories.
    """
    glasses = glasses_root()
    if not glasses.is_dir():
        raise PathSecurityError(f"Glasses project root missing: {glasses}")

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = glasses / candidate

    resolved = _normalize(candidate, must_be_under=glasses)

    # The first path segment under glasses/ must be one of the allowed
    # sub-trees; this prevents, e.g., touching ``projects/glasses/CLAUDE.md``
    # even if it lived under glasses/.
    try:
        first_segment = resolved.relative_to(glasses).parts[0]
    except IndexError as exc:
        raise PathSecurityError(f"Path has no segments: {resolved}") from exc

    if first_segment not in allowed_roots:
        raise PathSecurityError(
            f"Path is outside an allowed sub-tree "
            f"({first_segment!r} not in {sorted(allowed_roots)})"
        )

    return resolved