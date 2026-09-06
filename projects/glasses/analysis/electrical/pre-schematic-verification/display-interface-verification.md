# Display Interface Pre-Schematic Verification

**Component:** 0.23-inch 640×400 monocular micro-OLED / waveguide display engine
**File under verification:** `projects/glasses/references/components/display/lumus_dk50.yaml` and `display_bridge_evaluation.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**What is the electrical interface of the chosen display engine? MIPI DSI, RGB, LVDS, HDMI, or sub-LVDS? Can the V853 DSI 4-lane directly drive it? Is a bridge IC required? Is the Linux DRM/KMS driver chain available?**

This determines whether the display is a direct-DSI connection (no bridge) or requires a bridge IC (Lontium LT8912B or similar).

---

## 2. Status of the display engine selection

**The specific display engine has NOT been selected yet.** The reference library identifies:
- Lumus DK-50 (NDA-gated, 0.23-inch 640×400, LCoS + reflective waveguide) — REFERENCE ONLY
- DigiLens DesignLink v1.0 (NDA-gated, SRG + LCoS) — REFERENCE ONLY
- Toshiba TC358870 (HDMI-to-DSI) — REJECTED (V853 has no HDMI output)
- Lontium LT8912B (RGB/LVDS-to-MIPI DSI, 7×7 mm QFN) — ALTERNATIVE BRIDGE

**The display is mechanically and optically unresolved.** The brief says: "If the exact module is not yet selected, keep the display interface provisional."

---

## 3. The general interface profile for a 0.23-inch 640×400 display

The brief specifies: "0.23-inch-class 640×400 monocular MIPI DSI display". This is the TARGET interface, not the CONFIRMED interface of a specific product.

### What the V853 DSI supports (per datasheet section 1.3.5.1)

- 4-lane MIPI DSI
- Up to 1920 × 1200 @ 60 fps
- Per lane: up to 1.0 Gbps
- Protocols: MIPI DSI V1.02, D-PHY V1.2
- Pixel formats: RGB-888, RGB-666, RGB-565

The 640 × 400 target is well within the V853 DSI's capability (approximately 17 MHz pixel clock for 60 fps refresh; the V853 can provide up to 148 MHz pixel clock).

### What a typical 0.23-inch micro-OLED panel supports

The Sony ECX336-class 0.23-inch micro-OLED panels typically have:
- MIPI DSI input (1, 2, or 4 lanes)
- 1.8 V or 3.3 V logic
- 16.7 million colors (RGB-888)
- Built-in timing controller

If the chosen panel has a MIPI DSI input, the V853 DSI connects DIRECTLY with no bridge.

If the chosen panel has a different input (RGB, LVDS, sub-LVDS), a bridge IC is required:
- RGB-to-DSI: Toshiba TC358778 or Lontium LT8912B
- LVDS-to-DSI: Lontium LT8912B
- sub-LVDS-to-DSI: no widely-available commercial IC (custom design)

---

## 4. Pixel format and lane count

The brief specifies 640 × 400 resolution. The 640 × 400 active area is uncommon; the closest standard resolutions are 640 × 480 (VGA) and 640 × 360 (nHD). The 640 × 400 may be a custom resolution for the chosen panel. The V853 DSI supports custom resolutions via the device tree `display-timings` node.

For 640 × 400 @ 60 fps with 10% blanking:
- Pixel clock ≈ 16.9 MHz
- With RGB-888 (24 bpp): aggregate ≈ 405 Mbps
- With 4-lane DSI at 1 Gbps/lane: 4 Gbps aggregate
- **Bandwidth utilization: approximately 10%** — the V853 DSI is massively over-provisioned for this resolution. The glasses' design has enormous headroom.

---

## 5. Logic voltage

The V853 DSI I/O (VCC18-MDSI) is 1.8 V. The display panel's DSI input must be 1.8 V compatible. Most modern micro-OLED panels support 1.8 V DSI I/O.

If the chosen panel requires 3.3 V DSI I/O, a level shifter is required on each DSI lane (4 lanes + clock = 10 signals). A TXS0108E-class level shifter can handle 8 signals; 2 are needed (or 1 if the clock is shared with another set). This is a YELLOW item with potential architectural impact.

---

## 6. TE (tearing-effect), reset, backlight

- **TE (tearing-effect)**: a GPIO input from the panel to the V853. The V853 DSI controller uses TE to gate the frame update. Required for tear-free display. Standard 1.8 V GPIO.
- **RESET**: a GPIO output from the V853 to the panel. Active-low. Held high during normal operation; pulled low for at least 10 ms to reset the panel. Standard 1.8 V GPIO.
- **BACKLIGHT_ENABLE**: only needed for LCoS-based displays (the LCoS backlight is a separate LED array). The micro-OLED is self-emissive and does NOT need a backlight. If the chosen engine is LCoS-based (Lumus DK-50 / DigiLens DesignLink), a backlight enable GPIO and a PWM brightness control are required.

---

## 7. Initialization sequence and Linux DRM/KMS

The V853 DSI controller is initialized by the Linux kernel / Tina SDK at boot. The panel's timing parameters, DCS commands, and reset sequence are specified in the device tree (panel-timing node) and in a custom DRM/KMS panel driver.

**A custom DRM/KMS panel driver is required for the chosen 0.23-inch 640×400 micro-OLED.** The driver is a small C file (~200-500 lines) that:
- Defines the panel's timing (HFP, HBP, HSync, VFP, VBP, VSync, pixel clock)
- Sends the DCS initialization sequence (via the drm_panel's prepare / enable callbacks)
- Sets the panel's display mode (RGB-888 / 24-bit)
- Configures the TE pin (if used)

The driver structure is in `include/drm/drm_panel.h`. The standard pattern is:
1. Define the panel's `struct drm_panel_funcs` (prepare, enable, disable, get_modes)
2. Register the panel via `drm_panel_init` and add it to the device tree
3. The bridge driver (sun6i-mipi-dsi in the kernel tree) connects the panel to the V853's DSI output

**The driver must be written for the chosen panel.** The driver is a few hundred lines; the estimated effort is 1-2 days of an experienced Linux kernel engineer.

---

## 8. Update to the qualification record

The qualification record `projects/glasses/references/components/display/lumus_dk50.yaml` is **CORRECT as-is** in its REFERENCE_ONLY classification. The verification pass CONFIRMS that the display is mechanically and optically unresolved, and the electrical interface (MIPI DSI vs RGB vs LVDS vs sub-LVDS) is unknown until the display engine is selected.

**No correction to the existing YAMLs is required at this time.** The display remains REFERENCE_ONLY until the NDA acquisition.

---

## 9. Status

| Item | Status | Notes |
| --- | --- | --- |
| 0.23-inch 640×400 DSI-input micro-OLED (the brief's target) | **GREEN (architecture)** | V853 DSI 4-lane can directly drive it |
| Pixel format and lane count | **GREEN** | 4-lane DSI is massively over-provisioned; 640×400 @ 60 fps is 10% bandwidth |
| Logic voltage (1.8 V vs 3.3 V) | **YELLOW** | Verify with the chosen panel; 1.8 V is preferred (no level shifter) |
| TE / reset / backlight | **GREEN (architecture)** | Standard 1.8 V GPIO control |
| Linux DRM/KMS panel driver | **YELLOW** | Custom driver must be written (200-500 lines) |
| Bridge IC requirement | **YELLOW** | None if DSI; Lontium LT8912B if RGB/LVDS; no commercial IC if sub-LVDS |
| Display engine selection | **RED (NDA)** | Lumus / DigiLens NDA required |

**Architectural impact**: the display interface is GREEN at the architecture level (V853 DSI 4-lane directly drives a DSI-input 0.23-inch 640×400 micro-OLED). The remaining items are YELLOW (driver write, logic voltage verification) and RED (display engine NDA). The glasses' design can proceed with the DSI-direct architecture, with the bridge as a fallback if the chosen engine is RGB/LVDS.
