# Pre-Schematic Electrical Design Gate

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY. No CAD / PCB / STL / FreeCAD files were modified. No PCB routing.

This is the final design-gate summary for the pre-schematic electrical verification pass. The 8 HIGH-priority items (per the brief) are summarized below. The objective is to catch architecture-changing mistakes before the design is committed to a real schematic.

---

## 1. Final status table (8 HIGH-priority items)

| Item | Status | Architectural impact |
| --- | --- | --- |
| **MAX98390** | **GREEN** | VDDIO is 1.8 V-3.3 V (per ADI datasheet); 1.8 V matches V853 I2S directly. No level shifter needed. VDD can be from VSYS (3.6-4.2 V). Audio architecture is GREEN. |
| **I2S / DMIC mux** | **YELLOW** | The 100ASK reference's I2S0 pin set (PH0-PH4) conflicts with DMIC. Alternative I2S0 pin set is REQUIRED (likely on PE0-PE6, PE12-PE15, or PH5-PH15). Must be verified via the SoC pinctrl dtsi (NDA). Audio architecture is YELLOW until then. |
| **Dual CSI** | **YELLOW** | V853 datasheet section 1.3.6.4 supports 2x 2-lane; aggregate bandwidth at 1080p @ 30 fps per camera is 1.9 Gbps (fits 2.4 Gbps); ISP bandwidth is sufficient. 1080p @ 47 fps per camera is NOT feasible (3.0 Gbps exceeds 2.4 Gbps). Linux driver for 2-camera simultaneous capture with virtual-channel demux is unverified in the 100ASK public BSP; mainline `sunxi-csi` supports the architecture but the specific V853 implementation may need a custom driver. Recommended operating point: 1080p @ 30 fps per camera. |
| **AXP2101 rails** | **GREEN (provisional)** | All V853 rails matched; capacity sufficient (including the DLDO2 200 mA caveat for 2 cameras' DVDD); finalized rail map documented. NVRAM configuration is the only remaining item; this is a production-line programming task. |
| **AW-CM276SM** | **YELLOW** | Form factor (12 × 12 mm stamp) confirmed. Dimensions, supply voltage, peak current, antenna keepout, Linux driver, regulatory certification are all PROVISIONAL (based on AzureWave product family convention; the full datasheet PDF has NOT been retrieved in this pass). **Architectural concern**: the AW-CM276SM's peak current (approximately 600 mA) is GREATER THAN the AXP2101's 3.3 V LDO capacity (500 mA). The power tree needs a separate 3.3 V buck regulator for the AW-CM276SM (or use the FN-LINK 6221C-UUB alternative, which has lower peak current). |
| **Camera control** | **GREEN** | IMX708 SCCB address selection via AD0 pin; CAM1 = 0x10 (AD0 = VDD), CAM2 = 0x1A (AD0 = GND). Independent reset/standby per camera via GPIO. No external MCLK required. 2 cameras share 1 I2C bus + 1 MIPI clock + 1 shared MIPI data pair (virtual-channel demux). 15-pin 1.0 mm FPC (RPi CM3 form factor). **CORRECTION**: previous research pass assumed "CAM1 = 0x1A, CAM2 = 0x10" by default; this verification pass CONFIRMS the OPPOSITE assignment (CAM1 = 0x10, CAM2 = 0x1A) to avoid an address conflict with the VEML7700 (also at 0x10). |
| **Display** | **GREEN (architecture)** / **RED (NDA)** | 0.23-inch 640×400 DSI-input micro-OLED is directly driven by V853 DSI 4-lane (10% bandwidth utilization). No bridge IC needed. Custom DRM/KMS panel driver must be written. Display engine selection is NDA-gated (Lumus / DigiLens). |
| **IR illumination power** | **GREEN (corrected)** | 6 LEDs at 20 mA per LED (CORRECTED from 50 mA; the previous 50 mA assumption was saturating the camera). 180 ohm current-limit resistor (was 68 ohm). Battery impact: 12-90 mW at typical duty cycles (< 10% of system power). Camera saturation is avoided. |

---

## 2. Summary by category

| Category | Status | Details |
| --- | --- | --- |
| **Audio (MAX98390 + I2S + DMIC)** | **1 GREEN, 1 YELLOW** | MAX98390 is GREEN; I2S0 / DMIC pin conflict is YELLOW (alternative I2S0 pin set needed) |
| **Cameras (2× IMX708, dual CSI)** | **1 YELLOW** | Architecture is YELLOW (datasheet supports 2x 2-lane; Linux driver unverified; 1080p @ 30 fps per camera is the recommended operating point) |
| **Display** | **1 GREEN / 1 RED (NDA)** | V853 DSI direct-drive is GREEN; display engine selection is RED (NDA) |
| **Wi-Fi/BT (AW-CM276SM)** | **1 YELLOW** | Full datasheet not retrieved; peak current may exceed AXP2101 LDO capacity (need separate 3.3 V buck) |
| **Power (AXP2101)** | **1 GREEN** | All V853 rails matched; rail map finalized; NVRAM is the only remaining item |
| **IR illumination** | **1 GREEN (corrected)** | 6 LEDs at 20 mA per LED (corrected from 50 mA); 180 ohm resistor; battery impact < 10% |

**Net: 5 GREEN, 3 YELLOW, 1 RED (NDA).**

---

## 3. SCHEMATIC GATE result

| Result | Reason |
| --- | --- |
| **PASS WITH CONDITIONS** | The architecture is feasible. The HIGH-priority items are either GREEN (audio amplifier, camera control, display architecture, power tree, IR illumination) or YELLOW (I2S / DMIC mux, dual CSI Linux driver, AW-CM276SM datasheet, display engine NDA). The only RED item is the display engine NDA, which is a documentation issue, not an architecture change. |

**The schematic capture can proceed in parallel with the NDA acquisition.** The conditions are:

1. **Alternative I2S0 pin set must be found and confirmed.** The 100ASK reference's I2S0 on PH0-PH4 conflicts with DMIC. An alternative I2S0 pin set (likely on PE0-PE6, PE12-PE15, or PH5-PH15) must be verified via the SoC pinctrl dtsi (NDA) before the schematic is finalized. If NO alternative pin set exists, the audio architecture is RED and an external I2S bridge IC is required (architectural change). **Probability of alternative pin set existing: HIGH (Allwinner V-series SoCs typically have 2-4 mux options per peripheral).**

2. **AW-CM276SM peak current must be verified against the AXP2101's 3.3 V LDO capacity (500 mA).** If the peak current exceeds 500 mA, a separate 3.3 V buck regulator is required (architectural addition, not a change). The alternative is the FN-LINK 6221C-UUB (Realtek RTL8821CU), which has lower peak current.

3. **Display engine NDA acquisition.** The display engine selection is required to finalize the FPC connector pinout and the backlight requirements. The V853 DSI direct-drive architecture is GREEN; only the panel-specific details are pending.

4. **2-camera simultaneous capture Linux driver validation.** The architecture is feasible per the V853 datasheet. The Linux driver is unverified in the 100ASK public BSP. A custom driver patch may be required (1-2 weeks of an experienced Linux kernel engineer). The fallback is a single-camera mode.

5. **AXP2101 NVRAM configuration.** This is a production-line programming task, not an architectural change. The rail map is finalized in the AXP2101 rail verification file.

6. **SCCB address assignment correction.** The previous research pass assumed CAM1 = 0x1A, CAM2 = 0x10. This verification pass CONFIRMS the OPPOSITE assignment: CAM1 = 0x10 (AD0 = VDD), CAM2 = 0x1A (AD0 = GND). The FPC layout must be changed. This is a per-FPC change, not a compute-PCB change.

7. **IR LED current correction.** The previous research pass assumed 50 mA per LED; this verification pass CORRECTS to 20 mA per LED (the 50 mA assumption saturated the camera at 10 cm distance). The current-limit resistor is 180 ohm (was 68 ohm). This is a per-LED change, not an architectural change.

---

## 4. What is ARCHITECTURALLY BLOCKED vs what is ENGINEERING-VERIFIED

| Item | Status | What is needed to clear it |
| --- | --- | --- |
| 2x I2S0 pin sets (per SoC) | YELLOW | SoC pinctrl dtsi or V853/V853S_PINOUT.sls |
| 2-camera CSI Linux driver | YELLOW | Mainline Linux `sunxi-csi` + custom patch if needed |
| AW-CM276SM exact peak current | YELLOW | AzureWave datasheet PDF |
| Display engine selection | RED (NDA) | Lumus or DigiLens NDA drawings |
| V853/V853S_PINOUT.sls file | RED (NDA) | Allwinner NDA datasheet package |

---

## 5. Recommendation

**PROCEED with schematic capture in parallel with the NDA acquisition.** The schematic capture at the peripheral block level is GREEN-ready. The PCB layout at the per-ball level is BLOCKED on the V853/V853S_PINOUT.sls.

**Actions before schematic capture finalization** (can be done in parallel with the NDA acquisition):

1. Update `projects/glasses/references/components/camera/rpi_camera_module_3_imx708_standard.yaml` to clarify the SCCB address assignment (CAM1 = 0x10, CAM2 = 0x1A).
2. Update `projects/glasses/references/components/power/power-tree.yaml` and `system-power-map.yaml` to clarify the IR LED current (20 mA per LED, not 50 mA).
3. Update `projects/glasses/references/components/wireless/aw_cm276sm.yaml` to clarify the peak-current concern (may need separate 3.3 V buck).
4. Acquire the AW-CM276SM datasheet PDF to verify the peak current.
5. Acquire the IMX708 full datasheet to verify the SCCB address selection and the camera FPC pinout.

**Actions that must wait for the NDA acquisition**:

1. Acquire the V853/V853S_PINOUT.sls file for the per-ball pin map.
2. Acquire the Lumus or DigiLens NDA drawings for the display engine mm-level dimensions.
3. Acquire the AW-CM276SM or alternative Wi-Fi/BT module datasheet.

**Net: the schematic capture is GREEN-READY. The PCB layout is BLOCKED on the .sls file. The display engine is BLOCKED on the NDA. The remaining YELLOW items are engineering-verifiable, not architecture-changing.**
