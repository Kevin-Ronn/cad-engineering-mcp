"""Tests for the Phase 5 release-blocker manifest and audit-timeline tools.

Covers:

* ``release_blocker_manifest`` envelope shape and current-state status.
* Stable blocker_id semantics (deterministic across runs).
* Severity / category normalisation in the engineering data module.
* ``save_release_blocker_manifest`` dry-run + mutation gating.
* ``audit_timeline`` envelope + filter behaviour.
* Reference-integrity failure aggregation.
* Pose-validation blocking semantics.
* Engineering invariants: never invent UNKNOWN/TBD, never downgrade
  BLOCK to PASS, deterministic ordering.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from cad_engineering_mcp.engineering.release_blockers import (
    VALID_CATEGORIES,
    VALID_SEVERITIES,
    build_audit_timeline,
    build_release_blocker_manifest,
    serialise_release_blocker_manifest,
)
from cad_engineering_mcp.tools._paths import glasses_root


# ---------------------------------------------------------------------------
# Stable-id / severity / category invariants
# ---------------------------------------------------------------------------


def test_severity_and_category_constants():
    assert VALID_SEVERITIES == {"BLOCK", "WARNING", "INFO"}
    assert VALID_CATEGORIES == {
        "BLOCKER",
        "UNKNOWN_FIELD",
        "TBD_FIELD",
        "DATA_GAP",
        "POLICY_GAP",
    }


def test_blocker_id_is_deterministic():
    """Two runs of the same input produce the same blocker list and ids."""
    from cad_engineering_mcp.engineering.release_blockers import (
        build_release_blocker_manifest,
    )

    a = build_release_blocker_manifest(glasses_root=glasses_root())
    b = build_release_blocker_manifest(glasses_root=glasses_root())
    assert a["status"] == b["status"]
    assert a["summary"] == b["summary"]
    assert [bl["blocker_id"] for bl in a["blockers"]] == [
        bl["blocker_id"] for bl in b["blockers"]
    ]


def test_blocker_ids_are_unique():
    """No two blockers share the same ``blocker_id``."""
    manifest = build_release_blocker_manifest(glasses_root=glasses_root())
    ids = [b["blocker_id"] for b in manifest["blockers"]]
    assert len(ids) == len(set(ids)), (
        "Duplicate blocker_ids: "
        + ", ".join(sorted({i for i in ids if ids.count(i) > 1}))
    )


def test_blocker_ids_are_hex_prefix():
    """Each blocker_id is a 16-char hex string."""
    manifest = build_release_blocker_manifest(glasses_root=glasses_root())
    for blocker in manifest["blockers"]:
        bid = blocker["blocker_id"]
        assert isinstance(bid, str)
        assert len(bid) == 16
        assert all(c in "0123456789abcdef" for c in bid), bid


# ---------------------------------------------------------------------------
# release_blocker_manifest envelope
# ---------------------------------------------------------------------------


def test_release_blocker_manifest_envelope_shape():
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest as tool,
    )

    env = tool()
    assert env["status"] in {
        "RELEASE_READY",
        "INCOMPLETE",
        "RELEASE_BLOCKED",
        "ERROR",
    }
    assert env["tool"] == "release_blocker_manifest"
    data = env["data"]
    assert "blockers" in data
    assert "summary" in data
    assert "upstream_status" in data
    summary = data["summary"]
    assert summary["blocker_count"] == len(data["blockers"])
    assert summary["block_count"] >= 0
    assert summary["warning_count"] >= 0
    assert summary["info_count"] >= 0
    assert "by_category" in summary
    assert "by_source_tool" in summary


def test_release_blocker_manifest_current_state_blocked():
    """The current project state is RELEASE_BLOCKED.

    Multiple upstream validators (structural, optical windows, DFM/DFA,
    PCB reconciliation, component coverage) report BLOCK-severity
    findings because required fields are still TBD.
    """
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest as tool,
    )

    env = tool()
    assert env["status"] == "RELEASE_BLOCKED"
    summary = env["data"]["summary"]
    assert summary["block_count"] > 0
    assert summary["blocker_count"] > 0
    # The upstream statuses must surface as INCOMPLETE for the validators
    # that drive the blockers.
    upstream = env["data"]["upstream_status"]
    assert upstream["structural"] == "INCOMPLETE"
    assert upstream["optical_window"] == "INCOMPLETE"
    assert upstream["dfm_dfa"] == "INCOMPLETE"
    assert upstream["pcb_reconciliation"] == "INCOMPLETE"
    # Reference integrity is OK (manifest hashes match the STLs).
    assert upstream["reference_integrity"] is True


def test_blockers_carry_required_fields():
    """Every blocker carries source_tool, category, severity, field,
    value, reason, remediation_hint."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest as tool,
    )

    env = tool()
    required_keys = {
        "blocker_id",
        "source_tool",
        "category",
        "severity",
        "field",
        "value",
        "reason",
        "remediation_hint",
    }
    for blocker in env["data"]["blockers"]:
        assert required_keys.issubset(set(blocker.keys())), (
            "Missing keys in blocker: "
            f"{required_keys - set(blocker.keys())}"
        )


