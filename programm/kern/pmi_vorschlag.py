"""Tolerierungsberater: PMI-Vorschlaege fuer die gewaehlten Flaechen (ohne Qt).

Regeln (Stufe 1, nach gaengiger Tolerierungspraxis):
- Zylinder (Bohrung/Zapfen): Durchmesser mit Passung (Bohrung H7, Welle h7) und Position Ø mit Ⓜ zum Bezugssystem.
- Ebene: Ebenheit; ist noch kein Bezug vergeben, Vorschlag als Bezug.
- Zwei parallele Ebenen: Abstand bzw. Breite (gegenlaeufige Normalen) und Parallelitaet zum Bezug.
- Zwei senkrechte Ebenen: Rechtwinkligkeit der zweiten zur ersten.
- Kegel: Kegelwinkel; Kugel: Kugeldurchmesser.
Werte sind Startwerte (aus der Geometrie gemessen bzw. typische Toleranzen) und werden vom Nutzer angepasst.

Stufe 2: Toleranzwerte nach ISO-286-IT-Grad bei der Elementgroesse (Form IT6, Richtung IT7, Lage IT8, Profil IT9,
Abstaende +-IT11/2); gleiche Bohrungen auf verschiedenen Achsen als Muster mit gemeinsamer Positionstoleranz;
Abgleich mit den vorhandenen PMI (was es an diesen Flaechen schon gibt, ist markiert und abgewaehlt; eine gewaehlte
Flaeche, die schon Bezug ist, wird nicht noch einmal Bezug; Bezuege ohne Bezugselement werden genannt).
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
    hinweis: str = ""  # Abgleich mit den vorhandenen PMI (schon uebersetzt)
    vorhanden: bool = False  # gleiche Angabe gibt es an diesen Flaechen schon: abgewaehlt vorschlagen

GRAD = {"form": 6, "richtung": 7, "lage": 8, "profil": 9, "abstand": 11}  # IT-Grade der Startwerte


def _wert(art: str, groesse: float, ersatz: float) -> float:
    """Startwert nach IT-Grad bei der Elementgroesse (auf 3 Stellen gerundet), sonst der Ersatzwert."""
    from .iso286 import it
    t = it(GRAD[art], max(groesse, 1.0)) if groesse else None  # in µm
    return max(0.001, round(float(t) / 1000, 3)) if t else ersatz


def _groesse(flaeche) -> float:
    """Ausdehnung einer Flaeche (Diagonale ihres Quaders) als Groesse fuer den IT-Grad."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(flaeche, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    return math.dist((x0, y0, z0), (x1, y1, z1))


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
        ax = s.Cylinder().Axis()
        o, d = ax.Location(), ax.Direction()
        return "zylinder", {"r": s.Cylinder().Radius(), "bohrung": rev, "voll": (u1 - u0) >= 2 * math.pi - 1e-6,
                            "punkt": (o.X(), o.Y(), o.Z()), "achse": (d.X(), d.Y(), d.Z())}
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
    groesse = max((_groesse(modell.flaechen[i]) for i, _ in infos), default=0.0)
    if infos and all(a == "zylinder" for a in arten):
        r = infos[0][1]["r"]
        if all(abs(x["r"] - r) < 1e-6 for _, x in infos):  # Halbschalen derselben Bohrung zusammen
            bohrung = infos[0][1]["bohrung"]
            out.append(Vorschlag(Pmi(MASS, "Size_Diameter", "", nennwert=round(2 * r, 4),
                                     passung="H7" if bohrung else "h7", flaechen=alle),
                                 "Bohrung: Passmaß H7" if bohrung else "Welle/Zapfen: Passmaß h7"))
            muster = _achsen(infos) > 1
            out.append(Vorschlag(Pmi(TOLERANZ, "Position", "", wert=_wert("lage", 2 * r, 0.1), material="M",
                                     modifikatoren=["Diameter"], bezuege=list(drf), flaechen=alle),
                                 "Lochmuster: gemeinsame Positionstoleranz aller Achsen zum Bezugssystem" if muster else
                                 "Lage der Achse zum Bezugssystem, Ⓜ für Montierbarkeit"))
    elif len(infos) == 1 and arten[0] == "ebene":
        out.append(Vorschlag(Pmi(TOLERANZ, "Flatness", "", wert=_wert("form", groesse, 0.05), flaechen=alle),
                             "Form der Funktionsfläche"))
        schon_bezug = any(p.art == BEZUG and p.flaechen & alle for p in pmi)
        if not schon_bezug and (not any(p.art == BEZUG for p in pmi) or len(drf) < 3):
            out.append(Vorschlag(Pmi(BEZUG, "Datum", _naechster_bezug(pmi), flaechen=alle),
                                 "Große ebene Anlagefläche als Bezug"))
    elif len(infos) == 2 and arten == ["ebene", "ebene"]:
        (ia, a), (ib, b) = infos
        na, nb = np.array(a["normale"]), np.array(b["normale"])
        cos = float(na @ nb)
        if abs(abs(cos) - 1) < 1e-6:
            abstand = abs(float((np.array(b["punkt"]) - np.array(a["punkt"])) @ na))
            breite = cos < 0 and float((np.array(b["punkt"]) - np.array(a["punkt"])) @ na) < 0
            t = _wert("abstand", abstand, 0.2) / 2
            out.append(Vorschlag(Pmi(MASS, "Size_Thickness" if breite else "Location_LinearDistance", "",
                                     nennwert=round(abstand, 4), oben=t, unten=-t, flaechen=alle),
                                 "Breite zwischen gegenüberliegenden Flächen" if breite else "Abstand paralleler Flächen"))
            bez = [r for r in drf[:1]] or [BezugsRef(_naechster_bezug(pmi), 1)]
            out.append(Vorschlag(Pmi(TOLERANZ, "Parallelism", "", wert=_wert("richtung", groesse, 0.05), bezuege=bez,
                                     flaechen={ib}),
                                 "Richtung der zweiten Fläche zum Bezug"))
        elif abs(cos) < 1e-6:
            bez = [r for r in drf[:1]] or [BezugsRef(_naechster_bezug(pmi), 1)]
            out.append(Vorschlag(Pmi(TOLERANZ, "Perpendicularity", "", wert=_wert("richtung", groesse, 0.05),
                                     bezuege=bez, flaechen={ib}),
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
        out.append(Vorschlag(Pmi(TOLERANZ, "ProfileOfSurface", "", wert=_wert("profil", groesse, 0.2),
                                 bezuege=list(drf), flaechen=alle), "Allgemeine Flächenform zum Bezugssystem"))
    _abgleich(out, pmi)
    return out


def _achsen(infos) -> int:
    """Anzahl verschiedener Achsen gleich grosser Zylinder (Halbschalen derselben Bohrung zaehlen einmal)."""
    import numpy as np
    achsen: list[tuple] = []
    for _, x in infos:
        p, d = np.array(x.get("punkt", (0, 0, 0)), float), np.array(x.get("achse", (0, 0, 1)), float)
        if not any(abs(abs(float(d @ e)) - 1) < 1e-6 and np.linalg.norm((p - q) - e * float((p - q) @ e)) < 1e-6
                   for q, e in achsen):
            achsen.append((p, d))
    return len(achsen)


def _abgleich(out: list[Vorschlag], pmi: list):
    """Vorschlaege mit den vorhandenen PMI abgleichen: gleiche Art an diesen Flaechen -> vorhanden (abgewaehlt);
    Bezuege ohne Bezugselement nennen."""
    from ..i18n import tr
    merkmale = {p.name for p in pmi if p.art == BEZUG and p.typ == "Datum"}
    for v in out:
        gleich = next((p for p in pmi if p.art == v.pmi.art and p.typ == v.pmi.typ and p.flaechen & v.pmi.flaechen),
                      None)
        if gleich is not None:
            v.vorhanden = True
            v.hinweis = tr("schon vorhanden: {}").format(gleich.wert_text())
        fehlt = [b.name for b in v.pmi.bezuege if not set(b.name.split("-")) <= merkmale]  # auch gemeinsam A-B
        if fehlt and not v.vorhanden:
            v.hinweis = tr("Bezug {} hat noch kein Bezugselement").format(", ".join(fehlt))


GRUENDE = ("Bohrung: Passmaß H7", "Welle/Zapfen: Passmaß h7", "Lage der Achse zum Bezugssystem, Ⓜ für Montierbarkeit",
           "Form der Funktionsfläche", "Große ebene Anlagefläche als Bezug", "Breite zwischen gegenüberliegenden Flächen",
           "Abstand paralleler Flächen", "Richtung der zweiten Fläche zum Bezug", "Rechtwinkligkeit zur Bezugsfläche",
           "Winkel zwischen den Flächen", "Kegelwinkel", "Kugeldurchmesser", "Allgemeine Flächenform zum Bezugssystem",
           "Lochmuster: gemeinsame Positionstoleranz aller Achsen zum Bezugssystem")
