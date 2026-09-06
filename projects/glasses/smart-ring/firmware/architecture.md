# Firmware Architecture — V1 Smart Ring

**Project:** `projects/glasses/smart-ring/`
**Date:** 2026-09-05
**Status:** READ-ONLY for hardware artifacts. This document defines the firmware architecture only. No PCB / CAD / KiCad / FreeCAD / firmware source code is created by this artifact.

**Target MCU:** Nordic nRF54L15 (Cortex-M33F; 256 KB RAM; 1 MB flash; BLE 5.4; TrustZone-M)
**RTOS:** Zephyr (nRF Connect SDK v2.x; mainstream support per `components/mcu-selection.yaml`)
**Parent artifacts:** `electrical/system-architecture.yaml`, `electrical/ble-interface.yaml`, `electrical/sensor-interface.yaml`, `protocol/ring-gatt-spec.yaml`

---

## 1. Goals and non-goals

### Goals
- Single-SoC architecture. No separate touch MCU (Azoteq IQS127D is a slave IC, not an MCU). No separate charger MCU (MCP73831 is a standalone charger, not an MCU). The nRF54L15 owns all firmware.
- Deterministic, low-latency gesture pipeline. Gesture events reach the central within 25 ms of the touch/IMU event (per `protocol/ring-gatt-spec.yaml` §"Gesture Delivery").
- Deep-sleep-dominant. The ring spends ~95% of its time in System OFF or System ON / idle with BLE only (see `electrical/power-budget.yaml`).
- Portable sensor manager. All sensor acquisition is mediated by a C11-friendly module with mockable interfaces so the same firmware logic is host-testable under ctest + ASan/UBSan/TSan (see `research/even-r1-reference.md` §4, "Honest boundary on unattributable behavior").
- Honest drop counter + sequence-gap accounting on every BLE-bound event stream (per `research/even-r1-reference.md` §4).
- OTA via MCUboot over BLE (per `electrical/ble-interface.yaml` §security).

### Non-goals (V1)
- No on-device AI / ML inference. Gesture recognition is deterministic (per the brief).
- No PPG (V2 only; see `components/ppg-selection.yaml`).
- No simultaneous BLE connections (V1 role-switches within 100 ms; per `electrical/ble-interface.yaml`).
- No on-device audio. No on-device display.
- No Wi-Fi. BLE only.

---

## 2. Layered architecture

The firmware is organised into nine layers. Layers depend only on layers below them (no upward dependencies). The boundary between layers is a `static inline` function or a function pointer table; never a `#define`.

```
+---------------------------------------------------+
|  Application: ring app (boot, factory, OTA)        |  ← main()
+---------------------------------------------------+
|  Configuration manager  (RR07; TLV)               |
+---------------------------------------------------+
|  Gesture engine + wear-state manager              |
+---------------------------------------------------+
|  BLE / GATT service  (RR01..RR09; advertising)    |
+---------------------------------------------------+
|  Haptic manager  (DRV2605L over I2C)              |
+---------------------------------------------------+
|  Power manager  (rail gating; state machine)      |
+---------------------------------------------------+
|  Portable sensor manager  (sample ring buffers)   |
+---------------------------------------------------+
|  Sensor drivers  (IQS127D, BMI270, TMP117,        |
|                   MAX17048; V2: MAX86140)         |
+---------------------------------------------------+
|  Hardware / board  (Zephyr devicetree + HAL)      |
+---------------------------------------------------+
```

### 2.1 Hardware / board layer

Responsibilities:
- Zephyr devicetree binding the nRF54L15 WLCSP-2.5x2.5 mm package pins to peripherals (I2C, GPIO, RADIO, RTC, SAADC, CRYPTO).
- Zephyr board file (`boards/arm/v1_ring/v1_ring.dts`) for the ring's PCB. The board file is the **only** place where pin assignments live. All other firmware references peripherals by Zephyr `pinctrl-names` + `&i2c0 { ... }` aliases.
- Bootloader split: MCUboot in the first 32 KB of flash; application in the next 256 KB; settings in the next 16 KB; storage (bonding + config) in the final 24 KB. (TBD: exact layout; see §14.)
- Power rail enable/disable GPIO. The 3.3 V and 1.8 V LDOs are gated by the nRF54L15's GPIO (per `electrical/power-tree.yaml`).

**No pin numbers are fabricated here.** The actual pin map is decided when the schematic is drawn. Until then, every reference to a GPIO uses a Zephyr devicetree alias such as `touch_int_gpios = <&gpio0 5 GPIO_ACTIVE_HIGH>;`.

### 2.2 Sensor drivers

Responsibilities:
- One driver per sensor. Each driver implements a `struct sensor_driver_api` with `init`, `enable`, `disable`, `read`, `irq_handler` members.
- All drivers use the Zephyr I2C bus API (`i2c_read`, `i2c_write`, `i2c_burst_read`) on `I2C0` at 400 kHz Fast-Mode (per `electrical/sensor-interface.yaml`).
- All drivers put the sensor in its lowest-power state on `disable()`. The sensor-manager layer calls `disable()` when no consumer is interested in the data.

| Driver | Sensor | I2C address | Notes |
| --- | --- | --- | --- |
| `drv_iqs127d` | Azoteq IQS127D-00200 touch IC | 0x34 (TBD per `electrical/sensor-interface.yaml` `known_uncertainties`) | INT GPIO; built-in gesture recognition (the firmware also has a gesture engine for fusion) |
| `drv_bmi270` | Bosch BMI270 IMU | 0x68 (SDO=GND) | INT1+INT2; FIFO 1 KB; 50 Hz ODR for V1 |
| `drv_tmp117` | TI TMP117 temperature | 0x48 (A0=GND) | ALERT open-drain; polled at 1 Hz |
| `drv_max17048` | ADI MAX17048 fuel gauge | 0x36 | ALERT open-drain; on low battery |
| `drv_drv2605l` | TI DRV2605L haptic driver | 0x5A (TBD) | OUT+ / OUT- to the LRA; EN GPIO; auto-resonance |
| `drv_max86140` (V2 only) | Maxim MAX86140 PPG | TBD | INT GPIO; LED anode drives; PD cathode input |
| `drv_mcp73831` (passive) | MCP73831 charger | n/a | STAT open-drain (optional GPIO) |

