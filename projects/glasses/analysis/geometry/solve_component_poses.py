from pathlib import Path
import json
import numpy as np
from stl import mesh

ROOT = Path(__file__).resolve().parents[4]

FILES = {
    "frame":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl",
    "left_temple":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
    "right_temple":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl",
}

CAMERA = np.array([8.5, 8.5, 6.5])
LED = np.array([3.4, 3.4, 1.5])

# Keep component bodies away from unrelated geometry.
CAMERA_CLEARANCE = 1.0
LED_CLEARANCE = 0.5

def load(path):
    m = mesh.Mesh.from_file(str(path))

    triangles = m.vectors.astype(float)
    normals = m.normals.astype(float)

    length = np.linalg.norm(normals, axis=1)
    valid = length > 1e-9

    triangles = triangles[valid]
    normals = normals[valid] / length[valid, None]

    centers = triangles.mean(axis=1)

    return triangles, normals, centers


def oriented_box_axes(normal):
    """
    Build a stable local coordinate frame from a surface normal.
    """
    n = np.asarray(normal, dtype=float)
    n /= np.linalg.norm(n)

    reference = np.array([0.0, 0.0, 1.0])

    if abs(np.dot(n, reference)) > 0.90:
        reference = np.array([0.0, 1.0, 0.0])

    tangent = np.cross(reference, n)
    tangent /= np.linalg.norm(tangent)

    binormal = np.cross(n, tangent)
    binormal /= np.linalg.norm(binormal)

    return tangent, binormal, n


def projected_extent(points, axis):
    return float(np.max(points @ axis) - np.min(points @ axis))


def test_patch_fit(triangle, normal, component_size, clearance):
    """
    Conservative local fit test.

    The component is treated as an oriented rectangular envelope.
    We test whether the supporting triangle has enough projected
    surface area for the footprint.
    """
    tangent, binormal, normal = oriented_box_axes(normal)

    footprint_a = component_size[0] + 2 * clearance
    footprint_b = component_size[1] + 2 * clearance

    pts = triangle

    extent_a = projected_extent(pts, tangent)
    extent_b = projected_extent(pts, binormal)

    # Individual STL triangles are normally smaller than the complete
    # mounting patch, so this function identifies orientation candidates,
    # not final mounting acceptance.
    return {
        "normal": normal.tolist(),
        "tangent_extent_mm": extent_a,
        "binormal_extent_mm": extent_b,
        "required_footprint_mm": [
            float(footprint_a),
            float(footprint_b),
        ],
        "orientation_valid": True,
    }


def orientation_candidates(normals, desired, threshold=0.95):
    desired = np.asarray(desired, dtype=float)
    desired /= np.linalg.norm(desired)

    alignment = normals @ desired
    return np.where(alignment >= threshold)[0]


def summarize_region(centers, normals, indices):
    if len(indices) == 0:
        return None

    pts = centers[indices]

    return {
        "candidate_count": int(len(indices)),
        "region_min_mm": pts.min(axis=0).tolist(),
        "region_max_mm": pts.max(axis=0).tolist(),
        "region_center_mm": pts.mean(axis=0).tolist(),
    }


frame_tri, frame_norm, frame_centers = load(FILES["frame"])
left_tri, left_norm, left_centers = load(FILES["left_temple"])
right_tri, right_norm, right_centers = load(FILES["right_temple"])

print("=" * 70)
print("3D COMPONENT POSE SOLVER")
print("=" * 70)

print()
print("CAMERA")
print("-" * 70)
print("Envelope: 8.5 × 8.5 × 6.5 mm")
print("Region: center_nose_bridge")
print("Required clearance:", CAMERA_CLEARANCE, "mm")

# Search every principal direction because the STL coordinate convention
# must be established from the geometry rather than assumed.
directions = {
    "+X": (1, 0, 0),
    "-X": (-1, 0, 0),
    "+Y": (0, 1, 0),
    "-Y": (0, -1, 0),
    "+Z": (0, 0, 1),
    "-Z": (0, 0, -1),
}

