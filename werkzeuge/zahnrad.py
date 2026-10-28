"""Evolventen-Zahnraeder als Testgeometrie mit bekannten Sollwerten (PLAN §8.27, eigene Geometrie, frei verwendbar).

Aufruf: pixi run python werkzeuge/zahnrad.py   -> tests/daten/zahnrad_*.stp (nur bei Bedarf; die Tests erzeugen sie)
Stirnschnitt als Linienzug: Evolventenflanken (Grundkreis rb, unterhalb davon radial), Kopf- und Fusskreisboegen;
gerade Zaehne als Prisma, schraege als Regelflaechen durch gedrehte Stirnschnitte (rechtssteigend: beta > 0).
Aussenrad mit Bohrung; Innenrad (Hohlrad) als Ring, dessen Bohrung die Verzahnung traegt.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _inv(a: float) -> float:
    return math.tan(a) - a


def stirnschnitt(z: int, mn: float, alpha_n: float = 20.0, beta: float = 0.0, x: float = 0.0, innen: bool = False,
                 flanke: int = 12) -> np.ndarray:
    """Punkte (N x 2) des Stirnschnitts; innen: Kontur der Bohrung eines Hohlrads (Zaehne nach innen)."""
    b = math.radians(beta)
    at = math.atan(math.tan(math.radians(alpha_n)) / math.cos(b))
    mt = mn / math.cos(b)
    d = z * mt
    rb = d / 2 * math.cos(at)
    if innen:  # Luecke des Hohlrads wie der Zahn eines Aussenrads: Kopf und Fuss vertauscht
        ra, rf = d / 2 + mn * (1.25 + x), d / 2 - mn * (1.0 - x)
        s = mt * (math.pi / 2 + 2 * x * math.tan(at))  # Lueckenweite am Teilkreis
    else:
        ra, rf = d / 2 + mn * (1.0 + x), d / 2 - mn * (1.25 - x)
        s = mt * (math.pi / 2 + 2 * x * math.tan(at))  # Zahndicke am Teilkreis
    eta = s / d  # halber Winkel am Teilkreis

    def winkel(r):  # halber Winkel der Flanke beim Radius r (Mitte des Zahns bzw. der Luecke = 0)
        return eta + _inv(at) - _inv(math.acos(min(1.0, rb / r))) if r > rb else eta + _inv(at)
    r0 = max(rf, rb)
    radien = np.linspace(r0, ra, flanke)
    punkte = []
    for i in range(z):
        c = 2 * math.pi * i / z
        if rf < rb:
            punkte.append((rf, c - winkel(rb)))
        punkte += [(r, c - winkel(r)) for r in radien]
        kopf = np.linspace(c - winkel(ra), c + winkel(ra), 4)[1:-1]
        punkte += [(ra, t) for t in kopf]
        punkte += [(r, c + winkel(r)) for r in radien[::-1]]
        if rf < rb:
            punkte.append((rf, c + winkel(rb)))
        naechste = 2 * math.pi * (i + 1) / z - winkel(r0)
        fuss = np.linspace(c + winkel(r0), naechste, 4)[1:-1]
        punkte += [(rf, t) for t in fuss]
    p = np.array([(r * math.cos(t), r * math.sin(t)) for r, t in punkte])
    if innen:  # Zahn des Hohlrads liegt in der Luecke der Kontur: um eine halbe Teilung drehen
        w = math.pi / z
        p = p @ np.array([[math.cos(w), math.sin(w)], [-math.sin(w), math.cos(w)]])
    return p


def _draht(p: np.ndarray, z0: float, drehung: float = 0.0):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCC.Core.gp import gp_Pnt
    c, s = math.cos(drehung), math.sin(drehung)
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in p:
        poly.Add(gp_Pnt(c * x - s * y, s * x + c * y, z0))
    poly.Close()
    return poly.Wire()


def zahnrad(z: int, mn: float, b: float, alpha_n: float = 20.0, beta: float = 0.0, x: float = 0.0,
            innen: bool = False, schnitte: int = 9):
    """Zahnrad als Volumen, Achse Z ab z = 0, Breite b."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    p = stirnschnitt(z, mn, alpha_n, beta, x, innen)
    if abs(beta) < 1e-9:
        verzahnung = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(_draht(p, 0.0)).Face(), gp_Vec(0, 0, b)).Shape()
    else:
        d = z * mn / math.cos(math.radians(beta))
        dreh = math.tan(math.radians(beta)) / (d / 2)  # rad je mm (rechtssteigend positiv)
        thru = BRepOffsetAPI_ThruSections(True, True)
        for s in np.linspace(0.0, b, schnitte):
            thru.AddWire(_draht(p, float(s), float(s * dreh)))
        thru.Build()
        verzahnung = thru.Shape()
    r = float(np.linalg.norm(p, axis=1).min())
    if innen:
        ring = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)),
                                        float(np.linalg.norm(p, axis=1).max()) + 3 * mn, b).Shape()
        return BRepAlgoAPI_Cut(ring, verzahnung).Shape()
    bohrung = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -1), gp_Dir(0, 0, 1)), 0.4 * r, b + 2).Shape()
    return BRepAlgoAPI_Cut(verzahnung, bohrung).Shape()


def speichere(form, pfad: str, name: str) -> str:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.STEPControl import STEPControl_AsIs
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
    doc = TDocStd_Document("MDTV-XCAF")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    TDataStd_Name.Set(st.AddShape(form, False), TCollection_ExtendedString(name, True))
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(pfad) != IFSelect_RetDone:
        raise RuntimeError("STEP nicht geschrieben")
    return pfad


if __name__ == "__main__":
    sys.path.insert(0, WURZEL)
    ziel = os.path.join(WURZEL, "tests", "daten")
    print(speichere(zahnrad(23, 2.0, 20.0, beta=15.0, x=0.2), os.path.join(ziel, "zahnrad_schraeg.stp"),
                    "Zahnrad z23 mn2 b15"))
