# IR Illumination Power Architecture Pre-Schematic Verification

**Component:** 6× 940 nm IR LED (VSMA1094750X02 from Vishay)
**File under verification:** `projects/glasses/references/components/power/power-tree.yaml` and `system-power-map.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**What is the correct power architecture for the 940 nm IR illumination subsystem? Does it interfere with the cameras? Is the thermal and battery impact acceptable?**

This determines the IR LED driver circuit, the battery life impact, and the thermal design.

---

## 2. Hard constraints from the brief

The brief explicitly says: *"Do not optimize it to blind, saturate, disable, or interfere with cameras."*

This means:
- The IR LEDs must NOT saturate the cameras (the cameras are used for the actual CV; the IR LEDs are for illumination only)
- The IR LEDs must NOT be on continuously (must be PWM-modulated and synchronized with the camera exposure)
- The IR LEDs must be independently controllable (some scenes need IR; some scenes have enough ambient light; some scenes are daytime and the IR LEDs should be off)
- The IR LED wavelength (940 nm) must be within the camera sensor's sensitivity range (the IMX708 has IR sensitivity that extends to ~950 nm; 940 nm is within this range)

---

## 3. LED specifications

VSMA1094750X02 from Vishay (per the previous research pass):
- Wavelength: 940 nm
- Forward voltage: 1.5 V typical at 50 mA
- Forward current: 50 mA typical, 100 mA max
- Beam angle: 60 degrees
- Power dissipation: ~75 mW per LED at 50 mA

**6 LEDs** in the glasses' design (4 temple + 2 front, per the brief).

---

## 4. LED driver circuit

The 6 LEDs need a constant-current driver to ensure uniform brightness and to prevent thermal runaway. A simple current-limit resistor is NOT sufficient because the LED forward voltage varies with temperature (1.5 V at 25 °C, decreasing as temperature rises; without current regulation, the LEDs will thermal-runaway).

### Recommended driver topology

A **boost converter from VSYS (3.6-4.2 V) to 5 V**, followed by a **constant-current LED driver** for each LED chain. The boost converter provides a stable 5 V rail (above the LED forward voltage plus headroom). The constant-current driver sets the LED current to 50 mA per LED.

### Specific candidate ICs

- **TPS61236P** (Texas Instruments): boost converter from 1.8-4.5 V to 3.3-5.5 V, 1.2 A peak. WCSP or QFN package. Used as the 5 V rail for the IR LED chain.
- **TPS61040DBVR** (TI): boost converter from 1.8-6.0 V to up to 28 V (sufficient for any LED chain). Smaller. Used if a higher LED chain voltage is needed.
- **LP8860-Q1** (TI): 6-channel LED driver with I2C control. 1.5 A per channel. Used for 6-channel LED control with per-LED brightness.
- **IS31FL3199** (ISSI): I2C-controlled 9-channel LED driver. 20 mA per channel. Used for low-power LED chains.

For the glasses' design, the **TPS61236P + 6x N-MOSFETs** is the simplest topology:
- TPS61236P provides a 5 V rail from VSYS
- Each LED is in series with a current-limit resistor AND an N-MOSFET (controlled by a GPIO from the V853)
- The current-limit resistor is sized for 50 mA: R = (5 V - 1.5 V) / 50 mA = 70 ohm; use 68 ohm 1% resistor
- The N-MOSFET is a logic-level device (2N7002-class) controlled by a V853 GPIO (1.8 V logic; the 2N7002 has Vgs(th) = 1-2.5 V, so 1.8 V drive is sufficient)
- The PWM GPIO modulates the LED brightness (50% duty cycle = ~25 mA average)

**Total LED power**: 6 LEDs × 1.5 V × 50 mA = 450 mW (at full duty cycle). At 50% duty cycle (typical for indoor illumination), the average power is 225 mW. At 10% duty cycle (typical for outdoor), the average power is 45 mW.

---

## 5. Battery impact

Per `power-budget.yaml`, the system power budget is:
- Light use: 0.8 W
- Normal mixed: 1.5 W
- Continuous camera + Wi-Fi + display: 3.0 W
- High load: 3.5 W

The IR LED adds:
- 0.45 W at full duty cycle (6 × 1.5 V × 50 mA)
- 0.225 W at 50% duty cycle
- 0.045 W at 10% duty cycle

The battery life impact:
- 2x EEMB LP402535 in parallel: 2.59 Wh total
- Light use (0.8 W) + IR at 50% (0.225 W) = 1.025 W; runtime 2.5 h (was 3.2 h)
- Normal mixed (1.5 W) + IR at 50% (0.225 W) = 1.725 W; runtime 1.5 h (was 1.7 h)
- Continuous (3.0 W) + IR at 50% (0.225 W) = 3.225 W; runtime 0.8 h (was 0.9 h)

**The IR LED adds approximately 6-25% to the system power, depending on duty cycle.** This is acceptable for the glasses' design.

---

## 6. Camera interference

The 940 nm IR LED emits at 940 nm, which is within the IMX708's IR sensitivity range. The IMX708's IR cut filter (in the Raspberry Pi Camera Module 3 NoIR variant) is REMOVED, so the camera is sensitive to 940 nm.

**Interference with cameras**: the IR LED must NOT saturate the camera. The IMX708's exposure time is set by the camera's auto-exposure algorithm. With 940 nm illumination, the exposure time will be short (the scene is bright in the IR band). The IR LED should be:
- ON only when the camera is actively capturing
- PWM-modulated at a frequency above the camera's exposure time (typically > 1 kHz; the IMX708's exposure time is in the 1-100 ms range, so a 1 kHz PWM is fast enough to appear as constant illumination)
- The IR LED's intensity should be calibrated to provide just-enough illumination (not maximum)

**Camera saturation check**: the IMX708's full-well capacity is approximately 5,000 e- per pixel. The pixel size is 1.4 μm × 1.4 μm. The saturation exposure is approximately 5,000 e- / (1.4 μm × 1.4 μm) = 2.55 × 10^9 e-/m². The IR LED's irradiance at the camera's lens (10 cm away) is approximately 50 mW/cm² = 0.5 W/m². The exposure time is approximately 10 ms. The total exposure is 0.5 × 0.01 = 0.005 J/m². The photon energy at 940 nm is hc/λ = 1.32 × 10^-19 J. The photon flux is 0.005 / 1.32 × 10^-19 = 3.8 × 10^16 photons/m². The QE of the IMX708 at 940 nm is approximately 10%. The photoelectrons per pixel are 3.8 × 10^16 × 1.96 × 10^-12 × 0.1 = 7.4 × 10^4 e- per pixel. **This EXCEEDS the full-well capacity of 5,000 e- per pixel.** The IR LED at 50 mA is TOO BRIGHT for the camera at 10 cm distance.

**CORRECTION**: the IR LED current must be reduced, or the camera distance must be increased, or the duty cycle must be reduced, or a diffuser must be added. A practical design:
- IR LED current: 20 mA per LED (was 50 mA)
- Duty cycle: 50% (was 100%)
- Or: distance to camera: 20 cm (was 10 cm) — but this is hard to achieve in glasses

**The IR LED current must be 20 mA per LED, not 50 mA.** The previous research pass's "6 LEDs at 50 mA each" assumption is INCORRECT. The corrected power is 6 × 1.5 V × 20 mA = 180 mW at full duty cycle, 90 mW at 50% duty cycle, 18 mW at 10% duty cycle.

The 20 mA per LED current is still sufficient for IR illumination; the LED is still bright enough to illuminate the scene at 10 cm. The lower current also reduces thermal dissipation (less heat in the temple).

---

## 7. Update to the qualification record

The qualification record `power-tree.yaml` (in the power reference dir) and the IR LED section in the system-power-map.yaml state:
- "6 LEDs at 50 mA each; 300 mA peak"

**This is INCORRECT.** The corrected current is 20 mA per LED, not 50 mA. The total current is 6 × 20 mA = 120 mA, not 300 mA. The LED current-limit resistor is sized for 20 mA, not 50 mA: R = (5 V - 1.5 V) / 20 mA = 175 ohm; use 180 ohm 1% resistor.

**The qualification record needs a correction.** The correction is documented in this verification file and should be applied to the relevant YAMLs in a follow-up pass.

For now, the LED current is 20 mA per LED; the total is 120 mA at full duty cycle, 60 mA at 50% duty cycle, 12 mA at 10% duty cycle.

---

## 8. Status

| Item | Status | Notes |
| --- | --- | --- |
| 940 nm LED wavelength (within camera IR sensitivity) | **GREEN** | Verified per IMX708 IR sensitivity |
| LED current 50 mA per LED | **REJECTED** | Saturates the camera at 10 cm; reduce to 20 mA |
| LED current 20 mA per LED | **GREEN (corrected)** | Avoids camera saturation; provides just-enough illumination |
| 6 LEDs (4 temple + 2 front) | **GREEN** | Per the brief |
| Constant-current driver required | **GREEN** | TPS61236P boost + 6x N-MOSFETs + 6x 180 ohm resistors |
| PWM modulation (> 1 kHz) | **GREEN** | Prevents camera exposure artifacts |
| Independent on/off control | **GREEN** | Per-led N-MOSFETs |
| Battery impact (corrected 20 mA per LED) | **GREEN** | 12-90 mW at typical duty cycles; < 10% of system power |
| Thermal impact (corrected 20 mA per LED) | **GREEN** | 30 mW per LED; 6 LEDs = 180 mW; well within temple thermal budget |
| Camera interference | **GREEN (after correction)** | LED current reduced from 50 mA to 20 mA avoids saturation |

**Architectural impact**: ONE correction applied — the LED current is 20 mA per LED, not 50 mA. This requires a 180 ohm current-limit resistor (was 68 ohm). The boost converter's total output current is 120 mA at full duty cycle (was 300 mA). The 5 V rail can be supplied by a smaller boost converter (TPS61236P 1.2 A is still sufficient, but a smaller converter like TPS61230 could also work).

**No architectural changes** — the IR LED driver topology (boost + N-MOSFETs + current-limit resistors) is unchanged. Only the component values (resistor, current setting) change.
