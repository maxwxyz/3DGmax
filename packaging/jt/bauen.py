"""JT-Konverter extern/jt2glb bauen (TKJT + OCCT der pixi-Umgebung) - macOS, Linux und Windows.

TKJT (Open Cascade, GPL v2+) als Fork wwmayer/TKJT (JT-10-Lesen, Basis von FreeCADs JT-Import) nach extern/TKJT,
Stand STAND; packaging/jt/*.patch mit eigenen JT-10-Korrekturen; fuer OCCT 8 wird MMgt_TShared ersetzt. Ohne tbb
(NO_JT_MULTITHREADING); zlib und LZMA aus der pixi-Umgebung (liblzma-devel); JtToTopoDS (Parasolid) bleibt weg.
Compiler: clang++ oder g++ (macOS/Linux), MSVC cl/link unter Windows (Entwicklerumgebung noetig, in GitHub Actions
ilammy/msvc-dev-cmd). Aufruf: pixi run python packaging/jt/bauen.py
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

WURZEL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUELLE = "https://github.com/wwmayer/TKJT.git"
STAND = "687cc519de"
TKJT = os.path.join(WURZEL, "extern", "TKJT")
BAU = os.path.join(WURZEL, "extern", "bau")
WINDOWS = sys.platform == "win32"
UMGEBUNG = sys.prefix  # pixi-Umgebung (pixi run python)
INCLUDE = os.path.join(UMGEBUNG, "Library", "include") if WINDOWS else os.path.join(UMGEBUNG, "include")
LIB = os.path.join(UMGEBUNG, "Library", "lib") if WINDOWS else os.path.join(UMGEBUNG, "lib")
OCCT_LIBS = ["TKernel", "TKMath", "TKG2d", "TKG3d", "TKGeomBase", "TKBRep", "TKTopAlgo", "TKMesh", "TKLCAF", "TKCAF",
             "TKCDF", "TKVCAF", "TKXCAF", "TKService", "TKV3d", "TKDE", "TKXSBase", "TKRWMesh", "TKDEGLTF", "TKBinL",
             "TKBin", "TKBinXCAF"]


def git(*args):
    subprocess.run(["git", "-C", TKJT, *args], check=True)


def quellen_holen():
    if not os.path.isdir(TKJT):
        subprocess.run(["git", "clone", "-q", QUELLE, TKJT], check=True)
    if subprocess.run(["git", "-C", TKJT, "cat-file", "-e", STAND + "^{commit}"], capture_output=True).returncode:
        git("fetch", "-q", QUELLE)
    git("checkout", "-q", "--", ".")
    git("clean", "-fdq", "src")
    git("checkout", "-q", STAND)
    for p in sorted(glob.glob(os.path.join(WURZEL, "packaging", "jt", "*.patch"))):
        git("apply", "--whitespace=nowarn", p)
    for datei in glob.glob(os.path.join(TKJT, "src", "**", "*.?xx"), recursive=True):
        with open(datei, encoding="utf-8", errors="surrogateescape") as f:
            text = f.read()
        if "MMgt_TShared" in text:  # OCCT 8
            with open(datei, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(text.replace("MMgt_TShared", "Standard_Transient"))


def includes() -> list[str]:
    ordner = [os.path.join(INCLUDE, "opencascade"), INCLUDE] + sorted(glob.glob(os.path.join(TKJT, "src", "*", "")))
    return [("/I" if WINDOWS else "-I") + o for o in ordner]


def _bibliothek(muster: str) -> str:
    """Pfad einer Bibliothek der Umgebung (Windows: .lib) nach Namensmuster."""
    treffer = sorted(glob.glob(os.path.join(LIB, muster)))
    if not treffer:
        raise SystemExit(f"Bibliothek {muster} nicht in {LIB}")
    return treffer[0]


def _msvc_linker() -> str:
    """link.exe neben cl.exe - im PATH steht sonst oft das GNU-link aus Git oder der pixi-Umgebung."""
    cl = shutil.which("cl")
    if not cl:
        raise SystemExit("cl nicht gefunden (MSVC-Entwicklerumgebung noetig)")
    return os.path.join(os.path.dirname(cl), "link.exe")


def uebersetzen(datei: str, obj: str):
    if WINDOWS:
        cmd = ["cl", "/nologo", "/std:c++17", "/O2", "/EHsc", "/MD", "/w", "/DNO_JT_MULTITHREADING", "/D_USE_MATH_DEFINES",
               "/DNOMINMAX", *includes(), "/c", datei, "/Fo" + obj]
    else:
        cxx = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
        cmd = [cxx, "-std=c++17", "-O2", "-fPIC", "-DNO_JT_MULTITHREADING", "-w", *includes(), "-c", datei, "-o", obj]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return datei, r.returncode, (r.stdout + r.stderr)[-2000:]


def main():
    quellen_holen()
    os.makedirs(os.path.join(BAU, "obj"), exist_ok=True)
    endung = ".obj" if WINDOWS else ".o"
    dateien = [d for d in glob.glob(os.path.join(TKJT, "src", "**", "*.cxx"), recursive=True) if "JtToTopoDS" not in d]
    auftraege = [(d, os.path.join(BAU, "obj", os.path.splitext(os.path.basename(d))[0] + endung)) for d in dateien]
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        ergebnisse = list(pool.map(lambda a: uebersetzen(*a), auftraege))
    fehler = [(d, t) for d, rc, t in ergebnisse if rc]
    for d, t in fehler[:5]:
        print(d, t, sep="\n")
    if fehler:
        raise SystemExit(f"{len(fehler)} Dateien nicht uebersetzt")
    konverter = os.path.join(WURZEL, "packaging", "jt", "jt2glb.cxx")
    objekte = [o for _, o in auftraege]
    if WINDOWS:
        ziel = os.path.join(WURZEL, "extern", "jt2glb.exe")
        hauptobj = os.path.join(BAU, "jt2glb.obj")
        datei, rc, text = uebersetzen(konverter, hauptobj)
        if rc:
            raise SystemExit(text)
        libs = [_bibliothek(n + ".lib") for n in OCCT_LIBS] + [_bibliothek("zlib*.lib"), _bibliothek("*lzma*.lib")]
        antwort = os.path.join(BAU, "link.rsp")  # Antwortdatei: Kommandozeile sonst zu lang
        with open(antwort, "w", encoding="utf-8") as f:
            f.write("\n".join(f'"{x}"' for x in [hauptobj, *objekte, *libs]))
        r = subprocess.run([_msvc_linker(), "/nologo", "/OUT:" + ziel, "@" + antwort], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit((r.stdout + r.stderr)[-4000:])
    else:
        ziel = os.path.join(WURZEL, "extern", "jt2glb")
        cxx = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
        relativ = "@loader_path" if sys.platform == "darwin" else "$ORIGIN"  # neben den Bibliotheken der App
        cmd = [cxx, "-std=c++17", "-O2", "-fPIC", "-DNO_JT_MULTITHREADING", "-w", *includes(), konverter, *objekte,
               "-L" + LIB, *("-l" + n for n in OCCT_LIBS), "-lz", "-llzma", "-Wl,-rpath," + LIB,
               "-Wl,-rpath," + relativ, "-o", ziel]
        subprocess.run(cmd, check=True)
    print("Fertig:", os.path.relpath(ziel, WURZEL))


if __name__ == "__main__":
    main()
