# Battery + Power System — Reference Index

This directory holds component references and the power-tree /
power-budget for the Allwinner V853 smart-glasses architecture.

The system load is:

- Allwinner V853 SoC (Cortex-A7 + RISC-V E907 + 1 TOPS NPU)
- 2× MIPI CSI cameras
- 1× monocular micro-OLED / waveguide display
- 1× PDM MEMS microphone
- 2× miniature speakers via I2S class-D amplifier
- Wi-Fi / Bluetooth module (XR829-class)
- 940 nm distributed near-IR LEDs (VSMA1094750X02)
- IMU (6-axis)
- USB-C charging

Heavy AI inference is offloaded to the user's phone; on-device NPU
usage is limited to local prefiltering and device control.

The existing authoritative frame geometry in
`projects/glasses/references/silhouette/wayfarer/` and
`projects/glasses/mechanical/main-frame/WORKING_FRAME_SOLID.FCStd`
was **not modified** during this research pass.

---

## Contents of this directory

```
power/
├── battery/
│   ├── eemb_lp402535.yaml                (350 mAh, 4.0x25x35 mm)
│   ├── eemb_lp503562.yaml                (1100 mAh, 5.0x30x56 mm)
│   ├── eemb_lp301430.yaml                (100 mAh, 3.0x14x30 mm; too small)
│   ├── lipol_301230_90mah.yaml           (90 mAh, 3.0x12x30 mm; too small)
│   ├── varta_cp1254_a4.yaml              (65 mAh, 12 dia x 5.4 mm; too small)
│   ├── lipo_503450_950mah.yaml           (950 mAh, 5.0x34x50 mm)
│   └── lipo_602535_550mah.yaml           (550 mAh, 6.0x25x35 mm)
├── charger/
│   ├── ti_bq25185.yaml                  (primary)
│   ├── microchip_mcp73831.yaml           (simple alternative)
│   ├── microchip_mcp73871.yaml           (load-sharing alternative)
│   └── adi_max77960.yaml                (USB-PD capable alternative)
├── pmic/
│   ├── axp2101.yaml                     (primary, Allwinner ecosystem)
│   ├── tps65217.yaml                    (alternative)
│   └── discrete_ldo_approach.yaml       (discrete regulator design pattern)
├── fuel_gauge/
│   ├── max17048.yaml                    (primary)
│   ├── ti_bq27426.yaml                  (alternative)
│   └── onsemi_lc709203f.yaml            (alternative)
├── usbc/
│   └── usb_c_16pin_midmount.yaml        (5 V charging, 16-pin mid-mount)
├── power-tree.yaml                     (full rail list and components)
├── power-budget.yaml                    (per-component and per-scenario power)
└── README.md                            (this file)
```

---

## 1. Recommended battery cell

**PRIMARY: 2× EEMB LP402535 in parallel (one per temple), 700 mAh / 2.59 Wh total**

Why:

- 4.0 mm thick fits the brief's 4-6 mm temple target
- 25 mm width fits a Wayfarer-style temple pod
- 35 mm length fits a 40-60 mm temple
- EEMB is a reputable Chinese LiPo manufacturer with UN38.3 and IEC62133 certifications (per typical EEMB class; verify per shipment)
- 2× cells in parallel (one per temple) gives natural left/right weight balance and per-temple mechanical isolation
- 2.59 Wh total gives 1.7-3.2 h of normal-to-light use (see battery life table)
- Two cells in parallel is the safest topology: no balancing required, both cells share current and charge/discharge together

**SECONDARY: 2× EEMB LP503562 in parallel (2200 mAh / 8.14 Wh total)** — for users who want 5+ hours of normal use. Requires a 30 mm wide temple cross-section, which is wider than a Wayfarer temple.

**REJECTED:**

- **EEMB LP301430 (100 mAh, 0.37 Wh)**: 200 mAh in parallel is insufficient for the V853 system
- **LiPol 301230 (90 mAh, 0.33 Wh)**: same — too small
- **Varta CoinPower CP1254 A4 (65 mAh, 0.24 Wh)**: 130 mAh in parallel is too small; consider larger Varta CoinPower part if Varta is the preferred vendor
- **All Alibaba unbranded cells**: rejected per the brief — reputation and traceability matter for safety

