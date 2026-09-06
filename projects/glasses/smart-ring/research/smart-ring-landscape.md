# Smart Ring Landscape — Reference Notes

**Project:** projects/glasses/smart-ring/
**Date:** 2026-09-05
**Status:** READ-ONLY research note.

This file collects short architecture notes for the 6 reference projects used in the comparative study (`reference-comparison.md`). The intent is reference-only; **no code or CAD is copied.**

---

## 1. Open Ring (stawiski/open-ring)

- **Source files referenced**: README.md (top-level), `/hardware/schematic_ring.pdf`, `/hardware/schematic_charger.pdf`.
- **Architecture**: 3-MCU approach
  - BLE SoC: Dialog DA14531 (BLE 5.1)
  - Capacitive-touch MCU: Atmel ATSAML10E16A
  - Charger MCU: STMicroelectronics STM32G030F6
  - PMIC: Texas Instruments BQ25125
  - Flash: Macronix MX25R2035
  - Antenna: PulseLARSEN BLE chip antenna
- **Form factor**: <3 mm ring thickness (wedding-band class); ring sizes US6–US13.
- **Charging**: wireless induction with a separate charger module (with its own MCU).
- **Limitations**: no PCB CAD / Gerbers in the repo; no battery / IMU specified; firmware is "pending deliverable" per the README; **AI/ML training restriction** at the top level.
- **License**: per-sub-directory (hardware + firmware separate). **Top-level restriction: this project cannot be used for AI/ML training without explicit written permission from the author.**

## 2. Intring (weierruisi/Intring)

- **Source files referenced**: README.md, `components/` (C source files for BLE HID, BLE OTA, air_mouse, gesture_detect, key, light_sleep, LSM6DS3TR), `tools/` (Python scripts for OTA and NN data collection).
- **Architecture**: single-SoC ESP32-C3 with:
  - IMU: LSM6DS3TR via I2C (SDA=GPIO18, SCL=GPIO19)
  - Touch keys A + B (GPIO4 + GPIO2) with pull-ups
  - Trackball + air-mouse mode (we have decided NOT to include the trackball; the air-mouse is also out of scope for V1)
- **Firmware**: Apache 2.0. **Reuse** the gesture vocabulary; re-implement the code.
- **Gestures**: 4-directional swipe (LEFT/RIGHT/UP/DOWN), double-click, long-press, A+B combo, mode-switch.
- **Low-power design**: dedicated `light_sleep` component handles sleep countdown and wake source management.
- **OTA**: dual-partition OTA via ESP-IDF v5.3.1; OTA control channel and data channel (UUIDs `0000fff1-` and `0000fff2-`); chunk-size 244; delay-ms 1.
- **Limitations**: ESP32-C3 is older and larger than nRF54L15; LSM6DS3TR is older than ICM-42688-P.

## 3. NERVA_Ring (NRG24/NERVA_Ring)

- **Source files referenced**: README.md (high level).
- **Architecture (inferred from the README)**:
  - PPG sensor (HR / SpO2)
  - Curved LiPo battery (~7 × 33 × 17.7 mm — approximate; the brief notes documentation has known discrepancies)
  - Flex PCB
  - Magnetic charging
  - BLE telemetry
  - Motion-artifact filtering for PPG
- **Limitations**: LICENSE file is **missing (404)**. **NO REUSE** until license is confirmed. Per the brief, documentation has known discrepancies.
- **Use as reference-only** for PPG sensor placement, curved battery form factor, flex PCB, and magnetic charging.

## 4. RRing (state-of-the-art/rring)

- **Source files referenced**: README.md.
- **Architecture**:
  - BLE SoC: DA14531-OG2 (WLCSP-17)
  - IMU: ICM-20948 (QFN-24) — 9-axis
  - Charger IC: LTC4124 (LQFN-12)
  - LDO: ADP160ACBZ-1.8-R7 (WLCSP-4)
  - BLE antenna: ANT3216LL00R2400A (SMD chip antenna)
  - 4-digit 7-segment LED driver: TCA6418EYFPR (DSBGA-25) + 30× IN-S21AT LEDs (0201)
  - Single button: KMT071NGJLHS (IP68 rated)
  - Custom vibro motor (no off-the-shelf part listed)
  - Battery: "TODO" (unknown)
- **Form factor**: tiny PCB in a 3D-printed ring.
- **Limitations**: LICENSE file is **missing (404)**. **NO REUSE** until license is confirmed. Battery is not specified. The haptic is custom. The 7-segment display is not part of our V1 design.
- **Use as reference-only** for compact DA14531 + 9-axis IMU + wireless charging + chip antenna.

## 5. Smart Ring Digital Twin (w1ne/smart-ring-digital-twin)

- **Source files referenced**: README.md, `firmware/nrf54l15/`, `src/` (C11 portable sensor manager), `app/sensor_demo/`.
- **Architecture**:
  - nRF54L15 (simulated) + Zephyr RTOS
  - Portable C11 sensor manager: `sm_rate_t` (drift-free rate control), `sm_ringbuf` (thread-safe ring buffers via port lock layer)
  - Capacities: 100 IMU samples, 20 temp samples
  - BLE pipeline: `sm_read` / `sm_peek`, `ble_batch` encoder, overwrite-oldest overflow policy, drop counter + sequence gap accounting
  - Firmware state machine: acquisition thread + BLE consumer thread
  - Test methodology: 43 test cases across 4 suites; host ctest (ASan/UBSan in `build-san`); ThreadSanitizer multi-threaded stress; Zephyr Ztest on `native_sim` and on-target
  - Build: CMake ≥ 3.16, any C11 compiler, no third-party deps; build flag `-DSM_SANITIZERS=ON`
- **Limitations**: LICENSE file is **missing (404)**. **Reference-only** for firmware patterns. Cannot copy code.
- **Use as reference-only** for the portable sensor manager, drop counter + sequence gap accounting, and the test methodology (host ctest + TSan + Ztest on `native_sim`).

## 6. Even openCFW (kalanihelekunihi/evenRealities-openCFW)

- **Source files referenced**: README.md.
- **Architecture**:
  - R1 (ring): Nordic nRF52840 (Cortex-M4F)
  - G2 (glasses): Ambiq Apollo510 (Cortex-M55)
  - Independent silicon / independent toolchains / independent reconstruction strategies
  - R1 firmware baseline: 2.2.6.0009
  - Firmware layout: `r1/include/openr1/`, `r1/src/`, `r1/platform/`, `r1/port/`, `r1/tests/`, `r1/tools/`, `r1/research/`, `r1/docs/`
  - Build outputs: portable host build, freestanding Cortex-M4 objects, linked nRF52840 image
  - Entry points: `r1-test`, `r1-sanitize`, `verify`, `SDK-image`
  - Vendor-attributable boundaries: Goodix biometrics (unsupported), GoMore health algorithms (unsupported), YHM power path (unsupported)
- **License**: MIT (for the clean-room code). Vendored upstream code retains its own terms. Official Even firmware payloads are EXCLUDED.
- **Use as reference-only** for the clean-room, honest-boundary philosophy. **DO NOT clone the R1's hardware or proprietary firmware.**
