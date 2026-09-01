from pathlib import Path

from mcp.server import MCPServer

from .tools import (
    add_assembly_component,
    audit_timeline,
    generate_pcb_outline,
    get_pose_validation_summary,
    list_analysis_artifacts,
    list_assembly_components,
    manufacturing_release_report,
    measure_mesh,
    mesh_interference,
    minimum_surface_distance,
    propose_pose,
    read_analysis_artifact,
    reconcile_pcb,
    release_blocker_manifest,
    run_pose_pipeline,
    save_manufacturing_release_report,
    save_release_blocker_manifest,
    validate_dfm_dfa,
    validate_optical_window_system,
    validate_poses,
    validate_structural_policy,
    verify_reference_integrity,
)
from .tools._paths import glasses_root, project_root


mcp = MCPServer(
    "Product Engineering MCP",
    instructions="""
You are connected to a persistent product-engineering workspace.

The workspace contains mechanical CAD, KiCad electronics,
component models, reference geometry, manufacturing data,
measurements, analysis results, and manufacturing exports.

Engineering rules:

- All dimensions are millimetres unless explicitly stated otherwise.
- Geometry precision must be preserved.
- Source CAD files are authoritative.
- Derived STEP/STL files must never silently become the primary source.
- Manufacturing exports must be validated after export.
- Mechanical and electrical designs are treated as one assembly.
- Component dimensions should come from measured geometry or authoritative specifications.
- Design changes must be revision tracked.
- Previous revisions must remain recoverable.
- Reference geometry is read-only.
- Never silently change units or scale.

Phase 1 exposes only read/verification tools. PASS is never
guaranteed to mean "production ready"; callers must inspect the
returned status and warnings.

Phase 2 adds the controlled geometry/pose validation layer:

  mesh_interference  -- deterministic mesh-mesh interference testing
                        with envelope and surface-distance reporting.
  propose_pose       -- geometry-derived candidate generation. Never
                        mutates the workspace.
  validate_poses     -- runs the geometry-aware pose validator in
                        memory. The summary never upgrades an
                        obstructed optical cone or an undeterministic
                        result to PASS.

Phase 3 adds the controlled-write and engineering-policy tools:

  run_pose_pipeline            -- executes the canonical pose-pipeline
                                  shell script under strict constraints.
                                  Rejects arbitrary script execution;
                                  refuses to mutate unless
                                  allow_mutation=true; backs up and
                                  audit-logs every change.
  generate_pcb_outline         -- executes the canonical PCB-outline
                                  generator. Requires pose validation
                                  PASS unless force=true; never silently
                                  overrides a non-PASS engineering state.
  list_assembly_components     -- structured view of the assembly YAML;
                                  read-only.
  add_assembly_component       -- adds a component to the assembly YAML
                                  with bounds, finiteness, and duplicate
                                  checks; backups and audit-logs the
                                  mutation.
  validate_structural_policy   -- validates structural-policy.yaml and
                                  rib-system.yaml; surfaces TBD fields,
                                  missing objectives, and an empty
                                  rib_zones as INCOMPLETE.
  validate_optical_window_system -- validates the IR optical-window
                                  YAMLs; surfaces TBD diameter,
                                  thickness, recess, retention, and
                                  adhesive fields. INCOMPLETE whenever
                                  a required field is TBD.

Phase 4 adds the engineering-data, DFM/DFA, PCB-reconciliation,
and manufacturing-readiness layer:

  validate_dfm_dfa             -- runs the DFM (wall thickness, rib
                                  geometry, PCB stackup, hole geometry,
                                  manufacturing method) and DFA
                                  (replaceability, wire routing,
                                  connector access, screw bosses,
                                  snap-fits, removable front) checks
                                  across every project manifest. Never
                                  upgrades an unresolved TBD to PASS.
  reconcile_pcb                -- derives a PCB outline from the
                                  mechanical envelope, the validated
                                  component poses, the LED keepouts,
                                  and the camera FPC; cross-checks the
                                  existing schematic outline; reports
                                  every UNKNOWN footprint / connector /
                                  stackup field that blocks release.
  manufacturing_release_report -- aggregates reference integrity,
                                  DFM/DFA, PCB reconciliation, and
                                  component-data UNKNOWN/TBD coverage
                                  into one release-readiness envelope.
                                  Returns RELEASE_READY only when every
                                  upstream validator has PASSed AND
                                  every required component field is
                                  authoritative.
  save_manufacturing_release_report
                               -- persists the manufacturing-readiness
                                  report under
                                  ``manufacturing/releases/`` with
                                  backup + audit; refuses to mutate
                                  unless allow_mutation=true.

Phase 5 adds the release-blocker resolution and audit-timeline layer:

  release_blocker_manifest     -- re-runs every upstream validator
                                  (reference integrity, structural
                                  policy, optical windows, DFM/DFA,
                                  PCB reconciliation, manufacturing
                                  release report, component-authority
                                  coverage, pose validation) and
                                  emits one canonical blocker list
                                  with source_tool / category /
                                  severity / field / component_id /
                                  value / reason / remediation_hint.
                                  UNKNOWN and TBD values are preserved
                                  verbatim; nothing is fabricated.
                                  Status is RELEASE_BLOCKED whenever
                                  any BLOCK-severity blocker is
                                  present, INCOMPLETE when only
                                  WARNING-severity blockers are
                                  present, and RELEASE_READY only
                                  when the blocker list is empty.
  audit_timeline               -- reads
                                  ``manufacturing/releases/audit/*.jsonl``
                                  and returns a chronological list of
                                  engineering events with optional
                                  tool / operation / success filters.
                                  Read-only inspection.
  save_release_blocker_manifest
                               -- persists the release-blocker manifest
                                  under ``manufacturing/releases/``
                                  with backup + audit; refuses to
                                  mutate unless allow_mutation=true.
"""
)


