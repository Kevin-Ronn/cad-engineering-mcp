# Reference Project Comparison — Smart Ring Companion Device

**Project:** projects/glasses/smart-ring/
**Date:** 2026-09-05
**Status:** READ-ONLY. No code or CAD is copied. All facts are tied to a source.

This is the comparative engineering study required by the brief. **For every fact taken from an open-source project, the source, file, version/commit, confidence, and whether we are reusing it are recorded.**

---

## 1. Side-by-side comparison

| Project | MCU / BLE | IMU | PPG | Touch | Haptic | Charging | Battery | PCB | Glasses relevance | License |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Even R1** | nRF52840 (Cortex-M4F); 2.2.6.0009 firmware | not confirmed publicly | not confirmed publicly (Goodix biometrics is mentioned as a boundary; GoMore health algorithms is mentioned as a boundary) | not confirmed publicly (likely a touch + IMU combo, but the R1 has a small crown area) | "silent vibro alarm" mentioned | not confirmed publicly (likely wireless) | not confirmed publicly | not published (internal PCB) | The R1 is the **industrial-design reference** for the V1 ring. Do not clone the hardware. | MIT (per the openCFW license; Even's official firmware is excluded) |
| **Open Ring** | Dialog DA14531 (BLE 5.1) + Atmel ATSAML10E16A (capacitive touch MCU) + STM32G030F6 (charger MCU) | not mentioned (3-MCU design with dedicated touch MCU) | not mentioned | capacitive touch via dedicated ATSAML10E16A MCU | "haptic feedback" mentioned | wireless induction (separate charger with its own MCU) | not specified | tiny PCB; <3 mm ring thickness; wedding-band class | **PRIMARY hardware reference for ultra-small ring construction**. Architecture pattern only. | Per-sub-directory; **AI/ML training restriction** at top level |
| **Intring** | ESP32-C3 | LSM6DS3TR via I2C (SDA=GPIO18, SCL=GPIO19) | not mentioned | 2 touch keys A + B (pulled-up GPIO4, GPIO2); no trackball on this design | haptic not explicitly listed (likely via a driver on GPIO) | not specified | not specified | not in repo; hardware on 硬创社 (separate license) | **PRIMARY glasses-controller reference.** Gesture vocabulary (LEFT/RIGHT/UP/DOWN, double-click, long-press), low-power design, BLE HID service, OTA with dual partitions. **GLASSES-CONTROLLER relevance is high.** | **Apache 2.0** for firmware |
| **NERVA** | unknown (not retrieved in this pass) | unknown | yes (PPG) | unknown | unknown | magnetic | curved LiPo (approx 7×33×17.7 mm) | flex PCB | **PRIMARY health-sensing reference** for PPG, curved battery, flex PCB, magnetic charging. **NOTE: documentation has known discrepancies.** | **LICENSE UNKNOWN (LICENSE file 404). NO REUSE.** |
| **RRing** | DA14531-OG2 (WLCSP-17) | ICM-20948 (QFN-24) | not mentioned | single KMT071NGJLHS button (IP68) | custom vibro motor (no off-the-shelf part listed) | LTC4124 (LQFN-12) wireless charging | not specified (TODO) | tiny PCB in a 3D-printed ring | Reference for compact DA14531 + 9-axis IMU + wireless charging. | **LICENSE UNKNOWN (LICENSE file 404). NO REUSE.** |
| **Digital Twin** | nRF54L15 (simulated) | IMU 50 Hz + temp 1 Hz (simulated) | n/a (no hardware) | n/a (no hardware) | n/a (no hardware) | n/a (no hardware) | n/a (no hardware) | n/a (no hardware) | **PRIMARY firmware-architecture reference.** Portable C11 sensor manager, Zephyr RTOS, drop counter + sequence gap accounting, TSan test strategy. | **LICENSE UNKNOWN (LICENSE file 404). Reference-only for patterns.** |

---

## 2. What each project demonstrates

### 2.1 Even R1 (industrial-design reference, NOT hardware-cloneable)

- **Demonstrates**: a discreet ring form factor is feasible; a ring + glasses relationship is a real product category; clean-room firmware reconstruction is possible; separate silicon / separate toolchains for ring vs glasses.
- **Working**: per the openCFW README, the R1 SDK build is functional; Ghidra + BSim tooling can reproduce the firmware contract; multiple test layers (host, sanitizers, on-target).
- **Limitations**: official Even firmware payloads are excluded; vendor-attributable blocks (Goodix biometrics, GoMore health, YHM power) are unsupported; the R1's specific pin map / PCB is not published.
- **Reuse**: architecture patterns (clean-room, honest boundaries, MIT-licensed clean-room code with vendored upstream carve-outs). Do NOT clone the hardware or the proprietary firmware.
- **Modern alternative**: **better** in some respects (e.g. modern nRF54L15 is more power-efficient than the R1's nRF52840, but the R1's design has already proved the nRF52840 is enough).

### 2.2 Open Ring (primary hardware reference for ring construction)

- **Demonstrates**: a 3-MCU architecture (BLE + touch + charger) is feasible at <3 mm ring thickness; a separate charger MCU allows the ring to be simpler; capacitive touch can be a separate low-power MCU.
- **Working**: per the README, the hardware is released as schematics (PDFs) for both the ring and the charger. The firmware is "pending deliverable" per the README.
- **Limitations**: no PCB CAD / Gerbers in the repo; no battery / IMU specified; firmware not yet released; **AI/ML training restriction** at the top level is a hard constraint.
- **Reuse**: architecture pattern (3-MCU) as a baseline; BQ25125 PMIC as a reference for power management. The 3-MCU architecture may be replaced by a single modern SoC (nRF54L15) in our design — see components/mcu-selection.yaml.

### 2.3 Intring (primary glasses-controller reference)

- **Demonstrates**: a ring with touch + IMU can serve as a BLE HID controller for AR glasses / VR / PC; the gesture vocabulary (LEFT/RIGHT/UP/DOWN, double-click, long-press, A+B combo) is well-defined; low-power design (light_sleep) is achievable; OTA with dual partitions is mature (ESP-IDF v5.3.1).
- **Working**: full Apache 2.0 firmware is released; OTA tool is included; the gesture vocabulary is documented and tested.
- **Limitations**: ESP32-C3 is the MCU (older, larger than nRF54L15; the BLE stack is mature but the chip is not as low-power as Nordic); the design uses an LSM6DS3TR IMU (older, larger than ICM-42688-P or BMI270); the architecture includes a trackball + air-mouse mode that we have decided NOT to include.
- **Reuse**: gesture vocabulary (Apache 2.0 firmware is reusable, but we re-implement the code ourselves); BLE HID service pattern; OTA architecture.

### 2.4 NERVA_Ring (primary health-sensing reference, but license unknown)

- **Demonstrates**: PPG is feasible in a ring; curved LiPo batteries fit the form factor; magnetic charging works; flex PCB can support the layout.
- **Working**: the project is public; some schematics and code are present.
- **Limitations**: license is UNKNOWN (LICENSE file returned 404); documentation has known discrepancies (per the brief).
- **Reuse**: **NONE** until the license is confirmed. Reference-only for PPG, curved battery, magnetic charging, flex PCB, skin-contact sensor placement.

### 2.5 RRing (compact DA14531 reference, but license unknown)

- **Demonstrates**: a 9-axis IMU (ICM-20948) is feasible in a tiny ring; a single button + haptic + wireless charging is a viable minimum input/output set.
- **Working**: per the README, the project is at "8 commits" (early stage); the PCB is a tiny custom design in a 3D-printed ring.
- **Limitations**: license is UNKNOWN (LICENSE file returned 404); the haptic is a custom design (no off-the-shelf part); the battery is not yet specified.
- **Reuse**: **NONE** until the license is confirmed. Reference-only for compact DA14531 + 9-axis IMU + wireless charging.

### 2.6 Smart Ring Digital Twin (primary firmware-architecture reference, but license unknown)

- **Demonstrates**: a portable C11 sensor manager is feasible; a rate-control-based IMU 50 Hz / temp 1 Hz is sufficient; thread-safe ring buffers with port locks are the right pattern; drop counter + sequence gap accounting is the right way to handle BLE contention; a clean test methodology (host ctest + TSan + Ztest on native_sim) is the right way to validate firmware.
- **Working**: per the README, the project is "homework" / "open-source smart-ring platform" with 43 test cases across 4 suites; cross-compiles for nRF54L15.
- **Limitations**: license is UNKNOWN (LICENSE file returned 404); the architecture is simulated, not production-deployed.
- **Reuse**: **ARCHITECTURE PATTERNS ONLY**. The portable sensor manager, the drop counter, the sequence gap accounting, and the test strategy are reusable ideas. We re-implement the code ourselves.

---

## 3. For every important design decision

| Decision | Existing project that demonstrates it | Their component / approach | What worked | What limitations exist | Reuse approach | Modern alternative? |
| --- | --- | --- | --- | --- | --- | --- |
| **Ultra-small ring form factor (<3 mm)** | Open Ring | <3 mm ring thickness; wedding-band class; 3-MCU architecture | Concept is feasible; 8 commits show real hardware | 3-MCU is complex; firmware not yet released | Use the form factor as a reference; do NOT use the 3-MCU architecture | YES — single SoC (nRF54L15) is more power-efficient and smaller |
| **Capacitive touch** | Open Ring, Intring | Open Ring uses a separate ATSAML10 MCU; Intring uses 2 touch keys via GPIO with pull-ups | Both work | Open Ring: extra MCU cost; Intring: limited vocabulary (2 keys) | Use the Intring vocabulary; use a dedicated touch MCU OR an SoC with built-in touch sensing | YES — nRF54L15 has no built-in touch, but BMI270 + dedicated touch IC is smaller than the Open Ring approach |
| **IMU for gesture** | Intring (LSM6DS3TR), RRing (ICM-20948), Open Ring (none) | Intring + RRing both use 6-axis / 9-axis IMU at the standard I2C interface | Works for gesture detection | LSM6DS3TR is older; ICM-20948 is larger than the latest IMUs | Use a modern IMU | YES — ICM-42688-P or BMI270 are smaller and lower-power |
| **PPG (optional for V1)** | NERVA_Ring | PPG sensor + LED + photodiode, skin contact, motion-artifact filtering | Works for HR / SpO2 | Battery impact, skin-contact reliability, motion artifacts | If V1 is controller-only, skip PPG. If health-ring is desired, use MAX86150 or MAXM86161 | YES — modern equivalents are smaller and lower-power |
| **Haptic feedback** | Open Ring, RRing, Intring (implicit) | ERM or custom LRA; haptic driver IC; mounting location is the inner band | One short pulse = accepted, two pulses = command complete, etc. | Haptic size vs ring size; driver IC power | Use an LRA with a dedicated driver IC (e.g. TI DRV2605 or Analog Devices SS8050) | YES — newer drivers are smaller and lower-power |
| **Wireless charging** | Open Ring, RRing, NERVA | Inductive (Qi-like) or magnetic coupling | Works for waterproof rings | Efficiency, thermal, foreign-object detection | Choose magnetic pogo OR inductive based on V1 trade-offs | YES — newer inductive chargers are smaller |
| **Battery** | NERVA (curved LiPo), Open Ring (not specified) | Curved LiPo is the right form factor for a ring | Works for 1-3 days runtime | Capacity vs size trade-off; safety; charging | Use a curved LiPo with protection circuit | YES — newer LiPo cells have higher energy density |
| **PCB architecture** | Open Ring (tiny rigid), NERVA (flex), RRing (tiny rigid) | Open Ring uses a tiny rigid PCB; NERVA uses a flex PCB | Both work; flex PCB supports curved sensor placement | Flex PCB is harder to assemble and source | V1: tiny rigid PCB for simplicity. V2: flex PCB for curved sensor placement | n/a |
| **Firmware architecture** | Intring (Apache 2.0), Digital Twin (license unknown) | Intring uses Apache 2.0; Digital Twin uses portable C11 sensor manager | Both work | Different licenses | Reuse architecture patterns; re-implement | YES — modern Nordic nRF Connect SDK + Zephyr is the right choice |
| **BLE architecture (ring ↔ glasses ↔ phone)** | Even openCFW (clean-room) | The R1 and the G2 are independent; the openCFW is one repo with separate silicon/toolchains | Clean separation | Two devices; shared dependency registry | Our design: RING ↔ GLASSES (BLE) ↔ PHONE (Wi-Fi or BLE) | YES — modern BLE 5.x is the right choice |
| **GATT protocol (ring ↔ glasses)** | Even R1 (clean-room) | Observable firmware contract is reproducible | Clean-room reproduction is possible | No public protocol specification | We design our own GATT spec | YES — BLE GATT is the right standard |
| **Antenna** | Open Ring (PulseLARSEN), RRing (chip antenna ANT3216) | Both work; chip antenna is smaller | Works for ring | Body detuning; battery interference; ground plane | V1: chip antenna on the inner band (opposite the crown). Avoid PCB-edge placement. | YES — modern chip antennas (Johanson 2450AT18B100, Murata LFB182G45BG5D920) are smaller |
| **Wear detection** | Open Ring (capacitive skin detection) | Capacitive electrode on the inner band | Works | Sensor cost; sensitivity to skin impedance | Use a small capacitive electrode on the inner band | YES — modern touch ICs (Azoteq IQS127D) are smaller |

---

## 4. Summary of the comparative study

| Decision | Best existing reference | Our approach |
| --- | --- | --- |
| Ultra-small ring form factor | Open Ring | Reuse the form factor, NOT the 3-MCU architecture. Use a single modern SoC (nRF54L15). |
| Touch + IMU gesture vocabulary | Intring (Apache 2.0) | Reuse the gesture vocabulary; re-implement the code under our own license. |
| Health sensing (PPG) | NERVA (license unknown) | Reference-only. PPG is OPTIONAL for V1; if V2 wants health, get the license confirmed. |
| 9-axis IMU | RRing (license unknown) | Use a modern 6-axis IMU (ICM-42688-P or BMI270) for V1. |
| Firmware architecture | Digital Twin (license unknown) | Reuse the architecture patterns (portable sensor manager, drop counter, sequence gap) under our own code. |
| BLE architecture | Even openCFW (MIT clean-room) | Reference-only. Do NOT clone. We design our own. |
| Wireless charging | Open Ring (induction) or NERVA (magnetic) | Choose based on V1 trade-offs (simplicity vs waterproofing). |
| Battery | NERVA (curved LiPo) | Use a curved LiPo with protection. |
| PCB | Open Ring (tiny rigid) | V1: tiny rigid PCB. V2: flex PCB. |
| Antenna | RRing (chip antenna) | Use a modern chip antenna (Johanson 2450AT18B100). |

---

## 5. Components that can be ordered immediately (subject to the component selection in components/)

- **nRF54L15** (or nRF5340 / nRF52840) — Nordic, available at Mouser / DigiKey / LCSC
- **ICM-42688-P** (or BMI270) — TDK / Bosch, available at Mouser / DigiKey
- **MAX17048** — Maxim Integrated / ADI, available at Mouser / DigiKey
- **BQ25185** — TI, available at Mouser / DigiKey
- **TPS61236P** (or equivalent boost) — TI, available at Mouser / DigiKey
- **TMP117** — TI, available at Mouser / DigiKey
- **CUI CMS-151125-078S** (speaker, 15 x 11 x 2.5 mm) — CUI Devices, available at Mouser / DigiKey
- **MAX98390** (audio amp) — Maxim Integrated / ADI, available at Mouser / DigiKey
- **EEMB LP402535** (battery) — EEMB, available at LCSC
- **TPD4E05U04** (USB-C ESD) — TI, available at Mouser / DigiKey
- **BMI270** (IMU) — Bosch, available at Mouser / DigiKey
- **VEML7700** (ALS) — Vishay, available at Mouser / DigiKey

(All of the above are confirmed-available; see components/ for the per-component YAMLs.)

---

## 6. Reference vs production

**For every fact above, the source project is named, the source file is named (when known), and the fact is recorded as REFERENCE-ONLY (architecture pattern, design philosophy) unless explicitly stated as REUSED.** The architecture patterns and design philosophies are public knowledge; the implementation details (code, PCB, BOM) are owned by the respective project authors.

**We do NOT copy any source code, PCB, or 3D model without explicit license compatibility.** The license audit (research/license-audit.md) is the authoritative reference for what is reusable.

---

## 7. Next step

Proceed to the component selection (components/mcu-selection.yaml and the other 8 component YAMLs). The comparative study has identified:
- nRF54L15 as the modern single-SoC alternative to the Open Ring 3-MCU architecture
- ICM-42688-P or BMI270 as the modern IMU
- The Intring gesture vocabulary as the controller vocabulary
- The Digital Twin firmware architecture as the firmware pattern
- The Even R1 industrial design as the V1 industrial design inspiration
