"""Dreiwellensaetze erkennen und Drehzahlen gekoppelter Stirnrad-, Kegelrad- und Umlaufstufen berechnen."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

import numpy as np

from ..i18n import tr
from . import verzahnung_daten as vd
from .verzahnung_sonder import kegelpaar_kandidaten


def _positive_achse(d):
    return d if d[np.argmax(abs(d))] > 0 else -d


@dataclass
class Dreiwelle:
    art: str
    a: int
    b: int
    umlauf: tuple[int, ...]
    koeffizienten: tuple[int, int]

    @property
    def teile(self):
        return {self.a, self.b, *self.umlauf}

    def name(self, liste):
        art = {"kegel": tr("Kegelraddifferential"), "planet": tr("Planetensatz"),
               "stufenplanet": tr("Stufenplanetensatz")}[self.art]
        return f"{art} · {liste[self.a].teil} / {liste[self.b].teil}"


def differentialgruppen(liste, kegelpaare):
    """Gegenueberliegende koaxiale Seitenraeder mit gemeinsamen Ausgleichsraedern.
    Bei symmetrischer Kreuzanordnung sind mehrere Traegerachsen geometrisch moeglich.
    """
    idx = {id(rad): i for i, rad in enumerate(liste)}
    nachbarn = {}
    for p in kegelpaare:
        i, j = idx[id(p.a)], idx[id(p.b)]
        nachbarn.setdefault(i, set()).add(j)
        nachbarn.setdefault(j, set()).add(i)
    gruppen = []
    for i, j in combinations(sorted(nachbarn), 2):
        a, b = liste[i], liste[j]
        # Einfache offene Bauform mit gleichen Seitenraedern und radialen Ausgleichskegeln.
        if a.z != b.z or a.richtung @ b.richtung > -.999999 or not vd._gleiche_achse(a, b):
            continue
        plan = tuple(k for k in sorted(nachbarn[i] & nachbarn[j]) if abs(a.richtung @ liste[k].richtung) < .001)
        if not plan:
            continue
        satz = Dreiwelle("kegel", i, j, plan, (a.z, b.z))
        kanten = {tuple(sorted((ende, k))) for ende in (i, j) for k in plan}
        passend = [g for g in gruppen if g[0] & kanten]
        varianten = [satz]
        for g in passend:
            kanten.update(g[0])
            varianten.extend(g[1])
            gruppen.remove(g)
        gruppen.append((kanten, varianten))
    return [varianten for _, varianten in gruppen]


def _addiere(zeile, i, wert):
    neu = zeile.get(i, 0) + wert
    if neu:
        zeile[i] = neu
    else:
        zeile.pop(i, None)


def _komponente_loesen(gleichungen):
    """Exakte Elimination mit Zahnzahlen, damit freie langsame Wellen auch bei vielen Stufen frei bleiben."""
    basis = {}
    for koeff, wert in gleichungen:
        zeile = {i: Fraction(k) for i, k in koeff.items()}
        ziel = Fraction(str(wert))
        while zeile:
            i = min(zeile)
            faktor = zeile.pop(i)
            if i not in basis:
                basis[i] = ({j: k / faktor for j, k in zeile.items()}, ziel / faktor)
                break
            rest, b = basis[i]
            ziel -= faktor * b
            for j, k in rest.items():
                _addiere(zeile, j, -faktor * k)
        else:
            if ziel:
                return None

    # Rueckwaerts einsetzen. Jede Restvariable ist eine unabhaengig freie Wellendrehzahl.
    for i in sorted(basis, reverse=True):
        rest, ziel = basis[i]
        frei = {}
        for j, faktor in rest.items():
            if j not in basis:
                _addiere(frei, j, faktor)
                continue
            abhaengig, b = basis[j]
            ziel -= faktor * b
            for k, v in abhaengig.items():
                _addiere(frei, k, -faktor * v)
        basis[i] = (frei, ziel)
    return {i: float(ziel) for i, (frei, ziel) in basis.items() if not frei}


def _loesen(anzahl, gleichungen):
    """Jeden verbundenen Teil getrennt loesen. Ein Widerspruch bleibt auf diesen Teil begrenzt."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    von, zu = [], []
    for koeff, _ in gleichungen:
        i = next(iter(koeff))
        for j in koeff:
            von.append(i)
            zu.append(j)
    graph = coo_matrix((np.ones(len(von)), (von, zu)), shape=(anzahl, anzahl))
    n, gruppe = connected_components(graph, directed=False)
    ergebnis = [None] * anzahl
    konflikt = set()
    komponenten = [[] for _ in range(n)]
    bedingungen = [[] for _ in range(n)]
    for i, k in enumerate(gruppe):
        komponenten[k].append(i)
    for a, b in gleichungen:
        bedingungen[gruppe[next(iter(a))]].append((a, b))
    for ids, zeilen in zip(komponenten, bedingungen):
        if not zeilen:
            continue
        loesung = _komponente_loesen(zeilen)
        if loesung is None:
            konflikt.update(ids)
        else:
            for i, wert in loesung.items():
                ergebnis[i] = wert
    return ergebnis, konflikt