The driver layer is the **only** place that talks to a sensor's register set. The portable sensor manager (§2.3) knows nothing about register addresses.

### 2.3 Portable sensor manager

The portable sensor manager is the abstraction that hosts the V1 ring's runtime state. It is inspired by the Smart Ring Digital Twin's portable sensor manager (per `research/smart-ring-landscape.md` §5) but is re-implemented, not copied. The contract:

```c
typedef struct sm_sample_header {
    uint32_t timestamp_us;     // monotonic microsecond timestamp from RTC counter
    uint8_t  sensor_id;        // SM_SENSOR_IMU, SM_SENSOR_TOUCH, SM_SENSOR_TEMP, ...
    uint8_t  flags;            // bit 0 = FIFO watermark; bit 1 = error; bits 2..7 reserved
    uint16_t payload_len;      // bytes of payload that follow
    uint8_t  payload[];        // sensor-specific; e.g. {int16 accel[3]; int16 gyro[3];} for BMI270
} sm_sample_header_t;
```

Public API:
- `sm_init()` — initialises ring buffers, allocates the sample-queue memory pool (static), starts the RTC counter.
- `sm_acquire(sensor_id, **out_buf)` — returns a writable buffer slot from the static pool; called by sensor drivers from their IRQ handlers (or from the sensor-manager worker thread, depending on driver policy).
- `sm_publish(sensor_id, payload, payload_len)` — commits the buffer; stamps the timestamp; pushes into the per-sensor lock-free ring buffer (MPSC for ISR->worker; SPSC for worker->worker).
- `sm_subscribe(sensor_id, cb, priority)` — registers a callback to be invoked on the worker thread when a sample becomes available.
- `sm_drop_count(sensor_id)` — returns the count of dropped samples since boot.

Design constraints:
- **No dynamic allocation in the real-time path.** All sample buffers, ring buffers, and metadata are allocated at `sm_init()` from a static memory pool (`K_HEAP` or static array). The pool size is fixed at compile time based on `SM_MAX_SAMPLES_PER_SENSOR` × `SM_NUM_SENSORS`.
- **Lock-free where possible.** Single-producer / single-consumer ring buffers with acquire/release memory ordering. Multi-producer is handled by a CAS-based slot allocator for the IMU (the only sensor with multi-source writers: INT1 wake + INT2 data-ready).
- **Drop-oldest overflow policy.** When a ring buffer is full, the new sample overwrites the oldest. The drop counter increments. This is the explicit policy chosen for the ring (per `research/smart-ring-landscape.md` §5, "overwrite-oldest overflow policy").
- **Common timestamping.** All samples use the nRF54L15 RTC counter (1 µs resolution after prescaler; per the nRF54L15 PS v1.0). The counter wraps at 2^24; firmware normalises to a monotonic 64-bit timestamp for host-side testability.

### 2.4 Gesture engine + wear-state manager

The gesture engine combines touch events from the IQS127D with IMU events from the BMI270 to produce the canonical gesture vocabulary defined in `protocol/ring-gatt-spec.yaml` §"gesture_vocabulary_table".

The wear-state manager tracks whether the ring is on a finger or off. In V1 it uses the touch IC's "touch detected" flag plus the IMU's stillness pattern to infer wear. (A dedicated skin-contact electrode is V2.)

These two managers share one state machine (see §5). The gesture engine is a pure function of the state machine's events; the wear-state manager is one of the state machine's high-level states.

### 2.5 BLE / GATT service

The BLE / GATT service exposes the RR01..RR09 characteristics defined in `protocol/ring-gatt-spec.yaml` §"ring_control_service". The service layer is a thin Zephyr wrapper:

- One Zephyr `bt_gatt_service` registration for the Ring Control service.
- One `bt_gatt_chrc` per characteristic.
- `CCCD` descriptors auto-managed by Zephyr.
- `notify` callbacks push into the BLE worker thread (see §3); they never run in ISR context.
- `write` callbacks validate + queue + ACK; they return `BT_GATT_ERR_SUCCESS` only after the write is durable (the configuration blob is persisted to flash before the ACK is sent; per `protocol/ring-gatt-spec.yaml` §"Configuration Update").

### 2.6 Haptic manager

A FIFO of `haptic_request_t { id, intensity, deadline_ms }`. The haptic manager drains the FIFO, writes the pattern + intensity to the DRV2605L, and records the completion time. See §9 for arbitration and cancellation rules.

### 2.7 Power manager

Drives the rail-enable GPIOs and the BLE connection-state machine. The power manager's state machine mirrors §8. It is the only module that calls `pm_policy_state_lock()` / `pm_policy_state_unlock()` in Zephyr.

### 2.8 Configuration manager

Owns the TLV blob in RR07. Provides typed accessors (`cfg_get_gesture_threshold_ms()`, `cfg_set_gesture_threshold_ms(uint16_t)`, ...). On every read, validates the blob against the schema; if the blob is invalid, falls back to compile-time defaults and increments a fault counter.

### 2.9 Application

The application layer contains `main()`, the boot sequence, the factory-reset command, the OTA entry, and the diagnostic shell command-line interface (when the device is in the BOOT state with the diagnostic GPIO asserted).

---

## 3. Thread / work-queue model

Zephyr provides several execution contexts. The V1 firmware uses five of them. The mapping is explicit; no thread is added without a reason.

| Context | Priority | Stack | Purpose | Pre-empted by |
| --- | --- | --- | --- | --- |
| ISR | n/a | 0 | Touch INT, IMU INT1/INT2, RTC compare, RADIO IRQ, I2C IRQ | Hard faults |
| System workqueue | 0 (lowest) | 1 KB | Zephyr internal; BLE host stack callbacks | All other threads |
| BLE worker | 5 | 1.5 KB | Notify-on-RR01, notify-on-RR03/RR04, write-of-RR02/RR05/RR07 handlers, connection-state transitions | Sensor worker, app worker |
| Sensor worker | 7 | 2 KB | Sample-queue drain, gesture state-machine tick, calibration, wear-state evaluation | App worker |
| App worker | 9 (highest) | 2 KB | OTA entry, factory reset, diagnostic CLI, configuration persist | (top) |
| Idle/system-on | n/a | n/a | Main CPU loop; BLE stack wakes on events; sensor worker wakes on sample-queue not-empty | All |

