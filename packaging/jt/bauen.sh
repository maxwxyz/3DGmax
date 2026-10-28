#!/bin/bash
# Baut den JT-Konverter extern/jt2glb (TKJT + OCCT der pixi-Umgebung); Einzelheiten in packaging/jt/bauen.py.
# Aufruf: packaging/jt/bauen.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
pixi run python packaging/jt/bauen.py
