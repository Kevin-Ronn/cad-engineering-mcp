# V853 Smart-Glasses — Design Gate Checklist

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** This is the design-gate checklist at the end of the electrical-feasibility audit. **The project is NOT CAD-ready.** All critical electrical conflicts are RESOLVED at the peripheral-block level, but the per-ball pin map (V853/V853S_PINOUT.sls) is still required before PCB routing.

---

## GATE 1 — ELECTRICAL

| Requirement | Status | Blocker | Required evidence | Owner / action |
| --- | --- | --- | --- | --- |
| V853 SoC datasheet | DONE | none | v853-datasheet.pdf | none |
| V853 peripheral inventory | DONE | none | v853-ball-map.yaml (peripheral block level) | none |
| V853 per-ball pin map | NOT DONE | V853/V853S_PINOUT.sls not in hand | per-ball pin map | acquire .sls file from Allwinner or BSP |
| V853 glasses pin assignment | PROVISIONAL | per-ball map missing | v853-glasses-pin-assignment.yaml (peripheral-level with UNKNOWN balls) | assign per-ball after .sls file |
| Peripheral conflict audit | DONE (peripheral block level) | GPIO ball-level mux not yet auditable without .sls | v853-peripheral-conflicts.yaml | re-audit at ball level after .sls file |
| Dual CSI validation | DONE | none | dual-csi-validation.yaml (2x 2-lane virtual-channel) | none |
| DSI validation | DONE | display engine electrical interface unknown (NDA) | display-electrical-validation.yaml (V853 DSI directly drives 640x400; no bridge needed in typical case) | acquire display engine NDA |
| eMMC + SDIO coexistence | DONE | none | sdio-emmc-coexistence.yaml | none |
| Wi-Fi/BT interface validation | PROVISIONAL | specific module datasheet PDF not retrieved | wifi-bt-interface-validation.yaml (SDIO + UART topology; voltage domain must match) | acquire module datasheet PDF |
| I2C bus audit (7 devices) | DONE | none | i2c-audit.yaml (all 7 addresses unique; 1.8 V IO; 400 kHz) | none |
| I2S audio validation (2x MAX98390) | DONE | MAX98390 IO voltage must be verified in datasheet | i2s-audio-validation.yaml (one amp per temple is the correct architecture) | verify MAX98390 IO voltage in ADI datasheet PDF |
| DMIC validation | DONE | none | dmic-validation.yaml (1 mic on DMIC0; 1.8 V IO) | none |
| USB-C + USB 2.0 validation | DONE | none | usb-electrical-validation.yaml (5 V only; no USB-PD; TPD4E05U04 ESD) | none |
| Boot architecture | DONE (architecture) | exact boot pin straps are in .sls file | boot-architecture.yaml (eMMC primary, SD fallback, FEL recovery) | acquire .sls file for boot pin straps |
| Power sequencing (AXP2101) | DONE | AXP2101 glasses-specific rail configuration not yet set | v853-power-sequencing.yaml (matches V853 Figure 2-2) | set AXP2101 NVRAM configuration at production-line programming time |

**GATE 1 status: PASS at the peripheral-block level. PROVISIONAL at the per-ball level (V853/V853S_PINOUT.sls required).**

---

## GATE 2 — MECHANICAL

