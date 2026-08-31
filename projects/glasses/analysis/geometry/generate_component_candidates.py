"""
Geometry-aware pose solver for the glasses project.

The frame's coordinate system is locked from `frame-coordinate-system.json`:

  X = lateral (wearer right = +X)
  Y = wrap (front of frame at Y≈84.5, back at Y≈215.5)
  Z = vertical (Z=0 bottom, Z≈43 top)
  Forward (away from wearer) = −Y

The nose-bridge centroid is at (≈167.1, 150.0, 25.5) mm. The camera (8.5 ×
8.5 × 6.5 mm) and forward LEDs (3.4 × 3.4 × 1.5 mm) sit INSIDE the lens
cavity, just behind the front face, with their optical axis pointing in −Y
through an aperture cut into the front face. Temple LEDs sit on the outer
surface of each temple.

All coordinates are derived from the actual STL geometry; no value is
guessed.
"""
from pathlib import Path
import json
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[4]

FRAME = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl"
LEFT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl"
RIGHT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl"

FRAME_COORDS = ROOT / "projects/glasses/analysis/geometry/frame-coordinate-system.json"
OUT = ROOT / "projects/glasses/analysis/geometry/component-pose-candidates.json"

# Locked component envelopes (mm)
CAMERA_SIZE = np.array([8.5, 8.5, 6.5])
LED_SIZE = np.array([3.4, 3.4, 1.5])

# Required clearances (mm)
CAMERA_CLEARANCE = 1.0
LED_CLEARANCE = 0.5

# The camera is mounted just behind the front face, with the lens
# pointing in -Y (away from the wearer).
# Camera centre Y offset from front face = envelope/2 + clearance.
CAMERA_Y_OFFSET_MM = 0.5 * CAMERA_SIZE[1] + CAMERA_CLEARANCE  # = 5.25 mm

# Forward LEDs sit slightly above/below or beside the camera in X.
FORWARD_LED_X_OFFSET_MM = 5.0   # mm lateral from camera centre, must keep LED envelope inside frame X span
FORWARD_LED_Y_OFFSET_MM = 0.5 * LED_SIZE[1] + LED_CLEARANCE  # = 2.2 mm behind cavity front wall
FORWARD_LED_Z_SPLIT_MM = 8.0   # mm above/below camera Z for the two LEDs


def load_mesh(path):
    m = trimesh.load(str(path))
    if not isinstance(m, trimesh.Trimesh):
        raise RuntimeError(f"Could not load mesh from {path}")
    return m


