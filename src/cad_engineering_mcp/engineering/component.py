from __future__ import annotations

from pathlib import Path
from typing import Any

from .component_geometry import measure_mesh
from .component_registry import (
    register_component,
    register_geometry,
)


def register_geometry_component(
    component_id: str,
    name: str,
    category: str,
    geometry_path: str | Path,
    *,
    source: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:

    geometry_path = Path(geometry_path).resolve()

    if not geometry_path.exists():
        raise FileNotFoundError(
            f"Geometry file not found: {geometry_path}"
        )

    measurement = measure_mesh(geometry_path)

    component = register_component(
        component_id=component_id,
        name=name,
        category=category,
        source=source,
        description=description,
    )

    return register_geometry(
        component_id=component["id"],
        geometry_path=geometry_path,
        measurement=measurement,
        source=source,
    )
