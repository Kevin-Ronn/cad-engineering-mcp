# Camera System — Reference Index

This directory holds component references for the two forward-facing
cameras of the glasses. The previous architecture used a single
CamThink OV5640 8.5 × 8.5 × 6.5 mm module; that module is retained
**as a historical reference only** and is **not** the preferred
candidate.

The new architecture requires:

- **2 forward-facing cameras**, one near the upper-outer region of
  each lens / front frame
- Approximately **symmetric left/right** placement
- **MIPI CSI-2** to the Allwinner V853 (2-lane per camera, or shared
  4-lane via a CSI-2 mux — see V853 reference)
- **Primarily for**: general CV, object detection/tracking, OCR,
  license-plate / registration-number recognition, scene capture
- Heavy AI inference runs on the connected phone; the on-board SoC
  handles capture, prefilter, and device control only

Priorities: small module size, low power, MIPI CSI-2, ≥1080p, good
daylight image quality, good dynamic range, small lens/module height,
public mechanical dimensions, public datasheet, FPC/connector info,
reasonable prototype availability. Global shutter is a bonus, not
required.

The existing authoritative frame geometry in
`projects/glasses/references/silhouette/wayfarer/` and
`projects/glasses/mechanical/main-frame/WORKING_FRAME_SOLID.FCStd`
was **not modified** during this research pass.

---

## Contents of this directory

| File | Description |
| --- | --- |
| `rpi_camera_module_3_imx708_standard.yaml` | Raspberry Pi Camera Module 3 Standard (IMX708, 11.9 MP, 25 × 24 × 11.5 mm, with IR-cut). Highest documentation quality. |
| `rpi_camera_module_3_imx708_noir.yaml` | Same hardware as Standard but **without** the IR-cut filter. Required for the 940 nm distributed near-IR LED use case. |
| `rpi_camera_module_3_imx708_wide.yaml` | Wide-FOV (102° H) variant of Camera Module 3. Best for scene capture; lower pixel density per degree, not preferred for OCR at distance. |
| `arducam_b0331_imx296.yaml` | Arducam B0331, IMX296 color global shutter. 40 × 40 mm PCB is too large for the glasses; listed for completeness. |
| `arducam_imx219_variants.yaml` | Arducam IMX219 family, 8 MP, 1.12 µm pixel. Cheap, well-known, many lens options. Lower low-light performance than IMX708. |
| `arducam_imx462_variants.yaml` | Arducam IMX462 STARVIS, 2 MP, 2.9 µm pixel. Best low-light candidate; lower resolution limits OCR distance. |
| `arducam_imx335_variants.yaml` | Arducam IMX335, 5 MP, 2.0 µm pixel. Middle-ground candidate. |
| `ov9281_global_shutter_modules.yaml` | OV9281 global shutter, 1 MP, B&W. Below the glasses spec; listed for completeness. |
| `ov7251_global_shutter_modules.yaml` | OV7251 global shutter, VGA, B&W. Below the glasses spec; listed for completeness. |
| `camthink_ov5640_historical.yaml` | Old single-camera CamThink OV5640 (8.5 × 8.5 × 6.5 mm). **Historical reference only.** Not preferred. |
| `camthink_ov5640_system_historical.yaml` | Old single-camera system spec. **Historical.** |
| `camthink_ov5640_geometry_requirements_historical.yaml` | Old single-camera geometry requirements. **Historical.** |

---

## Comparison of serious candidates

The OV7251 and OV9281 are below the glasses' resolution target and
are not listed as serious candidates. The Arducam B0331 (IMX296) is
listed but its 40 × 40 mm Jetson-Nano form factor is too large for
the Wayfarer rim. The serious candidates are:

