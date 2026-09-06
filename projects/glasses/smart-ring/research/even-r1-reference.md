# Even R1 — Industrial-Design Reference (Reference-Only)

**Project:** projects/glasses/smart-ring/
**Date:** 2026-09-05
**Status:** READ-ONLY. Not a clone. The objective is "Build an original open smart ring inspired by the R1," not "Clone the R1."

This file documents what we can learn from the Even R1's observable behavior and the openCFW (kalanihelekunihi/evenRealities-openCFW) without copying any proprietary source. We use the R1 as the **industrial-design** and **interaction-philosophy** reference; we do NOT use it as a hardware-cloneable reference.

---

## 1. Industrial design (ID) principles we adopt

- **Smooth exterior**: the R1 has a smooth, seamless exterior with no visible screws, seams, or displays.
- **Rounded crown**: the R1 has a gently rounded, ergonomic crown that sits comfortably on the finger.
- **Discreet profile**: the R1 looks like jewelry, not a gadget.
- **Comfortable inner band**: the R1's inner band is contoured for all-day wear.
- **Sensor window**: the R1 has a small sensor window on the inner band for optical sensors (PPG, SpO2, etc.).

**Adopted for V1**: rounded crown, smooth exterior, discreet profile, comfortable inner band. The sensor window is OPTIONAL for V1 (no PPG).

## 2. Interaction philosophy (from the openCFW observable contract)

- **Tap, double-tap, long-press**: core input vocabulary. The R1 supports all three.
- **Swipe gestures**: 4-directional (left, right, up, down). The R1 supports all four.
- **Rotational gestures**: the R1 supports rotation around the finger's axis (clockwise / counter-clockwise). We will EVALUATE this for V1 (requires a high-ODR IMU + careful gesture recognition; see protocol/gesture-vocabulary.yaml).
- **Haptic confirmation**: the R1 uses silent vibro alarms. We adopt this pattern (see components/haptic-selection.yaml).
- **BLE communication**: the R1 is a Bluetooth device. We adopt BLE 5.x as the primary communication (see electrical/ble-interface.yaml).

## 3. What we do NOT take from the R1

- **NOT the silicon**: the R1 uses nRF52840 + Goodix biometrics + GoMore health + YHM power path. We use a different silicon (nRF54L15 for V1; see components/mcu-selection.yaml) and do NOT depend on Goodix biometrics, GoMore health, or the YHM power path.
- **NOT the firmware**: the R1's firmware is vendor-attributable. We write our own firmware (see firmware/).
- **NOT the GATT protocol**: the R1's GATT protocol is vendor-attributable. We design our own (see protocol/ring-gatt-spec.yaml).
- **NOT the PCB / mechanical design**: the R1's internal PCB and mechanical design are not published. We design our own (see mechanical/).
- **NOT the brand / name**: we do NOT use the Even Realities brand or name.

## 4. Engineering constraints we learn from the R1

- **The ring is a separate device from the glasses** (per the openCFW: "R1 and G2 are independent devices with separate silicon, separate toolchains, separate reconstruction strategies"). Our design follows this: the ring and the glasses are independent BLE devices.
- **The ring-glasses relationship is a clean-room re-implementation** (per the openCFW's "Honest boundary on unattributable behavior" philosophy). We adopt the same philosophy: where vendor-attributable functionality exists, we use pinned upstream sources; where it does not, we write our own.
- **The firmware must be testable from the host** (per the openCFW: "r1-test, r1-sanitize"). Our firmware follows the same testability requirement (see tests/).
- **The firmware must handle BLE contention honestly** (per the openCFW: drop counter + sequence gap accounting). Our firmware follows the same pattern (see firmware/architecture.md).

## 5. Observable capabilities (R1-specific, from the openCFW README)

- **Goodix biometrics** — unsupported boundary; we do NOT use Goodix biometrics in V1.
- **GoMore health algorithms** — unsupported boundary; we do NOT use GoMore health algorithms in V1. PPG is OPTIONAL for V1.
- **YHM power path** — unsupported boundary; we use the AXP2101 + BQ25185 + MAX17048 stack (already validated for the glasses) for the ring's power.

## 6. Summary

The Even R1 is the **industrial-design** and **interaction-philosophy** reference. The Even openCFW is the **firmware-architecture-philosophy** reference. We do NOT clone the R1's silicon, firmware, GATT protocol, PCB, or mechanical design. We design our own V1 ring, INSPIRED by the R1's design philosophy but with a different silicon (nRF54L15), different sensors, and different firmware.

**No proprietary code is copied. No proprietary CAD is reproduced. The R1 is a design inspiration, not a clone.**
