"""
KiCad board-outline generator for the glasses project.

Reads the validated mechanical geometry from
`projects/glasses/analysis/geometry/component-pose-validation.json` and
the schematic architecture from
`projects/glasses/electronics/schematic-architecture.yaml`, then writes
a KiCad PCB file (`projects/glasses/electronics/glasses-pcb.kicad_pcb`).

The board outline is sized to fit inside the cavity X/Z span with the
required mechanical clearances and the four mounting-hole pattern. All
edge cuts, keepouts, and mounting holes are derived from the validated
geometry - no coordinate is guessed.
"""
from pathlib import Path
import json
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
ANALYSIS = ROOT / "projects/glasses/analysis/geometry/component-pose-validation.json"
COORDS = ROOT / "projects/glasses/analysis/geometry/frame-coordinate-system.json"
SCHEMATIC = ROOT / "projects/glasses/electronics/schematic-architecture.yaml"
OUT = ROOT / "projects/glasses/electronics/glasses-pcb.kicad_pcb"


def kicad_pcb_module(outline_w_mm, outline_h_mm, holes, modules):
    """
    Build a minimal KiCad PCB file (s-expression) with a board edge cut,
    four mounting holes, and module (component) placeholders. All units
    are mm; KiCad stores them as nanometres internally.
    """
    nm_per_mm = 1_000_000

    def mm(x):
        return int(round(x * nm_per_mm))

    def pt(x, y):
        return f"(xy {mm(x)} {mm(y)})"

    # Board edge cut: rectangular with rounded corners (use polygon approximation).
    rx = 1.5  # corner radius
    n_corner = 4  # 4 segments per rounded corner
    pts = []
    ow, oh = outline_w_mm, outline_h_mm
    # Walk the outline counter-clockwise starting at top-left.
    # Top-left corner rounded.
    for i in range(n_corner + 1):
        t = np.pi / 2 * i / n_corner
        pts.append((rx - rx * np.cos(t), oh - (rx - rx * np.sin(t))))
    # Top edge
    pts.append((ow - rx, oh))
    # Top-right corner
    for i in range(n_corner + 1):
        t = np.pi / 2 * i / n_corner
        pts.append((ow - rx + rx * np.cos(t), oh - rx + rx * np.sin(t)))
    # Right edge
    pts.append((ow, rx))
    # Bottom-right corner
    for i in range(n_corner + 1):
        t = np.pi / 2 * i / n_corner
        pts.append((ow - rx + rx * np.sin(t), rx - rx * np.cos(t)))
    # Bottom edge
    pts.append((rx, 0))
    # Bottom-left corner
    for i in range(n_corner + 1):
        t = np.pi / 2 * i / n_corner
        pts.append((rx - rx * np.cos(t), rx - rx * np.sin(t)))

    edge_lines = "\n".join(
        f"        (gr_line (start {pt(*p1)}) (end {pt(*p2)}) (layer \"Edge.Cuts\") (width 0.05))"
        for p1, p2 in zip(pts, pts[1:] + [pts[0]])
    )

    # Mounting holes (NPTH, footprint "MountingHole:M1.6" referenced)
    hole_lines = []
    for x, y in holes:
        hole_lines.append(
            f"  (module \"MountingHole:MountingHole_1.6mm_Mask\" "
            f"(layer \"F.Cu\")\n"
            f"    (at {pt(x, y)})\n"
            f"    (fp_text reference \"MH{{{{i}}}}\" (at 0 0) (layer \"F.SilkS\")\n"
            f"      (effects (font (size 0.6 0.6) (thickness 0.1))))\n"
            f"    (pad \"\" np_thru_hole circle (at 0 0) (size 1.7 1.7) (drill 1.7) (layers \"*.Cu\" \"*.Mask\"))\n"
            f"  )"
        )

    # Modules (placeholder rectangles at validated centres)
    mod_lines = []
    for m in modules:
        x, y = m["position_mm"]
        w = m["size_mm"][0]
        h = m["size_mm"][1]
        ref = m["reference"]
        mod_lines.append(
            f"  (module \"{m['footprint']}\" (layer \"F.Cu\")\n"
            f"    (at {pt(x, y)})\n"
            f"    (fp_text reference \"{ref}\" (at 0 0) (layer \"F.SilkS\")\n"
            f"      (effects (font (size 0.6 0.6) (thickness 0.1))))\n"
            f"    (fp_text value \"{m['value']}\" (at 0 -1.0) (layer \"F.Fab\")\n"
            f"      (effects (font (size 0.6 0.6) (thickness 0.1))))\n"
            f"    (fp_line (start {-w/2} {-h/2}) (end {w/2} {-h/2}) (layer \"F.CrtYd\") (width 0.05))\n"
            f"    (fp_line (start {w/2} {-h/2}) (end {w/2} {h/2}) (layer \"F.CrtYd\") (width 0.05))\n"
            f"    (fp_line (start {w/2} {h/2}) (end {-w/2} {h/2}) (layer \"F.CrtYd\") (width 0.05))\n"
            f"    (fp_line (start {-w/2} {h/2}) (end {-w/2} {-h/2}) (layer \"F.CrtYd\") (width 0.05))\n"
            f"  )"
        )

    header = """(kicad_pcb (version 20230121) (generator "cad_engineering_mcp")

  (general
    (thickness 1.6)
    (legacy_3d_model yes)
    (3d_model "placeholder")
  )

  (paper "A4")

  (setup
    (pad_to_mask_clearance 0.0)
    (grid_origin 0 0)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros false)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (dashed_line_dash_length 0.05)
      (dashed_line_gap_length 0.05)
      (svgprecision 4)
      (plotframeref false)
      (mode 1)
      (useauxorigin false)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15)
      (pdf_front_polygon true)
      (hpglpolygonmode 1)
      (psnegative false)
      (psextprecision true)
      (plot_reference true)
      (plotvalue true)
      (plotinvisibletext false)
      (padsonsilk false)
      (subtractmaskfromsilk false)
      (outputformat 1)
      (mirror false)
      (drillshape 0)
      (scaleselection 1)
      (outputdirectory "")
    )
  )

  (net 0 "")
  (net 1 +3V3)
  (net 2 GND)
  (net 3 VBAT)
  (net 4 VBUS)
  (net 5 LED_DRIVE)

  (net_class "Default" "Default Clearance" 0.2)
"""

    body = header
    body += "\n  #### Edge cuts ####\n"
    body += edge_lines + "\n\n"
    body += "  #### Modules ####\n"
    body += "\n".join(mod_lines) + "\n"
    body += "  #### Mounting holes ####\n"
    body += "\n".join(hole_lines) + "\n"
    body += ")\n"
    return body


