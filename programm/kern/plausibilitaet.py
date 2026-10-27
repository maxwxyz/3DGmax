"""Plausibilitaet der Spezifikation (PLAN §8.22): Widersprueche und unvollstaendige Angaben in den PMI eines Modells.

Ergaenzt kern.pmi_bericht.pruefe um Regeln, die mehrere PMI oder die Geometrie zusammen betrachten:
- Hierarchie: Form < Richtung < Lage an denselben Flaechen; groessere untergeordnete Toleranz ist ohne Wirkung.
- Mass und Form: unter der Huellbedingung (ASME Rule #1, ISO mit Ⓔ) begrenzt die Masstoleranz die Form bereits.
- Vollstaendigkeit: Flaechen ohne Angabe (ohne Allgemeintoleranz), Ⓜ/Ⓛ ohne Mass am Element.
- Bezugssystem: Sekundaerbezug parallel zum Primaerbezug, offene Freiheitsgrade einer Lagetoleranz, Bezugselement
  ohne eigene Formtoleranz.
- Ueberbestimmung: zwei Masse an denselben Flaechen mit verschiedenen Werten; geschlossene Masskette (tolerierte
  Laengenmasse zwischen parallelen Ebenen bilden einen Kreis – eines sollte Hilfsmass sein).
- Werte: unsymmetrische Zone groesser als die Toleranz, oberes < unteres Abmass, unbekannte Passung, projizierte Zone
  ohne Bohrung/Zapfen.
- Geometrie: Nennmass passt nicht zum Modell (Durchmesser, Radius, Abstand paralleler Ebenen).
- Theoretisch exakte Masse: mit Toleranz angegeben; Lage doppelt toleriert (toleriertes Lagemass und Position/Profil).
- Muster: ein Groessenmass an Elementen verschiedener Groesse.
- Bezugsstellen: zu wenige Stellen fuer die Stelle im Bezugssystem (Ebene primaer 3, sekundaer 2, tertiaer 1),
  Bezugsstellen ohne Bezug in einem Toleranzrahmen.
"""

from __future__ import annotations

import numpy as np

from ..i18n import tr
from . import toleranzzone as tz

GEOMETRIE_TOLERANZ = 1e-3  # mm: Nennmass und Modell gelten bis hier als gleich


def _befund(stufe, kategorie, text, nummern, flaechen=None):
    from .pmi_bericht import Befund
    return Befund(stufe, text, list(nummern), kategorie, set(flaechen or ()))


def _ebene(f):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane
    s = BRepAdaptor_Surface(f)
    if s.GetType() != GeomAbs_Plane:
        return None
    pl = s.Plane()
    n = pl.Axis().Direction()
    o = pl.Location()
    return np.array([o.X(), o.Y(), o.Z()]), np.array([n.X(), n.Y(), n.Z()])


def hierarchie(pmi, modell) -> list:
    from .pmi_bericht import WARNUNG
    out = []
    for p in pmi:
        if p.art != "toleranz" or p.wert is None:
            continue
        q = tz._uebergeordnet(p, pmi)
        if q is not None and p.wert >= q.wert:
            out.append(_befund(WARNUNG, "widerspruch", tr("{} {:.4g} ist nicht kleiner als {} {:.4g} an derselben Fläche – "
                                                        "ohne Wirkung").format(tr(p.merkmal()), p.wert,
                                                                                tr(q.merkmal()), q.wert),
                               [p.nummer, q.nummer], p.flaechen & q.flaechen))
    return out


def mass_und_form(pmi, modell) -> list:
    """Formtoleranz nicht kleiner als die Masstoleranz desselben Elements unter Huellbedingung."""
    from .pmi_bericht import INFO
    out = []
    for p in pmi:
        if p.art != "toleranz" or p.typ not in tz.FORM or p.wert is None:
            continue
        for m in pmi:
            if m.art != "mass" or not (m.flaechen & p.flaechen) or m.masstoleranz() is None:
                continue
            huelle = m.norm == "asme" or {"Envelope", "E"} & set(m.modifikatoren)
            if huelle and p.wert >= m.masstoleranz():
                out.append(_befund(INFO, "widerspruch", tr("{} {:.4g} ist nicht kleiner als die Maßtoleranz {:.4g}: die "
                                                         "Hüllbedingung begrenzt die Form bereits").format(
                    tr(p.merkmal()), p.wert, m.masstoleranz()), [p.nummer, m.nummer], p.flaechen))
    return out


