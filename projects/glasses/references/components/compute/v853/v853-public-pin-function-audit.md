# V853 Public-Source Pin-Function Audit

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY audit. No CAD / PCB / STL / FreeCAD files were modified.

This audit documents what the V853 pin-function assignment looks like
based on the public 100ASK V853-PRO TinaSDK source, and which
decisions are blocked by the missing V853/V853S_PINOUT.sls file.

---

## Sources used (read-only)

| ID | File | Lines | Repo |
| --- | --- | --- | --- |
| src-1 | `device/config/chips/v853/configs/100ask/board.dts` | 1967 | DongshanPI/100ASK_V853-PRO_TinaSDK |
| src-2 | `device/config/chips/v853/configs/100ask/uboot-board.dts` | 760 | DongshanPI/100ASK_V853-PRO_TinaSDK |
| src-3 | `device/config/chips/v853/configs/100ask/sys_config.fex` | 140 | DongshanPI/100ASK_V853-PRO_TinaSDK |

The companion file `v853-public-pin-function-map.yaml` contains every
per-pin / per-function / per-muxsel assignment with line references.

---

## GREEN / YELLOW / RED classification

### GREEN (verified from public source)

| Item | Public source | Notes |
| --- | --- | --- |
| V853 peripheral block inventory | src-1 line 532-969 | TWI0-TWI4, UART0-UART3, SPI0/SPI1/SPIF0, I2S0/I2S1, DMIC, PWM4/PWM8/PWM9, SDC0/SDC1/SDC2, GMAC0, codec, USB0, MIPI CSI (csi2 / vinc00..vinc33), LCD0 (RGB), disp, AXP2101, gpadc, wiegand |
| TWI0 (kernel dts) pin assignment | src-1 line 690-697 | PE16 (SCL), PE17 (SDA) |
| TWI0 (U-Boot dts) pin assignment | src-2 line 179-186 | PA0 (SCL), PA1 (SDA) |
| TWI1 pin assignment | src-1 line 707-714 | PA14, PA15 |
| TWI2 pin assignment (kernel) | src-1 line 724-731 | PH5, PH6 |
| TWI2 pin assignment (U-Boot) | src-2 line 213-220 | PE20, PE21 |
| TWI3 pin assignment (kernel) | src-1 line 741-748 | PI3, PI4 |
| TWI3 pin assignment (U-Boot) | src-2 line 230-237 | PA10, PA11 |
| TWI4 pin assignment (kernel) | src-1 line 758-765 | PI1, PI2 |
| TWI4 pin assignment (U-Boot) | src-2 line 247-254 | PI01, PI02 |
| TWI4 pin assignment (sys_config) | src-3 line 91-95 | PI01, PI02 |
| UART0 pin assignment | src-1 line 539-545, src-2 line 162-172, src-3 line 97-100 | PH9, PH10 |
| UART1 pin assignment | src-1 line 553-559 | PG6, PG7 |
| UART2 pin assignment (4-wire) | src-1 line 567-573 | PE10, PE11, PE12, PE13 |
| UART3 pin assignment | src-1 line 581-587 | PH0, PH1 |
| SPI0 pin assignment | src-1 line 595-619, src-2 line 135-152 | PC0 (SCLK), PC1 (CS0), PC2 (MOSI), PC3 (MISO), PC4 (WP), PC5 (HOLD) |
| SPI1 pin assignment | src-2 line 162-177 | PH5, PH6, PH7, PH8, PH9 |
| SPIF0 pin assignment | src-2 line 649-688 | PF20-PF23 (DQ4-DQ7), PF24 (MOSI), PF25 (CS), PF26 (HOLD), PF29 (MISO), PF30 (WP), PF31 (SCK) |
| DMIC pin assignment | src-1 line 775-789 | PH0 (MCLK), PH1 (BCLK), PH2 (DATA0), PH3 (DATA1), PH4 (DATA2) |
| I2S0 pin assignment | src-1 line 791-797 | PH0 (MCLK), PH1 (BCLK), PH2 (LRCLK), PH3 (DOUT), PH4 (DIN) |
| I2S1 pin assignment | src-1 line 807-813 | PE7 (MCLK), PE8 (BCLK), PE9 (LRCLK), PE10 (DOUT), PE11 (DIN) |
| GMAC0 RGMII pin assignment | src-1 line 865-885 | PE0-PE15 (16 pins) |
| RGB18 (LCD) pin assignment | src-1 line 940-968 | PD0-PD21 (22 pins) |
| RGB24 (LCD) pin assignment | src-2 line 661-715 | PD0-PD27 (28 pins) |
| SDC0 (SD card) pin assignment | src-2 line 263-270, src-3 line 50-59 | PF0-PF5 |
| SDC1 (SDIO Wi-Fi) pin assignment | src-2 line 271-278, src-1 line 1656-1674 | PG0-PG5 (D0-D3, CMD, CLK) |
| SDC2 (eMMC) pin assignment | src-2 line 279-303, src-3 line 61-76, src-1 line 1607-1626 | PC0-PC11 (8 data + clock + command + reset + DS) |
| PWM4 pin assignment | src-1 line 823-835 | PH11 |
| PWM8 pin assignment | src-2 line 305-317 | PH8 |
| PWM9 pin assignment | src-1 line 837-849, src-2 line 319-331 | PD22 |
| CSI MCLK0 pin assignment | src-1 line 887-903 | PA12 |
| CSI MCLK1 pin assignment | src-1 line 905-921 | PA13 |
| CSI MCLK2 pin assignment | src-1 line 923-939 | PE1 |
| Sensor0 (camera 0) reset GPIO | src-1 line 222 | PA18 |
| Sensor0 (camera 0) pwdn GPIO | src-1 line 223 | PA19 |
| Sensor1 (camera 1) power_en GPIO | src-1 line 249 | PI0 |
| Sensor1 (camera 1) reset GPIO | src-1 line 250 | PH13 |
| USB VBUS enable GPIO | src-1 line 15, src-2 line 13 | PH2 |
| USB charger detect GPIO | src-1 line 492 | PH3 |
| USB ID GPIO | src-1 line 1516 | PH14 |
| Wi-Fi/BT host wake GPIO | src-1 line 97 | PG7 |
| Wi-Fi/BT reg-on GPIO | src-1 line 96 | PH15 |
| AXP2101 PMU I2C | src-1 line 1103-1113 | TWI4 at 0x34 |
| Mux conflict: I2S0 vs DMIC vs UART3 (PH0-PH4) | src-1 line 581, 775, 791 | All three contend for the same 5 pins |
| Mux conflict: SDC2 vs SPI0 (PC0-PC5) | src-1 line 595, src-2 line 279 | eMMC vs SPI flash share 6 pins |
| Mux conflict: I2S1 vs GMAC0 (PE7-PE11) | src-1 line 807, 865 | I2S1 vs Ethernet share 5 pins |

