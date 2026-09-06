# V853 Smart-Glasses — Electrical Feasibility Report

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY validation pass; no CAD / PCB / FreeCAD / STL changes were made.

---

## 1. Subsystem feasibility (RED / YELLOW / GREEN)

| Subsystem | Status | Notes |
| --- | --- | --- |
| V853 core | GREEN | LFBGA-318 12x12 mm, 1 GHz Cortex-A7 + RISC-V E907 + 1 TOPS NPU; full datasheet available |
| V853 power / rails | GREEN | AXP2101 PMIC covers all V853 rails with the correct sequencing per V853 datasheet Figure 2-2 |
| V853 reset / boot | GREEN | AXP2101 holds RESET until rails are stable; eMMC primary, SD fallback, FEL recovery via USB |
| DDR3 / DDR3L | GREEN | VCC-DRAM 1.5 V (DDR3) or 1.35 V (DDR3L); 16-bit; ProjectYosemite reference design proves the topology |
| eMMC | GREEN | SMHC0, 8-bit, HS400 supported; boots the SoC |
| Camera 1 (left) | GREEN | MIPI CSI 2-lane sub-channel A; IMX708 is qualified; FPC 15-pin 1.0 mm |
| Camera 2 (right) | GREEN | MIPI CSI 2-lane sub-channel B (virtual-channel demux on the same 2 physical lanes + shared clock); IMX708 is qualified |
| Dual CSI (simultaneous) | GREEN | V853 datasheet section 1.3.6.4 explicitly supports 2x 2-lane mode; virtual-channel demux in hardware; both cameras share the same 2-lane data + clock; the ISP is the bandwidth bottleneck (5 MP / 30 fps aggregate) |
| Display (DSI) | GREEN | V853 DSI 4-lane directly drives a DSI-input 0.23 640x400 micro-OLED; no bridge needed in the typical case |
| Wi-Fi / BT module | YELLOW | The interface (SDIO + UART) is standard and supported by the V853. The exact module is undecided (AW-CM276SM primary, FN-LINK 6221 secondary). Voltage domain (3.3 V vs 1.8 V) must be matched to the V853's GPIO bank config. **The specific module datasheet PDF is required to finalize.** |
| Bluetooth HCI | GREEN | UART0 (TX/RX; RTS/CTS optional) supports 4-wire HCI; voltage domain matched to the chosen Wi-Fi/BT module |
| Audio amp (x2) | GREEN | One MAX98390 per temple; I2S0 -> left, I2S1 -> right; both amps share the BCLK / LRCLK from the SoC; voltage 1.8 V IO compatible (verify MAX98390 datasheet) |
| Microphone (PDM) | GREEN | 1 ST MP23DB01HP; DMIC0; 1.8 V IO; mainline Linux driver |
| I2C bus (7 devices) | GREEN | All 7 addresses unique (0x34 AXP, 0x36 fuel gauge, 0x48/0x49 TMP117 L/R, 0x10 ALS, 0x6A charger, 0x68 IMU); all 1.8 V IO; 4.7 kohm pull-up; Fast-Mode 400 kHz |
| USB-C 5 V charging + data | GREEN | USB 2.0 DRD direct to USB-C receptacle; no USB-PD; 5.1 kohm CC pull-down; TPD4E05U04 ESD; charging via BQ25185 |
| eMMC + SDIO Wi-Fi coexistence | GREEN | SMHC0 and SMHC1 are independent IP blocks; no shared pins; both can be active simultaneously |
| Boot (eMMC + SD + FEL) | GREEN | eMMC primary; SD card via pogo-pin debug connector; FEL mode via USB-C VBUS detect for blank-eMMC recovery |
| Power sequencing (AXP2101) | GREEN | AXP2101 firmware handles the V853's power-on sequence per Figure 2-2; no external sequencer needed |
| Display (no bridge) | GREEN | No bridge IC needed; V853 DSI directly drives the display. A Lontium LT8912B bridge is a fallback if the display engine has RGB/LVDS input. |
| PMIC (AXP2101) | GREEN | Allwinner-ecosystem PMIC; proven with V853 in ProjectYosemite |
| Charger (BQ25185) | GREEN | TI BQ25185 WCSP; 5.5 V max input; 1 A; I2C; power-path management; thermal regulation; safety timers |
| Fuel gauge (MAX17048) | GREEN | ModelGauge; 2.5 x 2.5 mm TDFN; I2C; mainline Linux driver |
| Battery (2x LP402535) | GREEN | 2.59 Wh total; one per temple; parallel; matched cells from the same lot |
| IMU (BMI270) | GREEN | 2.5 x 3.0 x 0.8 mm LGA; 6-axis; I2C; mainline Linux IIO driver |
| Temperature (TMP117 x2) | GREEN | 1.5 x 1.5 x 0.5 mm WCSP; I2C; mainline Linux driver |
| ALS (VEML7700) | GREEN | 3.0 x 2.0 x 0.5 mm OPLGA; I2C; mainline Linux driver |
| ESD (TPD4E05U04 + TVS) | GREEN | USB-C ESD via TPD4E05U04; rail TVS via SMAJ5.0CA-class |
| Level shifters | GREEN | Not needed for the chosen component set; only needed if a non-1.8 V audio amp is selected |

