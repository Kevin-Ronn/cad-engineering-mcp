from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path.home() / "cad-engineering-mcp"

WINDOW_SYSTEM_PATH = (
    PROJECT_ROOT
    / "projects"
    / "glasses"
    / "mechanical"
    / "interfaces"
    / "ir-optical-window-system.yaml"
)

WINDOW_GEOMETRY_PATH = (
    PROJECT_ROOT
    / "projects"
    / "glasses"
    / "mechanical"
    / "interfaces"
    / "ir-optical-window-geometry.yaml"
)


class OpticalWindowError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise OpticalWindowError(f"Missing optical-window file: {path}")

    data = yaml.safe_load(path.read_text())

    if not isinstance(data, dict):
        raise OpticalWindowError(f"Invalid YAML root: {path}")

    return data


def load_window_system() -> dict[str, Any]:
    return _load(WINDOW_SYSTEM_PATH)


def load_window_geometry() -> dict[str, Any]:
    return _load(WINDOW_GEOMETRY_PATH)


def list_window_placements() -> list[dict[str, Any]]:
    data = load_window_system()

    placements = data["interface"]["placements"]

    result = []

    for name, placement in placements.items():
        item = dict(placement)
        item["id"] = name
        result.append(item)

    return result


def validate_window_system() -> dict[str, Any]:
    system = load_window_system()
    geometry = load_window_geometry()

    interface = system["interface"]
    mechanical = interface["mechanical_interface"]

    if mechanical["shape"] != "circular":
        raise OpticalWindowError(
            "IR optical windows must be circular."
        )

    if mechanical["mounting"] if "mounting" in mechanical else False:
        pass

    surface = geometry["surface_relationship"]

    if surface["frame_exterior_z"] != 0.0:
        raise OpticalWindowError(
            "Frame exterior reference must be zero."
        )

    if surface["window_exterior_z"] != 0.0:
        raise OpticalWindowError(
            "Window must be flush with frame exterior."
        )

    if surface["condition"] != "coincident":
        raise OpticalWindowError(
            "Window/frame surfaces must be coincident."
        )

    placements = interface["placements"]

    if len(placements) != 6:
        raise OpticalWindowError(
            f"Expected 6 optical-window placements, "
            f"found {len(placements)}."
        )

    return {
        "status": "PASS",
        "window_count": len(placements),
        "shape": mechanical["shape"],
        "mounting": interface["design_intent"]["mounting"],
        "flush": True,
        "diameter_defined": mechanical["diameter_mm"] != "TBD",
        "thickness_defined": mechanical["thickness_mm"] != "TBD",
    }
