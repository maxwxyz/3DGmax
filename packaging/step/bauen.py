"""Kleine STEP-Ladebibliothek gegen dieselbe OCCT-Version wie pythonocc bauen."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def bauen():
    hier = Path(__file__).resolve().parent
    windows = sys.platform == "win32"
    prefix = Path(sys.prefix) / "Library" if windows else Path(sys.prefix)
    inc = prefix / "include" / "opencascade"
    lib = prefix / "lib"
    ziel = hier.parents[1] / "build" / "step"
    ziel.mkdir(parents=True, exist_ok=True)
    quelle = str(hier / "import.cxx")
    libs = ["TKDESTEP", "TKLCAF", "TKernel"]
    if windows:
        cmd = ["cl", "/nologo", "/LD", "/EHsc", "/MD", "/O2", "/std:c++17", f"/I{inc}", quelle,
               "/link", f"/LIBPATH:{lib}", *(n + ".lib" for n in libs), "/OUT:dg_step.dll"]
    else:
        mac = sys.platform == "darwin"
        cxx = os.environ.get("CXX") or shutil.which("c++") or "c++"
        cmd = [cxx, "-std=c++17", "-O2", "-fPIC", "-dynamiclib" if mac else "-shared", f"-I{inc}",
               quelle, f"-L{lib}", *(f"-l{n}" for n in libs), "-o", "dg_step.dylib" if mac else "dg_step.so"]
    subprocess.run(cmd, cwd=ziel, check=True)


if __name__ == "__main__":
    bauen()