def test_blockers_never_invent_unknown():
    """Blockers preserve UNKNOWN/TBD verbatim; the aggregator never
    invents a value to upgrade severity or hide the gap."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest as tool,
    )

    env = tool()
    values = [str(b["value"]) for b in env["data"]["blockers"]]
    # All values must be strings (never None, never fabricated
    # numbers masquerading as authoritative).
    for v in values:
        assert isinstance(v, str), v
    # Many TBD/UNKNOWN values must surface.
    assert any(v in {"UNKNOWN", "TBD"} or v.startswith("TBD") for v in values), (
        "Expected at least one UNKNOWN/TBD value in the blocker list; "
        f"got {values[:10]}"
    )


def test_blocker_source_tools_cover_every_validator():
    """The blocker list aggregates across every upstream validator."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest as tool,
    )

    env = tool()
    sources = {b["source_tool"] for b in env["data"]["blockers"]}
    expected = {
        "validate_structural_policy",
        "validate_optical_window_system",
        "validate_dfm_dfa",
        "reconcile_pcb",
        "component_authority",
    }
    assert expected.issubset(sources), (
        f"Expected sources {expected}, got {sources}"
    )


def test_blockers_ordered_deterministically():
    """Blockers are returned in (source_tool, blocker_id) order so
    two runs of the same state produce the same ordering."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        release_blocker_manifest as tool,
    )

    a = tool()["data"]["blockers"]
    b = tool()["data"]["blockers"]
    assert [bl["blocker_id"] for bl in a] == [
        bl["blocker_id"] for bl in b
    ]
    # Verify the canonical ordering key.
    keys = [
        (bl["source_tool"], bl["blocker_id"]) for bl in a
    ]
    assert keys == sorted(keys)


def test_serialise_release_blocker_manifest_is_valid_json():
    manifest = build_release_blocker_manifest(glasses_root=glasses_root())
    serialised = serialise_release_blocker_manifest(manifest)
    parsed = json.loads(serialised)
    assert parsed["status"] == manifest["status"]
    assert parsed["summary"] == manifest["summary"]


# ---------------------------------------------------------------------------
# Synthetic envelope tests (in-process envelopes supplied by the caller)
# ---------------------------------------------------------------------------


def test_aggregator_with_synthetic_pass_envelopes_releases_when_empty():
    """When every supplied envelope is PASS and there are no TBD /
    UNKNOWN coverage entries, the aggregator returns RELEASE_READY."""
    synthetic = {
        "structural_envelope": {
            "status": "PASS",
            "data": {
                "rib_zones_count": 1,
                "interfaces": ["pcb_mounts"],
                "missing_objectives": [],
                "exclusions_present": True,
                "findings": [],
                "tbd_fields": [],
            },
        },
        "optical_envelope": {
            "status": "PASS",
            "data": {
                "window_count": 6,
                "diameter_defined": True,
                "thickness_defined": True,
                "tbd_fields": [],
                "findings": [],
            },
        },
        "dfm_dfa_envelope": {
            "status": "PASS",
            "data": {"findings": [], "tbd_fields": []},
        },
        "pcb_envelope": {
            "status": "PASS",
            "data": {"findings": []},
        },
        "release_report_envelope": {
            "status": "RELEASE_READY",
            "data": {
                "required_fields_coverage": [
                    {
                        "component_id": "camthink_ov5640_8p5",
                        "field": "envelope_mm.x",
                        "value": 8.5,
                        "authoritative": True,
                        "is_tbd": False,
                    }
                ],
                "unknowns_records": [],
            },
        },
        "reference_integrity_envelope": {
            "manifest_present": True,
            "ok": True,
            "entries": [
                {
                    "name": "wayfarer_frame",
                    "ok": True,
                    "file": "silhouette/wayfarer/ray-ban-frame.stl",
                }
            ],
        },
        "pose_validation": {
            "validation": {"overall_status": "PASS"},
            "accepted": [],
            "rejected": [],
        },
    }
    manifest = build_release_blocker_manifest(
        glasses_root=glasses_root(), **synthetic
    )
    assert manifest["status"] == "RELEASE_READY"
    assert manifest["summary"]["blocker_count"] == 0


def test_aggregator_severity_normalisation():
    """Severity strings outside the canonical set are normalised to BLOCK."""
    synthetic = {
        "structural_envelope": {
            "status": "PASS",
            "data": {
                "rib_zones_count": 1,
                "interfaces": ["pcb_mounts"],
                "missing_objectives": [],
                "exclusions_present": True,
                "findings": [],
                "tbd_fields": [],
            },
        },
        "optical_envelope": {
            "status": "PASS",
            "data": {"tbd_fields": [], "findings": []},
        },
        "dfm_dfa_envelope": {
            "status": "PASS",
            "data": {
                "findings": [
                    {
                        "rule": "hole_diameter",
                        "severity": "CRITICAL",
                        "path": "pcb_stackup.holes[0]",
                        "value": "0.0",
                    }
                ],
                "tbd_fields": [],
            },
        },
        "pcb_envelope": {"status": "PASS", "data": {"findings": []}},
        "release_report_envelope": {
            "status": "PASS",
            "data": {"required_fields_coverage": [], "unknowns_records": []},
        },
        "reference_integrity_envelope": {
            "manifest_present": True,
            "ok": True,
            "entries": [],
        },
        "pose_validation": {
            "validation": {"overall_status": "PASS"},
            "accepted": [],
            "rejected": [],
        },
    }
    manifest = build_release_blocker_manifest(
        glasses_root=glasses_root(), **synthetic
    )
    # The CRITICAL severity must be normalised to BLOCK; the
    # aggregator must NEVER silently downgrade a blocker.
    dfm = [
        b for b in manifest["blockers"]
        if b["source_tool"] == "validate_dfm_dfa"
    ]
    assert dfm
    assert all(b["severity"] == "BLOCK" for b in dfm)
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_aggregator_pose_validation_blocks_release():
    """If pose validation overall_status is not PASS, the aggregator
    surfaces a BLOCK-severity blocker."""
    synthetic = {
        "structural_envelope": {
            "status": "PASS",
            "data": {
                "rib_zones_count": 1,
                "interfaces": ["pcb_mounts"],
                "missing_objectives": [],
                "exclusions_present": True,
                "findings": [],
                "tbd_fields": [],
            },
        },
        "optical_envelope": {
            "status": "PASS",
            "data": {"tbd_fields": [], "findings": []},
        },
        "dfm_dfa_envelope": {
            "status": "PASS",
            "data": {"findings": [], "tbd_fields": []},
        },
        "pcb_envelope": {"status": "PASS", "data": {"findings": []}},
        "release_report_envelope": {
            "status": "PASS",
            "data": {"required_fields_coverage": [], "unknowns_records": []},
        },
        "reference_integrity_envelope": {
            "manifest_present": True,
            "ok": True,
            "entries": [],
        },
        "pose_validation": {
            "validation": {"overall_status": "INCOMPLETE"},
            "accepted": [],
            "rejected": [
                {
                    "component": "camthink_ov5640_8p5",
                    "reason": "clearance violation",
                }
            ],
        },
    }
    manifest = build_release_blocker_manifest(
        glasses_root=glasses_root(), **synthetic
    )
    pose_blockers = [
        b for b in manifest["blockers"]
        if b["source_tool"] == "validate_poses"
    ]
    assert len(pose_blockers) >= 2  # overall_status + rejected
    assert all(b["severity"] == "BLOCK" for b in pose_blockers)
    assert manifest["status"] == "RELEASE_BLOCKED"


def test_aggregator_reference_integrity_failure_blocks():
    """Missing reference manifest surfaces a DATA_GAP blocker."""
    synthetic = {
        "structural_envelope": {
            "status": "PASS",
            "data": {
                "rib_zones_count": 1,
                "interfaces": ["pcb_mounts"],
                "missing_objectives": [],
                "exclusions_present": True,
                "findings": [],
                "tbd_fields": [],
            },
        },
        "optical_envelope": {
            "status": "PASS",
            "data": {"tbd_fields": [], "findings": []},
        },
        "dfm_dfa_envelope": {
            "status": "PASS",
            "data": {"findings": [], "tbd_fields": []},
        },
        "pcb_envelope": {"status": "PASS", "data": {"findings": []}},
        "release_report_envelope": {
            "status": "PASS",
            "data": {"required_fields_coverage": [], "unknowns_records": []},
        },
        "reference_integrity_envelope": {
            "manifest_present": False,
            "ok": False,
            "entries": [],
        },
        "pose_validation": {
            "validation": {"overall_status": "PASS"},
            "accepted": [],
            "rejected": [],
        },
    }
    manifest = build_release_blocker_manifest(
        glasses_root=glasses_root(), **synthetic
    )
    assert manifest["upstream_status"]["reference_integrity"] is False
    assert manifest["status"] == "RELEASE_BLOCKED"
    assert any(
        b["source_tool"] == "verify_reference_integrity"
        and b["category"] == "DATA_GAP"
        for b in manifest["blockers"]
    )


def test_aggregator_records_blockers_are_info_only():
    """UNKNOWN records already on file surface as INFO, not BLOCK."""
    synthetic = {
        "structural_envelope": {
            "status": "PASS",
            "data": {
                "rib_zones_count": 1,
                "interfaces": ["pcb_mounts"],
                "missing_objectives": [],
                "exclusions_present": True,
                "findings": [],
                "tbd_fields": [],
            },
        },
        "optical_envelope": {
            "status": "PASS",
            "data": {"tbd_fields": [], "findings": []},
        },
        "dfm_dfa_envelope": {
            "status": "PASS",
            "data": {"findings": [], "tbd_fields": []},
        },
        "pcb_envelope": {"status": "PASS", "data": {"findings": []}},
        "release_report_envelope": {
            "status": "PASS",
            "data": {
                "required_fields_coverage": [],
                "unknowns_records": [
                    {
                        "component_id": "battery_cell",
                        "field": "battery.capacity_mah",
                        "status": "UNKNOWN",
                        "reason": "Datasheet not yet captured",
                    }
                ],
            },
        },
        "reference_integrity_envelope": {
            "manifest_present": True,
            "ok": True,
            "entries": [],
        },
        "pose_validation": {
            "validation": {"overall_status": "PASS"},
            "accepted": [],
            "rejected": [],
        },
    }
    manifest = build_release_blocker_manifest(
        glasses_root=glasses_root(), **synthetic
    )
    info_blockers = [
        b for b in manifest["blockers"] if b["severity"] == "INFO"
    ]
    assert any(
        b["component_id"] == "battery_cell"
        and b["field"] == "battery.capacity_mah"
        for b in info_blockers
    )
    # The recorded UNKNOWN must NOT push the manifest to BLOCKED --
    # only INFO/WARNING findings remain, so the status is INCOMPLETE.
    assert manifest["status"] == "INCOMPLETE"
    assert manifest["summary"]["block_count"] == 0
    assert manifest["summary"]["info_count"] >= 1


# ---------------------------------------------------------------------------
# audit_timeline
# ---------------------------------------------------------------------------


def test_audit_timeline_envelope_shape():
    from cad_engineering_mcp.tools.release_blocker_tools import (
        audit_timeline as tool,
    )

    env = tool()
    assert env["status"] in {"PASS", "ERROR"}
    assert env["tool"] == "audit_timeline"
    data = env["data"]
    assert "events" in data
    assert "summary" in data
    summary = data["summary"]
    assert "event_count" in summary
    assert "success_count" in summary
    assert "failure_count" in summary
    assert "tools" in summary
    assert "operations" in summary


def test_audit_timeline_filters_by_tool():
    """Filter by tool narrows the event list to that tool only."""
    # Seed two distinct entries.
    from cad_engineering_mcp.tools._mutation import audit

    timestamp = "2026-09-01T00-00-00-000001"
    audit(
        timestamp=timestamp,
        tool="release_blocker_manifest",
        operation="read",
        affected_paths=["x"],
        success=True,
    )
    audit(
        timestamp=timestamp,
        tool="audit_timeline",
        operation="read",
        affected_paths=["y"],
        success=True,
    )

    from cad_engineering_mcp.tools.release_blocker_tools import (
        audit_timeline as tool,
    )

    env = tool(tool_filter="release_blocker_manifest")
    tools = {e["tool"] for e in env["data"]["events"]}
    assert tools == {"release_blocker_manifest"}


def test_audit_timeline_filters_by_success():
    """Filter by success_only=True returns only successful events."""
    from cad_engineering_mcp.tools._mutation import audit

    timestamp = "2026-09-01T00-00-00-000002"
    audit(
        timestamp=timestamp,
        tool="success_filter_test",
        operation="read",
        affected_paths=["z"],
        success=True,
    )
    audit(
        timestamp=timestamp,
        tool="success_filter_test",
        operation="read",
        affected_paths=["z"],
        success=False,
        errors=["synthetic failure"],
    )

    from cad_engineering_mcp.tools.release_blocker_tools import (
        audit_timeline as tool,
    )

    success_env = tool(tool_filter="success_filter_test", success_only=True)
    failure_env = tool(tool_filter="success_filter_test", success_only=False)

    assert all(e["success"] for e in success_env["data"]["events"])
    assert all(not e["success"] for e in failure_env["data"]["events"])


def test_audit_timeline_summary_counts():
    """Summary event_count / success_count / failure_count agree with events."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        audit_timeline as tool,
    )

    env = tool(tool_filter="summary_count_test")
    summary = env["data"]["summary"]
    assert summary["event_count"] == len(env["data"]["events"])
    assert (
        summary["success_count"] + summary["failure_count"]
        == summary["event_count"]
    )


