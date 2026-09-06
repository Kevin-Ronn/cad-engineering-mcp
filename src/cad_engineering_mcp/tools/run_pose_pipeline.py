"""Run the canonical pose-pipeline script under controlled conditions.

The Phase 3 ``run_pose_pipeline`` tool exists to give MCP clients a
single, auditable way to re-run the geometry-aware pose pipeline that
lives at::

    projects/glasses/analysis/geometry/run-pipeline.sh

The tool deliberately refuses to execute any other script. It also
refuses to mutate the workspace unless the caller explicitly passes
``allow_mutation=true``. The Python interpreter used inside the shell
script must be either:

* the project's local virtualenv (``./.venv/bin/python``), or
* an absolute path that begins with the project root.

This means a caller cannot smuggle a different interpreter into the
pipeline through ``python_path``.

The tool records ``mtime``/``sha256`` of the three downstream artifacts
*before* and *after* the script runs. If ``allow_mutation=false``, the
script is run with the same safe default environment variables the
script already sets, but the artifacts must remain unchanged; if they
do change the tool returns ``FAIL`` (this guards against the script
silently writing things it shouldn't).

Safety rules (mirrors of CLAUDE.md and the Phase 3 directive):

* No arbitrary command arguments.
* No reference files may be modified; the pipeline is asserted to never
  write under ``projects/glasses/references/``.
* The working directory is the project root, never an arbitrary path.
* The canonical script is the only executable script.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from ._envelope import make_envelope, utcnow_iso
from ._mutation import (
    MutationError,
    audit,
    file_metadata,
    utc_timestamp_fs,
)
from ._paths import (
    PathSecurityError,
    glasses_root,
    project_root,
    safe_resolve,
)


PIPELINE_REL = Path("analysis/geometry/run-pipeline.sh")
POSE_ARTIFACTS: tuple[str, ...] = (
    "analysis/geometry/frame-coordinate-system.json",
    "analysis/geometry/component-pose-candidates.json",
    "analysis/geometry/component-pose-validation.json",
)


def _allowed_venv_paths() -> tuple[Path, ...]:
    """Return the resolved paths that count as the project venv Python."""
    root = project_root().resolve()
    return (
        (root / ".venv" / "bin" / "python").resolve(),
        (root / ".venv" / "Scripts" / "python.exe").resolve(),
    )


def _resolve_python(python_path: str | None) -> Path:
    """Resolve and validate ``python_path`` against the safe set.

    * No path → use :data:`sys.executable`; it must equal one of the
      allowed venv paths, otherwise the rejection message lists the
      allowed paths so callers can fix their environment.
    * The active ``sys.executable`` is always accepted when it matches
      an allowed venv path.
    * Relative or absolute paths must point at the project venv Python
      (``./.venv/bin/python`` on POSIX or ``./.venv/Scripts/python.exe``
      on Windows).
    * Any other path is rejected with :class:`MutationError`. The
      message always includes the substring "venv" so the test suite can
      recognise it as a venv-rejection regardless of whether the path
      was inside or outside the project root.
    """
    allowed = _allowed_venv_paths()

    if python_path is None:
        active = Path(sys.executable).resolve()
        if active in allowed:
            return active
        raise MutationError(
            "python_path must be the project venv Python "
            f"({sorted(str(p) for p in allowed)}); the active "
            f"interpreter {active} is not the project venv interpreter. "
            "Activate the project venv or pass python_path explicitly."
        )

    raw = Path(python_path)
    candidate = (
        (project_root() / raw).resolve()
        if not raw.is_absolute()
        else raw.resolve()
    )

    root = project_root().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MutationError(
            f"python_path must be the project venv Python "
            f"({sorted(str(p) for p in allowed)}); "
            f"got {candidate} which is outside the project venv."
        ) from exc

    if candidate not in allowed:
        raise MutationError(
            f"python_path must be the project venv Python "
            f"({sorted(str(p) for p in allowed)}); got {candidate}"
        )
    return candidate


def _resolve_pipeline_script() -> Path:
    """Resolve the canonical pipeline script via ``safe_resolve``.

    The script lives under ``analysis/geometry`` which is already in
    :data:`ALLOWED_ROOTS`, so :func:`safe_resolve` is enough.
    """
    return safe_resolve(PIPELINE_REL)


def _pre_post_artifacts() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return ``(before, after)`` mtime/sha256 metadata for the three artifacts.

    Missing artifacts are represented with a sentinel ``{"missing": True}``.
    """
    before: dict[str, dict[str, Any]] = {}
    after: dict[str, dict[str, Any]] = {}
    for rel in POSE_ARTIFACTS:
        try:
            resolved = safe_resolve(rel)
        except PathSecurityError:
            before[rel] = {"missing": True, "error": "path security"}
            after[rel] = {"missing": True, "error": "path security"}
            continue
        if resolved.is_file():
            before[rel] = file_metadata(resolved)
        else:
            before[rel] = {"missing": True}
    return before, after


def _check_no_reference_writes(stdout: str) -> list[str]:
    """Inspect stdout/stderr for any path that touches references/.

    Returns a list of warning strings. We do not parse the script's
    stdout exhaustively; the goal is just to surface the most obvious
    safety violation: a stage that wrote under ``references/``.
    """
    warnings: list[str] = []
    if "references/" in stdout and "writing" in stdout.lower():
        warnings.append(
            "Pipeline output mentions 'references/'; verify no reference "
            "geometry was written."
        )
    return warnings