### YELLOW (plausible but requires datasheet / pinctrl dtsi confirmation)

| Item | Status | Why |
| --- | --- | --- |
| CSI data/clock lane pin assignments (CSI_D0P/N .. CSI_D3P/N, CSI_CLKP/N) | YELLOW | The 100ASK dts references `&ncsi_pins_a` but does not enumerate the pins; the underlying pins are in the SoC pinctrl dtsi (`sun8iw21p1-pinctrl.dtsi` or similar), which is NOT publicly available |
| DSI data/clock lane pin assignments (DSI_D0P/N .. DSI_D3P/N, DSI_CLKP/N) | YELLOW | Same — the 100ASK dts references `&dsi4lane_pins_a` (label only) in commented-out config; the SoC pinctrl dtsi is NOT publicly available |
| USB DP / USB DN | YELLOW | The SoC's USB 2.0 DRD PHY has dedicated balls; not in the public dts. Likely on the USB-PHY pins of the V853 (typically a separate power domain; the exact balls are in the V853/V853S_PINOUT.sls) |
| Specific GPIO ball for IMU INT1/INT2, ALS INT, TMP117 ALERT L/R, MAX17048 ALERT, BQ25185 INT, AXP2101 IRQ, IR LED EN/PWM, USER_BUTTON, STATUS_LED, USB_VBUS_DET, HAPTIC EN/PWM, display TE/reset/backlight-enable, camera reset/standby (2nd camera) | YELLOW | The 100ASK dts provides approximately 8 GPIO pin assignments; the glasses' design needs approximately 20 GPIO. The 100ASK pin choices may or may not be available on the SoC pinctrl dtsi for the glasses' specific combination. The V853 has approximately 128 GPIO across 8 banks; the available choices for the glasses' specific combination are in the SoC pinctrl dtsi. |
| Boot mode pin straps (eMMC vs SD card vs SPI NOR vs FEL) | YELLOW | The exact boot mode pin balls are in the SoC pinctrl dtsi / the V853 datasheet's boot section. The 100ASK dts references 'card_boot' and 'card2_boot_para' but does not enumerate the boot pin straps. |
| RESET ball (SoC's reset input from AXP2101) | YELLOW | The AXP2101 holds the SoC's RESET, but the exact ball is in the SoC pinctrl dtsi. The 100ASK dts has the powerkey0 node in the AXP2101, which controls the power-on/off function via the AXP2101's IRQ line. |
| I2S0 alternative pin set (to resolve DMIC / I2S0 / UART3 conflict on PH0-PH4) | YELLOW | The 100ASK dts only shows I2S0 on PH0-PH4. The SoC pinctrl dtsi may have alternative I2S0 pin sets (typically Allwinner I2S controllers have 2-4 mux options). The glasses' design needs to find an alternative I2S0 pin set to coexist with DMIC. This requires the SoC pinctrl dtsi. |
| SDC2 alternative pin set (to avoid SPI0 conflict) | YELLOW | Same — the SDC2 is on PC0-PC11. The SPI0 is on PC0-PC5. The 100ASK dts disables SPI0 in the kernel dts (SPI flash is optional). The glasses' design can do the same (disable SPI0 in the kernel dts) and use SDC2 for eMMC. This is acceptable. |
| GMAC0 alternative (must be disabled to free PE7-PE11 for I2S1) | YELLOW | Same — the glasses' design disables GMAC0 in the device tree. Acceptable. |

### RED (blocked by missing physical BGA ball map)

| Item | Status | Why |
| --- | --- | --- |
| Physical BGA ball number for every signal in the glasses' design | RED | The V853 datasheet does not contain the per-ball pin map; the V853/V853S_PINOUT.sls file is the only public path to per-ball data, and it is NDA-only (per the separate search in `source/SOURCE-SEARCH-LOG.md`). The SoC pinctrl dtsi is NOT publicly available. |
| USB DP / USB DN exact balls | RED | Same |
| RESET ball | RED | Same |
| XTAL24MH ball (24 MHz crystal input) | RED | The 100ASK dts does not enumerate the 24 MHz crystal pins. They are in the V853/V853S_PINOUT.sls. |
| The exact physical ball for every signal in the V853-glasses-pin-assignment.yaml (CSI, DSI, eMMC, SDIO, USB, I2C, I2S, DMIC, UART, GPIO) | RED | Same — the SoC pinctrl dtsi has the per-ball pad map; the .sls file has the per-ball pad map; neither is publicly available |
| Per-ball physical location for the LFBGA-318 12x12x~1.4 mm package | RED | The LFBGA-318 12x12x0.5 mm pitch package has 318 balls; the ball map is in the V853/V853S_PINOUT.sls. Without this, the PCB cannot be laid out (the LFBGA escape routing requires the exact ball positions) |

---

## Specific decisions that require V853/V853S_PINOUT.sls

The following decisions are BLOCKED by the missing .sls file. Each
decision is an actionable item that the glasses' PCB designer must
make, but cannot make without the .sls file.

1. **LFBGA-318 12x12x~1.4 mm package ball map.** The exact position (row, column) of every ball. Required for PCB escape routing. Without this, the LFBGA footprint cannot be drawn in the PCB layout.

2. **CSI data/clock lane physical balls.** The 100ASK dts references `&ncsi_pins_a` (label only); the actual balls are in the SoC pinctrl dtsi / the .sls file. The 2x 2-lane sub-channel configuration requires 6 differential pairs (12 balls): CSI_D0P/N, CSI_D1P/N, CSI_CLKP/N for sub-channel A; CSI_D2P/N, CSI_D3P/N, CSI_CLKP/N for sub-channel B. (Or 1x 4-lane + 1x 2-lane.) Without the .sls file, the FPC connector pinout for the two cameras cannot be finalized.

3. **DSI data/clock lane physical balls.** Same — 4 lanes + clock = 10 balls. The 100ASK dts does not enumerate them. Without the .sls file, the display FPC connector pinout cannot be finalized.

4. **USB DP / USB DN physical balls.** The V853 has dedicated USB PHY balls. Without the .sls file, the USB-C receptacle connection (DP, DN, ESD placement, common-mode choke) cannot be finalized.

5. **RESET ball.** The AXP2101 holds the SoC's RESET. Without the .sls file, the AXP2101's RESET_OUT ball cannot be confirmed against the SoC's RESET_IN ball.

6. **24 MHz XTAL balls.** The 100ASK dts does not enumerate the crystal pins. The V853 has dedicated XTAL24MH_IN / XTAL24MH_OUT balls. Without the .sls file, the crystal circuit design (load capacitors, layout) cannot be finalized.

7. **Boot mode pin straps.** The V853 has boot mode pins (typically 2-3 balls) sampled at reset. The 100ASK dts references 'card_boot' and 'card2_boot_para' but does not enumerate the boot pin straps. Without the .sls file, the production-line boot configuration cannot be defined.

8. **Power / ground balls.** The V853 has many VDD, VSS, AVCC, VCC-IO, VCC-PA, VCC-PC, VCC-PD, VCC-PE, VCC-PG, VCC-PI, VCC18-PF, VCC33-PF, VCC-RTC, VCC-PLL, VCC-DRAM, VCC18-MCSI, VCC18-MDSI, VCC33_USB, VDD09_USB, VDD33, VDD18-DRAM, VDD-SYS balls. The exact number and position of each is in the .sls file. Without the .sls file, the PCB power-plane design and decoupling capacitor placement cannot be finalized.

9. **I2S0 alternative pin set.** The 100ASK dts only shows I2S0 on PH0-PH4 (mux conflict with DMIC). The SoC pinctrl dtsi may have alternative I2S0 pin sets (typically Allwinner I2S controllers have 2-4 mux options). Without the SoC pinctrl dtsi, the glasses' design cannot find an alternative I2S0 pin set that coexists with DMIC.

10. **GPIO bank power domain verification.** The V853 has 8 GPIO banks (PA, PB, PC, PD, PE, PF, PG, PH, PI per the GPIO chapter). Each bank has a power domain (VCC-PA, VCC-PC, etc.) that is 1.8 V or 3.3 V. The glasses' design uses 1.8 V for I2C, I2S, CSI SCCB, DSI TE, IMU INT, ALS INT, etc. The specific pin choices must be on a 1.8 V-capable bank. The bank power domain is in the .sls file (or the SoC pinctrl dtsi).

11. **Wake-up / interrupt routing.** The V853 has multiple interrupt controllers (GIC, NMI, R-INTC). The 100ASK dts uses `interrupts = <0 IRQ_TYPE_LEVEL_LOW>; interrupt-parent = <&nmi_intc>;` for the AXP2101. The exact interrupt numbers and NMI mapping for the glasses' devices (IMU INT, ALS INT, TMP117 ALERT, MAX17048 ALERT, BQ25185 INT, etc.) are in the SoC pinctrl dtsi / the device tree bindings.

12. **Pin drive strength and pull-up/down configuration per ball.** The 100ASK dts provides a few drive strength and pull settings (e.g. `drive = <1>; pull = <1>;`) for specific pin sets. The full per-ball drive strength / pull-up / pull-down / open-drain options are in the SoC pinctrl dtsi.

---

## What the glasses' design can do WITHOUT the .sls file

- Use the 100ASK V853-Pro pin choices as a starting point (the kernel dts, U-Boot dts, and sys_config.fex provide 3 independent views of the same SoC's peripheral block assignment).
- Use the documented mux conflicts to identify which 100ASK pin choices must be migrated.
- Migrate the 100ASK pin choices to alternative pin sets within the same GPIO bank once the SoC pinctrl dtsi is available.
- Write the glasses' device tree and Linux driver code.
- Plan the schematic capture at the peripheral block level (which controller, which mux function, which power domain).
- Estimate the compute PCB area and component placement.
- Conduct thermal, power-budget, and acoustic analyses.

## What the glasses' design CANNOT do without the .sls file

- **PCB layout** (LFBGA escape routing, BGA fanout, decoupling capacitor placement). Without the .sls file, the BGA footprint cannot be drawn.
- **Exact pin assignment for CSI data/clock lanes.** Without the .sls file, the camera FPC connector pinout cannot be finalized.
- **Exact pin assignment for DSI data/clock lanes.** Same.
- **Exact pin assignment for USB DP/DN.** Same.
- **Exact pin assignment for the RESET, XTAL24MH, and boot mode pins.** Same.
- **Power plane design and decoupling.** The exact ball map of all power and ground balls is required.
- **Manufacturing.** Without the .sls file, the PCB cannot be fabricated, the LFBGA cannot be assembled, and the production-line programming flow cannot be defined (the boot mode pin straps are in the .sls file).

## Recommendation

**Acquire the V853/V853S_PINOUT.sls file from Allwinner under NDA before proceeding to PCB layout.** Until the .sls file is obtained, the glasses' PCB layout is BLOCKED at the per-ball level. The glasses' schematic capture and device tree work can proceed in parallel, but the layout cannot start.

In the meantime, use the 100ASK V853-Pro pin choices (documented in `v853-public-pin-function-map.yaml`) as the preliminary reference. Migrate to the correct per-ball assignment once the .sls file is obtained.

---

## Stop point

Per the brief: "Do not start PCB routing." This audit is COMPLETE. The audit documents what the public sources provide, what is plausible but requires confirmation, and what is blocked by the missing .sls file. Awaiting your direction on whether to (a) proceed with the NDA acquisition, (b) continue with the schematic-capture work in parallel, or (c) halt pending NDA acquisition.
