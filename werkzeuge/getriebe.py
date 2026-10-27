"""Demo Toleranzkette: Getriebewelle als STEP mit Werkstoffen und die passende Kettendatei erzeugen.

Aufruf: pixi run python werkzeuge/getriebe.py   -> tests/daten/getriebe.stp, tests/daten/getriebe.3dgkette
Aufbau (klassisches Lehrbeispiel der statistischen Tolerierung, Achse X): Welle mit Bund bei x = 0 und Nut fuer den
Sicherungsring, darauf Zahnrad 51 +0,2/-0,1, Distanzhuelse 43,2 +-0,15 (Aluminium), Waelzlager 12 +-0,05; Nut
106,5 +0,2 ab Bund, Nutbreite 1,3 +0,14, Sicherungsring 1,2 -0,06 an der aeusseren Nutflanke.
Schlussmass: Axialspiel zwischen Lager und Sicherungsring, nominal 0,4 (arithmetisch 0 ... 1,1).
Eigene Geometrie, frei verwendbar.
"""

from __future__ import annotations

import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEP = os.path.join(WURZEL, "tests", "daten", "getriebe.stp")
KETTE = os.path.join(WURZEL, "tests", "daten", "getriebe.3dgkette")

# Name, Werkstoff, Farbe, (x0, x1, Innenradius, Aussenradius)
TEILE = (("Zahnrad", "16MnCr5", (0.80, 0.55, 0.20), (0.0, 51.0, 15.0, 40.0)),
         ("Distanzhülse", "EN AW-6082", (0.75, 0.78, 0.82), (51.0, 94.2, 15.0, 20.0)),
         ("Wälzlager", "100Cr6", (0.35, 0.45, 0.70), (94.2, 106.2, 15.0, 30.0)),
         ("Sicherungsring", "C75S Federstahl", (0.25, 0.25, 0.28), (106.6, 107.8, 14.0, 19.0)))


def _name(label, text):
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    TDataStd_Name.Set(label, TCollection_ExtendedString(text, True))


def _zylinder(x0, x1, r):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x0, 0, 0), gp_Dir(1, 0, 0)), r, x1 - x0).Shape()


def _ring(x0, x1, ri, ra):
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    return BRepAlgoAPI_Cut(_zylinder(x0, x1, ra), _zylinder(x0 - 1, x1 + 1, ri)).Shape()


def _welle():
    """Welle mit Bund (x -10 ... 0) und Nut 106,5 ... 107,8."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    w = BRepAlgoAPI_Fuse(_zylinder(-10.0, 0.0, 25.0), _zylinder(0.0, 125.0, 15.0)).Shape()
    return BRepAlgoAPI_Cut(w, _ring(106.5, 107.8, 14.0, 16.0)).Shape()


def erzeuge_step(ziel: str = STEP) -> str:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.STEPControl import STEPControl_AsIs
    from OCC.Core.TCollection import TCollection_HAsciiString
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
    doc = TDocStd_Document("MDTV-XCAF")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool(doc.Main())
    mt = XCAFDoc_DocumentTool.MaterialTool(doc.Main())
    wurzel = st.NewShape()
    _name(wurzel, "Getriebewelle")
    teile = [("Welle", "42CrMo4", (0.62, 0.64, 0.68), _welle())]
    teile += [(n, w, f, _ring(*m)) for n, w, f, m in TEILE]
    for name, werkstoff, farbe, form in teile:
        lab = st.AddShape(form, False)
        _name(lab, name)
        ct.SetColor(lab, Quantity_Color(*farbe, Quantity_TOC_RGB), XCAFDoc_ColorSurf)
        mt.SetMaterial(lab, mt.AddMaterial(TCollection_HAsciiString(werkstoff), TCollection_HAsciiString(""), 0.0,
                                           TCollection_HAsciiString(""), TCollection_HAsciiString("")))
        _name(st.AddComponent(wurzel, lab, TopLoc_Location()), name)
    st.UpdateAssemblies()
    Interface_Static.SetCVal("write.step.schema", "AP242DIS")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(ziel) != IFSelect_RetDone:
        raise RuntimeError("STEP nicht geschrieben")
    return ziel


def _flaeche(erg, teil: str, x: float) -> int:
    """Index der ebenen Flaeche senkrecht zu X bei x am Teil."""
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern.toleranzkette import _ebene_oder_achse
    knoten = next(k for k in erg.baum.blaetter() if k.name == teil)
    ex = TopExp_Explorer(knoten.form, TopAbs_FACE)
    while ex.More():
        g = _ebene_oder_achse(ex.Current())
        if g is not None and g[0] == "ebene" and abs(abs(g[2][0]) - 1) < 1e-9 and abs(g[1][0] - x) < 1e-6:
            return erg.modell.flaechen_index(ex.Current())
        ex.Next()
    raise LookupError(f"{teil}: keine Ebene bei x = {x}")


def erzeuge_kette(step: str = STEP, ziel: str = KETTE) -> str:
    from programm.kern import kette_datei, toleranzkette as tk, werkstoffe
    from programm.ui.lader import lade_alles
    erg = lade_alles(step)
    glieder = []
    for name, teil, x0, x1, oben, unten, verteilung in (
            ("M1 Zahnradbreite 51 +0,2/−0,1", "Zahnrad", 0.0, 51.0, 0.2, -0.1, "dreieck"),
            ("M2 Distanzhülse 43,2 ±0,15", "Distanzhülse", 51.0, 94.2, 0.15, -0.15, "dreieck"),
            ("M3 Wälzlager 12 ±0,05", "Wälzlager", 94.2, 106.2, 0.05, -0.05, "normal"),
            ("M4 Bund bis Nut 106,5 +0,2", "Welle", 0.0, 106.5, 0.2, 0.0, "dreieck"),
            ("M5 Nutbreite 1,3 +0,14", "Welle", 106.5, 107.8, 0.14, 0.0, "dreieck"),
            ("M6 Sicherungsring 1,2 −0,06", "Sicherungsring", 106.6, 107.8, 0.0, -0.06, "normal")):
        nenn = round(x1 - x0, 4)
        glieder.append(tk.Glied(name, nenn, nenn + oben, nenn + unten, 1, quelle="eigen", verteilung=verteilung,
                                teil=teil, flaechen=(_flaeche(erg, teil, x0), _flaeche(erg, teil, x1))))
    # Schlussmass: rechte Lagerflaeche (x = 106,2) bis linke Flaeche des Sicherungsrings (x = 106,6)
    glieder, hinweise = tk.richtungen_aus_schlussmass(glieder, erg.modell, _flaeche(erg, "Wälzlager", 106.2),
                                                      _flaeche(erg, "Sicherungsring", 106.6))
    if hinweise:
        raise RuntimeError("; ".join(hinweise))
    aus_datei = werkstoffe.werkstoffe_aus_step(erg.modell.datei)
    stoffe = {t: {"name": w, "alpha": werkstoffe.alpha_fuer(w)} for t, w in aus_datei.items()}
    return kette_datei.speichere(ziel, kette_datei.KettenDatei(
        glieder, 1.0, (0.05, 1.1), (-20.0, 100.0), stoffe, os.path.basename(step), "Axialspiel Getriebewelle"))


if __name__ == "__main__":
    sys.path.insert(0, WURZEL)
    print(erzeuge_step())
    print(erzeuge_kette())