@mcp.tool()
def project_status() -> str:
    """Return the current status of the glasses engineering workspace."""

    root = project_root()
    glasses = glasses_root()
    return f"""Product Engineering MCP is online.

Project:
  glasses

Root:
  {root}

Glasses project:
  {glasses}

Units:
  mm

Mechanical:
  FreeCAD

Electronics:
  KiCad

Reference geometry:
  {glasses / "references"}

Components:
  {glasses / "components"}

Analysis:
  {glasses / "analysis"}

Exports:
  {glasses / "exports"}

Phase 1 tools:
  list_analysis_artifacts
  read_analysis_artifact
  get_pose_validation_summary
  verify_reference_integrity
  measure_mesh
  minimum_surface_distance

Phase 2 tools:
  mesh_interference
  propose_pose
  validate_poses

Phase 3 tools:
  run_pose_pipeline
  generate_pcb_outline
  list_assembly_components
  add_assembly_component
  validate_structural_policy
  validate_optical_window_system

Phase 4 tools:
  validate_dfm_dfa
  reconcile_pcb
  manufacturing_release_report
  save_manufacturing_release_report

Phase 5 tools:
  release_blocker_manifest
  audit_timeline
  save_release_blocker_manifest
"""


@mcp.tool()
def list_project_files() -> str:
    """List all files in the glasses engineering workspace."""

    if not glasses_root().exists():
        return "The glasses project directory does not exist."

    files = sorted(
        path.relative_to(glasses_root())
        for path in glasses_root().rglob("*")
        if path.is_file()
    )

    if not files:
        return "The glasses project contains no files yet."

    return "\n".join(str(path) for path in files)


@mcp.tool()
def list_analysis_artifacts(
    category: str = "all",
    subdir: str | None = None,
) -> dict:
    """List analysis artifacts under projects/glasses.

    category: geometry | optical | structure | analysis | mechanical |
               electronics | manufacturing | all (default all)
    subdir:   optional relative sub-path within the category
    """
    from .tools.read_tools import list_analysis_artifacts as _impl

    return _impl(category=category, subdir=subdir)


