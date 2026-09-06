import FreeCAD as App
import Part
import Mesh
import os

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../..")
)

STL = os.path.join(
    ROOT,
    "references/silhouette/wayfarer/ray-ban-frame.stl"
)

OUT = os.path.join(
    ROOT,
    "mechanical/main-frame/proposals/PCB_Channel_Lens_Rim_Proposal.FCStd"
)

DOC_NAME = "PCB_Channel_Lens_Rim_Proposal"

# ============================================================
# PROPOSAL PARAMETERS
# ============================================================

# These are intentionally proposal values.
# They must be validated against the real frame before release.

RIM_REINFORCEMENT = 1.5
PCB_CHANNEL_DEPTH = 1.2
PCB_CLEARANCE = 0.3

# Approximate flex PCB corridor width.
PCB_CHANNEL_WIDTH = 3.5

# Structural material left around the channel.
MIN_STRUCTURAL_WALL = 1.5

# Proposed IR LED pocket dimensions.
LED_DIAMETER = 3.7
LED_DEPTH = 1.7

# Additional lens-perimeter LED count.
# This is a proposal marker, not final placement.
LENS_LED_COUNT_PER_SIDE = 6

# ============================================================
# DOCUMENT
# ============================================================

try:
    App.closeDocument(DOC_NAME)
except:
    pass

doc = App.newDocument(DOC_NAME)

# ============================================================
# REFERENCE FRAME
# ============================================================

if not os.path.exists(STL):
    raise RuntimeError("Reference STL not found: " + STL)

Mesh.insert(STL, doc.Name)

mesh_obj = doc.Objects[-1]
mesh_obj.Label = "REFERENCE — ORIGINAL FRAME STL"
mesh_obj.ViewObject.ShapeColor = (0.75, 0.75, 0.75)
mesh_obj.ViewObject.Transparency = 65

# ============================================================
# REFERENCE COORDINATES FROM CURRENT GEOMETRY PIPELINE
# ============================================================

# Authoritative geometry-derived frame coordinates.
XMIN = 156.8119354248047
XMAX = 174.53895568847656

Y_FRONT_INNER = 89.09657232830386
Y_BACK_INNER = 210.90383800598684

ZMIN = 0.0
ZMAX = 42.846126556396484

NOSE_X = 167.0975311430375
NOSE_Y = 150.0002048605737
NOSE_Z = 25.501723299561572

# ============================================================
# PROPOSAL HELPERS
# ============================================================

def feature(name, shape, color=None, transparency=0):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Shape = shape

    if color:
        obj.ViewObject.ShapeColor = color

    obj.ViewObject.Transparency = transparency
    return obj


def marker_box(name, center, size, color=(1.0, 0.7, 0.0)):
    cx, cy, cz = center
    sx, sy, sz = size

    shape = Part.makeBox(
        sx, sy, sz,
        App.Vector(
            cx - sx / 2,
            cy - sy / 2,
            cz - sz / 2
        )
    )

    return feature(name, shape, color, 35)


def marker_cylinder(name, center, radius, depth, axis=(0,1,0)):
    shape = Part.makeCylinder(
        radius,
        depth,
        App.Vector(*center),
        App.Vector(*axis)
    )

    return feature(
        name,
        shape,
        (1.0, 0.2, 0.2),
        20
    )


# ============================================================
# PCB CHANNEL — PROPOSAL VOLUME
# ============================================================

# The current frame coordinate system places the front-frame
# electronics region along Y, with Z vertical and X lateral.
#
# Rather than cutting the STL, we create translucent proposal
# geometry showing where material should be added/removed.

# Main lower electronics spine.
#
# This intentionally does NOT claim that the entire bounding
# box is usable PCB space.

spine_y_start = 105.0
spine_y_end = 195.0

spine_z = 7.0

spine = Part.makeBox(
    PCB_CHANNEL_WIDTH,
    spine_y_end - spine_y_start,
    PCB_CHANNEL_DEPTH,
    App.Vector(
        NOSE_X - PCB_CHANNEL_WIDTH / 2,
        spine_y_start,
        spine_z
    )
)

feature(
    "PROPOSAL — Continuous PCB Spine",
    spine,
    (0.2, 1.0, 0.3),
    55
)

# ============================================================
# NOSE-BRIDGE PCB REGION
# ============================================================

nose_channel = Part.makeBox(
    PCB_CHANNEL_WIDTH + 2.0,
    18.0,
    PCB_CHANNEL_DEPTH,
    App.Vector(
        NOSE_X - (PCB_CHANNEL_WIDTH + 2.0) / 2,
        NOSE_Y - 9.0,
        spine_z
    )
)

feature(
    "PROPOSAL — Nose Bridge PCB Transition",
    nose_channel,
    (0.2, 0.8, 1.0),
    45
)

# ============================================================
# LENS-RIM REINFORCEMENT ZONE
# ============================================================

# A proposal envelope around the lower lens-holder region.
# It is deliberately shown as additive geometry rather than
# automatically fused to the reference mesh.

lens_rim_height = 5.0

left_rim = Part.makeBox(
    5.0,
    70.0,
    lens_rim_height,
    App.Vector(
        XMIN,
        115.0,
        0.0
    )
)

right_rim = Part.makeBox(
    5.0,
    70.0,
    lens_rim_height,
    App.Vector(
        XMAX - 5.0,
        115.0,
        0.0
    )
)