| Requirement | Status | Blocker | Required evidence | Owner / action |
| --- | --- | --- | --- | --- |
| Wayfarer frame assessment | DONE (read-only) | none | full-mechanical-inspection.md, system-block-diagram.md, system-power-map.yaml | none |
| Compute PCB temple pod | NOT DONE | wayfarer temple is 1.6 mm thick (insufficient for any battery, speaker, or display engine); front-frame cross-section is 5-7 mm (insufficient for 6 mm optical engine + 2 mm waveguide + 1 mm shell) | custom frame design with 5-8 mm temple pod and 8-10 mm front-frame cross-section | mechanical design (NOT YET STARTED; this is the next phase) |
| Optical engine placement | NOT DONE | display engine mm-level dimensions are NDA-gated | Lumus or DigiLens NDA drawings | acquire NDA drawings |
| Battery placement | NOT DONE | temple needs custom pod | temple pod cross-section design | mechanical design |
| Speaker placement | NOT DONE | temple needs custom pod | speaker back-volume test | acoustic measurement |
| Camera placement | NOT DONE | upper-outer-corner of each lens rim; rim needs modification | wayfarer rim cavity design | mechanical design |
| IMU, sensors, mic, USB-C placement | NOT DONE | compute PCB layout | compute PCB layout | mechanical + PCB design |
| Thermal envelope (compute PCB) | NOT DONE | AXP2101 dissipation, XR829 dissipation, MAX98390 dissipation, IR LED heat | thermal simulation | thermal design |

**GATE 2 status: NOT PASS. Mechanical design has not started. The Wayfarer frame is too thin for the chosen components; a custom frame design is required.**

---

## GATE 3 — OPTICAL

| Requirement | Status | Blocker | Required evidence | Owner / action |
| --- | --- | --- | --- | --- |
| Display engine selection | PROVISIONAL | Lumus / DigiLens NDA required; mm-level dimensions not in public docs | NDA drawings | acquire NDA |
| Display FOV | DONE (per Lumus public: ~26° H) | depends on chosen engine | lumus_dk50.yaml, digilens_designlink.yaml | finalize engine |
| Display brightness | PROVISIONAL | not in public docs | NDA drawings | finalize engine |
| Eyebox | UNKNOWN | NDA | NDA drawings | finalize engine |
| Transparency | PROVISIONAL | per Lumus reflective waveguide ~80% (estimated) | NDA drawings | finalize engine |
| Optical engine -> V853 DSI | GREEN | V853 DSI directly drives the engine in the typical case | display-electrical-validation.yaml, display-bridge-evaluation.yaml | none |
| Custom panel driver (Linux DRM/KMS) | NOT DONE | engine-specific panel timing / DCS commands | panel driver C code | write driver when engine is selected |
| See-through color / monochrome | UNKNOWN | depends on chosen engine | NDA | finalize engine |

**GATE 3 status: NOT PASS. Display engine is undecided. NDA acquisition is the blocker.**

---

## GATE 4 — THERMAL

| Requirement | Status | Blocker | Required evidence | Owner / action |
| --- | --- | --- | --- | --- |
| V853 system power | PROVISIONAL | power-budget.yaml engineering estimates; ~20-40% error expected | power-budget.yaml | measure on prototype |
| Compute PCB thermal dissipation | NOT DONE | AXP2101 + BQ25185 + 2x MAX98390 + Wi-Fi/BT module + IMU + sensors | thermal simulation | thermal design |
| IR LED thermal load | NOT DONE | 6x VSMA1094750X02 at 50 mA each; thermal isolation from the battery and the cell | thermal simulation | thermal design |
| Battery thermal management | NOT DONE | TMP117 placement; cell thermal coupling | thermal test | thermal design |
| Speaker thermal load | NOT DONE | MAX98390 + speaker coil heat | thermal test | thermal design |
| Optical engine thermal load | NOT DONE | micro-OLED + LCoS heat in the front frame | thermal test (NDA required) | thermal design |
| Ambient operating temperature | DONE (per V853 datasheet) | none | -20 to +70 °C ambient | none |
| Junction temperature | DONE (per V853 datasheet) | none | -40 to +125 °C junction | none |

**GATE 4 status: NOT PASS. Thermal design has not started. The glasses' compute PCB will be in a 5-8 mm temple pod with limited heat dissipation; the system power (1.5-3.5 W typical, 4.1 W peak) must be dissipated through the temple surface area and through the PCB copper.**

---

## GATE 5 — POWER

