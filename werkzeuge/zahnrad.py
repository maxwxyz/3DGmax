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
                 flanke: int = 12, kopf: float = 1.0, fuss: float = 1.25,
                 ruecknahme: tuple[float, float] = (0.0, 1.0)) -> np.ndarray:
    """Punkte (N x 2) des Stirnschnitts; innen: Kontur der Bohrung eines Hohlrads (Zaehne nach innen); kopf, fuss:
    Kopf- und Fusshoehe in Vielfachen von mn (Bezugsprofil ISO 53: 1 / 1,25; Zahnwelle ISO 4156 etwa 0,5 / 0,6).
    ruecknahme (Testdaten fuer die Mikrogeometrie-Erkennung): (Ca in mm je Flanke am Kopfkreis, Beginn als Anteil
    der Waelzlaenge zwischen Fussform- und Kopfkreis), linear in der Waelzlaenge."""
    b = math.radians(beta)
    at = math.atan(math.tan(math.radians(alpha_n)) / math.cos(b))
    mt = mn / math.cos(b)
    d = z * mt
    rb = d / 2 * math.cos(at)
    if innen:  # Luecke des Hohlrads wie der Zahn eines Aussenrads: Kopf und Fuss vertauscht
        ra, rf = d / 2 + mn * (fuss + x), d / 2 - mn * (kopf - x)
        s = mt * (math.pi / 2 + 2 * x * math.tan(at))  # Lueckenweite am Teilkreis
    else:
        ra, rf = d / 2 + mn * (kopf + x), d / 2 - mn * (fuss - x)
        s = mt * (math.pi / 2 + 2 * x * math.tan(at))  # Zahndicke am Teilkreis
    eta = s / d  # halber Winkel am Teilkreis

    r0 = max(rf, rb)
    ca, anfang = ruecknahme
    l0, la = math.sqrt(max(r0 ** 2 - rb ** 2, 0.0)), math.sqrt(max(ra ** 2 - rb ** 2, 0.0))
    ls = l0 + anfang * (la - l0)

    def winkel(r):  # halber Winkel der Flanke beim Radius r (Mitte des Zahns bzw. der Luecke = 0)
        w = eta + _inv(at) - _inv(math.acos(min(1.0, rb / r))) if r > rb else eta + _inv(at)
        lr = math.sqrt(max(r ** 2 - rb ** 2, 0.0))
        if ca and lr > ls:  # Kopfruecknahme: Flanke um ca * (l - ls) / (la - ls) zuruecknehmen (normal zur Flanke)
            w -= ca * (lr - ls) / (la - ls) / rb
        return w
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
            innen: bool = False, schnitte: int = 0, kopf: float = 1.0, fuss: float = 1.25,
            ruecknahme: tuple[float, float] = (0.0, 1.0)):
    """Zahnrad als Volumen, Achse Z ab z = 0, Breite b (Testdaten mit bekannten Sollwerten)."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    p = stirnschnitt(z, mn, alpha_n, beta, x, innen, flanke=40 if ruecknahme[0] else 12, kopf=kopf, fuss=fuss,
                     ruecknahme=ruecknahme)
    if abs(beta) < 1e-9:
        verzahnung = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(_draht(p, 0.0)).Face(), gp_Vec(0, 0, b)).Shape()
    else:
        d = z * mn / math.cos(math.radians(beta))
        dreh = math.tan(math.radians(beta)) / (d / 2)  # rad je mm (rechtssteigend positiv)
        # Regelflaechen zwischen den Schnitten: hoechstens 1/10 Teilung Drehung je Abschnitt, sonst laufen die
        # Verbindungslinien quer durch die Luecken und das Rad ist kein Schraegrad mehr
        schnitte = max(schnitte or 9, int(math.ceil(abs(dreh) * b / (2 * math.pi / z) * 10)) + 1)
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


# --- Steckverzahnungen (Testdaten fuer kern.passverzahnung; kein Generator als Funktion des Programms) ---

def zahnprofil(z: int, halbwinkel, rf: float, ra: float, flanke: int = 16, rund: float = 0.0) -> np.ndarray:
    """Kontur (N x 2) mit z Zaehnen in Wellenform (Zahnmitte bei 2 pi i / z), halbwinkel(r): halber Zahnwinkel beim
    Radius r, Kopfkreis ra, Fusskreis rf. Eine Nabe hat dieselbe Kontur (ihre Luecke ist der Wellenzahn): ra ist dann
    ihr Fuss-, rf ihr Kopfkreis. rund > 0: Fuss als Kreisbogen (Vollrundung) ab rf + rund * (ra - rf) durch die
    Mitte der Luecke auf dem Fusskreis, sonst flacher Fuss mit scharfen Ecken."""
    r0 = rf + rund * (ra - rf) if rund else rf
    radien = np.linspace(r0, ra, flanke)
    teilung = 2 * math.pi / z
    punkte = []
    for i in range(z):
        c = teilung * i
        punkte += [(r, c - halbwinkel(r)) for r in radien]
        punkte += [(ra, t) for t in np.linspace(c - halbwinkel(ra), c + halbwinkel(ra), 5)[1:-1]]
        punkte += [(r, c + halbwinkel(r)) for r in radien[::-1]]
        a, b = c + halbwinkel(r0), c + teilung - halbwinkel(r0)
        if rund:
            punkte += _bogen((r0, a), (rf, (a + b) / 2), (r0, b), 12)
        else:
            punkte += [(rf, t) for t in np.linspace(a, b, 6)[1:-1]]
    return np.array([(r * math.cos(t), r * math.sin(t)) for r, t in punkte])


def _bogen(p1, pm, p2, n: int) -> list[tuple[float, float]]:
    """Innere Punkte (polar) des Kreisbogens durch drei Punkte (polar), von p1 ueber pm nach p2."""
    a, m, b = (np.array([r * math.cos(t), r * math.sin(t)]) for r, t in (p1, pm, p2))
    s = np.array([[2 * (m - a)[0], 2 * (m - a)[1]], [2 * (b - a)[0], 2 * (b - a)[1]]])
    mp = np.linalg.solve(s, [m @ m - a @ a, b @ b - a @ a])
    w = [math.atan2(*(q - mp)[::-1]) for q in (a, m, b)]
    w1, w2 = np.unwrap([w[0], w[1]]), np.unwrap([w[0], w[2]])
    if not min(w1[0], w2[1]) <= w1[1] <= max(w1[0], w2[1]):  # ueber die andere Seite
        w2[1] += 2 * math.pi * (1 if w2[1] < w1[0] else -1)
    rho = float(np.linalg.norm(a - mp))
    q = [mp + rho * np.array([math.cos(t), math.sin(t)]) for t in np.linspace(w2[0], w2[1], n)[1:-1]]
    return [(float(np.hypot(*p)), math.atan2(p[1], p[0])) for p in q]


def evolventen_steck(z: int, m: float, alpha: float, x: float, da: float, df: float, rund: float = 0.0,
                     flanke: int = 16) -> np.ndarray:
    """Evolventen-Steckverzahnung (Wellenform, Teilkreis d = m z): Zahndicke am Teilkreis m (pi/2 + 2 x tan alpha),
    Kopfkreis da, Fusskreis df (Nabe: da = Fusskreis, df = Kopfkreis der Nabe, x = Lueckenweite wie bei der Welle)."""
    a = math.radians(alpha)
    d = m * z
    rb = d / 2 * math.cos(a)
    eta = m * (math.pi / 2 + 2 * x * math.tan(a)) / d

    def halb(r):
        return eta + _inv(a) - (_inv(math.acos(rb / r)) if r > rb else 0.0)
    return zahnprofil(z, halb, df / 2, da / 2, flanke, rund)


def keil_steck(n: int, d: float, D: float, B: float) -> np.ndarray:
    """Keilwelle (gerade, parallele Flanken; ISO 14: n x d x D, Keilbreite B); Nabe: Nut der Breite B."""
    return zahnprofil(n, lambda r: math.asin(B / (2 * r)), d / 2, D / 2)


def kerb_steck(z: int, da: float, df: float, winkel: float) -> np.ndarray:
    """Kerbverzahnung: gerade Flanken mit dem eingeschlossenen Winkel winkel (Grad) des Wellenzahns, Zahndicke und
    Lueckenweite auf dem mittleren Durchmesser gleich."""
    rm = (da + df) / 4
    pm = np.array([rm * math.cos(math.pi / (2 * z)), rm * math.sin(math.pi / (2 * z))])
    g = math.radians(winkel / 2)
    richtung = np.array([math.cos(g), -math.sin(g)])

    def halb(r):
        k = pm @ richtung
        t = -k + math.sqrt(k * k - rm * rm + r * r)
        p = pm + t * richtung
        return math.atan2(p[1], p[0])
    return zahnprofil(z, halb, df / 2, da / 2)


def steckteil(p: np.ndarray, b: float, innen: bool = False, rand: float = 4.0):
    """Welle (Prisma der Kontur) bzw. Nabe (Ring mit der Kontur als Bohrung), Achse Z ab z = 0, Laenge b."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    if not innen:
        return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(_draht(p, 0.0)).Face(), gp_Vec(0, 0, b)).Shape()
    profil = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(_draht(p, -1.0)).Face(), gp_Vec(0, 0, b + 2)).Shape()
    ring = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)),
                                    float(np.linalg.norm(p, axis=1).max()) + rand, b).Shape()
    return BRepAlgoAPI_Cut(ring, profil).Shape()


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