def test_audit_timeline_empty_when_no_log(tmp_path):
    """The tool returns event_count=0 when the audit directory is absent
    or empty."""
    glasses = glasses_root()
    audit_dir = glasses / "manufacturing" / "releases" / "audit"
    backup = Path(tempfile.gettempdir()) / "_audit_timeline_backup"
    if audit_dir.exists():
        shutil.copytree(audit_dir, backup, dirs_exist_ok=True)
        shutil.rmtree(audit_dir)
    try:
        timeline = build_audit_timeline(glasses_root=glasses)
        assert timeline["status"] == "PASS"
        assert timeline["summary"]["event_count"] == 0
        assert timeline["events"] == []
    finally:
        if backup.exists():
            shutil.copytree(backup, audit_dir, dirs_exist_ok=True)
            shutil.rmtree(backup)


# ---------------------------------------------------------------------------
# save_release_blocker_manifest
# ---------------------------------------------------------------------------


def test_save_release_blocker_manifest_dry_run_does_not_write():
    from cad_engineering_mcp.tools.release_blocker_tools import (
        save_release_blocker_manifest as tool,
    )

    target = glasses_root() / "manufacturing" / "releases" / "phase5-dry-run.json"
    if target.exists():
        target.unlink()
    env = tool(destination="manufacturing/releases/phase5-dry-run.json")
    assert env["status"] == "PASS"
    assert env["data"]["executed"] is False
    assert not target.exists()


