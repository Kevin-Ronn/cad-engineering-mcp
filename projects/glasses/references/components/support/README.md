# Support Components — Reference Index

This directory holds references for the small support components in
the V853 smart-glasses reference design.

The existing authoritative frame geometry and PCB were not modified
during this research pass.

---

## Contents

| File | Description |
| --- | --- |
| `veml7700_als.yaml` | Vishay VEML7700 ambient light sensor, 3.0 x 2.0 x 0.5 mm OPLGA, I2C, 0.003-120000 lux. Primary. |
| `tmp117_temperature.yaml` | TI TMP117 digital temperature sensor, 1.5 x 1.5 x 0.5 mm WCSP, I2C, 0.0078 C resolution, 0.1 C accuracy. Primary. |
| `lra_haptics_8mm.yaml` | Generic 8 mm LRA haptic actuator (market survey, no specific PN). OPTIONAL. |
| `tpd4e05u04_esd.yaml` | TI TPD4E05U04 4-channel ESD protection TVS array, USB-C. Primary. |
| `tvs_protection_misc.yaml` | Generic 5V unidirectional TVS (SMAJ5.0CA-class) for VBAT / VBUS / 3V3 / 1V8 rail protection. |
| `level_shifter_review.yaml` | Level-shifter requirements analysis: NO level shifters needed for the chosen component set, except potentially the audio amplifier I2S lines. |

---

## Recommended support components

| Item | Recommendation | Notes |
| --- | --- | --- |
| **Ambient light sensor** | Vishay VEML7700 (3.0 x 2.0 x 0.5 mm OPLGA) | Display brightness auto-adjust; 16-bit, 120000 lux dynamic range, I2C. |
| **Temperature sensor** | TI TMP117 (1.5 x 1.5 x 0.5 mm WCSP) | Battery / temple thermal monitoring; 0.1 C accuracy, 16-bit. |
| **Haptic actuator** | 8 mm LRA (OPTIONAL, no specific PN) | Requires temple pod (8 x 8 x 3 mm). Skip if temple thickness is hard-constrained. |
| **ESD: USB-C** | TI TPD4E05U04 (4-channel WCSP) | One per USB-C connector. |
| **ESD: VBAT / VBUS / 3V3 / 1V8 rails** | Generic 5V unidirectional TVS (SMAJ5.0CA or similar) | One per rail. |
| **Level shifters** | NONE required at this stage | All chosen components are 1.8 V I/O compatible except possibly the audio amp (verify per amplifier datasheet). |

---

## Geometry relevance

All recommended support components fit comfortably in the compute-PCB temple pod:
- VEML7700: 3.0 x 2.0 x 0.5 mm; mounted on the inner surface of the front-frame upper-bridge area with a small light pipe to the outside
- TMP117: 1.5 x 1.5 x 0.5 mm; mounted anywhere on the compute-PCB
- TPD4E05U04: 1.6 x 1.6 mm; mounted within 5 mm of the USB-C receptacle
- TVS diodes: 3.5 x 1.6 mm (SMA); mounted near the connector / rail
- LRA: 8 x 8 x 3 mm; too large for the Wayfarer 1.6 mm temple; requires a custom temple pod

---

## Open items

- [ ] Select the audio amplifier part number and verify the I/O voltage (most likely 1.8 V compatible; confirm)
- [ ] Confirm XR829 SDIO I/O voltage (1.8 V or 3.3 V)
- [ ] Decide on the haptic actuator (skip or include in BOM)
- [ ] Decide on the VEML7700 light-pipe location and geometry
- [ ] Validate the TMP117 placement for the best battery thermal coupling (must be in thermal contact with the cell)

---

## Stop point

Per the user's instructions, this is the support components
reference-acquisition deliverable. No mechanical placement, no PCB
design, no FreeCAD work, and no modification to the existing
glasses geometry, the working solid, or any glasses electronics has
been started. System interface and BOM-status files are next.
