"""Startpunkt der gebauten App (PyInstaller): OCCT-Ressourcen setzen, dann programm.app starten."""

import os
import sys


def occt_umgebung():
    """In der gebauten App liegen die OCCT-Ressourcen unter occt_resources (Shader, STEP-Einstellungen)."""
    basis = getattr(sys, "_MEIPASS", None)
    if not basis:
        return
    res = os.path.join(basis, "occt_resources")
    if not os.path.isdir(res):
        return
    os.environ.setdefault("CASROOT", basis)
    for name, unter in (("CSF_ShadersDirectory", "Shaders"), ("CSF_StandardDefaults", "StdResource"),
                        ("CSF_PluginDefaults", "StdResource"), ("CSF_XSMessage", "XSMessage"),
                        ("CSF_SHMessage", "SHMessage"), ("CSF_STEPDefaults", "XSTEPResource"),
                        ("CSF_XmlOcafResource", "XmlOcafResource"), ("CSF_TObjMessage", "TObj"),
                        ("CSF_XCAFDefaults", "StdResource"), ("CSF_BOPAlgoMessage", "BOPAlgo")):
        os.environ.setdefault(name, os.path.join(res, unter))
    os.environ.setdefault("CSF_UnitsLexicon", os.path.join(res, "UnitsAPI", "Lexi_Expr.dat"))
    os.environ.setdefault("CSF_UnitsDefinition", os.path.join(res, "UnitsAPI", "Units.dat"))


def _protokoll_pfad() -> str:
    import tempfile
    ordner = os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "3DGmax")
    os.makedirs(ordner, exist_ok=True)
    return os.path.join(ordner, "start_fehler.log")


def _melde(text: str):
    """Fehler sichtbar machen: die App hat keine Konsole (Windows-Meldungsfenster, sonst stderr)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "3DGmax", 0x10)
    else:
        print(text, file=sys.stderr)


def _aus_zip_gestartet() -> bool:
    """Explorer startet eine EXE aus einem ZIP ohne die DLLs daneben (nur die EXE liegt dann in Temp)."""
    basis = getattr(sys, "_MEIPASS", None)
    return bool(basis) and not os.path.isdir(os.path.join(basis, "occt_resources"))


def starte() -> int:
    if _aus_zip_gestartet():
        _melde("3DGmax wurde direkt aus dem ZIP-Archiv gestartet. Bitte das ZIP zuerst vollständig entpacken "
               "(Alle extrahieren) und dann 3DGmax.exe im entpackten Ordner starten.\n\n"
               "3DGmax was started from inside the ZIP archive. Please extract the whole ZIP first "
               "(Extract all) and start 3DGmax.exe from the extracted folder.")
        return 1
    import faulthandler
    protokoll = _protokoll_pfad()
    absturz = open(protokoll + ".absturz", "w", encoding="utf-8")  # noqa: SIM115 - offen bis Programmende
    faulthandler.enable(absturz)  # harte Abstuerze (z. B. OpenGL-Treiber) landen hier
    try:
        occt_umgebung()
        from programm.app import main
        return main()
    except Exception:  # noqa: BLE001 - jeder Startfehler soll sichtbar werden
        import traceback
        with open(protokoll, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        _melde(f"3DGmax konnte nicht starten / could not start.\n\n{traceback.format_exc(limit=3)}\n"
               f"Protokoll / log: {protokoll}")
        return 1


if __name__ == "__main__":
    sys.exit(starte())