Priorities follow Zephyr conventions where **higher = higher priority**.

### 3.1 ISR context

Only the following run in ISR context. Everything else defers via `k_work_submit` or a Zephyr semaphore.

- Touch IC INT GPIO handler (`touch_isr`). Wakes the sensor worker via `k_sem_give(&sm_touch_sem)`. Reads the IQS127D's event register inside the ISR (single byte, ≤ 4 µs) and stores the event mask in a static variable; the sensor worker re-reads the full event FIFO when scheduled.
- IMU INT1 handler (`imu_int1_isr`). The BMI270 INT1 fires on motion. The handler wakes the sensor worker (`k_sem_give(&sm_imu_sem)`) and records the wake reason. **No I2C read in ISR.** The sensor worker reads the FIFO when scheduled.
- IMU INT2 handler (`imu_int2_isr`). Fires on FIFO watermark. Same pattern as INT1.
- Temperature ALERT handler (`temp_alert_isr`). Optional; the V1 polls at 1 Hz so the ALERT is not strictly needed (per `electrical/sensor-interface.yaml`).
- Fuel-gauge ALERT handler (`fg_alert_isr`). Asserts on low battery. Wakes the sensor worker, which wakes the BLE worker to notify RR03 + RR04.
- RTC compare handler (`rtc_compare_isr`). Periodic 1 Hz tick for temperature + fuel-gauge poll.
- RADIO IRQ handler. Zephyr's BLE stack owns this.
- I2C IRQ handler. Zephyr's I2C driver owns this.

### 3.2 Sensor worker

The sensor worker is a Zephyr `k_work_q` with a single worker thread at priority 7. It runs the following loop:

```
for (;;) {
    k_sem_take(&sm_any_sem, K_FOREVER);  // wakes on any sensor sem
    drain_touch_fifo();                  // IQS127D events
    drain_imu_fifo();                    // BMI270 samples
    drain_temp_fifo();                   // TMP117 conversions
    drain_fg_fifo();                     // MAX17048 alerts
    run_gesture_state_machine();
    update_wear_state();
}
```

Drain functions are bounded: each one processes at most N samples per worker iteration, where N is the watermark that would saturate one full ring buffer (configurable; default 16). This guarantees that no single sensor can starve the others.

### 3.3 BLE worker

The BLE worker is a Zephyr `k_work_q` with a single worker thread at priority 5. It handles:

- Connection-state transitions (advertising → connected → disconnected).
- RR01 notifications (queue-drained; rate-limited to 1 per connection event).
- RR03 + RR04 notifications (rate-limited to 1 Hz).
- RR02 / RR05 / RR07 writes (validated, queued, ACKed).
- Configuration persist (writes the RR07 blob to flash).

The BLE worker never blocks on the sensor worker; if the sensor worker hasn't yet drained a gesture event, the BLE worker waits via a Zephyr semaphore (`sm_gesture_ready_sem`) with a 50 ms timeout. On timeout, the BLE worker drops the event and increments the drop counter.

### 3.4 App worker

The app worker runs OTA, factory reset, and the diagnostic CLI. It is priority 9 so that OTA (which freezes the BLE stack briefly) does not starve gesture notification.

---

## 4. Sensor acquisition timing

The acquisition timing budget is the most power-critical part of the firmware. Every sample must be acquired in a bounded time; missed deadlines are recorded as faults.

| Sensor | Mode | ODR | Interrupt | Worker drain latency | End-to-end latency (event → BLE notify) |
| --- | --- | --- | --- | --- | --- |
| IQS127D (touch) | Active scan | 100 Hz (configurable; 50 Hz OK for non-rotational) | INT GPIO rising | < 5 ms | < 25 ms |
| BMI270 (IMU) | FIFO + INT1 + INT2 | 50 Hz | INT1 on motion; INT2 on FIFO watermark | < 10 ms (FIFO drain) | < 50 ms |
| TMP117 (temperature) | One-shot conversion | 1 Hz | (none; polled) | < 5 ms | n/a (not real-time) |
| MAX17048 (fuel gauge) | Continuous conversion | on-demand | ALERT GPIO | < 5 ms | < 100 ms (low battery event) |
| DRV2605L (haptic) | Standby; wake on RR05 | event-driven | n/a | < 15 ms (write → LRA drive begins) | < 15 ms |
| MAX86140 (V2 PPG) | FIFO + INT | 100 Hz (configurable) | INT GPIO | < 50 ms (V2 streaming) | n/a (V2) |

The end-to-end latency for gestures is **25 ms**. This matches the latency target in `protocol/ring-gatt-spec.yaml` §"Gesture Delivery".

### 4.1 Deferred processing

The IQS127D has a built-in gesture engine that produces high-level events (TAP, SWIPE, ...) in firmware. The firmware **does not trust** the IQS127D's gesture engine for V1; the firmware re-runs the recognition on the touch sample stream so that we have full control over thresholds and so that the host-side tests can drive the gesture engine deterministically. (This is consistent with the brief: "do not claim IP-rating without testing" and the principle that vendor firmware must be validated, not trusted.)

The BMI270 also has a built-in step counter + activity recogniser. V1 uses only the raw 6-axis data from the FIFO; the built-in recogniser is left disabled to save power.

---

## 5. Gesture state machine

The gesture state machine is a single deterministic finite automaton. States and transitions are defined as a static const table so that host-side tests can verify all transitions.

### 5.1 States

```
IDLE
TOUCH_DOWN         (touch contact; no direction decided yet)
TOUCH_HOLD         (touch held; evaluating long-press timeout)
SWIPE_IN_PROGRESS  (touch slider movement detected; direction not yet committed)
GESTURE_CANDIDATE  (touch released or IMU event ready to emit)
GESTURE_EMIT       (gesture committed; sending to BLE worker)
WEAR_OFF           (ring is not on a finger)
WEAR_ON            (ring is on a finger; normal operation)
```

