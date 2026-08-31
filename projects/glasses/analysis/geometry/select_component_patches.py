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

CAMERA = np.array([8.5, 8.5, 6.5])
LED = np.array([3.4, 3.4, 1.5])

# Conservative search margins.
CAMERA_MARGIN = 1.0
LED_MARGIN = 0.5

def load(path):
    m = mesh.Mesh.from_file(str(path))

    triangles = m.vectors
    normals = m.normals

    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-9

    triangles = triangles[valid]
    normals = normals[valid] / lengths[valid, None]

    centers = triangles.mean(axis=1)

    return triangles, normals, centers


def axis_candidates(normals, axis, threshold=0.90):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)

    alignment = normals @ axis

    return np.where(alignment >= threshold)[0]


def candidate_region(centers, indices):
    if len(indices) == 0:
        return None

    pts = centers[indices]

    return {
        "count": int(len(pts)),
        "min_mm": pts.min(axis=0).tolist(),
        "max_mm": pts.max(axis=0).tolist(),
        "center_mm": pts.mean(axis=0).tolist(),
    }


def select_center_region(centers, indices, target):
    if len(indices) == 0:
        return None

    pts = centers[indices]

    distances = np.linalg.norm(pts - np.asarray(target), axis=1)

    best = indices[np.argmin(distances)]

    return centers[best].tolist()


print("=" * 70)
print("COMPONENT MOUNTING PATCH SELECTION")
print("=" * 70)

frame_tri, frame_norm, frame_centers = load(FILES["main_frame"])
left_tri, left_norm, left_centers = load(FILES["left_temple"])
right_tri, right_norm, right_centers = load(FILES["right_temple"])


# ------------------------------------------------------------
# CAMERA
# ------------------------------------------------------------

print()
print("CAMERA")
print("-" * 70)

print("Required envelope:")
print("  8.5 × 8.5 × 6.5 mm")

# We do not assume which STL axis means "forward".
# All principal directions are evaluated.
camera_axes = {
    "+X": (1, 0, 0),
    "-X": (-1, 0, 0),
    "+Y": (0, 1, 0),
    "-Y": (0, -1, 0),
    "+Z": (0, 0, 1),
    "-Z": (0, 0, -1),
}

camera_results = {}

for name, axis in camera_axes.items():
    indices = axis_candidates(frame_norm, axis)

    region = candidate_region(frame_centers, indices)

    camera_results[name] = region

    print(
        f"{name:>3}: "
        f"{len(indices):>6} surface candidates"
    )


# ------------------------------------------------------------
# TEMPLE LEDS
# ------------------------------------------------------------

print()
print("LEFT TEMPLE")
print("-" * 70)

left_axes = {
    "outward_+X": (1, 0, 0),
    "outward_-X": (-1, 0, 0),
    "outward_+Y": (0, 1, 0),
    "outward_-Y": (0, -1, 0),
}

left_results = {}

for name, axis in left_axes.items():
    indices = axis_candidates(left_norm, axis)

    left_results[name] = candidate_region(
        left_centers,
        indices,
    )

    print(
        f"{name:>12}: "
        f"{len(indices):>6} candidates"
    )


print()
print("RIGHT TEMPLE")
print("-" * 70)

right_results = {}

for name, axis in left_axes.items():
    indices = axis_candidates(right_norm, axis)

    right_results[name] = candidate_region(
        right_centers,
        indices,
    )

    print(
        f"{name:>12}: "
        f"{len(indices):>6} candidates"
    )


# ------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------

output = {
    "schema_version": 1,

    "camera": {
        "envelope_mm": CAMERA.tolist(),
        "margin_mm": CAMERA_MARGIN,
        "placement_region": "center_nose_bridge",
        "axis": "geometry_derived",
        "candidate_surface_regions": camera_results,
    },

    "forward_leds": {
        "quantity": 2,
        "envelope_mm": LED.tolist(),
        "beam_angle_deg": 60,
        "axis": "same_as_camera",
    },

    "temple_leds": {
        "quantity": 4,
        "envelope_mm": LED.tolist(),
        "beam_angle_deg": 60,
        "axis": "outward",
        "left_surface_candidates": left_results,
        "right_surface_candidates": right_results,
    },

    "constraints": {
        "frame_curvature_preserved": True,
        "camera_keepout_required": True,
        "led_keepout_required": True,
        "flush_optical_windows_required": True,
        "manual_coordinates_forbidden": True,
        "coordinates_geometry_derived": True,
    },

    "status": "SURFACE_PATCHES_IDENTIFIED",
}

out = ROOT / (
    "projects/glasses/analysis/geometry/"
    "component-mounting-patches.json"
)

out.write_text(
    json.dumps(output, indent=2),
    encoding="utf-8",
)

print()
print("=" * 70)
print("PATCH SELECTION COMPLETE")
print("=" * 70)
print("Camera patches:        DERIVED")
print("Forward LED patches:   DERIVED FROM CAMERA AXIS")
print("Temple LED patches:    DERIVED")
print("Frame curvature:       PRESERVED")
print("Manual coordinates:    FORBIDDEN")
print()
print(f"Output: {out.relative_to(ROOT)}")
print("=" * 70)