---

## 2. Recommended cell configuration

**PRIMARY: B. One battery in each temple, electrically paralleled**

| Configuration | Weight balance | Wiring | Charging | Safety | Capacity | Redundancy | Volume |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A. One in one temple | poor (front-heavy) | simplest | simplest | OK | smaller | none | small |
| **B. One each, paralleled** | **excellent** | **moderate** | **moderate** | **OK** | **larger** | **partial** | **moderate** |
| C. One each, separate protected | excellent | complex | complex | excellent | larger | good | moderate |
| D. One central | poor (rear-heavy) | complex | moderate | OK | small | none | OK |

Why B over A: better weight balance (no front-bias), larger total capacity, and per-temple mechanical isolation in case of impact.

Why B over C: separate protected power paths add complexity (two charger ICs, two fuel gauges) for marginal safety benefit. A single AXP2101 + BQ25185 can protect both cells when wired in parallel.

Why B over D: weight distribution is much better with one battery per temple.

**Key safety note for B**: when two cells are wired in parallel, they must be from the same manufacturer, same model, same lot, and matched in capacity. The protection circuit must disconnect the parallel pair if either cell goes out of spec. The AXP2101 + BQ25185 provide this.

---

## 3. Recommended charger

**PRIMARY: TI BQ25185** (WCSP, ~1.6 × 1.6 mm, 5.5 V max input, 1 A charge, I2C, power-path management, thermal regulation, safety timers)

Why: small package, modern, I2C programmable, integrated power-path management, well-documented, in production at TI, available from Mouser and DigiKey. The power-path management is critical for the glasses — it allows the system to run from USB while the battery is charging.

**SECONDARY: ADI MAX77960** — for designs that need USB-PD (not required for 5 V charging but available if the brief evolves).

**ALTERNATIVE: Microchip MCP73871** — load-sharing without I2C, cheaper, larger package.

**SIMPLEST: Microchip MCP73831T** — no I2C, no power-path management. Use only if the design does not need to run from USB while charging.

---

## 4. Recommended PMIC / power tree

**PRIMARY: X-Powers AXP2101** (QFN-32, ~5 × 5 mm)

Why: the AXP2101 is the Allwinner-ecosystem PMIC and is proven with the V853 in the ProjectYosemite reference design. It provides all the required V853 rails (DCDC1-5 for core/DRAM/GPU/PLL and LDO1-4 for I/O/RTC/sensor/MIPI), plus battery charging input, fuel-gauge support, and power-path management. The QFN-32 5 × 5 mm package is on the larger side but the compute PCB lives in the temple, not the front frame, so this is fine.

**The full power tree is in `power-tree.yaml`.** It includes all V853 rails (AVCC, VCC-IO, VCC-DRAM, VCC18-MCSI, VCC18-MDSI, VDD-CPU, VDD-GPU, VDD-RTC), the DDR3L supply, the camera analog, the display analog, the audio I2S supply, the USB-C VBUS, and the IR LED current-limit. Total compute-PCB power-component area is approximately 120-150 mm².

**ALTERNATIVE: TI TPS65217** — multi-rail PMIC, but designed for Sitara AM335x; rails need to be validated against V853 requirements.

**ALTERNATIVE: discrete regulator approach** — 2-3 small buck converters + 3-4 LDOs. More PCB area, more design work, but finer per-rail control. Use when the V853 rails are not a standard PMIC output set.

---

## 5. Recommended fuel gauge

**PRIMARY: ADI MAX17048** (TDFN-8, 2.5 × 2.5 mm, ModelGauge, no external sense resistor, 23 µA active / 1 µA sleep, I2C)

Why: ModelGauge is well-known to work with the Linux power-supply class driver (battery status via /sys/class/power_supply). No sense resistor saves PCB area. Low quiescent current extends battery life during idle.

