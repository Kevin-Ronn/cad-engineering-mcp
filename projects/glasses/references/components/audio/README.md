# Audio System — Reference Index

This directory holds component references for the glasses' audio
chain:

- **1 microphone** (single mono mic, in the upper-front-frame region
  near the nose bridge, or in a temple)
- **2 speakers** (one per temple, open-ear / near-ear)
- **1 audio amplifier** (or 2 mono amplifiers, one per speaker)
  driving the speakers from the V853's I2S0/I2S1 outputs

The V853 has a built-in audio codec (1× DAC, 2× ADC, 2× I2S/PCM
controllers, 8× DMIC channels). The simplest audio architecture
uses the on-die ADC + I2S amplifiers (no external codec needed),
with a single digital PDM MEMS microphone routed to the DMIC block.

The existing authoritative frame geometry in
`projects/glasses/references/silhouette/wayfarer/` and
`projects/glasses/mechanical/main-frame/WORKING_FRAME_SOLID.FCStd`
was **not modified** during this research pass.

---

## Contents of this directory

### Microphones (digital, PDM or I2S)

| File | Description |
| --- | --- |
| `stmicro_mp23db01hp.yaml` | ST MP23DB01HP, 3.0 × 4.0 × 1.0 mm LGA, digital PDM, bottom-port, 64 dB SNR, 120 dB SPL AOP. Primary mic candidate. |
| `stmicro_mp34dt06j.yaml` | ST MP34DT06J, 3.1 × 4.0 × 1.05 mm LGA, digital PDM, top-port. Secondary mic candidate. |
| `knowles_sph0645lm4h_b.yaml` | Knowles SPH0645LM4H-B, 3.5 × 2.65 × 0.98 mm LGA, digital I2S, bottom-port. |
| `tdk_ics_43432.yaml` | TDK ICS-43432, 3.5 × 2.65 × 0.98 mm LGA, digital I2S, bottom-port. |

### Speakers (open-ear / near-ear)

| File | Description |
| --- | --- |
| `generic_6x10_dynamic_speaker.yaml` | Generic 6 × 10 × 3 mm dynamic micro-speaker class (Sonion, Knowles, Foster, Bujeon, Fortech). Primary speaker class. |
| `knowles_balanced_armature.yaml` | Knowles FK-series balanced armature (approx 5 × 3 × 2.5 mm, ~0.3 g). Higher sensitivity, requires acoustic tube. |

### Audio amplifiers (class-D, I2S input)

| File | Description |
| --- | --- |
| `adi_max98390.yaml` | ADI MAX98390, 1.33 × 1.33 mm WLP, 2.5 W into 8 Ω, filterless, I2S. Primary amplifier. |
| `adi_max98357a.yaml` | ADI MAX98357A, 3.0 × 3.0 mm TQFN, 3.2 W into 8 Ω, filterless, I2S. Secondary amplifier. |
| `ti_tas2562.yaml` | TI TAS2562, WCSP (dimensions not in summary), ~3.5 W into 8 Ω, I2S/TDM, integrated speaker protection. Alternative. |

---

## Microphone comparison

| Spec | ST MP23DB01HP | ST MP34DT06J | Knowles SPH0645LM4H-B | TDK ICS-43432 |
| --- | --- | --- | --- | --- |
| Dimensions (mm) | 3.0 × 4.0 × 1.0 | 3.1 × 4.0 × 1.05 | 3.5 × 2.65 × 0.98 | 3.5 × 2.65 × 0.98 |
| Acoustic port | bottom | top | bottom | bottom |
| Interface | PDM | PDM | I2S | I2S |
| SNR (dB A) | 64 | 64 | 65 (class) | 65 |
| AOP (dB SPL) | 120 | 120 | UNKNOWN | 120 |
| Sensitivity (dBFS) | -26 | -26 | UNKNOWN | -26 (class) |
| Bandwidth (Hz) | 50-8000 | 50-8000 | 50-12000 (class) | 50-20000 |
| Supply (V) | 1.6-3.6 | 1.6-3.6 | 1.62-3.6 | 1.62-3.6 |
| Active current (µA) | 650 | 650 | UNKNOWN | UNKNOWN |
| Op. temp (°C) | -40 to +85 | -40 to +85 | UNKNOWN | UNKNOWN |
| Price (USD) | 1.90-2.50 | 1.20-2.60 | 1-3 | 3.19 |
| Datasheet | ST DS12493 | ST DS12347 | Knowles (gated) | TDK (gated) |
| Confidence | HIGH | HIGH | MEDIUM | MEDIUM |

