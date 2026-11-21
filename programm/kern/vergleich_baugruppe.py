"""Baugruppenvergleich: Teile (Exemplare) zweier Staende zuordnen und Unterschiede melden (ohne Qt).

Zuordnung je Grundname (ohne Exemplarnummer) ueber den naechsten Schwerpunkt; gleiche Kennwerte (Volumen,
Oberflaeche) bedeuten gleiche Geometrie. Meldungen: neu, entfernt, verschoben (Lage), geaendert (Geometrie),
umbenannt (gleiche Geometrie und Lage, anderer Name).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .eigenschaften import masseneigenschaften
from .stueckliste import _grundname

NEU, ENTFERNT, VERSCHOBEN, GEAENDERT, UMBENANNT = "neu", "entfernt", "verschoben", "geaendert", "umbenannt"


@dataclass
class Teil:
    knoten: object
    name: str
    volumen: float
    flaeche: float
    mitte: np.ndarray


@dataclass
class TeilAenderung:
    status: str
    name: str
    alt: Teil | None
    neu: Teil | None
    versatz: np.ndarray | None = None


def teile(wurzel, matrix=None) -> list[Teil]:
    m = np.eye(4) if matrix is None else matrix
    out = []
    for k in wurzel.blaetter():
        if k.hilfsgeometrie:
            continue
        volumen, flaeche, schwerpunkt = masseneigenschaften(k.form)
        c = np.asarray(schwerpunkt) @ m[:3, :3].T + m[:3, 3]
        out.append(Teil(k, _grundname(k.name), volumen, flaeche, c))
    return out


def _gleich(a: Teil, b: Teil) -> bool:
    return abs(a.volumen - b.volumen) <= 1e-6 * max(a.volumen, 1.0) and \
        abs(a.flaeche - b.flaeche) <= 1e-6 * max(a.flaeche, 1.0)


def _suchradius(abstand):
    """Suchraum fuer Rundungsunterschiede zwischen Raumindex und NumPy erweitern."""
    return np.nextafter(abstand * (1 + 8*np.finfo(float).eps), np.inf)


def _naechste(punkte, ziel):
    """Bei gleichem Abstand gewinnt wie in der sortierten Paarliste der erste Zielindex."""
    _, erste = np.unique(ziel, axis=0, return_index=True)
    if len(erste) == 1:
        return np.full(len(punkte), erste[0])
    baum = cKDTree(ziel[erste])
    abstand, treffer = baum.query(punkte, k=2)
    wahl = erste[treffer[:, 0]]
    # Benachbarte Gleitkommazahlen mit der urspruenglichen Distanzrechnung entscheiden.
    radius = _suchradius(abstand[:, 0])
    for i in np.flatnonzero(abstand[:, 1] <= radius):
        kandidaten = erste[baum.query_ball_point(punkte[i], radius[i])]
        wahl[i] = min(kandidaten, key=lambda j: (np.linalg.norm(punkte[i]-ziel[j]), j))
    return wahl


def _paare_am_minimum(x, y, hin, trifft):
    # Halbe Rasterteilung: viele gleiche kuerzeste Abstaende, aber nur eine gegenseitige erste Wahl.
    dist = np.array([np.linalg.norm(p-y[j]) for p, j in zip(x, hin)])
    minimum = dist.min()
    baum = cKDTree(y)
    radius = _suchradius(minimum)
    belegt = set()
    for i in np.flatnonzero(dist == minimum):
        for j in sorted(baum.query_ball_point(x[i], radius)):
            if j not in belegt and np.linalg.norm(x[i]-y[j]) == minimum:
                hin[i], trifft[i] = j, True
                belegt.add(j)
                break


def _paare(alt, neu, a, b):
    """Exemplare eines Grundnamens nach Abstand und urspruenglicher Reihenfolge paaren."""
    if len(a) == len(b) == 1:
        return [(float(np.linalg.norm(alt[a[0]].mitte-neu[b[0]].mitte)), a[0], b[0])]
    an_ort = defaultdict(deque)
    for j in b:
        an_ort[tuple(neu[j].mitte)].append(j)
    paare, rest_a = [], []
    for i in a:
        gleich = an_ort.get(tuple(alt[i].mitte))
        if gleich:
            paare.append((0., i, gleich.popleft()))
        else:
            rest_a.append(i)
    rest_b = sorted(j for reihe in an_ort.values() for j in reihe)
    ia, ib = np.asarray(rest_a, dtype=int), np.asarray(rest_b, dtype=int)
    while len(ia) and len(ib):
        x = np.array([alt[i].mitte for i in ia])
        y = np.array([neu[j].mitte for j in ib])
        hin, rueck = _naechste(x, y), _naechste(y, x)
        # Gegenseitige erste Wahl: Kein frueheres Paar kann einen der Partner belegen.
        trifft = rueck[hin] == np.arange(len(x))
        if trifft.sum()*4 < min(len(ia), len(ib)):
            _paare_am_minimum(x, y, hin, trifft)
        for i in np.flatnonzero(trifft):
            j = hin[i]
            paare.append((float(np.linalg.norm(x[i]-y[j])), ia[i], ib[j]))
        frei = np.ones(len(ib), dtype=bool)
        frei[hin[trifft]] = False
        ia, ib = ia[~trifft], ib[frei]
    return sorted(paare)


def vergleiche(wurzel_alt, wurzel_neu, matrix=None, toleranz: float = 0.01) -> list[TeilAenderung]:
    """matrix: Ausrichtung neu -> alt (4x4)."""
    alt, neu = teile(wurzel_alt), teile(wurzel_neu, matrix)
    gruppen_a, gruppen_b = defaultdict(list), defaultdict(list)
    for i, a in enumerate(alt):
        gruppen_a[a.name].append(i)
    for j, b in enumerate(neu):
        gruppen_b[b.name].append(j)
    offen_a, offen_b = set(range(len(alt))), set(range(len(neu)))
    out = []
    for name in sorted(gruppen_a.keys() & gruppen_b.keys()):
        for d, i, j in _paare(alt, neu, gruppen_a[name], gruppen_b[name]):
            a, n = alt[i], neu[j]
            offen_a.remove(i)
            offen_b.remove(j)
            if not _gleich(a, n):
                out.append(TeilAenderung(GEAENDERT, name, a, n, n.mitte-a.mitte))
            elif d > toleranz:
                out.append(TeilAenderung(VERSCHOBEN, name, a, n, n.mitte-a.mitte))
    # Reste in Dateireihenfolge: erste freie, geometrisch gleiche Umbenennung am Ort.
    if offen_a and offen_b and toleranz >= 0:
        ids = sorted(offen_b)
        baum = cKDTree([neu[j].mitte for j in ids])
        radius = _suchradius(toleranz)
        for i in sorted(offen_a):
            a = alt[i]
            for k in sorted(baum.query_ball_point(a.mitte, radius)):
                j = ids[k]
                n = neu[j]
                if j in offen_b and _gleich(a, n) and np.linalg.norm(a.mitte-n.mitte) <= toleranz:
                    out.append(TeilAenderung(UMBENANNT, f"{a.name} → {n.name}", a, n))
                    offen_a.remove(i)
                    offen_b.remove(j)
                    break
    out += [TeilAenderung(ENTFERNT, alt[i].name, alt[i], None) for i in sorted(offen_a)]
    out += [TeilAenderung(NEU, neu[j].name, None, neu[j]) for j in sorted(offen_b)]
    return out