def vollstaendigkeit(pmi, modell) -> list:
    from .pmi_bericht import INFO, WARNUNG
    out = []
    if modell is not None:
        belegt = {i for p in pmi if p.art in ("mass", "toleranz", "bezug") for i in p.flaechen}
        frei = set(range(len(modell.flaechen))) - belegt
        allgemein = tz.allgemein_aus_hinweisen(pmi)
        if frei and allgemein is None:
            out.append(_befund(INFO, "unvollstaendig", tr("{} von {} Flächen ohne Maß- oder Toleranzangabe und keine "
                                                          "Allgemeintoleranz angegeben").format(len(frei),
                                                                                                len(modell.flaechen)),
                               [], frei))
        elif frei:
            out.append(_befund(INFO, "unvollstaendig", tr("{} Flächen ohne eigene Angabe – durch {} abgedeckt").format(
                len(frei), allgemein.text()), [], frei))
    for p in pmi:
        if p.art == "toleranz" and p.material in ("M", "L") and modell is not None and p.flaechen:
            flaechen = [modell.flaechen[i] for i in p.flaechen if i < len(modell.flaechen)]
            achsen = tz._achsen(flaechen)
            if achsen and not any(m.art == "mass" and m.flaechen & p.flaechen and m.grenzen()[0] is not None
                                  for m in pmi):
                out.append(_befund(WARNUNG, "unvollstaendig", tr("{} mit Ⓜ/Ⓛ ohne Maß am Element: Bonus nicht "
                                                                 "bestimmbar").format(tr(p.merkmal())),
                                   [p.nummer], p.flaechen))
    return out


def bezugssystem(pmi, modell) -> list:
    from .pmi_bericht import INFO, WARNUNG
    out = []
    if modell is None:
        return out
    bezuege = {p.name: p for p in pmi if p.art == "bezug" and p.typ == "Datum"}

    def geometrie(name):
        b = bezuege.get(name)
        if b is None:
            return None
        flaechen = [modell.flaechen[i] for i in sorted(b.flaechen) if i < len(modell.flaechen)]
        achsen = tz._achsen(flaechen)
        if achsen:
            return "achse", achsen[0][1]
        ebenen = [e for e in (_ebene(f) for f in flaechen) if e is not None]
        if ebenen:
            return "ebene", ebenen[0][1]
        return None

    for p in pmi:
        if p.art != "toleranz" or len(p.bezuege) < 2:
            continue
        g = [geometrie(b.name) for b in sorted(p.bezuege, key=lambda b: b.stelle)]
        if g[0] and g[1] and g[0][0] == g[1][0] == "ebene" and abs(g[0][1] @ g[1][1]) > 0.9999:
            out.append(_befund(WARNUNG, "bezug", tr("Sekundärbezug {} ist parallel zum Primärbezug {} – er legt keinen "
                                                    "weiteren Freiheitsgrad fest").format(
                p.bezuege[1].name, p.bezuege[0].name), [p.nummer]))
    # Lagetoleranz (Position, Profil mit Bezug) an Achsen: wie viele Verschiebungen legt das Bezugssystem fest?
    for p in pmi:
        if p.art != "toleranz" or p.typ != "Position" or not p.bezuege or not p.flaechen:
            continue
        g = [x for x in (geometrie(b.name) for b in p.bezuege) if x is not None]
        normalen = [d for art, d in g if art == "ebene"]
        rang = np.linalg.matrix_rank(np.array(normalen), tol=1e-3) if normalen else 0
        feste = rang + (2 if any(art == "achse" for art, _ in g) else 0)
        if 0 < feste < 3 and len(g) == len(p.bezuege):
            out.append(_befund(INFO, "bezug", tr("Bezugssystem {} legt die Lage nur in {} von 3 Richtungen fest (z. B. als "
                                                 "Muster gemeint?)").format(p.bezug_text(), feste), [p.nummer]))
    # Bezugselement (Ebene) ohne eigene Formtoleranz
    for name, b in sorted(bezuege.items()):
        g = geometrie(name)
        if g and g[0] == "ebene" and not any(q.art == "toleranz" and q.flaechen & b.flaechen for q in pmi):
            out.append(_befund(INFO, "bezug", tr("Bezugselement {} ohne eigene Form- oder Lagetoleranz").format(name),
                               [b.nummer], b.flaechen))
    return out


