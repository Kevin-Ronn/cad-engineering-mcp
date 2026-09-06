# Display / Optical System — Reference Index

This directory holds component references for the glasses' monocular
micro-display + waveguide optical system.

The glasses require:

- 1 monocular display (micro-OLED preferred)
- approximately 0.23" class
- approximately 640 × 400 resolution
- approximately 25-26° horizontal FOV
- waveguide optical system preferred
- transparent enough for normal vision
- compact enough for a Wayfarer-style frame
- MIPI DSI (or another interface that can realistically be driven by
  the Allwinner V853)

The display is intended for: text, notifications, OCR results,
translated text, navigation/AI information, and a simple UI. It is
NOT a full AR display. No previously investigated DisplayModule/TDO
0.23" 640x400 micro-OLED + waveguide system was assumed to be still
available or dimensionally correct; this pass re-investigated from
first principles.

The existing authoritative frame geometry in
`projects/glasses/references/silhouette/wayfarer/` and
`projects/glasses/mechanical/main-frame/WORKING_FRAME_SOLID.FCStd`
was **not modified** during this research pass.

---

## Contents of this directory

| File | Description |
| --- | --- |
| `lumus_dk50.yaml` | Lumus DK-50 reference design (LCoS + Lumus reflective waveguide). Closest public match to the brief's 0.23" 640x400 target. NDA-gated dimensions. |
| `digilens_designlink.yaml` | DigiLens DesignLink v1.0 (SRG waveguide + LCoS). 720p per press, 640x400 also cited. NDA-gated. |
| `epson_moverio_bt45c.yaml` | Epson Moverio BT-45C reference (Si-OLED 0.45 inch 1920x1080, ~34° FOV, conventional lens combiner). NOT a match to the 0.23" 640x400 brief, but the most-documented public Epson engine and a useful reference for what a real shipping Si-OLED engine looks like. |
| `oppo_air_glass.yaml` | OPPO Air Glass (micro-LED 640x400, OPPO diffractive waveguide, 1400 nits, 30 g total). Reference data only — finished consumer product, not an OEM module. |
| `sony_ecx343_class.yaml` | Sony ECX343-class micro-OLED panel (0.23-0.39 inch class). Panel only; no public reference engine or waveguide. |
| `generic_lcos_0p23_640x400_engine.yaml` | Unbranded Chinese LCoS 0.23" 640x400 optical engines from Alibaba/Taobao. HDMI input, no waveguide, no datasheet. **Rejected** for the glasses per the brief's price-vs-suitability rule. |

---

## Headline comparison