class Betriebsmodell:
    """Benannte Wellen und lineare Drehzahlgleichungen im gemeinsamen Drehsinn paralleler Achsen."""

    def __init__(self, liste, paare, *, getrennte_wellen=False):
        from .verzahnung import Verzahnung
        self.liste = liste
        raeder = [v for v in liste if isinstance(v, Verzahnung)]
        idx = {id(v): i for i, v in enumerate(liste)}
        ri = [idx[id(v)] for v in raeder]
        self.planeten = [Dreiwelle("stufenplanet" if s.gestuft else "planet", ri[s.sonne], ri[s.hohlrad],
                                   tuple(ri[i] for i in s.umlaufraeder), s.koeffizienten)
                         for s in vd.planetensaetze(raeder, paare)]
        kegel = kegelpaar_kandidaten(liste)
        self.differentiale = differentialgruppen(liste, kegel)
        saetze = self.planeten + [v for gruppe in self.differentiale for v in gruppe]
        mitglieder = [s.teile for s in saetze]
        self.gruppen = vd.wellen(liste, mitglieder)
        einzeln = vd.wellen(liste, getrennte_wellen=True)
        self.trennbar = len(einzeln) > len(self.gruppen)
        if getrennte_wellen:
            self.gruppen = einzeln
        self.welle = {i: k for k, g in enumerate(self.gruppen) for i in g}
        self.namen = [" + ".join(liste[i].teil for i in g) for g in self.gruppen]
        self.achsteil = [g[0] for g in self.gruppen]
        self.feste_paare = []
        for p in [*paare, *kegel]:
            i, j = idx[id(p.a)], idx[id(p.b)]
            wa, wb = self.welle[i], self.welle[j]
            ea = _positive_achse(liste[self.achsteil[wa]].richtung)
            eb = _positive_achse(liste[self.achsteil[wb]].richtung)
            if isinstance(p.a, Verzahnung):
                if not vd.eingriff_moeglich(p):
                    continue
                sinn = -1 if p.a.innen or p.b.innen else 1
                sinn *= 1 if ea @ eb > 0 else -1
            else:
                # Die gemessenen Kegelachsen weisen vom Scheitel nach aussen.
                sinn = 1 if (p.a.richtung @ ea) * (p.b.richtung @ eb) > 0 else -1
            if wa != wb:
                self.feste_paare.append((i, j, {wa: p.a.z, wb: sinn * p.b.z}))

    def betrieb(self, auswahl=None):
        """Ein Steg je Satz. Nicht eindeutig bestimmte Differentialachsen brauchen eine Auswahl."""
        auswahl = auswahl or {}
        if any(k not in range(len(self.differentiale)) for k in auswahl):
            raise ValueError("Unbekannte Differentialgruppe")
        saetze = list(self.planeten)
        offen = []
        for k, varianten in enumerate(self.differentiale):
            wahl = auswahl.get(k, 0 if len(varianten) == 1 else None)
            if wahl is not None:
                if not isinstance(wahl, int) or wahl not in range(len(varianten)):
                    raise ValueError("Unbekannte Achsvariante")
                saetze.append(varianten[wahl])
            else:
                offen.extend(varianten)
        # Bis zur Achswahl kann jedes moegliche Ausgleichsrad umlaufen.
        umlauf = {self.welle[i] for s in (*saetze, *offen) for i in s.umlauf}
        zeilen = [(koeff, 0.) for i, j, koeff in self.feste_paare if self.welle[i] not in umlauf and self.welle[j] not in umlauf]
        ports = {w for koeff, _ in zeilen for w in koeff}
        namen, achsen = list(self.namen), list(self.achsteil)
        beschreibung = []
        for s in saetze:
            steg = len(namen)
            a, b = self.welle[s.a], self.welle[s.b]
            za, zb = s.koeffizienten
            ec = _positive_achse(self.liste[s.a].richtung)
            ea = _positive_achse(self.liste[achsen[a]].richtung)
            eb = _positive_achse(self.liste[achsen[b]].richtung)
            ka = za if ea @ ec > 0 else -za
            kb = zb if eb @ ec > 0 else -zb
            namen.append(tr("Steg") + " · " + s.name(self.liste))
            achsen.append(s.a)
            ports.update([a, b, steg])
            gleichung = {a: ka, steg: -(za + zb)}
            _addiere(gleichung, b, kb)
            zeilen.append((gleichung, 0.))
            beschreibung.append({"art": s.art, "raeder": [s.a, s.b], "umlaufraeder": list(s.umlauf),
                                 "wellen": [a, b, steg], "koeffizienten": [ka, kb, -(za + zb)]})
        return Betrieb(self, namen, achsen, sorted(ports), zeilen, beschreibung)


@dataclass
class Betrieb:
    modell: Betriebsmodell
    namen: list
    achsen: list
    ports: list
    zeilen: list
    saetze: list

    def koppelbar(self, i, j):
        teile = self.modell.liste
        return i != j and vd._gleiche_achse(teile[self.achsen[i]], teile[self.achsen[j]])

    def positive_achse(self, i):
        return _positive_achse(self.modell.liste[self.achsen[i]].richtung)

    def auswerten(self, drehzahlen, kupplungen):
        aktiv = set(self.ports)
        if any(i not in aktiv or not np.isfinite(n) for i, n in drehzahlen.items()):
            raise ValueError("Ungueltige Drehzahlvorgabe")
        kupplungen = sorted({tuple(sorted(paar)) for paar in kupplungen})
        zeilen = list(self.zeilen)
        zeilen.extend(({i: 1}, n) for i, n in drehzahlen.items())
        for i, j in kupplungen:
            if i not in aktiv or j not in aktiv or not self.koppelbar(i, j):
                raise ValueError("Ungueltige Wellenkupplung")
            sinn = 1 if self.positive_achse(i) @ self.positive_achse(j) > 0 else -1
            zeilen.append(({i: 1, j: -sinn}, 0.))
        werte, konflikt = _loesen(len(self.namen), zeilen)
        return {"saetze": self.saetze, "wellen": [{"id": i, "name": self.namen[i], "vorgabe": drehzahlen.get(i),
                "drehzahl": werte[i], "status": "widerspruch" if i in konflikt else
                "frei" if werte[i] is None else "bestimmt"} for i in self.ports],
                "kupplungen": list(kupplungen), "einheit": "1/min"}
