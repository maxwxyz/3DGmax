"""Kleine Test-Baugruppe als STEP AP242 erzeugen (Explosionsansicht, Stueckliste, Baugruppenvergleich).

Aufruf: pixi run python werkzeuge/baugruppe.py   -> tests/daten/baugruppe.stp, tests/daten/baugruppe_b.stp
Aufbau: Grundplatte, Deckel, 4x dieselbe Schraube (ein Produkt, vier Exemplare), Unterbaugruppe "Halter" mit Winkel.
Variante B: Deckel 5 statt 4 mm dick, eine Schraube entfaellt, Halter 10 mm verschoben, neues Teil "Stift".
"""

from __future__ import annotations

import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(WURZEL, "tests", "daten", "baugruppe.stp")


def _name(label, text):
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    TDataStd_Name.Set(label, TCollection_ExtendedString(text, True))


def _lage(x, y, z):
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(x, y, z))
    return TopLoc_Location(t)


def erzeuge(ziel: str = ZIEL, variante: bool = False) -> str:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.STEPControl import STEPControl_AsIs
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

    doc = TDocStd_Document("MDTV-XCAF")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool(doc.Main())

    platte = BRepPrimAPI_MakeBox(120.0, 80.0, 10.0).Shape()
    for x, y in ((15, 15), (105, 15), (15, 65), (105, 65)):
        loch = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), 3.3, 12.0).Shape()
        platte = BRepAlgoAPI_Cut(platte, loch).Shape()
    deckel = BRepPrimAPI_MakeBox(gp_Pnt(10, 10, 0), 100.0, 60.0, 5.0 if variante else 4.0).Shape()
    schraube = BRepPrimAPI_MakeCylinder(3.0, 25.0).Shape()
    kopf = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 25), gp_Dir(0, 0, 1)), 5.0, 4.0).Shape()
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    schraube = BRepAlgoAPI_Fuse(schraube, kopf).Shape()
    winkel = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(30.0, 20.0, 3.0).Shape(),
                              BRepPrimAPI_MakeBox(30.0, 3.0, 25.0).Shape()).Shape()

    wurzel = st.NewShape()
    _name(wurzel, "Testbaugruppe")
    teile = {}
    for name, form, farbe in (("Grundplatte", platte, (0.70, 0.72, 0.76)), ("Deckel", deckel, (0.25, 0.45, 0.80)),
                              ("Schraube M6x25", schraube, (0.35, 0.35, 0.38)), ("Winkel", winkel, (0.85, 0.55, 0.15))):
        lab = st.AddShape(form, False)
        _name(lab, name)
        ct.SetColor(lab, Quantity_Color(*farbe, Quantity_TOC_RGB), XCAFDoc_ColorSurf)
        teile[name] = lab
    for name, lage in (("Grundplatte", (0, 0, 0)), ("Deckel", (0, 0, 10))):
        _name(st.AddComponent(wurzel, teile[name], _lage(*lage)), name)
    schrauben = ((15, 15), (105, 15), (15, 65)) if variante else ((15, 15), (105, 15), (15, 65), (105, 65))
    for i, (x, y) in enumerate(schrauben, 1):
        _name(st.AddComponent(wurzel, teile["Schraube M6x25"], _lage(x, y, -12)), f"Schraube M6x25:{i}")
    halter = st.NewShape()
    _name(halter, "Halter")
    _name(st.AddComponent(halter, teile["Winkel"], _lage(0, 0, 0)), "Winkel")
    _name(st.AddComponent(wurzel, halter, _lage(55 if variante else 45, 85, 0)), "Halter")
    if variante:
        stift = st.AddShape(BRepPrimAPI_MakeCylinder(2.0, 15.0).Shape(), False)
        _name(stift, "Stift 4x15")
        _name(st.AddComponent(wurzel, stift, _lage(60, 40, 14)), "Stift 4x15")
    st.UpdateAssemblies()

    Interface_Static.SetCVal("write.step.schema", "AP242DIS")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    if w.Write(ziel) != IFSelect_RetDone:
        raise RuntimeError("STEP schreiben fehlgeschlagen")
    return ziel


if __name__ == "__main__":
    sys.path.insert(0, WURZEL)
    print(erzeuge())
    print(erzeuge(os.path.join(WURZEL, "tests", "daten", "baugruppe_b.stp"), variante=True))
