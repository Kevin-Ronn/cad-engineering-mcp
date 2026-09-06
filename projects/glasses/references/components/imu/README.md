# IMU + Magnetometer — Reference Index

This directory holds component references for the 6-axis IMU and
optional 9-axis magnetometer for the V853 smart glasses.

The existing authoritative frame geometry and PCB were not modified
during this research pass.

---

## Contents

| File | Description |
| --- | --- |
| `bosch_bmi270.yaml` | Bosch BMI270 6-axis, 2.5 x 3.0 x 0.8 mm LGA, I2C/SPI, ~685 uA active. Primary candidate. |
| `bosch_bmi323.yaml` | Bosch BMI323 6-axis, 2.0 x 2.0 x 0.8 mm LGA, I2C/SPI, ~600 uA active, newer generation. |
| `tdk_icm_42688_p.yaml` | TDK ICM-42688-P 6-axis, 2.5 x 3.0 x 0.8 mm LGA, 32 kHz ODR, ~700 uA active, on-chip AP. |
| `st_lsm6dso.yaml` | ST LSM6DSO 6-axis, 2.5 x 3.0 x 0.83 mm LGA, I2C/SPI, ~550 uA active. |
| `st_ism330dhcx.yaml` | ST ISM330DHCX 6-axis, 2.5 x 3.0 x 0.83 mm LGA, industrial temp, ML core, ~700 uA. |
| `st_asm330lhh.yaml` | ST ASM330LHH 6-axis, 2.5 x 3.0 x 0.83 mm LGA, automotive AEC-Q100, ML core, ~800 uA. |
| `bosch_bmm150.yaml` | Bosch BMM150 3-axis magnetometer, ~2.0 x 2.0 mm, optional for 9-axis fusion. |

---

## Headline comparison

| Spec | Bosch BMI270 | Bosch BMI323 | TDK ICM-42688-P | ST LSM6DSO | ST ISM330DHCX | ST ASM330LHH |
| --- | --- | --- | --- | --- | --- | --- |
| Dimensions (mm) | 2.5 x 3.0 x 0.8 | 2.0 x 2.0 x 0.8 | 2.5 x 3.0 x 0.8 | 2.5 x 3.0 x 0.83 | 2.5 x 3.0 x 0.83 | 2.5 x 3.0 x 0.83 |
| Accel range (g) | 2, 4, 8, 16 | 2, 4, 8, 16 | 2, 4, 8, 16, 32 | 2, 4, 8, 16 | 2, 4, 8, 16 | 2, 4, 8, 16 |
| Gyro range (dps) | 125-2000 | 125-2000 | 15.625-2000 | 125-2000 | 125-4000 | 125-4000 |
| ODR max (Hz) | 6400 gyro | 6400 gyro | 32000 gyro | 6664 | 6664 | 6664 |
| Supply (V) | 1.71-3.6 | 1.71-3.6 | 1.71-3.6 | 1.71-3.6 | 1.71-3.6 | 1.71-3.6 |
| Active current (uA) | 685 | 600 | 700 | 550 | 700 | 800 |
| Sleep current (uA) | 3 | 3 | 8 | 3 | 3 | 3 |
| FIFO (bytes) | 1024 | 1024 | 2048 | 1024 | 4096 | 4096 |
| Op. temp (°C) | -40 to +85 | -40 to +85 | -40 to +85 | -40 to +85 | -40 to +105 | -40 to +105 |
| Price (USD) | 1.91-3.00 | 2-4 | 4-7 | 2-4 | 6-10 | 6-12 |
| Linux driver | bmi160 / bmi270 | verify | icm42600 | st_lsm6dsx | st_lsm6dsx | st_lsm6dsx |
| Confidence | HIGH | HIGH | HIGH | HIGH | HIGH | HIGH |

---

## Magnetometer analysis

The brief asks whether a magnetometer is actually useful for this
project. The answer is **NO for the glasses primary use case**.

**Why a magnetometer is not needed for the V853 smart glasses:**

