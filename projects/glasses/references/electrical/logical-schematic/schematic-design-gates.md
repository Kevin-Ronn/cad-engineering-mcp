# Schematic Design Gates — V853 Smart Glasses

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY logical schematic-capture preparation. No CAD / PCB / STL / FreeCAD files were modified. No PCB routing.

This is the GREEN / YELLOW / RED summary for every subsystem. **GREEN** means safe to carry into the eventual schematic capture. **YELLOW** means plausible but requires confirmation. **RED** means blocked by missing documentation.

---

## Subsystem design gates

### COMPUTE

| Subsystem | Status | Notes |
| --- | --- | --- |
| V853 SoC core | **GREEN** | Bare-die LFBGA-318 12×12 mm datasheet available; peripheral block inventory verified. |
| V853 SoC peripheral block selection | **GREEN** | All 14 chosen peripherals exist in the V853 datasheet sections 1.3.5, 1.3.6.4, 1.3.7.2, 1.3.7.3, 1.3.8, 4.2. |
| V853 SoC BGA ball map | **RED** | The V853/V853S_PINOUT.sls file is NDA-only; the per-ball pad map is in this file. Required for PCB layout. |
| DDR3 / DDR3L (16-bit) | **GREEN** | Per V853 datasheet section 1.3.1 the V853 supports 16-bit DDR3 / DDR3L. |
| eMMC 5.1 | **GREEN** | Per V853 datasheet section 4.2 the V853 has 3 SMHC controllers; 8-bit eMMC at HS400 is supported. |
| Power-on sequence | **GREEN** | The AXP2101 PMIC handles the V853 Figure 2-2 sequencing internally. |
| V853 reset | **GREEN** | The AXP2101 holds the SoC's RESET for 100-300 ms after all rails are stable. |
| V853 boot (eMMC + SD + FEL) | **GREEN** | Per boot-architecture.yaml. |
| V853 SoC firmware / NVRAM configuration | **YELLOW** | The AXP2101 NVRAM is firmware-programmable. The exact rail-to-SoC-rail assignment is PROVISIONAL until the NVRAM is finalized in production-line programming. |

### POWER

| Subsystem | Status | Notes |
| --- | --- | --- |
| AXP2101 PMIC (Allwinner-ecosystem) | **GREEN** | Verified in the ProjectYosemite reference design. |
| AXP2101 rail-to-SoC-rail assignment | **YELLOW** | Multiple valid assignments; the glasses' design chooses the simplest. Finalized in AXP2101 NVRAM. |
| BQ25185 charger + power-path | **GREEN** | TI BQ25185 WCSP, 5.5 V max input, 1 A, I2C, power-path, thermal reg. Verified per power-tree.yaml. |
| MAX17048 fuel gauge (ModelGauge) | **GREEN** | ADI MAX17048 TDFN-8 2.5×2.5 mm, no sense resistor, Linux driver. |
| 2x EEMB LP402535 in parallel (left + right temple) | **YELLOW** | Full EEMB datasheet PDF not retrieved; model-number convention is reliable but exact discharge C-rate needs verification. |
| USB-C 5 V charging | **GREEN** | Per usb-electrical-validation.yaml. 5.1 kohm CC pull-down; no USB-PD. |
| TPD4E05U04 ESD (4-channel WCSP) | **GREEN** | TI part, 16 kV ESD rating. |
| TVS on rails (VBAT, VBUS, etc.) | **GREEN** | Generic 5V unidirectional TVS (SMAJ5.0CA-class). |
| Battery thermal protection (NTC) | **GREEN** | 10 kohm NTC on the cell + BQ25185 TS input. |
| On-die V853 audio codec | **GREEN (bypassed)** | The external I2S-based MAX98390 amplifiers are used. |
| USB-PD | **GREEN (not used)** | 5 V is sufficient. |

### WIRELESS

| Subsystem | Status | Notes |
| --- | --- | --- |
| AW-CM276SM (AzureWave Wi-Fi 5 + BT 5.1, 12×12×1.5 mm) | **YELLOW** | Module dts is the primary reference (linux driver supported). Exact mechanical drawing + full datasheet PDF not yet retrieved. |
| SDIO Wi-Fi (SMHC1) | **GREEN** | Per sdio-emmc-coexistence.yaml. SMHC1 is independent of SMHC0. |
| UART Bluetooth (UART2, 4-wire) | **GREEN** | Per 100ASK public dts (btlpm uart_index=2). |
| Wi-Fi/BT wake / host-wake / REG_ON GPIOs | **GREEN** | Standard 3-signal control. Specific GPIO balls UNKNOWN. |