**ALTERNATIVE: TI BQ27426** — Impedance Track technology, slightly smaller package, also Linux-supported via the bq27xxx driver.

**ALTERNATIVE: onsemi LC709203F** — small, low quiescent. Linux driver support is less universal.

---

## 6. Recommended USB-C connector

**PRIMARY: 16-pin USB Type-C mid-mount receptacle** (typical 8.94 × 7.35 × 2.56 mm)

Why: 5 V default VBUS is sufficient (no USB-PD required). 5.1 kΩ pull-down on CC1 and CC2 requests the default 5 V / 500 mA or 5 V / 1.5 A. USB 2.0 data only (no super-speed). TVS ESD protection on CC, D+, D- is required. No USB-PD controller IC is needed for the 5 V path.

**If USB-PD is required in the future** (e.g. for > 5 V input), a USB-PD controller like Infineon CYPD3170 or similar would be added.

---

## 7. Power budget (preliminary, engineering estimates)

The detailed power budget is in `power-budget.yaml`. The headline numbers:

| Scenario | Typical system power | Description |
| --- | --- | --- |
| Light use | **~0.8 W** | V853 idle, BT only, no camera, no display, audio off, IMU on |
| Normal mixed use | **~1.5 W** | V853 active, one camera on, BT + Wi-Fi intermittent, display occasionally on, audio idle |
| Continuous camera + Wi-Fi + display | **~3.0 W** | V853 + both cameras, Wi-Fi streaming, display on, audio off, IMU on |
| High load | **~3.5 W** | All subsystems active; both cameras, Wi-Fi streaming, display on, audio playback, IMU, IR LEDs |
| Peak transient | **~4.1 W** | All subsystems at peak simultaneously; must be within PMIC and battery peak current limits |

**Source-of-truth priority**: V853 datasheet typical values; component datasheet max values; engineering estimates where the data is not published. The actual measurement on a real glasses prototype will likely differ by 20-40% from these estimates.

**Critical note**: heavy AI inference is offloaded to the phone. The on-device NPU usage is limited to local prefiltering (motion-trigger, AE/AWB pre-stat, voice keyword). The 1 TOPS NPU is not used continuously; this is the single largest assumption in the budget and the largest source of error if the design is changed to use the NPU heavily.

---

## 8. Battery life (preliminary)

Assuming the power budget above and the recommended cell configurations:

| Configuration | Light (0.8 W) | Normal (1.5 W) | Cam+WiFi+Disp (3.0 W) | High load (3.5 W) |
| --- | --- | --- | --- | --- |
| 1× EEMB LP402535 (1.295 Wh) | 1.6 h (97 min) | 0.9 h (52 min) | 0.4 h (26 min) | 0.4 h (22 min) |
| **2× EEMB LP402535 parallel (2.59 Wh)** | **3.2 h (194 min)** | **1.7 h (104 min)** | **0.9 h (52 min)** | **0.7 h (44 min)** |
| 1× EEMB LP503562 (4.07 Wh) | 5.1 h (305 min) | 2.7 h (163 min) | 1.4 h (81 min) | 1.2 h (70 min) |
| 2× EEMB LP503562 parallel (8.14 Wh) | 10.2 h (610 min) | 5.4 h (326 min) | 2.7 h (163 min) | 2.3 h (140 min) |
| 1× 503450 (3.515 Wh) | 4.4 h (264 min) | 2.3 h (141 min) | 1.2 h (70 min) | 1.0 h (60 min) |
| 2× 503450 parallel (7.03 Wh) | 8.8 h (527 min) | 4.7 h (281 min) | 2.3 h (141 min) | 2.0 h (121 min) |
| 1× 602535 (2.035 Wh) | 2.5 h (153 min) | 1.4 h (81 min) | 0.7 h (41 min) | 0.6 h (35 min) |
| 2× 602535 parallel (4.07 Wh) | 5.1 h (305 min) | 2.7 h (163 min) | 1.4 h (81 min) | 1.2 h (70 min) |

