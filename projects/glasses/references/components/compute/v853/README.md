# V853 Compute Platform — Reference Index

This directory holds component references for the **Allwinner V853**
SoC and the small V853-based SoM / SBC / module candidates that were
investigated for the glasses compute platform.

The V853 was selected because the heavy AI processing for the glasses
runs on the user's phone, so the on-board compute is constrained to:

- Camera capture (two forward cameras)
- Audio capture and playback
- Monocular micro-OLED / waveguide display output
- Wi-Fi / Bluetooth connectivity to the phone
- Local preprocessing and device control
- Light on-device NPU use (prefilter, AE/AWB pre-stat, voice keyword)

The V853 with Cortex-A7 + 1 TOPS NPU + 4-lane MIPI DSI + 2x 2-lane or
1x 4-lane MIPI CSI matches this profile.

---

## Contents of this directory

| File | Description |
| --- | --- |
| `allwinner_v853_soc.yaml` | Bare V853 SoC reference: package (LFBGA-318, 12x12 mm, 0.50 mm pitch), CPU/NPU, MIPI, audio, USB, electrical limits, operating temperature. Source: Allwinner's own V853 datasheet Rev 1.1 (2022-03-23). |
| `v853-datasheet.pdf` | Allwinner V853 & V853S Datasheet, Rev 1.1, 2022-03-23 (mirror of the file in YuzukiHD/ProjectYosemite/Datasheets). |
| `v853-brief.pdf` | Allwinner V853 brief, v1.4 (image-heavy; limited text). |
| `100ask_v853_pro_som.yaml` | 100ASK-V853-Pro "V853 Core Lite" SoM candidate. Strong functional fit (XR829 Wi-Fi/BT, 2x USB 2.0, AXP2101 PMU, 1x 2-lane + 1x 4-lane MIPI CSI). **Mechanical drawing NOT public.** |
| `yuzukihd_project_yosemite.yaml` | ProjectYosemite open-source V853 SBC (RPi-A form factor). Has KiCad + Gerbers + 3D, but exact dimensions and power input not stated in the README and must be measured from the KiCad project file. **Only one 4-lane MIPI CSI exposed** (no 2x 2-lane), which is a disadvantage for the two-camera target. |
| `mangopi_mq_v.yaml` | MangoPi MQ-V V853 SoM. **Documented as an announcement only** (MangoPi Twitter, May 2022). No public product page or mechanical drawing was found during this inspection. |
| `tinyvision_v851s_related.yaml` | Reference / disambiguation. TinyVision is V851se/s3 (0.5 TOPS NPU, 1x 2-lane MIPI CSI, no MIPI DSI). NOT a V853. Included to make this explicit. |
| `projectyosemite-mechanical-reference.yaml` | Exact mechanical dimensions of the ProjectYosemite board, extracted from its EasyEDA Pro Gerbers, drill file, NDJSON, and STEP model: 65.0 × 56.0 mm, 4-layer 1.55 mm PCB, 4× M3 mounting holes, 2×20 GPIO header, MIPI CSI FPC, XR829, IPEX antenna, eMMC, DDR3, SoC, max component height 13.4 mm (FPC edge) / 5.0 mm (central). Plus a reproducibility assessment for V853 + DDR3 + eMMC + PMIC + Wi-Fi/BT on a custom PCB. |

---

## Comparison of candidates

All numbers are from the public sources cited in the per-candidate YAMLs.
`UNKNOWN` means the value was not in the public documentation and was
not guessed.