@mcp.tool()
def read_analysis_artifact(path: str) -> dict:
    """Parse a JSON or YAML artifact under projects/glasses.

    Only json.loads and yaml.safe_load are used. Files larger than
    4 MB are rejected.
    """
    from .tools.read_tools import read_analysis_artifact as _impl

    return _impl(path)


@mcp.tool()
def get_pose_validation_summary(
    artifact: str = "analysis/geometry/component-pose-validation.json",
) -> dict:
    """Summarise the latest component pose validation report.

    Never upgrades an obstructed-camera optical cone to PASS.
    """
    from .tools.read_tools import get_pose_validation_summary as _impl

    return _impl(artifact=artifact)


@mcp.tool()
def verify_reference_integrity(name: str | None = None) -> dict:
    """Verify SHA-256 of every (or one) reference in references/reference-manifest.yaml."""
    from .tools.verification_tools import verify_reference_integrity as _impl

    return _impl(name=name)


@mcp.tool()
def measure_mesh(path: str) -> dict:
    """Measure an STL/OBJ/PLY/OFF/3MF mesh under projects/glasses.

    Returns bounding box, dimensions, centroid, volume, surface area,
    watertight and winding-consistent flags, plus the file SHA-256.
    """
    from .tools.verification_tools import measure_mesh as _impl

    return _impl(path)


@mcp.tool()
def minimum_surface_distance(path_a: str, path_b: str) -> dict:
    """Compute minimum surface-to-surface distance between two meshes."""
    from .tools.verification_tools import minimum_surface_distance as _impl

    return _impl(path_a, path_b)


@mcp.tool()
def mesh_interference(component_a_id: str, component_b_id: str) -> dict:
    """Deterministic mesh-level interference testing between two registered components.

    component_a_id, component_b_id: component identifiers (e.g.
    ``camthink_ov5640_8p5``, ``vsma1094750x02``, ``wayfarer_frame``,
    ``wayfarer_left_temple``, ``wayfarer_right_temple``).

    Returns:
      * ``status``     PASS | FAIL | ERROR
      * ``intersects`` True / False / null (null when the collision
                       backend is unavailable; the tool refuses to
                       silently downgrade failures).
      * ``envelope_overlap``, ``bbox_gap_mm``, ``min_surface_distance_mm``
      * ``collision_engine`` (the engine actually used)
      * ``clearance_classification`` NOMINAL | CLEARANCE | INTERFERENCE | UNKNOWN
    """
    from .tools.mesh_interference import mesh_interference as _impl

    return _impl(component_a_id, component_b_id)


@mcp.tool()
def propose_pose(
    component_id: str,
    region: str,
    host_axis: str,
    clearance_mm: float,
) -> dict:
    """Generate geometry-derived component candidates for a component/region/axis.

    component_id: registered component id (e.g. ``camthink_ov5640_8p5``
                  or ``vsma1094750x02``).
    region:       center_nose_bridge | front_frame | left_temple | right_temple.
    host_axis:    forward | outward | same_as_camera.
    clearance_mm: required clearance in mm (positive finite).

    Candidates are returned in memory only; no files are written. All
    coordinates are DERIVED from authoritative frame STL geometry.
    """
    from .tools.propose_pose import propose_pose as _impl

    return _impl(
        component_id=component_id,
        region=region,
        host_axis=host_axis,
        clearance_mm=clearance_mm,
    )


@mcp.tool()
def validate_poses(
    candidates_path: str | None = None,
    tolerance_overrides_mm: dict | None = None,
) -> dict:
    """Run the geometry-aware pose validator and return the structured report.

    candidates_path:         default
        ``analysis/geometry/component-pose-candidates.json``
    tolerance_overrides_mm:  optional tolerance overrides. Values below
        the mandatory policy floors are rejected. Never silently
        applied.

    Returns the complete validator output. The summary ``status`` is
    INCOMPLETE whenever the camera optical cone is obstructed or the
    validator cannot produce a deterministic result, so callers cannot
    mistake an obstructed optical cone for a production-ready PASS.
    """
    from .tools.validate_poses import validate_poses as _impl

    return _impl(
        candidates_path=candidates_path,
        tolerance_overrides_mm=tolerance_overrides_mm,
    )


