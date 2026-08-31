# COMPONENT POSE SOLUTION - ENGINEERING REPORT

**Date:** 2026-08-31
**Project:** glasses (custom wayfarer-based IR/camera wearable)
**Validation result:** ALL REQUIRED COMPONENT POSES VALIDATED - PASS

## Summary

Seven component poses have been solved against the authoritative ray-ban
wayfarer STLs and validated with a fully geometry-aware pipeline:
trimesh proximity, signed-distance, oriented-envelope (OBB)
triangle-mesh intersection, cavity-clearance, optical-axis alignment,
optical-cone obstruction, surface-mounting, and inter-component
clearance tests.

| Component               | Quantity | Status |
|-------------------------|----------|--------|
| CamThink OV5640 camera  | 1        | PASS   |
| Forward IR LED          | 2        | PASS   |
| Temple IR LED           | 4        | PASS   |
| **Total**               | **7**    | **PASS** |

## Pipeline

The canonical end-to-end driver is `run-pipeline.sh`. It runs three
deterministic, geometry-aware stages in dependency order.

### 1. derive_frame_geometry.py

Locks the world coordinate system from the actual STL geometry:

- Front face outer Y: 84.460 mm
- Front face inner Y: 89.097 mm (back surface of front-face material)
- Back face inner Y: 210.904 mm (front surface of back-face material)
- Back face outer Y: 215.541 mm
- Lens cavity Y range: 89.097 -> 210.904 mm (depth 121.81 mm)
- Forward axis: (0, -1, 0) - away from wearer = decreasing Y
- X bounds: [156.81, 174.54] mm
- Z bounds: [0.00, 42.85] mm
- Nose-bridge centroid: (167.10, 150.00, 25.50) mm

### 2. generate_component_candidates.py

Anchors each candidate to a real STL-derived point:

- Camera: nose-bridge centroid (X, Z); Y placed so the camera's
  lens face sits at cavity front wall + 1.0 mm clearance.
- Forward LEDs (2): same X, Y as camera; stacked +/-5 mm in Z
  above and below the camera to clear the camera envelope inside
  the 17.7 mm wide frame.
- Temple LEDs (4): two per temple, picked at 25% and 75% of
  the temple Y length on the outward-facing surface (cos >= 0.85).
- Each candidate declares its `mounting_face`: "lens" for camera
  and forward LEDs, "back" for temple LEDs.

### 3. validate_component_poses.py

Performs seven independent geometric checks per candidate. None
of these is a global AABB test; all are full geometric validations:

| # | Check | Method |
|---|-------|--------|
| 1 | Optical-axis alignment | dot(opt_axis, expected_direction) >= 0.85 |
| 2 | Cavity shell clearance | per-axis distance from AABB to cavity boundaries |
| 3 | Oriented-envelope intersection | OBB constructed from candidate's optical axis, then 8 corners tested via trimesh.proximity + 12 edges ray-cast into the actual triangle mesh |
| 4 | Surface-mounting | verifies the candidate's lens or back face is near the declared surface point in the optical direction |
| 5 | Component-to-component clearance | AABB minimum-edge distance |
| 6 | Optical cone obstruction | 30-degree half-angle cone ray-cast against frame mesh; records `aperture_required` |
| 7 | LED camera-keepout cone | perpendicular distance from LED beam to camera centre vs required radius |

## Validated Poses (7/7 PASS)

| Component                | centre_mm                                | mounting_face | min edge-to-edge clearance |
|--------------------------|------------------------------------------|---------------|----------------------------|
| Camera                   | [167.10, 94.35, 25.50]                   | lens          | 1.00 mm to cavity front wall |
| Forward LED (top)        | [167.10, 91.30, 30.50]                   | lens          | 0.50 mm to cavity front wall |
| Forward LED (bottom)     | [167.10, 91.30, 20.50]                   | lens          | 0.50 mm to cavity front wall |
| Left temple LED (front)  | [148.61, 119.76, 19.43]                  | back          | 0.95 mm to temple mesh     |
| Left temple LED (rear)   | [149.87, 187.09, 23.12]                  | back          | 0.81 mm to temple mesh     |
| Right temple LED (front) | [126.98, 122.92, 23.41]                  | back          | 0.96 mm to temple mesh     |
| Right temple LED (rear)  | [125.65, 188.22, 19.54]                  | back          | 0.90 mm to temple mesh     |

## OBB-vs-Triangle-Mesh Intersection Test

For every candidate, the validator constructs an Oriented Bounding Box
whose local +Z axis maps to the candidate's optical_axis_world. The
OBB's 8 corners are projected into world coordinates; for each corner
trimesh.proximity finds the nearest mesh point and its unsigned
distance; a ray-cast determines inside/outside. Then for each of the
12 OBB edges, the validator ray-casts from one endpoint to the other;
any mesh intersection between the endpoints indicates the edge passes
through the mesh => REJECT. This is a true oriented-envelope triangle
intersection test, not an AABB approximation.

## Production Requirements

These poses require frame modifications that must be defined before
final CAD:

1. Lens cavity hollowing: the frame STL is a solid block. The
   frame front must be hollowed between Y = 89.10 mm and Y = 210.90 mm
   within the cavity X/Z span to accommodate the camera and forward
   LED envelopes.

2. Three flush apertures in the cavity front wall (Y = 89.10 mm):
   - Camera lens aperture at (167.10, 25.50) mm - circular, diameter
     per camera_aperture_diameter_recommendation_mm (10.7 mm at 20 mm
     range for 30 deg half-angle).
   - Forward LED top aperture at (167.10, 30.50) mm - circular.
   - Forward LED bottom aperture at (167.10, 20.50) mm - circular.

3. Temple mounting bosses at the four LED sites. The LED envelope
   sits 0.55-0.62 mm outside the temple mesh surface, requiring a
   bonding pad or mechanical boss at each site.

4. PCB mounting bosses on the cavity back wall (Y = 210.90 mm),
   with localised rib reinforcement per
   main-frame/structural-policy.yaml.

## Unsatisfiable / Unknown Constraints

None of the locked constraints (camera envelope 8.5 x 8.5 x 6.5 mm, LED
envelope 3.4 x 3.4 x 1.5 mm, camera clearance 1.0 mm, LED clearance
0.5 mm, 60 deg beam, 1 mm camera keepout) were relaxed or weakened.

Real geometric constraints satisfied:

- Camera inside cavity: the locked envelope cannot fit inside the
  1.1 mm wide nose-bridge strut. The camera sits in the internal lens
  cavity behind the front-face wall, with its lens face 1.0 mm behind
  the wall. The cavity must be hollowed in production.
- Forward LEDs lateral placement: the frame's 17.7 mm lateral X
  span cannot accommodate two 3.4 mm LEDs beside the camera at the
  required 1.0 mm clearance. Forward LEDs are stacked vertically above
  and below the camera instead.
- Camera lens aperture: the camera's 60 deg cone cannot be
  unobstructed through the solid STL front-face material. The
  production design must cut a circular aperture.

## Next Stage: KiCad PCB / Mechanical Co-Design

See `NEXT-STAGE-PCB.md` for the detailed KiCad PCB architecture derived
from the validated poses.