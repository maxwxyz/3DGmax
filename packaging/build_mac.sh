#!/bin/bash
# Baut die portable macOS-App: dist/3DGmax.app und dist/3DGmax-<version>-macOS-<arch>.zip
# Voraussetzung: pixi (https://pixi.sh). Die App laeuft auf Macs mit derselben Prozessorart wie der Bau-Mac.
# Aufruf mit --ohne-tests (oder DG_OHNE_TESTS=1): ohne Testlauf bauen.
set -euo pipefail
cd "$(dirname "$0")/.."
ARCH=$(uname -m)
pixi install
if [ "${1:-}" = "--ohne-tests" ] || [ "${DG_OHNE_TESTS:-0}" = "1" ]; then
  echo "Tests uebersprungen (--ohne-tests)"
else
  pixi run test
fi
rm -rf build/pyinstaller dist/3DGmax dist/3DGmax.app
pixi run bauen
rm -rf dist/3DGmax                                  # nur das .app-Paket weitergeben
codesign --force --deep --sign - dist/3DGmax.app    # Ad-hoc-Signatur (ohne Apple-Entwicklerkonto)
VER=$(pixi run python -c "from programm.version import VERSION; print(VERSION)")
ZIP="dist/3DGmax-${VER}-macOS-${ARCH}.zip"
rm -f "$ZIP"
ditto -c -k --keepParent dist/3DGmax.app "$ZIP"
dist/3DGmax.app/Contents/MacOS/3DGmax --selbsttest
echo "Fertig: dist/3DGmax.app  und  $ZIP"
