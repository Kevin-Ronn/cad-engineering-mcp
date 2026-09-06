# System Block Diagram

This document shows the complete architecture of the V853 smart-glasses
reference design. The block diagram is consistent with
`system-signal-map.yaml` and `system-power-map.yaml`.

The existing authoritative frame geometry and PCB were not modified
during this reference-acquisition pass.

---

## Top-level architecture

```
                    PHONE
                   (heavy AI:
                    vision, LLM, OCR, TTS)
                      ↕ Wi-Fi 5 GHz / BT 5
                 ┌──────────────┐
                 │ Wi-Fi/BT     │
                 │ module       │
                 │ AW-CM276SM   │
                 │ 12x12x1.5 mm │
                 └──────┬───────┘
                        │ SDIO + UART
                        ↓
┌──────────────────────────────────────────────────────┐
│                    V853 SoC                           │
│   ARM Cortex-A7 1 GHz + RISC-V E907 + 1 TOPS NPU     │
└──────┬─────────┬─────────┬─────────┬─────────┬────────┘
       │         │         │         │         │
       │CSI0     │DSI0     │SMHC0    │SMHC1    │USB0
       │2x 2-lane│4-lane   │eMMC 5.1 │(SDIO    │USB-C
       │         │         │         │reserved)│
       ↓         ↓         ↓         ↓         ↓
  ┌────────┐ ┌──────┐ ┌──────┐  ┌──────┐  ┌─────────┐
  │Cameras │ │Display│ │eMMC  │  │ SDIO │  │ USB-C   │
  │ 2x     │ │(Lumus│ │      │  │  out │  │ 5 V     │
  │IMX708  │ │or    │ │      │  │      │  │ TPD4E05U04│
  │25x24x  │ │Dig.  │ │      │  │      │  │ ESD TVS │
  │11.5 mm │ │wave  │ │      │  │      │  │         │
  │        │ │guide)│ │      │  │      │  └────┬────┘
  └────────┘ └──────┘ └──────┘  └──────┘       │
                                                 ↓
                                          ┌──────────────┐
                                          │  BQ25185     │
                                          │  charger IC  │
                                          │  1.6x1.6 mm  │
                                          │  USB-C in    │
                                          │  Li-ion out  │
                                          └──────┬───────┘
                                                 │
                                                 ↓
                                          ┌──────────────┐
                                          │  Li-ion     │
                                          │  2x LP402535│
                                          │  parallel   │
                                          │  700 mAh    │
                                          │  2.59 Wh    │
                                          └──────────────┘

      V853 peripherals (left side, top to bottom):

      DMIC0  ──→  MP23DB01HP MEMS mic (front-frame, PDM)
      I2S0   ──→  MAX98390 amp left  (temple, 8 Ω speaker)
      I2S1   ──→  MAX98390 amp right (temple, 8 Ω speaker)
      TWI0   ──→  Shared I2C bus:
                    ├── BMI270 IMU  (temple)
                    ├── VEML7700 ALS (front-frame, behind light pipe)
                    ├── 2x TMP117   (one per temple, battery thermal)
                    ├── MAX17048 fuel gauge
                    ├── BQ25185 charger (control)
                    └── AXP2101 PMIC (control)
      GPIO   ──→  IR LED enable, camera reset/standby, display TE/reset/backlight,
                   user button, status LED, VBUS detect, IMU INT1/INT2,
                   ALS INT, fuel gauge ALERT, charger INT, PMIC IRQ
      PWM0   ──→  IR LED brightness / backlight (optional)
      GPADC0 ──→  NTC thermistor backup (optional, the TMP117 covers this)
      UART1  ──→  Debug console
      UART0  ──→  Bluetooth HCI (on the Wi-Fi/BT module)

      Power tree (right side):

      USB-C 5 V ──→ BQ25185 (charger + power-path) ──→ Li-ion cell(s)
                                                          │
                                                          ↓
                                                       VSYS ~3.7 V
                                                          │
                                                          ↓
                                                    AXP2101 PMIC
                                                  /  |  |  |  \
                                              DCDC1  2  3  4   5
                                                │  │  │  │   │
                                          CPU 0.9 GPU DRAM PLL
                                                │  0.9 1.1/1.35 1.0
                                                │
                                              LDO1..4
                                                │
                                          I/O 1.8 + sensor rails
```

---

## Detailed signal map (textual, ASCII)