**PDM vs I2S** is the most important selection criterion. The V853
has 2× I2S/PCM controllers and a separate DMIC block. The DMIC block
supports up to 8 digital PDM microphones on a single bit-clock with
software-controlled L/R channel assignment. **PDM is preferred for
glasses** because the V853's DMIC block directly samples the bit
stream without needing the I2S controller, and because PDM is the
de-facto industry standard for multi-mic arrays. I2S mics (Knowles,
TDK) integrate a decimation filter inside the mic, which is a
slight cost / size penalty.

## Speaker comparison

| Spec | Generic 6 × 10 mm dynamic | Knowles FK balanced armature |
| --- | --- | --- |
| Dimensions (mm) | 6 × 10 × 3 (class) | ~5 × 3 × 2.5 (class) |
| Weight (g) | ~0.5 | ~0.3 |
| Impedance (Ω) | 32 (typical) | 100-200 |
| Rated power (mW) | 5-20 continuous | 1-5 continuous |
| Sensitivity (dB SPL / mW) | 90-105 | 105-115 |
| Bandwidth (Hz) | 300-10000 free-air, bass extends to ~80 with ear-canal coupling | 200-8000 (tuned per part) |
| THD at 1 kHz / 1 mW | < 5% (class) | < 2% (class) |
| Directivity | front-firing | very directional (tube-coupled) |
| Acoustic loading | needs back-volume enclosure | needs tuned acoustic tube |
| Confidence | MEDIUM (class); LOW (no specific PN) | MEDIUM (class); LOW (no specific PN) |

The brief asks for two speakers, one per temple. The Wayfarer temple
is 1.6 mm thick — far too thin to host any speaker. The speakers
must sit in the temple-integrated pod area (down the temple, near
the ear) or in a temple-tip pad. **A specific speaker must be
qualified and acoustically measured in a glasses-specific back-volume
before adoption.** The class is the right one; no specific part has
been chosen in this pass.

## Amplifier comparison

| Spec | ADI MAX98390 | ADI MAX98357A | TI TAS2562 |
| --- | --- | --- | --- |
| Package | 16-bump WLP | 16-pin TQFN-EP | WCSP |
| Dimensions (mm) | 1.33 × 1.33 × 0.5 | 3.0 × 3.0 × 0.75 | UNKNOWN (verify) |
| Interface | I2S | I2S | I2S / TDM |
| Output (W into 8 Ω) | 2.5 | 3.2 | ~3.5 |
| Efficiency (%) | 90 | 92 | 85 |
| THD+N (%) | < 0.1 | < 0.05 | < 0.1 |
| Filterless | yes | yes | yes |
| Speaker protection | no | no | yes (IV sense) |
| Supply (V) | 2.65-5.5 | 2.5-5.5 | 2.7-5.5 |
| Op. temp (°C) | -40 to +85 | -40 to +85 | -40 to +85 |
| Price (USD) | 2.50-3.50 | 1.65-1.85 | 3-5 |
| Confidence | HIGH | HIGH | MEDIUM |

The brief needs **two mono amplifiers** (one per temple), each
driving a 6-10 mm 32 Ω speaker. The MAX98390 (1.33 × 1.33 mm WLP)
is the smallest class-D I2S amplifier available; the MAX98357A is a
slightly larger but better-known second source. The TAS2562's
integrated speaker protection is a plus for micro speakers (which
can be over-driven), but its exact WCSP dimensions must be verified.