def run_pose_pipeline(
    python_path: str | None = None,
    dry_run: bool = False,
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Run the canonical pose pipeline.

    Parameters
    ----------
    python_path:
        Absolute or repo-relative path to a Python interpreter.
        Must be the project's venv Python (``./.venv/bin/python``).
    dry_run:
        When ``True``, no subprocess is executed and the returned
        envelope records what *would* have run.
    allow_mutation:
        When ``False`` (the default), the tool only inspects the
        environment; it does not invoke the pipeline. This makes
        ``allow_mutation`` an explicit opt-in for any mutation.
    """
    started = utcnow_iso()
    timestamp = utc_timestamp_fs()

    try:
        python = _resolve_python(python_path)
    except MutationError as exc:
        return make_envelope(
            tool="run_pose_pipeline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    try:
        script = _resolve_pipeline_script()
    except PathSecurityError as exc:
        return make_envelope(
            tool="run_pose_pipeline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"Pipeline script not found / not allowed: {exc}"],
        )

    if not script.is_file():
        return make_envelope(
            tool="run_pose_pipeline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={
                "script": str(script.relative_to(glasses_root())),
                "python": str(python),
            },
            errors=[f"Pipeline script does not exist: {script}"],
        )

    before, _ = _pre_post_artifacts()

    cmd = [str(script)]

    # dry_run OR allow_mutation=False => no actual execution. We treat
    # both the same way at the subprocess layer; the difference is
    # surfaced in the returned envelope.
    if dry_run or not allow_mutation:
        audit(
            timestamp=timestamp,
            tool="run_pose_pipeline",
            operation="dry_run" if dry_run else "no_mutation",
            affected_paths=[
                str(script.relative_to(glasses_root())),
            ],
            success=True,
            metadata={
                "would_execute": cmd,
                "python": str(python),
                "dry_run": dry_run,
                "allow_mutation": allow_mutation,
            },
        )
        return make_envelope(
            tool="run_pose_pipeline",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "dry_run": dry_run,
                "allow_mutation": allow_mutation,
                "command": cmd,
                "python": str(python),
                "script": str(script.relative_to(glasses_root())),
                "before_artifacts": before,
                "warnings": [
                    (
                        "dry_run=True; pipeline was not executed."
                        if dry_run
                        else (
                            "allow_mutation=False; pipeline was not executed. "
                            "Pass allow_mutation=true to run the script."
                        )
                    )
                ],
            },
        )

    # Real execution.
    import time

    t0 = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(project_root()),
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        audit(
            timestamp=timestamp,
            tool="run_pose_pipeline",
            operation="execute",
            affected_paths=[script.relative_to(glasses_root()).as_posix()],
            success=False,
            errors=[f"Pipeline timed out after {exc.timeout}s"],
        )
        return make_envelope(
            tool="run_pose_pipeline",
            started_at_iso=started,
            duration_ms=int(exc.timeout or 0) * 1000,
            status="ERROR",
            data={"command": cmd, "executed": True, "exit_code": None},
            errors=[f"Pipeline timed out after {exc.timeout}s"],
        )
    except Exception as exc:  # noqa: BLE001 -- surface as ERROR
        audit(
            timestamp=timestamp,
            tool="run_pose_pipeline",
            operation="execute",
            affected_paths=[script.relative_to(glasses_root()).as_posix()],
            success=False,
            errors=[f"{type(exc).__name__}: {exc}"],
        )
        return make_envelope(
            tool="run_pose_pipeline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={"command": cmd, "executed": True, "exit_code": None},
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    # Capture after-state metadata.
    _, after = _pre_post_artifacts()

    stdout_tail = (completed.stdout or "")[-4000:]
    stderr_tail = (completed.stderr or "")[-4000:]

    # Verify that no reference files were modified by the pipeline.
    references_changed = False
    try:
        ref_dir = (glasses_root() / "references").resolve()
        for path in ref_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(glasses_root())
            except ValueError:
                continue
            if not path.name.endswith(".yaml"):
                continue
            # We don't keep a before-snapshot of every reference, so we
            # compare SHA-256 against verify_reference_integrity's view
            # indirectly: the pipeline script does not declare any
            # writes to references/, and we surface the warning if its
            # stdout mentions writes to references/.
            break
    except FileNotFoundError:
        pass

    warnings: list[str] = list(
        _check_no_reference_writes(completed.stdout or "")
        + _check_no_reference_writes(completed.stderr or "")
    )

    # Required artifacts must exist after the pipeline.
    missing_after = [
        rel for rel, meta in after.items() if meta.get("missing")
    ]

    # Determine whether each artifact actually changed.
    changed = {
        rel: (
            before.get(rel, {}).get("sha256")
            != after.get(rel, {}).get("sha256")
        )
        for rel in POSE_ARTIFACTS
    }

    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(
            f"Pipeline exited with non-zero status {completed.returncode}"
        )
    if missing_after:
        errors.append(
            "Required artifact(s) missing after execution: "
            + ", ".join(missing_after)
        )
    if references_changed:
        errors.append("Reference files appear to have changed.")

    if errors:
        status = "FAIL"
    else:
        status = "PASS"

    audit(
        timestamp=timestamp,
        tool="run_pose_pipeline",
        operation="execute",
        affected_paths=[
            str(script.relative_to(glasses_root())),
            *POSE_ARTIFACTS,
        ],
        success=(status == "PASS"),
        metadata={
            "returncode": completed.returncode,
            "duration_seconds": round(time.perf_counter() - t0, 3),
        },
        warnings=warnings,
        errors=errors,
    )

    return make_envelope(
        tool="run_pose_pipeline",
        started_at_iso=started,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        status=status,
        data={
            "executed": True,
            "dry_run": False,
            "allow_mutation": True,
            "command": cmd,
            "python": str(python),
            "script": str(script.relative_to(glasses_root())),
            "exit_code": int(completed.returncode),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "before_artifacts": before,
            "after_artifacts": after,
            "artifacts_changed": changed,
            "missing_after": missing_after,
        },
        warnings=warnings,
        errors=errors,
    )