### 5.2 Events (inputs)

- `TOUCH_PRESS(electrode_id)` — IQS127D reports a touch on electrode `electrode_id`.
- `TOUCH_RELEASE` — IQS127D reports touch release.
- `TOUCH_MOVE(from_id, to_id)` — IQS127D reports a swipe motion.
- `IMU_MOTION(magnitude)` — BMI270 INT1; the magnitude is the peak acceleration in the last 100 ms.
- `IMU_ROTATION(angular_velocity_z)` — BMI270 gyroscope Z-axis reading above threshold.
- `TIMEOUT(deadline_id)` — RTC compare fires; one of the gesture-deadline timers expired.
- `WEAR_ON` / `WEAR_OFF` — wear-state manager transitions.

### 5.3 Outputs (gesture vocabulary)

The output gesture ID is the canonical set from `protocol/ring-gatt-spec.yaml` §"gesture_vocabulary_table":
- `0x01` TAP, `0x02` DOUBLE_TAP, `0x03` LONG_PRESS
- `0x04` SWIPE_LEFT, `0x05` SWIPE_RIGHT, `0x06` SWIPE_UP, `0x07` SWIPE_DOWN
- `0x08` ROTATE_CW, `0x09` ROTATE_CCW
- `0x10` WEAR_PUT_ON, `0x11` WEAR_TAKEN_OFF
- `0x7F` TEST_DIAGNOSTIC (host-side test only)

### 5.4 Transition rules (summary)

| From | Event | To | Output |
| --- | --- | --- | --- |
| IDLE | TOUCH_PRESS | TOUCH_HOLD | (start long-press timer = 600 ms; start double-tap window = 300 ms) |
| TOUCH_HOLD | TOUCH_RELEASE before long-press timer | GESTURE_CANDIDATE | (mark as TAP candidate) |
| TOUCH_HOLD | TOUCH_MOVE | SWIPE_IN_PROGRESS | (start swipe commit timer = 50 ms) |
| TOUCH_HOLD | TIMEOUT(long-press) | GESTURE_CANDIDATE | (mark as LONG_PRESS candidate) |
| SWIPE_IN_PROGRESS | TOUCH_MOVE consistent direction | SWIPE_IN_PROGRESS | (reset swipe commit timer) |
| SWIPE_IN_PROGRESS | TOUCH_RELEASE before swipe commit timer | GESTURE_CANDIDATE | (mark as SWIPE_* candidate) |
| SWIPE_IN_PROGRESS | TIMEOUT(swipe commit) | GESTURE_CANDIDATE | (mark as SWIPE_* candidate; direction = last move) |
| GESTURE_CANDIDATE | TIMEOUT(double-tap window) | GESTURE_EMIT | (emit TAP / SWIPE_* / LONG_PRESS) |
| GESTURE_CANDIDATE | TOUCH_PRESS within double-tap window | TOUCH_HOLD | (mark as DOUBLE_TAP candidate) |
| GESTURE_EMIT | (always) | IDLE | (send to BLE worker) |
| IDLE | IMU_ROTATION above threshold for 200 ms | GESTURE_CANDIDATE | (mark as ROTATE_* candidate; direction = sign of angular velocity) |
| WEAR_OFF | TOUCH_PRESS (debounced 100 ms) | WEAR_ON + emit WEAR_PUT_ON | (emit WEAR_PUT_ON) |
| WEAR_ON | (no touch for 5 s) AND (IMU still for 30 s) | WEAR_OFF + emit WEAR_TAKEN_OFF | (emit WEAR_TAKEN_OFF) |

### 5.5 Debounce

- All `TOUCH_PRESS` events are debounced with a 50 ms refractory period (the IQS127D has built-in debounce; this is a firmware second-pass).
- All `IMU_MOTION` events are debounced with a 20 ms refractory period.
- The wear-state manager uses a 100 ms debounce on TOUCH_PRESS for WEAR_OFF → WEAR_ON, and a 30 s stillness window for WEAR_ON → WEAR_OFF.

### 5.6 Timeout handling

- The long-press timer is 600 ms (compile-time default; configurable via RR07).
- The double-tap window is 300 ms.
- The swipe commit timer is 50 ms.
- All timers are Zephyr `k_timer` instances backed by the RTC.

### 5.7 Mutually exclusive gesture transitions

- A LONG_PRESS in progress blocks all subsequent gestures until the touch is released (LONG_PRESS is "absorbing").
- A SWIPE in progress blocks DOUBLE_TAP recognition (a swipe is a directional intent; the user has not tapped).
- TAP and DOUBLE_TAP are mutually exclusive within the double-tap window: a single touch becomes either a TAP or a DOUBLE_TAP, never both.
- WEAR_PUT_ON and WEAR_TAKEN_OFF are never emitted within 1 s of each other (debounced wear transitions).
- ROTATE_* is mutually exclusive with touch-based gestures during the same evaluation window (the IMU rotation event starts a 200 ms quiet window during which touch events are ignored; this prevents a wrist-rotation + accidental touch from being interpreted as two gestures).

---

## 6. Drop-counter / reliability model

Every sample and every gesture event has a monotonically increasing identifier. The drop counter increments when an overrun occurs. The model is consistent with the Digital Twin pattern (per `research/smart-ring-landscape.md` §5) but is re-implemented.

### 6.1 Sample counters

| Counter | Width | Wraps at | Purpose |
| --- | --- | --- | --- |
| `sample_seq` per sensor | uint32 | 2^32 | Monotonic per-sensor sample ID. The 16-bit LSB is exposed in BLE notifications for the sensors that stream (V2; V1 does not stream). |
| `gesture_seq` | uint16 | 65535 | Exposed in every RR01 notification. The glasses Central verifies monotonic sequence (per `protocol/ring-gatt-spec.yaml` §6 + `electrical/ble-interface.yaml` §security). Wraps; gaps indicate dropped events. |
| `drop_count_imu` | uint16 | 65535 | IMU ring buffer overflows since boot. |
| `drop_count_touch` | uint16 | 65535 | Touch ring buffer overflows since boot. |
| `drop_count_temp` | uint16 | 65535 | Temperature polling misses (if the worker is starved). |
| `drop_count_gesture` | uint16 | 65535 | Gestures that could not be enqueued for BLE notify (the BLE worker was saturated). |

