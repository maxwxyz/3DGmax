"""Nur grafisch vorhandene PMI semantisch machen ("Reparieren", PLAN §8.18/§8.28, ohne Qt).

Eine Grafik ohne Semantik (Callout ohne Verknuepfung, in der Liste als Hinweis oder "aus der Grafik abgeleitet")
wird nach Pruefung durch den Anwender zu einer eigenen PMI mit Art, Werten und Flaechen. Sie behaelt die Grafik der
Datei (Pmi.callout): beim Schreiben (step_schreiben) wird nur die Semantik angehaengt und mit dem vorhandenen Callout
verknuepft - die Datei zeigt danach dieselbe Darstellung, jetzt mit Semantik.

Vorschlag:
- Art aus den abgeleiteten Feldern (Text der Grafik) oder aus dem Namen des Callouts (CATIA/NX: "Flatness.1",
  "Linear Size.3", "Simple Datum.2", "Position surfacic profile.1" ...); Werte nur, wo die Grafik Text liefert
  (gestrichene Schrift ist ohne Texterkennung nicht lesbar).
- Flaechen: Enden der Linien und Ecken der Dreiecke (Pfeilspitzen, Bezugsdreieck), die auf einer Flaeche liegen.
"""

from __future__ import annotations

import re

import numpy as np

from .pmi import BEZUG, HINWEIS, MASS, TOLERANZ, Pmi

# Name des Callouts -> (Art, Typ); die erste passende Regel gilt (Reihenfolge beachten: "surfacic profile" vor
# "Position", "Total Runout" vor "Runout")
NAMEN = [
    (r"surfacic profile|surface profile|profile of (a )?surface", TOLERANZ, "ProfileOfSurface"),
    (r"line profile|profile of (a )?line", TOLERANZ, "ProfileOfLine"),
    (r"total runout", TOLERANZ, "TotalRunout"),
    (r"runout", TOLERANZ, "CircularRunout"),
    (r"flatness", TOLERANZ, "Flatness"), (r"straightness", TOLERANZ, "Straightness"),
    (r"circularity|roundness", TOLERANZ, "CircularityOrRoundness"), (r"cylindricity", TOLERANZ, "Cylindricity"),
    (r"perpendicularity", TOLERANZ, "Perpendicularity"), (r"parallelism", TOLERANZ, "Parallelism"),
    (r"angularity", TOLERANZ, "Angularity"), (r"position", TOLERANZ, "Position"),
    (r"concentricity", TOLERANZ, "Concentricity"), (r"coaxiality", TOLERANZ, "Coaxiality"),
    (r"symmetry", TOLERANZ, "Symmetry"),
    (r"datum target", BEZUG, "DatumTarget"), (r"datum", BEZUG, "Datum"),
    (r"angular size", MASS, "Size_Angular"), (r"angular|angle", MASS, "Location_Angular"),
    (r"diameter", MASS, "Size_Diameter"), (r"radius", MASS, "Size_Radius"),
    (r"linear size|size", MASS, ""),  # Groesse: Art aus den Flaechen
    (r"distance|linear dimension|dimension", MASS, "Location_LinearDistance"),
]
FELDER = ("nennwert", "oben", "unten", "grenzmass", "passung", "wert", "zone", "zonen_wert", "material",
          "modifikatoren", "bezuege")


def reparierbar(p, grafik: dict) -> bool:
    """Nur grafische PMI aus der Datei mit eigener Grafik (Callout)."""
    return (not p.semantisch and p.quelle != "eigen" and p.step_id > 0 and p.step_id in grafik
            and not grafik[p.step_id].erzeugt)


def aus_name(name: str) -> tuple[str, str] | None:
    """(Art, Typ) aus dem Namen eines Callouts; None, wenn nichts passt (z. B. "Text.1")."""
    for muster, art, typ in NAMEN:
        if re.search(rf"\b(?:{muster})\b", name or "", re.I):
            return art, typ
    return None


def _form(flaechen, modell) -> str:
    """Groessenmass nach den Flaechen: Zylinder -> Durchmesser, zwei Ebenen -> Dicke bzw. Abstand."""
    from .toleranzzone import _achsen
    fl = [modell.flaechen[i] for i in sorted(flaechen) if i < len(modell.flaechen)]
    if fl and _achsen(fl[:1]):
        return "Size_Diameter"
    return "Size_Thickness" if len(fl) == 2 else "Location_LinearDistance"


def vorschlag(p, g, modell) -> Pmi:
    """Eigene PMI als Startwert fuer die Pruefung: Art, Werte (soweit lesbar), Flaechen, Verweis auf den Callout."""
    art, typ = (p.art, p.typ) if p.art != HINWEIS and p.typ else (aus_name(p.name or (g.name if g else "")) or
                                                                  (TOLERANZ, ""))
    neu = Pmi(art, typ=typ, name=p.name if art == BEZUG and re.fullmatch(r"[A-Z]{1,2}", p.name or "") else "")
    for k in FELDER:
        if p.art == art and getattr(p, k, None) not in (None, "", []):
            setattr(neu, k, getattr(p, k))
    neu.flaechen = flaechen_vorschlag(g, modell) if g is not None else set()
    if art == MASS and not typ:
        neu.typ = _form(neu.flaechen, modell)
    neu.callout, neu.nur_grafik_text = p.step_id, p.nur_grafik_text or p.name
    return neu


def _punkte(g) -> np.ndarray:
    """Kandidaten fuer Beruehrpunkte: Enden der Linienzuege, Ecken gefuellter Dreiecke (Pfeile, Bezugsdreieck)."""
    pts = [l[i] for l in g.linien if len(l) > 1 for i in (0, -1)]
    pts += [q for p, _ in g.dreiecke for q in np.asarray(p)]
    return np.array(pts, float).reshape(-1, 3)


def flaechen_vorschlag(g, modell, max_punkte: int = 400) -> set[int]:
    """Flaechen, auf denen Pfeilspitzen, Hinweislinien oder das Bezugsdreieck enden (Abstand < 0,2 % der
    Modelldiagonale)."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.gp import gp_Pnt
    box = Bnd_Box()
    brepbndlib.Add(modell.form, box)
    lo, hi = np.array(box.Get()[:3]), np.array(box.Get()[3:])
    tol = 2e-3 * (float(np.linalg.norm(hi - lo)) or 1.0)
    pts = _punkte(g)
    pts = pts[np.all((pts >= lo - tol) & (pts <= hi + tol), axis=1)][:max_punkte]
    if not len(pts):
        return set()
    grenzen = []
    for f in modell.flaechen:
        b = Bnd_Box()
        brepbndlib.Add(f, b)
        grenzen.append(np.array(b.Get()) if not b.IsVoid() else None)
    out = set()
    for q in np.unique(np.round(pts, 6), axis=0):
        nah = [i for i, b in enumerate(grenzen) if b is not None and np.all(q >= b[:3] - tol) and np.all(q <= b[3:] + tol)]
        if not nah:
            continue
        v = BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, q))).Vertex()
        abst = []
        for i in nah:
            d = BRepExtrema_DistShapeShape(v, modell.flaechen[i])
            if d.IsDone() and d.NbSolution() > 0:
                abst.append((d.Value(), i))
        if abst and min(abst)[0] < tol:
            out.add(min(abst)[1])
    return out
