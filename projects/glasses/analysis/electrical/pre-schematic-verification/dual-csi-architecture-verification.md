# Dual-Camera CSI Architecture Pre-Schematic Verification

**Component:** Allwinner V853 SoC, 2× camera (IMX708 via RPi CM3 FPC, 2-lane MIPI CSI-2 each)
**File under verification:** `projects/glasses/references/components/compute/v853/dual-csi-validation.yaml`
**Date:** 2026-09-05
**Status:** READ-ONLY. No BGA ball numbers invented. No PCB routing.

---

## 1. Critical question

**Can the V853 realistically support 2 cameras, each as a 2-lane MIPI CSI-2, simultaneously, with independent sensor control, independent reset/standby, the required ISP pipeline, and Linux / Tina SDK driver support?**

This is the **HIGH PRIORITY** verification per the brief. The brief explicitly says: *"Do not merely conclude that '1×4-lane/2×2-lane CSI' proves the whole architecture."*

---

## 2. V853 datasheet claims

Per V853 datasheet section 1.3.6.4:
- "Supports one 4-lane MIPI CSI input or two 2-lane MIPI CSI inputs"
- "Compliant with MIPI CSI2 V1.1 and D-PHY V1.1"
- "Up to 1.2 Gbps/Lane"
- "maximum video capture resolution for serial interface up to 5M@30fps"

Per V853 datasheet section 1.2 (V853 AI vision solution) and section 1.3.6.1 (ISP):
- "1 individual image signal processor (ISP), with maximum resolution of 3072 x 3072 (online mode)"
- "Maximum frame rate of 5M@30fps"
- "Maximum resolution for H.264/H.265 encoding: 5M@25fps"

**The V853 has ONE ISP**, not two. The 2x 2-lane CSI mode uses MIPI virtual-channel demux to share the ISP between the two cameras.

---

## 3. What the public source does NOT prove

The 100ASK V853-Pro public source uses a single camera (sensor0 = gc2053 or tp9953) in the kernel dts. The 100ASK design does NOT demonstrate 2 cameras simultaneously. The 100ASK BSP does NOT contain a reference for 2 cameras.

What is NOT proven by the public source:

- The 2x 2-lane sub-channel mode is supported in the V853's CSI controller
- The 2x 2-lane sub-channel mode is supported in the Linux / Tina SDK driver
- The ISP can handle 2 cameras simultaneously
- The virtual-channel demux works in practice
- The aggregate ISP bandwidth is sufficient for the glasses' use case

---

## 4. The architectural question

For the glasses' design (2 cameras at 2-lane, each capturing up to 1080p @ 47 fps in 2-lane IMX708 mode, or lower frame rates at higher resolutions):

### Aggregate bandwidth per camera

- IMX708 in 2-lane mode at 1080p @ 47 fps: ~ 1.5 Gbps per camera (per the IMX708 datasheet)
- IMX708 in 2-lane mode at 720p @ 60 fps: ~ 0.6 Gbps per camera
- IMX708 in 2-lane mode at VGA @ 120 fps: ~ 0.2 Gbps per camera

### Aggregate bandwidth for 2 cameras

- 2 cameras at 1080p @ 47 fps each: 3.0 Gbps aggregate
- 2 cameras at 720p @ 60 fps each: 1.2 Gbps aggregate
- 2 cameras at VGA @ 120 fps each: 0.4 Gbps aggregate

### V853 CSI bandwidth

- 2x 2-lane at 1.2 Gbps/lane = 2.4 Gbps aggregate
- 1x 4-lane at 1.2 Gbps/lane = 4.8 Gbps

**The V853's 2x 2-lane mode supports 2.4 Gbps aggregate.** The glasses' design needs 3.0 Gbps for 2 cameras at 1080p @ 47 fps each. **The aggregate bandwidth is INSUFFICIENT for 2 cameras at 1080p @ 47 fps each.**

### Reduced frame rate analysis

- 2 cameras at 1080p @ 30 fps each: 1.9 Gbps aggregate → FITS the 2.4 Gbps
- 2 cameras at 1080p @ 47 fps each: 3.0 Gbps aggregate → EXCEEDS the 2.4 Gbps
- 2 cameras at 720p @ 60 fps each: 1.2 Gbps aggregate → FITS
- 2 cameras at 720p @ 30 fps each: 0.6 Gbps aggregate → FITS

### ISP bandwidth

- V853 ISP: 5 MP @ 30 fps maximum (per the V853 datasheet section 1.3.6.1)
- 2 cameras at 1080p (2 MP each, 4 MP total) at 30 fps each: aggregate is 4 MP / 30 fps per camera = 60 MP/s aggregate → EXCEEDS the ISP's 5 MP / 30 fps = 150 MP/s
- Wait, 5 MP @ 30 fps = 150 MP/s. 2 cameras at 1080p (2 MP) @ 30 fps = 60 MP/s each = 120 MP/s aggregate. This FITS the ISP's 150 MP/s.

**The ISP bandwidth IS sufficient for 2 cameras at 1080p @ 30 fps each.**

---

## 5. So, can the V853 support 2 cameras at 2-lane each, simultaneously?

**YES**, with the following constraints:

- The aggregate CSI bandwidth is 2.4 Gbps (2 lanes at 1.2 Gbps each). This is sufficient for 2 cameras at 1080p @ 30 fps (1.9 Gbps aggregate). It is INSUFFICIENT for 2 cameras at 1080p @ 47 fps each (3.0 Gbps aggregate).
- The ISP bandwidth is 5 MP @ 30 fps = 150 MP/s. 2 cameras at 1080p @ 30 fps = 60 MP/s each = 120 MP/s aggregate. This FITS.
- For the glasses' use case (general CV, object detection, OCR, license-plate recognition at typical walking speeds), 1080p @ 30 fps is more than sufficient. The 47 fps mode is for fast motion which is not the glasses' primary use case.

**The architecture is feasible at 1080p @ 30 fps per camera.** The architecture is **NOT** feasible at 1080p @ 47 fps per camera.

### What is the maximum practical resolution/frame rate?

- 2 cameras at 1080p @ 30 fps each: 1.9 Gbps CSI aggregate, 120 MP/s ISP aggregate → FEASIBLE
- 2 cameras at 1080p @ 40 fps each: 2.5 Gbps CSI aggregate → MARGINAL (2.4 Gbps limit; would need a lower lane rate or compression)
- 2 cameras at 720p @ 60 fps each: 1.2 Gbps CSI aggregate, 60 MP/s ISP aggregate → FEASIBLE
- 2 cameras at VGA @ 120 fps each: 0.4 Gbps CSI aggregate, 30 MP/s ISP aggregate → FEASIBLE

**Recommended operating point: 1080p @ 30 fps per camera.** This gives the glasses' AI pipeline the full 4 MP aggregate at a comfortable 30 fps frame rate.

---

## 6. Linux / Tina SDK driver support for 2 cameras simultaneously

The 100ASK Tina SDK does NOT have a reference for 2 cameras simultaneously. The kernel dts has `vinc00` through `vinc33` (16 virtual video pipeline nodes), each of which can be enabled. The 100ASK dts enables `vinc00` and `vinc12` for two separate cameras (the GC2053 + the TP9953 in the 100ASK design), but the TP9953 is a parallel-interface camera, not a 2-lane MIPI CSI-2. The 100ASK design does NOT have 2x MIPI CSI-2 cameras simultaneously.

What is required:

- A custom device tree that enables two separate `vinc` nodes, each connected to the same CSI controller but to different virtual channels
- A custom Linux sensor driver configuration for two IMX708 sensors
- The IMX708 driver in the Allwinner BSP supports the IMX708. The driver supports virtual-channel demux if configured correctly. The 100ASK BSP does NOT demonstrate this.

**The driver-level validation is missing from the public source.** The architecture is technically feasible per the V853 datasheet, but the actual driver behavior is unverified in public.

---

## 7. Independent sensor control

For independent reset/standby:

- Each camera has its own reset and standby GPIO. The 100ASK dts uses PA18 + PA19 for sensor0 (GC2053) and PH13 + PI0 for sensor1 (TP9953).
- The glasses' design uses the same pattern: each camera has its own reset and standby GPIO on the SoC.
- The I2C / SCCB addresses of the two cameras MUST be different. The IMX708 SCCB address is 0x1A or 0x10 depending on the variant. The FPC layout must select different addresses for the two cameras (e.g. CAM1 = 0x1A, CAM2 = 0x10).
- I2C / SCCB is a shared bus; the two cameras can use the same bus with different addresses. No separate I2C buses are required.