@mcp.tool()
def run_pose_pipeline(
    python_path: str | None = None,
    dry_run: bool = False,
    allow_mutation: bool = False,
) -> dict:
    """Run the canonical pose pipeline.

    Constrained to ``projects/glasses/analysis/geometry/run-pipeline.sh``.
    Rejects arbitrary script execution. Refuses to mutate unless
    ``allow_mutation=true``. Records mtime/sha256 of the three
    downstream artifacts before and after execution.
    """
    from .tools.run_pose_pipeline import run_pose_pipeline as _impl

    return _impl(
        python_path=python_path,
        dry_run=dry_run,
        allow_mutation=allow_mutation,
    )


@mcp.tool()
def generate_pcb_outline(
    python_path: str | None = None,
    force: bool = False,
    allow_mutation: bool = False,
) -> dict:
    """Run the canonical PCB-outline generator.

    Requires ``analysis/geometry/component-pose-validation.json`` to have
    ``overall_status == "PASS"`` unless ``force=true``. Refuses to
    mutate unless ``allow_mutation=true``. Surface PCB-architecture
    findings as warnings instead of silently overriding them.
    """
    from .tools.generate_pcb_outline import generate_pcb_outline as _impl

    return _impl(
        python_path=python_path,
        force=force,
        allow_mutation=allow_mutation,
    )


@mcp.tool()
def list_assembly_components() -> dict:
    """List components in ``projects/glasses/mechanical/assemblies/glasses-assembly.yaml``.

    Read-only.
    """
    from .tools.assembly_tools import list_assembly_components as _impl

    return _impl()


@mcp.tool()
def add_assembly_component(
    component_id: str,
    position_mm: list[float],
    rotation_deg: list[float] | None = None,
    coordinate_system: str = "glasses_master",
    confirm_out_of_bounds: bool = False,
) -> dict:
    """Add a component to the assembly manifest with safety checks.

    Duplicate component IDs are rejected. Positions outside the frame
    bounding box are rejected unless ``confirm_out_of_bounds=true``.
    Every mutation is backed up under
    ``projects/glasses/manufacturing/releases/<UTC>/`` and recorded in
    the audit log.
    """
    from .tools.assembly_tools import add_assembly_component as _impl

    return _impl(
        component_id=component_id,
        position_mm=position_mm,
        rotation_deg=rotation_deg,
        coordinate_system=coordinate_system,
        confirm_out_of_bounds=confirm_out_of_bounds,
    )


@mcp.tool()
def validate_structural_policy() -> dict:
    """Validate ``structural-policy.yaml`` and ``rib-system.yaml``.

    Reports ``missing_objectives``, ``rib_zones_count``, ``interfaces``,
    ``tbd_fields``, and human-readable findings. Returns ``INCOMPLETE``
    whenever ``rib_zones`` is empty (current project state).
    """
    from .tools.structural_tools import validate_structural_policy as _impl

    return _impl()


@mcp.tool()
def validate_optical_window_system() -> dict:
    """Validate the IR optical-window YAML files.

    Reports placements, status of each required field (diameter,
    thickness, recess diameter, recess depth, retention lip,
    adhesive), and TBD findings. Returns ``INCOMPLETE`` whenever any
    required field is ``TBD``.
    """
    from .tools.optical_window_tools import (
        validate_optical_window_system as _impl,
    )

    return _impl()


@mcp.tool()
def validate_dfm_dfa() -> dict:
    """Run the DFM and DFA checks across the project YAML manifests.

    Read-only. Returns a structured envelope with per-rule
    findings, the combined DFM/DFA status, and the TBD field scan.
    The status is ``INCOMPLETE`` whenever any BLOCK-severity
    finding is present or any required field is TBD.
    """
    from .tools.manufacturing_tools import validate_dfm_dfa as _impl

    return _impl()


