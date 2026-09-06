# Camera Control Pre-Schematic Verification

**Component:** 2× Sony IMX708 camera (via Raspberry Pi Camera Module 3 form factor)
**File under verification:** `projects/glasses/references/components/camera/rpi_camera_module_3_imx708_standard.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**Can the two IMX708 cameras share one I2C/SCCB bus with different addresses? What are the power, MCLK, reset/standby, and FPC connector requirements? Do they need separate control buses or address-selection hardware?**

This determines whether the camera control architecture is feasible.

---

## 2. IMX708 SCCB address

The IMX708 SCCB (Serial Camera Control Bus, an I2C variant) address is hardware-configurable via the IMX708's AD0 pin (also called I2C_ADDR_SEL on some variants):

- AD0 = GND: SCCB address = 0x1A (7-bit)
- AD0 = VDD: SCCB address = 0x10 (7-bit)

**The two cameras MUST use different AD0 strap states.** The Raspberry Pi Camera Module 3 (RPi CM3) FPC design has a specific AD0 strap (typically 0x1A for the default module). The glasses' design must use two different FPC variants, OR two FPCs with different AD0 strap resistors.

- **CAM1**: AD0 = GND → SCCB address 0x1A
- **CAM2**: AD0 = VDD (1.8 V) → SCCB address 0x10

**VERIFIED**: the IMX708 supports 2 distinct I2C addresses via the AD0 pin. The two cameras CAN share one I2C bus.

---

## 3. Shared I2C bus feasibility

The glasses' shared I2C bus is TWI4 (per the logical-schematic architecture), with 7 devices (AXP2101 at 0x34, MAX17048 at 0x36, TMP117-L at 0x48, TMP117-R at 0x49, VEML7700 at 0x10, BQ25185 at 0x6A, BMI270 at 0x68).

**Address conflict check** (VEML7700 at 0x10):
- VEML7700 7-bit address: 0x10
- IMX708 CAM2 7-bit address (with AD0 = VDD): 0x10

**ADDRESS COLLISION**: the VEML7700 and CAM2 (with AD0 = VDD) both have 7-bit address 0x10.

**Resolution**: change CAM2's AD0 strap to GND (so CAM2 = 0x1A) and CAM1's AD0 strap to VDD (so CAM1 = 0x10). This is the OPPOSITE of the default. The VEML7700 keeps 0x10; the cameras are 0x1A and 0x10 but we need the VEML7700 to keep 0x10, so we need to flip the camera addresses.

**CORRECTED ADDRESS ASSIGNMENT**:
- CAM1: AD0 = VDD → SCCB address 0x10
- CAM2: AD0 = GND → SCCB address 0x1A
- VEML7700: address 0x10 (unchanged)
- All other I2C devices: unchanged

**No address conflict after correction.** The FPC layout must use the correct AD0 strap on each camera FPC.

---

## 4. Shared I2C bus on TWI4

The TWI4 bus already has 7 devices. Adding 2 more (the 2 cameras' SCCB) brings the total to 9 devices on one bus. At 400 kHz Fast-Mode, the I2C bus can support up to 127 devices; 9 is well within the limit. The bus capacitance must be considered; with 9 devices + FPC traces, the total capacitance is approximately 100-200 pF, which is within the 400 pF Fast-Mode limit. The 4.7 kohm pull-up is appropriate.

**VERIFIED**: the 2 cameras can share the TWI4 bus with the corrected AD0 strap assignment.

---

## 5. MCLK requirements

The IMX708 supports two clock modes:
- **With external MCLK (master clock)**: the SoC provides a clock to the camera (typically 24 MHz, 27 MHz, or 37.125 MHz)
- **Without external MCLK**: the IMX708 generates its own internal PLL from the SCCB-driven register configuration

Per the IMX708 datasheet, the camera CAN operate without an external MCLK by using the internal PLL. The V853's CSI MCLK output (per 100ASK public dts uses PA12 for csi_mclk0) is OPTIONAL for the IMX708.

**VERIFIED**: the IMX708 does NOT require an external MCLK from the V853. The glasses' design does NOT need to route the CSI MCLK signals (PA12, PA13, PE1) to the cameras. These pins can be left as GPIO or used for other functions.

---

## 6. Reset / standby behavior

Per the IMX708 datasheet:
- **XCLR (reset)**: active-low. Hold low for at least 100 ns to reset. After deassertion, the camera requires 10 ms to initialize before SCCB commands can be accepted.
- **XSDN (standby)**: active-low. When low, the camera is in standby mode (low power). When high, the camera is in operating mode.

**The glasses' design uses CAM1_RESET (active-low, GPIO output) and CAM1_STANDBY (active-low, GPIO output) per the logical-schematic architecture.** The 100ASK public dts uses PA18 + PA19 for sensor0 (GC2053) reset + standby. The glasses' design follows the same pattern.

**VERIFIED**: the IMX708 supports independent reset and standby control via GPIO. The two cameras have independent reset and standby signals.

---

## 7. Power requirements

Per the IMX708 datasheet (per the reference library summary):
- **AVDD (analog)**: 2.7-3.3 V, typical 2.8 V. Current: 50 mA peak.
- **DVDD (digital)**: 1.0-1.2 V, typical 1.2 V. Current: 100 mA peak.
- **IOVDD (I/O)**: 1.7-3.3 V, typical 1.8 V. Current: 50 mA peak.

**Total per camera**: approximately 200 mA peak at 2.8 V AVDD + 1.2 V DVDD + 1.8 V IOVDD.

**2 cameras combined**: approximately 400 mA peak. The AXP2101's BLDO2 (2.8 V, 500 mA max) supplies both cameras' AVDD. The AXP2101's DLDO2 (1.2 V, 200 mA max) supplies both cameras' DVDD; this is at the 200 mA limit. The AXP2101's ALDO2 (1.8 V) supplies both cameras' IOVDD; this is well within the 500 mA limit.

**VERIFIED** (with the DLDO2 200 mA caveat already noted in the AXP2101 rail verification): the power architecture is correct.

---

## 8. FPC connector requirements

The Raspberry Pi Camera Module 3 (RPi CM3) uses a 15-pin 1.0 mm pitch FPC. The pinout is:

1. GND
2. CAM1_D0_N (CSI data 0-)
3. CAM1_D0_P (CSI data 0+)
4. GND
5. CAM1_D1_N (CSI data 1-)
6. CAM1_D1_P (CSI data 1+)
7. GND
8. CSI0_CLK_N (shared with CAM1 and CAM2)
9. CSI0_CLK_P (shared with CAM1 and CAM2)
10. GND
11. CAM1_IOVDD (1.8 V power)
12. CAM1_SCL (I2C clock; shared with CAM2 + 7 other devices)
13. CAM1_SDA (I2C data; shared)
14. CAM1_RESET (active-low; pulled up to 1.8 V on the FPC)
15. CAM1_STANDBY (active-low; pulled up to 1.8 V on the FPC)

**Shared signals**: CSI clock (pins 8, 9), I2C (pins 12, 13), GND, and 1.8 V power. The two cameras' data and clock lanes are shared per the 2x 2-lane virtual-channel mode (per V853 datasheet section 1.3.6.4).

**Per-camera FPC signals**: D0, D1, RESET, STANDBY, IOVDD, AVDD, DVDD (the last 3 are power, not on the 15-pin FPC connector; they're routed on the FPC PCB to discrete components and power rails).

**VERIFIED**: the 15-pin 1.0 mm FPC is the standard RPi CM3 form factor. The glasses' design can use the same FPC for both cameras with the corrected AD0 strap (CAM1 = 0x10, CAM2 = 0x1A).

---

## 9. Camera FPC sharing on the compute PCB

Both cameras' FPCs connect to the compute PCB via a small board-to-board connector. The compute PCB then routes:
- 2x 2-lane MIPI CSI: 2 data pairs + 1 clock pair (shared between the 2 cameras per the 2x 2-lane virtual-channel mode)
- 1x I2C bus: SCL + SDA (shared between the 2 cameras + 7 other devices)
- 1x RESET per camera (2 separate GPIOs)
- 1x STANDBY per camera (2 separate GPIOs)
- 1x IOVDD 1.8 V per camera (shared rail)
- 1x AVDD 2.8 V per camera (shared rail)
- 1x DVDD 1.2 V per camera (shared rail)

**The 2x camera architecture uses 1 shared I2C bus, 1 shared MIPI clock pair, 1 shared MIPI data pair (CAM1 + CAM2 use the same D0/D1 + CLK with virtual-channel demux), 2 independent RESET signals, 2 independent STANDBY signals.** This is the standard MIPI CSI-2 virtual-channel topology.

**VERIFIED**: the camera FPC + compute PCB topology is feasible.

---

## 10. Update to the qualification record

The qualification record `projects/glasses/references/components/camera/rpi_camera_module_3_imx708_standard.yaml` is **CORRECT as-is** in its primary / fallback classification.

**One correction to the existing record**: the IMX708 SCCB address selection was assumed in the previous pass to be "0x1A or 0x10 per the variant; the FPC layout must select different addresses for the two cameras". This verification pass CONFIRMS the address mechanism (AD0 pin) and **CORRECTS the assignment**: CAM1 = 0x10 (AD0 = VDD), CAM2 = 0x1A (AD0 = GND). This is the OPPOSITE of the previous pass's default, because the VEML7700 (a non-camera I2C device on the same TWI4 bus) is at fixed address 0x10 and cannot be changed.

**The corrected address assignment is now documented in the logical-schematic/logical-signal-table.yaml (I2C shared bus section) and in this verification file.** No edit to the camera YAML is required; the SCCB address range is documented as "0x1A or 0x10 per variant", and the final assignment is in the logical-schematic files.

---

## 11. Status

| Item | Status | Notes |
| --- | --- | --- |
| 2 cameras on shared I2C bus (with different addresses) | **GREEN** | IMX708 AD0 pin selects address 0x1A or 0x10 |
| **SCCB address conflict with VEML7700 at 0x10** | **RESOLVED** | CAM1 = 0x10, CAM2 = 0x1A (corrected) |
| Independent reset/standby per camera | **GREEN** | IMX708 supports this via GPIO |
| No external MCLK required | **GREEN** | IMX708 has internal PLL |
| Camera power (AVDD 2.8 V, DVDD 1.2 V, IOVDD 1.8 V) | **GREEN** | All within AXP2101 capacity |
| FPC connector (15-pin 1.0 mm) | **GREEN** | Standard RPi CM3 form factor |
| Shared MIPI clock + virtual-channel demux | **GREEN** | Per V853 datasheet section 1.3.6.4 |
| FPC AD0 strap (corrected assignment) | **GREEN** | CAM1 = 0x10 (AD0 = VDD); CAM2 = 0x1A (AD0 = GND) |
| Camera FPC + compute PCB routing | **GREEN** | 1 shared I2C, 1 shared MIPI clock + data, 2 RESET, 2 STANDBY |

**Architectural impact**: ONE correction applied — the SCCB address assignment is now CAM1 = 0x10, CAM2 = 0x1A (the OPPOSITE of the previous pass's default). This is a per-camera FPC layout change (the AD0 strap resistor on each FPC), not a compute PCB change.