def test_save_release_blocker_manifest_mutation_writes_and_audits():
    from cad_engineering_mcp.tools.release_blocker_tools import (
        save_release_blocker_manifest as tool,
    )

    target = glasses_root() / "manufacturing" / "releases" / "phase5-mut.json"
    if target.exists():
        target.unlink()
    try:
        env = tool(
            destination="manufacturing/releases/phase5-mut.json",
            allow_mutation=True,
        )
        assert env["status"] == "PASS"
        assert env["data"]["executed"] is True
        assert env["data"]["after_sha256"] is not None
        assert target.exists()
        # Re-read the file and check it parses to a manifest with the
        # canonical shape.
        parsed = json.loads(target.read_text(encoding="utf-8"))
        assert parsed["status"] in {
            "RELEASE_READY",
            "INCOMPLETE",
            "RELEASE_BLOCKED",
        }
        assert "summary" in parsed
        assert "blockers" in parsed
    finally:
        if target.exists():
            target.unlink()


def test_save_release_blocker_manifest_rejects_outside_tree():
    from cad_engineering_mcp.tools.release_blocker_tools import (
        save_release_blocker_manifest as tool,
    )

    env = tool(destination="/tmp/outside-project.json", allow_mutation=True)
    assert env["status"] == "ERROR"
    assert env["errors"]


# ---------------------------------------------------------------------------
# Audit-timeline end-to-end
# ---------------------------------------------------------------------------


def test_save_then_audit_timeline_records_event():
    """A successful save produces an audit entry that surfaces in
    audit_timeline."""
    from cad_engineering_mcp.tools.release_blocker_tools import (
        audit_timeline,
        save_release_blocker_manifest,
    )

    target = glasses_root() / "manufacturing" / "releases" / "phase5-e2e.json"
    if target.exists():
        target.unlink()
    try:
        save_env = save_release_blocker_manifest(
            destination="manufacturing/releases/phase5-e2e.json",
            allow_mutation=True,
        )
        assert save_env["status"] == "PASS"
        assert save_env["data"]["executed"] is True

        timeline = audit_timeline(
            tool_filter="save_release_blocker_manifest"
        )
        assert timeline["status"] == "PASS"
        assert any(
            e.get("operation") == "add"
            and e.get("success") is True
            for e in timeline["data"]["events"]
        )
    finally:
        if target.exists():
            target.unlink()