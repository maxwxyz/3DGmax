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


if __name__ == "__main__":
    occt_umgebung()
    from programm.app import main
    sys.exit(main())
