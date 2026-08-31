#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."

echo "============================================================"
echo "GLASSES ENGINEERING AGENT"
echo "============================================================"

echo
echo "Engineering rules:"
echo "  CLAUDE.md"
echo
echo "CAD/KiCad skill:"
echo "  .claude/skills/cad-kicad-engineer/SKILL.md"
echo
echo "Production skill:"
echo "  .claude/skills/production-engineer/SKILL.md"
echo
echo "Mission:"
echo "  projects/glasses/agent/ENGINEERING-MISSION.md"
echo
echo "============================================================"
echo

claude "$@"
