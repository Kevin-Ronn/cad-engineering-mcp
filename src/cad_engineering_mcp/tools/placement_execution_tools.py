"""Phase 7 MCP tools: engineering release execution.

Three tools:

  * ``placement_resolution_plan`` -- read-only inspection of which
    placement-policy YAML coordinates can be resolved from
    ``analysis/geometry/component-pose-validation.json`` (overall_status
    PASS), and which placements already carry authoritative
    coordinates. Never mutates the workspace.

  * ``apply_placement_resolution`` -- controlled write of the resolved
    coordinates back into
    ``mechanical/interfaces/component-placement-policy.yaml`` via the
    standard Phase 3 backup + audit infrastructure. Refuses to
    mutate unless ``allow_mutation=true``. Refuses to draw
    coordinates from a non-PASS pose-validation artifact.

  * ``verify_structural_objectives`` -- reads the structural YAMLs
    directly and verifies the 4 required production-engineering
    objectives are present. Returns PASS whenever every objective is
    authoritatively defined. Never invents data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engineering.plExecution import (
    PlExecutionError,
    apply_placement_resolution as _apply_engineering,
    build_placement_resolution_plan as _build_plan_engineering,
    verify_structural_objectives as _verify_objectives_engineering,
)
from ._envelope import make_envelope, utcnow_iso
from ._mutation import MutationError, perform_write
from ._paths import PathSecurityError, glasses_root


PLACEMENT_POLICY_REL = Path(
    "mechanical/interfaces/component-placement-policy.yaml"
)


def placement_resolution_plan() -> dict[str, Any]:
    """Read-only inspection of the placement-resolution plan.

    Returns a structured envelope whose ``data`` carries the full
    plan: pose-validation metadata (path / sha256 / overall_status /
    accepted_count / components), every placement's current
    coordinates, the resolved coordinates (when available), and the
    explicit provenance for each resolution.
    """
    started = utcnow_iso()
    try:
        plan = _build_plan_engineering(glasses_root=glasses_root())
    except (PlExecutionError, OSError) as exc:
        return make_envelope(
            tool="placement_resolution_plan",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="placement_resolution_plan",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data=plan,
    )


def apply_placement_resolution(
    *,
    only_keys: list[str] | None = None,
    allow_mutation: bool = False,
) -> dict[str, Any]:
    """Persist resolved placement coordinates.

    Dry-run by default; refuses to mutate unless
    ``allow_mutation=true``. The mutation flows through the standard
    Phase 3 ``perform_write`` helper (backup + audit).

    Args:
        only_keys: optional list of YAML placement keys (e.g.
            ``["placements.front_left_led"]``). When provided, only
            those placements are mutated; the rest of the RESOLVE
            actions are skipped.
        allow_mutation: must be ``True`` to actually write.

    Returns a structured envelope. When ``allow_mutation=False`` the
    tool performs a dry-run that audit-logs the intent and reports
    the would-apply summary.
    """
    started = utcnow_iso()
    try:
        plan = _build_plan_engineering(glasses_root=glasses_root())
    except (PlExecutionError, OSError) as exc:
        return make_envelope(
            tool="apply_placement_resolution",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    resolvable = plan["summary"]["resolvable"]
    if resolvable == 0:
        return make_envelope(
            tool="apply_placement_resolution",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "applied": 0,
                "skipped": 0,
                "resolutions": plan["resolutions"],
            },
            warnings=[
                "No RESOLVE actions in plan; nothing to apply."
            ]
        )

    if not allow_mutation:
        from ._mutation import audit as _audit, utc_timestamp_fs

        _audit(
            timestamp=utc_timestamp_fs(),
            tool="apply_placement_resolution",
            operation="no_mutation_dry_run",
            affected_paths=[str(PLACEMENT_POLICY_REL)],
            success=True,
            metadata={
                "would_apply": resolvable,
                "allow_mutation": False,
                "only_keys": only_keys,
                "plan_status": plan["status"],
            },
        )
        return make_envelope(
            tool="apply_placement_resolution",
            started_at_iso=started,
            duration_ms=0,
            status="PASS",
            data={
                "executed": False,
                "allow_mutation": False,
                "would_apply": resolvable,
                "resolutions": plan["resolutions"],
                "summary": plan["summary"],
            },
            warnings=[
                "allow_mutation=False; coordinates were not persisted. "
                "Pass allow_mutation=true to commit."
            ],
        )

    # allow_mutation=True path.
    try:
        result = _apply_engineering(
            glasses_root=glasses_root(),
            perform_write_fn=perform_write,
            only_keys=only_keys,
        )
    except (PlExecutionError, MutationError, OSError) as exc:
        return make_envelope(
            tool="apply_placement_resolution",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    return make_envelope(
        tool="apply_placement_resolution",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data=result,
    )


def verify_structural_objectives() -> dict[str, Any]:
    """Verify the 4 required structural-policy objectives.

    Read-only. Returns a structured envelope whose ``data`` carries
    the on-disk state of ``structural-policy.yaml`` and
    ``rib-system.yaml``: objectives_present, objectives_missing,
    interfaces_present, exclusions_present.
    """
    started = utcnow_iso()
    try:
        result = _verify_objectives_engineering(glasses_root=glasses_root())
    except (OSError, PlExecutionError) as exc:
        return make_envelope(
            tool="verify_structural_objectives",
            started_at_iso=started,
            duration_ms=0,
            status="ERROR",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return make_envelope(
        tool="verify_structural_objectives",
        started_at_iso=started,
        duration_ms=0,
        status="PASS",
        data=result,
    )


__all__ = [
    "apply_placement_resolution",
    "placement_resolution_plan",
    "verify_structural_objectives",
]