feature(
    "PROPOSAL — Left Thickened Lens Rim",
    left_rim,
    (0.9, 0.6, 0.1),
    65
)

feature(
    "PROPOSAL — Right Thickened Lens Rim",
    right_rim,
    (0.9, 0.6, 0.1),
    65
)

# ============================================================
# LED POCKET MARKERS
# ============================================================

# Two existing forward LED locations.
forward_leds = [
    (167.10, 91.30, 30.50),
    (167.10, 91.30, 20.50),
]

for i, p in enumerate(forward_leds, 1):
    marker_cylinder(
        "EXISTING FORWARD LED %02d" % i,
        p,
        LED_DIAMETER / 2,
        LED_DEPTH
    )

# ============================================================
# ADDITIONAL LENS-PERIMETER LED PROPOSALS
# ============================================================

# These are deliberately distributed along the lower/outer
# lens-holder zone. They are reference markers only.
#
# We keep them away from the known camera region and bridge.

extra_leds = []

for i in range(LENS_LED_COUNT_PER_SIDE):

    t = i / max(1, LENS_LED_COUNT_PER_SIDE - 1)

    y = 112.0 + t * 76.0

    # Slight Z progression gives us a lens-rim-following
    # proposal rather than a rigid rectangular LED array.
    z = 10.0 + 2.5 * (1.0 - abs(2.0*t - 1.0))

    extra_leds.append(
        ("LEFT LENS LED %02d" % (i + 1),
         (XMIN + 3.0, y, z))
    )

    extra_leds.append(
        ("RIGHT LENS LED %02d" % (i + 1),
         (XMAX - 3.0, y, z))
    )

for name, p in extra_leds:
    marker_cylinder(
        "PROPOSAL — " + name,
        p,
        LED_DIAMETER / 2,
        LED_DEPTH
    )

# ============================================================
# PCB KEEP-OUT / CAMERA REGION
# ============================================================

camera_keepout = Part.makeSphere(
    4.5,
    App.Vector(
        167.10,
        94.35,
        25.50
    )
)

feature(
    "KEEP-OUT — CAMERA",
    camera_keepout,
    (1.0, 0.0, 0.0),
    75
)

# Camera aperture marker.
aperture = Part.makeCylinder(
    10.7 / 2,
    2.0,
    App.Vector(
        167.10,
        89.0966,
        25.50
    ),
    App.Vector(0, 1, 0)
)

feature(
    "KEEP-OUT — CAMERA APERTURE",
    aperture,
    (1.0, 0.0, 0.0),
    60
)

# ============================================================
# STRUCTURAL WALL MARKERS
# ============================================================

wall_marker = Part.makeBox(
    MIN_STRUCTURAL_WALL,
    spine_y_end - spine_y_start,
    5.0,
    App.Vector(
        NOSE_X - PCB_CHANNEL_WIDTH / 2 - MIN_STRUCTURAL_WALL,
        spine_y_start,
        spine_z
    )
)

feature(
    "PROPOSAL — Minimum Structural Wall",
    wall_marker,
    (0.8, 0.8, 0.8),
    75
)

# ============================================================
# DESIGN NOTES
# ============================================================

notes = doc.addObject("App::FeaturePython", "Design_Proposal_Notes")

notes.addProperty(
    "App::PropertyString",
    "Architecture",
    "Proposal"
)
notes.Architecture = (
    "Continuous flexible PCB channel through lower front frame"
)

notes.addProperty(
    "App::PropertyLength",
    "LensRimReinforcement",
    "Proposal"
)
notes.LensRimReinforcement = RIM_REINFORCEMENT

notes.addProperty(
    "App::PropertyLength",
    "PCBChannelDepth",
    "Proposal"
)
notes.PCBChannelDepth = PCB_CHANNEL_DEPTH

notes.addProperty(
    "App::PropertyLength",
    "PCBChannelWidth",
    "Proposal"
)
notes.PCBChannelWidth = PCB_CHANNEL_WIDTH

notes.addProperty(
    "App::PropertyLength",
    "MinimumStructuralWall",
    "Proposal"
)
notes.MinimumStructuralWall = MIN_STRUCTURAL_WALL

notes.addProperty(
    "App::PropertyString",
    "Status",
    "Proposal"
)
notes.Status = "CONCEPT ONLY — NOT MANUFACTURING VALIDATED"

notes.addProperty(
    "App::PropertyString",
    "ReferenceIntegrity",
    "Proposal"
)
notes.ReferenceIntegrity = (
    "Original reference STL imported unchanged; proposal geometry is separate"
)

# ============================================================
# SAVE
# ============================================================

doc.recompute()

doc.saveAs(OUT)

print()
print("=" * 70)
print("PCB CHANNEL + THICKENED LENS RIM PROPOSAL")
print("=" * 70)
print()
print("Reference STL:")
print(STL)
print()
print("Proposal:")
print(OUT)
print()
print("PCB channel width:       %.2f mm" % PCB_CHANNEL_WIDTH)
print("PCB channel depth:       %.2f mm" % PCB_CHANNEL_DEPTH)
print("Lens rim reinforcement:  %.2f mm" % RIM_REINFORCEMENT)
print("Structural wall target:  %.2f mm" % MIN_STRUCTURAL_WALL)
print("Additional LED markers:  %d" % len(extra_leds))
print()
print("STATUS: CONCEPT ONLY")
print("STATUS: Reference STL was not modified")
print("=" * 70)