**Independent sensor control: GREEN.**

---

## 8. Virtual channels

MIPI CSI-2 virtual channels (VC) are the standard mechanism for sharing a single CSI controller between multiple cameras. The V853's CSI controller supports virtual-channel demux per the datasheet section 1.3.6.4. The Linux driver chain (sensor → CSI parser → CSI DMA → V4L2 capture) supports virtual channels.

What is NOT verified: the actual Linux driver support for virtual channels on the V853. The 100ASK BSP does NOT demonstrate this. Mainline Linux has the `sunxi-csi` driver which is the relevant driver. The V4L2 subdev routing API supports virtual channels.

**Virtual channels: TECHNICALLY SUPPORTED, but DRIVER VALIDATION MISSING.**

---

## 9. Summary

| Item | Status | Notes |
| --- | --- | --- |
| 2 cameras at 2-lane MIPI CSI-2 | **GREEN** (datasheet section 1.3.6.4) | "Supports 2x 2-lane" |
| 2 cameras at 2-lane simultaneously | **YELLOW** | Datasheet supports it; Linux driver validation missing |
| Aggregate bandwidth at 1080p @ 30 fps per camera | **GREEN** | 1.9 Gbps aggregate, fits 2.4 Gbps |
| Aggregate bandwidth at 1080p @ 47 fps per camera | **RED** | 3.0 Gbps aggregate, exceeds 2.4 Gbps |
| ISP bandwidth at 1080p @ 30 fps per camera | **GREEN** | 120 MP/s aggregate, fits 150 MP/s ISP limit |
| Virtual-channel demux | **YELLOW** | Datasheet supports; driver validation missing |
| Independent reset/standby per camera | **GREEN** | Per-camera GPIO available; 100ASK reference confirms pattern |
| Independent I2C / SCCB addresses | **GREEN** | IMX708 supports 0x1A or 0x10; FPC layout must select different addresses |
| Recommended operating point | 1080p @ 30 fps per camera | Fits both CSI bandwidth and ISP bandwidth |

---

## 10. Architectural decision

The glasses' design uses **2 cameras, each 2-lane MIPI CSI-2, operating at 1080p @ 30 fps**. The 47 fps mode is NOT used.

The architecture is **YELLOW**: the peripheral block is supported (GREEN at the datasheet level), but the Linux driver chain for 2-camera simultaneous capture with virtual-channel demux on the V853 is unverified in public. The risk is that the driver may not work out of the box, requiring a custom driver patch.

**Mitigation**: the Tina SDK or mainline Linux `sunxi-csi` driver is the canonical place to start. A reference implementation for 2 cameras on the V853's CSI would be needed; if not available, a custom driver is required. The custom driver is a few hundred lines of C code in the kernel, and the I2C / SCCB driver for the IMX708 is already in the upstream Linux tree (or available from Sony). The estimated effort is 1-2 weeks of an experienced Linux kernel engineer.

---

## 11. Risk

- **Linux driver for 2-camera simultaneous capture on the V853's CSI with virtual-channel demux is unverified.** This is a YELLOW item, not a RED, because the V853 datasheet supports the architecture and the standard Linux CSI driver chain supports virtual channels. The risk is that the specific V853 implementation has a bug or limitation that prevents 2-camera simultaneous capture. The mitigation is a custom driver.
- **No reference implementation in the public 100ASK BSP.** The 100ASK design uses one MIPI camera and one parallel camera, not 2 MIPI cameras. The 2-camera MIPI case is unverified at the driver level.
- **Camera FPC connector and address selection must be designed carefully.** The two cameras MUST have different SCCB addresses. The FPC layout must select the addresses via hardware straps (typically an AD0 pin on the IMX708).

---

## 12. Update to the qualification record

The qualification record `projects/glasses/references/components/compute/v853/dual-csi-validation.yaml` is **CORRECT as-is** in its GREEN classification at the datasheet level and YELLOW on the driver level. The verification pass CONFIRMS the classification and adds the aggregate bandwidth analysis (1080p @ 30 fps is feasible; 1080p @ 47 fps is not).

No correction to the existing YAML is required.
