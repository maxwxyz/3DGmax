#!/bin/bash
# Baut die portable Linux-App: dist/3DGmax/ und dist/3DGmax-<version>-Linux-<arch>.tar.gz
# Voraussetzung: pixi (https://pixi.sh). Aufruf mit --ohne-tests (oder DG_OHNE_TESTS=1): ohne Testlauf.
set -euo pipefail
cd "$(dirname "$0")/.."
ARCH=$(uname -m)
pixi install
if [ "${1:-}" = "--ohne-tests" ] || [ "${DG_OHNE_TESTS:-0}" = "1" ]; then
  echo "Tests uebersprungen (--ohne-tests)"
else
  pixi run test
fi
rm -rf build/pyinstaller dist/3DGmax
pixi run bauen
VER=$(pixi run python -c "from programm.version import VERSION; print(VERSION)")
TAR="dist/3DGmax-${VER}-Linux-${ARCH}.tar.gz"
tar -czf "$TAR" -C dist 3DGmax
QT_QPA_PLATFORM=offscreen dist/3DGmax/3DGmax --selbsttest
echo "Fertig: dist/3DGmax/  und  $TAR"
