# V853 I2S / DMIC Multiplexing Pre-Schematic Verification

**Component:** Allwinner V853 SoC
**File under verification:** `projects/glasses/references/components/compute/v853/i2s-audio-validation.yaml` and `dmic-validation.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**Can the V853 simultaneously support I2S0 → left MAX98390, I2S1 → right MAX98390, AND DMIC → MP23DB01HP, all at 1.8 V?**

This determines whether the audio architecture is feasible at the peripheral block level.

---

## 2. Known conflict in the public 100ASK reference

The 100ASK V853-Pro public source (`device/config/chips/v853/configs/100ask/board.dts`) uses the following pin assignments for the conflicting blocks:

- `dmic_pins_a` (src-1 line 775-781): pins = "PH0", "PH1", "PH2", "PH3", "PH4"; function = "dmic"; muxsel = 6
- `daudio0_pins_a` (src-1 line 791-797): pins = "PH0", "PH1", "PH2", "PH3", "PH4"; function = "i2s0"; muxsel = 3
- `uart3_pins_active` (src-1 line 581-587): pins = "PH0", "PH1"; function = "uart3"; muxsel = 5

**The same 5 pins (PH0, PH1, PH2, PH3, PH4) are claimed by THREE different peripherals.** The 100ASK reference resolves this by:
- Disabling the on-die audio codec and DMIC (src-1 line 1434-1435: `&dmic_mach { status = "disabled"; ... }`)
- Using I2S0 on PH0-PH4 (which routes the on-die audio codec's output to the audio jack)
- Disabling UART3 (not in the kernel dts; can be activated if needed)

**For the glasses' design, this is NOT acceptable** because the glasses NEED both DMIC (for the microphone) and I2S0 (for the left speaker). The 100ASK reference's I2S0 pin set on PH0-PH4 is unusable for the glasses.

---

## 3. Alternative I2S0 / DMIC pin sets

The V853 has multiple mux options per GPIO ball. The 100ASK reference documents ONE option per peripheral; the V853 datasheet section 1.3.7.2 (I2S/PCM) and section 1.3.7.3 (DMIC) state that each controller has multiple mux options, but the EXACT options are in the SoC pinctrl dtsi (`sun8iw21p1-pinctrl.dtsi`) which is NOT publicly available.

### What the public source does NOT provide

- The exact list of alternative I2S0 mux groups (other than PH0-PH4)
- The exact list of alternative DMIC mux groups (other than PH0-PH4)
- The exact list of alternative I2S1 mux groups (the 100ASK uses PE7-PE11, but there may be others)
- The exact list of alternative UART3 mux groups (other than PH0-PH1)

### Search performed

- Web search for "Allwinner V853 pinctrl daudio0 daudio1 dmic alternative pin mux groups" returned no useful results.
- Web search for "sun8iw21p1 pinctrl daudio i2s0 alternative pin group GPIO" returned no useful results.
- The SoC pinctrl dtsi is the canonical source; it is NOT in the public 100ASK Tina SDK (only the board dts is, which references labels without enumerating underlying pins).
- The Allwinner BSP is NDA-gated.

### Conclusion

**The exact alternative I2S0 / DMIC pin sets are UNKNOWN from the public source.** The V853 datasheet does NOT enumerate them in the PDF (it only says "see V853/V853S_PINOUT.sls"). The 100ASK reference only documents one option per peripheral (PH0-PH4 for both I2S0 and DMIC).

---

## 4. Available inference from the V853 datasheet

The V853 datasheet section 1.3.7.2 (I2S/PCM) states:
- 2x I2S/PCM
- Standard Philips I2S, left-justified, right-justified, PCM, TDM
- Sample rates 8 kHz to 384 kHz

The V853 datasheet section 1.3.7.3 (DMIC) states:
- 1x DMIC controller
- PDM (single-bit data + clock)
- Up to 8 microphones

The V853 datasheet section 1.3.8 (GPIO) describes 8 GPIO banks (PA, PB, PC, PD, PE, PF, PG, PH, PI), each with 16 pins (approximately 128 GPIO total). The I2S and DMIC mux options are within these 8 banks.

The 100ASK reference uses:
- I2S1 on PE7-PE11 (bank PE)
- DMIC on PH0-PH4 (bank PH)
- I2S0 on PH0-PH4 (bank PH; CONFLICT)

The PE bank has 16 pins; PE7-PE11 is 5 pins. The remaining PE pins (PE0-PE6, PE12-PE15) are available for I2S0 if the mux supports it. **This is a possibility that the SoC pinctrl dtsi would confirm.**

The PH bank has 16 pins; PH0-PH4 is 5 pins. The remaining PH pins (PH5-PH15) are available for I2S0 if the mux supports it. **This is another possibility.**

Without the SoC pinctrl dtsi, we cannot confirm that I2S0 has an alternative mux group on PE0-PE6, PE12-PE15, or PH5-PH15.

---

## 5. Architectural impact

The audio architecture is **PROVISIONAL** (YELLOW):

- I2S1 on PE7-PE11 is GREEN (per 100ASK reference; verified).
- DMIC on PH0-PH4 is GREEN for the 100ASK reference; for the glasses' design, the DMIC can use the same PH0-PH4 pin set IF I2S0 is moved to a different pin set. But if I2S0 is forced onto PH0-PH4 by the V853's mux options, then DMIC and I2S0 cannot coexist on PH0-PH4.
- I2S0 on PH0-PH4 (per 100ASK) CONFLICTS with DMIC. The 100ASK reference resolves this by disabling DMIC. The glasses' design cannot do that.

**To resolve: the V853/V853S_PINOUT.sls file (or the SoC pinctrl dtsi) must be obtained to confirm whether I2S0 has an alternative mux group that does NOT conflict with DMIC.**

If I2S0 has NO alternative mux group (i.e. it can only be on PH0-PH4), the audio architecture is **RED**: DMIC and I2S0 cannot coexist.

If I2S0 HAS an alternative mux group (e.g. on PE0-PE6, PE12-PE15, or PH5-PH15), the audio architecture is **GREEN** with the alternative pin set.

---

## 6. Provisional decision (for the schematic capture to proceed)

The glasses' design uses **I2S0 on an alternative pin set (TBD; likely PE0-PE6, PE12-PE15, or PH5-PH15)** and **I2S1 on PE7-PE11 (per 100ASK)**. The DMIC is on **PH0-PH4 (per 100ASK)**. The exact I2S0 alternative pin set will be determined when the V853/V853S_PINOUT.sls is obtained.

The 100ASK reference's I2S0 pin set on PH0-PH4 is **NOT USED** in the glasses' design. The 100ASK reference's PH bank usage for I2S0 is replaced by an alternative pin set for the glasses' design.

---

## 7. Update to the qualification records

The qualification records (`i2s-audio-validation.yaml` and `dmic-validation.yaml`) are **CORRECT as-is** in their YELLOW classification of the I2S0 / DMIC pin conflict. The verification pass confirms the conflict and documents the resolution path (alternative I2S0 pin set per the SoC pinctrl dtsi).

No correction to the existing YAMLs is required at this time. The YELLOW status remains until the SoC pinctrl dtsi or the V853/V853S_PINOUT.sls is obtained.

---

## 8. Status

| Item | Status | Notes |
| --- | --- | --- |
| I2S0 on PH0-PH4 (per 100ASK) | **REJECTED for the glasses** | Conflicts with DMIC |
| I2S1 on PE7-PE11 (per 100ASK) | **GREEN** | No conflict with DMIC; conflicts with GMAC0 (but GMAC0 is disabled in the glasses' design) |
| DMIC on PH0-PH4 (per 100ASK) | **GREEN for the glasses** | Used as-is |
| I2S0 alternative pin set (TBD) | **YELLOW** | Must be on a different pin set than PH0-PH4; requires SoC pinctrl dtsi verification |
| I2S0 / I2S1 simultaneous | **YELLOW** | I2S0 pin set TBD; I2S1 GREEN. If I2S0 has an alternative pin set, simultaneous operation is possible. |
| DMIC + I2S0 simultaneous | **YELLOW** | I2S0 pin set TBD; if I2S0 can be moved off PH0-PH4, simultaneous operation is possible. |

**Architectural impact**: the audio architecture is YELLOW until the V853/V853S_PINOUT.sls is obtained. The migration path is clear (find an alternative I2S0 pin set); the migration is mechanical (replace the pin set in the device tree and the schematic).

---

## 9. Risk

- If the V853 has NO alternative I2S0 pin set (i.e. I2S0 is only on PH0-PH4), then DMIC and I2S0 cannot coexist on the same SoC. The audio architecture would be **RED** and the design would require a workaround (e.g. an external I2S-to-I2S bridge, or an external PDM-to-PCM bridge). This is highly unlikely (Allwinner V-series SoCs typically have 2-4 mux options per peripheral) but cannot be ruled out without the SoC pinctrl dtsi.
- Mitigation: the AXP2101 PMIC, the BQ25185 charger, and the rest of the power tree do NOT depend on the I2S0 pin set. The audio architecture's only impact is on the I2S0 signal routing on the compute PCB. If the SoC has NO alternative I2S0 pin set, the workaround is to use a small I2S bridge IC (e.g. a TI TLV320ADC3100-class codec) that combines the DMIC and I2S into a single digital stream. This is a major architectural change.
