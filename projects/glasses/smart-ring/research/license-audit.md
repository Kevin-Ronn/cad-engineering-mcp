# License Audit — Open-Source Smart-Ring References

**Project:** projects/glasses/smart-ring/ — open-source smart-ring companion device
**Date:** 2026-09-05
**Status:** READ-ONLY. No CAD / PCB / STL / FreeCAD files were modified. No manufacturing files generated.

This file documents the licenses of each open-source reference project, what is reusable, and what is reference-only. **No code or CAD is copied without explicit license compatibility.**

---

## Summary table

| Project | Repo | License | Hardware | Firmware | 3D Models | CAD/Schematics | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Open Ring | stawiski/open-ring | Per-sub-directory (hardware + firmware separate) + AI/ML training restriction at the top level | TBD per sub-license | TBD per sub-license | TBD | TBD | **Cannot use for AI/ML training** without explicit written permission from the author (Mikolaj Stawiski / Joel Meredith). Hardware is schematics-only release, no CAD/source PCB. |
| Intring | weierruisi/Intring | **Apache License 2.0** | Hardware licensed separately on 硬创社 (not in this repo) | **Apache 2.0** — can be reused with attribution | n/a (no models in this repo) | n/a | Firmware is the main reusable artifact. **Hardware is not in this repo** and is licensed separately. |
| NERVA_Ring | NRG24/NERVA_Ring | LICENSE file is **missing (404)** — license status is **NOT STATED** in the repo root | Treat as UNKNOWN | Treat as UNKNOWN | Treat as UNKNOWN | Treat as UNKNOWN | **NO REUSE** until license is confirmed. Need to contact the project author. **Also: documentation contains known discrepancies between older docs and the current PCB** (per the brief). |
| RRing | state-of-the-art/rring | LICENSE file is **missing (404)** — license status is **NOT STATED** | Treat as UNKNOWN | Treat as UNKNOWN | UNKNOWN | Treat as UNKNOWN | **NO REUSE** until license is confirmed. |
| Smart Ring Digital Twin | w1ne/smart-ring-digital-twin | LICENSE file is **missing (404)** — license status is **NOT STATED** | n/a (no hardware) | Treat as UNKNOWN (no LICENSE file in repo) | n/a | n/a | **NO REUSE** until license is confirmed. **However, the architecture descriptions and patterns are public knowledge** and can be referenced (not copied). |
| Even openCFW | kalanihelekunihi/evenRealities-openCFW | **MIT License** (with the carve-outs noted below) | n/a (no hardware) | **MIT-licensed clean-room code** (R1-specific behavior, configuration, ports, safety corrections). Vendored upstream code (g2flash-derived gesture/patch sources, QP/C) retains its GPL terms. Official Even Realities firmware payloads are EXCLUDED from the MIT grant and the public community ZIP. | n/a | n/a | **Reference-only for architecture patterns.** Do NOT copy Even's proprietary code. Do NOT clone the R1 hardware. The objective is to be INSPIRED, not to clone. |

---

## What we can reuse

| Project | What we can reuse | How |
| --- | --- | --- |
| Open Ring | Conceptual architecture: 3-MCU approach (DA14531 BLE + SAMSUNG capacitive-touch + STM32 charger), BQ25125 power management, BGA-style tight ring layout | Architecture pattern only. Our component selection is independent. **Cannot use for AI/ML training.** |
| Intring | **Firmware under Apache 2.0**: gesture vocabulary (LEFT/RIGHT/UP/DOWN), low-power `light_sleep` component, BLE HID service, OTA with dual partitions, gesture detection state machine, debouncing + combo events, LED state machine | Reuse architecture patterns and re-implement code ourselves. Do NOT copy source verbatim. Note: Intring uses TFLite ML model for gesture detection — we are starting with deterministic gesture recognition per the brief. |
| NERVA_Ring | **NOT REUSABLE** until license is confirmed. **Reference-only** for PPG sensor placement, curved LiPo battery, magnetic charging architecture, motion-artifact filtering, flex PCB. |
| RRing | **NOT REUSABLE** until license is confirmed. **Reference-only** for DA14531, ICM-20948 IMU, LRA/EM haptic, wireless charging. |
| Smart Ring Digital Twin | **Reference-only** for firmware architecture: portable C11 sensor manager (`sm_rate_t`, `sm_ringbuf`), 50 Hz IMU / 1 Hz temp rate, drop counter + sequence gap accounting, Zephyr RTOS + Ztest + TSan test strategy, dual-port thread-safe pattern. Cannot copy code (no license). |
| Even openCFW | **MIT-licensed clean-room code** can be REUSED with attribution, BUT: (1) the R1-specific behavior is for the R1's hardware (nRF52840, Goodix biometrics, GoMore health, YHM power path) — not ours; (2) we are NOT cloning the R1. Reference the architecture and design philosophy, do NOT copy the code. |

---

## Attribution requirements

For any reuse, the following must accompany the glasses ring design:

- **Open Ring**: per-sub-directory license must be preserved; AI/ML training restriction is global and applies to **any** use of Open Ring's data.
- **Intring**: Apache 2.0 NOTICE must be preserved; if a NOTICE file exists, it must be included in derivative works.
- **Smart Ring Digital Twin**: license is unknown; treat as reference-only and do NOT copy code. If reuse is desired, contact the project author first.
- **NERVA_Ring** and **RRing**: license is unknown; treat as reference-only and do NOT copy code or hardware.
- **Even openCFW**: MIT copyright notice must be preserved; do NOT use Even's proprietary code or hardware; reference architecture and design philosophy only.

---

## Recommendations

1. **Use Intring's gesture vocabulary and BLE HID service as a reference** for the gesture vocabulary. Re-implement the code ourselves.
2. **Use Open Ring as a hardware reference** for the 3-MCU approach (BLE + touch + charger), but evaluate whether modern single-SoC alternatives (nRF54L15, nRF5340) can replace it.
3. **Use Smart Ring Digital Twin's firmware architecture patterns** (portable sensor manager, drop counter + sequence gap accounting) as inspiration for our own firmware.
4. **Use Even openCFW as a reference for the ring↔glasses protocol philosophy** (clean-room re-implementation, honest boundary on unattributable behavior, separate silicon / separate toolchains) — but do NOT clone the R1's hardware.
5. **NERVA_Ring and RRing** are reference-only for hardware patterns (PPG, curved battery, magnetic charging) until their licenses are confirmed.
6. **No code or CAD is copied** without explicit license compatibility.

---

## What we explicitly will NOT do

- Do not copy any source code verbatim.
- Do not reproduce the Even R1's internal PCB or mechanical design.
- Do not use any open-source project data for AI/ML model training without explicit written permission (per Open Ring's top-level restriction).
- Do not claim any open-source project's license permits use of hardware designs that are licensed on a different platform (per Intring: hardware is on 硬创社, not in the GitHub repo).
- Do not make medical claims about the ring (per the brief).
- Do not claim IP-rating without testing (per the brief).
