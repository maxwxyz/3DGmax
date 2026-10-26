"""Abweichungs-Farbkarte: vorzeichenbehafteter Abstand des neuen Stands zum alten je Netzknoten.

Vorzeichen: + = neuer Stand liegt ausserhalb des alten Materials (Aufmass), - = innerhalb (Untermass), bezogen
auf die nach aussen zeigende Flaechennormale des alten Stands.
Genauigkeit: Kandidatenflaeche ueber das Netz, Wert durch Projektion auf die exakte Flaeche; nur wenn die
Projektion unplausibel ist (Fortsetzung der Flaeche ausserhalb ihrer Berandung), bleibt der Netzwert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from OCC.Core.BRep import BRep_Tool
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCC.Core.gp import gp_Pnt, gp_Vec
from OCC.Core.TopAbs import TopAbs_REVERSED

from .ausrichten import Ausrichtung, NetzAbstand, tesselliere
from .vergleich_geo import _exakt


@dataclass
class Karte:
    netze: list  # je Flaeche des neuen Stands: (punkte (n,3) im alten System, dreiecke (m,3))
    werte: list  # je Flaeche: Abweichung je Knoten (mm, mit Vorzeichen)
    feinheit: float

    def alle(self) -> np.ndarray:
        return np.concatenate([w for w in self.werte if len(w)]) if self.werte else np.zeros(0)

    def bereich(self) -> tuple[float, float]:
        w = self.alle()
        return (float(w.min()), float(w.max())) if len(w) else (0.0, 0.0)

    def gesamt(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(Knoten, Dreiecke, Werte) aller Flaechen in einem Netz."""
        if getattr(self, "_gesamt", None) is None:
            pts, tris, ws, off = [], [], [], 0
            for (p, t), w in zip(self.netze, self.werte):
                if len(t) and len(w):
                    pts.append(p); tris.append(t + off); ws.append(w)
                    off += len(p)
            self._gesamt = ((np.vstack(pts), np.vstack(tris), np.concatenate(ws)) if pts else
                            (np.zeros((0, 3)), np.zeros((0, 3), dtype=int), np.zeros(0)))
        return self._gesamt

    def am_strahl(self, ursprung, richtung) -> tuple[np.ndarray, float] | None:
        """Erster Treffer eines Sichtstrahls auf dem Netz: (Punkt, interpolierte Abweichung)."""
        pts, tri, w = self.gesamt()
        if not len(tri):
            return None
        o, r = np.asarray(ursprung, float), np.asarray(richtung, float)
        a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
        e1, e2 = b - a, c - a
        h = np.cross(r, e2)
        det = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o - a
        u = inv * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = inv * (q @ r)
        t = inv * np.einsum("ij,ij->i", e2, q)
        treffer = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        if not treffer.any():
            return None
        i = int(np.where(treffer)[0][np.argmin(t[treffer])])
        wert = (1 - u[i] - v[i]) * w[tri[i, 0]] + u[i] * w[tri[i, 1]] + v[i] * w[tri[i, 2]]
        return o + t[i] * r, float(wert)


def _feinheit(flaechen) -> float:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    box = Bnd_Box()
    for f in flaechen:
        brepbndlib.Add(f, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    return min(max(float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) * 5e-4, 0.01), 0.2)


def _flaechen_mit_lage(form) -> list:
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    out, ex = [], TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        out.append(topods.Face(ex.Current()))
        ex.Next()
    return out


def _diagonale(netze) -> float:
    alle = [p for p, _ in netze if len(p)]
    if not alle:
        return 1.0
    a = np.vstack(alle)
    return float(np.linalg.norm(a.max(axis=0) - a.min(axis=0))) or 1.0


def _ist_ebene(flaeche) -> bool:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane
    if BRep_Tool.Surface(flaeche) is None:
        return False  # Netzflaeche
    return BRepAdaptor_Surface(flaeche, True).GetType() == GeomAbs_Plane


