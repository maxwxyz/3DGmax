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
    basis: np.ndarray | None = None  # Instanz -> Flaechenindex des Modells (None: eine Instanz je Flaeche)

    def index(self, instanzen: np.ndarray) -> np.ndarray:
        """Instanznummern (Abtastpunkte, Treffer) auf die Flaechenindizes des Modells abbilden."""
        return instanzen if self.basis is None else self.basis[instanzen]


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
    instanzen_b: dict[tuple, str] = field(default_factory=dict)  # instanz_schluessel -> Status (mehrfach verbaut)
    entfernt_a: list | None = None  # entfernte Flaechen-Instanzen von A mit Lage (None: wie status_a)


def instanz_schluessel(idx: int, flaeche) -> tuple:
    """Flaechenindex und Lage (gerundet): gleich fuer dieselbe Instanz, egal ueber welchen Baumweg erreicht."""
    t = flaeche.Location().Transformation()
    return (idx,) + tuple(round(t.Value(i, j), 5) + 0.0 for i in (1, 2, 3) for j in (1, 2, 3, 4))


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
        if flaechen_geom[fi] is None:
            continue  # Netzflaeche: Knoten liegen schon auf der Oberflaeche
        pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*p), flaechen_geom[fi])
        if pr.IsDone() and pr.NbPoints() > 0:
            q = pr.NearestPoint()
            out[j] = (q.X(), q.Y(), q.Z())
    return out


def _instanzen(modell) -> tuple[list, np.ndarray | None]:
    """Alle Flaechen mit ihrer Lage (jede Instanz eines mehrfach verbauten Teils einzeln) und ihr Modellindex."""
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    form = getattr(modell, "form", None)
    if form is None:
        return modell.flaechen, None
    gesehen, liste, basis = set(), [], []
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        k = f.Oriented(0).__hash__()  # Lage zaehlt (anders als modell.flaechen_index)
        idx = modell.flaechen_index(f)
        if k in gesehen or idx is None:
            continue
        gesehen.add(k)
        liste.append(f)
        basis.append(idx)
    if len(liste) <= len(modell.flaechen):
        return modell.flaechen, None
    return liste, np.asarray(basis, dtype=int)


def bereite_vor(modell, anzahl: int = 8000, feinheit: float | None = None) -> Seite:
    """Abtastung; mehrfach verbaute Teile werden je Instanz abgetastet (Flaechenstatus fasst sie zusammen)."""
    flaechen, basis = _instanzen(modell)
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
    if basis is None:
        nachbarn = _nachbarn(flaechen, modell.flaechen_index)
    else:
        nummer = {f.Oriented(0).__hash__(): i for i, f in enumerate(flaechen)}
        nachbarn = _nachbarn(flaechen, lambda f: nummer.get(f.Oriented(0).__hash__()))
    return Seite(flaechen, netze, NetzAbstand(netze), punkte, fi, nachbarn, feinheit, basis)


def _exakt(punkt, kandidaten, flaechen, ganze_form=None) -> tuple[float, int]:
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*punkt)).Vertex()
    beste, beste_f = np.inf, -1
    for fi in kandidaten:
        if BRep_Tool.Surface(flaechen[fi]) is None:
            continue  # Netzflaeche: nur Netzabstand
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
    instanzen_b = b.flaechen if b.basis is not None else []
    m = np.eye(4) if ausrichtung is None else ausrichtung.matrix
    pb = b.punkte @ m[:3, :3].T + m[:3, 3]
    # B im A-System: Netz von B transformieren fuer die Gegenrichtung
    if ausrichtung is not None and not np.allclose(m, np.eye(4)):
        b = _transformiert(b, modell_b, ausrichtung)
    abw_b, treffer_a = abstaende(pb, a, toleranz)
    abw_a, treffer_b = abstaende(a.punkte, b, toleranz)
    # Instanzen auf die Flaechen der Modelle abbilden (eine geaenderte Instanz macht die Flaeche geaendert)
    flaeche_b, flaeche_a = b.index(b.punkt_flaeche), a.index(a.punkt_flaeche)
    treffer_a, treffer_b = a.index(treffer_a), b.index(treffer_b)
    n_b, n_a = len(modell_b.flaechen), len(modell_a.flaechen)
    status_b, max_b = _status(abw_b, flaeche_b, n_b, toleranz, NEU, suchweite)
    status_a, _ = _status(abw_a, flaeche_a, n_a, toleranz, ENTFERNT, suchweite)
    zuordnung = {}
    for fi in range(n_b):
        sel = (flaeche_b == fi) & (abw_b <= suchweite)
        if sel.any():
            zuordnung[fi] = Counter(treffer_a[sel].tolist()).most_common(1)[0][0]
    zuordnung_ab = {}
    for fi in range(n_a):
        sel = (flaeche_a == fi) & (abw_a <= suchweite)
        if sel.any():
            zuordnung_ab[fi] = Counter(treffer_b[sel].tolist()).most_common(1)[0][0]
    zaehler = Counter(status_b.values())
    zaehler[ENTFERNT] = sum(1 for s in status_a.values() if s == ENTFERNT)
    erg = GeoErgebnis(status_b, status_a, zuordnung, zuordnung_ab, max_b, pb, abw_b, toleranz, ausrichtung,
                      dict(zaehler))
    # Mehrfach verbaute Teile: Status je Instanz fuer die Anzeige (der Flaechenstatus fasst die Instanzen zusammen)
    if instanzen_b:
        st, _ = _status(abw_b, b.punkt_flaeche, len(instanzen_b), toleranz, NEU, suchweite)
        erg.instanzen_b = {instanz_schluessel(int(b.basis[i]), f): st[i] for i, f in enumerate(instanzen_b)}
    if a.basis is not None:
        st, _ = _status(abw_a, a.punkt_flaeche, len(a.flaechen), toleranz, ENTFERNT, suchweite)
        erg.entfernt_a = [a.flaechen[i] for i, s in st.items() if s == ENTFERNT]
    return erg


def _transformiert(seite: Seite, modell_b, ausrichtung: Ausrichtung) -> Seite:
    """Flaechen und Netz von B in das A-System bringen (fuer die Richtung A -> B)."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.TopoDS import topods
    trsf = ausrichtung.gp_trsf()
    flaechen = [topods.Face(BRepBuilderAPI_Transform(f, trsf, True).Shape()) for f in seite.flaechen]
    m = ausrichtung.matrix
    netze = [(p @ m[:3, :3].T + m[:3, 3] if len(p) else p, t) for p, t in seite.netze]
    punkte = seite.punkte @ m[:3, :3].T + m[:3, 3]
    return Seite(flaechen, netze, NetzAbstand(netze), punkte, seite.punkt_flaeche, seite.nachbarn, seite.feinheit,
                 seite.basis)
