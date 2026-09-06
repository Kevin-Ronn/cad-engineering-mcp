# Logical Schematic Architecture — README

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY schematic-capture preparation. No CAD / PCB / STL / FreeCAD files were modified. No PCB routing.

This directory contains the **logical signal-level schematic specification** for the V853 smart-glasses reference design. The goal is to make the eventual PCB schematic capture fast and low-risk once the authoritative V853/V853S_PINOUT.sls file is obtained.

**The most important rule**: the V853 signals are documented here as **logical names** (e.g. `CSI0_D0_P/N`, `DSI_D3_P/N`, `SDIO_CMD`). They are **NOT** physical BGA ball numbers. Per the brief, "Treat physical V853 ball assignments as UNKNOWN until the authoritative `V853/V853S_PINOUT.sls` or equivalent Allwinner hardware-design documentation is obtained."

---

## Contents

| File | Purpose |
| --- | --- |
| `README.md` | This file |
| `logical-signal-table.yaml` | Every net in the design: source / destination / bus / voltage / direction / pull / status / source-reference |
| `power-rail-table.yaml` | Every voltage rail: source / consumers / current / sequencing / status |
| `interface-matrix.yaml` | Cross-reference: which V853 peripheral block is used for which glasses function |
| `v853-logical-connectivity.yaml` | The V853's logical connectivity in one place: each peripheral's logical signal list, voltage domain, and source-reference |
| `schematic-design-gates.md` | The design-gate checklist: GREEN / YELLOW / RED for every subsystem |

---

## Status legend (applied to every entry in every table)

- **VERIFIED**: source is an official component datasheet AND the signal/function is documented in the V853 datasheet. Cross-checked against the existing reference libraries.
- **PROVISIONAL**: the function is plausible and consistent with the public sources, but a specific datasheet detail (e.g. exact voltage, exact routing) is missing or is per the 100ASK V853-Pro reference and may need migration.
- **UNKNOWN**: no source confirms this. The decision is BLOCKED until further documentation is obtained (typically the V853/V853S_PINOUT.sls file or a component-specific datasheet PDF).

---

## Voltage-domain legend (applied to every signal)

The V853's I/O voltage domains (per datasheet section 2.3.4):

| Domain | Typical voltage | Used for |
| --- | --- | --- |
| VDD-SYS | 0.9 V | SoC internal core |
| VCC-DRAM | 1.5 V DDR3 / 1.35 V DDR3L | DRAM I/O |
| VCC-IO | 3.3 V | USB 2.0 DRD; some GPIO banks |
| VCC-PA / VCC-PC / VCC-PD / VCC-PE / VCC-PG / VCC-PI | 1.8 V OR 3.3 V (per the GPIO bank's power) | Most GPIO pins |
| VCC18-PF / VCC33-PF | 1.8 V / 3.3 V | GPIO Port F (high-drive) |
| VCC18-MCSI | 1.8 V | MIPI CSI PHY |
| VCC18-MDSI | 1.8 V | MIPI DSI PHY |
| VCC33_USB | 3.3 V | USB 2.0 analog |
| VDD09_USB | 0.9 V | USB 2.0 digital |
| AVCC | 1.8 V | SoC analog |

The chosen components in the reference libraries are all 1.8 V I/O compatible (per the previous pass). The V853's GPIO banks can be configured for 1.8 V or 3.3 V. The glasses' design uses **1.8 V** for all GPIO banks except the 3.3 V fixed banks (VCC-IO, VCC33_USB, VCC33-PF if used).

---

## Cross-references (the source-of-truth files for every claim)

Every entry in every table has a `source` field that points back to one of:

- `projects/glasses/references/components/compute/v853/v853-datasheet.pdf` (and the supporting `.sls` / pinctrl dtsi when obtained)
- `projects/glasses/references/components/compute/v853/v853-public-pin-function-audit.md` (the public-source pin-function audit)
- `projects/glasses/references/components/compute/v853/v853-public-pin-function-map.yaml` (the public-source pin-function map)
- `projects/glasses/references/components/compute/v853/v853-glasses-pin-assignment.yaml` (the glasses' peripheral block assignment)
- `projects/glasses/references/components/compute/v853/power-tree.yaml` (the power tree)
- `projects/glasses/references/components/compute/v853/system-signal-map.yaml` (the system signal map)
- `projects/glasses/references/components/compute/v853/system-power-map.yaml` (the system power map)
- `projects/glasses/references/components/compute/v853/system-block-diagram.md` (the system block diagram)
- `projects/glasses/references/components/compute/v853/dual-csi-validation.yaml` (dual CSI validation)
- `projects/glasses/references/components/compute/v853/display-electrical-validation.yaml` (DSI validation)
- `projects/glasses/references/components/compute/v853/sdio-emmc-coexistence.yaml` (eMMC + SDIO coexistence)
- `projects/glasses/references/components/compute/v853/i2c-audit.yaml` (I2C bus audit)
- `projects/glasses/references/components/compute/v853/i2s-audio-validation.yaml` (I2S audio validation)
- `projects/glasses/references/components/compute/v853/dmic-validation.yaml` (DMIC validation)
- `projects/glasses/references/components/compute/v853/usb-electrical-validation.yaml` (USB validation)
- `projects/glasses/references/components/compute/v853/boot-architecture.yaml` (boot architecture)
- `projects/glasses/references/components/compute/v853/v853-power-sequencing.yaml` (power sequencing)
- `projects/glasses/references/components/compute/v853/electrical-feasibility-report.md` (electrical feasibility)
- `projects/glasses/references/components/compute/v853/NDA-BLOCKERS.md` (NDA blockers)
- `projects/glasses/references/components/camera/*.yaml` (camera candidates)
- `projects/glasses/references/components/display/*.yaml` (display candidates)
- `projects/glasses/references/components/audio/*.yaml` (audio candidates)
- `projects/glasses/references/components/power/*.yaml` (battery + charger + PMIC + fuel gauge + USB-C)
- `projects/glasses/references/components/wireless/*.yaml` (Wi-Fi/BT modules)
- `projects/glasses/references/components/imu/*.yaml` (IMU)
- `projects/glasses/references/components/support/*.yaml` (ALS, temperature, ESD, etc.)

---

## Stop point

Per the brief: "Do not start PCB routing." This README is the entry point to the logical schematic architecture. The companion files (`logical-signal-table.yaml`, `power-rail-table.yaml`, `interface-matrix.yaml`, `v853-logical-connectivity.yaml`, `schematic-design-gates.md`) contain the per-signal detail. The `schematic-design-gates.md` file is the GREEN/YELLOW/RED summary for the eventual PCB schematic capture.
