# PyInstaller-Bauplan fuer die portable App (macOS .app, Windows/Linux-Ordner).
# Bauen: packaging/build_mac.sh, packaging/build_linux.sh, packaging\build_windows.bat (nutzen pixi)
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "programm")
sys.path.insert(0, ROOT)
from programm.version import VERSION  # noqa: E402

PREFIX = os.environ.get("CONDA_PREFIX", sys.prefix)
OCCT_RES = next((p for p in (os.path.join(PREFIX, "share", "opencascade", "resources"),
                             os.path.join(PREFIX, "Library", "share", "opencascade", "resources"))
                 if os.path.isdir(p)), None)

datas = [(os.path.join(SRC, f), ".") for f in ("Anleitung.html", "Manual.html", "i18n_en.json", "CHANGELOG.json")]
datas += [(os.path.join(SRC, "beispiele"), os.path.join("programm", "beispiele"))]   # fuer --selbsttest
if OCCT_RES:
    for teil in ("Shaders", "StdResource", "XSMessage", "SHMessage", "XSTEPResource", "XmlOcafResource",
                 "UnitsAPI", "TObj", "BOPAlgo", "Textures"):
        if os.path.isdir(os.path.join(OCCT_RES, teil)):
            datas.append((os.path.join(OCCT_RES, teil), os.path.join("occt_resources", teil)))
else:
    print("WARNUNG: OCCT-Ressourcen nicht gefunden")

from PyInstaller.utils.hooks import collect_submodules  # noqa: E402
hidden = collect_submodules("programm") + collect_submodules("OCC.Core") + ["OCC.Display.qtDisplay",
                                                                             "OCC.Display.backend"]
excludes = ["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PyQt6", "PySide2", "wx",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
            "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization"]

a = Analysis([os.path.join(ROOT, "packaging", "start_3dgmax.py")], pathex=[ROOT], datas=datas,
             hiddenimports=hidden, excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="3DGmax", console=False, upx=False,
          argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, name="3DGmax", upx=False)

if sys.platform == "darwin":
    doc_types = [{"CFBundleTypeName": "STEP-Modell", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
                  "CFBundleTypeExtensions": ["stp", "step"]}]
    app = BUNDLE(coll, name="3DGmax.app", bundle_identifier="de.3dgmax.app",
                 info_plist={"CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
                             "CFBundleDisplayName": "3DGmax", "NSHighResolutionCapable": True,
                             "LSMinimumSystemVersion": "14.0", "CFBundleDocumentTypes": doc_types,
                             "NSRequiresAquaSystemAppearance": False})