**Recommended configuration: 2× EEMB LP402535 in parallel** gives 1.7 h of normal mixed use, 0.9 h of continuous camera+Wi-Fi+display. This is short; if a full-workday battery life is required (4-8 h normal use), the 2× LP503562 parallel configuration (8.14 Wh) gives 5.4 h normal, 2.7 h continuous — at the cost of a 30 mm wide temple pod.

---

## 9. Safety

- **Overcharge protection**: AXP2101 + BQ25185 enforce 4.2 V max charge voltage per cell. Both ICs have programmable OV thresholds.
- **Overdischarge protection**: AXP2101 monitors VBAT; cuts off at 3.0 V per cell. External NTC thermistor for temperature.
- **Short-circuit protection**: AXP2101 has built-in short-circuit detection (configurable threshold). BQ25185 has built-in input short-circuit protection.
- **Thermal protection**: AXP2101 die-temperature sensor; BQ25185 thermal regulation reduces charge current at high temperature. NTC thermistor on the cell is the primary safety sensor.
- **Charging temperature**: charge is allowed in the 0-45 °C range (typical LiPo). At < 0 °C, charging must be inhibited (BQ25185 supports this via NTC). At > 45 °C, charging is reduced or stopped.
- **Battery balancing considerations if two cells are used**: the recommended configuration is two cells in PARALLEL (same model, same lot). Parallel cells self-balance during charge and discharge; no separate balancing IC is needed. Serial cells would require a balancing IC; this is NOT the recommended configuration.
- **Cell swelling / damage concerns**: the cell must be mechanically constrained in the temple pod with a slight compression fit (no rigid constraint; allow ~5% thickness expansion over cycle life). The cell must be protected from sharp edges and from accidental puncture. A rigid enclosure with foam padding is the standard solution.
- **Physical separation from high-temperature components**: the cell must be physically separated from the AXP2101 (which dissipates 200 mW of losses), the IR LEDs (which can heat to 50-60 °C in continuous operation), and the speaker driver (which dissipates 100-200 mW). Minimum 5 mm physical separation, with thermal foam or tape.

---

## 10. Mechanical envelope implications

The temple target is approximately 4-6 mm usable thickness and 40-60 mm usable length. The Wayfarer reference STL has a 1.6 mm temple transition thickness — too thin to host any battery. A custom temple with a battery pod is required for all serious configurations.

- **2× EEMB LP402535 (PRIMARY)**: 4.0 × 25 × 35 mm per cell. Two cells = 4.0 mm × 50 mm × 35 mm. Per-temple pod: 5 mm (4 mm cell + 1 mm wall + foam) × 26 mm × 40 mm. Achievable in a custom temple.
- **2× EEMB LP503562 (HIGHER CAPACITY)**: 5.0 × 30 × 56 mm per cell. Two cells per temple: 5 mm × 60 mm × 56 mm. This is the dominant dimension; the temple pod must be 60 mm long, which is achievable in a long-temple design but pushes the front-of-temple-to-bend transition further back.
- **Varta CoinPower CP1254 A4**: 12 × 5.4 mm. Two cells = 12 × 12 × 5.4 mm. But the 130 mAh total is too small for the V853 system.

**Two smaller cells vs one larger cell**: two smaller cells (one per temple) are preferable to one larger cell because (a) better weight balance, (b) per-temple mechanical isolation, (c) per-temple replaceability, (d) the brief explicitly targets battery-in-temple.

---

## 11. Alternatives

- **If a smaller battery is mandatory** (e.g. 4 mm max thickness): 2× EEMB LP301430 parallel (200 mAh / 0.74 Wh) — but this is too small for the V853 system. Listed for completeness.
- **If a larger battery is acceptable** (5 mm thickness, 30 mm width, 56 mm length): 2× EEMB LP503562 parallel (2200 mAh / 8.14 Wh) — much longer battery life, but requires a wider and longer temple.
- **If Varta CoinPower is the preferred vendor**: a larger Varta CoinPower part (e.g. CP1654) may be in the 150-200 mAh class. Verify the exact part number and dimensions.
- **If LiFePO4 chemistry is preferred** (3.2 V nominal, lower energy density, longer cycle life, safer thermal): consider AXP2101 + BQ25185 with a LiFePO4 cell. The AXP2101 supports LiFePO4 charge voltage (3.6 V max).
- **If USB-PD is required** (e.g. for fast charging > 5 V): use ADI MAX77960 charger and add an Infineon CYPD3170 USB-PD controller.