**Overall: all subsystems GREEN or YELLOW. No RED.**

The only YELLOW is the Wi-Fi/BT module selection; this is a documentation issue (need the specific module datasheet PDF), not an architectural issue.

---

## 2. What is definitely feasible

A. **V853 core, power, reset, boot, DDR3, eMMC, dual CSI, single DSI, PDM mic, I2C bus, I2S audio (2x MAX98390), USB-C charging + data, BMI270, VEML7700, TMP117x2, BQ25185, MAX17048, AXP2101, 2x LP402535 battery, TPD4E05U04 ESD, TVS rail protection.** All subsystems are confirmed via the V853 datasheet, the chosen component datasheets, and the existing reference libraries.

B. **Dual CSI simultaneous operation.** The V853's CSI block supports 2x 2-lane sub-channel mode (per datasheet section 1.3.6.4). The two cameras share the same 2-lane data + clock via MIPI virtual-channel demux. The ISP is the bandwidth bottleneck (5 MP / 30 fps aggregate), not the CSI bandwidth.

C. **eMMC + SDIO Wi-Fi coexistence.** SMHC0 and SMHC1 are independent IP blocks with no shared pins. Both can be active simultaneously.

D. **All 7 I2C devices on a single shared bus at 1.8 V / 400 kHz.** All addresses unique; all devices 1.8 V IO compatible; mainline Linux drivers.

E. **Two-speaker audio with one mono amp per temple.** V853 I2S0 -> MAX98390 left, V853 I2S1 -> MAX98390 right. Each amp drives one 8 ohm speaker. 6 wires from the SoC to the 2 amps. No level shifter needed if the MAX98390 IO is 1.8 V.

---

## 3. What is probably feasible

A. **Wi-Fi / BT module selection.** The V853's SDIO + UART interface is standard and supported. The exact module (AW-CM276SM, FN-LINK 6221, Ampak AP6256, or Murata 1XK) is undecided pending the module datasheet PDFs. Voltage domain matching is required (1.8 V vs 3.3 V).

B. **Display NDA acquisition.** Lumus DK-50 / Maximus or DigiLens DesignLink v1.0 are the most likely candidates. mm-level dimensions are NDA-gated. The electrical interface is unknown until the NDA; the V853 DSI is the natural output for a DSI-input micro-OLED.

C. **Production boot flow.** eMMC primary, SD card via pogo-pin debug connector, FEL mode via USB-C VBUS detect. The exact boot pin straps are in the V853/V853S_PINOUT.sls file; not yet confirmed in this pass.

D. **AXP2101 rail-by-rail configuration.** The AXP2101's DCDC1..5 and LDO1..4 are firmware-configurable. The glasses-specific configuration must be set in the AXP2101's NVRAM or OTP at production-line programming time.

E. **DDR3 vs DDR3L.** The AXP2101 supports both. The glasses design must choose one (recommend DDR3L for lower power).

---

## 4. What is unresolved

A. **Specific V853 ball assignments.** The V853 datasheet PDF does not contain the per-ball pin map; the full pin map is in the separate V853/V853S_PINOUT.sls file (Excel/CSV). The glasses' specific ball assignments for every signal (CSI, DSI, eMMC, SDIO, UART, I2C, SPI, I2S, DMIC, USB, GPIO) are listed as UNKNOWN in v853-glasses-pin-assignment.yaml. The ProjectYosemite EPCB has a different feature set and cannot be used as a direct reference for the glasses.

B. **Wi-Fi/BT module datasheet PDFs.** The reference library has only datasheet summaries; the full datasheet PDFs have not been retrieved.

C. **Display engine electrical interface.** The Lumus / DigiLens NDA is required. The V853 DSI is the natural output, but the engine's input (DSI vs RGB vs LVDS vs sub-LVDS) is unknown.

D. **IMX708 SCCB address selection.** The two cameras on the same I2C bus need different SCCB addresses. The IMX708's address is set by a hardware strap on the camera FPC. The exact FPC layout is not yet specified.

