"""Geometrievergleich zweier Staende: Abweichung Oberflaeche zu Oberflaeche, Flaechenstatus, Zuordnung.

Ablauf:
1. Beide Modelle tessellieren und gleichmaessig abtasten; Abtastpunkte auf die exakte eigene Flaeche projizieren.
2. Punkte von B (ausgerichtet) gegen A: schnell ueber das Netz, kritische Punkte exakt gegen die B-Rep-Flaechen
   (Kandidat + Nachbarflaechen, Rueckfall: ganze Form). Ebenso A gegen B (findet Entferntes).
3. Flaechenstatus: gleich (alle Punkte innerhalb Toleranz), geaendert (teils), neu / entfernt (keiner).
4. Zuordnung B -> A: die A-Flaeche, auf die die meisten Punkte einer B-Flaeche fallen (fuer den PMI-Vergleich).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCC.Core.gp import gp_Pnt
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCC.Core.TopExp import topexp
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

from .ausrichten import Ausrichtung, NetzAbstand, abtasten, tesselliere

GLEICH, GEAENDERT, NEU, ENTFERNT = "gleich", "geaendert", "neu", "entfernt"


@dataclass
class Seite:
    """Vorbereitete Daten eines Modells."""
    flaechen: list
    netze: list
    netz: NetzAbstand
    punkte: np.ndarray  # Abtastpunkte auf der exakten Oberflaeche
    punkt_flaeche: np.ndarray  # Flaechenindex je Punkt
    nachbarn: dict[int, set[int]]
    feinheit: float


@dataclass
class GeoErgebnis:
    status_b: dict[int, str]  # Flaeche in B -> Status
    status_a: dict[int, str]  # Flaeche in A -> Status (nur entfernt/geaendert interessant)
    zuordnung: dict[int, int]  # Flaeche B -> Flaeche A
    zuordnung_ab: dict[int, int]  # Flaeche A -> Flaeche B (Gegenrichtung, fuer anders unterteilte Flaechen)
    max_abw_b: dict[int, float]  # groesste Abweichung je B-Flaeche (mm)
    punkte_b: np.ndarray  # Abtastpunkte B (in A-Koordinaten)
    abw_b: np.ndarray  # Abweichung je Punkt (mm)
    toleranz: float
    ausrichtung: Ausrichtung | None = None
    zaehler: dict[str, int] = field(default_factory=dict)


def _nachbarn(flaechen, index_von) -> dict[int, set[int]]:
    """Flaechen, die eine Kante teilen."""
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound
    comp = TopoDS_Compound()
    bb = BRep_Builder()
    bb.MakeCompound(comp)
    for f in flaechen:
        bb.Add(comp, f)
    karte = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(comp, TopAbs_EDGE, TopAbs_FACE, karte)
    out: dict[int, set[int]] = {i: set() for i in range(len(flaechen))}
    for k in range(1, karte.Size() + 1):
        idx = [index_von(f) for f in karte.FindFromIndex(k)]
        idx = [i for i in idx if i is not None]
        for i in idx:
            out[i].update(j for j in idx if j != i)
    return out


def _auf_flaeche(punkte: np.ndarray, flaeche_idx: np.ndarray, flaechen) -> np.ndarray:
    """Netzpunkte auf die exakte Flaeche projizieren (Sehnenfehler des Netzes entfernen)."""
    out = punkte.copy()
    flaechen_geom = {}
    for j, (p, fi) in enumerate(zip(punkte, flaeche_idx)):
        if fi not in flaechen_geom:
            flaechen_geom[fi] = BRep_Tool.Surface(flaechen[fi])
        pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*p), flaechen_geom[fi])
        if pr.IsDone() and pr.NbPoints() > 0:
            q = pr.NearestPoint()
            out[j] = (q.X(), q.Y(), q.Z())
    return out


def bereite_vor(modell, anzahl: int = 8000, feinheit: float | None = None) -> Seite:
    flaechen = modell.flaechen
    if feinheit is None:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        box = Bnd_Box()
        for f in flaechen:
            brepbndlib.Add(f, box)
        x0, y0, z0, x1, y1, z1 = box.Get()
        diag = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0]))
        feinheit = min(max(diag * 5e-4, 0.01), 0.2)
    netze = tesselliere(flaechen, feinheit)
    punkte, fi = abtasten(netze, anzahl)
    punkte = _auf_flaeche(punkte, fi, flaechen)
    return Seite(flaechen, netze, NetzAbstand(netze), punkte, fi, _nachbarn(flaechen, modell.flaechen_index),
                 feinheit)


def _exakt(punkt, kandidaten, flaechen, ganze_form=None) -> tuple[float, int]:
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*punkt)).Vertex()
    beste, beste_f = np.inf, -1
    for fi in kandidaten:
        e = BRepExtrema_DistShapeShape(v, flaechen[fi], Extrema_ExtFlag_MIN)
        if e.IsDone() and e.NbSolution() and e.Value() < beste:
            beste, beste_f = e.Value(), fi
    return beste, beste_f


def abstaende(punkte: np.ndarray, ziel: Seite, toleranz: float, exakt_alle: bool = False):
    """Abstand von Punkten zur Oberflaeche 'ziel' und getroffene Flaeche.

    Netzwert fuer alle Punkte; exakt nachgerechnet werden Punkte, deren Netzwert nicht klar unter der
    Toleranz liegt (oder alle mit exakt_alle).
    """
    d, _, f = ziel.netz.abfrage(punkte)
    grenze = max(toleranz - 2 * ziel.feinheit, 0.0)
    kritisch = np.arange(len(punkte)) if exakt_alle else np.where(d > grenze)[0]
    for j in kritisch:
        kand = {int(f[j])} | ziel.nachbarn.get(int(f[j]), set())
        dj, fj = _exakt(punkte[j], kand, ziel.flaechen)
        if dj > d[j] + 3 * ziel.feinheit or not np.isfinite(dj):
            # Netz hat vermutlich die falsche Wandseite gefunden: alle Flaechen in der Naehe pruefen
            _, nahe = ziel.netz.baum.query(punkte[j], k=min(64, len(ziel.netz.a)))
            kand2 = set(ziel.netz.flaeche[np.atleast_1d(nahe)].tolist()) - kand
            d2, f2 = _exakt(punkte[j], kand2, ziel.flaechen) if kand2 else (np.inf, -1)
            if d2 < dj:
                dj, fj = d2, f2
        if np.isfinite(dj):
            d[j], f[j] = dj, fj
    return d, f


def _status(abw: np.ndarray, flaeche: np.ndarray, anzahl: int, toleranz: float, fehlend: str,
            suchweite: float):
    """gleich: alle Punkte in Toleranz; geaendert: Gegenstueck innerhalb der Suchweite; sonst neu/entfernt."""
    status, maxabw = {}, {}
    for fi in range(anzahl):
        sel = flaeche == fi
        if not sel.any():
            status[fi] = GLEICH  # zu klein zum Abtasten: als gleich werten
            maxabw[fi] = 0.0
            continue
        innen = abw[sel] <= toleranz
        nahe = abw[sel] <= suchweite
        maxabw[fi] = float(abw[sel].max())
        if innen.all():
            status[fi] = GLEICH
        else:
            status[fi] = GEAENDERT if (innen.mean() >= 0.05 or nahe.mean() >= 0.5) else fehlend
    return status, maxabw


def vergleiche(modell_a, modell_b, ausrichtung: Ausrichtung | None = None, toleranz: float = 0.01,
               anzahl: int = 8000, suchweite: float = 2.0) -> GeoErgebnis:
    """toleranz: bis hier gilt eine Flaeche als gleich; suchweite: bis hier als geaendert (sonst neu/entfernt)."""
    a, b = bereite_vor(modell_a, anzahl), bereite_vor(modell_b, anzahl)
    m = np.eye(4) if ausrichtung is None else ausrichtung.matrix
    pb = b.punkte @ m[:3, :3].T + m[:3, 3]
    # B im A-System: Netz von B transformieren fuer die Gegenrichtung
    if ausrichtung is not None and not np.allclose(m, np.eye(4)):
        b = _transformiert(b, modell_b, ausrichtung)
    abw_b, treffer_a = abstaende(pb, a, toleranz)
    abw_a, treffer_b = abstaende(a.punkte, b, toleranz)
    status_b, max_b = _status(abw_b, b.punkt_flaeche, len(b.flaechen), toleranz, NEU, suchweite)
    status_a, _ = _status(abw_a, a.punkt_flaeche, len(a.flaechen), toleranz, ENTFERNT, suchweite)
    zuordnung = {}
    for fi in range(len(b.flaechen)):
        sel = (b.punkt_flaeche == fi) & (abw_b <= suchweite)
        if sel.any():
            zuordnung[fi] = Counter(treffer_a[sel].tolist()).most_common(1)[0][0]
    zuordnung_ab = {}
    for fi in range(len(a.flaechen)):
        sel = (a.punkt_flaeche == fi) & (abw_a <= suchweite)
        if sel.any():
            zuordnung_ab[fi] = Counter(treffer_b[sel].tolist()).most_common(1)[0][0]
    zaehler = Counter(status_b.values())
    zaehler[ENTFERNT] = sum(1 for s in status_a.values() if s == ENTFERNT)
    return GeoErgebnis(status_b, status_a, zuordnung, zuordnung_ab, max_b, pb, abw_b, toleranz, ausrichtung,
                       dict(zaehler))


def _transformiert(seite: Seite, modell_b, ausrichtung: Ausrichtung) -> Seite:
    """Flaechen und Netz von B in das A-System bringen (fuer die Richtung A -> B)."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.TopoDS import topods
    trsf = ausrichtung.gp_trsf()
    flaechen = [topods.Face(BRepBuilderAPI_Transform(f, trsf, True).Shape()) for f in seite.flaechen]
    m = ausrichtung.matrix
    netze = [(p @ m[:3, :3].T + m[:3, 3] if len(p) else p, t) for p, t in seite.netze]
    punkte = seite.punkte @ m[:3, :3].T + m[:3, 3]
    return Seite(flaechen, netze, NetzAbstand(netze), punkte, seite.punkt_flaeche, seite.nachbarn, seite.feinheit)
