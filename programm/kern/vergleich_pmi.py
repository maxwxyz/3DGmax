"""Semantischer PMI-Vergleich: welche Masse, Toleranzen, Bezuege und Hinweise neu, entfallen, geaendert sind.

Zuordnung alt <-> neu: gleiche Art und gleicher Typ; Punkte fuer gemeinsame Flaechen (ueber die
Flaechenzuordnung des Geometrievergleichs), gleichen Wert, gleiches Bezugssystem und gleichen Namen.
Danach Feld fuer Feld vergleichen.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache
from math import inf, isfinite, nextafter

from ..i18n import tr

from .pmi import Pmi
from .vergleich_profilbereich import bereichsfeld, hat_ausschnitt

GLEICH, GEAENDERT, NEU, ENTFALLEN = "gleich", "geaendert", "neu", "entfallen"
GEOMETRIE = "geometrie"  # PMI unveraendert, aber Geometrie der zugeordneten Flaechen geaendert
FELDER = ("nennwert", "oben", "unten", "passung", "wert", "zone", "zonen_wert", "projektionsversatz",
          "maximum_toleranz", "material", "beschreibung", "einheitslaenge", "einheitsbreite", "einheitsdurchmesser")
FELD_TEXT = {"beschreibung": "Toleranzbeschreibung", "nennwert": "Nennwert", "oben": "oberes Abmaß/Höchstmaß", "unten": "unteres Abmaß/Mindestmaß",
             "passung": "Passung", "wert": "Toleranzwert", "zone": "Zone", "zonen_wert": "Zonenwert",
             "projektionsversatz": "Projektionsversatz", "projektionsflaechen": "Projektionsursprung",
             "einheitslaenge": "Länge der Einheitsfläche (mm)", "einheitsbreite": "Breite der Einheitsfläche (mm)",
             "einheitsdurchmesser": "Durchmesser der Einheitsfläche (mm)",
             "maximum_toleranz": "Höchstwert der geometrischen Toleranz",
             "grenzmass": "Grenzmaße", "bereichsgrenzen": "Begrenzter Profilbereich",
             "grenzen_offen": "Zuordnung der Grenzkanten offen",
             "profilbereich_offen": "Vergleich der Profilteilflächen offen",
             "profilteilflaeche": "Abweichende Profilteilfläche",
             "simultan_mit": "Gleichzeitig geltende Toleranzen",
             "simultan_offen": "Gleichzeitige Anforderung mit ungeprüfter Bezugsbasis",
             "folgetoleranzen": "Nachgeordnete Toleranz im Verbundrahmen",
             "mittenbezug": "Bezugsfläche der Mittenkoordinate",
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


_WERT_EPS = 1e-6


def _gleich(a, b, eps=_WERT_EPS) -> bool:
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


def _punkte(a: Pmi, b: Pmi, fb, gleicher_bezug) -> float:
    if a.art != b.art or a.typ != b.typ:
        return -1.0
    s = 0.0
    fa = a.traegerflaechen()
    if fa and fb:
        gemeinsam = len(fa & fb)
        s += 4.0 * gemeinsam / (len(fa) + len(fb) - gemeinsam)
    wert_a = a.nennwert if a.nennwert is not None else a.wert
    wert_b = b.nennwert if b.nennwert is not None else b.wert
    if wert_a is not None and _gleich(wert_a, wert_b):
        s += 1.5
    if gleicher_bezug:
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


def _kandidaten(alt, neu, merkmale_b, schwelle, offen_a, offen_b):
    """Nur Paare auslassen, die mit der gegebenen Schwelle nie genug Punkte erreichen."""
    if schwelle <= -1:
        for i in offen_a:
            for j in offen_b:
                yield i, j
        return
    typen, namen, orte, werte = (defaultdict(list) for _ in range(4))
    for j in offen_b:
        b = neu[j]
        typ = (b.art, b.typ)
        typen[typ].append(j)
        if b.name or b.art == "bezug":
            namen[typ, b.name].append(j)
        for f in merkmale_b[j].flaechen:
            orte[typ, f].append(j)
        wert = b.nennwert if b.nennwert is not None else b.wert
        if wert is not None and isfinite(wert):
            werte[typ].append((wert, j))
    for gruppe in werte.values():
        gruppe.sort()
    for i in offen_a:
        a = alt[i]
        typ = (a.art, a.typ)
        if schwelle <= .5 or a.art == "hinweis":
            kandidaten = typen.get(typ, ())
        else:
            # Das gleiche Bezugssystem allein zaehlt nur einen halben Punkt.
            kandidaten = set(namen.get((typ, a.name), ()))
            for f in a.traegerflaechen():
                kandidaten.update(orte.get((typ, f), ()))
            wert = a.nennwert if a.nennwert is not None else a.wert
            zahlen = werte.get(typ, ())
            if wert is not None and zahlen and isfinite(wert):
                l = bisect_left(zahlen, (nextafter(wert-_WERT_EPS, -inf), -1))
                r = bisect_right(zahlen, (nextafter(wert+_WERT_EPS, inf), len(neu)))
                kandidaten.update(zahlen[k][1] for k in range(l, r))
        for j in kandidaten:
            yield i, j


@dataclass(slots=True)
class _Paarmerkmal:
    flaechen: frozenset
    bezug: str
    inhalt: tuple
    exakt: tuple | None
    rolle: set | None
    gruppe: tuple | None


def _grenzen(p, kanten):
    if p.bereichsgrenzen is None:
        return None
    if not p.bereichsgrenzen:
        return ()
    return tuple((name, nr if kanten is None else kanten.get(nr)) for name, nr in p.bereichsgrenzen)


def _paarmerkmale(liste, zuordnung=None, simultan=None, kanten=None):
    rollen, gruppen = _verbundrollen(liste, simultan or {})
    ergebnis = []
    for p in liste:
        traeger = p.traegerflaechen()
        if zuordnung is None:
            flaechen, projektion = frozenset(traeger), frozenset(p.projektionsflaechen)
        else:
            flaechen = frozenset(zuordnung[n] for n in traeger if n in zuordnung)
            projektion = frozenset(zuordnung[n] for n in p.projektionsflaechen if n in zuordnung)
        bezug = p.bezug_text()
        ursprung = p.mittenbezug if zuordnung is None else zuordnung.get(p.mittenbezug)
        grenzen = _grenzen(p, kanten)
        inhalt = (grenzen, ursprung, tuple(getattr(p, f) for f in FELDER), p.grenzmass, p.mittenabstand,
                  tuple(sorted(p.modifikatoren)), p.name, p.nur_grafik_text if p.art == "hinweis" else "")
        exakt = None
        if (not hat_ausschnitt(p) and p.step_id not in rollen and grenzen is not None and all(k is not None for _, k in grenzen) and
                len(flaechen) == len(p.flaechen) and len(projektion) == len(p.projektionsflaechen)):
            exakt = (p.art, p.typ, flaechen, projektion, bezug, inhalt)
        ergebnis.append(_Paarmerkmal(flaechen, bezug, inhalt, exakt, rollen.get(p.step_id), gruppen.get(p.step_id)))
    return ergebnis


def _exakte_paare(alt, neu, merkmale_a, merkmale_b, schwelle):
    """Identische freie Merkmale vorab paaren: Ihr Punktwert ist auf beiden Seiten maximal."""
    nach_schluessel = defaultdict(list)
    for j, merkmal in enumerate(merkmale_b):
        if merkmal.exakt is not None:
            nach_schluessel[merkmal.exakt].append(j)
    paare = []
    for i in reversed(range(len(alt))):
        gruppe = nach_schluessel.get(merkmale_a[i].exakt)
        if gruppe:
            j = gruppe[-1]
            s = _punkte(alt[i], neu[j], merkmale_b[j].flaechen, True)
            if s >= schwelle:
                gruppe.pop()
                paare.append((s, True, True, True, True, i, j))
    return paare


def simultangruppen(liste):
    """Bestaetigte Gruppen aus direkten STEP-Paaren, mit einer gemeinsamen ID-Menge je Gruppe."""
    partner = {p.step_id: p.simultan_mit for p in liste if p.simultan_mit}
    gruppen = {}
    for start in partner:
        if start in gruppen:
            continue
        besucht, offen = {start}, [start]
        while offen:
            for nr in partner[offen.pop()]:
                if nr in partner and nr not in besucht:
                    besucht.add(nr)
                    offen.append(nr)
        gruppe = frozenset(besucht)
        gruppen.update(dict.fromkeys(besucht, gruppe))
    return gruppen


def _verbundrollen(liste, simultan):
    """Bei gleichem Paarwert die Rolle und die Nachbarzeilen im Rahmen beruecksichtigen."""
    if not any(p.folgetoleranzen or p.simultan_mit or p.simultan_offen for p in liste):
        return {}, {}
    pmis = {p.step_id: p for p in liste if p.step_id}
    rollen, nachbarn = {}, {}
    signaturen = {}
    for nr, gruppe in simultan.items():
        if gruppe not in signaturen:
            signaturen[gruppe] = (len(gruppe), frozenset((pmis[n].typ, pmis[n].wert, pmis[n].bezug_text()) for n in gruppe))
        rollen[nr] = {("simultan", signaturen[gruppe])}
        nachbarn[nr] = {n for n in pmis[nr].simultan_mit if n in pmis}
    for p in liste:
        for nr in p.folgetoleranzen:
            if nr in pmis:
                for zeile, richtung, nachbar in ((p, 1, pmis[nr]), (pmis[nr], -1, p)):
                    rollen.setdefault(zeile.step_id, set()).add((richtung, nachbar.typ, nachbar.wert, nachbar.bezug_text()))
                    nachbarn.setdefault(zeile.step_id, set()).add(nachbar.step_id)
        for nr in p.simultan_offen:
            if nr in pmis:
                n = pmis[nr]
                rollen.setdefault(p.step_id, set()).add(("simultan_offen", n.typ, n.wert, n.bezug_text()))
                nachbarn.setdefault(p.step_id, set()).add(nr)
    # Identische Rahmen mehrfach im Modell: bei Punktegleichstand ihre beiden Zeilen gemeinsam zuordnen.
    gruppen, anzahl = {}, {}
    for start in nachbarn:
        if start in gruppen:
            continue
        gruppe, offen = {start}, [start]
        while offen:
            neue = nachbarn.get(offen.pop(), set()) - gruppe
            gruppe.update(neue)
            offen.extend(neue)
        signatur = frozenset((pmis[n].typ, pmis[n].wert, pmis[n].bezug_text(), frozenset(rollen.get(n, ()))) for n in gruppe)
        nr = anzahl.get(signatur, 0)
        anzahl[signatur] = nr + 1
        for n in gruppe:
            gruppen[n] = (signatur, nr)
    return rollen, gruppen


def _vergleiche_verbund(paare, alt, neu, gruppe_a, gruppe_b):
    """Lokale STEP-Nummern erst ueber die bereits zugeordneten PMI vergleichen."""
    zu_neu = {p.alt.step_id: p.neu.step_id for p in paare if p.alt.step_id}
    def text(ids, pmis):
        return ", ".join(tr("PMI {}").format(pmis[nr].nummer) if nr in pmis else f"#{nr}"
                         for nr in sorted(ids)) or "–"

    alte = {p.step_id: p for p in alt}
    neue = {p.step_id: p for p in neu}
    umgerechnet, befund = {}, {}
    for paar in paare:
        a = gruppe_a.get(paar.alt.step_id, frozenset())
        b = gruppe_b.get(paar.neu.step_id, frozenset())
        if a or b:
            if a not in umgerechnet:
                umgerechnet[a] = {zu_neu.get(n) for n in a}
            if (a, b) not in befund:
                befund[a, b] = ("simultan_mit", text(a, alte), text(b, neue)) if umgerechnet[a] != b else None
            if unterschied := befund[a, b]:
                paar.felder = [f for f in paar.felder if f[0] != "geometrie"]
                paar.felder.append(unterschied)
                paar.status = GEAENDERT
        for feld in ("folgetoleranzen", "simultan_offen"):
            a, b = getattr(paar.alt, feld), getattr(paar.neu, feld)
            if {zu_neu.get(nr) for nr in a} != set(b):
                paar.felder = [f for f in paar.felder if f[0] != "geometrie"]
                paar.felder.append((feld, text(a, alte), text(b, neue)))
                paar.status = GEAENDERT


def vergleiche_pmi(alt: list[Pmi], neu: list[Pmi], zuordnung: dict[int, int] | None = None,
                   schwelle: float = 1.0, zuordnung_ab: dict[int, int] | None = None,
                   geo_status: dict[int, str] | None = None, kantenschluessel=(None, None),
                   modelle=(None, None), lage=None, toleranz=1e-7) -> list[PmiAenderung]:
    """zuordnung: Flaeche neu -> Flaeche alt (aus dem Geometrievergleich), zuordnung_ab die Gegenrichtung;
    ohne: gleiche Indizes. Ohne Kantenschluessel beziehen sich beide PMI-Listen auf denselben Nummernraum."""
    if zuordnung is None:
        zuordnung = {f: f for p in neu for f in (*p.traegerflaechen(), *p.projektionsflaechen)}
    @cache
    def profilfeld(i, j):
        return bereichsfeld(alt[i], neu[j], zuordnung, zuordnung_ab, modelle, lage, toleranz)
    gruppe_a, gruppe_b = simultangruppen(alt), simultangruppen(neu)
    kanten_a, kanten_b = kantenschluessel
    merk_a = _paarmerkmale(alt, simultan=gruppe_a, kanten=kanten_a)
    merk_b = _paarmerkmale(neu, zuordnung, gruppe_b, kanten_b)
    fest = _exakte_paare(alt, neu, merk_a, merk_b, schwelle)
    frei_a = set(range(len(alt))) - {paar[-2] for paar in fest}
    frei_b = set(range(len(neu))) - {paar[-1] for paar in fest}
    paare = []
    for i, j in _kandidaten(alt, neu, merk_b, schwelle, frei_a, frei_b):
        a, b = merk_a[i], merk_b[j]
        s = _punkte(alt[i], neu[j], b.flaechen, a.bezug == b.bezug)
        if s >= schwelle:
            deckung = not (hat_ausschnitt(alt[i]) or hat_ausschnitt(neu[j])) or profilfeld(i, j) is None
            paare.append((s, a.rolle == b.rolle, deckung, a.inhalt == b.inhalt, a.gruppe == b.gruppe, i, j))
    paare.sort(reverse=True)
    for paar in paare:
        i, j = paar[-2:]
        if i in frei_a and j in frei_b:
            frei_a.discard(i)
            frei_b.discard(j)
            fest.append(paar)
    out = [_vergleiche_felder(alt[i], neu[j], zuordnung, zuordnung_ab, geo_status, kantenschluessel,
                              profilfeld(i, j) if hat_ausschnitt(alt[i]) or hat_ausschnitt(neu[j]) else None)
           for *_, i, j in sorted(fest, reverse=True)]
    if any(a.rolle for a in merk_a) or any(b.rolle for b in merk_b):
        _vergleiche_verbund(out, alt, neu, gruppe_a, gruppe_b)
    out += [PmiAenderung(ENTFALLEN, alt[i], None) for i in sorted(frei_a)]
    out += [PmiAenderung(NEU, None, neu[j]) for j in sorted(frei_b)]
    return out


def _bereichstext(p, anderer_verlauf=()):
    if p.bereichsgrenzen is None:
        return "? ↔ ?"
    teile = []
    for i, (name, nr) in enumerate(p.bereichsgrenzen):
        muster = tr("{} (Kante #{}, geometrisch geändert)") if i in anderer_verlauf else tr("{} (Kante #{})")
        teile.append(muster.format(name, nr))
    return " ↔ ".join(teile) or "–"


def _bereichsfeld(a, b, kantenschluessel):
    alt, neu = _grenzen(a, kantenschluessel[0]), _grenzen(b, kantenschluessel[1])
    anderer_verlauf = set()
    if alt is None or neu is None:
        # Der STEP-Typ belegt den Bereich, auch wenn sich seine Enden nicht aufloesen lassen.
        feld = "bereichsgrenzen" if alt == () or neu == () else "grenzen_offen"
    else:
        verschieden = len(alt) != len(neu)
        offen = False
        for i, ((name_a, ka), (name_b, kb)) in enumerate(zip(alt, neu)):
            if name_a != name_b:
                verschieden = True
            if ka is None or kb is None:
                offen = True
            elif ka != kb:
                verschieden = True
                if a.bereichsgrenzen[i] == b.bereichsgrenzen[i]:
                    anderer_verlauf.add(i)
        if not verschieden and not offen:
            return None
        feld = "bereichsgrenzen" if verschieden else "grenzen_offen"
    return feld, _bereichstext(a), _bereichstext(b, anderer_verlauf)


def _vergleiche_felder(a: Pmi, b: Pmi, zuordnung, zuordnung_ab=None, geo_status=None,
                       kantenschluessel=(None, None), profilfeld=None) -> PmiAenderung:
    felder = [profilfeld] if profilfeld else []
    for f in FELDER:
        va, vb = getattr(a, f), getattr(b, f)
        if not _gleich(va, vb):
            felder.append((f, _zahl(va), _zahl(vb)))
    alt, neu = set(a.projektionsflaechen), set(b.projektionsflaechen)
    if (alt or neu) and ({zuordnung.get(i) for i in neu} != alt):
        felder.append(("projektionsflaechen", ", ".join(map(str, sorted(alt))) or "–",
                       ", ".join(map(str, sorted(neu))) or "–"))
    if a.grenzmass != b.grenzmass:
        felder.append(("grenzmass", tr("Ja") if a.grenzmass else tr("Nein"),
                       tr("Ja") if b.grenzmass else tr("Nein")))
    if (a.mittenbezug is None) != (b.mittenbezug is None) or a.mittenbezug != zuordnung.get(b.mittenbezug):
        felder.append(("mittenbezug", _zahl(a.mittenbezug), _zahl(b.mittenbezug)))
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
    mit_ausschnitt = hat_ausschnitt(a) or hat_ausschnitt(b)
    if (not mit_ausschnitt and (a.flaechen or b.flaechen)
            and not _gleiche_flaechen(a, b, zuordnung, zuordnung_ab)):
        felder.append(("flaechen", str(len(a.flaechen)),
                       tr("{} ({} gleich)").format(len(b.flaechen), len(a.flaechen & fb))))
    if a.bereichsgrenzen != [] or b.bereichsgrenzen != []:
        if grenze := _bereichsfeld(a, b, kantenschluessel):
            felder.append(grenze)
    if any(f not in ("grenzen_offen", "profilbereich_offen") for f, _, _ in felder):
        return PmiAenderung(GEAENDERT, a, b, felder)
    geaendert = [f for f in b.flaechen if (geo_status or {}).get(f, "gleich") != "gleich"]
    if felder:
        if geaendert:
            felder.append(("geometrie", "", tr("{} von {} Flächen geändert").format(len(geaendert), len(b.flaechen))))
        return PmiAenderung("ungeklaert", a, b, felder)
    if geaendert:
        return PmiAenderung(GEOMETRIE, a, b, [("geometrie", "", tr("{} von {} Flächen geändert, PMI unverändert")
                                                .format(len(geaendert), len(b.flaechen)))])
    return PmiAenderung(GLEICH, a, b, felder)