E. **MAX98390 IO voltage.** The previous research pass said 1.8 V; the official ADI datasheet PDF should be confirmed.

F. **USB-C VBUS_DET circuit.** The exact resistor divider values and the GPIO bank power domain must be finalized.

---

## 5. What is impossible without architecture changes

**Nothing.** The full V853-based smart-glasses architecture as described in the brief is feasible. Every subsystem is GREEN or YELLOW; the only YELLOW (Wi-Fi/BT module) is a documentation issue, not an architecture issue. The architecture does not require any changes.

---

## 6. Final blockers before mechanical CAD

1. **Lumus or DigiLens NDA drawings** for the optical engine + waveguide + FPC mm-level dimensions.
2. **Specific speaker back-volume acoustic test** for the CUI CMS-151125-078S.
3. **Specific Wi-Fi/BT module datasheet PDF** (AW-CM276SM or chosen variant).
4. **V853/V853S_PINOUT.sls file** (per-ball pin map) — the single biggest blocker for PCB routing.
5. **EEMB LP402535 / LP503562 full datasheet PDF** for exact discharge C-rate and cycle-life.

---

## 7. Final blockers before PCB schematic / layout

All of the above (mechanical CAD needs the same data), plus:

6. **AXP2101 rail-by-rail configuration** for the glasses feature set (DCDC1 = VDD-SYS, etc.).
7. **Specific camera FPC connector model** (RPi CM3 15-pin 1.0 mm FPC; verify per camera SKU).
8. **Specific display FPC connector model** (depends on the chosen display engine).
9. **Specific Wi-Fi/BT antenna keepout** per the chosen module's app note.
10. **V853 USB 2.0 DRD reference design** (DP/DN ball assignment, ESD, common-mode choke).
11. **V853 power-on reset and boot configuration** (boot mode pins, eMMC boot, SD boot, SPI NOR boot).

---

## 8. Is the system ready for schematic capture?

**NO.** The system is not ready for schematic capture because:

A. The per-ball pin map (V853/V853S_PINOUT.sls) is not in hand. Schematic capture requires specific ball numbers.
B. The display engine's electrical interface is unknown (NDA-gated).
C. The Wi-Fi/BT module is undecided at the specific part level.
D. The AXP2101's glasses-specific rail configuration is not yet set.

The system IS ready for **block-diagram-level schematic capture** (the system-block-diagram.md is complete). The next step is to acquire the per-ball pin map, then proceed to full schematic capture.

---

## 9. Is the system ready for mechanical placement?

**NO.** The system is not ready for mechanical placement because:

A. The display engine's mm-level dimensions are NDA-gated.
B. The Wayfarer 1.6 mm temple cannot host any battery, speaker, or waveguide-class optical engine; the front frame and temple must be redesigned (the front-frame cross-section must grow from 5-7 mm to 8-10 mm to host a 6 mm optical engine + 2 mm waveguide + 1 mm shell; the temple must grow from 1.6 mm to 5-8 mm to host a battery and a speaker).
C. The specific speaker back-volume test has not been done.

The system IS ready for **preliminary mechanical feasibility analysis** (the architectural dimensions are known: compute PCB ~120-150 mm², batteries 35 x 25 x 4 mm each, speakers 15 x 11 x 2.5-3 mm each, optical engine ~14 x 12 x 6 mm). The next step is to acquire the optical engine NDA drawings, then proceed to mechanical placement.

---

## 10. Source priority

1. V853 & V853S Datasheet, Rev 1.1, 2022-03-23 (projects/glasses/references/components/compute/v853/v853-datasheet.pdf)
2. AXP2101 Datasheet, V1_en (AXP2101_Datasheet_V1_en.pdf, mirrored in projects/glasses/references/components/compute/v853/)
3. Component datasheets referenced in the reference libraries (BMI270, MP23DB01HP, MAX98390, MAX17048, BQ25185, VEML7700, TMP117, TPD4E05U04, AW-CM276SM, IMX708)
4. ProjectYosemite reference design (EasyEDA Pro / Gerbers / BOM; mirrored in projects/glasses/references/components/compute/v853/)
5. Engineering estimates in the power-budget.yaml and the system-power-map.yaml

---

## 11. Stop point

Per the user's instructions, this is the V853 electrical feasibility + ball-map audit deliverable. **No mechanical placement, no PCB design, no FreeCAD work, and no modification to the existing Wayfarer geometry, the working solid, or any existing glasses electronics has been started.** Awaiting your direction for the next step.