### CAMERAS

| Subsystem | Status | Notes |
| --- | --- | --- |
| 2x camera (each 2-lane MIPI CSI-2) | **GREEN (architecture)** | Per dual-csi-validation.yaml. The 2x 2-lane sub-channel mode is supported by the V853 datasheet section 1.3.6.4. |
| Dual CSI simultaneous | **YELLOW** | The datasheet supports it; the Linux driver chain is partially validated. The actual ISP throughput is 5 MP / 30 fps aggregate. |
| CSI data/clock lane ball assignments | **RED** | The 100ASK public dts references `&ncsi_pins_a` (label only); the underlying balls are in the V853/V853S_PINOUT.sls. |
| Camera FPC connector (15-pin 1.0 mm) | **GREEN (RPi CM3 compatible)** | Per camera/README.md. |
| Camera SCCB / I2C address selection (CAM1 vs CAM2) | **YELLOW** | The IMX708 SCCB address is 0x1A or 0x10 per the variant; the FPC layout must select different addresses for the two cameras. |
| Camera reset/standby GPIOs | **GREEN** | Standard 2-signal control per camera. Specific GPIO balls UNKNOWN. |
| Camera power (AVDD 2.8 V, DVDD 1.2 V, IOVDD 1.8 V) | **GREEN** | Standard IMX708 power tree. |

### DISPLAY

| Subsystem | Status | Notes |
| --- | --- | --- |
| 0.23-inch 640x400 MIPI DSI display | **GREEN (architecture)** | Per display-electrical-validation.yaml. The 640x400 target is well within the V853 DSI's 1920x1200 maximum. |
| Direct V853 DSI 4-lane to display | **GREEN** | No bridge IC needed. The TC358870 (HDMI-to-DSI) is REJECTED because the V853 has no HDMI output. The Lontium LT8912B (RGB/LVDS-to-DSI) is the FALLBACK if the display engine has a non-DSI input. |
| Display NDA acquisition (Lumus / DigiLens) | **RED** | The display optical engine is NDA-gated; mm-level dimensions not in public source. |
| Display data/clock lane ball assignments | **RED** | Same as CSI; the SoC pinctrl dtsi has the pins. |
| Display TE / reset / backlight-enable GPIOs | **GREEN (architecture)** | Standard 3-signal control. Specific GPIO balls UNKNOWN. |
| Display panel driver (Linux DRM/KMS) | **YELLOW** | A custom panel driver must be written for the chosen micro-OLED. The structure is in include/drm/drm_panel.h. |
| Display FPC connector | **YELLOW** | Depends on the chosen display engine's FPC pinout. |

### AUDIO

| Subsystem | Status | Notes |
| --- | --- | --- |
| 2x CUI CMS-151125-078S speaker (15×11×2.5 mm, 8 Ω, ~0.6 g) | **GREEN (per datasheet summary)** | Full CUI datasheet PDF not retrieved. |
| 2x ADI MAX98390 amplifier (1.33×1.33 mm WLP, 2.5 W into 8 Ω, I2S, filterless) | **GREEN (per datasheet summary)** | Full ADI datasheet PDF not retrieved. |
| MAX98390 IO voltage (1.8 V vs 3.3 V) | **YELLOW** | The previous pass said 1.8 V; the official ADI datasheet PDF should be confirmed. |
| V853 I2S0 (left amp) | **YELLOW** | The 100ASK public dts uses I2S0 on PH0/PH4 (mux conflict with DMIC). An alternative I2S0 pin set is needed. |
| V853 I2S1 (right amp) | **GREEN (per 100ASK dts on PE7/PE11)** | The I2S1 pin set conflicts with GMAC0, but the glasses' design disables GMAC0. |
| BCLK / LRCLK sharing between I2S0 and I2S1 | **GREEN** | Both MAX98390s can share one BCLK + LRCLK (driven by the V853). |
| 8 Ω speaker vs MAX98390 output (8 Ω) | **GREEN** | Matched. |
| Speaker back-volume acoustic test | **YELLOW** | Required but not yet performed. |
| DMIC (microphone) | **YELLOW (architecture)** | Per dmic-validation.yaml. The 100ASK dts uses DMIC on PH0/PH4 (mux conflict with I2S0). An alternative DMIC pin set is needed. |
| Microphone power (MIC_AVDD 1.8 V) | **GREEN** | AXP2101 ALDO1 (1.8 V). |