1. The glasses primary use cases are head-motion tracking (display stabilization, gesture sensing). A 6-axis IMU (accel + gyro) is sufficient.
2. Compass heading is rarely needed for head-mounted displays — the user is looking at a world-fixed display, not navigating with a magnetic compass.
3. A magnetometer is sensitive to nearby metal and electromagnetic interference, which is a problem in a glasses chassis with speakers, IR LEDs, and a Wi-Fi/BT antenna.
4. The phone (which the glasses are tethered to) has a 9-axis IMU + magnetometer already; the glasses can fuse their 6-axis IMU with the phone's magnetometer over BT if a heading reference is needed.
5. A magnetometer adds cost, area, and current consumption (BMM150 is ~0.5 mA active).

**Conclusion: 6-axis IMU only. No magnetometer.**

---

## Recommendation

**PRIMARY: Bosch BMI270** — 2.5 x 3.0 x 0.8 mm LGA, 685 uA active, 3 uA sleep, 1024-byte FIFO, 2 interrupt pins, on-chip gesture and activity recognition firmware, mature Linux driver, well-known, $1.91-3.00, used in Meta Ray-Ban / Snap Spectacles class. Best for the V853 smart glasses.

**SECONDARY: ST LSM6DSO** — same 2.5 x 3.0 mm LGA package, 550 uA active (lower than BMI270), 1024-byte FIFO, mature Linux st_lsm6dsx driver (also covers ISM330DHCX, ASM330LHH). Competitive pricing ($2-4).

**SECONDARY (smaller): Bosch BMI323** — 2.0 x 2.0 mm, smaller than BMI270, lower power, newer generation. Best if the compute-PCB area is tight.

**ALTERNATIVE: TDK ICM-42688-P** — 32 kHz ODR, 32 g accel range, on-chip AP. Best for advanced gesture / head-tracking pipelines where the on-chip processor offloads the V853.

**NOT RECOMMENDED: ST ASM330LHH** — automotive grade (AEC-Q100), overkill for consumer smart glasses.

**NO MAGNETOMETER** — see analysis above.

---

## Glasses-specific considerations

1. **Head-motion tracking**: 6-axis IMU at 100-200 Hz ODR is sufficient for head-orientation estimation. Display stabilization (electronic image stabilization) typically uses a 6-axis IMU at 200-1000 Hz.
2. **Gesture sensing**: 6-axis IMU at 50-100 Hz with on-chip gesture recognition (BMI270, LSM6DSO, ISM330DHCX) can recognize head nod, head shake, double-tap on the frame. The on-chip recognition reduces host CPU load.
3. **Activity classification**: optional, used for the phone to know if the user is sitting / walking / running. Uses 6-axis IMU at 50 Hz with on-chip classifier.
4. **Power**: the IMU is always-on. With 3 uA sleep, the IMU contributes negligible standby current. With 550-700 uA active, the IMU contributes 1-1.5 mW of average power (assuming 10% duty cycle at 50 Hz ODR).
5. **Placement**: the IMU should be placed on the compute-PCB (temple), close to the V853 SoC. The compute-PCB has 5-8 mm of headroom inside the temple; the 0.8 mm IMU package fits comfortably.

---

## Open items

- [ ] Confirm V853 I2C bus assignment for the IMU (the V853 has 2x I2C controllers + a separate sensor interface; verify which one is used)
- [ ] Decide on the IMU interrupt routing: connect IMU INT1/INT2 to V853 GPIO for low-latency wake events
- [ ] Decide on the IMU placement relative to the magnetic components (speakers, IR LEDs, Wi-Fi antenna) — magnetometer-sensitive; the 6-axis IMU is less affected
- [ ] Validate BMI270 on-chip gesture recognition firmware with the chosen use cases (head nod, head shake, double-tap)

---

## Stop point

Per the user's instructions, this is the IMU reference-acquisition
deliverable. No mechanical placement, no PCB design, no FreeCAD
work, and no modification to the existing glasses geometry, the
working solid, or any glasses electronics has been started. Support
components and system-interface / BOM-status files are next.