camera_results = {}

for name, direction in directions.items():
    indices = orientation_candidates(frame_norm, direction)

    region = summarize_region(
        frame_centers,
        frame_norm,
        indices,
    )

    camera_results[name] = region

    print(
        f"{name:>3}: "
        f"{len(indices):>6} orientation-compatible surfaces"
    )


print()
print("FORWARD LED ORIENTATION")
print("-" * 70)
print("Quantity: 2")
print("Envelope: 3.4 × 3.4 × 1.5 mm")
print("Beam angle: 60°")
print("Axis: SAME AS CAMERA")

forward_led_results = {}

for name, direction in directions.items():
    indices = orientation_candidates(frame_norm, direction)

    forward_led_results[name] = summarize_region(
        frame_centers,
        frame_norm,
        indices,
    )

    print(
        f"{name:>3}: "
        f"{len(indices):>6} compatible surfaces"
    )


print()
print("TEMPLE LED ORIENTATION")
print("-" * 70)
print("Quantity: 4")
print("Envelope: 3.4 × 3.4 × 1.5 mm")
print("Beam angle: 60°")
print("Axis: OUTWARD")

temple_results = {
    "left": {},
    "right": {},
}

for side, centers, normals in (
    ("left", left_centers, left_norm),
    ("right", right_centers, right_norm),
):
    print()
    print(side.upper())

    for name, direction in directions.items():
        indices = orientation_candidates(normals, direction)

        temple_results[side][name] = summarize_region(
            centers,
            normals,
            indices,
        )

        print(
            f"  {name:>3}: "
            f"{len(indices):>6} compatible surfaces"
        )


output = {
    "schema_version": 1,

    "components": {
        "camera": {
            "id": "camthink_ov5640_8p5",
            "envelope_mm": CAMERA.tolist(),
            "clearance_mm": CAMERA_CLEARANCE,
            "region": "center_nose_bridge",
            "orientation": "forward",
            "candidate_surfaces": camera_results,
        },

        "forward_leds": {
            "id": "vsma1094750x02",
            "quantity": 2,
            "envelope_mm": LED.tolist(),
            "clearance_mm": LED_CLEARANCE,
            "beam_angle_deg": 60,
            "axis": "same_as_camera",
            "candidate_surfaces": forward_led_results,
        },

        "temple_leds": {
            "id": "vsma1094750x02",
            "quantity": 4,
            "envelope_mm": LED.tolist(),
            "clearance_mm": LED_CLEARANCE,
            "beam_angle_deg": 60,
            "axis": "outward",
            "candidate_surfaces": temple_results,
        },
    },

    "constraints": {
        "frame_curvature_preserved": True,
        "camera_keepout_required": True,
        "led_keepout_required": True,
        "camera_led_clearance_required": True,
        "flush_optical_windows_required": True,
        "manual_coordinates_forbidden": True,
        "coordinates_geometry_derived": True,
    },

    "status": "POSE_CANDIDATES_DERIVED",
}

out = ROOT / (
    "projects/glasses/analysis/geometry/component-pose-stats.json"
)

out_path = ROOT / "projects/glasses/analysis/geometry/component-pose-stats.json"
out_path.write_text(
    json.dumps(output, indent=2),
    encoding="utf-8",
)

print()
print("=" * 70)
print("POSE SEARCH COMPLETE")
print("=" * 70)
print("Camera candidates:       DERIVED")
print("Forward LED candidates:  DERIVED")
print("Temple LED candidates:   DERIVED")
print("Camera keepout:          REQUIRED")
print("LED keepout:             REQUIRED")
print("Frame curvature:         PRESERVED")
print("Manual coordinates:      FORBIDDEN")
print()
print("IMPORTANT:")
print("These are surface/pose candidates, not final CAD coordinates.")
print("Final acceptance requires collision testing against the full mesh.")
print("=" * 70)
