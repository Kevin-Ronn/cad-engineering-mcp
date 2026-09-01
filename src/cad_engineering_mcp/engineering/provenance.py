"""Phase 6 formal provenance + authoritative-override layer.

Phase 4 introduced :func:`resolve_component_field` which returns a
flat ``{value, source, authoritative, sources_checked}`` dict.
The ``source`` field is a short string label (``registry``,
``per_component_yaml``, ...) but it does *not* carry the structured
metadata an engineering release reviewer needs:

  * What kind of source produced the value? (manufacturer datasheet,
    measured geometry, project policy, generated derivation, external
    user input.)
  * Where is the evidence stored? (relative YAML/JSON path under
    ``projects/glasses/``.)
  * Who recorded it and when?
  * What is the confidence (authoritative / provisional / recorded)?

Phase 6 adds the formal :class:`ProvenanceRecord` plus an
authoritative-override file that lets a release engineer resolve
genuine UNKNOWN blockers *with* provenance instead of guessing.

Engineering rules (mirrors of CLAUDE.md and the Phase 6 directive):

* Provenance never invents a value. The override file stores values
  taken from authoritative sources (datasheets, measurements,
  project policies). If a caller passes ``UNKNOWN`` / ``TBD`` /
  ``TBD_FROM_*`` as the override value, the record is rejected.
* Each override carries a SHA-256 fingerprint of the evidence (when
  the evidence is a file under the project) so the provenance can be
  re-verified after subsequent edits.
* The override file lives at
  ``projects/glasses/components/component-authority-overrides.yaml``.
  It is read by :func:`resolve_component_field` so any recorded
  override automatically upgrades the field to authoritative.
* Overrides for fields the resolver already returns authoritatively
  are rejected (we never overwrite a known authoritative value with
  a different authoritative value without an explicit ``force=True``).

The :func:`build_resolution_plan` function consumes the release-blocker
manifest from Phase 5 and partitions every blocker into one of four
*resolution strategies*:

    OVERRIDE           -- resolvable now by recording an
                          authoritative value with provenance.
                          Example: ``battery.voltage_range_max``.
    POLICY_YAML        -- resolvable by editing a project policy YAML
                          (declarative, non-engineering data).
                          Example: structural-policy.yaml objectives.
    GEOMETRY_DERIVED   -- resolvable only by running the geometry
                          solver pipeline (Phase 2/3 concern).
                          Example: rib_zones, optical clearances.
    EXTERNAL_DATASHEET -- requires an external authoritative source
                          that the repository does not yet have.
                          Example: CamThink OV5640 FPC connector pin
                          pitch (lives in the CamThink datasheet).

The function never invents a strategy; it picks one per blocker
based on the source_tool and field path. UNKNOWN/TBD blockers that
cannot be resolved via OVERRIDE / POLICY_YAML / GEOMETRY_DERIVED
are correctly classified as EXTERNAL_DATASHEET and the release is
not silently upgraded to PASS.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class ProvenanceError(RuntimeError):
    """Raised by the Phase 6 provenance module on invalid input."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERRIDE_REL = Path("components/component-authority-overrides.yaml")

VALID_PROVENANCE_KINDS: frozenset[str] = frozenset(
    {
        "manufacturer_datasheet",
        "measured_geometry",
        "project_policy",
        "generated_derivation",
        "external_user_input",
    }
)

# Source-tool -> resolution strategy mapping for blockers. The mapping
# is conservative: any blocker whose strategy cannot be decided from
# the (source_tool, category) tuple defaults to EXTERNAL_DATASHEET.
_STRATEGY_BY_SOURCE: dict[str, str] = {
    "component_authority": "OVERRIDE",
    "validate_structural_policy": "POLICY_YAML",
    "validate_optical_window_system": "OVERRIDE",
    "validate_dfm_dfa": "POLICY_YAML",
    "reconcile_pcb": "EXTERNAL_DATASHEET",
    "validate_poses": "GEOMETRY_DERIVED",
    "verify_reference_integrity": "EXTERNAL_DATASHEET",
}


