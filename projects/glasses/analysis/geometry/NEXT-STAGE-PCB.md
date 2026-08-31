# NEXT STAGE - KiCad PCB / Mechanical Co-Design

The mechanical component poses are validated (see `POSE-SOLUTION.md`).
This document captures the constraints and artifacts the PCB design
stage must consume.

## Validated Mechanical Anchors

```
Camera centre            : (167.10, 94.35, 25.50) mm
Forward LED (top)        : (167.10, 91.30, 30.50) mm
Forward LED (bottom)     : (167.10, 91.30, 20.50) mm
Left temple LED (front)  : (148.61, 119.76, 19.43) mm
Left temple LED (rear)   : (149.87, 187.09, 23.12) mm
Right temple LED (front) : (126.98, 122.92, 23.41) mm
Right temple LED (rear)  : (125.65, 188.22, 19.54) mm
```

Lens cavity Y range (validated): **89.10 -> 210.90 mm** (depth 121.81 mm)
Frame X bounds: **156.81 -> 174.54 mm** (width 17.73 mm)
Frame Z bounds: **0.00 -> 42.85 mm** (height 42.85 mm)

## PCB Architecture Artifacts

Three artifacts are now in place:

| Artifact | Path |
|----------|------|
| Schematic architecture (YAML) | `projects/glasses/electronics/schematic-architecture.yaml` |
| KiCad board file (`.kicad_pcb`) | `projects/glasses/electronics/glasses-pcb.kicad_pcb` |
| Board summary (JSON) | `projects/glasses/electronics/glasses-pcb.summary.json` |
| Board outline generator | `projects/glasses/electronics/generate_board_outline.py` |

## Board Outline (Derived)

The PCB outline is **15.73 x 40.85 mm**, sized to fit inside the cavity
X/Z span with 1.0 mm mechanical margins on every edge. The board
origin in the STL frame is **(157.81, 209.30, 1.00) mm** — the board
sits at the cavity back wall (Y = 210.90 minus 1.6 mm thickness), with
its top edge 1.0 mm below the frame's top rim (Z = 42.85) and its
bottom edge 1.0 mm above the frame's bottom rim (Z = 0.00).

### Mounting Holes (4 x M1.6)

Drilled at the four corners of the board, inset 2.0 mm from each edge.
Through-hole pads with 1.7 mm drill (for M1.6 self-tapping screws
into the frame's PCB bosses).

### Module Placeholders (Derived from Schematic)

| Reference | Footprint | Function |
|-----------|-----------|----------|
| J1 | Connector_FPC:FPC_24_P0.5mm | Camera FPC |
| U1 | Module:ESP32-S3-WROOM-1 | Compute |
| J2 | Connector_USB:USB_C_Receptacle | USB-C charging |
| BT1 | Battery_Cell:Lipo_Pouch | Battery (TBD capacity) |
| U2 | Package_TO_SOT_SMD:SOT-23-5 | LiPo charger IC |
| U3 | Package_TO_SOT_SMD:SOT-23-5 | 3V3 LDO |
| U4 | Package_TO_SOT_SMD:SOT-23 | 6-channel LED driver |

J1 (camera FPC) is placed behind the PCB on the cavity side so the
FPC can reach the camera's rear face (Y = 98.60 mm).

## Mechanical Keepouts (from validated geometry)

- **Camera keepout** (sphere): centre (167.10, 94.35, 25.50), radius
  4.5 mm. No traces, vias, or copper pour within this sphere.
- **Camera lens aperture**: centre (167.10, 89.10, 25.50), diameter
  **10.7 mm** (computed for 30 deg half-angle at 20 mm range, with
  1 mm clearance).
- **LED keepouts** (spheres): radius 1.7 mm around each LED centre.
- **FPC keepout**: linear band from (167.10, 98.60, 25.50) to the FPC
  connector at the PCB.
- **Antenna keepout** (TBD): 10 x 10 mm copper-free zone around the
  ESP32-S3 antenna feed, depending on the chosen module variant.

## Cable Routing

- **Camera FPC**: 122 mm minimum length from camera rear (Y=98.60) to
  PCB FPC connector. Min bend radius 1.0 mm.
- **Temple LED wires**: 2 wires per temple (4 wires total) routed
  through the temple interior from the PCB to each LED site. Bundle
  diameter <= 1.5 mm.
- **USB-C cable**: 5 wires from the temple-mounted receptacle to the
  PCB. Bundle diameter <= 1.5 mm.
- **Battery**: 2 wires from PCB to battery cell.

## Required Frame Modifications Before PCB Assembly

1. **Lens cavity hollowing**: front-face material between Y=89.10 and
   Y=210.90 removed within cavity X/Z span.
2. **Three flush apertures** in cavity front wall at (167.10, 25.50),
   (167.10, 30.50), (167.10, 20.50). Diameter per aperture sizing.
3. **Four PCB mounting bosses** at the cavity back wall aligned with
   the four mounting holes in the PCB.
4. **Temple mounting bosses** at the four temple LED positions.
5. **USB-C cutout** on one temple exterior near the hinge (~9 x 3 mm).

## Outstanding Unknowns (TBD from datasheets)

These items must be resolved from manufacturer datasheets before final
CAD. None can be guessed from the available geometry and policy files.

- **ESP32-S3 module variant** (XIAO | WROOM-1 | WROOM-1U | custom)
- **Camera FPC connector** (must match CamThink OV5640 module spec)
- **USB-C receptacle model** (must include USB-C CC pull-down resistors)
- **Battery cell dimensions and capacity** (TBD cell chemistry, capacity)
- **LED driver FET part** (must meet 940 nm LED drive current spec)
- **Window material for the optical apertures** (IR-transmissive at
  940 nm; e.g., coated silicon, germanium, chalcogenide)

## DFM / DFA Checklist

- [ ] PCB material: FR-4 vs flex (flex recommended given 15.73 x 40.85
      mm envelope).
- [ ] Stackup: 2-layer minimum, 4-layer if USB 2.0 HS or MIPI DVP
      impedance control is required.
- [ ] Connector selection: ZIF or board-to-board for camera FPC.
- [ ] Mounting fasteners: M1.6 self-tapping, >= 4 fasteners per PCB.
- [ ] Battery: LiPo with PCM, conformal coating on connectors.
- [ ] Thermal: ESP32-S3 typically no heatsink needed; LED driver
      MOSFETs may need thermal vias.
- [ ] Coating: IR-reflective coating on frame exterior; mask apertures
      during coating.

## Validation Status

The geometry-aware pipeline validates:

- All 7 component poses (1 camera, 2 forward LEDs, 4 temple LEDs)
  against the actual triangle mesh, using oriented bounding box
  (OBB) edge-ray-cast and corner-proximity checks.
- Camera and LED clearances to the frame, temple, and each other.
- Optical cone obstruction (records `aperture_required` for the
  camera's lens aperture).
- LED 60 deg beam cones do not intersect the camera keepout.

The KiCad board file is generated only when overall pose validation
status is PASS. The board outline, mounting holes, and module
positions are all derived from the validated geometry - no coordinate
is guessed.

## Re-Running the Pipeline

```
bash projects/glasses/analysis/geometry/run-pipeline.sh
.venv/bin/python projects/glasses/electronics/generate_board_outline.py
```