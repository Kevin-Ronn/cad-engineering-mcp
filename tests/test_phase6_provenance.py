"""Tests for the Phase 6 provenance + resolution-plan layer.

Covers:

* ``ProvenanceRecord`` validation rules (kind, confidence, TBD refusal).
* Override file load / save / dedupe.
* ``resolve_with_provenance`` consults overrides first.
* ``authoritative_value_override`` dry-run + mutation gating.
* ``authoritative_value_override`` refuses UNKNOWN/TBD, invalid kind,
  unrecognised field, and silently-overwriting-an-authoritative.
* ``resolution_plan`` strategy partition (OVERRIDE / POLICY_YAML /
  GEOMETRY_DERIVED / EXTERNAL_DATASHEET).
* ``list_authoritative_overrides`` envelope shape.
* Engineering invariants: never invent values, never silently
  downgrade authority.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_engineering_mcp.engineering.provenance import (
    OVERRIDE_REL,
    VALID_PROVENANCE_KINDS,
    VALID_RESOLUTION_STRATEGIES,
    ProvenanceError,
    ProvenanceRecord,
    build_resolution_plan,
    find_override,
    list_overrides,
    load_overrides,
    resolve_with_provenance,
)
from cad_engineering_mcp.tools._paths import glasses_root


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_provenance_kind_constants():
    assert VALID_PROVENANCE_KINDS == {
        "manufacturer_datasheet",
        "measured_geometry",
        "project_policy",
        "generated_derivation",
        "external_user_input",
    }


def test_resolution_strategy_constants():
    assert VALID_RESOLUTION_STRATEGIES == {
        "OVERRIDE",
        "POLICY_YAML",
        "GEOMETRY_DERIVED",
        "EXTERNAL_DATASHEET",
    }


def test_override_rel_path():
    assert OVERRIDE_REL == Path(
        "components/component-authority-overrides.yaml"
    )


# ---------------------------------------------------------------------------
# ProvenanceRecord validation
# ---------------------------------------------------------------------------


def _good_record_kwargs() -> dict:
    return dict(
        component_id="camthink_ov5640_8p5",
        field="envelope_mm.x",
        value=8.5,
        kind="manufacturer_datasheet",
        evidence_path="docs/camthink-datasheet.pdf",
        evidence_sha256="deadbeef" * 8,
        confidence="authoritative",
        recorded_by="test",
        notes="Phase 6 test",
    )


def test_provenance_record_round_trip():
    kwargs = _good_record_kwargs()
    record = ProvenanceRecord(**kwargs)
    as_dict = record.to_dict()
    rebuilt = ProvenanceRecord.from_dict(as_dict)
    assert rebuilt.component_id == record.component_id
    assert rebuilt.field == record.field
    assert rebuilt.value == record.value
    assert rebuilt.kind == record.kind
    assert rebuilt.evidence_path == record.evidence_path
    assert rebuilt.evidence_sha256 == record.evidence_sha256
    assert rebuilt.confidence == record.confidence
    assert rebuilt.recorded_by == record.recorded_by
    assert rebuilt.notes == record.notes


def test_provenance_record_rejects_unknown_value():
    with pytest.raises(ProvenanceError) as exc:
        ProvenanceRecord(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value="UNKNOWN",
            kind="manufacturer_datasheet",
            evidence_path="docs/x",
        )
    assert "UNKNOWN" in str(exc.value) or "TBD" in str(exc.value).upper()


def test_provenance_record_rejects_tbd_value():
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value="TBD",
            kind="manufacturer_datasheet",
            evidence_path="docs/x",
        )
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value="TBD_FROM_BATTERY_DATASHEET",
            kind="manufacturer_datasheet",
            evidence_path="docs/x",
        )


def test_provenance_record_rejects_invalid_kind():
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="not_a_kind",
            evidence_path="docs/x",
        )


def test_provenance_record_rejects_invalid_confidence():
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/x",
            confidence="very_likely",
        )


def test_provenance_record_datasheet_requires_evidence():
    """manufacturer_datasheet records must declare evidence_path or notes."""
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
        )


def test_provenance_record_rejects_empty_field():
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            component_id="battery_cell",
            field="",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/x",
        )


# ---------------------------------------------------------------------------
# Override file load / save
# ---------------------------------------------------------------------------


def test_load_overrides_returns_empty_when_missing(tmp_path):
    """load_overrides returns an empty structure when the file is absent."""
    # Use a glasses_root that does not have the file.
    class _Root:
        def __truediv__(self, other):
            return tmp_path / str(other)

    doc = load_overrides(glasses_root=tmp_path)  # type: ignore[arg-type]
    assert doc == {"schema_version": 1, "records": []}


def test_find_override_returns_none_when_absent():
    assert (
        find_override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            glasses_root=glasses_root(),
        )
        is None
    )


# ---------------------------------------------------------------------------
# resolve_with_provenance
# ---------------------------------------------------------------------------


def test_resolve_with_provenance_falls_through_when_no_override():
    """Without an override, resolve_with_provenance matches the canonical
    resolver behaviour (may return UNKNOWN)."""
    resolution = resolve_with_provenance(
        component_id="battery_cell",
        field="battery.capacity_mah",
        glasses_root=glasses_root(),
    )
    # Battery capacity is UNKNOWN in the project; resolver falls through.
    assert resolution["provenance"] is None
    assert resolution["effective_source"] in {"UNKNOWN", resolution["source"]}
    # The shape of the canonical resolution is preserved.
    assert "value" in resolution
    assert "source" in resolution
    assert "authoritative" in resolution
    assert "sources_checked" in resolution


# ---------------------------------------------------------------------------
# MCP tool: list_authoritative_overrides
# ---------------------------------------------------------------------------


def test_list_authoritative_overrides_envelope_empty():
    from cad_engineering_mcp.tools.provenance_tools import (
        list_authoritative_overrides as tool,
    )

    env = tool()
    assert env["status"] == "PASS"
    assert env["tool"] == "list_authoritative_overrides"
    data = env["data"]
    assert data["path"] == str(OVERRIDE_REL)
    assert data["schema_version"] == 1
    assert data["count"] == len(data["records"])
    assert isinstance(data["records"], list)


# ---------------------------------------------------------------------------
# MCP tool: authoritative_value_override (validation)
# ---------------------------------------------------------------------------


def _override(**kwargs):
    from cad_engineering_mcp.tools.provenance_tools import (
        authoritative_value_override as tool,
    )

    return tool(**kwargs)


def test_authoritative_value_override_dry_run_does_not_write():
    target = glasses_root() / OVERRIDE_REL
    backup = Path("/tmp/_override_backup_dry.yaml")
    if target.exists():
        backup.write_text(target.read_text(encoding="utf-8"))
    try:
        env = _override(
            component_id="camthink_ov5640_8p5",
            field="envelope_mm.x",
            value=8.5,
            kind="measured_geometry",
            evidence_path="projects/glasses/analysis/geometry/camera-aperture-analysis.json",
            allow_mutation=False,
        )
        assert env["status"] == "PASS"
        assert env["data"]["executed"] is False
        assert "allow_mutation=False" in env["warnings"][0]
        # The override file must not exist (or must not have been touched).
        if target.exists():
            content = target.read_text(encoding="utf-8")
            assert "camthink_ov5640_8p5" not in content or content == backup.read_text(
                encoding="utf-8"
            )
    finally:
        if backup.exists():
            backup.unlink()


def test_authoritative_value_override_rejects_unknown():
    env = _override(
        component_id="battery_cell",
        field="battery.capacity_mah",
        value="UNKNOWN",
        kind="manufacturer_datasheet",
        evidence_path="docs/x",
        allow_mutation=False,
    )
    assert env["status"] == "ERROR"
    assert "UNKNOWN" in env["errors"][0] or "TBD" in env["errors"][0].upper()


def test_authoritative_value_override_rejects_tbd():
    env = _override(
        component_id="battery_cell",
        field="battery.capacity_mah",
        value="TBD_FROM_DATASHEET",
        kind="manufacturer_datasheet",
        evidence_path="docs/x",
        allow_mutation=False,
    )
    assert env["status"] == "ERROR"


def test_authoritative_value_override_rejects_invalid_kind():
    env = _override(
        component_id="battery_cell",
        field="battery.capacity_mah",
        value=350,
        kind="invented",
        evidence_path="docs/x",
        allow_mutation=False,
    )
    assert env["status"] == "ERROR"
    assert "kind" in env["errors"][0].lower()


def test_authoritative_value_override_rejects_unrecognised_field():
    env = _override(
        component_id="battery_cell",
        field="definitely.not.a.field",
        value=42,
        kind="manufacturer_datasheet",
        evidence_path="docs/x",
        allow_mutation=False,
    )
    assert env["status"] == "ERROR"
    assert "unrecognised" in env["errors"][0].lower()


# ---------------------------------------------------------------------------
# MCP tool: authoritative_value_override (mutation)
# ---------------------------------------------------------------------------


def _cleanup_override_file():
    """Delete the override file if it exists."""
    target = glasses_root() / OVERRIDE_REL
    if target.exists():
        target.unlink()
    # Also remove the back-up directory tree that perform_write creates.
    releases = glasses_root() / "manufacturing" / "releases"
    if releases.exists():
        # Remove only the back-up snapshot directories.
        for child in releases.iterdir():
            if child.is_dir() and child.name != "audit":
                # Keep the audit/ sub-directory; remove the timestamp dir.
                import shutil as _shutil

                _shutil.rmtree(child)


def test_authoritative_value_override_mutation_writes_and_audits():
    target = glasses_root() / OVERRIDE_REL
    _cleanup_override_file()
    try:
        env = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
        )
        assert env["status"] == "PASS"
        assert env["data"]["executed"] is True
        assert target.exists()
        # Re-read and verify the record is parseable.
        record = find_override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            glasses_root=glasses_root(),
        )
        assert record is not None
        assert record.value == 350
        assert record.kind == "manufacturer_datasheet"
    finally:
        _cleanup_override_file()


def test_authoritative_value_override_duplicate_rejected_without_force():
    target = glasses_root() / OVERRIDE_REL
    _cleanup_override_file()
    try:
        env1 = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
        )
        assert env1["status"] == "PASS"
        env2 = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=400,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
        )
        assert env2["status"] == "ERROR"
        assert "already" in env2["errors"][0].lower()
    finally:
        _cleanup_override_file()


def test_authoritative_value_override_duplicate_force_overwrites():
    target = glasses_root() / OVERRIDE_REL
    _cleanup_override_file()
    try:
        env1 = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
        )
        assert env1["status"] == "PASS"
        env2 = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=400,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
            force=True,
        )
        assert env2["status"] == "PASS"
        record = find_override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            glasses_root=glasses_root(),
        )
        assert record is not None
        assert record.value == 400
    finally:
        _cleanup_override_file()


def test_resolve_with_provenance_returns_override_when_present():
    """When an override is recorded, resolve_with_provenance surfaces it
    with provenance metadata and effective_source='override'."""
    target = glasses_root() / OVERRIDE_REL
    _cleanup_override_file()
    try:
        env = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
        )
        assert env["status"] == "PASS"

        resolution = resolve_with_provenance(
            component_id="battery_cell",
            field="battery.capacity_mah",
            glasses_root=glasses_root(),
        )
        assert resolution["authoritative"] is True
        assert resolution["effective_source"] == "override"
        assert resolution["source"] == "override"
        assert resolution["value"] == 350
        assert resolution["provenance"] is not None
        assert resolution["provenance"]["kind"] == "manufacturer_datasheet"
        assert (
            resolution["provenance"]["evidence_path"]
            == "docs/battery-datasheet.pdf"
        )
    finally:
        _cleanup_override_file()


# ---------------------------------------------------------------------------
# MCP tool: resolution_plan
# ---------------------------------------------------------------------------


def test_resolution_plan_envelope_shape():
    from cad_engineering_mcp.tools.provenance_tools import (
        resolution_plan as tool,
    )

    env = tool()
    assert env["status"] == "PASS"
    assert env["tool"] == "resolution_plan"
    data = env["data"]
    assert "status" in data
    assert "generated_at" in data
    assert "blocker_count" in data
    assert "by_strategy" in data
    assert "summary" in data
    assert "strategies" in data
    assert "resolvable_without_external" in data


def test_resolution_plan_current_state_requires_geometry_or_external():
    """The current release is honest: rib_zones or external keepout
    data means the plan is not RESOLVABLE_NOW."""
    from cad_engineering_mcp.tools.provenance_tools import (
        resolution_plan as tool,
    )

    env = tool()
    status = env["data"]["status"]
    assert status in {
        "RESOLVABLE_NOW",
        "REQUIRES_GEOMETRY",
        "REQUIRES_EXTERNAL_DATA",
    }
    # The current blocker list always contains at least one
    # GEOMETRY_DERIVED or EXTERNAL_DATASHEET entry.
    by_strategy = env["data"]["by_strategy"]
    assert (
        by_strategy["GEOMETRY_DERIVED"] > 0
        or by_strategy["EXTERNAL_DATASHEET"] > 0
    )
    assert env["data"]["resolvable_without_external"] is False


def test_resolution_plan_strategies_partition_blockers():
    """Every blocker in the manifest appears exactly once in the plan
    with a valid strategy."""
    from cad_engineering_mcp.tools.provenance_tools import (
        resolution_plan as tool,
    )
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest,
    )

    manifest = release_blocker_manifest()["data"]
    plan = tool()["data"]
    assert plan["blocker_count"] == len(manifest["blockers"])
    seen_blocker_ids = set()
    for entry in plan["strategies"]:
        assert entry["blocker_id"] in {
            b["blocker_id"] for b in manifest["blockers"]
        }
        assert entry["blocker_id"] not in seen_blocker_ids, (
            "Duplicate strategy entries: "
            f"{entry['blocker_id']}"
        )
        seen_blocker_ids.add(entry["blocker_id"])
        assert entry["strategy"] in VALID_RESOLUTION_STRATEGIES


def test_resolution_plan_deterministic():
    """Two runs of resolution_plan produce the same strategy list."""
    from cad_engineering_mcp.tools.provenance_tools import (
        resolution_plan as tool,
    )

    a = tool()["data"]
    b = tool()["data"]
    assert a["strategies"] == b["strategies"]
    assert a["by_strategy"] == b["by_strategy"]


def test_build_resolution_plan_with_synthetic_blockers():
    """Direct test of the strategy partitioner on synthetic blockers."""
    blocker_manifest = {
        "blockers": [
            {
                "blocker_id": "a" * 16,
                "source_tool": "component_authority",
                "category": "TBD_FIELD",
                "severity": "BLOCK",
                "field": "battery.capacity_mah",
                "component_id": "battery_cell",
                "value": "UNKNOWN",
            },
            {
                "blocker_id": "b" * 16,
                "source_tool": "validate_structural_policy",
                "category": "POLICY_GAP",
                "severity": "BLOCK",
                "field": "rib_system.rib_zones",
                "component_id": None,
                "value": 0,
            },
            {
                "blocker_id": "c" * 16,
                "source_tool": "reconcile_pcb",
                "category": "BLOCKER",
                "severity": "BLOCK",
                "field": "pcb.outline_w_mm",
                "component_id": "glasses_main_pcb",
                "value": "MISSING",
            },
            {
                "blocker_id": "d" * 16,
                "source_tool": "validate_dfm_dfa",
                "category": "TBD_FIELD",
                "severity": "WARNING",
                "field": "placement_policy.coordinates",
                "component_id": None,
                "value": "TBD",
            },
            {
                "blocker_id": "e" * 16,
                "source_tool": "validate_dfm_dfa",
                "category": "TBD_FIELD",
                "severity": "WARNING",
                "field": "schematic_architecture.capacity_mah",
                "component_id": None,
                "value": "TBD",
            },
        ]
    }
    plan = build_resolution_plan(blocker_manifest=blocker_manifest)
    by_id = {s["blocker_id"]: s for s in plan["strategies"]}
    assert by_id["a" * 16]["strategy"] == "OVERRIDE"
    assert by_id["b" * 16]["strategy"] == "GEOMETRY_DERIVED"
    assert by_id["c" * 16]["strategy"] == "EXTERNAL_DATASHEET"
    assert by_id["d" * 16]["strategy"] == "POLICY_YAML"
    assert by_id["e" * 16]["strategy"] == "POLICY_YAML"
    # Status is REQUIRES_GEOMETRY because GEOMETRY_DERIVED > 0.
    assert plan["status"] == "REQUIRES_GEOMETRY"
    assert plan["resolvable_without_external"] is False


def test_build_resolution_plan_empty_returns_resolvable_now():
    plan = build_resolution_plan(blocker_manifest={"blockers": []})
    assert plan["status"] == "RESOLVABLE_NOW"
    assert plan["blocker_count"] == 0
    assert plan["by_strategy"]["OVERRIDE"] == 0


def test_build_resolution_plan_only_override_or_policy_is_resolvable_now():
    """When every blocker is OVERRIDE or POLICY_YAML, the plan is
    RESOLVABLE_NOW."""
    blocker_manifest = {
        "blockers": [
            {
                "blocker_id": "f" * 16,
                "source_tool": "component_authority",
                "category": "TBD_FIELD",
                "severity": "BLOCK",
                "field": "battery.capacity_mah",
                "component_id": "battery_cell",
                "value": "UNKNOWN",
            },
            {
                "blocker_id": "1" * 16,
                "source_tool": "validate_dfm_dfa",
                "category": "TBD_FIELD",
                "severity": "WARNING",
                "field": "placement_policy.coordinates",
                "component_id": None,
                "value": "TBD",
            },
        ]
    }
    plan = build_resolution_plan(blocker_manifest=blocker_manifest)
    assert plan["status"] == "RESOLVABLE_NOW"
    assert plan["resolvable_without_external"] is True


# ---------------------------------------------------------------------------
# Audit / write safety
# ---------------------------------------------------------------------------


def test_authoritative_value_override_creates_audit_entry():
    """A successful mutation produces a JSONL audit entry."""
    target = glasses_root() / OVERRIDE_REL
    _cleanup_override_file()
    try:
        env = _override(
            component_id="battery_cell",
            field="battery.capacity_mah",
            value=350,
            kind="manufacturer_datasheet",
            evidence_path="docs/battery-datasheet.pdf",
            allow_mutation=True,
        )
        assert env["status"] == "PASS"

        # Read the audit log and confirm an entry exists.
        from cad_engineering_mcp.tools.release_blocker_tools import (
            audit_timeline,
        )

        timeline = audit_timeline(
            tool_filter="authoritative_value_override"
        )
        assert timeline["status"] == "PASS"
        assert any(
            e.get("operation") == "add"
            and e.get("success") is True
            for e in timeline["data"]["events"]
        )
    finally:
        _cleanup_override_file()


def test_authoritative_value_override_dry_run_audit_entry():
    """A dry-run also produces an audit entry (operation=
    no_mutation_dry_run)."""
    target = glasses_root() / OVERRIDE_REL
    _cleanup_override_file()
    try:
        env = _override(
            component_id="camthink_ov5640_8p5",
            field="envelope_mm.x",
            value=8.5,
            kind="measured_geometry",
            evidence_path="projects/glasses/analysis/geometry/camera-aperture-analysis.json",
            allow_mutation=False,
        )
        assert env["status"] == "PASS"

        from cad_engineering_mcp.tools.release_blocker_tools import (
            audit_timeline,
        )

        timeline = audit_timeline(
            tool_filter="authoritative_value_override"
        )
        assert any(
            e.get("operation") == "no_mutation_dry_run"
            for e in timeline["data"]["events"]
        )
    finally:
        _cleanup_override_file()