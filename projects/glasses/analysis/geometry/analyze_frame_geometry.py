from pathlib import Path
import json
import numpy as np
from stl import mesh

ROOT = Path(__file__).resolve().parents[4]

FILES = {
    "main_frame":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame.stl",
    "left_temple":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frame-side-left.stl",
    "right_temple":
        ROOT / "projects/glasses/references/silhouette/wayfarer/ray-ban-frameside-right.stl",
}


def load(path):
    m = mesh.Mesh.from_file(str(path))
    vertices = m.vectors.reshape(-1, 3)

    return {
        "triangles": len(m.vectors),
        "vertices": len(vertices),
        "min": vertices.min(axis=0),
        "max": vertices.max(axis=0),
        "size": vertices.max(axis=0) - vertices.min(axis=0),
        "center": (vertices.min(axis=0) + vertices.max(axis=0)) / 2,
    }


print("=" * 70)
print("FRAME GEOMETRY ANALYSIS")
print("=" * 70)

result = {}

for name, path in FILES.items():
    if not path.exists():
        raise FileNotFoundError(path)

    g = load(path)
    result[name] = {
        "file": str(path.relative_to(ROOT)),
        "triangles": g["triangles"],
        "vertices": g["vertices"],
        "bbox_min_mm": g["min"].tolist(),
        "bbox_max_mm": g["max"].tolist(),
        "size_mm": g["size"].tolist(),
        "center_mm": g["center"].tolist(),
    }

    print()
    print(name)
    print("-" * 70)
    print(f"Triangles: {g['triangles']}")
    print(
        "Bounding box: "
        f"{g['size'][0]:.3f} × "
        f"{g['size'][1]:.3f} × "
        f"{g['size'][2]:.3f} mm"
    )
    print(
        "Center: "
        f"({g['center'][0]:.3f}, "
        f"{g['center'][1]:.3f}, "
        f"{g['center'][2]:.3f})"
    )

out = (
    ROOT
    / "projects/glasses/analysis/geometry/"
    "frame-geometry-analysis.json"
)

out.write_text(
    json.dumps(result, indent=2),
    encoding="utf-8",
)

print()
print("=" * 70)
print("FRAME GEOMETRY ANALYSIS: PASS")
print("=" * 70)
print(f"Output: {out.relative_to(ROOT)}")
print("Coordinates remain geometry-derived.")
print("No component coordinates have been guessed.")
print("=" * 70)