| Spec | RPi CM3 (IMX708) Std | RPi CM3 (IMX708) NoIR | RPi CM3 Wide (IMX708) | Arducam IMX219 | Arducam IMX462 (STARVIS) | Arducam IMX335 |
| --- | --- | --- | --- | --- | --- | --- |
| Sensor | Sony IMX708 | Sony IMX708 | Sony IMX708 | Sony IMX219 | Sony IMX462 (STARVIS) | Sony IMX335 |
| Format | 1/2.43" | 1/2.43" | 1/2.43" | 1/4" | 1/2.8" | 1/2.8" |
| Resolution | 11.9 MP (4608×2592) | 11.9 MP | 11.9 MP | 8 MP (3280×2464) | 2 MP (1936×1096) | 5 MP (2592×1944) |
| Pixel size (µm) | 1.4 | 1.4 | 1.4 | 1.12 | 2.9 | 2.0 |
| Output | RAW10 | RAW10 | RAW10 | RAW10 | RAW10 | RAW10 |
| Shutter | rolling | rolling | rolling | rolling | rolling | rolling |
| HDR | yes (up to 3 MP) | yes (up to 3 MP) | yes (up to 3 MP) | no | yes (sensor supports) | yes (sensor supports) |
| Focus | PDAF | PDAF | PDAF | fixed | fixed | fixed |
| FOV H (deg) | 66 | 66 | 102 | 59-220 (lens-dep.) | lens-dep. | lens-dep. |
| Video modes | 1080p50, 720p100 | same | same | 1080p47 | 1080p120 | 5MP@30 |
| IR-cut | yes | **no** | yes (NoIR variant available) | depends | depends | depends |
| Interface | MIPI CSI-2 2-lane | MIPI CSI-2 2-lane | MIPI CSI-2 2-lane | MIPI CSI-2 2-lane | MIPI CSI-2 2-lane | MIPI CSI-2 2-lane |
| PCB (W × H, mm) | 25 × 24 | 25 × 24 | 25 × 24 | ~24 × 25 (mini) | ~24 × 25 (mini, if exists) | ~24 × 24 (mini) |
| Total height (mm) | 11.5 | 11.5 | 12.4 | UNKNOWN | UNKNOWN | UNKNOWN |
| FPC | 15-pin 1.0 mm, 200 mm | same | same | 15-pin 1.0 mm typical | 15-pin 1.0 mm typical | 15/22-pin 1.0 mm typical |
| Op. temp (°C) | 0 to 50 | 0 to 50 | 0 to 50 | UNKNOWN | UNKNOWN | UNKNOWN |
| Approx USD | 25 | 25 | 35 | 20-35 | 35-50 | 30-60 |
| Datasheet | **official brief + mech drawing** | official brief | official brief | Arducam catalog | Arducam catalog | Arducam catalog |
| Confidence | HIGH | HIGH | HIGH | MEDIUM | MEDIUM | MEDIUM |

---

## Mechanical fit potential (vs. existing Wayfarer frame)

The existing Wayfarer frame measurements come from
`projects/glasses/analysis/structure/full-mechanical-inspection.md`
(High-confidence table). Key facts for the upper-outer corner of
each lens rim:

- **Outer rim Y-width at Z=20 mm**: 5.1 mm (left and right)
- **Outer rim X-depth at Z=20 mm**: 5.1 mm (left and right)
- **Outer rim X-depth at upper corner (Y=85, Z=36)**: 9.36 mm
- **Temple transition thickness**: 1.6 mm (extremely thin)
- **Bridge Y-width**: 3.0 mm (too narrow for any of these modules)

All serious candidates have a **PCB envelope of ~25 × 24 mm or
larger**. The only frame region large enough to host a 25 × 24 mm
PCB is the **upper-outer corner of each lens rim**, and even there
the material is only 5-9 mm thick. Each candidate will require:

- Removing material from the rim to create a shallow cavity
- Cutting an aperture in the front-face material for the lens
  (the lens barrel protrudes outward; the back intrudes into the
  lens-cavity space)
- Routing the FPC through the lens-cavity space to a temple or
  to the upper-bridge FFC for the compute PCB

The 40 × 40 mm B0331 IMX296 module is **not mechanically feasible**
without major frame redesign — it cannot fit in any single region of
the rim.

The IMX219 / IMX335 / IMX462 Arducam "mini" form factor (if confirmed
to be ~24 × 24 / 25 mm) faces the same fit constraints as the RPi
Camera Module 3.

---

## Ranking on the glasses-specific criteria

1 = best, 6 = worst. Ties broken by documentation quality.

| Criterion | RPi CM3 Std | RPi CM3 NoIR | RPi CM3 Wide | Arducam IMX219 | Arducam IMX462 | Arducam IMX335 |
| --- | --- | --- | --- | --- | --- | --- |
| Mechanical fit potential | 4 | 4 | 4 | 4 | 4 | 4 |
| Daylight image quality | 2 | 2 | 3 (wide, lower px/deg) | 3 | 4 | 3 |
| Low-light performance | 3 | 3 | 3 | 5 | **1** | 2 |
| Dynamic range / HDR | 1 (PDAF + HDR up to 3MP) | 1 | 1 | 5 | 2 | 2 |
| OCR / license-plate suitability | **1** (11.9 MP, 1.4 µm) | **1** | 3 (wide reduces px/deg) | 2 | 4 | 2 |
| Power (assumed typical) | 2 | 2 | 2 | 2 | 1 (largest pixel, lower fps typical) | 2 |
| MIPI interface fit to V853 | 1 (2-lane) | 1 | 1 | 1 | 1 | 1 |
| Availability | **1** (RPi, in production to 2030) | 1 | 1 | 1 | 2 | 2 |
| Documentation quality | **1** (official brief + mech dwg) | 1 | 1 | 3 (catalog, no per-SKU dims) | 3 | 3 |
| Integration difficulty | 2 (PDAF needs I2C driver) | 2 | 2 | **1** (fixed focus, simplest) | 1 | 1 |

---

## Recommendation

### PRIMARY camera candidate

**Raspberry Pi Camera Module 3 NoIR (IMX708, 25 × 24 × 11.5 mm, 15-pin 1.0 mm FPC, 2-lane MIPI CSI-2, 11.9 MP, 1.4 µm pixel, HDR up to 3 MP, phase-detection autofocus, no IR-cut filter)**