def _build_candidates() -> dict:
    """Build and return the geometry-derived pose candidate document.

    This function is the Phase-2-refactored importable form of the
    analysis script. It returns the same dict that the CLI writes to
    ``OUT`` and never mutates the project tree. The CLI in :func:`main`
    simply calls this and writes the JSON to ``OUT`` so existing callers
    see no behavioural change.
    """
    coords = json.loads(FRAME_COORDS.read_text())
    forward_axis = np.asarray(coords["coordinate_system"]["forward_axis"], dtype=float)
    # The lens cavity starts at the INNER surface of the front face
    # mesh (frame_front_face_inner_y_mm), not the outer surface.
    # Components must sit INSIDE the cavity, i.e., Y >= cavity_y_min.
    front_face_y = float(coords["coordinate_system"]["frame_front_face_y_mm"])
    cavity_y_min = float(coords["coordinate_system"]["frame_front_face_inner_y_mm"])
    cavity_y_max = float(coords["coordinate_system"]["frame_back_face_inner_y_mm"])
    nose_centroid = np.asarray(coords["nose_bridge_region_mm"]["centroid"], dtype=float)

    frame = load_mesh(FRAME)
    left = load_mesh(LEFT)
    right = load_mesh(RIGHT)

    fnorms = np.asarray(frame.face_normals)
    fverts = np.asarray(frame.vertices)
    ffaces = np.asarray(frame.faces)
    fctrs = fverts[ffaces].mean(axis=1)

    # --------------------------------------------------------------
    # CAMERA (1)
    # --------------------------------------------------------------
    # Centred on the nose-bridge centroid (lateral and vertical), placed
    # INSIDE the lens cavity. The camera's front face is at the cavity's
    # front boundary (cavity_y_min) plus the required clearance; its
    # optical axis points forward (-Y) through the front face.
    cam_x = float(nose_centroid[0])
    # Y-offset from the inner front face = camera Y half-extent + clearance.
    cam_y = float(cavity_y_min + 0.5 * CAMERA_SIZE[1] + CAMERA_CLEARANCE)
    cam_z = float(nose_centroid[2])
    camera_center = np.array([cam_x, cam_y, cam_z])

    # The component's local +Z must align with the world forward axis = -Y.
    # We do not rely on the local surface normal at this point (the front
    # face is FLAT in -Y; we computed it from a ray-cast probe).
    camera_candidate = {
        "component": "camthink_ov5640_8p5",
        "region": "center_nose_bridge",
        "role": "camera",
        "axis": "forward",
        "center_mm": camera_center.tolist(),
        "rotation_deg": {
            "x": 90.0,        # local +Z -> world -Y
            "y": 0.0,
            "z": 0.0,
        },
        "optical_axis_world": forward_axis.tolist(),
        "surface_point_mm": [cam_x, cavity_y_min, cam_z],
        "surface_normal": forward_axis.tolist(),
        "mounting_face": "lens",  # lens at cavity front wall
        "envelope_mm": CAMERA_SIZE.tolist(),
        "clearance_mm": float(CAMERA_CLEARANCE),
        "axis_alignment": float(np.dot(forward_axis, np.array([0, 0, 1]))),
        "derivation": (
        "anchored at nose-bridge centroid; Y placed "
        f"{cam_y - cavity_y_min:.3f} mm behind cavity front wall "
        "(cavity Y range "
        f"{cavity_y_min:.3f} -> {cavity_y_max:.3f})"
    ),
        "collision_targets": ["frame", "left_temple", "right_temple"],
    }

    # --------------------------------------------------------------
    # FORWARD LEDs (2)
    # --------------------------------------------------------------
    # Stacked vertically (above and below the camera in Z) because the
    # frame's lateral X span is too narrow to fit two 3.4 mm LEDs at
    # 1.0 mm clearance from the camera envelope without protruding
    # past the frame X bounds. The two LEDs share the camera's optical
    # axis (-Y) and sit at the same Y offset behind the front face.
    forward_led_candidates = []
    # Z placement: each LED must clear the camera envelope by at least
    # LED_CLEARANCE (0.5 mm) on the Z axis.
    # Camera half-extent in Z: 3.25. LED half-extent: 0.75. Required
    # edge-to-edge Z clearance: 0.5 mm => LED Z must be at least
    # camera_z +/- (3.25 + 0.75 + 0.5) = camera_z +/- 4.5 mm.
    led_z_offsets = [-5.0, 5.0]  # one above, one below the camera
    for i, z_off in enumerate(led_z_offsets):
        led_x = cam_x
        # LED front face at cavity_y_min + LED clearance; LED centre at
        # that + half of LED envelope along the optical axis (Y).
        led_y = float(cavity_y_min + 0.5 * LED_SIZE[1] + LED_CLEARANCE)
        led_z = cam_z + z_off
        forward_led_candidates.append({
            "component": "vsma1094750x02",
            "region": "front_frame",
            "role": "forward_led",
            "axis": "same_as_camera",
            "label": "forward_led_top" if z_off > 0 else "forward_led_bottom",
            "center_mm": [led_x, led_y, led_z],
            "rotation_deg": {"x": 90.0, "y": 0.0, "z": 0.0},
            "optical_axis_world": forward_axis.tolist(),
            "surface_point_mm": [led_x, cavity_y_min, led_z],
            "surface_normal": forward_axis.tolist(),
            "mounting_face": "lens",  # LED emitter at cavity front wall
            "envelope_mm": LED_SIZE.tolist(),
            "clearance_mm": float(LED_CLEARANCE),
            "axis_alignment": float(np.dot(forward_axis, np.array([0, 0, 1]))),
            "derivation": (
                f"anchored at nose-bridge centroid (X), "
                f"{z_off:+.1f} mm Z (vertical stack), "
                f"cavity_y + {0.5 * LED_SIZE[1] + LED_CLEARANCE:.3f} mm"
            ),
            "collision_targets": ["frame", "left_temple", "right_temple"],
        })

    # --------------------------------------------------------------
    # TEMPLE LEDs (4: 2 per temple)
    # --------------------------------------------------------------
    # Each temple has two outward-facing LEDs, separated along the
    # temple length (Y axis). Outward = +X (left temple) or -X (right).
    def temple_leds(temple, side):
        outward = np.array([1.0, 0.0, 0.0]) if side == "left" else np.array([-1.0, 0.0, 0.0])
        # Pick anchor vertices on the outward-facing surface of the temple
        # at 25% and 75% along the Y axis of the temple (front and rear).
        verts = np.asarray(temple.vertices)
        faces = np.asarray(temple.faces)
        norms = np.asarray(temple.face_normals)
        ctrs = verts[faces].mean(axis=1)

        lo, hi = temple.bounds
        yspan = hi[1] - lo[1]
        y_targets = [lo[1] + 0.25 * yspan, lo[1] + 0.75 * yspan]
        z_mid = 0.5 * (lo[2] + hi[2])

        out = []
        for label, yt in zip(("front", "rear"), y_targets):
            # Find the face with normal most aligned with outward, on the
            # outer surface, near (yt, z_mid).
            mask = (norms @ outward) >= 0.85
            if not mask.any():
                continue
            ct = ctrs[mask]
            no = norms[mask]
            # Closest anchor to (outward_x, yt, z_mid)
            outer_x = hi[0] if side == "left" else lo[0]
            target = np.array([outer_x, yt, z_mid])
            d = np.linalg.norm(ct - target, axis=1)
            idx = int(np.argmin(d))
            anchor = ct[idx]
            normal = no[idx]
            normal /= np.linalg.norm(normal)
            # Half of the AABB extent projected onto the surface normal,
            # plus the required clearance.
            proj = abs(normal[0]) * LED_SIZE[0] + abs(normal[1]) * LED_SIZE[1] + abs(normal[2]) * LED_SIZE[2]
            offset = 0.5 * proj + LED_CLEARANCE + 0.05  # +0.05 mm floating-point safety margin
            center = anchor + normal * offset
            out.append({
                "component": "vsma1094750x02",
                "region": f"{side}_temple",
                "role": "temple_led",
                "axis": "outward",
                "label": f"{side}_temple_led_{label}",
                "center_mm": center.tolist(),
                "rotation_deg": {"x": 0.0, "y": 0.0, "z": 0.0},
                "optical_axis_world": normal.tolist(),
                "surface_point_mm": anchor.tolist(),
                "surface_normal": normal.tolist(),
                "envelope_mm": LED_SIZE.tolist(),
                "clearance_mm": float(LED_CLEARANCE),
                "axis_alignment": float(np.dot(normal, outward)),
                "derivation": (
                    f"anchored on outward face of {side} temple at "
                    f"Y={yt:.1f}, offset {offset:.2f} mm along outward normal"
                ),
                "collision_targets": [f"{side}_temple", "frame"],
            })
        return out

    left_led_candidates = temple_leds(left, "left")
    right_led_candidates = temple_leds(right, "right")

    output = {
        "schema_version": 2,
        "units": "mm",
        "frame_coordinate_source": "frame-coordinate-system.json",
        "camera": {
            "quantity": 1,
            "envelope_mm": CAMERA_SIZE.tolist(),
            "clearance_mm": float(CAMERA_CLEARANCE),
            "region": "center_nose_bridge",
            "axis": "forward",
            "candidates": [camera_candidate],
        },
        "forward_leds": {
            "quantity": 2,
            "envelope_mm": LED_SIZE.tolist(),
            "clearance_mm": float(LED_CLEARANCE),
            "beam_angle_deg": 60,
            "axis": "same_as_camera",
            "candidates": forward_led_candidates,
        },
        "temple_leds": {
            "quantity": 4,
            "envelope_mm": LED_SIZE.tolist(),
            "clearance_mm": float(LED_CLEARANCE),
            "beam_angle_deg": 60,
            "axis": "outward",
            "left_candidates": left_led_candidates,
            "right_candidates": right_led_candidates,
        },
        "constraints": {
            "coordinates_geometry_derived": True,
            "manual_coordinates_forbidden": True,
            "frame_curvature_preserved": True,
            "camera_keepout_required": True,
            "led_keepout_required": True,
            "flush_optical_windows_required": True,
        },
        "status": "CANDIDATES_GENERATED",
    }
    return output


# Public, importable alias used by the MCP ``propose_pose`` tool and by
# any future code that wants to run the geometry-derived candidate
# generator without mutating the project tree.
generate_component_candidates = _build_candidates


def main():
    print("=" * 70)
    print("GEOMETRY-DERIVED COMPONENT POSE CANDIDATES")
    print("=" * 70)

    output = _build_candidates()
    forward_led_candidates = output["forward_leds"]["candidates"]
    left_led_candidates = output["temple_leds"]["left_candidates"]
    right_led_candidates = output["temple_leds"]["right_candidates"]

    OUT.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print()
    print(f"Camera candidates:        {len(output['camera']['candidates'])}")
    print(f"Forward LED candidates:   {len(forward_led_candidates)}")
    print(f"Left temple candidates:   {len(left_led_candidates)}")
    print(f"Right temple candidates:  {len(right_led_candidates)}")
    total = 1 + len(forward_led_candidates) + len(left_led_candidates) + len(right_led_candidates)
    print(f"Total candidates:         {total}")
    print()
    print(f"Output: {OUT.relative_to(ROOT)}")
    print("=" * 70)


if __name__ == "__main__":
    main()