### 6.2 Overflow detection

- Every ring buffer has a watermark at 75% full. When the watermark is hit, the worker logs a warning and increments the drop counter.
- When the ring buffer is 100% full, the new sample overwrites the oldest; the drop counter increments.
- When the BLE worker's notify queue is full, the gesture engine receives `ERR_GESTURE_QUEUE_FULL` (per `protocol/ring-gatt-spec.yaml` §"error_handling"). The gesture engine increments `drop_count_gesture` and does not retry; the central will see a sequence gap and infer the drop.

### 6.3 BLE notification sequence numbers

- The 16-bit `gesture_seq` is incremented on every gesture committed to the BLE worker's queue (not on every notify — if the notify is dropped, the sequence still incremented; the central will see a gap).
- The sequence is reset to 0 only on factory reset. Bonding and reboot do NOT reset the sequence.

### 6.4 Synchronisation / recovery behaviour

- On reboot, the gesture sequence is **NOT** reset. The central's last-seen sequence is compared against the ring's current sequence; if the gap is > 100, the central can request a resync via the Configuration characteristic.
- On sensor failure (see §10), the firmware disables the sensor, increments a fault counter, and emits a `TEST_DIAGNOSTIC` gesture event (id 0x7F) with a payload describing the fault. The central logs the fault.

---

## 7. BLE integration

The BLE service layer is a thin Zephyr wrapper around the GATT database defined in `protocol/ring-gatt-spec.yaml`.

### 7.1 Module-to-characteristic mapping

| Firmware module | Characteristic(s) | Direction |
| --- | --- | --- |
| Gesture engine | RR01 (notify), RR02 (write; ACK) | ring → central; central → ring |
| Power manager + sensor manager (fuel gauge) | RR03 (read+notify; battery) | ring → central |
| Sensor manager (charger state) | RR04 (read+notify; charging state) | ring → central |
| Haptic manager | RR05 (write; haptic command) | central → ring |
| App (firmware version) | RR06 (read) | ring → central |
| Configuration manager | RR07 (read+write; TLV blob) | bidirectional |
| Sensor manager (TMP117, V2) | RR08 (read+notify; temperature) | ring → central |
| Sensor manager (MAX86140, V2) | RR09 (notify; PPG HR) | ring → central |

### 7.2 Connection-state machine

```
DISCONNECTED
   ↓ (advertise timeout = 0; central connects)
ADVERTISING
   ↓ (central initiates connection)
CONNECTING
   ↓ (connection complete; encryption established)
CONNECTED_IDLE
   ↓ (CCCD write of RR01/RR03/RR04 → notifications enabled)
CONNECTED_ACTIVE
   ↓ (gesture event)
CONNECTED_ACTIVE (notify)
   ↓ (no events for 5 min; or central requests sleep)
CONNECTED_IDLE
   ↓ (disconnect)
DISCONNECTED
   ↓ (re-advertise after 1 s)
ADVERTISING
```

The connection-state machine is driven by Zephyr's BLE host callbacks. The state machine transitions are atomic (Zephyr's `bt_conn` lock is held during transitions).

### 7.3 Notification scheduling

- RR01 notifications are scheduled by the BLE worker when the gesture engine enqueues a gesture event. The worker holds a single in-flight notification at a time; the next notification cannot be queued until the previous one is ACKed by the central (via RR02) or 50 ms elapses (whichever comes first).
- RR03 / RR04 notifications are rate-limited to 1 Hz. The state-change trigger fires immediately; the rate-limit guarantees no more than 1 notify per second.
- RR01 notifications are **not** rate-limited; they are event-driven.

### 7.4 Configuration updates

- The phone writes RR07 with a TLV blob. The BLE worker validates the version header (must be 0x0001 in V1), the tag lengths, and the tag values within allowed ranges.
- If the blob is valid, the BLE worker persists it to flash (sector erase + write; ~ 50 ms) and ACKs the write.
- If the blob is invalid, the BLE worker returns `ERR_CONFIG_INVALID` (0x81) and does not persist.

### 7.5 Replay-counter handling

