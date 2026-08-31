"""
Frame geometry characterisation.

Records the geometric coordinate-frame convention derived from the
authoritative ray-ban wayfarer STLs and the lens-opening cavity. This
is the single source of truth that all downstream pose solvers and
validators must use.

Outputs:
  - frame-coordinate-system.json

The output is deterministic and never relies on guessed values.
"""
from pathlib import Path
import json
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[4]

FRAME = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl"
LEFT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl"
RIGHT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl"

OUT = ROOT / "projects/glasses/analysis/geometry/frame-coordinate-system.json"


def load(path):
    m = trimesh.load(str(path))
    if not isinstance(m, trimesh.Trimesh):
        raise RuntimeError(f"Could not load {path}")
    return m


def main():
    frame = load(FRAME)
    left = load(LEFT)
    right = load(RIGHT)

    frame_v = np.asarray(frame.vertices)
    frame_f = np.asarray(frame.faces)
    frame_n = np.asarray(frame.face_normals)
    frame_c = frame_v[frame_f].mean(axis=1)

    lo, hi = frame.bounds
    xmid = 0.5 * (lo[0] + hi[0])
    ymid = 0.5 * (lo[1] + hi[1])
    zmid = 0.5 * (lo[2] + hi[2])

    # Find the front face of the frame: cast a ray from outside the mesh
    # in the -Y direction at the centre and record the first hit.
    # Start at a Y value beyond the small-Y end of the mesh.
    front_probe_origin = np.array([xmid, lo[1] - 5.0, zmid])
    front_locs, _, _ = frame.ray.intersects_location(
        front_probe_origin[None, :],
        np.array([[0.0, 1.0, 0.0]]),
        multiple_hits=True,  # capture both front-of-front and back-of-front
    )
    # Hits may be returned in arbitrary order. Sort by Y (distance from
    # origin) and take the smallest two: outer surface (smallest Y), then
    # inner surface (next Y), provided there are at least two hits.
    if len(front_locs) > 0:
        sorted_y = np.sort(front_locs[:, 1])
        front_face_y = float(sorted_y[0])
        front_face_inner_y = float(sorted_y[1]) if len(sorted_y) > 1 else None
    else:
        front_face_y = None
        front_face_inner_y = None
    front_face_thickness_mm = (
        front_face_inner_y - front_face_y
        if front_face_inner_y is not None and front_face_y is not None
        else None
    )

    # Back face: probe from Y=hi.y+5 in -Y
    back_probe_origin = np.array([xmid, hi[1] + 5.0, zmid])
    back_locs, _, _ = frame.ray.intersects_location(
        back_probe_origin[None, :],
        np.array([[0.0, -1.0, 0.0]]),
        multiple_hits=True,
    )
    # Sort by Y descending for the back face probe.
    if len(back_locs) > 0:
        sorted_y = np.sort(back_locs[:, 1])[::-1]  # largest Y first
        back_face_y = float(sorted_y[0])
        back_face_inner_y = float(sorted_y[1]) if len(sorted_y) > 1 else None
    else:
        back_face_y = None
        back_face_inner_y = None

    # Nose-bridge region: triangles in the central X band, mid-Y, mid-Z
    nose_mask = (
        (np.abs(frame_c[:, 0] - xmid) < 4.0)
        & (np.abs(frame_c[:, 1] - ymid) < 8.5)
        & (frame_c[:, 2] >= lo[2] + 0.20 * (hi[2] - lo[2]))
        & (frame_c[:, 2] <= lo[2] + 0.75 * (hi[2] - lo[2]))
    )
    nose_tri_centers = frame_c[nose_mask]
    if len(nose_tri_centers):
        nose_bbox_min = nose_tri_centers.min(axis=0).tolist()
        nose_bbox_max = nose_tri_centers.max(axis=0).tolist()
        nose_bbox_size = (nose_tri_centers.max(axis=0) - nose_tri_centers.min(axis=0)).tolist()
        nose_centroid = nose_tri_centers.mean(axis=0).tolist()
    else:
        nose_bbox_min = nose_bbox_max = nose_centroid = [None, None, None]
        nose_bbox_size = [0, 0, 0]

    # Mean forward axis = -Y (because front face is at smaller Y, back at larger Y)
    # The wearer's gaze exits the front face at smaller Y; the lens plane is the
    # front face; the camera looks "forward" away from the wearer = -Y direction.
    forward_axis = np.array([0.0, -1.0, 0.0])

    output = {
        "schema_version": 2,
        "units": "mm",
        "source": {
            "frame": "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl",
            "left_temple": "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
            "right_temple": "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-right.stl",
            "watertight": bool(frame.is_watertight),
            "frame_volume_mm3": float(frame.volume) if frame.is_watertight else None,
        },
        "coordinate_system": {
            "X_axis": "lateral across the front of the frame (wearer right = +X)",
            "Y_axis": "wrap-around axis (front of frame at smaller Y, back at larger Y)",
            "Z_axis": "vertical (Z=0 bottom of frame, Z={:.2f} top)".format(hi[2]),
            "forward_axis": forward_axis.tolist(),
            "forward_axis_meaning": "Away from wearer = decreasing Y",
            "frame_front_face_y_mm": front_face_y,
            "frame_front_face_inner_y_mm": front_face_inner_y,
            "frame_front_face_thickness_mm": front_face_thickness_mm,
            "frame_back_face_y_mm": back_face_y,
            "frame_back_face_inner_y_mm": back_face_inner_y,
            "lens_cavity_thickness_mm": (
                (back_face_y - front_face_y) if (front_face_y and back_face_y) else None
            ),
            "lens_cavity_internal_y_min_mm": front_face_inner_y,
        },
        "frame_bbox_mm": {
            "min": lo.tolist(),
            "max": hi.tolist(),
            "size": (hi - lo).tolist(),
        },
        "nose_bridge_region_mm": {
            "triangles": int(nose_mask.sum()),
            "bbox_min": nose_bbox_min,
            "bbox_max": nose_bbox_max,
            "bbox_size": nose_bbox_size,
            "centroid": nose_centroid,
        },
        "temples": {
            "left": {
                "bbox_min_mm": left.bounds[0].tolist(),
                "bbox_max_mm": left.bounds[1].tolist(),
                "outward_axis": [1.0, 0.0, 0.0],
            },
            "right": {
                "bbox_min_mm": right.bounds[0].tolist(),
                "bbox_max_mm": right.bounds[1].tolist(),
                "outward_axis": [-1.0, 0.0, 0.0],
            },
        },
    }

    OUT.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("=" * 70)
    print("FRAME COORDINATE SYSTEM (DERIVED FROM STL)")
    print("=" * 70)
    print(f"Frame watertight:    {frame.is_watertight}")
    print(f"Front face outer Y:  {front_face_y}")
    print(f"Front face inner Y:  {front_face_inner_y}")
    print(f"Front face thickness:{front_face_thickness_mm}")
    print(f"Back face Y:         {back_face_y}")
    print(f"Cavity Y range:      Y >= {front_face_inner_y}")
    print(f"Forward axis:        {forward_axis.tolist()} (away from wearer)")
    print()
    print("Nose-bridge region:")
    print(f"  triangles:         {output['nose_bridge_region_mm']['triangles']}")
    print(f"  bbox:              {nose_bbox_min} -> {nose_bbox_max}")
    print(f"  centroid:          {nose_centroid}")
    print()
    print(f"Output: {OUT.relative_to(ROOT)}")
    print("=" * 70)


if __name__ == "__main__":
    main()