_TBD_LIKE = re.compile(r"^(TBD(_FROM_[A-Z0-9_]+)?|UNKNOWN)$", re.IGNORECASE)


def _is_tbd_like(value: Any) -> bool:
    """True iff ``value`` is the literal ``TBD``/``TBD_FROM_*``/``UNKNOWN``."""
    if not isinstance(value, str):
        return False
    return bool(_TBD_LIKE.match(value.strip()))


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


# ---------------------------------------------------------------------------
# ProvenanceRecord
# ---------------------------------------------------------------------------


class ProvenanceRecord:
    """Structured provenance metadata for an authoritative override.

    Attributes are immutable after construction. The record is what the
    MCP tools and the audit log see; the YAML form is a dict with
    matching keys.
    """

    __slots__ = (
        "component_id",
        "field",
        "value",
        "kind",
        "evidence_path",
        "evidence_sha256",
        "confidence",
        "recorded_at",
        "recorded_by",
        "notes",
    )

    def __init__(
        self,
        *,
        component_id: str,
        field: str,
        value: Any,
        kind: str,
        evidence_path: str | None = None,
        evidence_sha256: str | None = None,
        confidence: str = "authoritative",
        recorded_at: str | None = None,
        recorded_by: str = "engineering_agent",
        notes: str | None = None,
    ) -> None:
        if not isinstance(component_id, str) or not component_id:
            raise ProvenanceError("component_id must be a non-empty string")
        if not isinstance(field, str) or not field:
            raise ProvenanceError("field must be a non-empty string")
        if kind not in VALID_PROVENANCE_KINDS:
            raise ProvenanceError(
                f"kind must be one of {sorted(VALID_PROVENANCE_KINDS)}; "
                f"got {kind!r}"
            )
        if confidence not in {"authoritative", "provisional", "recorded"}:
            raise ProvenanceError(
                "confidence must be authoritative, provisional, or recorded"
            )
        if _is_tbd_like(value):
            raise ProvenanceError(
                "Refusing to record provenance for an UNKNOWN/TBD value; "
                "the override must carry an authoritative value."
            )
        if kind == "manufacturer_datasheet" and not (
            evidence_path or notes
        ):
            raise ProvenanceError(
                "manufacturer_datasheet records must declare evidence_path "
                "or notes (datasheet URL / part number / revision)."
            )

        self.component_id = component_id
        self.field = field
        self.value = value
        self.kind = kind
        self.evidence_path = evidence_path
        self.evidence_sha256 = evidence_sha256
        self.confidence = confidence
        self.recorded_at = recorded_at or _now_utc()
        self.recorded_by = recorded_by
        self.notes = notes

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "component_id": self.component_id,
            "field": self.field,
            "value": self.value,
            "kind": self.kind,
            "confidence": self.confidence,
            "recorded_at": self.recorded_at,
            "recorded_by": self.recorded_by,
        }
        if self.evidence_path is not None:
            out["evidence_path"] = self.evidence_path
        if self.evidence_sha256 is not None:
            out["evidence_sha256"] = self.evidence_sha256
        if self.notes is not None:
            out["notes"] = self.notes
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProvenanceRecord":
        if not isinstance(data, dict):
            raise ProvenanceError("Provenance record must be a mapping")
        try:
            return cls(
                component_id=str(data["component_id"]),
                field=str(data["field"]),
                value=data["value"],
                kind=str(data["kind"]),
                evidence_path=(
                    str(data["evidence_path"])
                    if "evidence_path" in data
                    else None
                ),
                evidence_sha256=(
                    str(data["evidence_sha256"])
                    if "evidence_sha256" in data
                    else None
                ),
                confidence=str(data.get("confidence", "authoritative")),
                recorded_at=(
                    str(data["recorded_at"])
                    if "recorded_at" in data
                    else None
                ),
                recorded_by=str(data.get("recorded_by", "engineering_agent")),
                notes=(
                    str(data["notes"]) if "notes" in data else None
                ),
            )
        except KeyError as exc:
            raise ProvenanceError(
                f"Missing key in provenance record: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Override file persistence
# ---------------------------------------------------------------------------


def load_overrides(*, glasses_root: Path) -> dict[str, Any]:
    """Read ``components/component-authority-overrides.yaml``.

    Returns the parsed YAML mapping with the keys
    ``schema_version``, `` ``records``. An empty / missing file yields
    ``{schema_version: 1, records: []}``.
    """
    path = glasses_root / OVERRIDE_REL
    if not path.exists():
        return {"schema_version": 1, "records": []}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"schema_version": 1, "records": []}
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return {"schema_version": 1, "records": []}
    if not isinstance(doc, dict):
        return {"schema_version": 1, "records": []}
    doc.setdefault("records", [])
    if not isinstance(doc["records"], list):
        doc["records"] = []
    return doc