- The 16-bit gesture sequence on RR01 is the replay counter. The firmware increments the counter atomically on every gesture enqueued.
- The firmware does NOT validate the incoming RR02 ACK (the central's ACK is informational; the firmware uses it to advance its retry queue, but does not reject an out-of-order ACK).
- The firmware does NOT validate incoming BLE sequence numbers on its own writes; the BLE host handles encryption + integrity.

### 7.6 Pairing / security boundary

- The BLE host stack handles LE Secure Connections pairing (per `protocol/ring-gatt-spec.yaml` §"security_and_pairing").
- The application layer does NOT touch the LTK, IRK, or CSRK directly. The Zephyr settings subsystem stores them in the dedicated storage partition.
- The OOB data (public key + nonce) is provisioned in the factory; it is read-only at runtime.
- The OTA signing key (Ed25519 or ECDSA P-256 public key) is provisioned in the factory; it is read-only at runtime.

---

## 8. Power-state machine

The power manager is the only module that calls Zephyr PM APIs. It mirrors the states listed in `electrical/system-architecture.yaml` §"firmware_state_machine".

### 8.1 States

| State | CPU | BLE | Touch IC | IMU | TMP117 | Fuel gauge | LRA | Current estimate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BOOT | active | off | off | off | off | off | off | ~ 5 mA (peak; < 100 ms) |
| PAIRING | active | advertising | off | off | off | off | off | ~ 1 mA |
| CONNECTED_IDLE | System ON idle | connected (sleep) | sleep | sleep | sleep | sleep | off | ~ 0.2 mW |
| CONNECTED_ACTIVE | System ON | connected (event) | scan | FIFO | on-demand | on-demand | pulse | ~ 1.5 mW (avg) |
| IDLE | System ON | off | off | off | off | off | off | ~ 0.05 mW |
| GESTURE | System ON | connected | scan | FIFO | off | off | off | ~ 0.5 mW (avg) |
| HAPTIC | System ON | connected | off | off | off | off | drive | ~ 165 mW (peak; < 100 ms) |
| SENSING | System ON | connected | off | FIFO | off | off | off | ~ 0.5 mW (avg) |
| SLEEP | System OFF | off | off | off | off | off | off | ~ 0.015 mW |
| CHARGING | System OFF | off | off | off | off | off | off | ~ 0.015 mW (ring); ~ 500 mA into battery via pogo |
| OTA | active | DFU | off | off | off | off | off | ~ 5 mA |
| SHIPPING | System OFF; GPIO locked | off | off | off | off | off | off | ~ 0.005 mW |

### 8.2 Wake / sleep conditions

- **Wake from SLEEP**: Touch IC INT (rising edge), IMU INT1 (rising edge; motion), Fuel-gauge ALERT (rising edge; low battery), pogo insertion (MCP73831 STAT GPIO).
- **Wake from CONNECTED_IDLE**: any of the above; or RADIO IRQ (connection event).
- **Sleep from CONNECTED_IDLE**: 5 minutes of no events (configurable via RR07).
- **Sleep from IDLE**: 30 seconds of no events.

The power manager's decisions are based on a **policy** that is itself part of the configuration blob (RR07). The V1 default policy is the table above.

---

## 9. Haptic architecture

The haptic manager is a single FIFO with arbitration rules.

### 9.1 Canonical patterns

The haptic manager implements the 10 canonical patterns from `protocol/ring-gatt-spec.yaml` §"haptic_pattern_table":

| haptic_id | Name | Duration | Trigger source |
| --- | --- | --- | --- |
| 0x00 | NONE | 0 ms | (reserved) |
| 0x01 | ONE_SHORT_PULSE | 80 ms | Pairing success, command accepted |
| 0x02 | TWO_SHORT_PULSES | 240 ms | Command complete |
| 0x03 | THREE_SHORT_PULSES | 360 ms | Low battery |
| 0x04 | LONG_PULSE | 400 ms | Error |
| 0x05 | INCREASING_RAMP | 500 ms | Scroll forward |
| 0x06 | DECREASING_RAMP | 500 ms | Scroll backward |
| 0x07 | DOUBLE_TAP_TICK | 120 ms | Discrete UI selection |
| 0x08 | BONDED | 200 ms | Pairing successful |
| 0x09 | UNBONDED | 200 ms | Pairing lost / factory reset |

The actual waveforms are pre-loaded into the DRV2605L's RAM during boot from a fixed ROM library table. The pattern IDs map directly to DRV2605L waveform slots 1..10.

### 9.2 Priority / arbitration

- Haptic requests have no priority in V1; they are FIFO.
- However, the haptic manager **replaces** the in-flight haptic if a new request arrives within 100 ms (per `protocol/ring-gatt-spec.yaml` §"Haptic Request"). The DRV2605L supports mid-stream cancellation via the GO bit.
- If the FIFO has more than 3 pending requests, the oldest is dropped (with a fault counter increment) — this prevents an infinite haptic loop if the central misbehaves.

### 9.3 Cancellation

- The haptic manager can cancel an in-flight haptic on any of:
  - RR05 write within 100 ms of the previous (the new request replaces the old).
  - Battery SoC < 5 % (the haptic manager refuses to start a new pulse; an error haptic is queued if the SoC is critical).
  - DRV2605L fault (over-current, under-voltage, over-temperature; per the DRV2605L datasheet).

### 9.4 Queueing

- The FIFO holds up to 4 entries. Each entry is `{ haptic_id, intensity, deadline_ms }`.
- The haptic manager drains the FIFO via a Zephyr `k_work` scheduled by the BLE worker on each RR05 write.
- The DRV2605L is on the shared I2C bus; the haptic manager acquires the bus via the Zephyr I2C API and respects the bus's arbitration. The haptic is the lowest-priority I2C consumer; sensor reads always preempt.

---

## 10. Error handling and diagnostics

### 10.1 Sensor failures

- Each sensor driver returns one of: `SM_OK`, `SM_ERR_BUS`, `SM_ERR_TIMEOUT`, `SM_ERR_CRC`, `SM_ERR_FW`.
- The sensor manager counts failures per sensor. If a sensor's failure count exceeds 10 within 60 s, the sensor is disabled and a fault is emitted:
  - The fault counter `fault_count_<sensor>` is incremented (uint16, persistent in flash).
  - A `TEST_DIAGNOSTIC` gesture event is emitted with a payload describing the fault.
  - The BLE worker notifies RR03 with `charging_state = 0x03` (fault) and a fault code in the reserved bits. (TBD: this re-uses RR03 in a way that the GATT spec doesn't explicitly define; see §14.)

### 10.2 BLE failures

- The BLE host stack handles most BLE errors internally. The application layer sees only the high-level connection-state transitions.
- If the BLE stack reports an unrecoverable error (e.g. memory exhaustion), the power manager initiates a soft reboot.

### 10.3 Queue overflow

- See §6.2. Every drop is counted. The drop counters are exposed via the diagnostic CLI (not via a GATT characteristic; V1 does not expose them).

### 10.4 Invalid configuration

- The configuration manager validates every RR07 write. An invalid blob returns `ERR_CONFIG_INVALID` (0x81; per `protocol/ring-gatt-spec.yaml` §"error_handling") and is not persisted.

### 10.5 Watchdog / recovery

- A Zephyr `wdt` is enabled with a 30-second timeout. The app worker pings the watchdog every 10 seconds. If the app worker is starved (e.g. by a deadlock in the BLE worker), the watchdog fires and the nRF54L15 reboots.
- A second, independent watchdog (`wdt1`) is reserved for the BLE worker; it pings every 5 seconds and reboots if starved.
- The reboot reason is stored in the nRF54L15's non-volatile memory (a dedicated 16-byte register; GPIO-reset on factory reset).

### 10.6 Persistent fault counters

- `fault_count_touch`, `fault_count_imu`, `fault_count_temp`, `fault_count_fg`, `fault_count_haptic`, `fault_count_ble`, `fault_count_wdt` are uint16 counters stored in flash (1 sector; 4 KB; wear-levelled via Zephyr settings).
- The counters are exposed via the diagnostic CLI; they are NOT exposed via GATT in V1.
- Factory reset clears all fault counters.

---

## 11. Testability

The firmware is structured so that every layer above the hardware / board layer is host-testable on a POSIX machine.

### 11.1 Dependency boundaries

- The portable sensor manager, gesture engine, BLE service, haptic manager, configuration manager, and power manager are all **pure C** with no Zephyr dependencies in their headers. They are linked into the host test binary directly.
- Zephyr dependencies are injected via function pointers (the `sm_port_t` table; the `haptic_port_t` table; etc.). The host-side test provides a POSIX implementation; the on-target build provides the Zephyr implementation.
- The sensor drivers are Zephyr-only (they use the Zephyr I2C API); they are tested on-target via Ztest, not host.

### 11.2 Mockable sensor interfaces

- The `sm_port_t` table includes `sm_port_now_us()`, `sm_port_get_imu_sample()`, `sm_port_get_touch_event()`, etc. Host-side tests can drive these to inject synthetic events.
- The gesture engine consumes from `sm_port_t`. It does not consume directly from the IQS127D or BMI270 drivers.

### 11.3 Deterministic gesture testing

- The gesture state machine is a static const table. Every transition is enumerated in a test fixture.
- The host-side tests can replay a recorded sequence of touch + IMU events and assert the produced gesture vocabulary.
- The fixture includes all edge cases: double-tap within the window, long-press at the threshold, swipe direction reversals, rotation + simultaneous touch (mutually exclusive), etc.

### 11.4 Host-side unit testing

- The host-side test suite is `ctest` (per the Digital Twin pattern; per `research/smart-ring-landscape.md` §5).
- The suite compiles with `-DSM_SANITIZERS=ON` to enable ASan + UBSan + TSan. There is a separate `build-san` target that links against the sanitised runtime.
- The suite has ~ 100 test cases across 4 suites (sensor manager, gesture engine, configuration manager, drop counter). This is more than the Digital Twin's 43 cases (per `research/smart-ring-landscape.md` §5) because V1 has more sensors and more gesture vocabulary.

### 11.5 Zephyr / Ztest integration

- On-target tests run under Zephyr's `native_sim` (the x86 POSIX simulator) and on the actual nRF54L15 hardware.
- The on-target tests cover the sensor drivers, the Zephyr PM integration, the BLE host callbacks, and the OTA flow.
- The on-target tests are NOT a substitute for the host-side tests; they verify the hardware integration, not the algorithm correctness.

### 11.6 ThreadSanitizer where applicable

- The host-side `ctest --tsan` build runs the multi-threaded stress test (4 threads: sensor worker, BLE worker, app worker, drop-counter monitor). TSan reports data races; the test must be race-free.
- The on-target build does NOT use TSan (TSan adds ~ 5x memory overhead; not feasible on the nRF54L15's 256 KB RAM).

---

## 12. Memory / CPU constraints

### 12.1 Static buffers (no dynamic allocation in real-time paths)

| Buffer | Size | Where | Why |
| --- | --- | --- | --- |
| IMU ring buffer | 100 samples × 32 bytes = 3.2 KB | Static array | 2 seconds at 50 Hz; matches the gesture-engine window |
| Touch event ring buffer | 32 events × 16 bytes = 512 B | Static array | 0.32 s at 100 Hz; matches the swipe commit timer |
| Temperature sample buffer | 8 samples × 8 bytes = 64 B | Static array | 8 s at 1 Hz; matches the wear-state stillness window |
| Fuel-gauge alert buffer | 4 entries × 8 bytes = 32 B | Static array | Holds the last 4 alerts |
| Gesture event queue | 8 entries × 8 bytes = 64 B | Static array | 8 pending gestures; backed by the drop counter |
| Haptic request FIFO | 4 entries × 8 bytes = 32 B | Static array | Per §9.4 |
| Configuration blob | 32 bytes | Static array | Matches RR07 |
| Bonding storage | 4 KB | Flash (settings partition) | 2 bonds × 2 KB |
| OTA staging area | 256 KB | Flash (download partition) | Half of the 512 KB application partition; matches the MCUboot requirement |
| Drop counter / fault counter storage | 1 KB | Flash (settings partition) | 14 counters × 4 bytes + headers |

### 12.2 Major RAM consumers (estimate)

| Consumer | Estimate |
| --- | --- |
| Zephyr kernel + BLE host stack | ~ 60 KB |
| Application code (rodata + .text) | ~ 80 KB |
| Static buffers (above) | ~ 8 KB |
| BLE GATT database | ~ 4 KB |
| Zephyr PM + drivers | ~ 10 KB |
| Headroom | ~ 90 KB |
| **Total of 256 KB RAM** | ~ 252 KB |

The estimate is conservative. The headroom is reserved for V2 features (PPG streaming, on-device logging).

### 12.3 Timing-critical paths

The following paths are bounded by a deadline. A missed deadline increments a fault counter but does NOT cause a crash.

| Path | Deadline | Worst-case measured | Action on miss |
| --- | --- | --- | --- |
| Touch INT → gesture engine tick | 5 ms | (TBD on hardware) | Drop the touch event; increment drop_count_touch |
| IMU INT1 → IMU FIFO drain | 10 ms | (TBD) | Drop the IMU samples; increment drop_count_imu |
| Gesture state machine tick | 5 ms after any input | (TBD) | Re-schedule |
| Gesture → RR01 notify | 50 ms | (TBD) | Drop the gesture; increment drop_count_gesture; central will see a sequence gap |
| RR05 write → LRA drive begins | 15 ms | (TBD) | Drop the haptic; haptic manager increments fault_count_haptic |
| Watchdog ping | 10 s (app), 5 s (BLE) | (deterministic) | Reboot |

---

## 13. Architecture diagram (Mermaid)

```mermaid
flowchart TB
    subgraph App["Application (main / OTA / factory / diag)"]
        A[main]
    end

    subgraph Config["Configuration manager (RR07 TLV)"]
        C[cfg_*]
    end

    subgraph Gesture["Gesture engine + wear-state manager"]
        G[gesture_state_machine]
        W[wear_state]
    end

    subgraph BLE["BLE / GATT service"]
        B[bt_gatt_service]
    end

    subgraph Haptic["Haptic manager (DRV2605L FIFO)"]
        H[haptic_manager]
    end

    subgraph Power["Power manager (rail gating + state machine)"]
        P[power_state_machine]
    end

    subgraph SM["Portable sensor manager (ring buffers + drop counter)"]
        S[sm_*]
    end

    subgraph Drivers["Sensor drivers (I2C)"]
        D1[drv_iqs127d]
        D2[drv_bmi270]
        D3[drv_tmp117]
        D4[drv_max17048]
        D5[drv_drv2605l]
        D6[drv_max86140 (V2)]
    end

    subgraph HW["Hardware / board (Zephyr devicetree + HAL)"]
        HW1[nRF54L15 WLCSP]
        HW2[MCUboot]
    end

    A --> Config
    A --> BLE
    A --> Power
    Config --> Gesture
    Gesture --> SM
    Gesture --> BLE
    SM --> Drivers
    SM --> Power
    BLE --> SM
    Haptic --> Drivers
    Drivers --> HW1
    HW2 --> HW1

    ISR_TOUCH((touch INT)) -.-> D1
    ISR_IMU((IMU INT1/INT2)) -.-> D2
    ISR_TEMP((temp ALERT)) -.-> D3
    ISR_FG((fuel-gauge ALERT)) -.-> D4
    ISR_RADIO((RADIO IRQ)) -.-> BLE
    ISR_RTC((RTC compare)) -.-> SM
```

---

## 14. Explicit TBDs

These are unresolved by this architecture document. They are preserved here so that downstream artifacts (PCB, schematic, mechanical, packaging) can resolve them in order.

### 14.1 Hardware-dependent (to be resolved when the schematic exists)

- **nRF54L15 WLCSP-2.5x2.5 mm pin assignments** — TBD. The schematic must define every GPIO and I2C assignment. The firmware uses Zephyr devicetree aliases, so the firmware does not need to change when the pin map changes.
- **IQS127D I2C address** — TBD per the IQS127D datasheet (per `electrical/sensor-interface.yaml` §`known_uncertainties`).
- **DRV2605L I2C address** — TBD per the TI datasheet.
- **MAX86140 I2C address (V2)** — TBD.
- **LRA drive current limit** — TBD per the DRV2605L + LRA combination.
- **Touch electrode geometry** — TBD per `mechanical/crown-layout.yaml` (not yet created).
- **Pogo charger geometry + NTC sense** — TBD per `mechanical/pogo-charger-layout.yaml` (not yet created).
- **Antenna keepout interaction with battery + haptic placement** — TBD per `mechanical/inner-band-layout.yaml` (not yet created).
- **Flash partition layout** — TBD; the V1 estimate is 32 KB bootloader + 256 KB application + 16 KB settings + 24 KB storage + 512 KB application slot 2. The actual layout depends on the nRF54L15's flash geometry.

### 14.2 Architectural (decisions deferred to a later artifact)

- **RR07 TLV tag definitions** — TBD; V1 supports gesture thresholds, haptic defaults, and advertising intervals. More tags are added in V2.
- **The exact sequence of host-side test cases** — TBD; the V1 estimate is ~ 100 cases across 4 suites.
- **The RR03 charging_state encoding** — **resolved 2026-09-05.** RR03 is `8-bit percentage + 2-bit charging_state + 6-bit reserved`. `protocol/ring-gatt-spec.yaml` is authoritative; `electrical/ble-interface.yaml` was reconciled to match. The fault path in §10.1 uses `charging_state = 0x03` which is consistent with this encoding.
- **OTA transport time** — TBD on real hardware.
- **Rotational gesture accuracy** — TBD; requires empirical measurement on a prototype.
- **Wear-state recognition latency** — TBD; the 100 ms debounce + 30 s stillness window are engineering estimates.

---

## 15. References

- `electrical/system-architecture.yaml` — system architecture, power rails, GPIO allocation.
- `electrical/ble-interface.yaml` — BLE architecture, GATT services, security.
- `electrical/sensor-interface.yaml` — I2C topology, GPIO allocation, sensor signal table.
- `electrical/power-tree.yaml` — power rails, decoupling, power path.
- `electrical/power-budget.yaml` — battery life by scenario.
- `protocol/ring-gatt-spec.yaml` — GATT protocol specification (wire-level reference).
- `components/mcu-selection.yaml` — nRF54L15 selection.
- `components/imu-selection.yaml` — BMI270 selection.
- `components/touch-selection.yaml` — IQS127D selection.
- `components/temperature-selection.yaml` — TMP117 selection.
- `components/battery-selection.yaml` — battery selection.
- `components/charger-selection.yaml` — MCP73831 selection.
- `components/haptic-selection.yaml` — DRV2605L + LRA selection.
- `components/antenna-selection.yaml` — Johanson 2450AT18B100 selection.
- `components/ppg-selection.yaml` — MAX86140 selection (V2).
- `research/even-r1-reference.md` — Even openCFW patterns.
- `research/reference-comparison.md` — comparative study.
- `research/license-audit.md` — license audit.
- `research/smart-ring-landscape.md` — reference architecture notes.
- Bluetooth Core Specification 5.4 — GATT, GAP, security.
- Zephyr Project documentation — PM, work queues, drivers.
- Nordic nRF Connect SDK documentation — nRF54L15 HAL, MCUboot, DFU.
- TI DRV2605L datasheet — haptic driver.
- Bosch BMI270 datasheet — IMU.
- Azoteq IQS127D datasheet — touch IC.