| Spec | Allwinner V853 (bare die) | 100ASK-V853-Pro Core Lite SoM | ProjectYosemite SBC | MangoPi MQ-V SoM |
| --- | --- | --- | --- | --- |
| Manufacturer | Allwinner | 100ask | YuzukiHD (open source) | MangoPi (Widora) |
| Part number | V853 (V853S = 0.8 TOPS) | 100ASK-V853-Pro core board | ProjectYosemite | MQ-V |
| Form factor | LFBGA-318, 12x12x~1.4 mm | SoM, exact mm not public | "RPi A size", exact mm not public | SoM, exact mm not public |
| RAM | 16-bit DDR3/DDR3L (module-dep.) | 512 MB or 1 GB DDR3 | up to 1 GiB DDR3 | UNKNOWN |
| eMMC | via SMHC (module-dep.) | 8 GB or 32 GB eMMC 5.1 | up to 128 GiB | UNKNOWN |
| Wi-Fi | none (add externally) | XR829 (Wi-Fi 4, 2.4 GHz) | XR829 (Wi-Fi 4, 2.4 GHz) | UNKNOWN |
| Bluetooth | none (add externally) | XR829 BT 4.2 | XR829 BT 4.2 | UNKNOWN |
| MIPI CSI (config) | 1x 4-lane OR 2x 2-lane | 1x 2-lane + 1x 4-lane | 1x 4-lane | UNKNOWN |
| MIPI DSI | 1x 4-lane, 1920x1200@60 | 1x 4-lane | 1x 4-lane, 1920x1200@60 | UNKNOWN |
| Audio | on-die codec: 1x DAC, 2x ADC, 2x I2S/PCM, DMIC up to 8 mics, 2x analog mic, 1x line out | on-die codec + 1x S/PDIF + 2x speaker header | on-die codec + built-in mic | UNKNOWN |
| USB | 1x USB 2.0 DRD (OTG) | carrier has 2x Type-A + 2x Type-C | SoM-level USB count not stated | UNKNOWN |
| PMIC | external (carrier) | AXP2101 | AXP2101 | UNKNOWN (likely AXP2101) |
| Operating temperature | ambient -20 to +70 C (consumer die) | consumer-grade die inferred; SoM op-temp not published | consumer-grade die inferred | UNKNOWN |
| Price | UNKNOWN (die only) | 99 RMB (~$14) for SoM 512 MB + 8 GB eMMC; 129 RMB (~$18) for 512 MB + 32 GB | open hardware, fab + BOM cost | UNKNOWN |
| Availability | buy from Allwinner/100ask | China (Taobao) | fab-yourself from KiCad + Gerbers | UNKNOWN |
| Public mechanical drawing | YES (LFBGA-318, 12x12 mm, 0.50 mm pitch) | **NO** | YES in KiCad (must be opened) | **NO** |
| Open-source hardware | NO (Allwinner NDA datasheet mirrored here under fair-use engineering) | NO | YES (CERN-OHL-S 2.0) | NO |
| Glasses suitability | base target; not wearable by itself | high IF a mechanical drawing is obtainable | high IF a KiCad-measured outline is acceptable and a CSI mux is added | blocked until drawing is found |

---

## Recommended candidate

**Recommendation: ProjectYosemite (YuzukiHD), with 100ASK-V853-Pro as a
fallback if a private mechanical drawing can be obtained from 100ask.**

Why ProjectYosemite first:

1. **Open hardware (CERN-OHL-S 2.0).** Mechanical, schematic, BOM,
   Gerbers, 3D model and datasheets are all in one repository. There
   is no vendor gatekeeping the engineering data, which is the exact
   problem the previous QCS6490 reference directory exposed.
2. **Confirmed V853 + 1 TOPS NPU + 4-lane MIPI DSI + Wi-Fi/BT on
   board.** The SoC feature set matches the glasses target
   (capture, audio, display, connectivity, light NPU).
3. **The board outline is recoverable.** The KiCad project file in
   `Hardware/Project/ProProject_...zip` contains the exact Edge.Cuts
   outline in mm. Once extracted, this becomes a geometrically
   authoritative source.
4. **A single 4-lane MIPI CSI is the only real cost.** For two
   independent 2-lane cameras, a CSI-2 mux (e.g. Toshiba TC358743 or
   a TI SN65DSI83-type part) is required. This is small, cheap, and
   well-understood; latency is added but is acceptable for the
   license-plate-OCR latency budget when the heavy work is on the
   phone.
5. **Linux support is mature.** Buildroot, Tina Linux and mainline
   efforts exist for the V853 family.

Why 100ASK-V853-Pro as a fallback:

1. **Two MIPI CSI physical connectors** (1x 2-lane + 1x 4-lane) means
   no CSI mux is needed for the two-camera target. The cameras
   connect directly to two independent SoC sub-channels.
2. **Better factory carrier board** (USB-C OTG, USB-C console, 8
   buttons, Ethernet, 22-pin expansion, AXP2101 PMU).
3. **Cheaper and faster to first prototype** (commercial pre-built
   board; 99-129 RMB for the SoM alone, 449-499 RMB for the full
   kit).
4. **BLOCKER: no public mechanical drawing for the SoM.** Without a
   2D footprint / STEP model, the SoM cannot be dropped into a
   glasses-cavity design. Request the drawing from 100ask before
   adopting. If the request is refused or delayed, fall back to
   ProjectYosemite.

Why not the bare V853 die (file `allwinner_v853_soc.yaml`):

The bare die is the engineering reference for the SoC. It is not a
wearable product. The SoC must be placed on a carrier PCB with PMU,
DDR3, eMMC, and a board-to-board connector to a temple-mounted
flex. The SoM/SBC candidates above are that carrier; the die file is
the datasheet-level source the SoM/SBC files reference back to.

## ProjectYosemite mechanical facts (read from the open-source design)

`projectyosemite-mechanical-reference.yaml` is the ground-truth
mechanical document for ProjectYosemite. The headline numbers:

- **Board: 65.0 × 56.0 mm**, **4-layer 1.55 mm PCB**, ENIG, 1 oz Cu
- **4× M3 mounting holes** at the corners (3.0 mm drill, GND-tied pads)
- **2×20 GPIO header** at the top edge (RPi A pinout, 2.54 mm pitch)
- **1× 30-pin FPC (MIPI_RPI)** at the top edge, 0.5 mm pitch, flip-lock
- **1× IPEX MHF** antenna connector on the right edge
- **1× TF (microSD) socket** on the left edge
- **Allwinner V853 SoC** (LFBGA-318, 12×12×~1.4 mm footprint title is
  carried over as TFBGA-361 in the EasyEDA library — a footprint
  artifact, the silkscreen and the README both say V853)
- **DDR3 SDRAM** (FBGA-96 13.3×7.5, 0.8 mm pitch)
- **eMMC** (FBGA-153 15.0×13.0, 0.5 mm pitch)
- **Xradio XR829** Wi-Fi 4 + BT 4.2 (QFN-40 5×5)
- **AXP2101 PMIC** (per README and the AXP2101 datasheet in Datasheets/)
- **Onboard MEMS microphone**
- **32.768 kHz RTC crystal** (-40 to +85 C, 7 pF, ±20 ppm)
- **Max component height**: 13.4 mm at the FPC edge, 5.0 mm in the
  central area (PMIC and small ICs).

What is **not** in the extracted data: the MIPI DSI FPC connector, the
USB connector, the power input connector, audio line-out, and the
per-designator LCSC BOM (the public BOM folder is empty). The glasses
custom PCB will need its own choices for these.

**The glasses PCB must be a custom compact rigid-flex design, not a
copy of this 65×56 mm RPi-A-format board.** The value of
ProjectYosemite is as a verified reference for the V853 electrical
implementation (PMIC, DDR routing topology, eMMC, XR829, antenna
keepout) — not as the glasses PCB itself.

Why not MangoPi MQ-V:

The V853 SoM was announced in May 2022 but no public product page or
mechanical drawing has been located. Status is **blocked** until
MangoPi republishes the documentation or the user can obtain a
drawing directly.

Why not TinyVision:

TinyVision is the V851se / V851s3 (0.5 TOPS NPU, 1x 2-lane MIPI CSI
only, no MIPI DSI). Wrong SoC. Included in this directory only to
prevent confusion with the V853.

---

## Unresolved information (per candidate)

### Allwinner V853 (bare SoC)
- Power consumption parameters — datasheet refers to Allwinner FAE
  (Section 2.3.1). Cannot be guessed.
- Power-on / power-off sequence — present as Figure 2-2 in the
  datasheet but not transcribed here; AXP2101 PMIC design guide
  covers the SoC side.
- Detailed MIPI CSI / DSI electrical timing — present as Tables
  2-17 through 2-37 in the datasheet but not transcribed here.

### 100ASK-V853-Pro Core Lite SoM
- SoM board dimensions, PCB thickness, max component height, mounting
  holes, connector pinout and pitch — **not public**.
- SoM operating temperature range — not public; consumer die assumed.
- SoM weight — not public.

### ProjectYosemite
- Exact PCB dimensions, mounting holes, max component height — must
  be extracted from the KiCad project file in
  `Hardware/Project/ProProject_...zip`.
- Power input voltage range — not stated in README; AXP2101
  datasheet implies single-cell Li-ion + 5 V, but confirm from the
  schematic.
- Operating temperature — not stated; consumer die assumed.

### MangoPi MQ-V
- Everything mechanical and price/availability is currently
  unresolved.

---

## Datasheet and source links

- Allwinner V853 & V853S Datasheet Rev 1.1 (2022-03-23):
  mirrored at `v853-datasheet.pdf` and
  <https://raw.githubusercontent.com/YuzukiHD/ProjectYosemite/main/Datasheets/v853-amp-v853s_datasheet_v1.1%201.pdf>
- Allwinner V853 brief v1.4:
  mirrored at `v853-brief.pdf` and
  <https://raw.githubusercontent.com/YuzukiHD/ProjectYosemite/main/Datasheets/v853-brief_en_v1.4.pdf>
- ProjectYosemite repository:
  <https://github.com/YuzukiHD/ProjectYosemite>
- 100ASK-V853-Pro article (CNX-Software, 2023-04-20):
  <https://www.cnx-software.com/2023/04/20/100ask-v853-pro-allwinner-v853-board-ai-vision/>
- 100ask V853 forum:
  <https://forums.100ask.net/c/aw/v853/71>
- Allwinner V853 SoC announcement (CNX-Software, 2022-05-06):
  <https://www.cnx-software.com/2022/05/06/allwinner-v853-arm-cortex-a7-risc-v-soc-comes-with-1-tops-npu-for-ai-vision-applications/>
- Linux-sunxi V853 wiki (community-maintained, not Allwinner):
  <https://linux-sunxi.org/V853>

---

## Stop point

Per the user's instructions, this is the V853 reference-acquisition
deliverable. **No PCB design or mechanical placement has been
started.** Stop and wait for explicit instruction before continuing
to the next component (camera, display, audio, etc.).