Why:

1. **Best documentation** of any serious candidate — official Raspberry Pi brief with mechanical drawing, sensor and electrical specs, and a 200 mm FPC explicitly published.
2. **NoIR filter removal is required for the distributed near-IR LED use case** — the 940 nm illumination would be blocked by a standard IR-cut filter.
3. **11.9 MP with 1.4 µm pixel and HDR** is the strongest OCR / license-plate candidate. The 1.4 µm pixel is smaller than the IMX462's 2.9 µm, so per-pixel SNR is lower, but the much higher pixel count (11.9 MP vs 2 MP) and the HDR mode compensate for the typical use case (close-to-medium range plate recognition, good daylight).
4. **Raspberry Pi in production until at least January 2030** — no end-of-life risk during the glasses' development.
5. **FPC and MIPI interface are directly compatible** with the V853's 2-lane CSI-2 sub-channels (each camera on its own 2-lane sub-channel — no CSI-2 mux required).
6. **Phase-detection autofocus** allows factory focus-free assembly and software-controlled focus for infinity / close.

### SECONDARY / FALLBACK candidate

**Arducam IMX462 STARVIS module (B0325/B0342/B0381 family, 2 MP, 2.9 µm pixel, 1/2.8", MIPI CSI-2 2-lane, ~$35-50)**

Why as a fallback:

1. **Best low-light performance** in the candidate set — STARVIS back-illuminated, 2.9 µm pixel gives ~4× the per-pixel SNR of the IMX708. For night-vision / IR-illuminated scenes the IMX462 outperforms the IMX708.
2. **1080p @ 120 fps** is excellent for video; the IMX708 is limited to 50 fps at 1080p.
3. **Lens options** are M12 (standard mount) with multiple FOV choices, and the Arducam NoIR variant passes 940 nm.
4. **Main drawback**: only 2 MP. License-plate OCR at distance (>2-3 m) is limited; for shorter-range OCR (1-2 m) the larger pixel is an advantage.

A **third serious option** worth re-qualifying once dimensions are
public: **Arducam IMX335 "Mini"** (5 MP, 2.0 µm, 1/2.8") — middle
ground between the IMX708 and IMX462. Need to confirm a specific
mini SKU with documented dimensions before adoption.

### Two identical modules (recommended)

For the final glasses, the recommendation is to use **two identical
Raspberry Pi Camera Module 3 NoIR modules** — one for each upper-outer
corner. This:

- Symmetric FOV, symmetric firmware, single driver, single BOM line
- Same depth, same FPC routing, same mounting strategy
- Simplifies the compute-PCB layout (two identical 15-pin FPC
  connectors, two identical 2-lane MIPI CSI-2 sub-channels)
- Avoids the need to qualify two different modules' color/pixel
  characteristics, ISP tuning, and mechanical tolerances

### Why not the IMX296 (B0331)

The 40 × 40 mm B0331 form factor is too large for any region of the
Wayfarer rim. The IMX296 sensor is excellent (color global shutter,
good OCR potential at close range), but the only available Arducam
module is mechanically disqualified. A smaller Arducam "mini" IMX296
variant may exist; this needs a dedicated research pass before it
can be considered.

### Why not the OV9281 / OV7251

Both are monochrome (B&W). The glasses require color scene capture
for the CV/object-detection use case. Resolution (1 MP / VGA) is
also below the 1080p target. Global shutter is a bonus, not a
requirement.

---

## Open items to resolve before the next pass

- [ ] Confirm the exact PCB dimensions of the RPi Camera Module 3 mounting holes and FPC exit direction from the official mechanical drawing (page 4 of the brief; the brief's table reports the PCB size but the hole pattern is on the drawing).
- [ ] Decide on a single FOV strategy (66° H Standard vs 102° H Wide). Recommendation: Standard for OCR-priority, but the final answer depends on user scenarios.
- [ ] Decide on focus strategy. PDAF is the most flexible but requires the V853 to run an AF driver. A factory-fixed-focus lens (smaller total height, no AF actuator) is simpler and lighter.
- [ ] Decide whether to use the same lens for both cameras. Symmetric placement is required by the brief; asymmetric FOV between the two cameras would be unusual and should be justified.
- [ ] Confirm that two 2-lane MIPI CSI-2 sub-channels can run simultaneously on the V853 (the datasheet supports it, but Linux driver support needs to be validated).
- [ ] Identify the MIPI CSI-2 mux part number if a single 4-lane CSI-2 channel is preferred over two independent 2-lane sub-channels (the V853 supports both configurations).

---

## Stop point

Per the user's instructions, this is the camera reference-acquisition
deliverable. **No mechanical placement, no PCB design, no FreeCAD
work, and no modification to the existing Wayfarer geometry, the
working solid, or any glasses electronics has been started.** Awaiting
explicit instruction to continue.
