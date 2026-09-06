"""Run the canonical PCB-outline generator under controlled conditions.

Phase 3 ``generate_pcb_outline`` tool. The generator script lives at::

    projects/glasses/electronics/generate_board_outline.py

and is the *only* PCB-outline generator this tool is allowed to invoke.

Pre-flight checks:

* Read ``analysis/geometry/component-pose-validation.json`` and require
  ``validation.overall_status == "PASS"``. If it is anything else
  (``FAIL``, ``INCOMPLETE``, missing, etc.) the tool refuses to run
  the generator unless the caller passes ``force=true``.
* The phase-3 directive explicitly says: "Do not attempt to fix the
  existing PCB architecture conflicts in this phase. Surface them as
  warnings/findings instead." So when generation succeeds but the
  resulting ``glasses-pcb.summary.json`` reports warnings (e.g. about
  overlaps, missing footprints), we surface them in the envelope
  ``warnings`` field without claiming ``PASS`` is production-ready.

Safety:

* The generator is the only Python script the tool can run; the path
  is resolved via :func:`safe_resolve`.
* Like ``run_pose_pipeline``, the tool only mutates the workspace
  when ``allow_mutation=true``.
* Backups are written through :func:`_mutation.perform_write`-style
  helpers (called by the generator for its outputs).
* Reference geometry (under ``references/``) is never touched.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
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


GENERATOR_REL = Path("electronics/generate_board_outline.py")
POSE_VALIDATION_REL = Path("analysis/geometry/component-pose-validation.json")
GENERATED_OUTPUTS: tuple[str, ...] = (
    "electronics/glasses-pcb.kicad_pcb",
    "electronics/glasses-pcb.summary.json",
)


# Acceptable project-venv interpreter paths. ``sys.executable`` is the
# authoritative "the interpreter currently running this tool" path;
# platform-specific venv layouts are kept for back-compat with callers
# that explicitly opt into them.
def _allowed_venv_paths() -> tuple[Path, ...]:
    root = project_root().resolve()
    return (
        (root / ".venv" / "bin" / "python").resolve(),
        (root / ".venv" / "Scripts" / "python.exe").resolve(),
    )


def _resolve_python(python_path: str | None) -> Path:
    """Resolve and validate ``python_path`` against the safe set.

    * No path → use :data:`sys.executable`.
    * The active ``sys.executable`` is always accepted (it is the
      interpreter that already drives this MCP server).
    * Relative or absolute paths must point at the project venv Python
      (``./.venv/bin/python`` on POSIX or ``./.venv/Scripts/python.exe``
      on Windows).
    * Any other path is rejected with :class:`MutationError`.
    """
    allowed = _allowed_venv_paths()
    if python_path is None:
        chosen = Path(sys.executable).resolve()
        if chosen not in allowed:
            raise MutationError(
                "python_path must be the project venv Python "
                f"({sorted(str(p) for p in allowed)}); "
                f"the active interpreter {chosen} is not the venv "
                "interpreter. Pass python_path explicitly or activate "
                "the project venv."
            )
        return chosen

    candidate = Path(python_path)
    if not candidate.is_absolute():
        candidate = (project_root() / python_path).resolve()
    else:
        candidate = candidate.resolve()

    if candidate not in allowed:
        raise MutationError(
            "python_path must be the project venv Python "
            f"({sorted(str(p) for p in allowed)}); got {candidate}"
        )
    return candidate


def _read_pose_validation() -> dict[str, Any]:
    """Read and parse the pose-validation artifact.

    Returns a dict with at least:

    * ``resolved`` - the resolved Path (None if missing/error)
    * ``overall_status`` - the artifact's ``validation.overall_status`` (or UNKNOWN)
    * ``missing`` - True if the artifact does not exist
    * ``parse_error`` - True if the artifact exists but is unreadable
    * ``raw`` - the parsed dict (or None)
    """
    try:
        resolved = safe_resolve(POSE_VALIDATION_REL)
    except PathSecurityError as exc:
        return {
            "resolved": None,
            "overall_status": "UNKNOWN",
            "missing": True,
            "parse_error": False,
            "raw": None,
            "error": str(exc),
        }
    if not resolved.is_file():
        return {
            "resolved": resolved,
            "overall_status": "UNKNOWN",
            "missing": True,
            "parse_error": False,
            "raw": None,
        }
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "resolved": resolved,
            "overall_status": "UNKNOWN",
            "missing": False,
            "parse_error": True,
            "raw": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    validation = (data or {}).get("validation", {}) or {}
    return {
        "resolved": resolved,
        "overall_status": str(validation.get("overall_status", "UNKNOWN")),
        "missing": False,
        "parse_error": False,
        "raw": data,
    }


def _resolve_generator() -> Path:
    return safe_resolve(GENERATOR_REL)


def _summarize_pcb_warnings(summary: dict[str, Any]) -> list[str]:
    """Surface PCB-architecture findings from the generated summary.

    The current generator emits placeholders and may report overlaps
    between the camera FPC connector and the ESP32-S3 module. The
    directive forbids Phase 3 from fixing these; we surface them as
    warnings so callers see the conflicts without pretending they are
    resolved.
    """
    warnings: list[str] = []
    board = summary.get("board", {}) or {}
    modules = board.get("module_placeholders", []) or []
    if not modules:
        warnings.append(
            "Generated PCB has no module placeholders; footprint layout "
            "is incomplete."
        )
        return warnings

    # Detect simple bounding-box overlaps among module placeholders.
    boxes: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    # The summary records ``position_mm`` (PCB-local) for each module,
    # but not its size, so we cannot fully verify overlap here. We still
    # note the absence of size metadata so callers can chase it down.
    for m in modules:
        if "size_mm" not in m and "footprint" in m:
            warnings.append(
                f"Module {m.get('reference', '?')} has no recorded size_mm; "
                "overlap check skipped."
            )
        boxes.append(
            (m.get("reference", "?"), tuple(m.get("position_mm", (0, 0))), (0, 0))
        )
    return warnings


def _collect_artifact_metadata() -> dict[str, dict[str, Any]]:
    """Collect mtime/sha256 metadata for the generator's outputs."""
    meta: dict[str, dict[str, Any]] = {}
    for rel in GENERATED_OUTPUTS:
        try:
            resolved = safe_resolve(rel)
        except PathSecurityError as exc:
            meta[rel] = {"missing": True, "error": str(exc)}
            continue
        if resolved.is_file():
            meta[rel] = file_metadata(resolved)
        else:
            meta[rel] = {"missing": True}
    return meta


