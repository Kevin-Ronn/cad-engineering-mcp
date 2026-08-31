from pathlib import Path
import json
import numpy as np
from stl import mesh

ROOT = Path(__file__).resolve().parents[4]

FILES = {
    "main_frame":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl",
    "left_temple":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
    "right_temple":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl",
}


def analyse(path):
    m = mesh.Mesh.from_file(str(path))

    triangles = m.vectors
    normals = m.normals

    # Normalize normals defensively.
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-9
    normals = normals[valid] / lengths[valid, None]
    triangles = triangles[valid]

    centers = triangles.mean(axis=1)

    # Surface statistics by dominant normal direction.
    axes = {
        "x": np.abs(normals[:, 0]),
        "y": np.abs(normals[:, 1]),
        "z": np.abs(normals[:, 2]),
    }

    dominant = {
        axis: {
            "triangle_count": int(np.sum(values > 0.90)),
            "max_alignment": float(values.max()),
        }
        for axis, values in axes.items()
    }

    return {
        "triangle_count": int(len(triangles)),
        "bbox_min_mm": triangles.reshape(-1, 3).min(axis=0).tolist(),
        "bbox_max_mm": triangles.reshape(-1, 3).max(axis=0).tolist(),
        "surface_normal_statistics": dominant,
    }


print("=" * 70)
print("MOUNTING SURFACE ANALYSIS")
print("=" * 70)

result = {}

for name, path in FILES.items():
    if not path.exists():
        raise FileNotFoundError(path)

    result[name] = analyse(path)

    print()
    print(name)
    print("-" * 70)

    stats = result[name]["surface_normal_statistics"]

    for axis, data in stats.items():
        print(
            f"{axis.upper()}-aligned surfaces: "
            f"{data['triangle_count']} triangles"
        )

print()
print("=" * 70)
print("COMPONENT MOUNTING TARGETS")
print("=" * 70)

targets = {
    "camera": {
        "component": "camthink_ov5640_8p5",
        "region": "center_nose_bridge",
        "envelope_mm": [8.5, 8.5, 6.5],
        "orientation": "forward",
        "placement": "surface_derived",
        "status": "candidate_surface_search_required",
    },

    "forward_led_left": {
        "component": "vsma1094750x02",
        "region": "front_left",
        "envelope_mm": [3.4, 3.4, 1.5],
        "orientation": "same_as_camera",
        "beam_angle_deg": 60,
        "placement": "surface_derived",
        "window": "flush_circular",
    },

    "forward_led_right": {
        "component": "vsma1094750x02",
        "region": "front_right",
        "envelope_mm": [3.4, 3.4, 1.5],
        "orientation": "same_as_camera",
        "beam_angle_deg": 60,
        "placement": "surface_derived",
        "window": "flush_circular",
    },

    "left_temple_leds": {
        "component": "vsma1094750x02",
        "quantity": 2,
        "region": "left_temple",
        "orientation": "outward",
        "beam_angle_deg": 60,
        "placement": "temple_surface_derived",
        "window": "flush_circular",
    },

    "right_temple_leds": {
        "component": "vsma1094750x02",
        "quantity": 2,
        "region": "right_temple",
        "orientation": "outward",
        "beam_angle_deg": 60,
        "placement": "temple_surface_derived",
        "window": "flush_circular",
    },
}

output = {
    "schema_version": 1,
    "units": "mm",
    "source_geometry": result,
    "mounting_targets": targets,
    "constraints": {
        "camera_keepout_required": True,
        "led_keepout_required": True,
        "camera_led_clearance_geometry_derived": True,
        "frame_curvature_preserved": True,
        "optical_axes_geometry_derived": True,
        "manual_component_coordinates_forbidden": True,
    },
}

out = (
    ROOT
    / "projects/glasses/analysis/geometry/"
    "mounting-surface-analysis.json"
)

out.write_text(
    json.dumps(output, indent=2),
    encoding="utf-8",
)

print()
print(f"Output: {out.relative_to(ROOT)}")
print()
print("STATUS: MOUNTING TARGETS DEFINED")
print("STATUS: COMPONENT COORDINATES STILL UNASSIGNED")
print("STATUS: NO COORDINATES GUESSED")
print("=" * 70)