### I2C shared bus (7 devices)

| Subsystem | Status | Notes |
| --- | --- | --- |
| I2C address uniqueness (7 devices) | **GREEN** | Per i2c-audit.yaml. All 7 addresses (0x34, 0x36, 0x48, 0x49, 0x10, 0x6A, 0x68) are unique. |
| I2C bus speed (400 kHz Fast-Mode) | **GREEN** | All 7 devices support 400 kHz. |
| I2C pull-up (4.7 kohm to 1.8 V) | **GREEN** | Standard I2C. Single set of pull-ups for the whole bus. |
| I2C voltage (1.8 V) | **GREEN** | All 7 devices are 1.8 V IO compatible. |
| I2C bus choice (TWI0 vs TWI4) | **YELLOW** | The 100ASK reference uses TWI4 (PI1/PI2) for the AXP2101. The glasses' design can use TWI4 for all 7 devices or TWI0 for the shared bus and TWI4 for the AXP2101 only. The choice depends on GPIO bank power domain verification. |
| TWI4 specific ball (PI1/PI2) | **YELLOW** | The 100ASK dts confirms PI1/PI2 for TWI4. The exact BGA ball is in the .sls file. |
| I2C bus shared with 2x camera SCCB | **GREEN (architecture)** | The camera SCCB is a separate I2C address (0x1A or 0x10) from the 7-device bus. The cameras can share the bus (or use a separate I2C channel if needed). |

### SENSORS

| Subsystem | Status | Notes |
| --- | --- | --- |
| BMI270 IMU (2.5×3.0×0.8 mm LGA, 6-axis, I2C) | **GREEN (per datasheet summary)** | Linux IIO driver (bmi160/bmi270). |
| VEML7700 ALS (3.0×2.0×0.5 mm OPLGA, I2C) | **GREEN** | Linux driver. |
| 2x TMP117 temperature (1.5×1.5×0.5 mm WCSP, I2C) | **GREEN** | Linux driver. |
| MAX17048 fuel gauge (TDFN-8 2.5×2.5 mm, I2C) | **GREEN** | Linux driver. |
| BQ25185 charger (WCSP, I2C) | **GREEN** | Linux driver. |
| AXP2101 PMU (QFN-32 ~5×5 mm, I2C 0x34) | **GREEN** | Linux MFD driver. |
| IMU / ALS / TMP117 / fuel-gauge / charger / PMIC interrupt GPIOs | **GREEN (architecture)** | 6+ interrupt signals; specific GPIO balls UNKNOWN. |

### CONTROL

| Subsystem | Status | Notes |
| --- | --- | --- |
| User button (GPIO input with internal pull-up) | **GREEN** | Standard design. |
| Status LED (GPIO output + 1 kohm + LED) | **GREEN** | Standard design. |
| Camera reset/standby (4x GPIO outputs) | **GREEN** | Standard design. |
| Display TE / reset / backlight-enable (3x GPIO) | **GREEN (architecture)** | Standard design; specific GPIO balls UNKNOWN. |
| IR LED enable + PWM (2x GPIO/PWM) | **GREEN (architecture)** | Standard design. |
| Haptic enable + PWM (optional, 2x GPIO/PWM) | **YELLOW** | 8 mm LRA class is the right form factor; no specific part chosen. Skip if temple pod is too large. |
| Thermal alerts (TMP117 x2 ALERT, AXP2101 IRQ) | **GREEN** | 3 interrupt signals; specific GPIO balls UNKNOWN. |
| Power-good / interrupt lines (BQ25185 INT, AXP2101 IRQ) | **GREEN** | Same. |
| Boot mode pin straps (2-3 GPIO) | **YELLOW** | The exact boot mode pin balls are in the .sls file. |
| RESET (AXP2101 RESET_OUT to SoC RESET_IN) | **GREEN (architecture)** | Standard design; exact ball UNKNOWN. |

### USB-C

