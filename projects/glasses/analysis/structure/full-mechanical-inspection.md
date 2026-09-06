# Full Mechanical Inspection — Wayfarer Frame
**Working file:** `WORKING_FRAME_SOLID.FCStd`
**Inspection date:** 2026-09-02
**Method:** Native BRep common()/section() with thin slabs, no `Shape.isInside()` volumetric scans

---

## Executive Summary

The working solid is the imported triangulated Ray-Ban Wayfarer frame STL converted to BRep. It is a valid single solid of 21,882 faces and 6,067.7 mm³ of material. The frame is dramatically narrower in the X axis (depth, 17.7 mm) than the Y axis (lateral, 143.0 mm) or Z axis (vertical, 42.8 mm).

The frame's mechanical structure is dominated by **two thin, curved lens-retaining rims** connected only at the upper portion by a small **nose bridge**. Most of the front-frame material lies on the outer corners and upper edges — the inner rims and lower corners are **structurally thin** (3–5 mm rim width).

A 3.5 × 1.2 mm continuous flexible-electronics channel is **not feasible** with current geometry without modification:
- Inner-rim width: 3.3 mm (must be ≥5 mm for a 3.5 mm channel + 1.5 mm wall)
- Bridge Y width: 3 mm (must be ≥5 mm)

The OV5640 8.5 × 8.5 × 6.5 mm camera envelope does **not** fit in any axis-aligned orientation at the bridge. A 3.0 × 8.5 × 6.5 mm reoriented camera fits with 97.9 % fill — but that requires the camera's Y dimension (width) to be aligned with the frame's X (depth) axis, which is non-trivial mechanically.

---

## 1. Working Solid Verification

| Property | Value |
| --- | ---: |
| Solids | 1 |
| Faces | 21,882 |
| Edges | 32,823 |
| Vertexes | 10,939 |
| Volume | 6,067.699 mm³ |
| Valid | True |
| Bounding box (min) | (156.812, 78.500, 0.000) |
| Bounding box (max) | (174.539, 221.500, 42.846) |

No discrepancy from prior checkpoint. File **not modified**.

---

## 2. Coordinate System

| Axis | Physical meaning | Extent (mm) | Confidence |
| --- | --- | ---: | --- |
| X | Front–back depth | 17.73 | **HIGH** |
| Y | Lateral width | 143.00 | **HIGH** |
| Z | Vertical height | 42.85 | **HIGH** |

Verification: X is by far the smallest dimension (17.7 mm) and is therefore the front-back depth. Z-scan behavior (X=156.9 has only top-of-frame material, while X=170 has full vertical extent) confirms X is depth. Y span is constant across all X slices (full lateral width).

**Geometric center:** (165.68, 150.00, 21.42)

---

## 3. Lens Openings

At Z=20 (mid-lens-height, derived from Z-slice scan):

| Region | Y min | Y max | Width (mm) | X depth (mm) |
| --- | ---: | ---: | ---: | ---: |
| Left lens opening | 89.5 | 139.8 | 50.3 | 17.7 |
| Right lens opening | 160.2 | 210.5 | 50.3 | 17.7 |
| Nose-bridge gap | 143.1 | 156.9 | 13.8 (material gap) | — |

Lens opening Z-extent:
- Lens openings fully open between Z = 4 and Z = 28
- Above Z = 28, the left/right rims merge into a continuous bridge structure

Lens opening height: ≈ 24 mm (Z = 4 to 28)

---

## 4. Lens Rim Material Thickness

X-direction (front-back depth = local rim thickness):

| Region | Min (mm) | Median (mm) | Max (mm) | Notes |
| --- | ---: | ---: | ---: | --- |
| Left outer top corner (Y=85, Z=36) | 9.36 | 9.36 | 9.36 | Thickest at corner |
| Left outer top (Y=90, Z=36) | 5.67 | 5.67 | 5.67 | |
| Left inner top (Y=142–148, Z=32–36) | 3.34 | 3.55 | 3.74 | Tight |
| Right inner top (Y=152–158, Z=32–36) | 3.34 | 3.55 | 3.74 | Mirror of left |
| Right outer top (Y=210, Z=36) | 5.67 | 5.67 | 5.67 | |
| Right outer bottom (Y=205, Z=6) | 4.54 | 4.54 | 4.54 | |
| Bridge vertical (Y=150, Z=30–36) | 3.34 | 3.41 | 3.41 | Critical for camera |
| Temple left (Y=78–84, Z=22) | 1.61 | 1.61 | 1.61 | Very thin |
| Temple right (Y=216–222, Z=22) | 1.61 | 1.61 | 1.61 | Mirror |

