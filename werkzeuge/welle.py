"""Beispiel Funktion -> Tolerierung: einfache Getriebewelle als STEP erzeugen (eigene Geometrie, frei verwendbar).

Aufruf: pixi run python werkzeuge/welle.py   -> tests/daten/getriebewelle.stp
Aufbau (Achse X, von links): Wellenende Ø20 mit Passfedernut 6 x 3,5 (DIN 6885-1, Kupplungsnabe), Dichtsitz Ø25 fuer
einen Radialwellendichtring 25 x 40 x 7 (DIN 3760) mit Einfuehrschraege, Lagersitz Ø30 fuer das Festlager 6206
(30 x 62 x 16) mit Sicherungsringnut 28,6 x 1,6 (DIN 471, Ring 30 x 1,5) links und Wellenschulter Ø40 rechts,
Nabensitz Ø36 fuer das Zahnrad mit Passfedernut 10 x 5 (Anschlag an der Schulter), Lagersitz Ø30 fuer das Loslager
6206 an der Schulter Ø36; Fasen 1 x 45° an den Enden und am linken Lagersitz.
Die Funktion der Flaechen ordnet das Beispiel im Programm zu (Hauptfenster._beispiel_funktion, ueber die Lage X).
"""

from __future__ import annotations

import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEP = os.path.join(WURZEL, "tests", "daten", "getriebewelle.stp")

# Kontur (x, Radius) im Laengsschnitt, von links nach rechts
KONTUR = ((0.0, 0.0), (0.0, 9.0), (1.0, 10.0), (36.0, 10.0), (36.0, 11.25), (39.5, 12.5), (50.0, 12.5),
          (50.0, 14.0), (51.0, 15.0), (52.4, 15.0), (52.4, 14.3), (54.0, 14.3), (54.0, 15.0), (70.0, 15.0),
          (70.0, 20.0), (78.0, 20.0), (78.0, 18.0), (118.0, 18.0), (118.0, 15.0), (135.0, 15.0), (136.0, 14.0),
          (136.0, 0.0))
# Passfedernuten: (x Anfang, x Ende, Wellenradius, Breite b, Wellennuttiefe t1) - Form A mit runden Enden
NUTEN = ((4.0, 32.0, 10.0, 6.0, 3.5), (82.0, 114.0, 18.0, 10.0, 5.0))
# Lage der Funktionsflaechen (x) fuer das Beispiel
LAGERSITZE = (62.0, 127.0)  # Mitte der Lagersitze (Zylinder Ø30)
SCHULTER_FESTLAGER = 70.0  # Ebene, an der das Festlager anliegt
SCHULTER_NABE = 78.0  # Ebene, an der die Zahnradnabe anliegt
SCHULTER_LOSLAGER = 118.0
RINGNUT = 53.2  # Nutgrund Ø28,6
DICHTSITZ = 45.0  # Zylinder Ø25
NABENSITZ = 98.0  # Zylinder Ø36
WELLENENDE = 18.0  # Zylinder Ø20 (Kupplung)


def _rotationskoerper():
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt
    poly = BRepBuilderAPI_MakePolygon()
    for x, r in KONTUR:
        poly.Add(gp_Pnt(x, 0.0, r))
    poly.Close()
    flaeche = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    return BRepPrimAPI_MakeRevol(flaeche, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0))).Shape()


def _nut(x0, x1, r, b, t1):
    """Passfedernut Form A oben (+Z): Quader zwischen den Mittelpunkten der Enden und zwei Zylinder Ø b."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    z0, h = r - t1, t1 + 2.0
    form = BRepPrimAPI_MakeBox(gp_Pnt(x0 + b / 2, -b / 2, z0), x1 - x0 - b, b, h).Shape()
    for x in (x0 + b / 2, x1 - b / 2):
        form = BRepAlgoAPI_Fuse(form, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 0, z0), gp_Dir(0, 0, 1)), b / 2, h)
                                .Shape()).Shape()
    return form


def welle():
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    form = _rotationskoerper()
    for nut in NUTEN:
        form = BRepAlgoAPI_Cut(form, _nut(*nut)).Shape()
    vereinen = ShapeUpgrade_UnifySameDomain(form, True, True, True)
    vereinen.Build()
    form = vereinen.Shape()
    if not BRepCheck_Analyzer(form).IsValid():
        raise RuntimeError("Welle ungueltig")
    return form


def erzeuge_step(ziel: str = STEP) -> str:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.STEPControl import STEPControl_AsIs
    from OCC.Core.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
    doc = TDocStd_Document("MDTV-XCAF")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    lab = st.AddShape(welle(), False)
    TDataStd_Name.Set(lab, TCollection_ExtendedString("Getriebewelle", True))
    XCAFDoc_DocumentTool.ColorTool(doc.Main()).SetColor(lab, Quantity_Color(0.62, 0.64, 0.68, Quantity_TOC_RGB),
                                                        XCAFDoc_ColorSurf)
    mt = XCAFDoc_DocumentTool.MaterialTool(doc.Main())
    mt.SetMaterial(lab, mt.AddMaterial(TCollection_HAsciiString("42CrMo4"), TCollection_HAsciiString(""), 0.0,
                                       TCollection_HAsciiString(""), TCollection_HAsciiString("")))
    Interface_Static.SetCVal("write.step.schema", "AP242DIS")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(ziel) != IFSelect_RetDone:
        raise RuntimeError("STEP nicht geschrieben")
    return ziel


if __name__ == "__main__":
    sys.path.insert(0, WURZEL)
    print(erzeuge_step())