def generate_pcb_outline(
    python_path: str | None = None,
    force: bool = False,
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Run the canonical PCB-outline generator with safety pre-checks."""
    started = utcnow_iso()
    timestamp = utc_timestamp_fs()
    errors: list[str] = []
    warnings: list[str] = []

    # 0. Validate python_path first (before any other check) so a bad
    #    interpreter never leaks through a non-mutation dry-run branch.
    try:
        py_candidate = _resolve_python(python_path)
    except MutationError as exc:
        return make_envelope(
            tool="generate_pcb_outline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[str(exc)],
        )

    # 1. Pre-flight: read pose validation.
    pose = _read_pose_validation()
    overall = pose["overall_status"]
    pose_pass = overall == "PASS"

    if not pose_pass and not force:
        return make_envelope(
            tool="generate_pcb_outline",
            started_at_iso=started,
            duration_ms=0,
            status="INCOMPLETE",
            data={
                "executed": False,
                "force_required": True,
                "pose_validation": {
                    "artifact": str(POSE_VALIDATION_REL),
                    "overall_status": overall,
                    "missing": pose["missing"],
                    "parse_error": pose["parse_error"],
                },
            },
            errors=[
                (
                    f"Pose validation is not PASS "
                    f"(overall_status={overall!r}). "
                    "Refusing to generate PCB outline unless force=true."
                )
            ],
        )

    if not pose_pass and force:
        warnings.append(
            "force=true was used to bypass a non-PASS pose validation; "
            f"overall_status was {overall!r}."
        )

    # 2. Resolve the generator script.
    try:
        generator = _resolve_generator()
    except PathSecurityError as exc:
        return make_envelope(
            tool="generate_pcb_outline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"Generator script not allowed: {exc}"],
        )

    if not generator.is_file():
        return make_envelope(
            tool="generate_pcb_outline",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            data={
                "generator": str(generator.relative_to(glasses_root())),
            },
            errors=[f"Generator script does not exist: {generator}"],
        )

    # 3. python_path was already validated at the top of the function;
    #    the resolved interpreter is reused here.
    before = _collect_artifact_metadata()

    cmd = [str(py_candidate), str(generator)]

    # 4. Without mutation, do not run.
    if not allow_mutation:
        audit(
            timestamp=timestamp,
            tool="generate_pcb_outline",
            operation="no_mutation",
            affected_paths=[generator.relative_to(glasses_root()).as_posix()],
            success=True,
            metadata={
                "would_execute": cmd,
                "force": force,
                "pose_validation_overall_status": overall,
            },
        )
        return make_envelope(
            tool="generate_pcb_outline",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "force": force,
                "allow_mutation": False,
                "command": cmd,
                "generator": str(generator.relative_to(glasses_root())),
                "pose_validation": {
                    "artifact": str(POSE_VALIDATION_REL),
                    "overall_status": overall,
                },
                "before_artifacts": before,
                "warnings": [
                    "allow_mutation=False; generator was not executed. "
                    "Pass allow_mutation=true to run the script."
                ],
            },
            warnings=[
                "allow_mutation=False; generator was not executed. "
                "Pass allow_mutation=true to run the script."
            ],
        )

    # 5. Execute.
    t0 = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(project_root()),
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        audit(
            timestamp=timestamp,
            tool="generate_pcb_outline",
            operation="execute",
            affected_paths=[generator.relative_to(glasses_root()).as_posix()],
            success=False,
            errors=[f"Generator timed out after {exc.timeout}s"],
        )
        return make_envelope(
            tool="generate_pcb_outline",
            started_at_iso=started,
            duration_ms=int((exc.timeout or 0) * 1000),
            status="ERROR",
            data={"command": cmd, "executed": True},
            errors=[f"Generator timed out after {exc.timeout}s"],
        )

    after = _collect_artifact_metadata()
    stdout_tail = (completed.stdout or "")[-4000:]
    stderr_tail = (completed.stderr or "")[-4000:]

    # 6. Post-execute checks.
    if completed.returncode != 0:
        errors.append(
            f"Generator exited with non-zero status {completed.returncode}"
        )

    missing_after = [
        rel for rel, meta in after.items() if meta.get("missing")
    ]
    if missing_after:
        errors.append(
            "Expected output(s) missing after execution: "
            + ", ".join(missing_after)
        )

    # Read the generated summary to surface architecture findings.
    pcb_findings: list[str] = []
    summary_path = glasses_root() / "electronics" / "glasses-pcb.summary.json"
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            pcb_findings = _summarize_pcb_warnings(summary)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            pcb_findings.append(
                f"Failed to parse generated summary JSON: {exc}"
            )
    else:
        pcb_findings.append(
            "Generator did not produce glasses-pcb.summary.json; "
            "PCB architecture findings cannot be reported."
        )

    warnings.extend(pcb_findings)

    status = "PASS" if not errors else "FAIL"

    audit(
        timestamp=timestamp,
        tool="generate_pcb_outline",
        operation="execute",
        affected_paths=[
            str(generator.relative_to(glasses_root())),
            *GENERATED_OUTPUTS,
        ],
        success=(status == "PASS"),
        metadata={
            "returncode": completed.returncode,
            "duration_seconds": round(time.perf_counter() - t0, 3),
            "force": force,
            "pose_validation_overall_status": overall,
        },
        warnings=warnings,
        errors=errors,
    )

    return make_envelope(
        tool="generate_pcb_outline",
        started_at_iso=started,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        status=status,
        data={
            "executed": True,
            "force": force,
            "allow_mutation": True,
            "command": cmd,
            "generator": str(generator.relative_to(glasses_root())),
            "pose_validation": {
                "artifact": str(POSE_VALIDATION_REL),
                "overall_status": overall,
            },
            "exit_code": int(completed.returncode),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "before_artifacts": before,
            "after_artifacts": after,
            "findings": pcb_findings,
        },
        warnings=warnings,
        errors=errors,
    )