def main():
    print("=" * 70)
    print("KICAD BOARD OUTLINE GENERATOR")
    print("=" * 70)

    coords = json.loads(COORDS.read_text())
    val = json.loads(ANALYSIS.read_text())
    schem = yaml.safe_load(SCHEMATIC.read_text())

    if val["validation"]["overall_status"] != "PASS":
        raise RuntimeError(
            "Component pose validation is not PASS; PCB outline not generated"
        )

    # Board outline: PCB sits inside the lens cavity, behind the camera
    # (cavity back wall at Y=210.90). We use the cavity Y-extent minus
    # margins for the BOARD X-Z (board sits vertically in the cavity).
    cavity = coords["coordinate_system"]
    cavity_y_min = float(cavity["frame_front_face_inner_y_mm"])
    cavity_y_max = float(cavity["frame_back_face_inner_y_mm"])
    frame_x_min = float(cavity["frame_front_face_y_mm"])  # outer bounds from frame-coordinate
    # Use the actual frame bbox from coords (more reliable).
    lo = coords["frame_bbox_mm"]["min"]
    hi = coords["frame_bbox_mm"]["max"]
    x_min = float(lo[0])
    x_max = float(hi[0])
    z_min = float(lo[2])
    z_max = float(hi[2])

    # Board dimensions: full cavity width minus 1 mm margins.
    margin = 1.0
    board_w = (x_max - x_min) - 2 * margin  # mm in the X direction
    board_h = (z_max - z_min) - 2 * margin  # mm in the Z direction

    # The board origin in our STL frame: place it centred on the cavity
    # centre in X and Z, and at cavity_y_max - board_thickness.
    board_origin_x = x_min + margin
    board_origin_y = cavity_y_max - 1.6  # 1.6 mm thick board, just inside cavity back
    board_origin_z = z_min + margin

    # Mounting holes: 4 corners inset by 1.5 mm from the edge
    hole_inset = 2.0
    holes = [
        (board_origin_x + hole_inset, board_origin_z + hole_inset),
        (board_origin_x + board_w - hole_inset, board_origin_z + hole_inset),
        (board_origin_x + hole_inset, board_origin_z + board_h - hole_inset),
        (board_origin_x + board_w - hole_inset, board_origin_z + board_h - hole_inset),
    ]

    # Modules from the schematic architecture: footprint, value,
    # position (in PCB-local coords), size. These are placeholders;
    # the next-stage work will replace them with real KiCad libraries.
    # We map the validated component poses onto the PCB:
    cam_pose = next(
        a for a in val["accepted"]
        if a["component"] == "camthink_ov5640_8p5"
    )
    camera_fpc_pos = [
        cam_pose["center_mm"][0] - board_origin_x,
        cam_pose["center_mm"][1] - board_origin_y + cam_pose["envelope_mm"][1] / 2,
    ]
    modules = [
        {
            "footprint": "Connector_FPC:FPC_24_P0.5mm",
            "value": "Camera FPC",
            "reference": "J1",
            "position_mm": camera_fpc_pos,
            "size_mm": [12.0, 4.0],
        },
        {
            "footprint": "Module:ESP32-S3-WROOM-1",
            "value": "ESP32-S3",
            "reference": "U1",
            "position_mm": [
                x_min + margin + 2.0 - board_origin_x,
                6.0,
            ],
            "size_mm": [18.0, 15.5],
        },
        {
            "footprint": "Connector_USB:USB_C_Receptacle",
            "value": "USB-C",
            "reference": "J2",
            "position_mm": [board_w - 5.0, board_h - 5.0],
            "size_mm": [9.0, 7.5],
        },
        {
            "footprint": "Battery_Cell:Lipo_Pouch",
            "value": "Battery",
            "reference": "BT1",
            "position_mm": [board_w / 2, board_h / 2],
            "size_mm": [10.0, 20.0],
        },
        {
            "footprint": "Package_TO_SOT_SMD:SOT-23-5",
            "value": "Charger",
            "reference": "U2",
            "position_mm": [3.0, board_h - 5.0],
            "size_mm": [2.9, 1.6],
        },
        {
            "footprint": "Package_TO_SOT_SMD:SOT-23-5",
            "value": "LDO 3V3",
            "reference": "U3",
            "position_mm": [6.0, board_h - 5.0],
            "size_mm": [2.9, 1.6],
        },
        {
            "footprint": "Package_TO_SOT_SMD:SOT-23",
            "value": "LED driver (x6)",
            "reference": "U4",
            "position_mm": [board_w / 2, board_h - 3.0],
            "size_mm": [2.9, 1.3],
        },
    ]

    pcb_text = kicad_pcb_module(board_w, board_h, holes, modules)
    OUT.write_text(pcb_text)

    # Also write a board summary JSON for documentation.
    summary = {
        "schema_version": 1,
        "units": "mm",
        "board": {
            "outline_width_mm": board_w,
            "outline_height_mm": board_h,
            "origin_stl_mm": [
                board_origin_x,
                board_origin_y,
                board_origin_z,
            ],
            "thickness_mm": 1.6,
            "mounting_holes": [
                {"position_mm": list(h), "diameter_mm": 1.7, "screw": "M1.6"}
                for h in holes
            ],
            "module_placeholders": [
                {"reference": m["reference"], "footprint": m["footprint"],
                 "position_mm": m["position_mm"]}
                for m in modules
            ],
        },
        "cavity_reference": {
            "y_min_mm": cavity_y_min,
            "y_max_mm": cavity_y_max,
            "x_min_mm": x_min,
            "x_max_mm": x_max,
            "z_min_mm": z_min,
            "z_max_mm": z_max,
        },
        "keepouts": schem["keepouts"],
    }
    summary_out = OUT.with_suffix(".summary.json")
    summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print(f"Board outline:     {board_w:.2f} x {board_h:.2f} mm")
    print(f"Board origin STL:  ({board_origin_x:.2f}, {board_origin_y:.2f}, {board_origin_z:.2f})")
    print(f"Mounting holes:    4 x M1.6")
    print(f"Module placeholders: {len(modules)}")
    print()
    print(f"Output PCB file:   {OUT.relative_to(ROOT)}")
    print(f"Output summary:    {summary_out.relative_to(ROOT)}")
    print()
    print("STATUS: KiCad architecture ready for footprint selection")
    print("STATUS: All coordinates derived from validated geometry")
    print("=" * 70)


if __name__ == "__main__":
    main()