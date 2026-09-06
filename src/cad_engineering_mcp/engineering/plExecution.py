"""Phase 7 engineering release-execution module.

Phase 5 produced a release-blocker manifest from the existing YAML
state. Phase 6 added the formal provenance + authoritative-override
infrastructure for resolving UNKNOWN/TBD blockers with explicit
provenance. Phase 7 closes the loop for the two blocker categories
that have *authoritative, in-project sources* the existing
infrastructure already contains but does not auto-route:

  * **Placement coordinates** -- the project carries
    ``analysis/geometry/component-pose-validation.json`` with an
    overall_status of ``PASS`` and a populated ``accepted`` list of
    geometry-derived poses (camera + 6 LEDs). The placement policy
    YAML (``mechanical/interfaces/component-placement-policy.yaml``)
    declares ``coordinates: TBD`` for each placement even though the
    authoritative coordinates already exist in the analysis JSON.
    Phase 7 surfaces a deterministic execution plan that maps every
    accepted pose onto its YAML placeholder and persists the
    resolved coordinates with provenance.

  * **Structural-policy objectives / interfaces / exclusions** --
    the structural YAMLs already contain every required objective,
    interface, and exclusion, but the Phase 5 aggregator relied on
    the (incomplete) output of :func:`validate_structural_policy`
    and fabricated ``missing_objectives`` when the key was absent.
    Phase 7 fixes that synthesis bug (see :mod:`release_blockers`)
    so the aggregator no longer fabricates missing-objective
    blockers from absent keys.

Engineering rules (mirrors of the directive):

* Coordinates are only ever read from
    ``analysis/geometry/component-pose-validation.json`` when its
    ``validation.overall_status == "PASS"``. Refuses to read
    partial / incomplete pose data.
* Each resolved placement carries explicit provenance (source
    artifact path, sha256, pose index, kind).
* Refuses to overwrite a placement whose coordinates is already an
    authoritative source (non-TBD, non-empty numeric vector).
* The placement_policy YAML is rewritten only via the controlled
    Phase 3 ``perform_write`` helper (backup + audit), never by
    direct file I/O.
* The execution plan is deterministic: two runs over the same
    project state produce the same plan.
* No fabrication. If the pose validation is not PASS, no
    placement coordinates can be resolved; the plan surfaces the
    blocker honestly.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class PlExecutionError(RuntimeError):
    """Raised by the Phase 7 placement-execution module on invalid input."""


POSE_VALIDATION_REL = Path("analysis/geometry/component-pose-validation.json")
PLACEMENT_POLICY_REL = Path("mechanical/interfaces/component-placement-policy.yaml")


# ---------------------------------------------------------------------------
# Canonical engineering-status resolution
# ---------------------------------------------------------------------------


def _resolve_pose_validation_status(doc: dict[str, Any]) -> tuple[str, str]:
    """Return ``(canonical_status, status_kind)`` for a pose-validation
    artifact.

    P0-2 fix: Phase 7 consumes the canonical engineering-aware status,
    NOT the raw ``validation.overall_status``. The legacy raw PASS
    is no longer a sufficient condition for Phase 7 to consume the
    artifact -- that was the original P0-2 audit finding (raw PASS
    bypass of the engineering-level INCOMPLETE downgrade for
    obstructed optical cones / missing mesh-collision backend).

    The artifact carries three status fields produced by
    :func:`validate_poses_tool`:

      * ``engineering_status`` -- the canonical engineering verdict
        consumed by Phase 7.
      * ``validator_status`` -- the raw validator's verdict. This is
        NOT sufficient on its own for Phase 7.
      * ``release_status`` -- the manufacturing/release readiness
        result. This is a SEPARATE concept from engineering_status
        (it does not replace or downgrade it); Phase 7 must not
        treat it as a fallback.

    Resolution precedence (canonical for Phase 7):

      1. ``engineering_status`` -- if present, it is the canonical
         verdict. ``PASS`` -> proceed; anything else -> reject.
      2. ``engineering_status`` absent -- the artifact is LEGACY
         (produced before the engineering-aware tool was wired into
         the MCP path). Phase 7 must FAIL CLOSED and require the
         operator to re-run the engineering-aware ``validate_poses``
         tool so the canonical fields are populated. Legacy raw
         PASS is explicitly NOT trusted.

    ``status_kind`` records which path was used so callers can
    detect legacy artifacts and re-run the engineering-aware tool.
    """
    engineering_status = doc.get("engineering_status")
    if isinstance(engineering_status, str) and engineering_status:
        return engineering_status, "engineering_status"
    # No canonical engineering_status -- legacy artifact. Fail
    # closed. We do NOT fall back to validator_status or to
    # validation.overall_status; doing so would re-introduce the
    # raw-PASS bypass that P0-2 audit specifically called out.
    return "LEGACY_NO_ENGINEERING_STATUS", "legacy"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except (OSError, FileNotFoundError):
        return None


def _load_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PlExecutionError(f"File not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise PlExecutionError(
            f"File is not valid UTF-8: {path}"
        ) from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PlExecutionError(
            f"YAML parse error in {path}: {exc}"
        ) from exc


def _load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PlExecutionError(f"File not found: {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlExecutionError(
            f"JSON parse error in {path}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Pose validation reader
# ---------------------------------------------------------------------------


def _load_pose_validation(glasses_root: Path) -> dict[str, Any]:
    """Load the component-pose-validation artifact.

    Raises :class:`PlExecutionError` when:

      * the artifact is missing;
      * the artifact carries no ``engineering_status`` field
        (legacy artifact produced before the engineering-aware
        ``validate_poses`` tool was wired into the MCP path);
      * the canonical engineering status is not ``PASS``.

    P0-2 fix: legacy raw PASS is NOT a sufficient condition for
    Phase 7. The original audit finding was that raw
    ``validation.overall_status == "PASS"`` could be consumed by
    Phase 7 even when the engineering-aware status (e.g. for an
    obstructed optical cone) was INCOMPLETE. The MCP path now
    persists ``engineering_status`` to the artifact; Phase 7
    requires it.
    """
    path = glasses_root / POSE_VALIDATION_REL
    if not path.exists():
        raise PlExecutionError(
            f"Pose validation artifact missing: {path}. "
            "Run the geometry solver pipeline first."
        )
    doc = _load_json(path)
    if not isinstance(doc, dict):
        raise PlExecutionError(
            f"Pose validation artifact is not a JSON object: {path}"
        )
    canonical_status, status_kind = _resolve_pose_validation_status(doc)
    if canonical_status == "LEGACY_NO_ENGINEERING_STATUS":
        raise PlExecutionError(
            "Pose validation artifact is legacy: it carries no "
            "engineering_status field. The original P0-2 audit "
            "finding specifically forbade trusting raw "
            "validation.overall_status == 'PASS' as sufficient for "
            "Phase 7. Re-run the engineering-aware 'validate_poses' "
            "MCP tool so the canonical engineering_status is "
            "persisted to the artifact."
        )
    if canonical_status != "PASS":
        raise PlExecutionError(
            "Pose validation canonical status "
            f"({status_kind}) is {canonical_status!r}; "
            "refused to derive placement coordinates from a "
            "non-authoritative source."
        )
    return doc


def _index_pose_validation(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index the accepted poses by the authoritative unique identity.

    P0-3 fix: the index key is ``component::region::identity`` where
    ``identity`` is the entry's ``label`` field if present, or the
    literal string ``"_no_label"`` otherwise. This keeps the index
    scheme uniform across all entries (cameras with ``label: null``
    and LEDs with explicit labels both produce stable keys) while
    preserving the ability to disambiguate multiple physical
    instances of the same component and region.

    A duplicate ``(component, region, identity)`` is treated as an
    ambiguous authoring error: the conflicting key is REMOVED from
    the index so that :func:`_pose_at` returns ``None`` (fail-closed).
    The duplicate is recorded in ``_duplicates`` for diagnostic
    visibility. Phase 7 will surface such duplicates as
    ``SKIP_NO_AUTHORITATIVE_POSE`` and refuse to fabricate a
    resolution.
    """
    accepted = doc.get("accepted", []) or []
    if not isinstance(accepted, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for entry in accepted:
        if not isinstance(entry, dict):
            continue
        component = entry.get("component")
        region = entry.get("region")
        if not component or not region:
            continue
        label_value = entry.get("label")
        identity = str(label_value) if label_value else "_no_label"
        key = f"{component}::{region}::{identity}"
        if key in index:
            # Fail-closed: remove the conflicting entry from the
            # index so neither occurrence can be resolved. The
            # duplicate is logged for diagnostics.
            del index[key]
            duplicates.append(
                {
                    "component": component,
                    "region": region,
                    "label": label_value,
                }
            )
            continue
        index[key] = entry
    if duplicates:
        index["_duplicates"] = {"items": duplicates}  # type: ignore[assignment]
    return index


# ---------------------------------------------------------------------------
# Placement policy reader
# ---------------------------------------------------------------------------


def _placement_yield_components(doc: dict[str, Any]) -> dict[str, str]:
    """Build the ``{placement_key: side_or_label}`` map for the YAML.

    ``side_or_label`` is the natural-language annotation the
    :class:`PlacementResolver` uses to disambiguate placements that
    share a region (e.g. ``front_left``, ``front_left_aux``). The
    resolver never invents this label -- it is read verbatim from the
    YAML structure.

    The returned mapping has these keys (when present):

        placements.front_left_led.region
        placements.front_right_led.region
        placements.left_temple_led_front.region
        placements.left_temple_led_rear.region
        placements.right_temple_led_front.region
        placements.right_temple_led_rear.region
        cameras.<camera_id>.region
    """
    mapping: dict[str, str] = {}
    if not isinstance(doc, dict):
        return mapping
    placements = doc.get("placements", {}) or {}
    if isinstance(placements, dict):
        for key, value in placements.items():
            if not isinstance(value, dict):
                continue
            mapping[f"placements.{key}"] = str(value.get("region", ""))
    cameras = doc.get("cameras", {}) or {}
    if isinstance(cameras, dict):
        for key, value in cameras.items():
            if not isinstance(value, dict):
                continue
            mapping[f"cameras.{key}"] = str(value.get("region", ""))
    return mapping


# ---------------------------------------------------------------------------
# Placement resolver
# ---------------------------------------------------------------------------


# Map YAML placement keys to (component_id, region) tuples that
# appear in component-pose-validation.json. The mapping is read-only
# data -- no inference, no fabrication. When a YAML key is missing
# from this map the resolver returns ``None`` (the placement cannot
# be auto-resolved; the YAML is left untouched).
#
# P0-3 fix: each entry is keyed by the *authoritative unique pose
# identity* -- a triple of (component_id, region, label). Multiple
# physical instances of the same component and region (e.g. two
# forward LEDs with labels ``forward_led_bottom`` /
# ``forward_led_top``) are now distinct and resolve to their own
# coordinates. Previously these collapsed onto the first occurrence.
PLACEMENT_KEY_TO_POSE: dict[str, tuple[str, str, str]] = {
    # Front-frame LEDs (the artifact carries two distinct physical
    # instances under the same component+region; each is identified
    # by its ``label``).
    "placements.front_left_led": (
        "vsma1094750x02",
        "front_frame",
        "forward_led_bottom",
    ),
    "placements.front_right_led": (
        "vsma1094750x02",
        "front_frame",
        "forward_led_top",
    ),
    # Temple LEDs (one per side, one each side of the temple).
    "placements.left_temple_led_front": (
        "vsma1094750x02",
        "left_temple",
        "left_temple_led_front",
    ),
    "placements.left_temple_led_rear": (
        "vsma1094750x02",
        "left_temple",
        "left_temple_led_rear",
    ),
    "placements.right_temple_led_front": (
        "vsma1094750x02",
        "right_temple",
        "right_temple_led_front",
    ),
    "placements.right_temple_led_rear": (
        "vsma1094750x02",
        "right_temple",
        "right_temple_led_rear",
    ),
    # Camera placements (single OV5640 in center_nose_bridge;
    # all four YAML keys resolve to the same canonical pose -- the
    # artifact carries ``label: null`` for the camera entry, so we
    # index it under the ``_no_label`` sentinel per _index_pose_validation).
    "cameras.left_camera_front": (
        "camthink_ov5640_8p5",
        "center_nose_bridge",
        "_no_label",
    ),
    "cameras.left_camera_rear": (
        "camthink_ov5640_8p5",
        "center_nose_bridge",
        "_no_label",
    ),
    "cameras.right_camera_front": (
        "camthink_ov5640_8p5",
        "center_nose_bridge",
        "_no_label",
    ),
    "cameras.right_camera_rear": (
        "camthink_ov5640_8p5",
        "center_nose_bridge",
        "_no_label",
    ),
}


def _pose_at(
    index: dict[str, dict[str, Any]], key: str
) -> dict[str, Any] | None:
    """Look up a pose by YAML placement key.

    P0-3 fix: the index is keyed by ``component::region::label`` so
    multiple physical instances of the same component and region
    remain distinct. A missing or ambiguous triple returns ``None``
    (fail-closed); the resolver surfaces it as
    ``SKIP_NO_AUTHORITATIVE_POSE``.
    """
    triple = PLACEMENT_KEY_TO_POSE.get(key)
    if triple is None:
        return None
    component, region, label = triple
    return index.get(f"{component}::{region}::{label}")


def build_placement_resolution_plan(
    *, glasses_root: Path
) -> dict[str, Any]:
    """Build the deterministic placement-resolution plan.

    Reads the pose-validation artifact and the placement-policy YAML
    and emits a structured plan:

        {
          "status":               "RESOLVABLE_NOW" | "BLOCKED",
          "generated_at":         ISO,
          "pose_validation": {
            "path": str,
            "sha256": str | None,
            "overall_status": str,
            "accepted_count": int,
            "components": [str, ...],
          },
          "placement_policy_path": str,
          "resolutions": [
            {
              "placement_key",
              "component_id",
              "region",
              "pose_index",
              "coordinates_from_yaml": "TBD" | "...",
              "resolved_coordinates_mm": [x, y, z],
              "provenance": {
                "kind": "geometry_derived",
                "source_path": str,
                "source_sha256": str,
                "source_overall_status": "PASS",
                "pose_index": int,
              },
              "action": "RESOLVE" | "SKIP_ALREADY_RESOLVED" |
                         "SKIP_NO_AUTHORITATIVE_POSE",
              "reason": str,
            },
            ...
          ],
          "summary": {
            "total_placements": int,
            "resolvable": int,
            "already_resolved": int,
            "no_authoritative_pose": int,
          },
        }

    The plan never invents a value. A placement whose coordinates
    field is already an authoritative number (not ``TBD``/``UNKNOWN``)
    is skipped (it is already resolved). A placement that maps to a
    pose-validation key with no matching pose is reported as
    ``SKIP_NO_AUTHORITATIVE_POSE``.
    """
    pose_doc = _load_pose_validation(glasses_root=glasses_root)
    pose_path = glasses_root / POSE_VALIDATION_REL
    pose_sha = _file_sha256(pose_path)
    canonical_status, _status_kind = _resolve_pose_validation_status(
        pose_doc
    )
    index = _index_pose_validation(pose_doc)
    accepted = pose_doc.get("accepted", []) or []
    components_seen: list[str] = []
    for entry in accepted:
        if isinstance(entry, dict):
            component = entry.get("component")
            if component and component not in components_seen:
                components_seen.append(str(component))

    policy_path = glasses_root / PLACEMENT_POLICY_REL
    policy_doc = _load_yaml(policy_path)
    mapping = _placement_yield_components(policy_doc)

    # Walk the policy in deterministic order.
    plan_keys: list[str] = []
    placements_section = (
        policy_doc.get("placements", {}) if isinstance(policy_doc, dict) else {}
    )
    cameras_section = (
        policy_doc.get("cameras", {}) if isinstance(policy_doc, dict) else {}
    )
    if isinstance(placements_section, dict):
        for key in sorted(placements_section.keys()):
            plan_keys.append(f"placements.{key}")
    if isinstance(cameras_section, dict):
        for key in sorted(cameras_section.keys()):
            plan_keys.append(f"cameras.{key}")

    resolutions: list[dict[str, Any]] = []
    resolvable = 0
    already_resolved = 0
    no_authoritative_pose = 0

    for placement_key in plan_keys:
        container = "placements"
        sub_key = placement_key.split(".", 1)[1] if "." in placement_key else ""
        # Find the coordinates field as currently stored in the YAML.
        coord_value: Any = "MISSING"
        try:
            container_dict = (
                policy_doc.get("placements", {})
                if container == "placements"
                else policy_doc.get("cameras", {})
            )
            if (
                isinstance(container_dict, dict)
                and sub_key in container_dict
                and isinstance(container_dict[sub_key], dict)
            ):
                coord_value = container_dict[sub_key].get("coordinates", "MISSING")
        except (AttributeError, TypeError):
            coord_value = "MISSING"

        # Determine the action.
        pose = _pose_at(index, placement_key)
        component_id, region, label = PLACEMENT_KEY_TO_POSE.get(
            placement_key, (None, None, None)
        )
        if pose is None:
            no_authoritative_pose += 1
            resolutions.append(
                {
                    "placement_key": placement_key,
                    "component_id": component_id,
                    "region": mapping.get(placement_key, ""),
                    "pose_index": None,
                    "coordinates_from_yaml": coord_value,
                    "resolved_coordinates_mm": None,
                    "provenance": None,
                    "action": "SKIP_NO_AUTHORITATIVE_POSE",
                    "reason": (
                        "Placement key is not mapped to a "
                        "component-pose-validation entry; no "
                        "authoritative source."
                    ),
                }
            )
            continue
        center_mm = pose.get("center_mm")
        # Determine "already resolved": a non-TBD, non-UNKNOWN,
        # non-empty, finite 3-vector of floats.
        is_authoritative = (
            isinstance(coord_value, list)
            and len(coord_value) == 3
            and all(
                isinstance(v, (int, float)) and v == v for v in coord_value
            )
        )
        if is_authoritative:
            already_resolved += 1
            resolutions.append(
                {
                    "placement_key": placement_key,
                    "component_id": component_id,
                    "region": mapping.get(placement_key, ""),
                    "pose_index": _pose_index(
                        accepted, pose
                    ),
                    "coordinates_from_yaml": list(coord_value),
                    "resolved_coordinates_mm": None,
                    "provenance": None,
                    "action": "SKIP_ALREADY_RESOLVED",
                    "reason": (
                        "Placement coordinates are already an "
                        "authoritative 3-vector."
                    ),
                }
            )
            continue
        if not (
            isinstance(center_mm, list)
            and len(center_mm) == 3
            and all(
                isinstance(v, (int, float)) and v == v for v in center_mm
            )
        ):
            no_authoritative_pose += 1
            resolutions.append(
                {
                    "placement_key": placement_key,
                    "component_id": component_id,
                    "region": mapping.get(placement_key, ""),
                    "pose_index": None,
                    "coordinates_from_yaml": coord_value,
                    "resolved_coordinates_mm": None,
                    "provenance": None,
                    "action": "SKIP_NO_AUTHORITATIVE_POSE",
                    "reason": (
                        "Pose-validation entry has no valid center_mm."
                    ),
                }
            )
            continue
        # Action: RESOLVE.
        resolvable += 1
        resolutions.append(
            {
                "placement_key": placement_key,
                "component_id": component_id,
                "region": mapping.get(placement_key, ""),
                "pose_index": _pose_index(accepted, pose),
                "coordinates_from_yaml": coord_value,
                "resolved_coordinates_mm": [
                    float(v) for v in center_mm
                ],
                "provenance": {
                    "kind": "geometry_derived",
                    "source_path": str(POSE_VALIDATION_REL),
                    "source_sha256": pose_sha,
                    "source_overall_status": canonical_status,
                    "pose_index": _pose_index(accepted, pose),
                    "component_id": component_id,
                    "region": region,
                },
                "action": "RESOLVE",
                "reason": (
                    "Placement coordinate resolved from authoritative "
                    "component-pose-validation.json (overall_status PASS)."
                ),
            }
        )

    status = "RESOLVABLE_NOW" if resolvable > 0 else "NO_RESOLUTIONS"
    if resolvable == 0 and already_resolved > 0:
        status = "ALL_ALREADY_RESOLVED"
    elif (
        resolvable == 0
        and already_resolved == 0
        and no_authoritative_pose > 0
    ):
        status = "BLOCKED_NO_AUTHORITATIVE_SOURCE"

    return {
        "status": status,
        "generated_at": _now_utc(),
        "pose_validation": {
            "path": str(POSE_VALIDATION_REL),
            "sha256": pose_sha,
            "overall_status": canonical_status,
            "accepted_count": len(accepted),
            "components": components_seen,
        },
        "placement_policy_path": str(PLACEMENT_POLICY_REL),
        "resolutions": resolutions,
        "summary": {
            "total_placements": len(resolutions),
            "resolvable": resolvable,
            "already_resolved": already_resolved,
            "no_authoritative_pose": no_authoritative_pose,
        },
    }


def _pose_index(
    accepted: Iterable[Any], target: dict[str, Any]
) -> int | None:
    """Return the index of ``target`` in ``accepted`` (0-based), or None."""
    for i, entry in enumerate(accepted):
        if entry is target:
            return i
    return None


# ---------------------------------------------------------------------------
# Controlled-write resolver
# ---------------------------------------------------------------------------


def apply_placement_resolution(
    *,
    glasses_root: Path,
    perform_write_fn,
    only_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Resolve placement coordinates in the policy YAML using the
    deterministic plan from :func:`build_placement_resolution_plan`.

    Every mutation flows through ``perform_write_fn`` (the Phase 3
    backup + audit helper) so the change is reversible and
    audit-logged. The function never invents a value: it only
    persists coordinates taken verbatim from the pose-validation
    artifact.

    Args:
        glasses_root: project root.
        perform_write_fn: the Phase 3 controlled-write helper.
        only_keys: optional iterable of YAML placement keys (e.g.
            ``["placements.front_left_led"]``); when provided only
            those placements are mutated. By default every
            ``RESOLVE`` action is applied.

    Returns:

        {
          "executed": bool,
          "applied": int,
          "skipped": int,
          "errors": [str, ...],
          "resolutions": [resolution dict, ...],
          "write_summary": {...} | None,
        }
    """
    plan = build_placement_resolution_plan(glasses_root=glasses_root)
    if plan["status"] == "BLOCKED_NO_AUTHORITATIVE_SOURCE":
        return {
            "executed": False,
            "applied": 0,
            "skipped": 0,
            "errors": [
                "Pose validation is not PASS; refusing to resolve "
                "placements from a non-authoritative source."
            ],
            "resolutions": plan["resolutions"],
            "write_summary": None,
        }

    only_set = set(only_keys) if only_keys is not None else None

    # Load the policy YAML as text so the write is lossless.
    policy_path = glasses_root / PLACEMENT_POLICY_REL
    original_text = policy_path.read_text(encoding="utf-8")
    doc = yaml.safe_load(original_text)
    if not isinstance(doc, dict):
        return {
            "executed": False,
            "applied": 0,
            "skipped": 0,
            "errors": [
                "Placement policy YAML root is not a mapping; refusing "
                "to mutate."
            ],
            "resolutions": plan["resolutions"],
            "write_summary": None,
        }

    applied = 0
    skipped = 0
    errors: list[str] = []
    applied_records: list[dict[str, Any]] = []

    for resolution in plan["resolutions"]:
        if resolution["action"] != "RESOLVE":
            continue
        key = resolution["placement_key"]
        if only_set is not None and key not in only_set:
            continue
        container_name, sub_key = (
            key.split(".", 1) if "." in key else (None, None)
        )
        if container_name not in {"placements", "cameras"} or not sub_key:
            skipped += 1
            continue
        container = doc.get(container_name, {}) or {}
        if not isinstance(container, dict) or sub_key not in container:
            skipped += 1
            errors.append(
                f"Placement {key!r} not present in policy YAML."
            )
            continue
        sub = container[sub_key]
        if not isinstance(sub, dict):
            skipped += 1
            errors.append(
                f"Placement {key!r} sub-entry is not a mapping."
            )
            continue
        # Mutate.
        sub["coordinates"] = list(resolution["resolved_coordinates_mm"])
        sub["coordinate_source"] = {
            "kind": resolution["provenance"]["kind"],
            "source_artifact": resolution["provenance"]["source_path"],
            "source_sha256": resolution["provenance"]["source_sha256"],
            "source_overall_status": resolution["provenance"][
                "source_overall_status"
            ],
            "pose_index": resolution["provenance"]["pose_index"],
            "resolved_at": _now_utc(),
        }
        applied += 1
        applied_records.append(
            {
                "placement_key": key,
                "component_id": resolution["component_id"],
                "resolved_coordinates_mm": list(
                    resolution["resolved_coordinates_mm"]
                ),
                "provenance": resolution["provenance"],
            }
        )

    if applied == 0:
        return {
            "executed": False,
            "applied": 0,
            "skipped": skipped,
            "errors": errors
            + [
                "No RESOLVE actions in plan (or only_keys filter excluded "
                "all of them); no mutation performed."
            ],
            "resolutions": plan["resolutions"],
            "write_summary": None,
        }

    payload = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    write_summary = perform_write_fn(
        destination=str(PLACEMENT_POLICY_REL),
        content=payload,
        tool="apply_placement_resolution",
        operation="resolve",
        metadata={
            "applied": applied,
            "skipped": skipped,
            "applied_records": applied_records,
            "pose_validation_path": str(POSE_VALIDATION_REL),
            "pose_validation_sha256": plan["pose_validation"]["sha256"],
        },
    )
    # The controlled-write helper may signal a dry-run by returning a
    # mapping with ``dry_run`` truthy. Honour that signal: a dry-run
    # never persists anything, so ``executed`` must be False and
    # ``applied`` must be 0 (the in-memory diff never reached disk).
    if isinstance(write_summary, dict) and write_summary.get("dry_run"):
        return {
            "executed": False,
            "applied": 0,
            "skipped": skipped,
            "errors": errors,
            "resolutions": plan["resolutions"],
            "applied_records": applied_records,
            "write_summary": write_summary,
        }
    return {
        "executed": True,
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
        "resolutions": plan["resolutions"],
        "applied_records": applied_records,
        "write_summary": write_summary,
    }


# ---------------------------------------------------------------------------
# Apply structural-policy objectives / interfaces verification
# ---------------------------------------------------------------------------


STRUCTURAL_POLICY_REL = Path("mechanical/main-frame/structural-policy.yaml")
RIB_SYSTEM_REL = Path("mechanical/ribs/rib-system.yaml")


REQUIRED_OBJECTIVES_LIST: tuple[str, ...] = (
    "minimum_structural_mass",
    "minimum_wall_thickness",
    "maximum_required_stiffness",
    "maintain_serviceability",
)


def verify_structural_objectives(
    *, glasses_root: Path
) -> dict[str, Any]:
    """Read the structural YAMLs and verify the required objectives.

    Returns a structured report:

        {
          "status":        "PASS" | "MISSING_OBJECTIVES" | "INCOMPLETE",
          "policy_path":   str,
          "rib_path":      str,
          "objectives_present": [str, ...],
          "objectives_missing": [str, ...],
          "interfaces_present": [str, ...],
          "exclusions_present": [str, ...],
        }

    The function reads the YAMLs directly (not the
    :func:`validate_structural_policy` output) so the report
    faithfully reflects the on-disk state. UNKNOWN/TBD values are
    preserved verbatim; this function never invents data.
    """
    from .release_blockers import _read_structural_yaml_state

    objectives, interfaces, exclusions = _read_structural_yaml_state(
        glasses_root
    )
    objectives_missing = [
        o for o in REQUIRED_OBJECTIVES_LIST if o not in objectives
    ]
    status = "PASS"
    if objectives_missing:
        status = "MISSING_OBJECTIVES"
    elif not interfaces:
        status = "INCOMPLETE"
    elif not exclusions:
        status = "INCOMPLETE"
    return {
        "status": status,
        "policy_path": str(STRUCTURAL_POLICY_REL),
        "rib_path": str(RIB_SYSTEM_REL),
        "objectives_present": objectives,
        "objectives_missing": objectives_missing,
        "interfaces_present": interfaces,
        "exclusions_present": exclusions,
    }


__all__ = [
    "PlExecutionError",
    "PLACEMENT_KEY_TO_POSE",
    "REQUIRED_OBJECTIVES_LIST",
    "STRUCTURAL_POLICY_REL",
    "RIB_SYSTEM_REL",
    "POSE_VALIDATION_REL",
    "PLACEMENT_POLICY_REL",
    "apply_placement_resolution",
    "build_placement_resolution_plan",
    "verify_structural_objectives",
]