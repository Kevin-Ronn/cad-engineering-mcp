# V853/V853S_PINOUT.sls — NDA Blockers

**Project:** projects/glasses/ — V853-based smart glasses
**Date:** 2026-09-05
**Status:** READ-ONLY. No CAD / PCB / STL / FreeCAD files were modified.

This file enumerates exactly which decisions in the glasses' design are
BLOCKED by the missing `V853/V853S_PINOUT.sls` file. The file is
part of the Allwinner NDA datasheet package and is not publicly
redistributable. See `source/SOURCE-SEARCH-LOG.md` for the documented
public-source search.

---

## 1. LFBGA-318 12x12x0.5 mm package ball map

The V853 ships in a 12 mm x 12 mm LFBGA-318 with 0.50 mm ball pitch
(per the V853 datasheet section 2.1.1). The 318 balls are organized
in a 21x21 grid (or similar) with 4 missing-corner balls.

**The exact ball-to-pin map (row, column, signal name) is in the V853/V853S_PINOUT.sls file.**

**Status:** RED. The glasses' PCB layout (LFBGA escape routing, BGA
fanout, via placement) cannot start without this map.

**Resolution:** Acquire the .sls file from Allwinner under NDA. Place
the file at `projects/glasses/references/components/compute/v853/source/V853_V853S_PINOUT.sls`. Record the SHA-256 in `source/SOURCE-SEARCH-LOG.md`.

---

## 2. Per-ball peripheral pin assignments

The V853 datasheet section 2.2 states: *"For details about pin description of the V853/V853S, see the V853/V853S_PINOUT.sls."* The 100ASK V853-Pro public source provides function-to-pin mapping (e.g. "TWI0 is on PE16/PE17") but the underlying physical ball numbers are in the .sls file.

**The following signals are not in the public source:**

### CSI / MIPI CSI-2 (camera)
- CSI_D0P, CSI_D0N, CSI_D1P, CSI_D1N, CSI_CLKP, CSI_CLKN
- CSI_D2P, CSI_D2N, CSI_D3P, CSI_D3N (for the second sub-channel in 2x 2-lane mode)
- CSI_REFCLK_P / CSI_REFCLK_N (the reference clock; not always present in MIPI CSI-2)

### DSI / MIPI DSI-2 (display)
- DSI_D0P, DSI_D0N, DSI_D1P, DSI_D1N, DSI_D2P, DSI_D2N, DSI_D3P, DSI_D3N
- DSI_CLKP, DSI_CLKN
- DSI_DPHY_TURNREQUEST (the TE / turn-request line; may be on a different pin)

