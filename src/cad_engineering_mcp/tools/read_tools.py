"""Read-only MCP tools for inspecting project artifacts.

These three tools do not mutate anything; they list, read, or summarise
files under ``projects/glasses``. All paths are run through
:func:`cad_engineering_mcp.tools._paths.safe_resolve` so symlink-based
escape attempts are rejected.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ._envelope import make_envelope, utcnow_iso
from ._paths import (
    MAX_ARTIFACT_BYTES,
    PathSecurityError,
    glasses_root,
    safe_resolve,
)


_CATEGORIES: dict[str, tuple[str, ...]] = {
    "geometry": ("analysis/geometry",),
    "optical": ("analysis/optical",),
    "structure": ("analysis/structure",),
    "analysis": (
        "analysis/geometry",
        "analysis/optical",
        "analysis/structure",
    ),
    "mechanical": (
        "mechanical",
        "manufacturing",
    ),
    "electronics": ("electronics",),
    "manufacturing": ("manufacturing",),
    "all": (),  # sentinel: walk everything
}


_SIZE_FIELD_RE = re.compile(r"^\s*_SIZE\s*=", re.MULTILINE)


def list_analysis_artifacts(
    category: str = "all",
    subdir: str | None = None,
) -> dict[str, Any]:
    """List analysis artifacts under ``projects/glasses``.

    Parameters
    ----------
    category:
        One of ``geometry``, ``optical``, ``structure``, ``analysis``,
        ``mechanical``, ``electronics``, ``manufacturing``, ``all``.
    ``subdir``:
        Optional relative sub-path within the category (e.g.
        ``"geometry"``). Only consulted when ``category`` is not ``all``.
    """
    warnings: list[str] = []
    if category not in _CATEGORIES:
        return make_envelope(
            tool="list_analysis_artifacts",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data=None,
            warnings=warnings,
            errors=[f"Unknown category: {category!r}"],
        )

    if category == "all":
        roots = [glasses_root()]
    else:
        roots = [glasses_root() / d for d in _CATEGORIES[category]]

    artifacts: list[dict[str, Any]] = []
    errors: list[str] = []
    for root in roots:
        if not root.is_dir():
            warnings.append(f"Category directory missing: {root}")
            continue
        walk_root = root
        if subdir:
            walk_root = walk_root / subdir
            # A non-existent sub-directory is a no-op for this category
            # root, not an error (other roots in the category may still
            # match). When it does exist we must still verify it lives
            # under an allowed sub-tree to defeat ../ traversal.
            if walk_root.is_dir():
                try:
                    safe_resolve(walk_root)
                except PathSecurityError as exc:
                    errors.append(f"subdir {subdir!r}: {exc}")
                    continue
            else:
                warnings.append(
                    f"Sub-directory missing: {walk_root}"
                )
                continue
        for path in sorted(walk_root.rglob("*")):
            if not path.is_file():
                continue
            try:
                resolved = safe_resolve(path)
            except PathSecurityError as exc:
                errors.append(f"{path}: {exc}")
                continue
            rel = resolved.relative_to(glasses_root())
            artifacts.append(
                {
                    "path": str(rel),
                    "kind": _kind_of(resolved),
                    "bytes": resolved.stat().st_size,
                    "mtime_iso": _mtime_iso(resolved),
                }
            )

    return make_envelope(
        tool="list_analysis_artifacts",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status="PASS" if not errors else "ERROR",
        data={
            "schema_version": 1,
            "category": category,
            "subdir": subdir,
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        },
        warnings=warnings,
        errors=errors,
    )


def read_analysis_artifact(
    path: str,
    *,
    max_bytes: int = MAX_ARTIFACT_BYTES,
) -> dict[str, Any]:
    """Parse a JSON or YAML artifact and return its contents.

    ``path`` may be absolute or relative to ``projects/glasses``. The
    file must live under ``projects/glasses`` (symlinks are resolved and
    must not escape). Files larger than ``max_bytes`` are rejected with a
    structured error; this prevents accidentally slurping a multi-MB STL
    into memory.
    """
    try:
        resolved = safe_resolve(path)
    except PathSecurityError as exc:
        return make_envelope(
            tool="read_analysis_artifact",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    size = resolved.stat().st_size
    if size > max_bytes:
        return make_envelope(
            tool="read_analysis_artifact",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
                "bytes": size,
                "max_bytes": max_bytes,
            },
            errors=[
                f"Artifact is {size} bytes, exceeds limit of {max_bytes} bytes"
            ],
        )

    fmt = _format_of(resolved)
    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return make_envelope(
            tool="read_analysis_artifact",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
                "format": fmt,
                "bytes": size,
            },
            errors=[f"File is not valid UTF-8: {exc}"],
        )

    if fmt == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return make_envelope(
                tool="read_analysis_artifact",
                started_at_iso=utcnow_iso(),
                duration_ms=0,
                status="ERROR",
                data={
                    "path": str(resolved.relative_to(glasses_root())),
                    "format": fmt,
                },
                errors=[f"JSON parse error: {exc}"],
            )
    elif fmt == "yaml":
        # yaml.safe_load only: no arbitrary Python object construction.
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return make_envelope(
                tool="read_analysis_artifact",
                started_at_iso=utcnow_iso(),
                duration_ms=0,
                status="ERROR",
                data={
                    "path": str(resolved.relative_to(glasses_root())),
                    "format": fmt,
                },
                errors=[f"YAML parse error: {exc}"],
            )
    else:
        return make_envelope(
            tool="read_analysis_artifact",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
                "format": fmt,
                "bytes": size,
            },
            errors=[
                f"Unsupported format {fmt!r}; expected one of: json, yaml"
            ],
        )

    return make_envelope(
        tool="read_analysis_artifact",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status="PASS",
        data={
            "path": str(resolved.relative_to(glasses_root())),
            "format": fmt,
            "bytes": size,
            "data": data,
        },
    )


def get_pose_validation_summary(
    artifact: str = "analysis/geometry/component-pose-validation.json",
) -> dict[str, Any]:
    """Summarise the latest pose validation report.

    Returns per-component counts, accepted / rejected / invalid totals,
    and the list of components for which the validator flagged
    ``aperture_required`` (camera and forward LEDs whose 60-degree
    optical cone is obstructed by the frame mesh). The summary never
    upgrades ``overall_status``; the value is copied verbatim from the
    artifact, with explicit notes where it should not be interpreted as
    production-ready.
    """
    try:
        resolved = safe_resolve(artifact)
    except PathSecurityError as exc:
        return make_envelope(
            tool="get_pose_validation_summary",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return make_envelope(
            tool="get_pose_validation_summary",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
            },
            errors=[f"Failed to read validation artifact: {exc}"],
        )

    accepted = payload.get("accepted", []) or []
    rejected = payload.get("rejected", []) or []
    invalid = payload.get("invalid", []) or []
    validation = payload.get("validation", {}) or {}
    overall_status = str(validation.get("overall_status", "UNKNOWN"))

    # Incomplete if any component in the required set (1 camera,
    # 2 forward LEDs, 4 temple LEDs) is not in the accepted list.
    accepted_components = {
        a.get("component"): a.get("label") for a in accepted
    }
    required = {
        "camthink_ov5640_8p5": 1,
        "vsma1094750x02": 6,  # 2 forward + 4 temple
    }
    missing: list[dict[str, Any]] = []
    cam_count = sum(
        1 for c in accepted if c.get("component") == "camthink_ov5640_8p5"
    )
    if cam_count < required["camthink_ov5640_8p5"]:
        missing.append(
            {
                "component": "camthink_ov5640_8p5",
                "required": required["camthink_ov5640_8p5"],
                "accepted": cam_count,
            }
        )
    led_count = sum(
        1 for c in accepted if c.get("component") == "vsma1094750x02"
    )
    if led_count < required["vsma1094750x02"]:
        missing.append(
            {
                "component": "vsma1094750x02",
                "required": required["vsma1094750x02"],
                "accepted": led_count,
            }
        )

    aperture_required = [
        {
            "component": a.get("component"),
            "label": a.get("label"),
            "aperture_location_mm": (
                a.get("checks", {}).get("aperture_location_mm")
            ),
            "optical_cone_obstruction_mm": (
                a.get("checks", {}).get("optical_cone_obstruction_mm")
            ),
            "obstruction_reason": (
                "60-degree optical cone obstructed by frame mesh; "
                "production design must cut a flush aperture"
            ),
        }
        for a in accepted
        if a.get("checks", {}).get("aperture_required") is True
    ]

    # Camera is *required* to have aperture_required=False for a true
    # optical PASS. We surface this explicitly: never silently upgrade
    # overall_status when the camera cone is obstructed.
    camera_obstructed = any(
        a.get("component") == "camthink_ov5640_8p5"
        and a.get("checks", {}).get("aperture_required") is True
        for a in accepted
    )

    if missing:
        status = "INCOMPLETE"
    elif camera_obstructed:
        # overall_status from the artifact may say PASS, but the camera's
        # optical cone is obstructed: downgrade to INCOMPLETE so callers
        # cannot mistake it for a production-ready result.
        status = "INCOMPLETE"
    elif overall_status == "PASS":
        status = "PASS"
    elif overall_status == "FAIL":
        status = "FAIL"
    else:
        status = "INCOMPLETE"

    notes: list[str] = []
    notes.append(
        "overall_status reflects the implemented validator's checks only; "
        "PASS does not imply production readiness."
    )
    if camera_obstructed:
        notes.append(
            "Camera optical cone is obstructed by the frame mesh. "
            "Production design must cut a circular aperture through the "
            "front face (see component-pose-validation.json:aperture_location_mm)."
        )
    if rejected or invalid:
        notes.append(
            f"Validator rejected {len(rejected)} candidate(s) and marked "
            f"{len(invalid)} as invalid; see component-pose-validation.json."
        )

    return make_envelope(
        tool="get_pose_validation_summary",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status=status,
        data={
            "path": str(resolved.relative_to(glasses_root())),
            "artifact_overall_status": overall_status,
            "summary_status": status,
            "counts": {
                "accepted": len(accepted),
                "rejected": len(rejected),
                "invalid": len(invalid),
            },
            "missing_required": missing,
            "aperture_required": aperture_required,
            "validation_method": validation.get("validation_method"),
            "frame_treated_as": validation.get("frame_treated_as"),
            "notes": notes,
        },
    )


def _format_of(path: Path) -> str:
    """Return ``"json"`` or ``"yaml"`` based on suffix, else ``""``."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    return ""


def _kind_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".stl", ".obj", ".ply", ".off", ".3mf"}:
        return "mesh"
    if suffix in {".py", ".sh"}:
        return "script"
    if suffix == ".md":
        return "markdown"
    if suffix == ".kicad_pcb":
        return "kicad_pcb"
    return "other"


def _mtime_iso(path: Path) -> str:
    import datetime as _dt

    ts = path.stat().st_mtime
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat()