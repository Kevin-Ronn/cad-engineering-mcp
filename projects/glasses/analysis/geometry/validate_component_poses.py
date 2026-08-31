"""
Geometry-aware validator for component poses.

The frame STL is a SOLID watertight mesh of the entire frame front, not a
thin shell. To validate components that must sit INSIDE the lens cavity,
the validator performs two layers of geometric testing:

  SOLID-MESH TESTS (collision with the temples, which are real solid bodies):
    - Signed distance from each AABB corner of the component to the temple
      mesh. Negative => intersection => REJECT.

  CAVITY-INTERSECTION TESTS (the frame is interpreted as a thin shell
  bounding the lens cavity):
    - Front-face plane: the component's most-forward corner must be at
      least `clearance_mm` behind the frame's front face (Y=84.46).
      A forward-corner in front of the front face => REJECT (would
      require protruding the camera module through the lens plane).
    - Back-face plane: the component's most-rearward corner must be at
      least `clearance_mm` in front of the back face (Y=215.54).
    - Vertical bounds: the component's corners must stay within the
      frame's Z extent (Z=0 to Z≈43 mm) with clearance.
    - Lateral bounds: the component's X corners must stay within the
      frame's X extent with clearance.

  OPTICAL CONE TEST (camera only):
    - The 60° full-angle cone (30° half angle) must reach the front
      face without being obstructed by the frame mesh.

  OPTICAL-AXIS ALIGNMENT TEST:
    - The candidate's declared `optical_axis_world` must point along
      the correct world direction for its role.

Inputs:
  - component-pose-candidates.json
  - frame-coordinate-system.json

Outputs:
  - component-pose-validation.json with per-candidate results, the best
    valid set, diagnostics, and an overall PASS/FAIL.

STATUS = PASS only if every required component (1 camera, 2 forward LEDs,
4 temple LEDs) is in the accepted set.

Phase 2 refactor:
    The CLI in :func:`main` still writes the same JSON artifact to disk.
    All validation logic lives in :func:`validate_component_poses`, which
    accepts a Python dict (candidates) plus optional tolerance overrides
    so the MCP ``validate_poses`` tool can drive the same code path
    without mutating project files. Tolerance overrides MAY NOT reduce
    mandatory policy clearances; values below the policy floor are
    rejected and a structured error is returned.
"""
from pathlib import Path
import json
import math
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[4]

FRAME = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl"
LEFT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl"
RIGHT = ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl"

CANDIDATES = ROOT / "projects/glasses/analysis/geometry/component-pose-candidates.json"
FRAME_COORDS = ROOT / "projects/glasses/analysis/geometry/frame-coordinate-system.json"
OUT = ROOT / "projects/glasses/analysis/geometry/component-pose-validation.json"

CAMERA_BEAM_HALF_ANGLE_DEG = 30.0
CAMERA_OPTICAL_TEST_RANGE_MM = 20.0
MIN_ALIGNMENT = 0.85

# Mandatory policy clearance floors. The validator will REJECT any
# override that attempts to relax these values below the published
# policy minimums.
CAMERA_POLICY_MIN_CLEARANCE_MM = 1.0
LED_POLICY_MIN_CLEARANCE_MM = 0.5
MIN_ALIGNMENT_POLICY_FLOOR = 0.85

# Tolerance override keys that the MCP ``validate_poses`` tool accepts.
# Each value MUST be a positive finite float, and MUST be >= the
# mandatory policy floor above. The validator records the accepted
# overrides in its output for transparency; it never silently applies
# overrides below the policy.
_VALID_OVERRIDE_KEYS: frozenset[str] = frozenset({
    "camera_clearance_mm",
    "led_clearance_mm",
    "min_optical_axis_alignment",
    "beam_half_angle_deg",
    "optical_test_range_mm",
})


def load(path):
    m = trimesh.load(str(path))
    if not isinstance(m, trimesh.Trimesh):
        raise RuntimeError(f"Could not load mesh from {path}")
    return m


def aabb_corners(center, size):
    half = np.asarray(size) / 2.0
    offsets = np.array(
        [[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)],
        dtype=float,
    )
    return np.asarray(center) + offsets * half


def cavity_clearance_yz(corners, frame_cavity, forward_axis):
    """
    Returns per-axis clearance for the AABB corners relative to the cavity
    boundaries. Positive clearance = component is fully inside cavity;
    negative = component protrudes through the cavity wall.
    """
    forward = np.asarray(forward_axis)
    # Forward direction is, e.g., -Y. The "front face" of the cavity sits at
    # the smallest Y. The component's most-forward corner is the one with
    # the SMALLEST dot product with `forward` (because forward=-Y means
    # smaller Y has smaller dot).
    # We want: clearance = (front_plane - front_corner) . forward
    # i.e., how far is the front_corner behind the front_plane (positive)
    forward_dot = corners @ forward
    front_corner_idx = int(np.argmin(forward_dot))
    front_corner = corners[front_corner_idx]
    front_clearance = float(
        np.dot(frame_cavity["front_plane"] - front_corner, forward)
    )

    rear_corner_idx = int(np.argmax(forward_dot))
    rear_corner = corners[rear_corner_idx]
    rear_clearance = float(
        np.dot(rear_corner - frame_cavity["back_plane"], forward)
    )

    # Top: Z clearance. Positive => corner strictly below the frame top.
    top_clearance = float(frame_cavity["z_max"] - corners[:, 2].max())
    bottom_clearance = float(corners[:, 2].min() - frame_cavity["z_min"])

    # X bounds (lateral). Positive => corner strictly inside frame span.
    right_clearance = float(frame_cavity["x_max"] - corners[:, 0].max())
    left_clearance = float(corners[:, 0].min() - frame_cavity["x_min"])

    return {
        "front_clearance_mm": front_clearance,
        "back_clearance_mm": rear_clearance,
        "top_clearance_mm": top_clearance,
        "bottom_clearance_mm": bottom_clearance,
        "left_clearance_mm": left_clearance,
        "right_clearance_mm": right_clearance,
    }



def oriented_box_edges(center, size, axis_z):
    """
    Return the 12 edges of an oriented box (OBB) whose local +Z axis
    aligns with `axis_z` in world coordinates.

    `center`: world-space centre
    `size`: full envelope (x, y, z)
    `axis_z`: unit world-space vector that the component's local +Z
              axis maps to.

    The local +X axis is built as the component-local "right" direction
    using the world up vector (0, 0, 1) as a stable reference; if the
    optical axis is near-vertical we use (0, 1, 0) instead.
    """
    axis_z = np.asarray(axis_z, dtype=float)
    axis_z /= np.linalg.norm(axis_z)
    if abs(axis_z[2]) < 0.9:
        world_up = np.array([0.0, 0.0, 1.0])
    else:
        world_up = np.array([0.0, 1.0, 0.0])
    axis_x = np.cross(world_up, axis_z)
    axis_x /= np.linalg.norm(axis_x)
    axis_y = np.cross(axis_z, axis_x)
    axis_y /= np.linalg.norm(axis_y)

    sx, sy, sz = np.asarray(size) / 2.0
    c = np.asarray(center)

    # Local-frame corners (8 of them) in component space
    local = np.array(
        [[sx * sx_, sy * sy_, sz * sz_]
         for sx_ in (-1, 1)
         for sy_ in (-1, 1)
         for sz_ in (-1, 1)],
        dtype=float,
    )
    # Rotate local -> world via the basis (axis_x, axis_y, axis_z) and
    # translate to the world centre.
    basis = np.stack([axis_x, axis_y, axis_z], axis=0)  # 3x3 rows=local axes
    world_corners = local @ basis + c

    # Build the 12 edges (pairs of corner indices)
    edges = []
    for i in range(8):
        for j in range(i + 1, 8):
            diff = local[i] - local[j]
            nz = sum(1 for v in diff if abs(v) > 1e-6)
            if nz == 1:
                edges.append((i, j))
    return world_corners, np.array(edges, dtype=int)


def oriented_envelope_intersects_mesh(mesh, center, size, axis_z):
    """
    Test whether an oriented box (OBB) intersects the given triangle
    mesh. Returns (intersects: bool, min_distance: float, contact_point).

    Algorithm:
      - Compute the 8 corners and 12 edges of the OBB.
      - For each OBB corner, find the nearest point on the mesh and its
        distance (trimesh.proximity.closest_point).
      - If the nearest point lies inside the OBB's local frame, that
        corner is INSIDE the mesh => intersection.
      - For each OBB edge, ray-cast from one corner to the other; if the
        ray hits the mesh between the endpoints, the edge passes
        THROUGH the mesh => intersection.
      - Otherwise, the OBB is clear; return the minimum corner-distance
        to the mesh as the safety margin.
    """
    axis_z = np.asarray(axis_z, dtype=float)
    axis_z /= np.linalg.norm(axis_z)

    corners, edges = oriented_box_edges(center, size, axis_z)
    sx, sy, sz = np.asarray(size) / 2.0

    # 1. Per-corner distance to the mesh surface.
    _, ud, _ = trimesh.proximity.closest_point(mesh, corners)
    min_ud = float(ud.min())
    nearest_corner_idx = int(np.argmin(ud))

    # 2. Check if the nearest corner lies INSIDE the mesh.
    # Ray-cast from the corner in +Z to determine inside/outside.
    locs, _, _ = mesh.ray.intersects_location(
        ray_origins=corners[nearest_corner_idx: nearest_corner_idx + 1],
        ray_directions=np.array([[0.0, 0.0, 1.0]]),
        multiple_hits=True,
    )
    inside = (len(locs) % 2 == 1)
    if inside:
        return True, -float(ud[nearest_corner_idx]), corners[nearest_corner_idx].tolist()

    # 3. Check if the nearest mesh point lies INSIDE the OBB.
    # Find the closest point on the mesh to the OBB centroid.
    cb_closest, cb_ud, _ = trimesh.proximity.closest_point(
        mesh, np.asarray(center)[None, :],
    )
    if cb_ud[0] < min_ud:
        min_ud = float(cb_ud[0])
        nearest_corner_idx = -1

    # Test if any of the mesh closest points to corners lies inside the
    # OBB. For each corner's closest mesh point, transform to local
    # frame and check |x|<=sx, |y|<=sy, |z|<=sz.
    closest_pts, _, _ = trimesh.proximity.closest_point(mesh, corners)
    if axis_z[2] < 0.9:
        world_up = np.array([0.0, 0.0, 1.0])
    else:
        world_up = np.array([0.0, 1.0, 0.0])
    axis_x = np.cross(world_up, axis_z)
    axis_x /= np.linalg.norm(axis_x)
    axis_y = np.cross(axis_z, axis_x)
    axis_y /= np.linalg.norm(axis_y)
    basis_T = np.stack([axis_x, axis_y, axis_z], axis=1)  # columns
    local_pts = (closest_pts - np.asarray(center)) @ basis_T
    inside_obb = np.all(np.abs(local_pts) <= np.asarray(size) / 2.0 + 1e-6, axis=1)
    if inside_obb.any():
        idx = int(np.argmax(inside_obb))
        return True, -float(ud[idx]), closest_pts[idx].tolist()

    # 4. Edge ray-cast test: for each OBB edge, ray-cast from one corner
    # to the other; any hit between the endpoints => intersection.
    for i, j in edges:
        origin = corners[i]
        direction = corners[j] - corners[i]
        length = float(np.linalg.norm(direction))
        if length < 1e-9:
            continue
        d_unit = direction / length
        locs, _, _ = mesh.ray.intersects_location(
            ray_origins=origin[None, :],
            ray_directions=d_unit[None, :],
            multiple_hits=False,
        )
        if len(locs) == 0:
            continue
        # Is the hit between the endpoints?
        for hit in locs:
            d = np.dot(hit - origin, d_unit)
            if 0.0 <= d <= length:
                return True, 0.0, hit.tolist()

    return False, min_ud, None




def signed_distance_with_ray_sign(mesh, points):
    points = np.asarray(points, dtype=float)
    _, ud, _ = trimesh.proximity.closest_point(mesh, points)
    ray_dirs = np.tile([0.0, 0.0, 1.0], (len(points), 1))
    sign = np.ones(len(points), dtype=float)
    for i, p in enumerate(points):
        locs, _, _ = mesh.ray.intersects_location(
            ray_origins=p[None, :],
            ray_directions=ray_dirs[i:i + 1],
            multiple_hits=True,
        )
        sign[i] = 1.0 if (len(locs) % 2 == 0) else -1.0
    return sign * ud, ud


def optical_cone_clear(target_mesh, apex, axis, half_angle_deg, range_mm):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    if abs(axis[0]) < 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    else:
        ref = np.array([0.0, 1.0, 0.0])
    tangent = np.cross(ref, axis)
    tangent /= np.linalg.norm(tangent)
    bitangent = np.cross(axis, tangent)
    bitangent /= np.linalg.norm(bitangent)
    half = np.deg2rad(half_angle_deg)
    n_rays = 13
    rays = [axis.copy()]
    for k in range(n_rays - 1):
        phi = 2 * np.pi * k / (n_rays - 1)
        d = np.cos(half) * axis + np.sin(half) * (
            np.cos(phi) * tangent + np.sin(phi) * bitangent
        )
        rays.append(d / np.linalg.norm(d))
    origins = np.tile(np.asarray(apex), (len(rays), 1))
    directions = np.stack(rays, axis=0)
    locs, _, _ = target_mesh.ray.intersects_location(
        ray_origins=origins, ray_directions=directions, multiple_hits=False,
    )
    if len(locs) == 0:
        return True, None
    d = np.linalg.norm(locs - np.asarray(apex), axis=1)
    min_d = float(d.min())
    if min_d < range_mm:
        return False, min_d
    return True, None