def verfeinere(pts: np.ndarray, tri: np.ndarray, laenge: float, runden: int = 6):
    """Dreiecke an Kantenmitten teilen, bis keine Kante laenger als 'laenge' ist (Knoten gemeinsam genutzt)."""
    pts = [tuple(p) for p in pts]
    tri = [tuple(t) for t in tri]
    for _ in range(runden):
        mitten: dict[tuple[int, int], int] = {}
        neu, geteilt = [], False

        def mitte(a, b):
            k = (min(a, b), max(a, b))
            if k not in mitten:
                pa, pb = pts[a], pts[b]
                pts.append(((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, (pa[2] + pb[2]) / 2))
                mitten[k] = len(pts) - 1
            return mitten[k]

        for a, b, c in tri:
            pa, pb, pc = np.array(pts[a]), np.array(pts[b]), np.array(pts[c])
            if max(np.linalg.norm(pa - pb), np.linalg.norm(pb - pc), np.linalg.norm(pc - pa)) <= laenge:
                neu.append((a, b, c))
                continue
            geteilt = True
            ab, bc, ca = mitte(a, b), mitte(b, c), mitte(c, a)
            neu += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        tri = neu
        if not geteilt:
            break
    # Nachbardreiecke, die nicht geteilt wurden, haben T-Knoten: fuer die Farbdarstellung unkritisch
    return np.array(pts), np.array(tri, dtype=int)


class _Flaeche:
    """Exakte Flaeche des alten Stands: Projektion mit Lagepruefung und Normale nach aussen."""

    def __init__(self, f, rand: float = 1e-6):
        from OCC.Core.BRepClass import BRepClass_FaceClassifier
        self.f, self.geom = f, BRep_Tool.Surface(f)
        # Ebenen: Parameter = Laenge -> Knoten knapp ausserhalb der Berandung (Sehnen an Bohrungen) zulassen
        self.rand = rand if _ist_ebene(f) else 1e-6
        self.klassifikator = BRepClass_FaceClassifier()
        self.umgedreht = f.Orientation() == TopAbs_REVERSED

    def projektion(self, p, innen: bool = True):
        """(Abstand mit Vorzeichen, |Abstand|) oder None; innen=True: Fusspunkt muss in der Berandung liegen."""
        from OCC.Core.gp import gp_Pnt2d
        from OCC.Core.TopAbs import TopAbs_OUT
        if self.geom is None:
            return None  # Netzflaeche: Wert kommt aus dem Netzabstand
        pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*p), self.geom)
        if not pr.IsDone() or pr.NbPoints() == 0:
            return None
        u, v = pr.LowerDistanceParameters()
        if innen:
            self.klassifikator.Perform(self.f, gp_Pnt2d(u, v), self.rand)
            if self.klassifikator.State() == TopAbs_OUT:
                return None
        pnt, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
        self.geom.D1(u, v, pnt, du, dv)
        n = du.Crossed(dv)
        if n.Magnitude() < 1e-12:
            return None
        n.Normalize()
        if self.umgedreht:
            n.Reverse()
        s = pr.NearestPoint()
        diff = np.asarray(p) - (s.X(), s.Y(), s.Z())
        abstand = float(pr.LowerDistance())
        return (abstand if float(np.dot(diff, (n.X(), n.Y(), n.Z()))) >= 0 else -abstand), abstand


def _netz_wert(netz: NetzAbstand, p, alt_f, k: int = 64):
    """Abstand mit Vorzeichen zu Netzflaechen: viele Kandidatendreiecke exakt, Vorzeichen aus der Dreiecksnormale."""
    for anzahl in (k, 8 * k):  # schmale, lange Dreiecke (Zylinder in STL): Mittelpunkte liegen weit weg
        _, kand = netz.baum.query(p, k=min(anzahl, len(netz.a)))
        d, q, fl = netz._naechste(np.asarray(p, float)[None], np.atleast_2d(kand))
        if d[0] < 1e-6:
            break
    t = netz.letzte_dreiecke[0]
    n = np.cross(netz.b[t] - netz.a[t], netz.c[t] - netz.a[t])
    if alt_f[int(fl[0])].Orientation() == TopAbs_REVERSED:
        n = -n
    vz = 1.0 if float(np.dot(np.asarray(p) - q[0], n)) >= 0 else -1.0
    return vz * float(d[0]), float(d[0])


def _beste(p, kand, flaechen: dict, alt_f, rand: float):
    """Kleinster Abstand ueber die Projektion auf die Kandidatenflaechen (Fusspunkt innen)."""
    beste = None
    for fi in kand:
        if fi not in flaechen:
            flaechen[fi] = _Flaeche(alt_f[fi], rand)
        erg = flaechen[fi].projektion(p)
        if erg is not None and (beste is None or erg[1] < beste[1]):
            beste = erg
    return beste


