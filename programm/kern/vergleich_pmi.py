"""Semantischer PMI-Vergleich: welche Masse, Toleranzen, Bezuege und Hinweise neu, entfallen, geaendert sind.

Zuordnung alt <-> neu: gleiche Art und gleicher Typ; Punkte fuer gemeinsame Flaechen (ueber die
Flaechenzuordnung des Geometrievergleichs), gleichen Wert, gleiches Bezugssystem und gleichen Namen.
Danach Feld fuer Feld vergleichen.
"""

from __future__ import annotations

from ..i18n import tr

from dataclasses import dataclass, field

from .pmi import Pmi

GLEICH, GEAENDERT, NEU, ENTFALLEN = "gleich", "geaendert", "neu", "entfallen"
GEOMETRIE = "geometrie"  # PMI unveraendert, aber Geometrie der zugeordneten Flaechen geaendert
FELDER = ("nennwert", "oben", "unten", "passung", "wert", "zone", "zonen_wert", "material")
FELD_TEXT = {"nennwert": "Nennwert", "oben": "oberes Abmaß/Höchstmaß", "unten": "unteres Abmaß/Mindestmaß",
             "passung": "Passung", "wert": "Toleranzwert", "zone": "Zone", "zonen_wert": "Zonenwert",
             "material": "Materialbedingung", "modifikatoren": "Modifikatoren", "bezuege": "Bezüge",
             "flaechen": "zugeordnete Flächen", "name": "Name", "geometrie": "Geometrie"}


@dataclass
class PmiAenderung:
    status: str
    alt: Pmi | None
    neu: Pmi | None
    felder: list[tuple[str, str, str]] = field(default_factory=list)  # (Feld, alt, neu)

    def text(self) -> str:
        p = self.neu or self.alt
        if self.felder:
            return "; ".join(f"{tr(FELD_TEXT.get(f, f))}: {a} → {n}" if a else f"{tr(FELD_TEXT.get(f, f))}: {n}"
                             for f, a, n in self.felder)
        return p.wert_text()


def _gleich(a, b, eps=1e-6) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= eps
    return a == b


def _zahl(x) -> str:
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x) or "–"


def _flaechen_in_a(p: Pmi, zuordnung: dict[int, int]) -> set[int]:
    return {zuordnung[f] for f in p.flaechen if f in zuordnung}


def _gleiche_flaechen(a: Pmi, b: Pmi, zuordnung: dict[int, int], zuordnung_ab: dict[int, int] | None) -> bool:
    """Gleiche Flaechen, auch wenn ein Stand sie anders unterteilt (z. B. Bohrung als zwei Halbschalen)."""
    if _flaechen_in_a(b, zuordnung) == a.flaechen:
        return True
    if zuordnung_ab is not None:
        b_aus_a = {zuordnung_ab[f] for f in a.flaechen if f in zuordnung_ab}
        a_aus_b = _flaechen_in_a(b, zuordnung)
        return b_aus_a == b.flaechen or (a_aus_b <= a.flaechen and b_aus_a <= b.flaechen and bool(a_aus_b))
    return False


def _punkte(a: Pmi, b: Pmi, zuordnung: dict[int, int]) -> float:
    if a.art != b.art or a.typ != b.typ:
        return -1.0
    s = 0.0
    fb = _flaechen_in_a(b, zuordnung)
    if a.flaechen and fb:
        s += 4.0 * len(a.flaechen & fb) / len(a.flaechen | fb)
    wert_a = a.nennwert if a.nennwert is not None else a.wert
    wert_b = b.nennwert if b.nennwert is not None else b.wert
    if wert_a is not None and _gleich(wert_a, wert_b):
        s += 1.5
    if a.bezug_text() == b.bezug_text():
        s += 0.5
    if a.name and a.name == b.name:
        s += 1.0
    if a.art == "bezug" and a.name == b.name:
        s += 3.0
    return s


def vergleiche_pmi(alt: list[Pmi], neu: list[Pmi], zuordnung: dict[int, int] | None = None,
                   schwelle: float = 1.0, zuordnung_ab: dict[int, int] | None = None,
                   geo_status: dict[int, str] | None = None) -> list[PmiAenderung]:
    """zuordnung: Flaeche neu -> Flaeche alt (aus dem Geometrievergleich), zuordnung_ab die Gegenrichtung;
    ohne: gleiche Indizes."""
    if zuordnung is None:
        zuordnung = {f: f for p in neu for f in p.flaechen}
    paare = []
    for i, a in enumerate(alt):
        for j, b in enumerate(neu):
            s = _punkte(a, b, zuordnung)
            if s >= schwelle:
                paare.append((s, i, j))
    paare.sort(reverse=True)
    frei_a, frei_b = set(range(len(alt))), set(range(len(neu)))
    out = []
    for s, i, j in paare:
        if i in frei_a and j in frei_b:
            frei_a.discard(i)
            frei_b.discard(j)
            out.append(_vergleiche_felder(alt[i], neu[j], zuordnung, zuordnung_ab, geo_status))
    out += [PmiAenderung(ENTFALLEN, alt[i], None) for i in sorted(frei_a)]
    out += [PmiAenderung(NEU, None, neu[j]) for j in sorted(frei_b)]
    return out


def _vergleiche_felder(a: Pmi, b: Pmi, zuordnung, zuordnung_ab=None, geo_status=None) -> PmiAenderung:
    felder = []
    for f in FELDER:
        va, vb = getattr(a, f), getattr(b, f)
        if not _gleich(va, vb):
            felder.append((f, _zahl(va), _zahl(vb)))
    if sorted(a.modifikatoren) != sorted(b.modifikatoren):
        felder.append(("modifikatoren", ", ".join(a.modifikatoren) or "–", ", ".join(b.modifikatoren) or "–"))
    if a.bezug_text() != b.bezug_text():
        felder.append(("bezuege", a.bezug_text() or "–", b.bezug_text() or "–"))
    if (a.name or "") != (b.name or ""):
        felder.append(("name", a.name or "–", b.name or "–"))
    fb = _flaechen_in_a(b, zuordnung)
    if (a.flaechen or b.flaechen) and not _gleiche_flaechen(a, b, zuordnung, zuordnung_ab):
        felder.append(("flaechen", str(len(a.flaechen)),
                       tr("{} ({} gleich)").format(len(b.flaechen), len(a.flaechen & fb))))
    if felder:
        return PmiAenderung(GEAENDERT, a, b, felder)
    geaendert = [f for f in b.flaechen if (geo_status or {}).get(f, "gleich") != "gleich"]
    if geaendert:
        return PmiAenderung(GEOMETRIE, a, b, [("geometrie", "", tr("{} von {} Flächen geändert, PMI unverändert")
                                                .format(len(geaendert), len(b.flaechen)))])
    return PmiAenderung(GLEICH, a, b, felder)
