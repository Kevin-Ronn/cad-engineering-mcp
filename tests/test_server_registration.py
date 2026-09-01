"""Verify the MCP server exposes every registered tool by name.

Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 + Phase 6: 27 tools total.
"""
from __future__ import annotations

import pytest


EXPECTED_TOOLS = {
    # Phase 1.
    "project_status",
    "list_project_files",
    "list_analysis_artifacts",
    "read_analysis_artifact",
    "get_pose_validation_summary",
    "verify_reference_integrity",
    "measure_mesh",
    "minimum_surface_distance",
    # Phase 2.
    "mesh_interference",
    "propose_pose",
    "validate_poses",
    # Phase 3.
    "run_pose_pipeline",
    "generate_pcb_outline",
    "list_assembly_components",
    "add_assembly_component",
    "validate_structural_policy",
    "validate_optical_window_system",
    # Phase 4.
    "validate_dfm_dfa",
    "reconcile_pcb",
    "manufacturing_release_report",
    "save_manufacturing_release_report",
    # Phase 5.
    "release_blocker_manifest",
    "audit_timeline",
    "save_release_blocker_manifest",
    # Phase 6.
    "list_authoritative_overrides",
    "authoritative_value_override",
    "resolution_plan",
}


def test_all_tools_registered():
    from cad_engineering_mcp.server import mcp

    registered = set(mcp._tool_manager._tools.keys())
    missing = EXPECTED_TOOLS - registered
    assert not missing, f"Missing tools: {sorted(missing)}"
    extra = registered - EXPECTED_TOOLS
    assert not extra, f"Unexpected tools: {sorted(extra)}"
    assert len(registered) == 27, (
        f"Expected exactly 27 tools, got {len(registered)}: {sorted(registered)}"
    )


def test_phase1_tools_still_present():
    from cad_engineering_mcp.server import mcp

    for name in (
        "project_status",
        "list_project_files",
        "list_analysis_artifacts",
        "read_analysis_artifact",
        "get_pose_validation_summary",
        "verify_reference_integrity",
        "measure_mesh",
        "minimum_surface_distance",
    ):
        assert name in mcp._tool_manager._tools, name


def test_phase2_tools_present():
    from cad_engineering_mcp.server import mcp

    for name in ("mesh_interference", "propose_pose", "validate_poses"):
        assert name in mcp._tool_manager._tools, name


def test_phase3_tools_present():
    from cad_engineering_mcp.server import mcp

    expected_phase3 = (
        "run_pose_pipeline",
        "generate_pcb_outline",
        "list_assembly_components",
        "add_assembly_component",
        "validate_structural_policy",
        "validate_optical_window_system",
    )
    for name in expected_phase3:
        assert name in mcp._tool_manager._tools, name


def test_phase4_tools_present():
    from cad_engineering_mcp.server import mcp

    expected_phase4 = (
        "validate_dfm_dfa",
        "reconcile_pcb",
        "manufacturing_release_report",
        "save_manufacturing_release_report",
    )
    for name in expected_phase4:
        assert name in mcp._tool_manager._tools, name


def test_phase5_tools_present():
    from cad_engineering_mcp.server import mcp

    expected_phase5 = (
        "release_blocker_manifest",
        "audit_timeline",
        "save_release_blocker_manifest",
    )
    for name in expected_phase5:
        assert name in mcp._tool_manager._tools, name


def test_phase6_tools_present():
    from cad_engineering_mcp.server import mcp

    expected_phase6 = (
        "list_authoritative_overrides",
        "authoritative_value_override",
        "resolution_plan",
    )
    for name in expected_phase6:
        assert name in mcp._tool_manager._tools, name


def test_tool_count_exact():
    from cad_engineering_mcp.server import mcp

    assert len(mcp._tool_manager._tools) == 27