#!/bin/bash
# Baut den JT-Konverter extern/jt2glb (TKJT + OCCT der pixi-Umgebung). Optional: nur fuer die Build-Variante mit JT.
# TKJT (Open Cascade, GPL v2+) wird als Fork wwmayer/TKJT nach extern/TKJT geholt (Stand 687cc51 mit JT-10-Lesen,
# Basis mmaenz/TKJT, wie in FreeCAD). Fuer OCCT 8 wird MMgt_TShared ersetzt; tkjt_jt10.patch: eigene JT-10-Korrekturen
# (Move-to-Front, Wertetabelle ohne Vorzeichen, Lag1 fuer Binaerkoordinaten, Netzdekoder ohne Absturz), siehe PLAN 8.32.
# Ohne tbb (NO_JT_MULTITHREADING), zlib vom System, LZMA aus pixi (liblzma-devel); JtToTopoDS (Parasolid) bleibt weg.
# Aufruf: packaging/jt/bauen.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
WURZEL=$PWD
E="$WURZEL/.pixi/envs/default"
STAND=687cc519de
TKJT="$WURZEL/extern/TKJT"
BAU="$WURZEL/extern/bau"
QUELLE=https://github.com/wwmayer/TKJT.git
if [ ! -d "$TKJT" ]; then
  git clone -q "$QUELLE" "$TKJT"
fi
git -C "$TKJT" cat-file -e "$STAND^{commit}" 2>/dev/null || git -C "$TKJT" fetch -q "$QUELLE"
git -C "$TKJT" checkout -q -- . 2>/dev/null || true
git -C "$TKJT" clean -fdq src
git -C "$TKJT" checkout -q "$STAND"
for p in "$WURZEL"/packaging/jt/*.patch; do git -C "$TKJT" apply "$p"; done  # Move-to-Front, Wertetabelle JT 10
grep -rl MMgt_TShared "$TKJT/src" | xargs sed -i.alt 's/MMgt_TShared/Standard_Transient/g'  # OCCT 8
find "$TKJT/src" -name "*.alt" -delete
mkdir -p "$BAU/obj"
CXX=${CXX:-$(command -v clang++ || command -v g++)}
INC=(-I"$E/include/opencascade" -I"$E/include")
for d in "$TKJT"/src/*/; do INC+=(-I"$d"); done
FLAGS=(-std=c++17 -O2 -fPIC -DNO_JT_MULTITHREADING -w)
fehler=0
pids=()
while IFS= read -r f; do  # alle parallel (46 Dateien), Bash 3.2 kennt kein wait -n
  "$CXX" "${FLAGS[@]}" "${INC[@]}" -c "$f" -o "$BAU/obj/$(basename "$f" .cxx).o" &
  pids+=($!)
done < <(find "$TKJT/src" -name "*.cxx" ! -path "*JtToTopoDS*")
for p in "${pids[@]}"; do wait "$p" || fehler=$((fehler + 1)); done
[ "$fehler" -eq 0 ] || { echo "$fehler Dateien nicht uebersetzt"; exit 1; }
RELATIV='@loader_path'
[ "$(uname)" = "Darwin" ] || RELATIV='$ORIGIN'
LIBS=(-lTKernel -lTKMath -lTKG2d -lTKG3d -lTKGeomBase -lTKBRep -lTKTopAlgo -lTKMesh -lTKLCAF -lTKCAF -lTKCDF -lTKVCAF
      -lTKXCAF -lTKService -lTKV3d -lTKDE -lTKXSBase -lTKRWMesh -lTKDEGLTF -lTKBinL -lTKBin -lTKBinXCAF -lz -llzma)
"$CXX" "${FLAGS[@]}" "${INC[@]}" "$WURZEL/packaging/jt/jt2glb.cxx" "$BAU"/obj/*.o -L"$E/lib" "${LIBS[@]}" \
  -Wl,-rpath,"$E/lib" -Wl,-rpath,"$RELATIV" -o "$WURZEL/extern/jt2glb"  # relativ: neben den Bibliotheken der App
echo "Fertig: extern/jt2glb"