```
V853
├── CSI0 (2x 2-lane sub-channels)
│   ├── sub-channel A → Camera 1 (left)
│   │   ├── CSI_D0P/N, CSI_D1P/N, CSI_CLKP/N
│   │   ├── I2C control (shared TWI0)
│   │   ├── GPIO reset, GPIO standby, GPIO INT
│   │   └── 1.0 mm FPC to the IMX708 15-pin connector
│   └── sub-channel B → Camera 2 (right)
│       ├── (same signals)
│       └── 1.0 mm FPC
│
├── DSI0 (4-lane)
│   ├── DSI_D0P/N, DSI_D1P/N, DSI_D2P/N, DSI_D3P/N, DSI_CLKP/N
│   ├── GPIO TE (tearing-effect), GPIO reset, GPIO backlight-enable
│   └── 1.0 mm FPC to the display engine (Lumus DK-50 / DigiLens / direct-DSI micro-OLED)
│
├── SMHC0 → eMMC 5.1
│   ├── D0-D7, CLK, CMD, RSTN
│   └── 1.8 V VCCQ; 3.3 V VCC
│
├── SMHC1 (reserved for SDIO Wi-Fi fallback or SD card)
│
├── USB0 (USB 2.0 DRD)
│   ├── USB_DP, USB_DN
│   ├── VBUS (5 V)
│   ├── CC1, CC2 (5.1 kohm to GND)
│   └── TPD4E05U04 4-channel ESD TVS
│
├── I2S0 → MAX98390 amp (left temple)
├── I2S1 → MAX98390 amp (right temple)
│
├── DMIC0 → MP23DB01HP mic (front-frame)
│
├── TWI0 (shared I2C bus, 1.8 V, 4.7 kohm pull-up)
│   ├── BMI270 IMU (0x68)
│   ├── VEML7700 ALS (0x10)
│   ├── TMP117 left (0x48)
│   ├── TMP117 right (0x49)
│   ├── MAX17048 fuel gauge (0x36)
│   ├── BQ25185 charger (0x6A)
│   └── AXP2101 PMIC (0x34)
│
├── SPI0 (reserved for debug / optional haptic)
│
├── UART0 → Bluetooth HCI (on the Wi-Fi/BT module)
├── UART1 → Debug console
│
├── GPIO
│   ├── IMU INT1, IMU INT2
│   ├── ALS INT
│   ├── TMP117 left ALERT
│   ├── TMP117 right ALERT
│   ├── MAX17048 ALERT
│   ├── BQ25185 INT
│   ├── AXP2101 IRQ
│   ├── Camera 1 reset, Camera 1 standby
│   ├── Camera 2 reset, Camera 2 standby
│   ├── Display TE, Display reset, Display backlight-enable
│   ├── IR LED enable
│   ├── IR LED 5 V boost enable
│   ├── User button
│   ├── Status LED
│   ├── Haptic enable (optional)
│   └── VBUS detect
│
├── PWM0 → IR LED brightness / backlight
├── PWM1 → Haptic drive (optional)
│
├── GPADC0 → NTC thermistor backup (optional)
│
└── Audio Codec (on-die, NOT used)

Wireless (off-SoC, connected via SDIO + UART)
├── AW-CM276SM (or FN-LINK 6221, Ampak AP6256, Murata 1XK)
├── Wi-Fi 2.4/5 GHz (or 2.4 GHz only) via SDIO
└── BT 4.2/5.0/5.1 via UART

Power (right side, see system-power-map.yaml)
├── USB-C 5 V → BQ25185 → VBAT (Li-ion 2x LP402535)
├── BQ25185 → VSYS (3.6-4.2 V)
├── AXP2101 → DCDC1 (CPU 0.9 V), DCDC2 (DRAM), DCDC3 (GPU), DCDC4 (DDR3L), DCDC5/LDO (PLL)
├── AXP2101 → LDO1 (I/O 1.8 V), LDO2 (RTC), LDO3 (sensor), LDO4 (display/audio)
└── VSYS direct → Wi-Fi module, audio amp PVDD, IR LED (via current-limit)
```

---

## Stop point

Per the user's instructions, this is the system-level electrical
architecture + final component qualification deliverable. No
mechanical placement, no PCB design, no FreeCAD work, and no
modification to the existing Wayfarer geometry, the working solid,
or any existing glasses electronics has been started. Awaiting
explicit instruction to continue.