| Requirement | Status | Blocker | Required evidence | Owner / action |
| --- | --- | --- | --- | --- |
| Power budget | DONE (engineering estimates) | ~20-40% error expected | power-budget.yaml | measure on prototype |
| Battery life | DONE (engineering estimates) | derived from power budget | README.md battery life table | measure on prototype |
| AXP2101 sequencing | DONE | matches V853 Figure 2-2 | v853-power-sequencing.yaml | set AXP2101 NVRAM |
| BQ25185 charging | DONE | none | power-tree.yaml | none |
| MAX17048 fuel gauge | DONE | none | power-tree.yaml | none |
| USB-C 5 V charging | DONE | none | usb-electrical-validation.yaml | none |
| Battery (2x LP402535 parallel) | PROVISIONAL | EEMB full datasheet PDF not retrieved | battery yaml files | acquire full EEMB datasheet |
| Safety: overcharge, overdischarge, OVP, OTP, NTC | DONE | none | power-tree.yaml, README.md | none |

**GATE 5 status: PASS at the architecture level. PROVISIONAL at the verification level (full EEMB datasheet PDF + prototype measurement needed).**

---

## GATE 6 — MANUFACTURING

| Requirement | Status | Blocker | Required evidence | Owner / action |
| --- | --- | --- | --- | --- |
| PCB fabricator (4-layer rigid-flex) | NOT STARTED | PCB design not started | PCB fab quote | design PCB first |
| PCB assembly (SMT + flex attachment) | NOT STARTED | PCB design not started | assembly quote | design PCB first |
| Lens cavity optical engine integration | NOT STARTED | display NDA + custom optical engine | NDA drawings | acquire NDA |
| Speaker back-volume tuning | NOT STARTED | temple pod design + acoustic test | acoustic test | acoustic engineering |
| Battery sourcing (2x LP402535) | PROVISIONAL | EEMB datasheet not retrieved | EEMB datasheet | acquire datasheet |
| Component sourcing (all) | PROVISIONAL | some component datasheets are datasheet summaries, not full PDFs | full PDFs for each component | acquire PDFs |
| Production-line programming (eMMC boot, FEL) | NOT STARTED | programming flow not defined | programming procedure document | define procedure |
| Test fixture (USB-C, pogo-pin debug connector) | NOT STARTED | test design not started | test fixture design | design fixture |

**GATE 6 status: NOT PASS. Manufacturing design has not started.**

---

## Summary

| Gate | Status |
| --- | --- |
| Gate 1 — Electrical | PASS at peripheral-block level; PROVISIONAL at per-ball level (V853/V853S_PINOUT.sls required) |
| Gate 2 — Mechanical | NOT PASS |
| Gate 3 — Optical | NOT PASS (display NDA required) |
| Gate 4 — Thermal | NOT PASS |
| Gate 5 — Power | PASS at architecture level; PROVISIONAL at verification level |
| Gate 6 — Manufacturing | NOT PASS |

**The project is NOT CAD-ready.**

**The project IS ready for:**

- Block-diagram-level architecture design (system-block-diagram.md is complete)
- Electrical feasibility validation at the peripheral block level (all subsystems GREEN or YELLOW)
- I2C bus address allocation (all 7 addresses unique)
- Power rail architecture (AXP2101 + BQ25185 + MAX17048)
- Boot architecture (eMMC + SD + FEL)
- AXP2101 rail configuration planning (per v853-power-sequencing.yaml)

**The project is NOT ready for:**

- Schematic capture (V853 per-ball pin map required)
- PCB layout (V853 per-ball pin map required)
- Mechanical placement (display NDA + custom frame design required)
- Thermal design (thermal simulation required)
- Manufacturing design (test fixture, programming flow required)

---

## Stop point

Per the user's instructions, this is the design-gate checklist deliverable. **No mechanical placement, no PCB design, no FreeCAD work, and no modification to the existing Wayfarer geometry, the working solid, or any existing glasses electronics has been started.** Awaiting your direction for the next step.
