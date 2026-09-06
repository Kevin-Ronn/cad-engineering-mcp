from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


from .paths import project_root as _project_root


PROJECT_ROOT = _project_root()

STRUCTURAL_POLICY = (
    PROJECT_ROOT
    / "projects"
    / "glasses"
    / "mechanical"
    / "main-frame"
    / "structural-policy.yaml"
)

RIB_SYSTEM = (
    PROJECT_ROOT
    / "projects"
    / "glasses"
    / "mechanical"
    / "ribs"
    / "rib-system.yaml"
)


class StructuralDesignError(RuntimeError):
    pass


def load_structural_policy() -> dict[str, Any]:
    if not STRUCTURAL_POLICY.exists():
        raise StructuralDesignError(
            f"Structural policy not found: {STRUCTURAL_POLICY}"
        )

    with STRUCTURAL_POLICY.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise StructuralDesignError(
            "Structural policy must contain a YAML mapping."
        )

    return data


def load_rib_system() -> dict[str, Any]:
    if not RIB_SYSTEM.exists():
        raise StructuralDesignError(
            f"Rib system not found: {RIB_SYSTEM}"
        )

    with RIB_SYSTEM.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise StructuralDesignError(
            "Rib system must contain a YAML mapping."
        )

    return data


def structural_interfaces() -> list[str]:
    policy = load_structural_policy()

    return list(
        policy.get("load_interfaces", [])
    )


def rib_rule(interface: str) -> dict[str, Any]:
    policy = load_structural_policy()

    rules = policy.get("rib_rules", {})

    if interface not in rules:
        raise StructuralDesignError(
            f"No rib rule defined for interface: {interface}"
        )

    return dict(rules[interface])


def validate_structural_policy() -> dict[str, Any]:
    policy = load_structural_policy()
    ribs = load_rib_system()

    required = [
        "minimum_structural_mass",
        "minimum_wall_thickness",
        "maximum_required_stiffness",
        "maintain_serviceability",
    ]

    objectives = policy.get(
        "design_intent", {}
    ).get("objective", [])

    missing = [
        item for item in required
        if item not in objectives
    ]

    if missing:
        raise StructuralDesignError(
            "Missing structural objectives: "
            + ", ".join(missing)
        )

    if ribs.get("rib_generation", {}).get(
        "exclusions"
    ) is None:
        raise StructuralDesignError(
            "Rib keep-out exclusions are missing."
        )

    return {
        "status": "PASS",
        "interfaces": structural_interfaces(),
        "rib_zones": len(
            ribs.get("rib_zones", {})
        ),
    }
