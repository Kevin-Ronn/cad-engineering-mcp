"""Path resolution and security helpers for the CAD Engineering MCP.

Phase 1 only exposes read/verification tools. Every tool that takes a path
must resolve it through :func:`safe_resolve` so that:

* the path lives under the project's ``projects/glasses`` tree
* symlinks that escape the project root are rejected
* missing files raise a structured error rather than crashing

The project root is portable and is computed by the shared resolver in
:mod:`cad_engineering_mcp.engineering.paths`. It honours the
``CAD_ENGINEERING_ROOT`` environment variable, falls back to the
repository root that contains ``src/cad_engineering_mcp/server.py``
(resolved via ``__file__``), and finally to the historical
``~/cad-engineering-mcp`` default for back-compatibility.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..engineering.component_geometry import ComponentGeometryError
from ..engineering.paths import (
    glasses_root as _glasses_root,
    project_root as _project_root,
    resolve_project_root as _resolve_project_root,
    reset_project_root_cache as _reset_project_root_cache,
)


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


# Re-export the shared resolver so existing ``from .tools._paths import
# project_root`` / ``glasses_root`` imports keep working.
project_root = _project_root
glasses_root = _glasses_root
resolve_project_root = _resolve_project_root


def reset_project_root_cache() -> None:
    """Clear the cached project root.

    Delegates to :func:`cad_engineering_mcp.engineering.paths.reset_project_root_cache`
    so the cache is shared between engineering and tools modules.
    """
    _reset_project_root_cache()


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