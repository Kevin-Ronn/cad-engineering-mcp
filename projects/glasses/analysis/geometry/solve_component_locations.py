from pathlib import Path
import json
import numpy as np
from stl import mesh

ROOT = Path(__file__).resolve().parents[4]

FRAME = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl"
LEFT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl"
RIGHT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl"

CAMERA_SIZE = np.array([8.5, 8.5, 6.5])
LED_SIZE = np.array([3.4, 3.4, 1.5])


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


def surface_summary(triangles, normals):
    """
    Return actual STL-derived surface information.

    No component coordinates are generated here.
    """
    bbox_min = triangles.reshape(-1, 3).min(axis=0)
    bbox_max = triangles.reshape(-1, 3).max(axis=0)

    return {
        "bbox_min_mm": bbox_min.tolist(),
        "bbox_max_mm": bbox_max.tolist(),
        "triangle_count": int(len(triangles)),
        "mean_normal": normals.mean(axis=0).tolist(),
    }


def candidate_surfaces(triangles, normals, axis, tolerance=0.15):
    """
    Find triangles whose normals approximately face the requested axis.

    axis:
      +X, -X, +Y, -Y, +Z, -Z
    """
    direction = np.array(axis, dtype=float)
    direction /= np.linalg.norm(direction)

    alignment = normals @ direction

    mask = alignment >= (1.0 - tolerance)

    return {
        "count": int(mask.sum()),
        "mean_alignment": (
            float(alignment[mask].mean())
            if mask.any()
            else None
        ),
        "max_alignment": (
            float(alignment[mask].max())
            if mask.any()
            else None
        ),
    }


print("=" * 70)
print("COMPONENT LOCATION SOLVER")
print("=" * 70)

frame_tri, frame_norm, frame_centers = load(FRAME)
left_tri, left_norm, left_centers = load(LEFT)
right_tri, right_norm, right_centers = load(RIGHT)

print()
print("SOURCE GEOMETRY")
print("-" * 70)

for name, tri, norm in (
    ("main_frame", frame_tri, frame_norm),
    ("left_temple", left_tri, left_norm),
    ("right_temple", right_tri, right_norm),
):
    summary = surface_summary(tri, norm)

    print(
        f"{name}: "
        f"{summary['triangle_count']} triangles"
    )

print()
print("CAMERA TARGET")
print("-" * 70)
print("Envelope: 8.5 × 8.5 × 6.5 mm")
print("Region: center_nose_bridge")
print("Axis: forward")
print("Mount: main_frame")
print("Status: surface candidate search")

# The exact forward direction depends on the STL coordinate convention.
# We therefore inspect all principal directions rather than assuming one.
camera_surface_search = {}

for label, axis in {
    "+X": (1, 0, 0),
    "-X": (-1, 0, 0),
    "+Y": (0, 1, 0),
    "-Y": (0, -1, 0),
    "+Z": (0, 0, 1),
    "-Z": (0, 0, -1),
}.items():
    camera_surface_search[label] = candidate_surfaces(
        frame_tri,
        frame_norm,
        axis,
    )

print()
print("CAMERA SURFACE ORIENTATION SEARCH")
for direction, result in camera_surface_search.items():
    print(
        f"{direction:>3}: "
        f"{result['count']:>6} candidate triangles"
    )

print()
print("TEMPLE LED TARGETS")
print("-" * 70)

for name, tri, norm in (
    ("left_temple", left_tri, left_norm),
    ("right_temple", right_tri, right_norm),
):
    print()
    print(name)

    for label, axis in {
        "+X": (1, 0, 0),
        "-X": (-1, 0, 0),
        "+Y": (0, 1, 0),
        "-Y": (0, -1, 0),
        "+Z": (0, 0, 1),
        "-Z": (0, 0, -1),
    }.items():
        result = candidate_surfaces(tri, norm, axis)

        print(
            f"  {label:>3}: "
            f"{result['count']:>6} candidate triangles"
        )

print()
print("=" * 70)
print("SOLVER RESULT")
print("=" * 70)
print("Camera envelope:        LOCKED")
print("LED envelope:           LOCKED")
print("Frame geometry:         AUTHORITATIVE")
print("Surface candidates:     DERIVED")
print("Optical axes:           NOT YET ASSIGNED")
print("Component coordinates:  NOT YET ASSIGNED")
print("Manual coordinates:     FORBIDDEN")
print()
print("Next stage: select valid surface patches and")
print("calculate collision-free component poses.")
print("=" * 70)

output = {
    "schema_version": 1,
    "camera_envelope_mm": CAMERA_SIZE.tolist(),
    "led_envelope_mm": LED_SIZE.tolist(),
    "camera_surface_search": camera_surface_search,
    "source_geometry": {
        "main_frame": str(FRAME.relative_to(ROOT)),
        "left_temple": str(LEFT.relative_to(ROOT)),
        "right_temple": str(RIGHT.relative_to(ROOT)),
    },
    "status": {
        "surface_candidates_derived": True,
        "component_coordinates_assigned": False,
        "manual_coordinates_forbidden": True,
    },
}

out = ROOT / "projects/glasses/analysis/geometry/component-location-search.json"
out.write_text(json.dumps(output, indent=2), encoding="utf-8")

print()
print(f"Saved: {out.relative_to(ROOT)}")