def ueberbestimmung(pmi, modell) -> list:
    from .pmi_bericht import FEHLER
    out = []
    # nur Masse, die vollstaendig an Flaechen haengen (ein Abstandsmass an nur einer Flaeche endet an einer Kante
    # oder einem Punkt; zwei solche Masse an derselben Flaeche widersprechen sich nicht)
    masse = [p for p in pmi if p.art == "mass" and p.nennwert is not None and p.flaechen and not p.kanten
             and (len(p.flaechen) >= 2 or p.typ.startswith("Size"))]
    for i, a in enumerate(masse):
        for b in masse[i + 1:]:
            if a.typ == b.typ and a.flaechen == b.flaechen and \
                    abs(a.nennwert - b.nennwert) > max(1e-6, 1e-6 * abs(a.nennwert)):
                out.append(_befund(FEHLER, "widerspruch", tr("Zwei Maße an denselben Flächen mit verschiedenen Werten: "
                                                             "{} und {}").format(a.wert_text(), b.wert_text()),
                                   [a.nummer, b.nummer], a.flaechen))
    return out


def geschlossene_ketten(pmi, modell) -> list:
    """Tolerierte Abstandsmasse zwischen parallelen Ebenen je Richtung als Graph (Knoten: Lagen); ein Kreis aus drei
    oder mehr Massen ist eine geschlossene Masskette – die Toleranzen widersprechen sich, eines sollte Hilfsmass sein."""
    from collections import defaultdict, deque
    from .pmi_bericht import WARNUNG
    if modell is None:
        return []
    kanten = defaultdict(list)  # Richtung -> [(Lage a, Lage b, PMI)]
    for p in pmi:
        if p.art != "mass" or p.nennwert is None or p.typ not in ("Location_LinearDistance", "Size_Thickness") or \
                len(p.flaechen) != 2 or None in p.grenzen():
            continue
        e = [_ebene(modell.flaechen[i]) for i in sorted(p.flaechen) if i < len(modell.flaechen)]
        if len(e) != 2 or None in e or abs(e[0][1] @ e[1][1]) < 0.9999:
            continue
        n = e[0][1] * (1 if max(e[0][1], key=abs) > 0 else -1)  # Richtung eindeutig (groesste Komponente positiv)
        a, b = sorted(round(float(x[0] @ n), 4) for x in e)
        if b - a > 1e-6:
            kanten[tuple(np.round(n, 6))].append((a, b, p))
    out = []
    for liste in kanten.values():
        nachbarn = defaultdict(list)
        for a, b, p in liste:
            # Weg von a nach b ueber die bisherigen Masse? Dann schliesst p eine Kette
            vorher = {a: None}
            offen = deque([a])
            while offen and b not in vorher:
                x = offen.popleft()
                for y, q in nachbarn[x]:
                    if y not in vorher:
                        vorher[y] = (x, q)
                        offen.append(y)
            if b in vorher:
                kette, x = [p], b
                while vorher[x] is not None:
                    x, q = vorher[x][0], vorher[x][1]
                    kette.append(q)
                if len(kette) >= 3:
                    out.append(_befund(WARNUNG, "widerspruch", tr(
                        "Geschlossene Maßkette: {} – die Toleranzen bestimmen sich gegenseitig, ein Maß als Hilfsmaß "
                        "(in Klammern) angeben").format(", ".join(q.wert_text() for q in kette)),
                        [q.nummer for q in kette], {i for q in kette for i in q.flaechen}))
                    continue
            nachbarn[a].append((b, p))
            nachbarn[b].append((a, p))
    return out