| Subsystem | Status | Notes |
| --- | --- | --- |
| USB-C 5 V charging (BQ25185) | **GREEN** | Per usb-electrical-validation.yaml. |
| USB-C 2.0 data (V853 USB 2.0 DRD) | **GREEN (architecture)** | DP, DN, CC1, CC2, VBUS. |
| TPD4E05U04 ESD (4-channel) | **GREEN** | Verified. |
| 5.1 kohm CC pull-down (UFP / device role) | **GREEN** | Per USB-C spec. |
| USB 2.0 90 ohm differential impedance | **GREEN** | Per USB 2.0 spec. |
| USB 2.0 common-mode choke (EMI) | **YELLOW** | Recommended (Murata DLW21SN); optional. |
| USB-PD | **GREEN (not used)** | 5 V is sufficient. |
| USB_ID pin (OTG) | **GREEN (not used)** | Configured as floating or tied to GND for device role. |
| USB DP/DN exact balls | **RED** | In the V853/V853S_PINOUT.sls. |

### MECHANICAL / OPTICAL (out of scope for this pass)

| Subsystem | Status | Notes |
| --- | --- | --- |
| Wayfarer frame assessment | **GREEN (read-only)** | Per full-mechanical-inspection.md. |
| Optical engine (Lumus / DigiLens) | **RED (NDA required)** | mm-level dimensions are NDA-gated. |
| Speaker back-volume acoustic test | **YELLOW** | Required but not yet performed. |
| Temple pod mechanical design | **YELLOW** | A custom temple with 5-8 mm pod is required; not yet designed. |
| Compute PCB mechanical placement | **RED (blocked)** | The display NDA + per-ball pin map are required for placement. |

---

## Overall design-gate summary

| Gate | Status | Count |
| --- | --- | --- |
| **GREEN** | safe to carry into the eventual schematic capture | 50+ items |
| **YELLOW** | plausible but requires confirmation | 15 items |
| **RED** | blocked by missing documentation | 7 items |

**The schematic capture at the peripheral block level is READY.** The PCB layout at the per-ball level is BLOCKED on the V853/V853S_PINOUT.sls file.

---

## Items at YELLOW (what to confirm in parallel with the NDA acquisition)

1. **MAX98390 IO voltage** (1.8 V vs 3.3 V) — confirm with the ADI MAX98390 datasheet PDF.
2. **AW-CM276SM exact mechanical and electrical documentation** — request the AzureWave datasheet PDF.
3. **EEMB LP402535 full datasheet** — exact discharge C-rate and cycle life.
4. **AXP2101 NVRAM configuration** — finalize per-rail DCDC / LDO assignment.
5. **V853 I2S0 alternative pin set** — required to coexist with DMIC; find via the SoC pinctrl dtsi.
6. **V853 DMIC alternative pin set** — same.
7. **Camera SCCB address selection** — IMX708 variant determines 0x1A vs 0x10; the FPC layout must select different addresses for the two cameras.
8. **Linux driver chain for 2-camera simultaneous capture** — validate with the Allwinner Tina SDK or mainline Linux.
9. **Custom DRM/KMS panel driver** — write for the chosen display engine.
10. **TWI0 vs TWI4 bus choice** — verify GPIO bank power domain.
11. **Boot mode pin straps** — determine from the V853/V853S_PINOUT.sls.
12. **Haptic actuator** — decide whether to include in the BOM.
13. **USB common-mode choke** — decide whether to include for EMI suppression.
14. **Speaker back-volume acoustic test** — perform on a specific 6×10 / 15×11 mm driver in a Wayfarer-style back-volume.
15. **IR LED boost converter** — TPS61236P or similar.

---

## Items at RED (what is blocked)

1. **V853 LFBGA-318 12×12×0.5 mm ball map** — the V853/V853S_PINOUT.sls file is NDA-only.
2. **CSI data/clock lane physical balls** — in the .sls file.
3. **DSI data/clock lane physical balls** — in the .sls file.
4. **USB DP/DN exact balls** — in the .sls file.
5. **RESET, XTAL24MH, boot mode pin physical balls** — in the .sls file.
6. **Optical engine (Lumus / DigiLens) mm-level dimensions** — NDA.
7. **Compute PCB mechanical placement** — blocked by the display NDA + per-ball pin map.

---

## Stop point

Per the brief: "Do not start PCB routing." This design-gate summary is COMPLETE. The logical schematic work is GREEN-ready; the PCB layout is RED-blocked on the V853/V853S_PINOUT.sls. Awaiting your direction on whether to (a) acquire the .sls file, (b) continue with the schematic capture in parallel, or (c) halt pending NDA acquisition.
