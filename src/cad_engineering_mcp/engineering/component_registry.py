from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


from .paths import project_root as _project_root


PROJECT_ROOT = _project_root()

COMPONENT_ROOT = (
    PROJECT_ROOT
    / "projects"
    / "glasses"
    / "components"
)

REGISTRY_PATH = COMPONENT_ROOT / "component-registry.yaml"


class ComponentRegistryError(RuntimeError):
    pass


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise ComponentRegistryError(
            f"Component registry not found: {REGISTRY_PATH}"
        )

    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ComponentRegistryError(
            "Component registry must contain a YAML mapping."
        )

    data.setdefault("components", {})

    return data


def save_registry(registry: dict[str, Any]) -> None:
    COMPONENT_ROOT.mkdir(parents=True, exist_ok=True)

    with REGISTRY_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            registry,
            f,
            sort_keys=False,
            allow_unicode=True,
        )


def list_components() -> list[dict[str, Any]]:
    registry = load_registry()

    return list(registry["components"].values())


def component_exists(component_id: str) -> bool:
    registry = load_registry()

    return component_id in registry["components"]


def get_component(component_id: str) -> dict[str, Any] | None:
    registry = load_registry()

    return registry["components"].get(component_id)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def register_component(
    component_id: str,
    name: str,
    category: str,
    *,
    source: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:

    if not component_id:
        raise ComponentRegistryError(
            "component_id cannot be empty."
        )

    registry = load_registry()

    if component_id in registry["components"]:
        raise ComponentRegistryError(
            f"Component already exists: {component_id}"
        )

    component: dict[str, Any] = {
        "id": component_id,
        "name": name,
        "category": category,
    }

    if source is not None:
        component["source"] = source

    if description is not None:
        component["description"] = description

    registry["components"][component_id] = component

    save_registry(registry)

    return component


def register_geometry(
    component_id: str,
    geometry_path: str | Path,
    measurement: dict[str, Any],
    *,
    source: str | None = None,
) -> dict[str, Any]:

    geometry_path = Path(geometry_path).resolve()

    if not geometry_path.exists():
        raise ComponentRegistryError(
            f"Geometry file not found: {geometry_path}"
        )

    registry = load_registry()

    component = registry["components"].get(component_id)

    if component is None:
        raise ComponentRegistryError(
            f"Component not registered: {component_id}"
        )

    component["geometry"] = {
        "file": str(
            geometry_path.relative_to(PROJECT_ROOT)
            if geometry_path.is_relative_to(PROJECT_ROOT)
            else geometry_path
        ),
        "format": geometry_path.suffix.lower().lstrip("."),
        "sha256": _sha256(geometry_path),
    }

    component["measurement"] = measurement

    if source is not None:
        component["geometry"]["source"] = source

    save_registry(registry)

    return component
