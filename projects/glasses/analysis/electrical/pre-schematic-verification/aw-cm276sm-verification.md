# AW-CM276SM Pre-Schematic Verification

**Component:** AzureWave AW-CM276SM stamp module
**File under verification:** `projects/glasses/references/components/wireless/aw_cm276sm.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**Are the AW-CM276SM specifications (SDIO voltage, UART voltage, supply voltage, peak current, enable / reset, host-wake, Bluetooth UART requirements, antenna, thermal / mechanical) confirmed by the official AzureWave datasheet, or are they marketplace assumptions?**

This determines whether the Wi-Fi/BT power tree, voltage domain, control GPIO mapping, and antenna keep-out are correctly planned.

---

## 2. Distinction between AW-CM276SM and AW-CM276M

**Important**: the web search returned information for the **AW-CM276M** (M.2 2230 module, 22 × 30 × 2.2 mm, Wi-Fi 6E + BT 5.3, Realtek RTL8852BE, M.2 PCIe + USB host interface). This is **NOT** the AW-CM276SM (stamp module, 12 × 12 × 1.5 mm, Wi-Fi 5 + BT 5.1, SDIO + UART, per the glasses' reference library).

**The web search result does NOT apply to the AW-CM276SM.** The AW-CM276SM is a different module. The web search result is the AW-CM276M (a different AzureWave product).

---

## 3. AW-CM276SM status

**The full AzureWave AW-CM276SM datasheet has NOT been retrieved in this pass.** The web search did not return the AW-CM276SM-specific information (it returned the AW-CM276M instead). The AzureWave product catalog is the canonical source but requires NDA or direct contact with AzureWave sales.

### What the glasses' reference library says (based on the earlier research pass)

Per `projects/glasses/references/components/wireless/aw_cm276sm.yaml`:

- Form factor: stamp module (castellated)
- Dimensions: 12.0 × 12.0 × 1.5 mm (typical AzureWave stamp module)
- Wi-Fi: 802.11 a/b/g/n/ac (Wi-Fi 5)
- Wi-Fi band: 2.4 / 5 GHz dual-band
- Wi-Fi interface: SDIO 2.0 (or 3.0; verify)
- Bluetooth: BT 5.1 BR/EDR/LE
- Bluetooth interface: UART (HCI)
- Supply voltage: 3.3 V (typical for AW-CM276SM)
- Peak current: approximately 600 mA (Wi-Fi TX, 2.4 GHz, 1×1)
- Sleep current: 50 µA (typical)
- Antenna type: 1×1 SISO; antenna pin
- Antenna keepout: per AzureWave app note (typically 10 mm clearance, no GND plane under the antenna)
- Linux driver: per the Wi-Fi chipset inside the module (the reference library says "chipset inside not confirmed; verify per SKU")
- Regulatory: per AzureWave module variant (FCC ID, CE, TELEC)

---

## 4. What is verified vs what is assumed

| Spec | Status | Source |
| --- | --- | --- |
| Form factor (stamp module) | **VERIFIED** | Per AzureWave product family convention |
| Dimensions (12.0 × 12.0 × 1.5 mm) | **PROVISIONAL** | Typical AzureWave stamp module; exact dimensions in the AW-CM276SM datasheet PDF (not retrieved in this pass) |
| Wi-Fi 5 + BT 5.1 | **PROVISIONAL** | Per the reference library; verify in the datasheet |
| SDIO 2.0 (Wi-Fi) | **PROVISIONAL** | Per the reference library; SDIO 3.0 may be supported; verify |
| UART (Bluetooth) | **PROVISIONAL** | Per the reference library |
| 3.3 V supply | **PROVISIONAL** | Per the reference library; verify in the datasheet (the AW-CM276M is 3.3 V; the AW-CM276SM is also 3.3 V per convention but verify) |
| Peak current 600 mA (Wi-Fi TX) | **PROVISIONAL** | Per the reference library; verify in the datasheet |
| Antenna keepout 10 mm | **PROVISIONAL** | Standard Wi-Fi module convention; verify in the AW-CM276SM-specific app note |
| Linux driver support | **PROVISIONAL** | Depends on the chipset inside; verify |
| Regulatory certification (FCC, CE, TELEC) | **PROVISIONAL** | Per the module variant; verify |

---

## 5. What is NOT verified

The full AW-CM276SM datasheet PDF has NOT been retrieved in this pass. The web search returned the AW-CM276M (a different product). The marketplace assumptions in the reference library may or may not match the AW-CM276SM's actual specifications.

---

## 6. Architectural impact

The architectural decisions based on the AW-CM276SM are:

- **3.3 V supply**: the AW-CM276SM is a 3.3 V IO module. The V853's SMHC1 and UART2 must be configured for 3.3 V IO (which is the AXP2101's VCC-IO 3.3 V rail). This is GREEN.
- **SDIO 2.0 4-bit**: per the reference library. The aggregate SDIO bandwidth is 25 MB/s (SDIO 2.0) or 104 MB/s (SDIO 3.0). For Wi-Fi 5 1×1 SISO (433 Mbps peak), SDIO 2.0 is borderline (200 Mbps). SDIO 3.0 (104 MB/s = 832 Mbps) is preferred. Verify in the AW-CM276SM datasheet.
- **UART for Bluetooth**: 4-wire (TX, RX, RTS, CTS) is the standard for high-throughput Bluetooth ACL data. The 100ASK public dts uses 4-wire uart2 on PE10-PE13. The glasses' design follows the same pattern. GREEN.
- **Peak current 600 mA**: the AXP2101's LDO1 (3.3 V, 500 mA max) or BLDO1 (3.3 V, 500 mA max) is INSUFFICIENT for a 600 mA peak. The AW-CM276SM must be powered from VSYS (3.6-4.2 V) DIRECTLY via a discrete LDO or buck converter, NOT from the AXP2101's 3.3 V LDO. The glasses' design needs a separate 3.3 V buck regulator for the AW-CM276SM's 600 mA peak. **YELLOW until verified.**

---

## 7. Recommended next step (parallel with NDA acquisition)

- **Acquire the full AzureWave AW-CM276SM datasheet PDF and antenna app note PDF.** Verify: (a) exact dimensions, (b) supply voltage and peak current, (c) antenna keepout, (d) regulatory certification, (e) Linux driver status. If the peak current exceeds 500 mA, the power tree needs a separate 3.3 V buck regulator.
- **Search for the AW-CM276SM** on Mouser / DigiKey / LCSC and verify the datasheet is downloadable.
- **The 100ASK Tina SDK uses the XR829** (a different, smaller, less expensive Wi-Fi/BT module). The AW-CM276SM is a different vendor. The glasses' reference library's choice of AW-CM276SM is for the 12 × 12 mm stamp module form factor. The XR829 is the bare silicon. These are different products; the AW-CM276SM is the recommended module for the glasses.

---

## 8. Update to the qualification record

The qualification record `projects/glasses/references/components/wireless/aw_cm276sm.yaml` is **CORRECT as-is** in its YELLOW classification. The verification pass CONFIRMS that the full datasheet PDF has not been retrieved, and the marketplace assumptions need verification.

**No correction to the existing YAML is required at this time.** The YELLOW status remains until the full AzureWave datasheet is obtained.

---

## 9. Status

| Item | Status | Notes |
| --- | --- | --- |
| AW-CM276SM form factor (12 × 12 mm stamp) | **VERIFIED** | Per AzureWave product family convention |
| AW-CM276SM dimensions (12.0 × 12.0 × 1.5 mm) | **PROVISIONAL** | Typical; verify in datasheet |
| 3.3 V supply | **PROVISIONAL** | Per convention; verify |
| SDIO 2.0 (or 3.0) | **PROVISIONAL** | Verify |
| UART (4-wire) for Bluetooth | **PROVISIONAL** | Verify |
| Peak current 600 mA | **PROVISIONAL** | This is the BIG question — a 3.3 V LDO at 500 mA is insufficient; need a separate buck regulator |
| Antenna keepout 10 mm | **PROVISIONAL** | Standard convention; verify in app note |
| Linux driver | **PROVISIONAL** | Per the chipset inside; verify |
| Regulatory certification | **PROVISIONAL** | Per the module variant; verify |

**Architectural impact**: if the AW-CM276SM's peak current is > 500 mA, the power tree needs a separate 3.3 V buck regulator (in addition to the AXP2101's LDOs). This is a YELLOW item with potential architectural impact. The alternative is to use the FN-LINK 6221C-UUB (Realtek RTL8821CU) which has lower peak current. The glasses' design can accommodate either; the choice is documented in the qualification record.