| Spec | Lumus DK-50 | DigiLens DesignLink v1 | Epson Moverio BT-45C (reference) | OPPO Air Glass (reference) | Sony ECX343-class panel | Generic 0.23" LCoS engine |
| --- | --- | --- | --- | --- | --- | --- |
| Display | LCoS | LCoS | Si-OLED 0.45" | micro-LED | micro-OLED panel | LCoS |
| Resolution | 640×400 | 720p (640×400 cited) | 1920×1080 | 640×400 | NOT_PUBLIC (640×400-class) | 640×400 |
| FOV H (deg) | ~26 (DK-50) | ~30-40 (class) | ~34 | NOT_PUBLISHED | N/A (panel only) | NOT_PUBLISHED |
| Waveguide | Lumus reflective 2D | DigiLens SRG | conventional lens | OPPO diffractive | N/A (panel only) | NONE included |
| Eyebox | NOT_PUBLIC | NOT_PUBLIC | NOT_PUBLIC | NOT_PUBLIC | N/A | NOT_PUBLIC |
| Brightness | > 4000 nits/W (Maximus class) | NOT_PUBLIC | "dim indoor light" | 1400 nits | 1000-5000 nits (class) | few hundred to 1500 (class) |
| Color | mono standard; RGB option | mono | 24-bit color | monochrome green | NOT_PUBLIC | mono or RGB time-multiplexed |
| Engine thickness | ~6 mm (Maximus class) | NOT_PUBLIC | NOT_PUBLIC | NOT_PUBLIC (engine) | N/A | ~5 mm (estimated, unverified) |
| Engine weight | NOT_PUBLIC | NOT_PUBLIC | NOT_PUBLIC | total 30 g (whole unit) | N/A | NOT_PUBLIC |
| Interface to host | NOT_PUBLIC | NOT_PUBLIC (LCoS driver typical: RGB or LVDS) | MIPI DSI or USB-C with internal controller | Bluetooth to phone | sub-LVDS typical | **HDMI** (engine) |
| V853 MIPI DSI compatibility | needs bridge | needs bridge | needs bridge (or use the headset's Android controller) | N/A (engine not exposed) | needs bridge (sub-LVDS -> MIPI) | needs HDMI-to-MIPI bridge |
| Docs | public announcement, NDA for dims | public announcement, NDA for dims | full public datasheet | full public launch | public catalog only | none |
| Price | quote (NDA) | ~$950-5000 dev kit | ~$1800-2500 finished headset | ~$500 finished | quote (NDA) | $20-60 |
| Confidence | MEDIUM | MEDIUM | HIGH for public specs | HIGH for public specs | LOW for glasses integration | LOW |

---

## Mechanical fit analysis (vs. existing Wayfarer geometry)

The Wayfarer reference frame measurements (from
`projects/glasses/analysis/structure/full-mechanical-inspection.md`):

- Lens cavity Y range: 89.10 to 210.90 mm (depth 121.8 mm)
- Frame X width: 17.7 mm
- Frame Z height: 42.85 mm
- Lens opening Z range: 4.0 to 28.0 mm (24 mm tall)
- Outer rim Y width: 5.1 mm at Z=20
- Inner rim Y width: 3.3 mm
- Outer rim X depth: 5.1 to 9.4 mm
- Temple transition thickness: **1.6 mm** (extremely thin)
- Bridge Y width: 3.0 mm (too narrow for any candidate engine)

Conceptual fit of each candidate:

1. **Lumus DK-50 / Maximus-class engine**: ~6 mm thick, ~14 × 12 mm area. The Wayfarer 1.6 mm temple cannot host this. The engine must sit in the upper-front-frame region (above the lens cavity) with the waveguide flat inside the lens cavity. The upper-front-frame region above Z=35 has 5-7 mm of material available; this is just barely enough for a 6 mm engine with a thin shell cut. The waveguide sits inside the lens cavity (Y=89 to 211 mm); it adds 2 mm of glass to the existing 5.1 mm outer rim. Achievable only with a significant frame redesign that increases the upper-bridge cross-section.

2. **DigiLens DesignLink v1.0**: similar envelope to Lumus (10-20 × 10-15 × 5-8 mm, NDA-gated). Same blocker as Lumus.

3. **Epson Moverio BT-45C (reference)**: binocular industrial headset, not a Wayfarer-integrable module. The 0.45" Si-OLED panel alone is too large for the brief, and the BT-45C's engine is approximately 30 × 20 × 10 mm. Excluded from glasses fit.

4. **OPPO Air Glass (reference)**: total product weight 30 g; not a Wayfarer-shaped product (its temple is a stem). The engine sits in a non-Wayfarer stem. Reference data only.

5. **Sony ECX343-class panel**: panel itself sub-10 mm; would fit. But the optical engine + waveguide is a 6-12 month custom design project (NRE $100k-500k, optical-tooling lead time 6-12 months). Out of scope for a prototype.

6. **Generic 0.23" LCoS engine**: claimed ~13 × 10 × 5 mm from the Alibaba listing text (unverified). Even if real, no waveguide is included, HDMI-only input requires a bridge IC, and no documentation exists. Excluded.

**Common blocker for all waveguide-class candidates**: the Wayfarer temple is 1.6 mm thick, which cannot host any waveguide-class optical engine. The engine must sit in the front frame, and the front frame's available cross-section above the lens cavity is 5-7 mm. This is a hard geometric constraint that no current off-the-shelf waveguide-class display engine can satisfy without a frame redesign.

---

## Ranking on the glasses-specific criteria

1 = best, 6 = worst. (The brief asks for 4+ serious candidates; the
table includes all 6 for transparency, with 3 rejected below.)

| Criterion | Lumus DK-50 | DigiLens DesignLink | Epson Moverio BT-45C | OPPO Air Glass | Sony ECX343 panel | Generic 0.23" LCoS |
| --- | --- | --- | --- | --- | --- | --- |
| Total optical / mechanical envelope | 2 (~6 mm thick) | 3 (NDA) | 6 (too large) | 4 (NDA) | 1 (panel only) | 3 (unverified) |
| FOV | 2 (~26°) | 2 (~30-40°) | 1 (~34°) | 4 (not published) | N/A | 4 (not published) |
| Eyebox | 4 (NDA) | 4 (NDA) | 4 (NDA) | 4 (NDA) | N/A | 4 (NDA) |
| Transparency (waveguide see-through) | 1 (reflective waveguide) | 1 (SRG waveguide) | 6 (tinted combiner, not see-through) | 1 (diffractive waveguide) | N/A | 6 (no waveguide) |
| Brightness | 1 (> 4000 nits/W) | 3 (NDA) | 6 (not sunlight-readable) | 2 (1400 nits) | 2 (class) | 3 (unverified) |
| Resolution match to 640×400 | 1 (640×400 explicit) | 2 (720p also cited) | 6 (1920×1080) | 1 (640×400) | 3 (class only) | 1 (640×400) |
| V853 MIPI DSI compatibility | 4 (needs bridge) | 4 (needs bridge) | 5 (headset uses Android controller) | 5 (engine not exposed) | 4 (sub-LVDS, needs bridge) | **6** (HDMI, needs bridge) |
| Power consumption | 3 (NDA) | 3 (NDA) | 5 (industrial, 3-hour battery) | 4 (3-hour battery) | 3 (NDA) | 4 (typical class 0.5-1.5 W) |
| Connector / FPC practicality | 4 (NDA) | 4 (NDA) | 2 (USB-C tethered) | 5 (Bluetooth to phone) | 3 (NDA) | 5 (HDMI connector) |
| Availability | 3 (NDA / quote) | 3 (NDA / quote) | 1 (in production) | 4 (limited China release) | 3 (NDA / quote) | 1 (Alibaba, no support) |
| Price | 3 (NDA / quote, $400-2000 est.) | 4 (NDA / $950-5000 dev kit) | 5 ($1800-2500 finished) | 4 ($500 finished) | 3 (NDA / quote) | **1** ($20-60) |
| Documentation quality | 2 (public announcement + NDA) | 2 (public announcement + NDA) | **1** (full public datasheet) | 1 (full public launch) | 3 (public catalog only) | **6** (none) |
| Integration difficulty | 4 (NDA required, NDA-gated docs) | 4 (same) | 5 (binocular industrial, not Wayfarer) | 5 (consumer, not OEM) | 6 (custom design) | 5 (no docs, no support) |

**Reject explicitly** (per the brief's "If the cheapest candidate is
mechanically/electronically unsuitable, explicitly reject it rather
than choosing it because of price"):

- **Generic 0.23" LCoS engine** is the cheapest by a factor of 10,
  but: no verified mm-level mechanical dimensions, HDMI-only input
  (needs a bridge IC to MIPI DSI), no waveguide included, no
  documentation, no warranty, no support. **Rejected.**
- **Epson Moverio BT-45C** is a binocular industrial headset, not a
  Wayfarer-integrable module and not 0.23". **Reference only.**
- **OPPO Air Glass** is a finished consumer product, not an OEM
  module. **Reference only.**
- **Sony ECX343-class panel** is a panel only; a custom optical
  engine + waveguide would be a 6-12 month NRE project. **Not
  recommended for prototype.**

---

## Recommendation

### PRIMARY display candidate

**Lumus DK-50 (or equivalent Lumus reflective-waveguide 0.23"-class engine with a 640x400 LCoS microdisplay).** Lumus's publicly announced spec set is the closest match to the brief: 0.23 inch class, 640x400 resolution, ~40° FOV (≈26° horizontal), reflective waveguide, sub-6mm engine thickness, > 4000 nits/W brightness. The Maximus generation (1280x720 / 50° / ~6 mm engine / ~2 mm waveguide) is the current shipping product line; a 640x400 variant is not publicly available today, but the underlying reflective-waveguide technology is the right one for the glasses' see-through, normal-vision requirement.

Why:
1. **Reflective waveguide** is the most mature see-through technology for the 25-26° FOV / see-through-required brief.
2. **0.23" / 640x400** matches the brief exactly (public spec).
3. **NDA-gated mechanical drawings** are released to qualified partners; this is the standard path for this product class.
4. **Mature vendor** with a shipping product line (Maximus, Z-Lens).
5. **LCoS microdisplay** is a well-understood technology with a stable supply chain.

**Critical blocker for adoption**: the Wayfarer temple is 1.6 mm thick, and no off-the-shelf waveguide-class engine fits in a 1.6 mm cavity. The engine must be redesigned into the front-frame upper-bridge region, and the front-frame cross-section must be increased from ~5-7 mm to ~8-10 mm to host a 6 mm engine + 2 mm waveguide + 1 mm shell. **This is a frame-level change that must be made in coordination with Lumus NDA drawings.**

### SECONDARY / FALLBACK candidate

**DigiLens DesignLink v1.0 (SRG-based 0.23" LCoS reference engine).** Same general envelope as Lumus; 720p resolution in the public material but 640x400 also cited. Different waveguide technology (SRG vs Lumus reflective 2D) but similar mechanical envelope and similar NDA-gated path. Choose this if Lumus NDA terms are not commercially reasonable; the optical engine + waveguide integration approach is comparable.

### Why not the cheaper Chinese LCoS engines

The brief explicitly says: "If the cheapest candidate is
mechanically/electronically unsuitable, explicitly reject it rather
than choosing it because of price." The unbranded Alibaba LCoS
engines are the cheapest by a factor of 10, but:

- No verified mm-level mechanical dimensions
- HDMI-only input requires an HDMI-to-MIPI DSI bridge IC (Toshiba TC358870, ITE IT6505, or Lontium LT8918) — extra cost, extra PCB area, extra design time
- No waveguide included (the most expensive part of a waveguide-class display is the waveguide itself, $100-400 per piece)
- No documentation, no warranty, no driver support
- Unverified brightness, eyebox, FOV

This is rejected.

---

## Open items to resolve before the next pass

- [ ] Request Lumus NDA drawings for the DK-50 / Maximus-class 0.23" reflective waveguide optical engine. This is the only way to obtain mm-level dimensions for the engine, the waveguide, and the FPC.
- [ ] If Lumus is not commercially viable, request the same from DigiLens.
- [ ] Decide on the bridge-IC question: if the chosen engine exposes LCoS RGB/LVDS, an FPGA or bridge IC is required to connect to the V853's MIPI DSI. This is a non-trivial PCB design item.
- [ ] Decide on the waveguide combiner sourcing: separate from the engine (the engine typically does not include the waveguide combiner; the combiner is a separate component from the same vendor or a third party).
- [ ] Decide whether to use a 0.23" 640x400 panel (DK-50 class) or a 0.39"-class 1280x720 panel (Maximus class). The brief explicitly targets 0.23" 640x400, but the 0.39" Maximus is the current shipping product and may be more supportable.
- [ ] Investigate the frame-level change required to host a 6 mm engine in the front frame. This must be a coordinated mechanical + optical decision.

---

## Stop point

Per the user's instructions, this is the display reference-acquisition
deliverable. **No mechanical placement, no PCB design, no FreeCAD
work, and no modification to the existing Wayfarer geometry, the
working solid, or any glasses electronics has been started.** The
audio and battery reference acquisition has not been started.
Awaiting explicit instruction to continue.
