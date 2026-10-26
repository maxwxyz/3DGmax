"""Vergleich zweier Staende: Ausrichten, Geometrie, PMI, Aenderungsliste (nummeriert, mit Pruefstatus)."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ausrichten, vergleich_geo, vergleich_pmi
from .vergleich_geo import ENTFERNT, GEAENDERT, GLEICH, NEU

GEOMETRIE, PMI = "geometrie", "pmi"
PRUEF_STATUS = ("offen", "geprueft", "abgelehnt")


@dataclass
class Aenderung:
    nummer: int
    kategorie: str  # geometrie | pmi
    status: str  # neu, entfernt/entfallen, geaendert, geometrie
    titel: str
    beschreibung: str = ""
    flaechen_neu: set[int] = field(default_factory=set)  # Flaechenindizes im neuen Stand
    flaechen_alt: set[int] = field(default_factory=set)  # im alten Stand
    pmi_alt: object = None
    pmi_neu: object = None
    pruefstatus: str = "offen"
    kommentar: str = ""


@dataclass
class Vergleich:
    alt: object  # lader.Ergebnis
    neu: object
    ausrichtung: ausrichten.Ausrichtung
    geo: vergleich_geo.GeoErgebnis
    pmi: list
    aenderungen: list[Aenderung]
    toleranz: float
    suchweite: float

    def zaehler(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.aenderungen:
            out[a.pruefstatus] = out.get(a.pruefstatus, 0) + 1
        return out


def _gruppen(flaechen: set[int], nachbarn: dict[int, set[int]]) -> list[set[int]]:
    """Zusammenhaengende Bereiche (Flaechen mit gemeinsamer Kante)."""
    rest, out = set(flaechen), []
    while rest:
        start = rest.pop()
        gruppe, stapel = {start}, [start]
        while stapel:
            for n in nachbarn.get(stapel.pop(), ()):
                if n in rest:
                    rest.discard(n)
                    gruppe.add(n)
                    stapel.append(n)
        out.append(gruppe)
    return sorted(out, key=lambda g: min(g))


GEO_TITEL = {GEAENDERT: "Geometrie geändert", NEU: "Geometrie neu", ENTFERNT: "Geometrie entfernt"}
PMI_TITEL = {"geaendert": "PMI geändert", "neu": "PMI neu", "entfallen": "PMI entfallen",
             "geometrie": "Geometrie unter PMI geändert"}


def _geo_aenderungen(geo, nachbarn_neu, nachbarn_alt) -> list[Aenderung]:
    out = []
    for status in (GEAENDERT, NEU):
        menge = {f for f, s in geo.status_b.items() if s == status}
        for g in _gruppen(menge, nachbarn_neu):
            alt = {geo.zuordnung[f] for f in g if f in geo.zuordnung}
            abw = max(geo.max_abw_b.get(f, 0.0) for f in g)
            out.append(Aenderung(0, GEOMETRIE, status, GEO_TITEL[status],
                                 f"{len(g)} Fläche(n), größte Abweichung {abw:.3f} mm", g, alt))
    weg = {f for f, s in geo.status_a.items() if s == ENTFERNT}
    for g in _gruppen(weg, nachbarn_alt):
        out.append(Aenderung(0, GEOMETRIE, ENTFERNT, GEO_TITEL[ENTFERNT], f"{len(g)} Fläche(n)", set(), g))
    return out


def _pmi_aenderungen(liste) -> list[Aenderung]:
    out = []
    for x in liste:
        if x.status == vergleich_pmi.GLEICH:
            continue
        p = x.neu or x.alt
        art = {"mass": "Maß", "toleranz": "Toleranz", "bezug": "Bezug", "hinweis": "Hinweis"}.get(p.art, p.art)
        out.append(Aenderung(0, PMI, x.status, f"{PMI_TITEL[x.status]}: {art} {p.wert_text()}", x.text(),
                             set(x.neu.flaechen) if x.neu else set(), set(x.alt.flaechen) if x.alt else set(),
                             x.alt, x.neu))
    return out


def vergleiche(alt, neu, toleranz: float = 0.01, suchweite: float = 2.0, ausrichtung=None,
               fortschritt=lambda text: None) -> Vergleich:
    """alt, neu: Ergebnisse von ui.lader.lade_alles (Modell, PMI, ...)."""
    if ausrichtung is None:
        fortschritt("Ausrichten …")
        ausrichtung = ausrichten.richte_aus(alt.modell.flaechen, neu.modell.flaechen, toleranz)
    fortschritt("Geometrie vergleichen …")
    geo = vergleich_geo.vergleiche(alt.modell, neu.modell, ausrichtung, toleranz, suchweite=suchweite)
    fortschritt("PMI vergleichen …")
    pmi = vergleich_pmi.vergleiche_pmi(alt.pmi, neu.pmi, geo.zuordnung, zuordnung_ab=geo.zuordnung_ab,
                                       geo_status=geo.status_b)
    nachbarn_neu = vergleich_geo._nachbarn(neu.modell.flaechen, neu.modell.flaechen_index)
    nachbarn_alt = vergleich_geo._nachbarn(alt.modell.flaechen, alt.modell.flaechen_index)
    aenderungen = _pmi_aenderungen(pmi) + _geo_aenderungen(geo, nachbarn_neu, nachbarn_alt)
    for i, a in enumerate(aenderungen, 1):
        a.nummer = i
    return Vergleich(alt, neu, ausrichtung, geo, pmi, aenderungen, toleranz, suchweite)


def ist_gleich(v: Vergleich) -> bool:
    return not v.aenderungen and all(s == GLEICH for s in v.geo.status_b.values())
