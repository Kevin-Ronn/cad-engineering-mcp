#!/usr/bin/env bash
# Canonical end-to-end pipeline for the glasses component-pose solver.
# Runs the three geometry-aware stages in dependency order:
#   1. derive_frame_geometry.py  -> frame-coordinate-system.json
#   2. generate_component_candidates.py -> component-pose-candidates.json
#   3. validate_component_poses.py -> component-pose-validation.json
set -euo pipefail
cd "$(dirname "$0")/../../../../"

PY="${PYTHON:-./.venv/bin/python}"

echo "============================================================"
echo "GLASSES POSE PIPELINE (geometry-aware)"
echo "============================================================"

echo
echo "[1/3] Deriving frame coordinate system..."
"$PY" projects/glasses/analysis/geometry/derive_frame_geometry.py

echo
echo "[2/3] Generating geometry-derived component candidates..."
"$PY" projects/glasses/analysis/geometry/generate_component_candidates.py

echo
echo "[3/3] Validating candidates with trimesh proximity + cavity checks..."
"$PY" projects/glasses/analysis/geometry/validate_component_poses.py

echo
echo "============================================================"
echo "PIPELINE COMPLETE"
echo "============================================================"
echo "Artifacts:"
echo "  projects/glasses/analysis/geometry/frame-coordinate-system.json"
echo "  projects/glasses/analysis/geometry/component-pose-candidates.json"
echo "  projects/glasses/analysis/geometry/component-pose-validation.json"
echo "  projects/glasses/analysis/geometry/POSE-SOLUTION.md"