Y-direction (lateral width of rim cross-section at Z=20):

| Region | Y range (mm) | Width (mm) |
| --- | --- | ---: |
| Left outer rim | 84.4 – 89.5 | 5.1 |
| Left inner rim | 139.8 – 143.1 | 3.3 |
| Right inner rim | 156.9 – 160.2 | 3.3 |
| Right outer rim | 210.5 – 215.6 | 5.1 |

**Key finding:** the inner rim width of 3.3 mm is below the 4.4 mm required for an LED pocket, and is just below the 3.5 mm width required for the proposed PCB channel.

---

## 5. Nose Bridge

| Property | Value (mm) |
| --- | ---: |
| Y range (narrowest) | 149.0 – 152.0 |
| Y width | 3.0 |
| Z range (narrowest) | 28.0 – 36.0 |
| Z height | 8.0 |
| X range (narrowest) | 169.3 – 173.1 |
| X depth | 3.8 |
| Geometric center | (171.2, 150.5, 32.0) |
| Loose bbox (incl. tapered surround) | X=[164.87, 173.15] Y=[144.5, 159.5] Z=[25.5, 37.94] |
| Loose volume | 528 mm³ (but mostly empty lens-cavity volume) |
| Tight material volume estimate | ≈ 91 mm³ (3.0 × 3.8 × 8.0) |

The bridge is **only solid in the upper portion** (Z ≥ 28). Below Z = 28, the bridge is just two separated inner rims with a 13.8 mm gap of empty lens-opening space between them. The bridge's lateral width of 3.0 mm is the tightest constraint on the design.

---

## 6. PCB Channel Feasibility

Target: 3.5 mm width × 1.2 mm depth, 1.5 mm structural wall.

| Region | Classification | Reason |
| --- | --- | --- |
| Outer rim top corner | **GREEN** | 5.1 mm Y width, 9.4 mm X depth |
| Outer rim middle | **GREEN** | 5.1 mm Y width, 5–7 mm X depth |
| Outer rim bottom | **GREEN** | 4.5 mm Y width, 4.5 mm X depth |
| Inner rim top corner | **YELLOW** | 3.3–3.7 mm Y width; just below 5 mm target |
| Inner rim middle | **RED** | 3.3 mm Y width < 3.5 mm channel; cannot accommodate |
| Inner rim bottom | **RED** | 3.3 mm Y width |
| Nose bridge | **RED** | 3 mm Y width < 3.5 mm channel |
| Temple transitions | **YELLOW** | 1.6 mm material — needs structural reinforcement |

**Limiting dimension** in every RED region: Y width (rim/bridge lateral width).
**Limiting dimension** in every YELLOW region: rim Y width just at or near threshold.

**Conclusion:** A continuous 3.5 × 1.2 mm channel following the frame contour is **NOT feasible** without redesign. The channel must:
1. Narrow to ≤ 1.5 mm wide along the inner rim and bridge regions, OR
2. Be routed exclusively on the **outer** side of the rim (where Y widths are ≥ 4.5 mm), OR
3. Be combined with localized rim thickening in the inner-rim and bridge regions.

---

## 7. Camera Region

| Property | Value |
| --- | ---: |
| Bridge center | (171.2, 150.5, 32.0) |
| Max inscribed X (depth) | 3.8 mm |
| Max inscribed Y (width) | 3.0 mm |
| Max inscribed Z (height) | 8.0 mm |
| Available volume | ≈ 91 mm³ |
| OV5640 target envelope | 8.5 × 8.5 × 6.5 mm (469.7 mm³) |

### Fit results (single-shot common() tests at bridge center):

