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
FELDER = ("nennwert", "oben", "unten", "passung", "wert", "zone", "zonen_wert", "projektionsversatz",
          "maximum_toleranz", "material", "beschreibung")
FELD_TEXT = {"beschreibung": "Toleranzbeschreibung", "nennwert": "Nennwert", "oben": "oberes Abmaß/Höchstmaß", "unten": "unteres Abmaß/Mindestmaß",
             "passung": "Passung", "wert": "Toleranzwert", "zone": "Zone", "zonen_wert": "Zonenwert",
             "projektionsversatz": "Projektionsversatz", "projektionsflaechen": "Projektionsursprung",
             "maximum_toleranz": "Höchstwert der geometrischen Toleranz",
             "folgetoleranzen": "Nachgeordnete Toleranz im Verbundrahmen",
             "mittenabstand": "Abstand zwischen Symmetriezentren",
             "material": "Materialbedingung", "modifikatoren": "Modifikatoren", "bezuege": "Bezüge",
             "flaechen": "zugeordnete Flächen", "name": "Name", "geometrie": "Geometrie", "text": "Text"}


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
    if a.art == "hinweis":  # rein grafische Hinweise: ueber den Text zuordnen
        ta, tb = (a.nur_grafik_text or "").strip(), (b.nur_grafik_text or "").strip()
        if ta and ta == tb:
            s += 3.0
        elif ta and tb and _aehnlich(ta, tb) >= 0.6:
            s += 1.5
    return s


def _aehnlich(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def _verbundrollen(liste):
    """Bei gleichem Paarwert die Rolle und die Nachbarzeilen im Rahmen beruecksichtigen."""
    if not any(p.folgetoleranzen for p in liste):
        return {}, {}
    pmis = {p.step_id: p for p in liste if p.step_id}
    rollen, nachbarn = {}, {}
    for p in liste:
        for nr in p.folgetoleranzen:
            if nr in pmis:
                for zeile, richtung, nachbar in ((p, 1, pmis[nr]), (pmis[nr], -1, p)):
                    rollen.setdefault(zeile.step_id, set()).add((richtung, nachbar.typ, nachbar.wert, nachbar.bezug_text()))
                    nachbarn.setdefault(zeile.step_id, set()).add(nachbar.step_id)
    # Identische Rahmen mehrfach im Modell: bei Punktegleichstand ihre beiden Zeilen gemeinsam zuordnen.
    gruppen, anzahl = {}, {}
    for start in nachbarn:
        if start in gruppen:
            continue
        gruppe, offen = {start}, [start]
        while offen:
            neue = nachbarn[offen.pop()] - gruppe
            gruppe.update(neue)
            offen.extend(neue)
        signatur = frozenset((pmis[n].typ, pmis[n].wert, pmis[n].bezug_text(), frozenset(rollen[n])) for n in gruppe)
        nr = anzahl.get(signatur, 0)
        anzahl[signatur] = nr + 1
        for n in gruppe:
            gruppen[n] = (signatur, nr)
    return rollen, gruppen


def _vergleiche_verbund(paare, alt, neu):
    """Lokale STEP-Nummern erst ueber die bereits zugeordneten PMI vergleichen."""
    zu_neu = {p.alt.step_id: p.neu.step_id for p in paare if p.alt.step_id}
    def text(ids, pmis):
        return ", ".join(tr("PMI {}").format(pmis[nr].nummer) if nr in pmis else f"#{nr}"
                         for nr in sorted(ids)) or "–"

    alte = {p.step_id: p for p in alt}
    neue = {p.step_id: p for p in neu}
    for paar in paare:
        a, b = paar.alt.folgetoleranzen, paar.neu.folgetoleranzen
        if {zu_neu.get(nr) for nr in a} != set(b):
            paar.felder = [f for f in paar.felder if f[0] != "geometrie"]
            paar.felder.append(("folgetoleranzen", text(a, alte), text(b, neue)))
            paar.status = GEAENDERT


def vergleiche_pmi(alt: list[Pmi], neu: list[Pmi], zuordnung: dict[int, int] | None = None,
                   schwelle: float = 1.0, zuordnung_ab: dict[int, int] | None = None,
                   geo_status: dict[int, str] | None = None) -> list[PmiAenderung]:
    """zuordnung: Flaeche neu -> Flaeche alt (aus dem Geometrievergleich), zuordnung_ab die Gegenrichtung;
    ohne: gleiche Indizes."""
    if zuordnung is None:
        zuordnung = {f: f for p in neu for f in (*p.flaechen, *p.projektionsflaechen)}
    rolle_a, gruppe_a = _verbundrollen(alt)
    rolle_b, gruppe_b = _verbundrollen(neu)
    paare = []
    for i, a in enumerate(alt):
        for j, b in enumerate(neu):
            s = _punkte(a, b, zuordnung)
            if s >= schwelle:
                paare.append((s, i, j))
    if rolle_a or rolle_b:
        def prioritaet(paar):
            s, i, j = paar
            a, b = alt[i].step_id, neu[j].step_id
            return s, rolle_a.get(a) == rolle_b.get(b), gruppe_a.get(a) == gruppe_b.get(b), i, j
        paare.sort(key=prioritaet, reverse=True)
    else:
        paare.sort(reverse=True)
    frei_a, frei_b = set(range(len(alt))), set(range(len(neu)))
    out = []
    for _, i, j in paare:
        if i in frei_a and j in frei_b:
            frei_a.discard(i)
            frei_b.discard(j)
            out.append(_vergleiche_felder(alt[i], neu[j], zuordnung, zuordnung_ab, geo_status))
    if rolle_a or rolle_b:
        _vergleiche_verbund(out, alt, neu)
    out += [PmiAenderung(ENTFALLEN, alt[i], None) for i in sorted(frei_a)]
    out += [PmiAenderung(NEU, None, neu[j]) for j in sorted(frei_b)]
    return out


def _vergleiche_felder(a: Pmi, b: Pmi, zuordnung, zuordnung_ab=None, geo_status=None) -> PmiAenderung:
    felder = []
    for f in FELDER:
        va, vb = getattr(a, f), getattr(b, f)
        if not _gleich(va, vb):
            felder.append((f, _zahl(va), _zahl(vb)))
    alt, neu = set(a.projektionsflaechen), set(b.projektionsflaechen)
    if (alt or neu) and ({zuordnung.get(i) for i in neu} != alt):
        felder.append(("projektionsflaechen", ", ".join(map(str, sorted(alt))) or "–",
                       ", ".join(map(str, sorted(neu))) or "–"))
    if a.mittenabstand != b.mittenabstand:
        felder.append(("mittenabstand", tr("Ja") if a.mittenabstand else tr("Nein"),
                       tr("Ja") if b.mittenabstand else tr("Nein")))
    if sorted(a.modifikatoren) != sorted(b.modifikatoren):
        felder.append(("modifikatoren", ", ".join(a.modifikatoren) or "–", ", ".join(b.modifikatoren) or "–"))
    if a.bezug_text() != b.bezug_text():
        felder.append(("bezuege", a.bezug_text() or "–", b.bezug_text() or "–"))
    if (a.name or "") != (b.name or ""):
        felder.append(("name", a.name or "–", b.name or "–"))
    if a.art == "hinweis" and (a.nur_grafik_text or "").strip() != (b.nur_grafik_text or "").strip():
        felder.append(("text", a.nur_grafik_text or "–", b.nur_grafik_text or "–"))
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
