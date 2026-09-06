from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml


from .paths import project_root as _project_root


PROJECT_ROOT = _project_root()

ASSEMBLY_PATH = (
    PROJECT_ROOT
    / "projects"
    / "glasses"
    / "mechanical"
    / "assemblies"
    / "glasses-assembly.yaml"
)


class AssemblyError(RuntimeError):
    pass


def load_assembly() -> dict[str, Any]:
    if not ASSEMBLY_PATH.exists():
        raise AssemblyError(
            f"Assembly manifest not found: {ASSEMBLY_PATH}"
        )

    with ASSEMBLY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise AssemblyError(
            "Assembly manifest must contain a YAML mapping."
        )

    if data.get("units") != "mm":
        raise AssemblyError(
            "Assembly must use millimetres."
        )

    data.setdefault("components", {})

    return data


def save_assembly(data: dict[str, Any]) -> None:
    with ASSEMBLY_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            allow_unicode=True,
        )


def identity_matrix() -> list[list[float]]:
    return np.eye(4).tolist()


def make_transform(
    position: list[float],
    rotation_deg: list[float],
) -> list[list[float]]:

    x, y, z = np.radians(rotation_deg)

    cx, sx = np.cos(x), np.sin(x)
    cy, sy = np.cos(y), np.sin(y)
    cz, sz = np.cos(z), np.sin(z)

    rx = np.array(
        [
            [1, 0, 0],
            [0, cx, -sx],
            [0, sx, cx],
        ]
    )

    ry = np.array(
        [
            [cy, 0, sy],
            [0, 1, 0],
            [-sy, 0, cy],
        ]
    )

    rz = np.array(
        [
            [cz, -sz, 0],
            [sz, cz, 0],
            [0, 0, 1],
        ]
    )

    rotation = rz @ ry @ rx

    matrix = np.eye(4)

    matrix[:3, :3] = rotation
    matrix[:3, 3] = np.asarray(position)

    return matrix.tolist()


def add_component(
    component_id: str,
    position: list[float] | None = None,
    rotation_deg: list[float] | None = None,
    coordinate_system: str = "glasses_master",
) -> dict[str, Any]:

    assembly = load_assembly()

    if component_id in assembly["components"]:
        raise AssemblyError(
            f"Component '{component_id}' is already in assembly."
        )

    position = position or [0.0, 0.0, 0.0]
    rotation_deg = rotation_deg or [0.0, 0.0, 0.0]

    if len(position) != 3:
        raise AssemblyError(
            "Position must contain exactly 3 values."
        )

    if len(rotation_deg) != 3:
        raise AssemblyError(
            "Rotation must contain exactly 3 values."
        )

    component = {
        "coordinate_system": coordinate_system,
        "position_mm": [float(v) for v in position],
        "rotation_deg": [float(v) for v in rotation_deg],
        "transform": make_transform(
            position,
            rotation_deg,
        ),
        "interfaces": [],
        "constraints": [],
    }

    assembly["components"][component_id] = component

    save_assembly(assembly)

    return {
        "id": component_id,
        **component,
    }


def remove_component(component_id: str) -> None:
    assembly = load_assembly()

    if component_id not in assembly["components"]:
        raise AssemblyError(
            f"Component '{component_id}' is not in assembly."
        )

    del assembly["components"][component_id]

    save_assembly(assembly)


def list_assembly_components() -> list[dict[str, Any]]:
    assembly = load_assembly()

    result = []

    for component_id, component in assembly["components"].items():
        result.append(
            {
                "id": component_id,
                "coordinate_system": component[
                    "coordinate_system"
                ],
                "position_mm": component[
                    "position_mm"
                ],
                "rotation_deg": component[
                    "rotation_deg"
                ],
            }
        )

    return result


def get_component_transform(
    component_id: str,
) -> np.ndarray:

    assembly = load_assembly()

    if component_id not in assembly["components"]:
        raise AssemblyError(
            f"Component '{component_id}' is not in assembly."
        )

    return np.asarray(
        assembly["components"][component_id]["transform"],
        dtype=float,
    )


def transform_point(
    component_id: str,
    point_mm: list[float],
) -> list[float]:

    if len(point_mm) != 3:
        raise AssemblyError(
            "Point must contain exactly 3 values."
        )

    transform = get_component_transform(
        component_id
    )

    point = np.array(
        [*point_mm, 1.0],
        dtype=float,
    )

    result = transform @ point

    return [
        float(result[0]),
        float(result[1]),
        float(result[2]),
    ]