def save_overrides(
    *, doc: dict[str, Any], glasses_root: Path, perform_write_fn
) -> dict[str, Any]:
    """Persist ``doc`` to the override file using the controlled-write helper.

    ``perform_write_fn`` is the Phase 3
    :func:`cad_engineering_mcp.tools._mutation.perform_write` callable.
    It is injected so this module does not depend on the tool layer.
    """
    records = doc.get("records", [])
    if not isinstance(records, list):
        raise ProvenanceError("records must be a list")
    payload = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    return perform_write_fn(
        destination=str(OVERRIDE_REL),
        content=payload,
        tool="authoritative_value_override",
        operation="add",
        metadata={
            "records_count": len(records),
            "schema_version": doc.get("schema_version", 1),
        },
    )


def find_override(
    *,
    component_id: str,
    field: str,
    glasses_root: Path,
) -> ProvenanceRecord | None:
    """Return the override record for ``(component_id, field)`` if any."""
    doc = load_overrides(glasses_root=glasses_root)
    for entry in doc.get("records", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("component_id") == component_id and entry.get(
            "field"
        ) == field:
            try:
                return ProvenanceRecord.from_dict(entry)
            except ProvenanceError:
                continue
    return None


def add_override(
    *,
    record: ProvenanceRecord,
    glasses_root: Path,
    force: bool = False,
    perform_write_fn,
) -> dict[str, Any]:
    """Append ``record`` to the override file.

    Refuses to overwrite an existing record for the same
    ``(component_id, field)`` unless ``force=True``. Refuses to
    override a value the resolver already considers authoritative
    (we never silently downgrade an authoritative resolution).
    """
    doc = load_overrides(glasses_root=glasses_root)
    records = doc.get("records", [])
    for existing in records:
        if not isinstance(existing, dict):
            continue
        if (
            existing.get("component_id") == record.component_id
            and existing.get("field") == record.field
        ):
            if not force:
                raise ProvenanceError(
                    f"Override already present for "
                    f"({record.component_id!r}, {record.field!r}); "
                    "pass force=True to overwrite."
                )
            records.remove(existing)
            break
    # Cross-check the resolver.
    from .component_authority import resolve_component_field

    resolution = resolve_component_field(
        component_id=record.component_id,
        field=record.field,
        glasses_root=glasses_root,
    )
    if resolution.get("authoritative") and not force:
        raise ProvenanceError(
            f"Field {record.field!r} for component "
            f"{record.component_id!r} already resolves authoritatively "
            f"(source={resolution.get('source')!r}); pass force=True to "
            "overwrite with a new authoritative value."
        )
    records.append(record.to_dict())
    doc["records"] = records
    return save_overrides(
        doc=doc,
        glasses_root=glasses_root,
        perform_write_fn=perform_write_fn,
    )


def list_overrides(*, glasses_root: Path) -> list[ProvenanceRecord]:
    """Return every override as a list of :class:`ProvenanceRecord`."""
    doc = load_overrides(glasses_root=glasses_root)
    out: list[ProvenanceRecord] = []
    for entry in doc.get("records", []) or []:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(ProvenanceRecord.from_dict(entry))
        except ProvenanceError:
            continue
    return out


# ---------------------------------------------------------------------------
# Resolver extension
# ---------------------------------------------------------------------------


def resolve_with_provenance(
    *, component_id: str, field: str, glasses_root: Path
) -> dict[str, Any]:
    """Resolve ``field`` for ``component_id`` and surface a full provenance.

    Returns the standard :func:`resolve_component_field` envelope with
    two extra fields:

        * ``provenance``: a :class:`ProvenanceRecord`-shaped dict when
          the value is authoritative and came from an explicit
          override; otherwise ``None``.
        * ``effective_source``: ``"override"`` when an override took
          precedence, otherwise the resolver ``source`` string.

    Resolution order:

        1. explicit override (when present and authoritative)
        2. canonical resolver order (registry → per_component_yaml →
           analysis_json → policy_yaml → measured_reference_geometry)
    """
    from .component_authority import resolve_component_field

    override = find_override(
        component_id=component_id, field=field, glasses_root=glasses_root
    )
    if override is not None:
        return {
            "component_id": component_id,
            "field": field,
            "value": override.value,
            "source": "override",
            "authoritative": True,
            "sources_checked": ["override"],
            "effective_source": "override",
            "provenance": override.to_dict(),
        }
    resolution = resolve_component_field(
        component_id=component_id,
        field=field,
        glasses_root=glasses_root,
    )
    resolution["provenance"] = None
    resolution["effective_source"] = resolution.get("source", "UNKNOWN")
    return resolution


# ---------------------------------------------------------------------------
# Resolution plan
# ---------------------------------------------------------------------------


def _strategy_for_blocker(blocker: dict[str, Any]) -> str:
    """Pick the resolution strategy for a single blocker."""
    source_tool = str(blocker.get("source_tool", ""))
    category = str(blocker.get("category", ""))
    field = str(blocker.get("field", ""))
    component_id = blocker.get("component_id")

    # Structural blockers with POLICY_GAP category -> policy_yaml edit.
    if source_tool == "validate_structural_policy":
        if "rib_zones" in field:
            return "GEOMETRY_DERIVED"
        if "missing_objective" in field or "objectives" in field:
            return "POLICY_YAML"
        if "load_interfaces" in field or "interfaces" in field:
            return "POLICY_YAML"
        if "exclusions" in field:
            return "POLICY_YAML"
        return "POLICY_YAML"

    # Optical-window TBD fields -> data override.
    if source_tool == "validate_optical_window_system":
        return "OVERRIDE"

    # DFM/DFA findings split: TBD values are override-eligible, structural
    # findings are policy_yaml / geometry_derived.
    if source_tool == "validate_dfm_dfa":
        if category == "TBD_FIELD":
            # Many DFM TBD fields live in the schematic-architecture or
            # mechanical interfaces; some are data, some are policy.
            if component_id is not None:
                return "OVERRIDE"
            if field.startswith("placement_policy.") or field.startswith(
                "constraints."
            ):
                return "POLICY_YAML"
            if "wire_route_tbd" in field:
                return "POLICY_YAML"
            return "POLICY_YAML"
        if category == "BLOCKER":
            if field.startswith("dfm.") or field.startswith("dfa."):
                return "POLICY_YAML"
            return "POLICY_YAML"
        return "POLICY_YAML"

    # PCB reconcile findings: footprint / connector / stackup -> external
    # datasheet (those fields live in vendor datasheets, not in the
    # project).
    if source_tool == "reconcile_pcb":
        return "EXTERNAL_DATASHEET"

    # Component-authority coverage: every UNKNOWN/TBD value is a
    # data override (the resolver already returns authoritative when
    # the value is concrete, so anything missing here is a real gap).
    if source_tool == "component_authority":
        return "OVERRIDE"

    # Pose validation: geometry_derived only.
    if source_tool == "validate_poses":
        return "GEOMETRY_DERIVED"

    # Reference-integrity failures: external (the reference hashes are
    # fixed; either the file was mutated or the manifest hash needs to
    # be re-derived from a verified source).
    if source_tool == "verify_reference_integrity":
        return "EXTERNAL_DATASHEET"

    # Fallback. We never silently invent a strategy; the conservative
    # default is EXTERNAL_DATASHEET because any blocker we cannot
    # classify needs an authoritative source we don't yet have.
    return _STRATEGY_BY_SOURCE.get(source_tool, "EXTERNAL_DATASHEET")


VALID_RESOLUTION_STRATEGIES: frozenset[str] = frozenset(
    {"OVERRIDE", "POLICY_YAML", "GEOMETRY_DERIVED", "EXTERNAL_DATASHEET"}
)


def build_resolution_plan(
    *, blocker_manifest: dict[str, Any]
) -> dict[str, Any]:
    """Build the engineering-data resolution plan from the blocker manifest.

    Args:
        blocker_manifest: the structured dict returned by
            :func:`cad_engineering_mcp.engineering.release_blockers.build_release_blocker_manifest`.

    Returns:
        A structured plan:

            {
              "status":             "RELEASE_READY" | "INCOMPLETE" |
                                      "RELEASE_BLOCKED",
              "generated_at":       ISO timestamp,
              "blocker_count":      int,
              "by_strategy": {
                "OVERRIDE":          int,
                "POLICY_YAML":       int,
                "GEOMETRY_DERIVED":  int,
                "EXTERNAL_DATASHEET":int,
              },
              "resolvable_without_external": bool,
              "strategies": [
                {
                  "blocker_id",
                  "source_tool",
                  "field",
                  "component_id",
                  "strategy":       "OVERRIDE" | ...,
                  "rationale":      str,
                  "next_action":    str,
                },
                ...
              ],
              "summary": {
                "override_blockers":           int,
                "policy_yaml_blockers":        int,
                "geometry_derived_blockers":   int,
                "external_datasheet_blockers": int,
              }
            }

    The plan never invents a strategy. ``OVERRIDE`` means the field
    can be resolved by recording an authoritative value with
    provenance; ``POLICY_YAML`` means the field lives in a project
    policy YAML and is declarative; ``GEOMETRY_DERIVED`` means it must
    be solved by the geometry pipeline; ``EXTERNAL_DATASHEET`` means
    the authoritative source lives outside the project and must be
    supplied by a human.
    """
    blockers = (
        blocker_manifest.get("blockers", [])
        if isinstance(blocker_manifest, dict)
        else []
    )

    strategies: list[dict[str, Any]] = []
    by_strategy: dict[str, int] = {
        "OVERRIDE": 0,
        "POLICY_YAML": 0,
        "GEOMETRY_DERIVED": 0,
        "EXTERNAL_DATASHEET": 0,
    }

    for blocker in blockers:
        if not isinstance(blocker, dict):
            continue
        strategy = _strategy_for_blocker(blocker)
        rationale, next_action = _strategy_rationale(strategy, blocker)
        strategies.append(
            {
                "blocker_id": blocker.get("blocker_id"),
                "source_tool": blocker.get("source_tool"),
                "field": blocker.get("field"),
                "component_id": blocker.get("component_id"),
                "category": blocker.get("category"),
                "severity": blocker.get("severity"),
                "strategy": strategy,
                "rationale": rationale,
                "next_action": next_action,
            }
        )
        by_strategy[strategy] = by_strategy.get(strategy, 0) + 1

    # Deterministic ordering: by strategy, then blocker_id.
    strategies.sort(
        key=lambda s: (
            str(s.get("strategy", "")),
            str(s.get("blocker_id", "")),
        )
    )

    # Status: the resolution plan itself is honest about what can be
    # resolved. A project is ``RESOLVABLE_NOW`` only when every blocker
    # is OVERRIDE or POLICY_YAML; otherwise ``REQUIRES_GEOMETRY`` (when
    # at least one GEOMETRY_DERIVED blocker is present) or
    # ``REQUIRES_EXTERNAL_DATA`` (when at least one
    # EXTERNAL_DATASHEET blocker is present).
    if not strategies:
        status = "RESOLVABLE_NOW"
    elif (
        by_strategy["GEOMETRY_DERIVED"] == 0
        and by_strategy["EXTERNAL_DATASHEET"] == 0
    ):
        status = "RESOLVABLE_NOW"
    elif by_strategy["GEOMETRY_DERIVED"] > 0:
        status = "REQUIRES_GEOMETRY"
    else:
        status = "REQUIRES_EXTERNAL_DATA"

    return {
        "status": status,
        "generated_at": _now_utc(),
        "blocker_count": len(strategies),
        "by_strategy": dict(sorted(by_strategy.items())),
        "resolvable_without_external": (
            by_strategy["GEOMETRY_DERIVED"] == 0
            and by_strategy["EXTERNAL_DATASHEET"] == 0
        ),
        "strategies": strategies,
        "summary": {
            "override_blockers": by_strategy["OVERRIDE"],
            "policy_yaml_blockers": by_strategy["POLICY_YAML"],
            "geometry_derived_blockers": by_strategy["GEOMETRY_DERIVED"],
            "external_datasheet_blockers": by_strategy["EXTERNAL_DATASHEET"],
        },
    }


def _strategy_rationale(
    strategy: str, blocker: dict[str, Any]
) -> tuple[str, str]:
    """Human-readable (rationale, next_action) for a blocker strategy."""
    component_id = blocker.get("component_id")
    field = blocker.get("field")
    if strategy == "OVERRIDE":
        return (
            "Field value can be recorded with explicit provenance via the "
            "authoritative_value_override MCP tool.",
            (
                f"Call authoritative_value_override(component_id="
                f"{component_id!r}, field={field!r}, value=<from "
                "datasheet>, kind='manufacturer_datasheet', "
                "evidence_path=<datasheet path>)."
            ),
        )
    if strategy == "POLICY_YAML":
        return (
            "Field lives in a project policy YAML and is declarative; "
            "edit the YAML to supply the authoritative field.",
            (
                f"Edit the project YAML that carries {field!r}; do not "
                "guess values."
            ),
        )
    if strategy == "GEOMETRY_DERIVED":
        return (
            "Field requires a geometry-derived value; it cannot be "
            "resolved without running the geometry solver pipeline.",
            (
                "Run the canonical pose pipeline (run_pose_pipeline) "
                "and the geometry analysis scripts; the value will "
                "appear in analysis/geometry/component-pose-validation.json."
            ),
        )
    # EXTERNAL_DATASHEET.
    return (
        "Authoritative source lives outside the repository; the field "
        "cannot be resolved from the project alone.",
        (
            "Obtain the authoritative value from the vendor datasheet "
            f"for component {component_id!r} and record it via "
            "authoritative_value_override with "
            "kind='manufacturer_datasheet'."
        ),
    )


__all__ = [
    "ProvenanceError",
    "ProvenanceRecord",
    "VALID_PROVENANCE_KINDS",
    "VALID_RESOLUTION_STRATEGIES",
    "OVERRIDE_REL",
    "add_override",
    "build_resolution_plan",
    "find_override",
    "list_overrides",
    "load_overrides",
    "resolve_with_provenance",
    "save_overrides",
]