def werte(pmi, modell) -> list:
    from .pmi_bericht import FEHLER, WARNUNG
    out = []
    for p in pmi:
        if p.art == "toleranz" and p.wert is not None:
            u = tz.unsymmetrisch(p)
            if u is not None and abs(u) > p.wert:
                out.append(_befund(FEHLER, "wert", tr("Unsymmetrische Zone {:.4g} größer als die Toleranz {:.4g}").format(
                    u, p.wert), [p.nummer]))
            if p.zone == "Projected" and modell is not None and p.flaechen and \
                    not tz._achsen([modell.flaechen[i] for i in p.flaechen if i < len(modell.flaechen)]):
                out.append(_befund(WARNUNG, "wert", tr("Projizierte Zone an einem Element ohne Achse"), [p.nummer]))
        if p.art == "mass":
            if not p.grenzmass and p.oben is not None and p.unten is not None and p.oben < p.unten:
                out.append(_befund(FEHLER, "wert", tr("Oberes Abmaß kleiner als unteres ({} / {})").format(p.oben, p.unten),
                                   [p.nummer]))
            if p.passung and p.nennwert is not None and "/" not in p.passung and p.abmasse()[0] is None:
                out.append(_befund(WARNUNG, "wert", tr("Passung {} nach ISO 286 unbekannt").format(p.passung),
                                   [p.nummer]))
    return out


def geometrie(pmi, modell) -> list:
    """Nennmass gegen das Modell: Durchmesser/Radius am Zylinder, Abstand paralleler Ebenen."""
    from .pmi_bericht import WARNUNG
    out = []
    if modell is None:
        return out
    for p in pmi:
        if p.art != "mass" or p.nennwert is None or not p.flaechen:
            continue
        flaechen = [modell.flaechen[i] for i in sorted(p.flaechen) if i < len(modell.flaechen)]
        ist = None
        if p.typ in ("Size_Diameter", "Size_Radius"):
            achsen = tz._achsen(flaechen)
            if achsen:
                radien = {round(a[3], 6) for a in achsen}
                r = max(radien, key=lambda x: -abs(x * (2 if p.typ == "Size_Diameter" else 1) - abs(p.nennwert)))
                ist = r * (2 if p.typ == "Size_Diameter" else 1)
        elif p.typ in ("Location_LinearDistance", "Size_Thickness") and len(flaechen) == 2:
            e1, e2 = _ebene(flaechen[0]), _ebene(flaechen[1])
            if e1 and e2 and abs(e1[1] @ e2[1]) > 0.9999:
                ist = abs((e2[0] - e1[0]) @ e1[1])
        if ist is not None and abs(ist - abs(p.nennwert)) > GEOMETRIE_TOLERANZ:
            out.append(_befund(WARNUNG, "geometrie", tr("Nennmaß {:.4g} passt nicht zum Modell ({:.4f})").format(
                abs(p.nennwert), ist), [p.nummer], p.flaechen))
    return out


THEORETISCH = {"Theoretisch", "Basic"}
LAGE_TOLERANZEN = {"Position", "ProfileOfSurface", "ProfileOfLine"}
STELLEN_NOETIG = {1: 3, 2: 2, 3: 1}  # Bezugsstellen je Stelle im Bezugssystem, wenn der Bezug eine Ebene ist


def _theoretisch(p) -> bool:
    return bool(THEORETISCH & set(p.modifikatoren))


def theoretische_masse(pmi, modell) -> list:
    from .pmi_bericht import FEHLER, WARNUNG
    out = []
    for m in pmi:
        if m.art != "mass":
            continue
        if _theoretisch(m) and (m.oben is not None or m.unten is not None or m.passung):
            out.append(_befund(FEHLER, "wert", tr("Theoretisch exaktes Maß {} mit Toleranz").format(m.wert_text()),
                               [m.nummer], m.flaechen))
            continue
        if not m.typ.startswith("Location") or _theoretisch(m) or m.masstoleranz() is None:
            continue
        for p in pmi:
            if p.art != "toleranz" or p.typ not in LAGE_TOLERANZEN or not p.bezuege or not m.flaechen & p.flaechen:
                continue
            bezug = set().union(*(tz._bezug_flaechen(b.name, pmi) for b in p.bezuege))
            rest = m.flaechen - p.flaechen
            if rest and rest <= bezug:  # das Mass verbindet das Element mit einem seiner Bezuege
                out.append(_befund(WARNUNG, "widerspruch", tr(
                    "Lage doppelt toleriert: {} und toleriertes Lagemaß {} – das Lagemaß als theoretisch exakt "
                    "(eingerahmt) angeben").format(tr(p.merkmal()), m.wert_text()), [p.nummer, m.nummer],
                    m.flaechen & p.flaechen))
                break
    return out


