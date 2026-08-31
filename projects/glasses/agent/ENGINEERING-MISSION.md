# GLASSES ENGINEERING AGENT MISSION

The agent is responsible for taking the glasses project from geometry
specification to validated mechanical/electrical architecture.

CURRENT HARDWARE:

Camera:
1 × CamThink OV5640
8.5 × 8.5 × 6.5 mm
center nose bridge
forward

IR:
2 × forward VSMA1094750X02
4 × temple VSMA1094750X02

Compute:
ESP32-S3

Charging:
USB-C

PCB:
custom

FRAME:
Wayfarer reference geometry.

CURRENT OBJECTIVE:

Solve the actual component poses.

Required outputs:

1. Camera pose
2. Forward LED poses
3. Temple LED poses
4. Camera keepout
5. LED keepouts
6. Optical windows
7. Collision validation
8. Mechanical mounting interfaces
9. PCB/mechanical interface requirements

Do not accept a pose based solely on bounding-box overlap.

After mechanical placement is solved:

10. derive PCB envelope
11. identify PCB component placement constraints
12. identify connector locations
13. identify camera interface
14. identify LED driver interface
15. prepare KiCad architecture
16. validate mechanical/electrical integration

The agent must modify scripts when existing validators are inadequate.

The agent must not weaken constraints simply to obtain PASS.
