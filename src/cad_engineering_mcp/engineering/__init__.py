from .assembly import (
    AssemblyError,
    add_component,
    get_component_transform,
    identity_matrix,
    list_assembly_components,
    load_assembly,
    make_transform,
    remove_component,
    transform_point,
)

from .component_registry import (
    ComponentRegistryError,
    component_exists,
    get_component,
    list_components,
    load_registry,
    register_component,
    register_geometry,
)

from .reference_geometry import (
    ReferenceGeometryError,
    get_reference,
    list_references,
    load_reference_mesh,
    measure_distance,
    measure_reference,
    mesh_summary,
    verify_reference_integrity,
)


__all__ = [
    "AssemblyError",
    "add_component",
    "get_component_transform",
    "identity_matrix",
    "list_assembly_components",
    "load_assembly",
    "make_transform",
    "remove_component",
    "transform_point",

    "ComponentRegistryError",
    "component_exists",
    "get_component",
    "list_components",
    "load_registry",
    "register_component",
    "register_geometry",

    "ReferenceGeometryError",
    "get_reference",
    "list_references",
    "load_reference_mesh",
    "measure_distance",
    "measure_reference",
    "mesh_summary",
    "verify_reference_integrity",
]

from .component import (
    register_geometry_component,
)

from .component_geometry import (
    ComponentGeometryError,
    load_mesh,
    measure_mesh,
    mesh_contains_point,
    minimum_surface_distance,
)

from .assembly_analysis import (
    AssemblyAnalysisError,
    component_envelope,
    envelope_intersects,
    minimum_envelope_clearance,
    mesh_interference,
    transformed_mesh,
)

from .structural import (
    StructuralDesignError,
    load_rib_system,
    load_structural_policy,
    rib_rule,
    structural_interfaces,
    validate_structural_policy,
)

from .optical_windows import (
    OpticalWindowError,
    list_window_placements,
    load_window_geometry,
    load_window_system,
    validate_window_system,
)

from .component_mesh_resolution import (
    ComponentMeshResolutionError,
    resolve_component_mesh_path,
    resolve_component_metadata,
)

from .component_authority import (
    ComponentAuthorityError,
    KNOWN_COMPONENT_IDS,
    PER_COMPONENT_YAML,
    append_unknown_record,
    is_recognised_field,
    load_unknowns,
    mark_component_unknown,
    resolve_component_field,
)

from .dfm_dfa import (
    DfmDfaError,
    run_dfm_dfa_validation,
)

from .pcb_reconcile import (
    PcbReconcileError,
    run_pcb_reconciliation,
)

from .manufacturing_readiness import (
    run_manufacturing_release_report,
)
