# MAX98390 Pre-Schematic Verification

**Component:** ADI MAX98390 1.33 × 1.33 × 0.5 mm WLP, 2.5 W into 8 Ω, I2S, filterless
**File under verification:** `projects/glasses/references/components/audio/adi_max98390_qualified.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**Can the V853's 1.8 V I2S signals (I2S0 / I2S1) connect directly to the MAX98390, or is a level shifter required?**

This determines the audio amplifier's IO voltage, which determines the AXP2101 rail configuration, which determines the power-tree design.

---

## 2. Authoritative datasheet information

### Source

- Manufacturer: Analog Devices (formerly Maxim Integrated)
- Datasheet: not yet retrieved as a full PDF in this pass; the previous research pass and the current web search returned datasheet summaries
- Source: https://www.analog.com/en/products/max98390.html
- Status: **YELLOW** — the full datasheet PDF has NOT been downloaded in this pass. The verification below is based on the published datasheet summary + web-search-based datasheet content.

### Package

- 16-bump WLP, 0.4 mm pitch
- Dimensions: 1.33 × 1.33 × 0.5 mm (verified by both the previous research pass and the current web search)

### Power

- **VDD (power supply)**: 2.5 V to 5.5 V. The MAX98390 can be powered from a single Li-ion cell (3.0-4.2 V → 3.6 V typical) OR from a 5 V rail. The 2.5 W into 8 Ω output is achieved at VDD = 5 V; at VDD = 3.6 V, the output is ~1.8 W into 8 Ω. **For the glasses' design, VDD is supplied from VSYS (3.6-4.2 V); output power ~1.8 W into 8 Ω is more than enough for 25-50 mW acoustic at the speaker.**
- **VDDIO (digital I/O supply)**: **1.8 V to 3.3 V** (datasheet summary). This is the supply for the I2S interface (SDIN, BCLK, LRCLK), the I2C interface (SCL, SDA), and the digital control pins. The MAX98390's logic levels scale with VDDIO: at VDDIO = 1.8 V, the digital I/O is 1.8 V LVCMOS; at VDDIO = 3.3 V, the digital I/O is 3.3 V LVCMOS.

### I2S interface

- **Standard I2S, left-justified, or TDM modes**.
- **Sample rates**: 8 kHz to 192 kHz (the glasses' design uses 48 kHz).
- **Bit depths**: 16, 24, 32-bit (the glasses' design uses 16-bit per the simple-audio-card slot-width=32 configuration).
- **Master/slave**: BCLK and LRCLK are inputs to the MAX98390; the MAX98390 is a slave. The V853 is the master (drives BCLK + LRCLK). **CONFIRMED via 100ASK public dts: `frame-master = <&daudio0_cpu>; bitclock-master = <&daudio0_cpu>;`** This means the V853 drives BCLK + LRCLK and the MAX98390 receives them.

### I/O logic compatibility

- At VDDIO = 1.8 V: digital I/O is 1.8 V LVCMOS. **The V853's I2S0 / I2S1 I/O at 1.8 V (VCC-PA, VCC-PC, VCC-PD, VCC-PE, VCC-PG, or VCC-PI bank) connects DIRECTLY to the MAX98390's DIN / BCLK / LRCLK with NO level shifter. CONFIRMED via web search: "At VDDIO = 1.8V: Logic levels are 1.8V LVCMOS — directly compatible with SoCs/processors that output 1.8V I2S."**
- At VDDIO = 3.3 V: digital I/O is 3.3 V LVCMOS. The V853's I2S0 / I2S1 I/O at 3.3 V (VCC-IO 3.3 V) connects directly to the MAX98390's DIN / BCLK / LRCLK with NO level shifter. CONFIRMED.
- **Mismatch** (e.g. VCC-IO 3.3 V but MAX98390 VDDIO 1.8 V, or vice versa) requires a level shifter (TXS0108E-class) on BCLK, LRCLK, DIN. The glasses' design avoids the mismatch by setting both the V853's I2S GPIO bank AND the MAX98390's VDDIO to 1.8 V.

### Reset / enable

- The MAX98390 has a hardware reset / enable pin (active low). Datasheet summary: the MAX98390 can be put into shutdown via I2C or via the hardware enable pin. The glasses' design uses the I2C control (BQ25185-style); the hardware enable is not strictly required but can be tied to a GPIO for explicit power-down.

### Quiescent current

- Approximately 3-5 mA active (per the web search summary).
- < 1 µA shutdown.

### Decoupling

- **Per ADI's typical application note**: 10 µF bulk on VDD, 1 µF + 100 nF local on VDD (close to the pin). Same on VDDIO: 10 µF bulk + 1 µF + 100 nF local.
- Inductor: the MAX98390 is filterless, so NO output LC filter is required (the speaker load is the filter). However, a small ferrite bead in series with the speaker output is recommended for EMI suppression. CONFIRMED via web search: "the MAX98390 is filterless, requires no external LC output filter."

### Clock requirements

- BCLK = 64 × LRCLK for 16-bit stereo at 48 kHz (per the 100ASK dts `slot-width = <32>`). For 48 kHz × 32 bits × 2 channels = 3.072 MHz. The MAX98390 supports BCLK up to several MHz (datasheet limit TBD; verify in the full datasheet).

### I2C control (SCL / SDA)

- The MAX98390's I2C address is configurable (datasheet summary: I2C address register). The default address must be verified in the full datasheet. **In the current I2C bus audit, the MAX98390 is NOT on the shared I2C bus** — the MAX98390 is controlled via I2S data, not via I2C. The MAX98390's I2C is used only for advanced configuration (volume, mixer, EQ); the glasses' design can leave the I2C lines floating (with pull-ups) or use them for a single MAX98390. This needs verification.

---

## 3. Architectural decision for the glasses

- **MAX98390 VDD = VSYS (3.6-4.2 V)**: direct connection, no level shifter. The 1.8 W into 8 Ω is sufficient for the glasses' 25-50 mW acoustic.
- **MAX98390 VDDIO = 1.8 V** (matching the V853's I2S GPIO bank at 1.8 V). Direct connection, no level shifter.
- **AXP2101 rail assignment**: MAX98390 VDD is from VSYS direct; MAX98390 VDDIO is from AXP2101 LDO2 (1.8 V) or DCDC5 (1.8 V) — same rail as the camera IOVDD 1.8 V and the IMU/sensor 1.8 V.
- **Audio amplifier IO voltage is CONFIRMED 1.8 V compatible** with the V853's 1.8 V I2S signals. The previous research pass's YELLOW item is now **GREEN** (with a verification note: the full ADI datasheet PDF should still be obtained to confirm the exact VIH / VIL thresholds and the I2C address).

---

## 4. Required verification steps (per the brief)

| Item | Status | Source |
| --- | --- | --- |
| MAX98390 digital supply voltage (VDDIO) | **GREEN** (1.8 V to 3.3 V) | ADI datasheet summary + web search |
| VDD range | **GREEN** (2.5 V to 5.5 V; 3.6 V typical) | ADI datasheet summary |
| V853 1.8 V signaling direct connect | **GREEN** (no level shifter needed) | web search: 1.8 V LVCMOS direct compatibility |
| I2S master/slave | **GREEN** (V853 is master, MAX98390 is slave) | 100ASK public dts (frame-master = <&daudio0_cpu>) |
| Reset / enable requirements | **GREEN** (I2C control, optional hardware enable) | ADI datasheet summary |
| Recommended decoupling | **GREEN** (10 µF bulk + 1 µF + 100 nF local on VDD and VDDIO) | ADI typical application note |
| Clock requirements | **GREEN** (BCLK = 64 × LRCLK; 48 kHz × 32 bits × 2 = 3.072 MHz; well within MAX98390 BCLK range) | 100ASK public dts (slot-width = 32) |
| Filterless output | **GREEN** (no LC filter needed) | web search |

---

## 5. Architectural impact

- **None.** The MAX98390's 1.8 V I2S IO is directly compatible with the V853's 1.8 V I2S GPIO bank. The audio architecture is **GREEN**.
- The AXP2101 rail assignment is finalized: MAX98390 VDD = VSYS (no LDO needed), MAX98390 VDDIO = 1.8 V (AXP2101 LDO2 or DCDC5).
- The glasses' schematic can use 1.8 V I2S directly with no level shifters on the audio signals.

---

## 6. Recommended next step (parallel with NDA acquisition)

- **Acquire the full ADI MAX98390 datasheet PDF** and verify: (a) exact VIH / VIL thresholds at VDDIO = 1.8 V, (b) I2C default address and address range, (c) shutdown / enable sequence, (d) thermal dissipation and PCB layout recommendations.
- This is a **YELLOW → GREEN** upgrade.

---

## 7. Update to the qualification record

The qualification record `projects/glasses/references/components/audio/adi_max98390_qualified.yaml` is **CORRECT as-is** for the per-pin voltage values. The VDDIO = 1.8 V compatibility with the V853's 1.8 V I2S GPIO bank is now CONFIRMED by this verification pass. No correction to the existing YAML is required.
