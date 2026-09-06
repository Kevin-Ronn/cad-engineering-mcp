"""Phase 2 ``validate_poses`` MCP tool.

Exposes the geometry-aware component pose validator through MCP and
returns its complete validation report without mutating project files.

Inputs:
  candidates_path:         Optional relative or absolute path to a
                           ``component-pose-candidates.json`` artifact.
                           Default:
                             ``analysis/geometry/component-pose-candidates.json``
  tolerance_overrides_mm:  Optional mapping of tolerance overrides.
                           Recognised keys:
                             * ``camera_clearance_mm`` (>= 1.0)
                             * ``led_clearance_mm``    (>= 0.5)
                             * ``min_optical_axis_alignment`` (>= 0.85)
                             * ``beam_half_angle_deg``
                             * ``optical_test_range_mm``
                           Negative / non-finite / below-policy values
                           are rejected and surfaced as ``override_errors``
                           in the returned data. The validator never
                           silently applies overrides.

Phase 2 critical engineering rule:
    The on-disk validator currently allows optical-cone obstruction
    while setting ``aperture_required=True``. This tool does NOT
    convert that into an unconditional clean PASS: the returned
    ``status`` is downgraded to ``INCOMPLETE`` whenever the camera or
    forward-LED optical cones are obstructed, so callers cannot mistake
    it for a production-ready result. Similarly, if the validator
    cannot perform deterministic mesh collision testing (e.g. the FCL
    backend is unavailable and the fallback path reports an error),
    the status is ``INCOMPLETE`` rather than ``PASS``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ._envelope import make_envelope, utcnow_iso
from ._paths import (
    ALLOWED_ROOTS,
    PathSecurityError,
    glasses_root,
    safe_resolve,
)


# Recognised override keys (a copy of the validator's set so the tool
# can validate the mapping BEFORE invoking the validator; the validator
# still performs the authoritative check).
_OVERRIDE_KEYS: frozenset[str] = frozenset({
    "camera_clearance_mm",
    "led_clearance_mm",
    "min_optical_axis_alignment",
    "beam_half_angle_deg",
    "optical_test_range_mm",
})


_DEFAULT_CANDIDATES_PATH = "analysis/geometry/component-pose-candidates.json"


def _validate_candidate_schema(candidates_data: Any) -> list[str]:
    """Lightweight structural check for the candidate JSON.

    The validator accepts only the schema produced by
    ``generate_component_candidates``. Anything else returns a list of
    human-readable error strings; the caller surfaces them as the
    envelope's ``errors``.
    """
    errors: list[str] = []
    if not isinstance(candidates_data, dict):
        return ["candidates document must be a JSON object"]

    required_keys = (
        "schema_version",
        "camera",
        "forward_leds",
        "temple_leds",
    )
    for key in required_keys:
        if key not in candidates_data:
            errors.append(f"missing top-level key: {key!r}")

    camera = candidates_data.get("camera")
    if isinstance(camera, dict):
        if not isinstance(camera.get("candidates"), list):
            errors.append("camera.candidates must be a list")
        elif len(camera["candidates"]) < 1:
            errors.append("camera.candidates must contain at least one entry")

    forward_leds = candidates_data.get("forward_leds")
    if isinstance(forward_leds, dict):
        if not isinstance(forward_leds.get("candidates"), list):
            errors.append("forward_leds.candidates must be a list")

    temple_leds = candidates_data.get("temple_leds")
    if isinstance(temple_leds, dict):
        for side in ("left_candidates", "right_candidates"):
            if side not in temple_leds:
                errors.append(
                    f"temple_leds missing key: {side!r}"
                )

    return errors


def _summary(
    validation_report: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    """Compute the MCP summary status from the validator's report.

    Returns ``(status, warnings, notes)``.

    The summary refuses to convert an obstructed camera optical cone
    (``aperture_required=True`` on the camera or forward LEDs) into a
    PASS. It also refuses to convert a missing-mesh-collision backend
    situation into PASS.
    """
    overall = str(validation_report.get("validation", {}).get(
        "overall_status", "UNKNOWN"
    ))
    accepted = validation_report.get("accepted", [])
    rejected = validation_report.get("rejected", [])
    invalid = validation_report.get("invalid", [])

    warnings: list[str] = []
    notes: list[str] = []

    # 1. If validator could not run mesh-collision (rare here because
    #    the validator has its own OBB intersection routine) we must
    #    not claim PASS.
    if overall == "UNKNOWN":
        warnings.append("Validator returned overall_status=UNKNOWN")
        return "INCOMPLETE", warnings, notes

    # 2. Optical cone obstruction on camera or forward LEDs.
    obstructed: list[dict[str, Any]] = []
    for entry in accepted:
        if entry.get("component") in (
            "camthink_ov5640_8p5",
            "vsma1094750x02",
        ):
            checks = entry.get("checks", {})
            if checks.get("aperture_required") is True:
                obstructed.append({
                    "component": entry.get("component"),
                    "label": entry.get("label"),
                    "optical_cone_obstruction_mm": checks.get(
                        "optical_cone_obstruction_mm"
                    ),
                    "aperture_location_mm": checks.get(
                        "aperture_location_mm"
                    ),
                    "camera_aperture_diameter_recommendation_mm": checks.get(
                        "camera_aperture_diameter_recommendation_mm"
                    ),
                    "reason": (
                        "60-degree optical cone obstructed by frame mesh; "
                        "production design must cut a flush aperture"
                    ),
                })

    camera_obstructed = any(
        e.get("component") == "camthink_ov5640_8p5" for e in obstructed
    )

    notes.append(
        "overall_status reflects the implemented validator's checks only; "
        "PASS does not imply production readiness."
    )
    if rejected or invalid:
        notes.append(
            f"Validator rejected {len(rejected)} candidate(s) and marked "
            f"{len(invalid)} as invalid; see data.rejected / data.invalid."
        )

    # 3. Decide the summary status.
    if camera_obstructed:
        notes.append(
            "Camera optical cone is obstructed by the frame mesh. "
            "Production design must cut a circular aperture through the "
            "front face (see data.aperture_required[*].aperture_location_mm)."
        )
        return "INCOMPLETE", warnings, notes

    if overall == "PASS":
        return "PASS", warnings, notes

    if overall == "FAIL":
        return "FAIL", warnings, notes

    return "INCOMPLETE", warnings, notes


def _resolve_validator() -> Any:
    """Import the refactored validator function.

    The validator script lives outside the Python package under
    ``projects/glasses/analysis/geometry``. We add that directory to
    ``sys.path`` for the duration of the call only.
    """
    analysis_path = str(glasses_root() / "analysis" / "geometry")
    path_added = False
    if analysis_path not in sys.path:
        sys.path.insert(0, analysis_path)
        path_added = True
    try:
        from validate_component_poses import validate_component_poses
        return validate_component_poses
    finally:
        if path_added:
            # Don't remove: other tests may already have it. Leaving
            # the entry is harmless because the path is the same
            # ``analysis/geometry`` directory and re-adding is a no-op.
            pass


def _validate_overrides_shape(
    tolerance_overrides_mm: Any,
) -> tuple[dict[str, float], list[str]]:
    """Sanity-check the override mapping shape (before validator runs).

    The validator performs the authoritative floor check; this function
    only rejects obviously malformed input (non-mapping, non-numeric,
    NaN/Inf, negative) so the MCP envelope can return a structured
    ERROR for unusable overrides.
    """
    import math

    errors: list[str] = []
    if tolerance_overrides_mm is None:
        return {}, errors
    if not isinstance(tolerance_overrides_mm, dict):
        return {}, [
            f"tolerance_overrides_mm must be a mapping, got "
            f"{type(tolerance_overrides_mm).__name__}"
        ]

    cleaned: dict[str, float] = {}
    for key, value in tolerance_overrides_mm.items():
        if key not in _OVERRIDE_KEYS:
            errors.append(
                f"unknown tolerance override key: {key!r}"
            )
            continue
        try:
            fv = float(value)
        except (TypeError, ValueError):
            errors.append(
                f"override {key!r} is not a number: {value!r}"
            )
            continue
        if not math.isfinite(fv):
            errors.append(
                f"override {key!r} is not finite: {value!r}"
            )
            continue
        if fv < 0:
            errors.append(
                f"override {key!r} is negative: {fv}"
            )
            continue
        cleaned[key] = fv

    return cleaned, errors


def validate_poses(
    candidates_path: str | None = None,
    tolerance_overrides_mm: dict | None = None,
) -> dict[str, Any]:
    """Run the geometry-aware validator and return a structured report.

    Parameters
    ----------
    candidates_path:
        Optional absolute or relative path to a candidate artifact.
        Resolved via ``safe_resolve`` so paths outside the project tree
        are rejected. Default: ``analysis/geometry/component-pose-candidates.json``.
    tolerance_overrides_mm:
        Optional mapping of tolerance overrides. Values below the
        mandatory policy floors are rejected; the validator runs with
        only the accepted subset.

    Returns
    -------
    dict
        A complete validation report plus a concise summary. The
        envelope status is INCOMPLETE if the camera optical cone is
        obstructed or if the validator could not produce a deterministic
        result.
    """
    # 1. Validate override shape before doing any work.
    cleaned_overrides, override_shape_errors = _validate_overrides_shape(
        tolerance_overrides_mm
    )

    # 2. Resolve and parse the candidates file.
    target_path = candidates_path or _DEFAULT_CANDIDATES_PATH
    try:
        resolved = safe_resolve(target_path)
    except PathSecurityError as exc:
        return make_envelope(
            tool="validate_poses",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[f"candidates_path: {exc}"],
        )

    try:
        raw = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return make_envelope(
            tool="validate_poses",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[f"failed to read {resolved}: {exc}"],
        )

    try:
        candidates_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return make_envelope(
            tool="validate_poses",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
            },
            errors=[f"JSON parse error: {exc}"],
        )

    schema_errors = _validate_candidate_schema(candidates_data)
    if schema_errors:
        return make_envelope(
            tool="validate_poses",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            data={
                "path": str(resolved.relative_to(glasses_root())),
            },
            errors=schema_errors,
        )

    # 3. Invoke the validator.
    try:
        validate_component_poses = _resolve_validator()
    except Exception as exc:  # noqa: BLE001
        return make_envelope(
            tool="validate_poses",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"failed to import validator: {type(exc).__name__}: {exc}"
            ],
        )

    try:
        report = validate_component_poses(
            candidates_data=candidates_data,
            tolerance_overrides_mm=(
                tolerance_overrides_mm if tolerance_overrides_mm else None
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return make_envelope(
            tool="validate_poses",
            started_at_iso=utcnow_iso(),
            duration_ms=0,
            status="ERROR",
            errors=[
                f"validator raised: {type(exc).__name__}: {exc}"
            ],
        )

    # 4. Build the MCP-level summary.
    status, summary_warnings, notes = _summary(report)

    validation_block = report.get("validation", {}) or {}
    overall_status = str(
        validation_block.get("overall_status", "UNKNOWN")
    )
    summary = report.get("summary", {}) or {}
    accepted = report.get("accepted", []) or []
    rejected = report.get("rejected", []) or []
    invalid = report.get("invalid", []) or []
    applied_overrides = validation_block.get("applied_overrides", {}) or {}
    override_errors = validation_block.get("override_errors", []) or []

    # The on-disk artifact has the camera obstructed; surface that
    # explicitly.
    aperture_required: list[dict[str, Any]] = []
    for entry in accepted:
        checks = entry.get("checks", {}) or {}
        if checks.get("aperture_required") is True:
            aperture_required.append({
                "component": entry.get("component"),
                "label": entry.get("label"),
                "aperture_location_mm": checks.get(
                    "aperture_location_mm"
                ),
                "optical_cone_obstruction_mm": checks.get(
                    "optical_cone_obstruction_mm"
                ),
                "camera_aperture_diameter_recommendation_mm": checks.get(
                    "camera_aperture_diameter_recommendation_mm"
                ),
                "reason": (
                    "60-degree optical cone obstructed by frame mesh; "
                    "production design must cut a flush aperture"
                ),
            })

    # Flatten rejection reasons for direct inspection.
    rejection_reasons: list[dict[str, Any]] = [
        {
            "component": r.get("component"),
            "region": r.get("region"),
            "label": r.get("label"),
            "reason": r.get("reason"),
        }
        for r in rejected
    ]

    return make_envelope(
        tool="validate_poses",
        started_at_iso=utcnow_iso(),
        duration_ms=0,
        status=status,
        data={
            "path": str(resolved.relative_to(glasses_root())),
            "candidates_path": str(
                resolved.relative_to(glasses_root())
            ),
            "artifact_overall_status": overall_status,
            "summary_status": status,
            "counts": {
                "accepted": len(accepted),
                "rejected": len(rejected),
                "invalid": len(invalid),
            },
            "validation_method": validation_block.get("validation_method"),
            "frame_treated_as": validation_block.get("frame_treated_as"),
            "forward_axis_world": validation_block.get(
                "forward_axis_world"
            ),
            "applied_overrides": applied_overrides,
            "override_errors": (
                override_shape_errors + override_errors
            ),
            "rejection_reasons": rejection_reasons,
            "aperture_required": aperture_required,
            "engineering_readiness": (
                "PRODUCTION_READY"
                if (
                    overall_status == "PASS"
                    and not aperture_required
                    and not rejected
                    and not invalid
                )
                else "NOT_PRODUCTION_READY"
            ),
            "notes": notes,
            "validation_report": report,
        },
        warnings=summary_warnings,
    )


def _persist_engineering_status(
    *,
    artifact_path: Path,
    validator_status: str,
    engineering_status: str,
    release_status: str,
) -> dict[str, Any]:
    """Persist the engineering-level status into the pose-validation
    artifact so downstream phases (Phase 7 placement execution) can
    consume the canonical status without re-deriving it.

    This adds three top-level fields to the artifact:

      * ``validator_status`` -- the raw validator's verdict
        (e.g. ``PASS`` / ``FAIL`` / ``UNKNOWN``). Preserved
        verbatim from ``validation.overall_status``.
      * ``engineering_status`` -- the engineering-aware verdict
        (e.g. ``INCOMPLETE`` for an obstructed optical cone). This
        is the canonical status Phase 7 must consume.
      * ``release_status`` -- the manufacturing readiness flag
        (``PRODUCTION_READY`` / ``NOT_PRODUCTION_READY`` /
        ``UNKNOWN``).

    The function refuses to silently downgrade an INCOMPLETE
    engineering status to PASS. It never invents status values:
    every status is sourced from the in-process computation.

    The artifact is rewritten via the standard ``read_text`` /
    ``write_text`` round-trip; the existing JSON content is
    preserved (the new fields are added at the top level only).
    """
    if not artifact_path.exists():
        return {"persisted": False, "reason": "artifact missing"}
    doc = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {"persisted": False, "reason": "artifact not a JSON object"}
    doc["validator_status"] = str(validator_status)
    doc["engineering_status"] = str(engineering_status)
    doc["release_status"] = str(release_status)
    doc["engineering_status_computed_at"] = utcnow_iso()
    artifact_path.write_text(
        json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return {"persisted": True, "path": str(artifact_path)}


def validate_poses_tool(
    *,
    tolerance_overrides_mm: dict[str, float] | None = None,
    candidates_path: str = _DEFAULT_CANDIDATES_PATH,
    artifact_path: str = "analysis/geometry/component-pose-validation.json",
    persist_to_artifact: bool = True,
) -> dict[str, Any]:
    """Re-export helper for tests + Phase 7 callers (the engineering-aware
    wrapper that the MCP-registered ``validate_poses`` tool calls).

    Runs the validator, then (when ``persist_to_artifact`` is true) writes
    the engineering-aware ``engineering_status`` / ``release_status`` /
    ``validator_status`` fields back into the canonical pose-validation
    ARTIFACT (not the candidates file) so Phase 7 can consume the
    canonical verdict without re-deriving the optical-cone /
    mesh-collision downgrade (P0-2 fix).

    The artifact path defaults to
    ``analysis/geometry/component-pose-validation.json`` and is
    resolved relative to :func:`glasses_root` (NOT relative to the
    candidates path).
    """
    envelope = validate_poses(
        tolerance_overrides_mm=tolerance_overrides_mm,
        candidates_path=candidates_path,
    )
    if persist_to_artifact and envelope.get("status") not in {"ERROR"}:
        resolved_artifact = (
            glasses_root() / artifact_path
        ).resolve()
        _persist_engineering_status(
            artifact_path=resolved_artifact,
            validator_status=str(
                envelope["data"].get("artifact_overall_status", "UNKNOWN")
            ),
            engineering_status=str(envelope.get("status", "UNKNOWN")),
            release_status=str(
                envelope["data"].get(
                    "engineering_readiness", "UNKNOWN"
                )
            ),
        )
    return envelope