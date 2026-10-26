"""Tolerierungsberater: PMI-Vorschlaege fuer die gewaehlten Flaechen (ohne Qt).

Regeln (Stufe 1, nach gaengiger Tolerierungspraxis):
- Zylinder (Bohrung/Zapfen): Durchmesser mit Passung (Bohrung H7, Welle h7) und Position Ø mit Ⓜ zum Bezugssystem.
- Ebene: Ebenheit; ist noch kein Bezug vergeben, Vorschlag als Bezug.
- Zwei parallele Ebenen: Abstand bzw. Breite (gegenlaeufige Normalen) und Parallelitaet zum Bezug.
- Zwei senkrechte Ebenen: Rechtwinkligkeit der zweiten zur ersten.
- Kegel: Kegelwinkel; Kugel: Kugeldurchmesser.
Werte sind Startwerte (aus der Geometrie gemessen bzw. typische Toleranzen) und werden vom Nutzer angepasst.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .pmi import BEZUG, BezugsRef, MASS, TOLERANZ, Pmi


@dataclass
class Vorschlag:
    pmi: Pmi
    grund: str  # Begruendung (Anzeige ueber tr())


def _flaeche_info(f):
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
    from OCC.Core.TopAbs import TopAbs_REVERSED
    if BRep_Tool.Surface(f) is None:
        return None
    s = BRepAdaptor_Surface(f, True)
    typ = s.GetType()
    rev = f.Orientation() == TopAbs_REVERSED
    if typ == GeomAbs_Plane:
        n = s.Plane().Axis().Direction()
        v = (n.X(), n.Y(), n.Z())
        if rev:
            v = tuple(-c for c in v)
        p = s.Plane().Location()
        return "ebene", {"normale": v, "punkt": (p.X(), p.Y(), p.Z())}
    if typ == GeomAbs_Cylinder:
        u0, u1, _, _ = breptools.UVBounds(f)
        return "zylinder", {"r": s.Cylinder().Radius(), "bohrung": rev, "voll": (u1 - u0) >= 2 * math.pi - 1e-6}
    if typ == GeomAbs_Cone:
        return "kegel", {"winkel": 2 * math.degrees(abs(s.Cone().SemiAngle()))}
    if typ == GeomAbs_Sphere:
        return "kugel", {"r": s.Sphere().Radius()}
    return "sonst", {}


def _haupt_bezugssystem(pmi: list) -> list[BezugsRef]:
    """Haeufigstes Bezugssystem der vorhandenen Toleranzen (Vorschlag fuer neue Lagetoleranzen)."""
    systeme = Counter(tuple((b.name, b.stelle) for b in p.bezuege) for p in pmi if p.art == TOLERANZ and p.bezuege)
    if not systeme:
        namen = sorted(p.name for p in pmi if p.art == BEZUG and p.typ == "Datum")[:3]
        return [BezugsRef(n, i) for i, n in enumerate(namen, 1)]
    return [BezugsRef(n, s) for n, s in systeme.most_common(1)[0][0]]


def _naechster_bezug(pmi: list) -> str:
    vergeben = {p.name for p in pmi if p.art == BEZUG}
    return next(c for c in "ABCDEFGHJKLMNPRSTUVWXYZ" if c not in vergeben)


def vorschlaege(flaechen_idx: list[int], modell, pmi: list) -> list[Vorschlag]:
    import numpy as np
    roh = [(i, _flaeche_info(modell.flaechen[i])) for i in flaechen_idx]
    infos = [(i, x[1]) for i, x in roh if x is not None]
    arten = [x[0] for _, x in roh if x is not None]
    drf = _haupt_bezugssystem(pmi)
    out: list[Vorschlag] = []
    alle = set(flaechen_idx)
    if infos and all(a == "zylinder" for a in arten):
        r = infos[0][1]["r"]
        if all(abs(x["r"] - r) < 1e-6 for _, x in infos):  # Halbschalen derselben Bohrung zusammen
            bohrung = infos[0][1]["bohrung"]
            out.append(Vorschlag(Pmi(MASS, "Size_Diameter", "", nennwert=round(2 * r, 4),
                                     passung="H7" if bohrung else "h7", flaechen=alle),
                                 "Bohrung: Passmaß H7" if bohrung else "Welle/Zapfen: Passmaß h7"))
            out.append(Vorschlag(Pmi(TOLERANZ, "Position", "", wert=0.1, material="M", modifikatoren=["Diameter"],
                                     bezuege=list(drf), flaechen=alle),
                                 "Lage der Achse zum Bezugssystem, Ⓜ für Montierbarkeit"))
    elif len(infos) == 1 and arten[0] == "ebene":
        out.append(Vorschlag(Pmi(TOLERANZ, "Flatness", "", wert=0.05, flaechen=alle), "Form der Funktionsfläche"))
        if not any(p.art == BEZUG for p in pmi) or len(drf) < 3:
            out.append(Vorschlag(Pmi(BEZUG, "Datum", _naechster_bezug(pmi), flaechen=alle),
                                 "Große ebene Anlagefläche als Bezug"))
    elif len(infos) == 2 and arten == ["ebene", "ebene"]:
        (ia, a), (ib, b) = infos
        na, nb = np.array(a["normale"]), np.array(b["normale"])
        cos = float(na @ nb)
        if abs(abs(cos) - 1) < 1e-6:
            abstand = abs(float((np.array(b["punkt"]) - np.array(a["punkt"])) @ na))
            breite = cos < 0 and float((np.array(b["punkt"]) - np.array(a["punkt"])) @ na) < 0
            out.append(Vorschlag(Pmi(MASS, "Size_Thickness" if breite else "Location_LinearDistance", "",
                                     nennwert=round(abstand, 4), oben=0.1, unten=-0.1, flaechen=alle),
                                 "Breite zwischen gegenüberliegenden Flächen" if breite else "Abstand paralleler Flächen"))
            bez = [r for r in drf[:1]] or [BezugsRef(_naechster_bezug(pmi), 1)]
            out.append(Vorschlag(Pmi(TOLERANZ, "Parallelism", "", wert=0.05, bezuege=bez, flaechen={ib}),
                                 "Richtung der zweiten Fläche zum Bezug"))
        elif abs(cos) < 1e-6:
            bez = [r for r in drf[:1]] or [BezugsRef(_naechster_bezug(pmi), 1)]
            out.append(Vorschlag(Pmi(TOLERANZ, "Perpendicularity", "", wert=0.05, bezuege=bez, flaechen={ib}),
                                 "Rechtwinkligkeit zur Bezugsfläche"))
        else:
            out.append(Vorschlag(Pmi(MASS, "Location_Angular", "", nennwert=round(math.degrees(math.acos(abs(cos))), 3),
                                     oben=0.5, unten=-0.5, flaechen=alle), "Winkel zwischen den Flächen"))
    elif len(infos) == 1 and arten[0] == "kegel":
        out.append(Vorschlag(Pmi(MASS, "Size_Angular", "", nennwert=round(infos[0][1]["winkel"], 3), oben=0.5,
                                 unten=-0.5, flaechen=alle), "Kegelwinkel"))
    elif len(infos) == 1 and arten[0] == "kugel":
        out.append(Vorschlag(Pmi(MASS, "Size_SphericalDiameter", "", nennwert=round(2 * infos[0][1]["r"], 4),
                                 oben=0.05, unten=-0.05, flaechen=alle), "Kugeldurchmesser"))
    if not out and infos:
        out.append(Vorschlag(Pmi(TOLERANZ, "ProfileOfSurface", "", wert=0.2, bezuege=list(drf), flaechen=alle),
                             "Allgemeine Flächenform zum Bezugssystem"))
    return out


GRUENDE = ("Bohrung: Passmaß H7", "Welle/Zapfen: Passmaß h7", "Lage der Achse zum Bezugssystem, Ⓜ für Montierbarkeit",
           "Form der Funktionsfläche", "Große ebene Anlagefläche als Bezug", "Breite zwischen gegenüberliegenden Flächen",
           "Abstand paralleler Flächen", "Richtung der zweiten Fläche zum Bezug", "Rechtwinkligkeit zur Bezugsfläche",
           "Winkel zwischen den Flächen", "Kegelwinkel", "Kugeldurchmesser", "Allgemeine Flächenform zum Bezugssystem")