---

## Mechanical fit analysis (vs. existing Wayfarer geometry)

Wayfarer reference measurements (from
`projects/glasses/analysis/structure/full-mechanical-inspection.md`):

- Lens cavity Y range: 89.10 to 210.90 mm (depth 121.8 mm)
- Frame X width: 17.7 mm
- Frame Z height: 42.85 mm
- Temple transition thickness: **1.6 mm**
- Bridge Y width: 3.0 mm

**Microphone** (4 × 3 × 1 mm): easily fits in the upper-front-frame
region above the lens cavity (5-7 mm material) or in a small pad in
the upper-bridge. The V853's DMIC interface means only 1 bit-clock
+ 1 data line + 1 VDD + 1 GND are needed. Total: a 4-wire FPC.

**Speakers** (6 × 10 × 3 mm or 5 × 3 × 2.5 mm): **cannot fit in the
Wayfarer 1.6 mm temple transition**. The speakers must sit in a
temple-integrated pod area (which the Wayfarer reference STL does
not show — the temple is a thin solid block in the reference). A
custom temple design with a 7-10 mm cross-section is required, OR
the speakers are mounted at the front of the temple near the ear
opening. The acoustic path from the speaker to the ear canal is
unproven without a temple redesign.

**Amplifier** (1.33 × 1.33 mm WLP): easily fits anywhere on the
compute PCB (temple).

---

## Ranking on the glasses-specific criteria

1 = best, 4 = worst for mics; 1 = best, 2 = worst for speakers and
amplifiers.

### Microphones

| Criterion | ST MP23DB01HP | ST MP34DT06J | Knowles SPH0645LM4H-B | TDK ICS-43432 |
| --- | --- | --- | --- | --- |
| Size | 1 | 2 | 1 | 1 |
| Bottom-port (better gasket) | 1 | 4 | 1 | 1 |
| PDM interface (V853 native) | 1 | 1 | 4 (I2S) | 4 (I2S) |
| SNR | 1 | 1 | 1 | 1 |
| AOP | 1 | 1 | UNKNOWN | 1 |
| Bandwidth | 2 (50-8 kHz) | 2 | 1 (50-12 kHz) | 1 (50-20 kHz) |
| Price | 2 | **1** | 2 | 3 |
| Documentation | 1 | 1 | 2 (gated) | 2 (gated) |
| Availability | 1 | 1 | 1 | 1 |
| **Score (lower is better)** | **9** | **12** | **12** | **12** |

### Speakers (the class is right; no specific PN chosen)

| Criterion | 6 × 10 dynamic | FK balanced armature |
| --- | --- | --- |
| Size | 2 (6 × 10 × 3 mm) | **1** (5 × 3 × 2.5 mm) |
| Sensitivity | 2 (90-105 dB/mW) | **1** (105-115 dB/mW) |
| Power handling | **1** (5-20 mW) | 2 (1-5 mW) |
| Impedance match to MAX98390 / MAX98357A (8 Ω) | **1** (32 Ω close) | 2 (100-200 Ω — needs a higher-Z amp) |
| Acoustic loading | 2 (needs back-volume) | 2 (needs tuned tube) |
| Price | **1** ($0.30-5) | 2 ($5-20) |
| **Score (lower is better)** | **10** | **11** |

### Amplifiers

| Criterion | ADI MAX98390 | ADI MAX98357A | TI TAS2562 |
| --- | --- | --- | --- |
| Size | **1** (1.33 × 1.33) | 2 (3.0 × 3.0) | UNKNOWN (verify) |
| Output power | 3 (2.5 W) | 2 (3.2 W) | **1** (~3.5 W) |
| THD+N | 2 (< 0.1%) | **1** (< 0.05%) | 2 (< 0.1%) |
| Filterless | 1 | 1 | 1 |
| Speaker protection | 3 (none) | 3 (none) | **1** (IV sense) |
| I2S interface (V853 native) | 1 | 1 | 1 |
| Price | 2 ($2.50-3.50) | **1** ($1.65-1.85) | 3 ($3-5) |
| Documentation | **1** | **1** | 1 |
| Confidence | **1** | **1** | 2 (WCSP dim TBD) |
| **Score (lower is better)** | **14** | **12** | **10** *(but WCSP dim unverified)* |