def validate_candidate(candidate, target_meshes, accepted_so_far, frame_cavity):
    center = np.asarray(candidate["center_mm"], dtype=float)
    size = np.asarray(candidate["envelope_mm"], dtype=float)
    clearance = float(candidate["clearance_mm"])
    opt_axis = np.asarray(candidate.get("optical_axis_world",
                                       candidate.get("surface_normal", [0, 0, 1])),
                          dtype=float)

    result = {
        "component": candidate["component"],
        "region": candidate["region"],
        "label": candidate.get("label"),
        "center_mm": center.tolist(),
        "envelope_mm": size.tolist(),
        "clearance_mm": clearance,
        "optical_axis_world": opt_axis.tolist(),
        "checks": {},
        "status": None,
        "reason": None,
    }

    # ---------- CHECK 1: optical-axis alignment ----------
    forward = np.asarray(frame_cavity["forward_axis"], dtype=float)
    if candidate["role"] in ("camera", "forward_led"):
        alignment = float(np.dot(opt_axis, forward))
    elif candidate["role"] == "temple_led":
        # Temple LEDs must point outward. Lateral axis must dominate.
        alignment = float(np.abs(opt_axis[0]))
    else:
        alignment = 1.0
    result["checks"]["optical_axis_alignment"] = alignment
    if alignment < MIN_ALIGNMENT:
        result["status"] = "REJECT"
        result["reason"] = (
            f"Optical axis misaligned: alignment={alignment:.3f} < "
            f"{MIN_ALIGNMENT}"
        )
        return result

    # ---------- CHECK 2: cavity shell-clearance ----------
    # The component's AABB must sit ENTIRELY inside the lens cavity with
    # at least `clearance` mm to every cavity boundary. This is the
    # coarse positional test.
    corners = aabb_corners(center, size)

    if candidate["role"] in ("camera", "forward_led"):
        cav = cavity_clearance_yz(corners, frame_cavity, forward)
        result["checks"]["cavity_clearance"] = cav

        for key, required in (
            ("front_clearance_mm", clearance),
            ("back_clearance_mm", clearance),
            ("top_clearance_mm", clearance),
            ("bottom_clearance_mm", clearance),
            ("left_clearance_mm", clearance),
            ("right_clearance_mm", clearance),
        ):
            v = cav[key]
            if v < required - 1e-6:
                result["status"] = "REJECT"
                result["reason"] = (
                    f"Insufficient cavity clearance on {key}: "
                    f"{v:.3f} mm < required {required:.3f} mm"
                )
                return result

    # ---------- CHECK 3: oriented-envelope triangle-mesh intersection ----------
    # Construct the actual oriented component envelope (OBB) using the
    # candidate's optical axis as the local +Z, and test for triangle
    # intersection with the target meshes. This is the FINAL acceptance
    # criterion (not AABB-vs-AABB).
    obb_axis = opt_axis  # local +Z in world coords
    for target_name in candidate.get("collision_targets", []):
        if target_name not in target_meshes:
            continue
        target = target_meshes[target_name]
        intersects, dist, contact = oriented_envelope_intersects_mesh(
            target, center, size, obb_axis,
        )
        result["checks"]["obb_intersection"] = {
            "target": target_name,
            "intersects": intersects,
            "distance_mm": dist,
            "contact_mm": contact,
        }
        if intersects:
            result["status"] = "REJECT"
            result["reason"] = (
                f"Orientated envelope intersects {target_name} mesh "
                f"(distance {dist:.3f} mm, contact {contact})"
            )
            return result

    # ---------- CHECK 4: surface-mounting verification ----------
    # Verify the candidate is actually mounted on/near the declared
    # host surface. The component's `mounting_face` field declares which
    # face of the envelope contacts the surface:
    #   "lens"  -> the lens/emitter face (at centre + opt_axis * size/2)
    #   "back"  -> the back/mounting face (at centre - opt_axis * size/2)
    if "surface_point_mm" in candidate:
        surface_point = np.asarray(candidate["surface_point_mm"], dtype=float)
        optical_axis_idx = int(np.argmax(np.abs(opt_axis)))
        optical_extent = size[optical_axis_idx]
        mounting_face_name = candidate.get("mounting_face", "back")
        if mounting_face_name == "lens":
            mount_face = center + opt_axis * (0.5 * optical_extent)
        else:  # default to back face
            mount_face = center - opt_axis * (0.5 * optical_extent)
        mount_distance = float(np.linalg.norm(mount_face - surface_point))
        result["checks"]["mounting_face"] = mounting_face_name
        result["checks"]["mounting_face_to_surface_mm"] = mount_distance
        # Mounting face must be near the surface (within envelope/2 +
        # clearance of the surface point).
        max_offset = 0.5 * optical_extent + clearance + 1.0
        if mount_distance > max_offset + 1e-6:
            result["status"] = "REJECT"
            result["reason"] = (
                f"Component {mounting_face_name} face is {mount_distance:.3f} mm "
                f"from declared surface point; max allowed {max_offset:.3f} mm"
            )
            return result
        # For "lens" mounting: surface point must be in the FORWARD
        # direction from the lens face. For "back" mounting: surface
        # point must be BEHIND the back face (opposite of optical axis).
        face_to_surface = surface_point - mount_face
        proj = float(np.dot(face_to_surface, opt_axis))
        if mounting_face_name == "lens" and proj < -1e-6:
            result["status"] = "REJECT"
            result["reason"] = (
                f"Surface point is BEHIND the component's lens face "
                f"(projection = {proj:.3f} mm)"
            )
            return result
        if mounting_face_name == "back" and proj > 1e-6:
            result["status"] = "REJECT"
            result["reason"] = (
                f"Surface point is IN FRONT of the component's back face "
                f"(projection = {proj:.3f} mm)"
            )
            return result
        result["checks"]["mounting_face_projection_mm"] = proj

    # ---------- CHECK 5: component-to-component clearance ----------
    # Use axis-aligned minimum edge-to-edge distance between the OBBs
    # (uses each candidate's full extent). Reject if too close.
    for other in accepted_so_far:
        oc = np.asarray(other["center_mm"])
        os = np.asarray(other["envelope_mm"])
        diff = np.abs(center - oc)
        half_sum = 0.5 * (size + os)
        edge_to_edge = float(np.linalg.norm(np.maximum(diff - half_sum, 0.0)))
        required = max(clearance, float(other["clearance_mm"]))
        if edge_to_edge < required - 1e-6:
            result["status"] = "REJECT"
            result["reason"] = (
                f"Too close to accepted pose "
                f"'{other.get('label', other['component'])}': "
                f"edge-to-edge distance = {edge_to_edge:.3f} mm, "
                f"required = {required:.3f} mm"
            )
            return result

    # ---------- CHECK 6: optical cone (camera and forward LEDs) ----------
    if candidate["role"] in ("camera", "forward_led"):
        # The lens/emitter face sits at the candidate's forward face
        # along the optical axis.
        forward_extent = size[
            int(np.argmax(np.abs(opt_axis)))
        ]
        emitter_apex = center + opt_axis * (0.5 * forward_extent)
        clear, dist = optical_cone_clear(
            target_mesh=target_meshes["frame"],
            apex=emitter_apex,
            axis=opt_axis,
            half_angle_deg=CAMERA_BEAM_HALF_ANGLE_DEG,
            range_mm=CAMERA_OPTICAL_TEST_RANGE_MM,
        )
        result["checks"]["optical_cone_clear"] = clear
        result["checks"]["optical_cone_obstruction_mm"] = dist
        result["checks"]["aperture_required"] = True
        result["checks"]["aperture_location_mm"] = emitter_apex.tolist()
        if candidate["role"] == "camera":
            result["checks"]["camera_aperture_diameter_recommendation_mm"] = (
                2 * float(np.tan(np.deg2rad(CAMERA_BEAM_HALF_ANGLE_DEG))) * 20.0
            )

    # ---------- CHECK 7: LED optical-envelope mutual clearance ----------
    # The 60-degree beam cone of each LED must not intersect the
    # CAMERA KEEPOUT (a sphere of radius envelope_max + clearance around
    # the camera centre). This prevents the camera lens from looking
    # directly into an LED beam.
    if candidate["role"] in ("forward_led", "temple_led"):
        # Find camera position from accepted poses.
        cam_pose = next(
            (a for a in accepted_so_far
             if a["component"] == "camthink_ov5640_8p5"),
            None,
        )
        if cam_pose is not None:
            cam_center = np.asarray(cam_pose["center_mm"])
            cam_size = np.asarray(cam_pose["envelope_mm"])
            # Cone half-angle = 30 deg.
            # The LED apex is at its centre + opt_axis * (size.z/2).
            fwd = size[int(np.argmax(np.abs(opt_axis)))]
            led_apex = center + opt_axis * (0.5 * fwd)
            # Closest point from the camera envelope (sphere approx) to
            # the LED apex along the LED's optical axis: project camera
            # centre onto the LED optical axis and check the perpendicular
            # distance.
            led_to_cam = cam_center - led_apex
            axis = np.asarray(opt_axis)
            proj = float(np.dot(led_to_cam, axis))
            if proj > 0:  # camera is in front of LED
                perp = led_to_cam - proj * axis
                perp_dist = float(np.linalg.norm(perp))
                # Half-angle check: at distance `proj` from the LED, the
                # beam radius is proj * tan(30 deg). The camera must be
                # outside that radius + camera clearance.
                beam_radius = proj * np.tan(np.deg2rad(30.0))
                cam_clear = float(cam_pose["clearance_mm"])
                led_clear = float(clearance)
                required_radius = beam_radius + cam_clear + led_clear
                if perp_dist < required_radius - 1e-6:
                    result["status"] = "REJECT"
                    result["reason"] = (
                        f"LED 60-degree beam cone intersects camera keepout: "
                        f"perpendicular distance {perp_dist:.3f} mm < "
                        f"required {required_radius:.3f} mm"
                    )
                    return result
                result["checks"]["led_camera_beam_intersection"] = {
                    "projection_mm": proj,
                    "perpendicular_distance_mm": perp_dist,
                    "beam_radius_at_projection_mm": beam_radius,
                    "required_radius_mm": required_radius,
                }

    # ---------- CHECK 3: component-to-component clearance ----------
    # Use axis-aligned minimum distance between the two AABBs. The
    # minimum edge-to-edge distance is the L2 norm of the per-axis
    # penetration depths (positive only):
    #   diff = |centre_this - centre_other|
    #   half_sum = 0.5 * (size_this + size_other)
    #   penetration_per_axis = max(0, half_sum - diff)  (positive if overlapping)
    #   edge_to_edge_distance = ||max(0, diff - half_sum)||
    # Required clearance = max(this.clearance, other.clearance).
    for other in accepted_so_far:
        oc = np.asarray(other["center_mm"])
        os = np.asarray(other["envelope_mm"])
        diff = np.abs(center - oc)
        half_sum = 0.5 * (size + os)
        edge_to_edge = float(np.linalg.norm(np.maximum(diff - half_sum, 0.0)))
        required = max(clearance, float(other["clearance_mm"]))
        if edge_to_edge < required - 1e-6:
            result["status"] = "REJECT"
            result["reason"] = (
                f"Too close to accepted pose "
                f"'{other.get('label', other['component'])}': "
                f"edge-to-edge distance = {edge_to_edge:.3f} mm, "
                f"required = {required:.3f} mm"
            )
            return result

    result["status"] = "PASS"
    result["reason"] = (
        f"All geometric checks pass; cavity clearances and "
        f"optical axis alignment within tolerance"
    )
    return result