@mcp.tool()
def reconcile_pcb() -> dict:
    """Reconcile the PCB architecture against the mechanical envelope.

    Read-only. Returns the derived PCB outline (from the frame
    bbox), the existing outline (from schematic-architecture.yaml),
    the fitted-in-frame verdict, the per-component envelopes, and
    a list of UNKNOWN/TBD findings that block release.
    """
    from .tools.manufacturing_tools import reconcile_pcb as _impl

    return _impl()


@mcp.tool()
def manufacturing_release_report() -> dict:
    """Build the manufacturing-readiness release report.

    Combines reference integrity, DFM/DFA, PCB reconciliation, and
    component-data UNKNOWN/TBD coverage. The status is
    ``RELEASE_READY`` only when every upstream validator PASSed AND
    every required component field is authoritative; otherwise
    ``INCOMPLETE`` or ``RELEASE_BLOCKED``.
    """
    from .tools.manufacturing_tools import (
        manufacturing_release_report as _impl,
    )

    return _impl()


@mcp.tool()
def save_manufacturing_release_report(
    destination: str = "manufacturing/releases/manufacturing-readiness.json",
    allow_mutation: bool = False,
) -> dict:
    """Persist the manufacturing-readiness report.

    Refuses to mutate unless ``allow_mutation=true``. Every write
    is backed up under ``manufacturing/releases/<UTC>/`` and
    audit-logged. The tool never overwrites a release-readiness
    report with an ``ERROR`` envelope.
    """
    from .tools.manufacturing_tools import (
        save_manufacturing_release_report as _impl,
    )

    return _impl(
        destination=destination,
        allow_mutation=allow_mutation,
    )


@mcp.tool()
def release_blocker_manifest() -> dict:
    """Build the canonical release-blocker manifest.

    Re-runs every upstream validator (reference integrity, structural
    policy, optical windows, DFM/DFA, PCB reconciliation,
    manufacturing release report, component-authority coverage,
    pose validation) and emits one deterministic blocker list. Each
    blocker carries ``source_tool``, ``category``, ``severity``,
    ``field``, ``component_id``, ``value``, ``reason``, and
    ``remediation_hint``. UNKNOWN/TBD values are preserved verbatim.

    Read-only. Status is ``RELEASE_BLOCKED`` whenever any BLOCK-severity
    blocker is present, ``INCOMPLETE`` when only WARNING-severity
    blockers remain, and ``RELEASE_READY`` only when the blocker list
    is empty.
    """
    from .tools.release_blocker_tools import (
        release_blocker_manifest as _impl,
    )

    return _impl()


@mcp.tool()
def audit_timeline(
    tool_filter: str | None = None,
    operation_filter: str | None = None,
    success_only: bool | None = None,
) -> dict:
    """Build the engineering audit-timeline from the JSONL log.

    Reads ``manufacturing/releases/audit/*.jsonl`` and returns a
    chronological list of engineering events with optional filters
    by tool name, operation, or success/failure. Read-only.
    """
    from .tools.release_blocker_tools import (
        audit_timeline as _impl,
    )

    return _impl(
        tool_filter=tool_filter,
        operation_filter=operation_filter,
        success_only=success_only,
    )


@mcp.tool()
def save_release_blocker_manifest(
    destination: str = "manufacturing/releases/release-blocker-manifest.json",
    allow_mutation: bool = False,
) -> dict:
    """Persist the release-blocker manifest.

    Refuses to mutate unless ``allow_mutation=true``. Every write is
    backed up under ``manufacturing/releases/<UTC>/`` and
    audit-logged. The tool never overwrites a destination outside the
    allowed roots and never downgrades BLOCK to WARNING.
    """
    from .tools.release_blocker_tools import (
        save_release_blocker_manifest as _impl,
    )

    return _impl(
        destination=destination,
        allow_mutation=allow_mutation,
    )


if __name__ == "__main__":
    mcp.run()