### USB 2.0 DRD
- USB_DP, USB_DN
- USB_VBUS (the VBUS sense input to the SoC; distinct from the USB-C receptacle's VBUS pin)
- USB_ID (the OTG ID pin; PH14 in the 100ASK reference)
- USB_RREF (the reference resistor; typically a dedicated ball)

### I2C / TWI
- All 5 TWI controllers have 2 pins (SCL, SDA) at the per-bank level
- The exact ball numbers for PE16/PE17 (TWI0), PA14/PA15 (TWI1), PH5/PH6 or PE20/PE21 (TWI2), PI3/PI4 or PA10/PA11 (TWI3), PI1/PI2 (TWI4) are in the .sls file

### SPI / SPIF
- PC0, PC1, PC2, PC3, PC4, PC5 (SPI0)
- PH5, PH6, PH7, PH8, PH9 (SPI1)
- PF20-PF31 (SPIF0)
- The exact ball numbers are in the .sls file

### I2S / PCM
- PH0, PH1, PH2, PH3, PH4 (I2S0 in the 100ASK reference)
- PE7, PE8, PE9, PE10, PE11 (I2S1)
- The exact ball numbers for the I2S0 alternative pin set (to avoid the DMIC conflict) are in the .sls file

### DMIC
- PH0, PH1, PH2, PH3, PH4 (DMIC in the 100ASK reference)
- The exact ball numbers for the DMIC alternative pin set (to avoid the I2S0 conflict) are in the .sls file

### UART
- PH9, PH10 (UART0)
- PG6, PG7 (UART1)
- PE10, PE11, PE12, PE13 (UART2 4-wire)
- PH0, PH1 (UART3; conflicts with DMIC / I2S0)
- The exact ball numbers for the UART2 alternative pin set (to avoid the GMAC0 conflict) are in the .sls file

### SD / SDIO / eMMC
- PC0-PC11 (SDC2 / SMHC2 for eMMC; 8-bit data + clock + command + reset + data strobe)
- PG0-PG5 (SDC1 / SMHC1 for SDIO Wi-Fi; 4-bit data + clock + command)
- PF0-PF5 (SDC0 / SMHC0 for SD card; not used in the glasses' design)
- The exact ball numbers are in the .sls file

### PWM
- PH11 (PWM4)
- PH8 (PWM8)
- PD22 (PWM9)
- Other PWM channels (PWM0-PWM3, PWM5-PWM7, PWM10-PWM11) are not enumerated in the public source; the exact ball numbers are in the .sls file

### Camera / IMU / Sensor / Status GPIOs
- All GPIO pin-to-ball mapping is in the .sls file
- Specific pins used in the 100ASK reference (PA12, PA13, PA18, PA19, PA20, PA21, PE1, PE13, PH2, PH3, PH13, PH14, PH15, PI0, PG7) are function-level; the ball numbers are in the .sls file

### AXP2101 PMIC
- The 100ASK dts uses TWI4 (PI1, PI2) at address 0x34. The exact ball numbers are in the .sls file
- The AXP2101's RESET_OUT to the SoC's RESET_IN: the SoC's RESET_IN ball is in the .sls file
- The AXP2101's IRQ line: the SoC's NMI / GIC interrupt input is in the .sls file

### Boot and Reset
- Boot mode pin straps (typically 2-3 balls): in the .sls file
- RESET ball: in the .sls file
- JTAG pins (if used for debug): in the .sls file
- FEL mode entry pins: in the .sls file

### Crystal
- 24 MHz XTAL24MH_IN, XTAL24MH_OUT: in the .sls file

### Power and Ground
- VDD-SYS balls (multiple, typically 4-6)
- VCC-RTC, VCC-PLL
- VCC-IO, VCC-PA, VCC-PC, VCC-PD, VCC-PE, VCC-PG, VCC-PI
- VCC18-PF, VCC33-PF
- VCC-DRAM, VDD18-DRAM
- VCC18-MCSI, VCC18-MDSI
- VCC33_USB, VDD09_USB, VDD33
- AVCC
- VCC-EFUSE
- VSS balls (multiple, typically 30-50)
- The exact number, position, and ball map of all power and ground balls are in the .sls file

---

## 3. Decisions blocked

The following decisions are BLOCKED by the missing .sls file:

1. **PCB layout** (LFBGA escape routing, BGA fanout, via placement, decoupling capacitor placement). Cannot start.
2. **Camera FPC connector pinout** (which 100ASK mux pins map to which BGA balls). Cannot finalize.
3. **Display FPC connector pinout**. Cannot finalize.
4. **USB-C receptacle connection** (DP, DN, ESD, common-mode choke). Cannot finalize.
5. **Crystal circuit design** (24 MHz crystal, load capacitors, layout). Cannot finalize.
6. **Power plane design** (which balls need VDD-SYS decoupling, which need VCC-IO, etc.). Cannot finalize.
7. **Ground plane design** (VSS ball distribution). Cannot finalize.
8. **Boot mode pin straps** (production-line configuration). Cannot finalize.
9. **RESET circuit** (AXP2101 RESET_OUT to SoC RESET_IN). Cannot finalize.
10. **JTAG debug header** (if used). Cannot finalize.
11. **Manufacturing fixtures** (test pads, programming header). Cannot finalize.

## 4. Decisions NOT blocked

The following decisions can proceed in parallel with the .sls file acquisition:

1. **Peripheral block selection** (which V853 IP block for which glasses' function). Done in `v853-glasses-pin-assignment.yaml`.
2. **Mux conflict analysis** (which 100ASK pin choices must be migrated). Done in `v853-public-pin-function-audit.md`.
3. **Schematic capture at the peripheral block level** (with placeholder pin numbers; fill in the actual ball numbers once the .sls file is obtained).
4. **Device tree and Linux driver development** (Linux, U-Boot, drivers).
5. **Thermal and power-budget analysis** (per `power-budget.yaml`).
6. **Acoustic analysis and speaker back-volume design**.
7. **Display engine NDA acquisition** (Lumus / DigiLens).
8. **Wi-Fi/BT module specific datasheet PDF acquisition**.
9. **Battery cell specific datasheet PDF acquisition** (EEMB).
10. **MAX98390 IO voltage verification** (1.8 V vs 3.3 V per the ADI datasheet PDF).

## 6. Logical schematic work can proceed in parallel (2026-09-05 update)

The V853 public-source pin-function audit (see `v853-public-pin-function-audit.md`) confirms that approximately 70% of the glasses' pin-function assignment is publicly verifiable, and the remaining 30% requires the SoC pinctrl dtsi (not publicly available) or the V853/V853S_PINOUT.sls.

**The logical schematic architecture for the glasses is now documented in:**

- `projects/glasses/references/electrical/logical-schematic/README.md` (entry point)
- `projects/glasses/references/electrical/logical-schematic/v853-logical-connectivity.yaml` (every V853 peripheral's logical signal list, voltage domain, and source-reference)
- `projects/glasses/references/electrical/logical-schematic/logical-signal-table.yaml` (every net in the design: source / destination / bus / voltage / direction / pull / status / source-reference)
- `projects/glasses/references/electrical/logical-schematic/power-rail-table.yaml` (every voltage rail: source / consumers / current estimate / sequencing / status)
- `projects/glasses/references/electrical/logical-schematic/interface-matrix.yaml` (which V853 peripheral block is used for which glasses function; per-peripheral use / not-use classification)
- `projects/glasses/references/electrical/logical-schematic/schematic-design-gates.md` (GREEN / YELLOW / RED design-gate summary for the eventual PCB schematic capture)

**The logical schematic work is READY for the eventual PCB schematic capture at the peripheral block level.** The eventual PCB layout at the per-ball level is BLOCKED on the V853/V853S_PINOUT.sls file (RED items 1-5 above).

**What the logical schematic work does NOT cover** (still blocked on the .sls file):

- LFBGA-318 escape routing (requires per-ball coordinates)
- BGA fanout and via placement (requires per-ball coordinates)
- Decoupling capacitor placement under the BGA (requires per-ball power and ground ball positions)
- Specific GPIO ball assignments for the ~20 glass-specific GPIOs (the function is verified, the ball is in the .sls file)
- USB DP/DN exact balls
- RESET, XTAL24MH, boot mode pin physical balls

**What the logical schematic work DOES cover** (ready for schematic capture):

- The peripheral block selection for every glasses function (14 peripherals)
- The bus and interface for every glasses function (MIPI CSI, MIPI DSI, SDIO, I2S, DMIC, I2C, USB, SPI, UART, PWM, GPIO)
- The voltage domain for every signal (1.8 V or 3.3 V)
- The pull-up / pull-down requirement for every signal
- The decoupling / ESD requirement for every signal
- The power-on sequencing per the AXP2101 PMIC and the V853 datasheet Figure 2-2
- The battery + charger + power-path architecture (BQ25185 with 2x EEMB LP402535 in parallel)
- The shared I2C bus topology (TWI4 with 7 unique-address devices)
- The audio amplifier topology (2x MAX98390, one per temple, I2S0 + I2S1)
- The USB-C topology (5 V only, no USB-PD, TPD4E05U04 ESD)
- The display topology (direct V853 DSI 4-lane, no bridge)
- The dual-camera CSI architecture (2x 2-lane sub-channel mode with MIPI virtual-channel demux)
- The boot architecture (eMMC primary, SD card via pogo-pin debug connector, FEL recovery)

**Next step**: when the V853/V853S_PINOUT.sls is obtained, the logical schematic work can be migrated to a full schematic with per-ball assignments. The peripheral block decisions are already made; the migration is mostly mechanical (replace each `physical_bga_ball: UNKNOWN` with the actual ball number from the .sls file).

---

## 5. Resolution path

**Action 1: Acquire V853/V853S_PINOUT.sls from Allwinner.**

- Contact: Allwinner Technology (allwinnertech.com). The typical path is to contact Allwinner FAE / sales with an NDA request.
- Distributors: LCSC, Mouser, DigiKey may also provide the NDA package for active customers.
- The .sls file is part of the V853 datasheet V1.1 (Rev 2022-03-23) package, which is the same version mirrored in `projects/glasses/references/components/compute/v853/v853-datasheet.pdf`.

**Action 2: Once obtained, place the file at:**

`projects/glasses/references/components/compute/v853/source/V853_V853S_PINOUT.sls`

**Action 3: Compute the SHA-256 of the file and record:**

- Source URL (e.g. `https://allwinnertech.com/index.php?c=show&id=XXX&p=download`)
- Package version (e.g. "V853 Datasheet V1.1 - 2022-03-23")
- Date downloaded
- SHA-256 checksum

**Action 4: Update the public-pin-function map to include the actual BGA ball numbers.**

Edit `v853-public-pin-function-map.yaml` to replace each `physical_bga_ball: UNKNOWN` with the actual ball number from the .sls file.

**Action 5: Update the audit and BOM status.**

Edit `v853-public-pin-function-audit.md` to reclassify the RED items as GREEN once the actual ball numbers are known.

## 6. Stop point

Per the brief: "Do not start PCB routing." This file documents the
blockers. No PCB routing is started. The next step (NDA acquisition)
is a separate action requiring user authorization.
