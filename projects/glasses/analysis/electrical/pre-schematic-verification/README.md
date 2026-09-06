# Pre-Schematic Electrical Verification — README

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY pre-schematic verification. No CAD / PCB / STL / FreeCAD files were modified. No PCB routing. No BGA ball numbers invented.

This is the **pre-schematic electrical verification pass**. The goal is to catch architecture-changing mistakes before the design is committed to a real schematic.

---

## Files in this directory

| File | Purpose |
| --- | --- |
| `max98390-verification.md` | MAX98390 IO voltage, decoupling, reset, clock — based on the ADI datasheet information |
| `v853-audio-mux-verification.md` | I2S0 / I2S1 / DMIC muxing on the V853; alternative mux groups |
| `dual-csi-architecture-verification.md` | Dual-camera CSI-2 architecture: ISP bandwidth, virtual channels, Linux driver |
| `axp2101-rail-verification.md` | AXP2101 rail-to-SoC-rail assignment; finalized provisional rail map |
| `aw-cm276sm-verification.md` | AW-CM276SM stamp module datasheet verification |
| `camera-control-verification.md` | IMX708 SCCB address, reset/standby, MCLK, AVDD/DVDD/IOVDD, FPC |
| `display-interface-verification.md` | 0.23-inch 640×400 DSI display interface verification |
| `ir-illumination-power-verification.md` | 940 nm IR LED power architecture, constant-current driver, PWM, thermal |
| `pre-schematic-design-gate.md` | The final design-gate summary: PASS / PASS WITH CONDITIONS / BLOCKED |

---

## The 8 items being verified (per the brief, in priority order)

1. **MAX98390 digital I/O voltage** — HIGH PRIORITY. Determines whether V853 1.8 V I2S connects directly or needs a level shifter.
2. **V853 I2S / DMIC multiplexing** — HIGH PRIORITY. Resolves the PH0-PH4 mux conflict between I2S0 / DMIC / UART3.
3. **Dual-camera CSI architecture** — HIGH PRIORITY. Determines whether the V853 can simultaneously capture two 2-lane cameras.
4. **AXP2101 rail assignment** — finalized provisional rail map.
5. **AW-CM276SM** — datasheet verification (not the M.2 AW-CM276**M**; the glasses' design uses the stamp module AW-CM276**SM**).
6. **Camera control / addressing** — IMX708 SCCB address, reset/standby, MCLK, AVDD/DVDD/IOVDD, FPC.
7. **Display interface** — DSI vs RGB/LVDS/HDMI, lane count, logic voltage, init sequence, TE/reset.
8. **IR illumination power architecture** — LED supply, constant-current driver, PWM, battery impact, thermal.

---

## Source-of-truth files used

- `projects/glasses/references/components/compute/v853/v853-datasheet.pdf` (V853 & V853S Datasheet Rev 1.1, 2022-03-23)
- `projects/glasses/references/components/compute/v853/v853-public-pin-function-audit.md` (V853 public-source pin-function audit)
- `projects/glasses/references/components/compute/v853/v853-public-pin-function-map.yaml` (V853 public-source pin-function map)
- `projects/glasses/references/components/compute/v853/i2s-audio-validation.yaml` (I2S audio validation)
- `projects/glasses/references/components/compute/v853/dmic-validation.yaml` (DMIC validation)
- `projects/glasses/references/components/compute/v853/dual-csi-validation.yaml` (dual CSI validation)
- `projects/glasses/references/components/compute/v853/v853-power-sequencing.yaml` (power sequencing)
- `projects/glasses/references/components/compute/v853/power-tree.yaml` (power tree)
- `projects/glasses/references/components/compute/v853/NDA-BLOCKERS.md` (NDA blockers)
- `projects/glasses/references/electrical/logical-schematic/*` (logical schematic architecture, this pass's input)
- `projects/glasses/references/components/audio/adi_max98390_qualified.yaml` (MAX98390 qualification record)
- `projects/glasses/references/components/wireless/aw_cm276sm.yaml` (AW-CM276SM qualification record)
- `projects/glasses/references/components/camera/rpi_camera_module_3_imx708_standard.yaml` (IMX708 / RPi CM3 qualification record)
- `projects/glasses/references/components/power/axp2101.yaml` (AXP2101 qualification record)
- `projects/glasses/references/components/compute/v853/source/AXP2101_Datasheet_V1_en.pdf` (the AXP2101 datasheet mirrored in the V853 source dir)

---

## Status legend

- **GREEN**: confirmed by authoritative source (manufacturer datasheet, validated reference design) and consistent with the glasses' architecture. Safe to carry into schematic capture.
- **YELLOW**: plausible, with reasonable engineering judgement, but a specific datasheet detail is missing or per a secondary source. Needs confirmation in the next pass.
- **RED**: confirmed not feasible, OR confirmed blocked by missing documentation.

---

## Stop point

Per the brief: "Do not start schematic capture if any HIGH-PRIORITY architectural issue is RED." The final `pre-schematic-design-gate.md` will state the gate result.