def _achsen_von(modell, flaechen) -> list:
    return tz._achsen([modell.flaechen[i] for i in sorted(flaechen) if i < len(modell.flaechen)])


def muster(pmi, modell) -> list:
    """Groessenmass an mehreren Achsen (Muster): gleiche Groesse und Toleranzen an allen Elementen."""
    from .pmi_bericht import WARNUNG
    out = []
    if modell is None:
        return out
    for m in pmi:
        if m.art != "mass" or m.typ not in ("Size_Diameter", "Size_Radius") or len(m.flaechen) < 2:
            continue
        achsen = _achsen_von(modell, m.flaechen)
        if len(achsen) < 2:
            continue
        radien = sorted({round(a[3], 4) for a in achsen})
        if len(radien) > 1:
            out.append(_befund(WARNUNG, "muster", tr("Maß {} gilt für {} Elemente verschiedener Größe ({})").format(
                m.wert_text(), len(achsen), ", ".join("⌀{:.4g}".format(2 * r) for r in radien)), [m.nummer],
                m.flaechen))
    return out


def _buchstabe(name: str) -> str:
    return "".join(c for c in name if c.isalpha())


def bezugsstellen(pmi, modell) -> list:
    from .pmi_bericht import INFO, WARNUNG
    stellen: dict[str, list] = {}
    for p in pmi:
        if p.art == "bezug" and p.typ == "DatumTarget" and _buchstabe(p.name):
            stellen.setdefault(_buchstabe(p.name), []).append(p)
    out = []
    genutzt: dict[str, int] = {}  # Buchstabe -> kleinste Stelle im Bezugssystem
    for p in pmi:
        for b in p.bezuege if p.art == "toleranz" else ():
            genutzt[b.name] = min(genutzt.get(b.name, 3), b.stelle)
    for buchstabe, liste in sorted(stellen.items()):
        nummern = [p.nummer for p in liste]
        if buchstabe not in genutzt:
            out.append(_befund(INFO, "bezug", tr("Bezugsstellen {} ohne Bezug {} in einem Toleranzrahmen").format(
                ", ".join(p.name for p in liste), buchstabe), nummern))
            continue
        flaechen = set().union(*(p.flaechen for p in liste))
        eben = modell is not None and flaechen and all(_ebene(modell.flaechen[i]) is not None
                                                       for i in flaechen if i < len(modell.flaechen))
        noetig = STELLEN_NOETIG[genutzt[buchstabe]]
        if eben and len(liste) < noetig:
            out.append(_befund(WARNUNG, "bezug", tr(
                "Bezug {} ({}. Stelle) aus {} Bezugsstelle(n) – eine Ebene braucht hier {}").format(
                buchstabe, genutzt[buchstabe], len(liste), noetig), nummern, flaechen))
    return out


REGELN = (hierarchie, mass_und_form, vollstaendigkeit, bezugssystem, ueberbestimmung, geschlossene_ketten, werte,
          geometrie, theoretische_masse, muster, bezugsstellen)
KATEGORIE_TEXT = {"widerspruch": "Widerspruch", "unvollstaendig": "Unvollständig", "bezug": "Bezugssystem",
                  "wert": "Wert", "geometrie": "Geometrie", "muster": "Muster", "": "Angabe"}


def pruefe(pmi, modell) -> list:
    out = []
    for regel in REGELN:
        try:
            out += regel(pmi, modell)
        except Exception:  # noqa: BLE001 - eine Regel darf die Pruefung nicht abbrechen
            continue
    return out
