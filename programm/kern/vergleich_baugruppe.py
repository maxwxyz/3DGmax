"""Baugruppenvergleich: Teile (Exemplare) zweier Staende zuordnen und Unterschiede melden (ohne Qt).

Zuordnung je Grundname (ohne Exemplarnummer) ueber den naechsten Schwerpunkt; gleiche Kennwerte (Volumen,
Oberflaeche) bedeuten gleiche Geometrie. Meldungen: neu, entfernt, verschoben (Lage), geaendert (Geometrie),
umbenannt (gleiche Geometrie und Lage, anderer Name).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .eigenschaften import berechne
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
        w = berechne(k.form)
        c = np.asarray(w.schwerpunkt) @ m[:3, :3].T + m[:3, 3]
        out.append(Teil(k, _grundname(k.name), w.volumen, w.oberflaeche, c))
    return out


def _gleich(a: Teil, b: Teil) -> bool:
    return abs(a.volumen - b.volumen) <= 1e-6 * max(a.volumen, 1.0) and \
        abs(a.flaeche - b.flaeche) <= 1e-6 * max(a.flaeche, 1.0)


def vergleiche(wurzel_alt, wurzel_neu, matrix=None, toleranz: float = 0.01) -> list[TeilAenderung]:
    """matrix: Ausrichtung neu -> alt (4x4)."""
    alt, neu = teile(wurzel_alt), teile(wurzel_neu, matrix)
    out: list[TeilAenderung] = []
    offen_alt, offen_neu = list(alt), list(neu)
    for name in sorted({t.name for t in alt} | {t.name for t in neu}):
        a_liste = [t for t in offen_alt if t.name == name]
        n_liste = [t for t in offen_neu if t.name == name]
        paare = sorted(((float(np.linalg.norm(a.mitte - n.mitte)), i, j) for i, a in enumerate(a_liste)
                        for j, n in enumerate(n_liste)))
        genutzt_a, genutzt_n = set(), set()
        for d, i, j in paare:
            if i in genutzt_a or j in genutzt_n:
                continue
            genutzt_a.add(i)
            genutzt_n.add(j)
            a, n = a_liste[i], n_liste[j]
            offen_alt.remove(a)
            offen_neu.remove(n)
            if not _gleich(a, n):
                out.append(TeilAenderung(GEAENDERT, name, a, n, n.mitte - a.mitte))
            elif d > toleranz:
                out.append(TeilAenderung(VERSCHOBEN, name, a, n, n.mitte - a.mitte))
    # Reste: gleiche Geometrie und Lage, anderer Name -> umbenannt
    for a in list(offen_alt):
        for n in offen_neu:
            if _gleich(a, n) and np.linalg.norm(a.mitte - n.mitte) <= toleranz:
                out.append(TeilAenderung(UMBENANNT, f"{a.name} → {n.name}", a, n))
                offen_alt.remove(a)
                offen_neu.remove(n)
                break
    out += [TeilAenderung(ENTFERNT, a.name, a, None) for a in offen_alt]
    out += [TeilAenderung(NEU, n.name, None, n) for n in offen_neu]
    return out