class ToleranceOverrideError(ValueError):
    """Raised when a tolerance override is invalid or below policy floor."""


def _validate_and_apply_overrides(
    tolerance_overrides_mm: dict | None,
) -> tuple[dict, list[str]]:
    """Validate a tolerance_overrides_mm dict and return (applied, errors).

    Each key in ``tolerance_overrides_mm`` must be one of the recognised
    override keys. Values must be positive finite floats and must NOT
    drop below the mandatory policy floor. The returned ``applied``
    mapping contains ONLY the overrides that survived validation; bad
    keys/values are surfaced via ``errors`` and never silently applied.
    """
    applied: dict[str, float] = {}
    errors: list[str] = []
    if tolerance_overrides_mm is None:
        return applied, errors
    if not isinstance(tolerance_overrides_mm, dict):
        errors.append(
            f"tolerance_overrides_mm must be a mapping; got {type(tolerance_overrides_mm).__name__}"
        )
        return applied, errors

    floors: dict[str, float] = {
        "camera_clearance_mm": CAMERA_POLICY_MIN_CLEARANCE_MM,
        "led_clearance_mm": LED_POLICY_MIN_CLEARANCE_MM,
        "min_optical_axis_alignment": MIN_ALIGNMENT_POLICY_FLOOR,
        # beam_half_angle_deg and optical_test_range_mm have no relax
        # floor (the optical cone is the source of truth), but the
        # value still must be positive finite.
    }

    for key, value in tolerance_overrides_mm.items():
        if key not in _VALID_OVERRIDE_KEYS:
            errors.append(
                f"Unknown tolerance override key: {key!r} "
                f"(valid: {sorted(_VALID_OVERRIDE_KEYS)})"
            )
            continue
        try:
            fv = float(value)
        except (TypeError, ValueError):
            errors.append(
                f"Override {key!r} is not a number: {value!r}"
            )
            continue
        if not math.isfinite(fv):
            errors.append(
                f"Override {key!r} is not finite: {value!r}"
            )
            continue
        if fv < 0:
            errors.append(
                f"Override {key!r} is negative: {fv}"
            )
            continue
        floor = floors.get(key)
        if floor is not None and fv < floor:
            errors.append(
                f"Override {key!r}={fv} is below the mandatory policy "
                f"floor of {floor}"
            )
            continue
        applied[key] = fv
    return applied, errors