def berechne(modell_alt, modell_neu, ausrichtung: Ausrichtung | None = None, feinheit: float | None = None,
             fortschritt=lambda anteil: None, teilung: float = 40.0) -> Karte:
    """Abweichung aller Netzknoten des neuen Stands (im System des alten) zum alten Stand.

    Je Knoten: Kandidatenflaechen aus dem Netz des alten Stands, Projektion auf jede (Fusspunkt innerhalb der
    Berandung), kleinster Abstand gewinnt; liegt kein Fusspunkt innen (Kante/Ecke), exakt per BRepExtrema.
    """
    # alle Flaechen mit Lage (jedes Exemplar einer Baugruppe einzeln; modell.flaechen fasst Exemplare zusammen)
    alt_f, neu_f = _flaechen_mit_lage(modell_alt.form), _flaechen_mit_lage(modell_neu.form)
    feinheit = feinheit or _feinheit(alt_f)
    netz_alt = NetzAbstand(tesselliere(alt_f, feinheit))
    m = np.eye(4) if ausrichtung is None else ausrichtung.matrix
    netze, werte = [], []
    flaechen: dict[int, _Flaeche] = {}
    neu_netze = tesselliere(neu_f, feinheit)
    laenge = _diagonale(neu_netze) / teilung
    k = min(8, len(netz_alt.a))
    for i, (pts, tri) in enumerate(neu_netze):
        fortschritt(i / max(len(neu_netze), 1))
        if len(tri) and _ist_ebene(neu_f[i]):
            pts, tri = verfeinere(pts, tri, laenge)  # Ebenen: Sehnen exakt, feinere Farbverlaeufe
        if not len(pts):
            netze.append((pts, tri))
            werte.append(np.zeros(0))
            continue
        p = pts @ m[:3, :3].T + m[:3, 3]
        d, _, fl = netz_alt.abfrage(p)
        _, nahe = netz_alt.baum.query(p, k=k)
        nahe = nahe.reshape(len(p), -1)
        w = np.empty(len(p))
        for j in range(len(p)):
            kand = set(netz_alt.flaeche[nahe[j]].tolist()) | {int(fl[j])}
            beste = _beste(p[j], kand, flaechen, alt_f, 2 * feinheit)
            if beste is None or beste[1] > 1e-4:
                # Abweichung oder falsche Kandidaten (Netzsuche bei grossen Dreiecken): weiter suchen
                _, weiter = netz_alt.baum.query(p[j], k=min(48, len(netz_alt.a)))
                mehr = set(netz_alt.flaeche[np.atleast_1d(weiter)].tolist()) - kand
                kand |= mehr
                zweite = _beste(p[j], mehr, flaechen, alt_f, 2 * feinheit)
                if zweite is not None and (beste is None or zweite[1] < beste[1]):
                    beste = zweite
            if beste is None or beste[1] > d[j] + 2 * feinheit:
                # Fusspunkt auf Kante/Ecke: exakt gegen die nahen Flaechen
                dj, fj = _exakt(p[j], kand, alt_f)
                if fj >= 0:
                    if fj not in flaechen:
                        flaechen[fj] = _Flaeche(alt_f[fj], 2 * feinheit)
                    seite = flaechen[fj].projektion(p[j], innen=False)
                    vz = 1.0 if seite is None or seite[0] >= 0 else -1.0
                    if beste is None or dj < beste[1]:
                        beste = (vz * dj, dj)
            if beste is None:
                beste = _netz_wert(netz_alt, p[j], alt_f)  # Netzflaechen ohne exakte Geometrie
            w[j] = beste[0] if beste is not None else float(d[j])
        netze.append((p, tri))
        werte.append(w)
    fortschritt(1.0)
    return Karte(netze, werte, feinheit)


def farbe(wert: float, toleranz: float, grenze: float) -> tuple[float, float, float]:
    """Farbe einer Abweichung: gruen innerhalb +-Toleranz, dann ueber gelb nach rot (+) bzw. cyan nach blau (-)."""
    a = abs(wert)
    if a <= toleranz:
        return (0.22, 0.62, 0.32)
    t = min((a - toleranz) / max(grenze - toleranz, 1e-12), 1.0)
    if wert > 0:
        # gelb -> orange -> rot
        return (0.98, 0.85 * (1 - t) + 0.12 * t, 0.10 * (1 - t))
    # cyan -> blau
    return (0.10 * (1 - t), 0.80 * (1 - t) + 0.25 * t, 0.95 * (1 - t) + 0.85 * t)


def standard_grenze(karte: Karte, toleranz: float) -> float:
    """Skalenende: 98. Perzentil der Betraege ausserhalb der Toleranz (Ausreisser stauchen die Skala nicht),
    aufgerundet auf 1/2/5 x 10^n, mindestens 2x Toleranz."""
    w = np.abs(karte.alle())
    aussen = w[w > toleranz]
    if not len(aussen):
        return 5 * toleranz
    g = float(np.percentile(aussen, 98))
    stufe = 10 ** np.floor(np.log10(g))
    for faktor in (1, 2, 5, 10):
        if g <= faktor * stufe * (1 + 1e-9):
            g = faktor * stufe
            break
    return max(float(g), 2 * toleranz)


def stufen(toleranz: float, grenze: float, je_seite: int = 4) -> list[float]:
    """Grenzen der Legende: -grenze .. -toleranz | +toleranz .. +grenze (gleich viele Stufen je Seite)."""
    aussen = np.linspace(toleranz, grenze, je_seite + 1)
    return [-float(x) for x in aussen[::-1]] + [float(x) for x in aussen]


GRAU = (0.62, 0.63, 0.66)  # kein Wert (z. B. keine Gegenflaeche gefunden)


@dataclass
class Skala:
    """Farbskala einer Farbkarte: Titel, Stufengrenzen (Legende), Farbe je Wert, Text je Wert (Klick)."""
    titel: str
    grenzen: list[float]
    farbe: Callable[[float], tuple]
    wert_text: Callable[[float], str] = lambda w: f"{w:+.4f} mm"
    beschriftung: list[str] = field(default_factory=list)  # Texte an den Grenzen (leer = Zahlen)
    name: str = "Abweichung"  # fuer die Klickanzeige (Anzeige ueber tr())

    def texte(self) -> list[str]:
        return self.beschriftung or [f"{g:+.3f}".replace("+0.000", "0") for g in self.grenzen]


def abweichungs_skala(toleranz: float, grenze: float, titel: str = "Abweichung (mm)") -> Skala:
    return Skala(titel, stufen(toleranz, grenze), lambda w: GRAU if w != w else farbe(w, toleranz, grenze))
