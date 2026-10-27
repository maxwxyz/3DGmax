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

datas = [(os.path.join(SRC, f), ".") for f in ("Anleitung.html", "Manual.html", "i18n_en.json", "CHANGELOG.json",
                                               "icon.png", "icon.ico", "icon.icns")]
datas += [(os.path.join(ROOT, "LICENSE"), ".")]   # GPL-3.0-or-later, liegt der App bei
datas += [(os.path.join(SRC, "doc_img"), "doc_img")]   # Bilder der Anleitung (packaging/doc_screenshots.py)
datas += [(os.path.join(SRC, "beispiele"), os.path.join("programm", "beispiele"))]   # fuer --selbsttest
from programm.kern import beispiele  # noqa: E402 - Dateien fuer Datei > Beispiele (liegen in tests/daten)
for _name in sorted(beispiele.alle_dateien()):
    _pfad = beispiele.datei(_name)
    if _pfad is None:
        raise SystemExit(f"Beispieldatei fehlt: {_name} (pixi run python werkzeuge/testmodelle.py)")
    datas.append((_pfad, os.path.join("programm", "beispiele")))
if OCCT_RES:
    for teil in ("Shaders", "StdResource", "XSMessage", "SHMessage", "XSTEPResource", "XmlOcafResource",
                 "UnitsAPI", "TObj", "BOPAlgo", "Textures"):
        if os.path.isdir(os.path.join(OCCT_RES, teil)):
            datas.append((os.path.join(OCCT_RES, teil), os.path.join("occt_resources", teil)))
else:
    print("WARNUNG: OCCT-Ressourcen nicht gefunden")

# Build-Variante mit JT (DG_MIT_JT=1): Konverter jt2glb aus packaging/jt/bauen.sh (TKJT, GPL v2+) mitliefern
jt_binaer = []
if os.environ.get("DG_MIT_JT") == "1":
    _jt = os.path.join(ROOT, "extern", "jt2glb")
    if not os.path.isfile(_jt):
        raise SystemExit("DG_MIT_JT=1, aber extern/jt2glb fehlt (packaging/jt/bauen.sh)")
    jt_binaer = [(_jt, ".")]

from PyInstaller.utils.hooks import collect_submodules  # noqa: E402
hidden = collect_submodules("programm") + collect_submodules("OCC.Core") + ["OCC.Display.qtDisplay",
                                                                             "OCC.Display.backend"]
excludes = ["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PyQt6", "PySide2", "wx",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
            "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization"]

a = Analysis([os.path.join(ROOT, "packaging", "start_3dgmax.py")], pathex=[ROOT], datas=datas, binaries=jt_binaer,
             hiddenimports=hidden, excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
# Startbild des Starters (Windows/Linux; macOS kennt es nicht): sichtbar, bevor Python und Qt geladen sind,
# packaging/startbild.py erzeugt das Bild; programm.app schliesst es, sobald das Qt-Startbild steht
starter = []
if sys.platform != "darwin":
    splash = Splash(os.path.join(ROOT, "packaging", "startbild.png"), binaries=a.binaries, datas=a.datas,
                    text_pos=None, always_on_top=False)
    starter = [splash, splash.binaries]
exe = EXE(pyz, a.scripts, *starter[:1], [], exclude_binaries=True, name="3DGmax", console=False, upx=False,
          argv_emulation=False, icon=os.path.join(SRC, "icon.icns" if sys.platform == "darwin" else "icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, *starter[1:], name="3DGmax", upx=False)

if sys.platform == "darwin":
    # Finder bietet 3DGmax zum Oeffnen an (Alternate: ersetzt nicht das Standardprogramm); PDF bleibt aussen vor
    doc_types = [{"CFBundleTypeName": name, "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
                  "CFBundleTypeExtensions": endungen} for name, endungen in (
        ("STEP-Modell", ["stp", "step", "p21", "stpz", "stepz"]), ("IGES-Modell", ["igs", "iges"]),
        ("Netz", ["stl", "obj", "gltf", "glb", "3mf", "ply"]), ("QIF", ["qif"]), ("PRC", ["prc"]))]
    if jt_binaer:
        doc_types.append({"CFBundleTypeName": "JT", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
                          "CFBundleTypeExtensions": ["jt"]})
    app = BUNDLE(coll, name="3DGmax.app", bundle_identifier="de.3dgmax.app", icon=os.path.join(SRC, "icon.icns"),
                 info_plist={"CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
                             "CFBundleDisplayName": "3DGmax", "NSHighResolutionCapable": True,
                             "LSMinimumSystemVersion": "14.0", "CFBundleDocumentTypes": doc_types,
                             "NSRequiresAquaSystemAppearance": False})