---

## 12. Risks

- **Power budget uncertainty**: the V853 system power is an engineering estimate; the actual measurement on a real prototype will likely differ by 20-40%. The battery life numbers above are the central estimate; the actual range is ±40%.
- **NPU usage assumption**: heavy AI is offloaded to the phone per the brief. If the design is changed to use the NPU heavily, the high-load power could exceed 5 W, and the battery life would halve.
- **Temple mechanical redesign required**: the Wayfarer temple is 1.6 mm thick, which is too thin for any battery. A custom temple with a 5-8 mm pod is required. This is a frame-level change.
- **Cell supplier quality**: the recommended cells (EEMB) are from a reputable Chinese manufacturer. Verify the actual UN38.3, IEC62133, and UL certifications per shipment. Do not use unbranded Alibaba cells.
- **AXP2101 ecosystem dependency**: the AXP2101 is the Allwinner-ecosystem PMIC; if the SoC changes, the PMIC must change too.
- **Single supplier for AXP2101**: the AXP2101 is supplied by X-Powers. If the supplier is constrained, the compute PCB design must change.

---

## 13. Confidence levels

- **Battery cell dimensions**: HIGH for the EEMB LP-series (model-number convention is industry-standard and well-validated). MEDIUM for electrical specs (per-cell datasheet summaries, not the full datasheet).
- **Charger IC**: HIGH (TI BQ25185 datasheet summary is well-known).
- **PMIC**: HIGH (AXP2101 is proven in the ProjectYosemite reference design; the rail set is matched to the V853 requirements).
- **Fuel gauge**: HIGH (MAX17048 is well-known and Linux-supported).
- **USB-C**: HIGH (USB-C 5 V is standard; the connector pinout is universal).
- **Power budget**: LOW_TO_MEDIUM (V853 system power is an engineering estimate; the actual measurement on a prototype will differ).
- **Battery life**: MEDIUM (derived from the power budget; the error is the same as the power budget error).

---

## 14. Datasheet / manufacturer sources

- **EEMB**: https://www.eemb.com/ (LP-series datasheets available on the product page)
- **TI BQ25185**: https://www.ti.com/product/BQ25185
- **TI BQ27426**: https://www.ti.com/product/BQ27426
- **Microchip MCP73831**: https://www.microchip.com/en-us/product/MCP73831
- **Microchip MCP73871**: https://www.microchip.com/en-us/product/MCP73871
- **ADI MAX17048**: https://www.analog.com/en/products/max17048.html
- **ADI MAX77960**: https://www.analog.com/en/products/max77960.html
- **ADI MAX98390**: https://www.analog.com/en/products/max98390.html (audio amp, from audio reference)
- **X-Powers AXP2101**: https://github.com/YuzukiHD/ProjectYosemite/blob/main/Datasheets/AXP2101_Datasheet_V1_en.pdf (mirrored in the V853 reference)
- **Allwinner V853**: https://github.com/YuzukiHD/ProjectYosemite/blob/main/Datasheets/v853-amp-v853s_datasheet_v1.1%201.pdf (mirrored in the V853 reference)
- **USB-C specification**: USB Implementers Forum (usb.org)
- **Varta CoinPower**: https://www.varta-ag.com/en/company/brands/varta-microbattery

---

## Stop point

Per the user's instructions, this is the battery + power reference-acquisition deliverable. **No mechanical placement, no PCB design, no FreeCAD work, and no modification to the existing Wayfarer geometry, the working solid, or any glasses electronics has been started.** The IMU and any other minor components have not been started. Awaiting explicit instruction to continue.