---

## Recommendation

### Microphone

**PRIMARY: STMicro MP23DB01HP** (3.0 × 4.0 × 1.0 mm, PDM, bottom-port, 64 dB SNR, 120 dB SPL AOP)

Why: bottom-port makes the gasket to the front-frame enclosure easy to design; PDM is native to the V853's DMIC block; active production; well-documented ST datasheet; cheap.

**SECONDARY: STMicro MP34DT06J** (3.1 × 4.0 × 1.05 mm, PDM, top-port) — drop-in if the bottom-port gasket is awkward to design in the front frame.

### Speaker

**PRIMARY CLASS: 6 × 10 mm dynamic micro-speaker** (Sonion / Knowles / Foster / Bujeon / Fortech, 32 Ω, 5-20 mW). A specific part must be selected and acoustically measured in a glasses-specific back-volume.

**SECONDARY CLASS: Knowles FK-series balanced armature** (5 × 3 × 2.5 mm, 100-200 Ω, 1-5 mW). Higher sensitivity and smaller volume, but requires acoustic-tube engineering and a higher-impedance amplifier.

**Cannot pick a specific part number yet** — both classes are right, and the final choice requires acoustic measurement of specific candidate parts in a Wayfarer-style temple / back-volume. This must happen in the next pass.

### Amplifier

**PRIMARY: ADI MAX98390** (1.33 × 1.33 × 0.5 mm WLP, 2.5 W into 8 Ω, filterless, I2S)

Why: smallest class-D I2S amplifier in the 1.3 × 1.3 mm class; 2.5 W is more than enough for a 6-10 mm 32 Ω micro-speaker (max continuous power 5-20 mW); filterless means no bulky LC output components; I2S interface matches V853 I2S0/I2S1 directly.

**SECONDARY: ADI MAX98357A** (3.0 × 3.0 × 0.75 mm TQFN, 3.2 W into 8 Ω, filterless, I2S). Better-known, on breakout boards for prototyping, slightly larger.

**ALTERNATIVE: TI TAS2562** (WCSP, ~3.5 W, I2S/TDM, integrated speaker protection). The integrated speaker protection is a real plus for micro speakers (which can be over-driven and damaged); verify the WCSP dimensions before adoption.

---

## Open items to resolve before the next pass

- [ ] Qualify a specific 6 × 10 mm dynamic micro-speaker (Sonion, Knowles, Foster, Bujeon, or Fortech). Acquire a sample, measure sensitivity and frequency response in a Wayfarer-style back-volume.
- [ ] Verify the TAS2562 WCSP package dimensions.
- [ ] Decide whether the speakers mount at the temple-tip (behind the ear) or at the front of the temple (near the ear-canal entrance). Each location has a different acoustic path.
- [ ] Decide whether the speakers are open-ear (no seal, leakage-tolerant) or sealed (ear-canal seal, requires a custom ear-tip). Open-ear is simpler but lower SPL at low frequencies; sealed is louder but requires custom ear-tip design.
- [ ] Confirm that the V853's I2S0 / I2S1 outputs can drive the MAX98390/MAX98357A directly (signal levels, clock frequencies, master/slave mode).
- [ ] Confirm that the V853's DMIC block supports 8 kHz / 16 kHz / 48 kHz decimation as required by the voice pipeline.

---

## Stop point

Per the user's instructions, this is the audio reference-acquisition
deliverable. **No mechanical placement, no PCB design, no FreeCAD
work, and no modification to the existing Wayfarer geometry, the
working solid, or any glasses electronics has been started.** The
battery / power reference acquisition has not been started.
Awaiting explicit instruction to continue.