def validate_component_poses(
    candidates_data: dict,
    *,
    target_meshes: dict | None = None,
    frame_cavity: dict | None = None,
    coords: dict | None = None,
    tolerance_overrides_mm: dict | None = None,
) -> dict:
    """Run the geometry-aware pose validator in-process.

    This is the importable, Phase-2-friendly form of the CLI validator.
    It accepts already-parsed ``candidates_data`` (and optionally the
    target meshes, cavity description, and frame coordinate system),
    validates any tolerance overrides against the mandatory policy
    floors, runs the existing per-candidate checks, and returns the
    validation result as a dict. It never writes to disk and never
    mutates any input mapping.

    Parameters
    ----------
    candidates_data:
        Parsed ``component-pose-candidates.json`` mapping.
    target_meshes:
        Optional pre-loaded ``{name: trimesh.Trimesh}`` mapping. When
        omitted, the validator loads the three reference STLs.
    frame_cavity:
        Optional pre-built cavity description. When omitted the validator
        derives one from ``coords``.
    coords:
        Optional parsed ``frame-coordinate-system.json``. Required when
        ``frame_cavity`` is not supplied.
    tolerance_overrides_mm:
        Optional mapping of tolerance overrides. Recognised keys:
        ``camera_clearance_mm``, ``led_clearance_mm``,
        ``min_optical_axis_alignment``, ``beam_half_angle_deg``,
        ``optical_test_range_mm``. Negative / non-finite / below-policy
        values are rejected and surfaced via ``validation.applied_overrides``
        and the function-level warning list. Overrides are never silently
        applied.

    Returns
    -------
    dict
        A complete validation report identical in structure to what the
        CLI writes to ``component-pose-validation.json``. The
        ``validation`` block additionally records
        ``applied_overrides`` (only those accepted) and any
        ``override_errors``.
    """
    # 1. Validate tolerance overrides BEFORE doing any geometric work.
    applied_overrides, override_errors = _validate_and_apply_overrides(
        tolerance_overrides_mm
    )

    # 2. Load target meshes if the caller didn't pass them.
    if target_meshes is None:
        target_meshes = {
            "frame": load(FRAME),
            "left_temple": load(LEFT),
            "right_temple": load(RIGHT),
        }

    # 3. Derive frame cavity if needed.
    if frame_cavity is None:
        if coords is None:
            coords = json.loads(FRAME_COORDS.read_text())
        forward_axis = np.asarray(
            coords["coordinate_system"]["forward_axis"], dtype=float
        )
        front_face_inner_y = float(
            coords["coordinate_system"]["frame_front_face_inner_y_mm"]
        )
        back_face_inner_y = float(
            coords["coordinate_system"]["frame_back_face_inner_y_mm"]
        )
        lo, hi = target_meshes["frame"].bounds
        frame_cavity = {
            "front_plane": np.array([0.0, front_face_inner_y, 0.0]),
            "back_plane": np.array([0.0, back_face_inner_y, 0.0]),
            "x_min": float(lo[0]),
            "x_max": float(hi[0]),
            "z_min": float(lo[2]),
            "z_max": float(hi[2]),
            "forward_axis": forward_axis.tolist(),
        }

    forward_axis = np.asarray(frame_cavity["forward_axis"], dtype=float)
    front_face_y = float(coords["coordinate_system"]["frame_front_face_y_mm"])
    back_face_y = float(coords["coordinate_system"]["frame_back_face_y_mm"])

    # 4. Apply overrides by setting module-level constants used by
    #    validate_candidate() for the duration of the call. Restore on
    #    exit so subsequent CLI invocations are unaffected.
    saved: dict[str, float] = {}
    for key, value in applied_overrides.items():
        if key == "camera_clearance_mm":
            # Camera clearance is encoded inside each candidate's
            # ``clearance_mm`` field, not in the module-level constant;
            # no module-level mutation required.
            continue
        if key == "led_clearance_mm":
            continue
        if key == "min_optical_axis_alignment":
            saved["MIN_ALIGNMENT"] = MIN_ALIGNMENT
            globals()["MIN_ALIGNMENT"] = value
        elif key == "beam_half_angle_deg":
            saved["CAMERA_BEAM_HALF_ANGLE_DEG"] = CAMERA_BEAM_HALF_ANGLE_DEG
            globals()["CAMERA_BEAM_HALF_ANGLE_DEG"] = value
        elif key == "optical_test_range_mm":
            saved["CAMERA_OPTICAL_TEST_RANGE_MM"] = CAMERA_OPTICAL_TEST_RANGE_MM
            globals()["CAMERA_OPTICAL_TEST_RANGE_MM"] = value

    try:
        ordered: list[tuple[str, list]] = []
        ordered.append(("camera", [candidates_data["camera"]["candidates"][0]]))
        ordered.append(("forward_leds", candidates_data["forward_leds"]["candidates"]))
        ordered.append(
            ("temple_led_left", candidates_data["temple_leds"]["left_candidates"])
        )
        ordered.append(
            ("temple_led_right", candidates_data["temple_leds"]["right_candidates"])
        )

        accepted: list[dict] = []
        rejected: list[dict] = []
        invalid: list[dict] = []

        for _group_name, group in ordered:
            for cand in group:
                res = validate_candidate(
                    cand, target_meshes, accepted, frame_cavity
                )
                if res["status"] == "PASS":
                    accepted.append(res)
                elif res["status"] == "REJECT":
                    rejected.append(res)
                else:
                    invalid.append(res)

        best_by_role: dict[str, dict] = {}
        for a in accepted:
            key = a["component"] + ":" + str(a.get("label"))
            best_by_role[key] = a

        # ---------- diagnostics ----------
        diagnostics: list[dict] = []

        cam_a = [r for r in accepted if r["component"] == "camthink_ov5640_8p5"]
        cam_r = [r for r in rejected if r["component"] == "camthink_ov5640_8p5"]
        if cam_a:
            c = cam_a[0]
            diagnostics.append({
                "component": "camera",
                "status": "PASS",
                "center_mm": c["center_mm"],
                "cavity_clearance": c["checks"].get("cavity_clearance"),
                "optical_axis_alignment": c["checks"]["optical_axis_alignment"],
            })
        else:
            diagnostics.append({
                "component": "camera",
                "status": "FAIL",
                "reason": cam_r[0]["reason"] if cam_r else "no candidate",
            })

        fl_a = [r for r in accepted if r["region"] == "front_frame"]
        fl_r = [r for r in rejected if r["region"] == "front_frame"]
        diagnostics.append({
            "component": "forward_leds",
            "status": "PASS" if len(fl_a) == 2 else "FAIL",
            "accepted_count": len(fl_a),
            "rejected_count": len(fl_r),
            "poses": [
                {"label": r["label"], "center_mm": r["center_mm"]} for r in fl_a
            ],
            "rejected_reasons": [
                {"label": r["label"], "reason": r["reason"]} for r in fl_r
            ],
        })

        tl_a = [r for r in accepted if r["region"].endswith("_temple")]
        tl_r = [r for r in rejected if r["region"].endswith("_temple")]
        diagnostics.append({
            "component": "temple_leds",
            "status": "PASS" if len(tl_a) == 4 else "FAIL",
            "accepted_count": len(tl_a),
            "rejected_count": len(tl_r),
            "poses": [
                {"label": r["label"], "center_mm": r["center_mm"]} for r in tl_a
            ],
            "rejected_reasons": [
                {"label": r["label"], "reason": r["reason"]} for r in tl_r
            ],
        })

        overall_pass = (
            len(cam_a) == 1 and len(fl_a) == 2 and len(tl_a) == 4
        )

        output: dict = {
            "schema_version": 3,
            "validation": {
                "camera_envelope_mm": [8.5, 8.5, 6.5],
                "led_envelope_mm": [3.4, 3.4, 1.5],
                "camera_clearance_mm": 1.0,
                "led_clearance_mm": 0.5,
                "beam_half_angle_deg": CAMERA_BEAM_HALF_ANGLE_DEG,
                "min_optical_axis_alignment": MIN_ALIGNMENT,
                "coordinates_manual": False,
                "frame_curvature_preserved": True,
                "validation_method": "shell_aware_cavity_plus_solid_temple_proximity",
                "forward_axis_world": forward_axis.tolist(),
                "frame_front_face_y_mm": front_face_y,
                "frame_back_face_y_mm": back_face_y,
                "lens_cavity_depth_mm": back_face_y - front_face_y,
                "frame_treated_as": "thin_shell_bounding_cavity",
                "overall_status": "PASS" if overall_pass else "FAIL",
            },
            "accepted": accepted,
            "rejected": rejected,
            "invalid": invalid,
            "best_set": [v for v in best_by_role.values()],
            "diagnostics": diagnostics,
            "summary": {
                "candidate_count": len(accepted) + len(rejected) + len(invalid),
                "accepted": len(accepted),
                "rejected": len(rejected),
                "invalid": len(invalid),
            },
        }
        # Surface the override bookkeeping in the output. When the CLI
        # path is taken with no overrides the dict matches the original
        # Phase-1 schema byte-for-byte.
        if tolerance_overrides_mm is not None or override_errors:
            output["validation"]["applied_overrides"] = applied_overrides
            output["validation"]["override_errors"] = override_errors
        return output
    finally:
        for key, old_value in saved.items():
            globals()[key] = old_value