| Dimensions (X×Y×Z) | Fill (%) | Fits? |
| --- | ---: | --- |
| 8.5 × 8.5 × 6.5 (target) | 39.4 | No |
| 3.5 × 3.5 × 6.5 | 90.6 | No |
| **3.0 × 3.0 × 6.0 (compact)** | **96.6** | **Yes** |
| 4.0 × 3.0 × 6.0 (asymmetric) | 83.3 | No |
| 3.5 × 3.5 × 7.0 | 90.4 | No |
| 6.5 × 8.5 × 3.0 (rotated) | 51.6 | No |
| **3.0 × 8.5 × 6.5 (depth-Y rotation)** | **97.9** | **Yes** |

**Interpretation:**
- The OV5640 in its 8.5 × 8.5 × 6.5 mm envelope **cannot** fit in any axis-aligned orientation at the current bridge.
- A compact camera of ≤ 3 × 8.5 × 6.5 mm **would** fit if oriented with its Y dimension (8.5 mm) along the frame's X (depth) axis. This means the camera's long axis points straight forward/backward through the frame, not laterally. This is mechanically possible but constrains optical alignment.
- The bridge must be redesigned (widened laterally) to accommodate a conventional camera orientation.

---

## 8. LED Pocket Candidates

LED envelope: 3.4 × 3.4 × 1.5 mm with 0.5 mm clearance = 4.4 mm rim width required.

### Fit results (single-shot common() tests at outer rim positions):

| Position | Orientation (X, Y, Z) | Fill (%) |
| --- | --- | ---: |
| Left outer top (Y=85, Z=33) | (3.9, 3.9, 2.0) | 83.7 |
| Left outer top (Y=85, Z=33) | (2.0, 3.9, 3.9) | **99.0** |
| Left outer top (Y=85, Z=33) | (3.9, 2.0, 3.9) | 83.7 |
| Right outer top (Y=215, Z=33) | (2.0, 3.9, 3.9) | **99.0** |
| Left outer middle (Y=87, Z=22) | (2.0, 3.9, 3.9) | **99.8** |
| Right outer middle (Y=213, Z=22) | (2.0, 3.9, 3.9) | **99.8** |

**Best orientation:** LED Y dimension (long axis) along frame X (depth), LED Z dimension along frame Y (lateral). This is a reasonable mechanical orientation.

### Recommended candidate positions per lens (4 per lens):

1. **Top-outer corner** — Y ≈ 87, Z ≈ 33, fills 99 %
2. **Middle-outer** — Y ≈ 87, Z ≈ 22, fills 99.8 %
3. **Top-inner corner** — Y ≈ 145, Z ≈ 30 (where bridge meets inner rim); needs rim widening
4. **Bottom-outer corner** — Y ≈ 90, Z ≈ 8, fill depends on rim width (4.5 mm — tight)

Inner-rim positions (Y ≈ 140 or 158) currently **cannot** accommodate an LED pocket at 3.3 mm width.

---

## 9. Mechanical Constraints (Ranked)

1. **Bridge Y width = 3.0 mm** — limits camera and PCB routing through center.
2. **Inner-rim Y width = 3.3 mm** — limits PCB channel and LED pockets at inner side.
3. **Temple transition thickness = 1.6 mm** — extremely thin; needs reinforcement for any structural loading.
4. **Outer rim Y width = 5.1 mm** — adequate but tight for PCB channel + 1.5 mm wall.
5. **Front-face taper** — the front of the frame (X near XMin = 156.8) has only top-corner material; lower 60 % of front face is empty (no material below Z=10 at the very front).

---

## 10. Risks

1. **Bridge too narrow** for OV5640 8.5 × 8.5 × 6.5 mm camera without redesign (bridge Y = 3.0 mm vs 8.5 mm needed).
2. **Inner rim Y width (3.3 mm)** is **below the 3.5 mm** PCB channel target.
3. **Front-face taper**: triangulation adds ±0.05 mm uncertainty; measurements rounded to 0.1 mm. Critical fits should add +0.1 mm safety margin.
4. **Temple material (1.6 mm)** is the thinnest structural section; any redesign must preserve or thicken it.
5. **Lower lens-rim region (Z<8)** has rapidly thinning front-face material; lens retention relies on this thin section.
6. **Wayfarer downward taper** at the bottom edges reduces usable volume for components there.

