"""Moegliche parallelachsige Differentiale aus gegenhaendigen Schraegantrieben und gepaarten Ritzeln."""

from collections import defaultdict
from itertools import combinations

from ..i18n import tr
from . import verzahnung_daten as vd
from .getriebe_betrieb import Umlaufstufe


class Schraegraddifferential(Umlaufstufe):
    def titel(self, n):
        return tr("Schrägraddifferential {}").format(n)

    @property
    def umlaufraeder(self):
        return self.umlauf

    @property
    def eingriffe(self):
        return [paar for i, j in zip(self.umlauf[::2], self.umlauf[1::2], strict=True)
                for paar in ((self.a, i), (i, j), (j, self.b))]


def _ritzelpaare(liste, netz, a, b):
    """Zwei oder mehr verschiedene Ritzelpaare mit je drei passenden Aussenradeingriffen."""
    links, rechts = netz[a], netz[b]
    if links & rechts:
        return []
    paare = [(i, j) for i in sorted(links) for j in sorted(netz[i] & rechts)]
    if len(paare) < 2:
        return []
    bolzen = [i for paar in paare for i in paar]
    if len(set(bolzen)) != len(bolzen):
        return []
    if len({(liste[i].z, liste[j].z) for i, j in paare}) != 1:
        return []
    if any(vd._gleiche_achse(liste[i], liste[j]) for i, j in combinations(bolzen, 2)):
        return []
    return bolzen


def schraegradgruppen(liste, paare):
    """Gleich grosse getrennte Seitenraeder und zwei wiederkehrende dreifache Eingriffspfade."""
    idx = {id(v): i for i, v in enumerate(liste)}
    netz = defaultdict(set)
    am_ring = set()
    for p in paare:
        a, b = p.a, p.b
        if not vd.eingriff_moeglich(p):
            continue
        i, j = idx[id(a)], idx[id(b)]
        if a.innen or b.innen:
            am_ring.add(j if a.innen else i)
        elif a.beta > 0 and b.beta > 0 and {a.hand, b.hand} == {"links", "rechts"}:
            netz[i].add(j)
            netz[j].add(i)
    kandidaten = []
    for i, j in combinations(sorted(k for k in netz if len(netz[k]) >= 2), 2):
        a, b = liste[i], liste[j]
        if a.z != b.z or a.hand == b.hand or not vd._gleiche_achse(a, b):
            continue
        # Getrennte Achsabschnitte der Seitenraeder (kleines Aufmass fuer gemessene Stirnenden).
        if abs((a.punkt - b.punkt) @ a.richtung) < (a.b + b.b) / 2 - .001:
            continue
        ritzel = _ritzelpaare(liste, netz, i, j)
        teile = [i, j, *ritzel]
        if (ritzel and am_ring.isdisjoint(ritzel) and
                len({vd._koerperkennung(liste[k], k) for k in teile}) == len(teile)):
            kandidaten.append(Schraegraddifferential.dreiwellig("schraegraddifferential", i, j, tuple(ritzel), (a.z, b.z)))
    # Konkurrierende Zuordnungen der gleichen Zahnraeder sind geometrisch nicht eindeutig.
    return [[s] for s in kandidaten if all(s is t or s.teile.isdisjoint(t.teile) for t in kandidaten)]