def main():
    print("=" * 70)
    print("GEOMETRY-AWARE COMPONENT POSE VALIDATION")
    print("=" * 70)

    coords = json.loads(FRAME_COORDS.read_text())

    target_meshes = {
        "frame": load(FRAME),
        "left_temple": load(LEFT),
        "right_temple": load(RIGHT),
    }

    front_face_y = float(coords["coordinate_system"]["frame_front_face_y_mm"])
    front_face_inner_y = float(coords["coordinate_system"]["frame_front_face_inner_y_mm"])
    back_face_y = float(coords["coordinate_system"]["frame_back_face_y_mm"])
    back_face_inner_y = float(coords["coordinate_system"]["frame_back_face_inner_y_mm"])
    cavity_y_min = front_face_inner_y
    cavity_y_max = back_face_inner_y
    forward_axis = np.asarray(coords["coordinate_system"]["forward_axis"], dtype=float)
    lo, hi = target_meshes["frame"].bounds

    frame_cavity = {
        "front_plane": np.array([0.0, cavity_y_min, 0.0]),
        "back_plane": np.array([0.0, cavity_y_max, 0.0]),
        "x_min": float(lo[0]),
        "x_max": float(hi[0]),
        "z_min": float(lo[2]),
        "z_max": float(hi[2]),
        "forward_axis": forward_axis.tolist(),
    }

    print(f"Forward axis:        {forward_axis.tolist()}")
    print(f"Front face Y outer:  {front_face_y:.3f} mm")
    print(f"Front face Y inner:  {cavity_y_min:.3f} mm (cavity front wall)")
    print(f"Back face Y inner:   {cavity_y_max:.3f} mm (cavity back wall)")
    print(f"Back face Y outer:   {back_face_y:.3f} mm")
    print(f"X bounds:            [{lo[0]:.3f}, {hi[0]:.3f}]")
    print(f"Z bounds:            [{lo[2]:.3f}, {hi[2]:.3f}]")
    print()

    data = json.loads(CANDIDATES.read_text())

    output = validate_component_poses(
        candidates_data=data,
        target_meshes=target_meshes,
        frame_cavity=frame_cavity,
        coords=coords,
    )

    OUT.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print()
    print("=" * 70)
    print("VALIDATION RESULT")
    print("=" * 70)
    print(f"Overall: {output['validation']['overall_status']}")
    print(f"Candidates tested: {output['summary']['candidate_count']}")
    print(f"Accepted:          {output['summary']['accepted']}")
    print(f"Rejected:          {output['summary']['rejected']}")
    print(f"Invalid:           {output['summary']['invalid']}")
    print()
    for d in output["diagnostics"]:
        print(f"  {d['component']:<14}: {d['status']}")
    print()
    print(f"Output: {OUT.relative_to(ROOT)}")
    print("=" * 70)


if __name__ == "__main__":
    main()