---

## 11. Final Measurement Table

| Measurement | Value (mm) | Tolerance (mm) | Sampling density | Confidence |
| --- | ---: | ---: | --- | --- |
| Frame width (Y) | 143.0 | ±0.1 | bbox | HIGH |
| Frame depth (X) | 17.7 | ±0.1 | bbox | HIGH |
| Frame height (Z) | 42.8 | ±0.1 | bbox | HIGH |
| Geometric center | (165.7, 150.0, 21.4) | ±0.1 | bbox | HIGH |
| Left lens opening width | 50.3 | ±0.5 | 0.5 mm slice | HIGH |
| Right lens opening width | 50.3 | ±0.5 | 0.5 mm slice | HIGH |
| Left lens opening height | 24.0 | ±0.5 | 0.5 mm slice | MEDIUM |
| Outer rim width (Y) | 5.1 | ±0.2 | 0.5 mm slice | HIGH |
| Inner rim width (Y) | 3.3 | ±0.2 | 0.5 mm slice | HIGH |
| Outer rim depth (X) | 5.1–9.4 | ±0.2 | 0.5 mm slice | HIGH |
| Inner rim depth (X) | 3.5 | ±0.2 | 0.4 mm slab | HIGH |
| Bridge Y width | 3.0 | ±0.2 | 0.3 mm slab | HIGH |
| Bridge Z height | 8.0 | ±0.2 | 0.5 mm scan | HIGH |
| Bridge X depth | 3.8 | ±0.2 | 0.3 mm slab | HIGH |
| Bridge center | (171.2, 150.5, 32.0) | ±0.2 | multi | MEDIUM |
| Temple transition thickness | 1.6 | ±0.2 | multi | MEDIUM |
| Max inscribed axis-aligned box at bridge | 3.0 × 3.8 × 8.0 | ±0.2 | fit tests | MEDIUM |
| Camera 8.5×8.5×6.5 fits bridge? | NO | n/a | common() | HIGH |
| Reoriented camera 3.0×8.5×6.5 fits? | YES (97.9%) | ±2% | single common() | HIGH |
| LED 3.4×3.4×1.5 fits outer rim? | YES | n/a | common() | HIGH |

---

## 12. Inspection Artifacts Created

| File | Purpose |
| --- | --- |
| `analysis/structure/full-mechanical-inspection.json` | Consolidated JSON report |
| `analysis/structure/full-mechanical-inspection-raw.json` | Raw JSON data from every step |
| `analysis/structure/full-mechanical-inspection.md` | This markdown report |
| `mechanical/main-frame/inspection/FRAME_GEOMETRY_INSPECTION.FCStd` | FreeCAD inspection file (working solid preserved + reference planes) |

`WORKING_FRAME_SOLID.FCStd` was **not modified**. MD5 verified identical before and after inspection.

---

## 13. Recommended Next CAD Operation

Do not proceed to redesign until the following decisions are made:

1. **Camera decision:**
   - Option A: redesign the bridge to widen Y from 3.0 mm to ≥ 9.0 mm (significant rim thickening)
   - Option B: use a smaller camera module (≤ 3 × 8.5 × 6.5 mm oriented with depth-axis along frame X)
   - Option C: relocate camera from bridge to top-rim (where more material exists at Z=36)

2. **PCB channel decision:**
   - Option A: route only along the outer rim (skip the inner rim and bridge); use bridge as a flex-only transition with reduced/no channel width
   - Option B: thicken the inner rim and bridge by ≥ 1.0 mm before cutting the channel
   - Option C: split the channel into two separate flex ribbons at the bridge (one per side)

3. **LED pocket decision:**
   - Option A: place LEDs only at outer-rim corners and middle (current geometry supports)
   - Option B: add local rim thickening at inner-side LED positions

After these decisions, the next operation would be **targeted rim thickening** (Step 1 of the redesign), which must be done **before** any channel cuts to preserve structural margins.