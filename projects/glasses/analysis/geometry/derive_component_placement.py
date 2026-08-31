from pathlib import Path
import math
import yaml

ROOT = Path(__file__).resolve().parents[4]

FRAME = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl"
LEFT_TEMPLE = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl"
RIGHT_TEMPLE = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl"

CAMERA = {
    "id": "camthink_ov5640_8p5",
    "envelope_mm": (8.5, 8.5, 6.5),
    "position": "center_nose_bridge",
    "axis": "forward",
}

LED = {
    "id": "vsma1094750x02",
    "envelope_mm": (3.4, 3.4, 1.5),
    "beam_angle_deg": 60,
}

PLACEMENTS = {
    "camera": {
        "count": 1,
        "region": "center_nose_bridge",
        "axis": "forward",
        "geometry_derived": True,
    },

    "forward_leds": {
        "count": 2,
        "regions": ["front_left", "front_right"],
        "axis": "same_as_camera",
        "beam_angle_deg": LED["beam_angle_deg"],
        "geometry_derived": True,
    },

    "temple_leds": {
        "count": 4,
        "regions": [
            "left_temple_front",
            "left_temple_rear",
            "right_temple_front",
            "right_temple_rear",
        ],
        "axis": "outward",
        "beam_angle_deg": LED["beam_angle_deg"],
        "geometry_derived": True,
    },
}


def require_geometry(path):
    if not path.exists():
        raise FileNotFoundError(f"Required geometry missing: {path}")

    if path.stat().st_size == 0:
        raise RuntimeError(f"Geometry file is empty: {path}")


def main():
    for geometry in (FRAME, LEFT_TEMPLE, RIGHT_TEMPLE):
        require_geometry(geometry)

    output = {
        "schema_version": 1,

        "source_geometry": {
            "frame": str(FRAME.relative_to(ROOT)),
            "left_temple": str(LEFT_TEMPLE.relative_to(ROOT)),
            "right_temple": str(RIGHT_TEMPLE.relative_to(ROOT)),
            "authoritative": True,
        },

        "component_geometry": {
            "camera": {
                **CAMERA,
                "placement_status": "pending_geometry_solver",
            },

            "leds": {
                "part": LED["id"],
                "envelope_mm": LED["envelope_mm"],
                "beam_angle_deg": LED["beam_angle_deg"],
                "total_quantity": 6,
                "placement_status": "pending_geometry_solver",
            },
        },

        "placement_rules": PLACEMENTS,

        "optical_windows": {
            "shape": "circular",
            "mounting": "recessed_flush",
            "surface_offset_mm": 0.0,
            "diameter": "geometry_derived",
            "thickness": "geometry_derived",
            "count": 6,
        },

        "keepouts": {
            "camera": {
                "required": True,
                "source": "locked_camera_envelope",
            },
            "led": {
                "required": True,
                "source": "locked_led_envelope",
            },
            "camera_led_clearance": {
                "required": True,
                "minimum_mm": "geometry_derived",
            },
        },

        "constraints": {
            "frame_curvature_preserved": True,
            "outer_silhouette_preserved": True,
            "uniform_thickening_forbidden": True,
            "manual_coordinates_forbidden": True,
            "coordinates_must_be_geometry_derived": True,
        },
    }

    out = (
        ROOT
        / "projects/glasses/mechanical/generated/"
        "component-placement-derived.yaml"
    )

    out.write_text(
        yaml.safe_dump(output, sort_keys=False),
        encoding="utf-8",
    )

    print("=" * 70)
    print("GEOMETRY PLACEMENT DERIVATION")
    print("=" * 70)
    print(f"Frame geometry:       {FRAME}")
    print(f"Left temple:          {LEFT_TEMPLE}")
    print(f"Right temple:         {RIGHT_TEMPLE}")
    print()
    print("Camera:")
    print("  quantity:           1")
    print("  envelope:           8.5 × 8.5 × 6.5 mm")
    print("  region:             center nose bridge")
    print("  axis:               forward")
    print()
    print("IR LEDs:")
    print("  forward:            2")
    print("  temple:             4")
    print("  total:              6")
    print("  beam angle:         60°")
    print()
    print("Optical windows:      6")
    print("Window surface:       FLUSH")
    print("Camera keepout:       REQUIRED")
    print("LED keepout:          REQUIRED")
    print("Coordinates:          GEOMETRY-DERIVED")
    print()
    print("STATUS: SPECIFICATION READY FOR GEOMETRIC SOLVER")
    print("=" * 70)


if __name__ == "__main__":
    main()
