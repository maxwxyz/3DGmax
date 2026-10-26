"""PMI als Tabelle (CSV) und Plausibilitaetspruefung; Export der Aenderungsliste eines Vergleichs."""

from __future__ import annotations

from ..i18n import tr

import csv
import io
from collections import Counter
from dataclasses import dataclass

from .pmi import BEZUG, HINWEIS, MASS, TOLERANZ, Pmi

ART_TEXT = {MASS: "Maß", TOLERANZ: "Toleranz", BEZUG: "Bezug", HINWEIS: "Hinweis"}
JA, NEIN = "ja", "nein"

# Lage-, Richtungs- und Lauftoleranzen brauchen ein Bezugssystem; Formtoleranzen haben keins
MIT_BEZUG = {"Position", "Perpendicularity", "Parallelism", "Angularity", "Concentricity", "Coaxiality",
             "Symmetry", "CircularRunout", "TotalRunout"}
OHNE_BEZUG = {"Flatness", "Straightness", "CircularityOrRoundness", "Cylindricity"}

FEHLER, WARNUNG, INFO = "Fehler", "Warnung", "Hinweis"  # Schluessel; Anzeige ueber tr()
HINWEIS_STUFE = WARNUNG


@dataclass
class Befund:
    stufe: str
    text: str
    nummern: list[int]


def _zahl(x) -> str:
    if x is None:
        return ""
    return f"{x:.6f}".rstrip("0").rstrip(".").replace(".", ",")


def tabelle(pmi: list[Pmi], ansichten: list, modell=None) -> list[dict]:
    je_pmi: dict[int, list[str]] = {}
    for a in ansichten:
        for nr in a.pmi_nummern:
            je_pmi.setdefault(nr, []).append(a.name)
    zeilen = []
    for p in pmi:
        step = [modell.flaeche_zu_step.get(i) for i in sorted(p.flaechen)] if modell is not None else []
        hoechst, mindest = p.grenzen()
        werte = [("Nr", p.nummer), ("Art", tr(ART_TEXT.get(p.art, p.art))), ("Merkmal", tr(p.merkmal())),
                 ("Typ", p.typ), ("Name", p.name),
                 ("Wert", p.wert_text()), ("Nennwert", _zahl(p.nennwert)), ("Oben", _zahl(p.oben)),
                 ("Unten", _zahl(p.unten)), ("Grenzmaß", tr(JA) if p.grenzmass else ""),
                 ("Höchstmaß", _zahl(hoechst)), ("Mindestmaß", _zahl(mindest)), ("Maßtoleranz", _zahl(p.masstoleranz())),
                 ("Passung", p.passung),
                 ("Toleranzwert", _zahl(p.wert)), ("Zone", p.zone), ("Zonenwert", _zahl(p.zonen_wert)),
                 ("Material", p.material), ("Modifikatoren", ", ".join(p.modifikatoren)), ("Bezüge", p.bezug_text()),
                 ("Flächen", len(p.flaechen)), ("Flächen (STEP-#ID)", " ".join(f"#{s}" for s in step if s)),
                 ("Ansichten", ", ".join(je_pmi.get(p.nummer, []))),
                 ("Semantisch", tr(JA) if p.semantisch else tr(NEIN)), ("Grafisch", tr(JA) if p.grafisch else tr(NEIN)),
                 ("STEP-#ID", f"#{p.step_id}" if p.step_id else "")]
        zeilen.append({tr(k): v for k, v in werte})
    return zeilen


def als_csv(zeilen: list[dict]) -> str:
    puffer = io.StringIO()
    if not zeilen:
        return ""
    w = csv.DictWriter(puffer, fieldnames=list(zeilen[0]), delimiter=";")
    w.writeheader()
    w.writerows(zeilen)
    return puffer.getvalue()


def _flaechenarten(p: Pmi, modell) -> set[str]:
    """Arten der zugeordneten Flaechen ('Ebene', 'Zylinder', ...); leer ohne Modell."""
    if modell is None or not p.flaechen:
        return set()
    from .messen import art_von
    return {art_von(modell.flaechen[i]) for i in p.flaechen if i < len(modell.flaechen)}


def _norm_regeln(pmi: list[Pmi], modell) -> list[Befund]:
    """Regeln, die von der Geometrie oder der Norm abhaengen (ISO GPS / ASME)."""
    out = []
    bezugsflaechen = {p.name: _flaechenarten(p, modell) for p in pmi if p.art == BEZUG and p.typ == "Datum"}
    for p in pmi:
        arten = _flaechenarten(p, modell)
        if p.art == TOLERANZ and p.typ == "Position" and arten and arten <= {"Zylinder", "Kegel"} and \
                "Diameter" not in p.modifikatoren and p.zone != "Diameter":
            out.append(Befund(HINWEIS_STUFE, tr("Position einer Achse ohne ⌀-Zone (zylindrische Zone üblich)"),
                              [p.nummer]))
        if p.art == TOLERANZ and p.typ in ("Flatness", "Straightness") and p.material in ("M", "L") and \
                arten == {"Ebene"}:
            out.append(Befund(FEHLER, tr("{}: Ⓜ/Ⓛ an einer Fläche ohne Größenmaß nicht zulässig").format(
                tr(p.merkmal())), [p.nummer]))
        if p.art == TOLERANZ and p.typ in ("CircularRunout", "TotalRunout") and arten and \
                not arten & {"Zylinder", "Kegel", "Kugel", "Torus", "Ebene"}:
            out.append(Befund(WARNUNG, tr("Lauftoleranz an einer Fläche ohne Drehachse"), [p.nummer]))
        if p.art == TOLERANZ:
            for b in p.bezuege:
                if any(m in ("MaximumMaterialRequirement", "LeastMaterialRequirement") for m in b.modifikatoren):
                    for name in b.name.split("-"):
                        if bezugsflaechen.get(name) == {"Ebene"}:
                            out.append(Befund(WARNUNG, tr("Bezug {} ist eine Ebene: Ⓜ/Ⓛ am Bezug ohne Wirkung").format(
                                name), [p.nummer]))
        if p.art == MASS and p.norm == "iso" and p.passung and p.typ in ("Size_Diameter", "Size_Thickness") and \
                not ({"Envelope", "E"} & set(p.modifikatoren)):
            out.append(Befund(INFO, tr("Passmaß ohne Ⓔ: nach ISO 8015 ohne Hüllbedingung (Form nicht begrenzt)"),
                              [p.nummer]))
    return out


def pruefe(pmi: list[Pmi], ansichten: list | None = None, modell=None) -> list[Befund]:
    """Unstimmigkeiten und Unplausibles in der PMI eines Modells (modell: fuer geometrieabhaengige Regeln)."""
    out: list[Befund] = _norm_regeln(pmi, modell)
    bezuege = {p.name: p for p in pmi if p.art == BEZUG and p.typ == "Datum"}
    benutzt: set[str] = set()
    for p in pmi:
        if p.art != TOLERANZ:
            continue
        namen = {n for b in p.bezuege for n in b.name.split("-")}
        benutzt |= namen
        fehlend = sorted(n for n in namen if n not in bezuege)
        if fehlend:
            out.append(Befund(FEHLER, tr("Toleranz verweist auf nicht definierte Bezüge: {}").format(
                ", ".join(fehlend)), [p.nummer]))
        if p.typ in MIT_BEZUG and not p.bezuege and p.typ != "Position":
            out.append(Befund(FEHLER, tr("{}: Richtungs-/Lauftoleranz ohne Bezug").format(p.typ), [p.nummer]))
        if p.typ == "Position" and not p.bezuege:
            out.append(Befund(WARNUNG, tr("Positionstoleranz ohne Bezug (nur als Muster sinnvoll)"), [p.nummer]))
        if p.typ in OHNE_BEZUG and p.bezuege:
            out.append(Befund(WARNUNG, tr("{}: Formtoleranz mit Bezug").format(p.typ), [p.nummer]))
        if p.norm == "asme" and p.typ in ("Concentricity", "Symmetry"):
            out.append(Befund(WARNUNG, tr("{}: in ASME Y14.5-2018 entfallen – Position, Profil oder Lauf verwenden")
                              .format(tr(p.merkmal())), [p.nummer]))
        if p.wert is not None and p.wert <= 0 and p.material != "M" and p.material != "L":
            out.append(Befund(WARNUNG, tr("Toleranzwert 0 ohne Materialbedingung"), [p.nummer]))
    for name, p in sorted(bezuege.items()):
        if name not in benutzt:
            out.append(Befund(WARNUNG, tr("Bezug {} wird von keiner Toleranz verwendet").format(name), [p.nummer]))
    for p in pmi:
        if p.art in (MASS, TOLERANZ, BEZUG) and not p.flaechen and p.typ != "DatumTarget":
            out.append(Befund(WARNUNG, tr("Keine Fläche zugeordnet"), [p.nummer]))
        if p.art == MASS and p.nennwert is None:
            out.append(Befund(WARNUNG, tr("Maß ohne Wert"), [p.nummer]))
        if p.art == HINWEIS:
            out.append(Befund(INFO, tr("Nur grafisch (Hinweis ohne auswertbare Semantik)"), [p.nummer]))
    if ansichten:
        in_ansicht = {nr for a in ansichten for nr in a.pmi_nummern}
        ohne = [p.nummer for p in pmi if p.nummer not in in_ansicht and p.art != BEZUG]
        if ohne:
            out.append(Befund(INFO, tr("{} PMI in keiner gespeicherten Ansicht").format(len(ohne)), ohne))
    schluessel = Counter((p.art, p.typ, p.wert_text(), p.bezug_text(), frozenset(p.flaechen))
                         for p in pmi if p.art in (MASS, TOLERANZ) and p.flaechen)
    for k, n in schluessel.items():
        if n > 1:
            nummern = [p.nummer for p in pmi if (p.art, p.typ, p.wert_text(), p.bezug_text(),
                                                 frozenset(p.flaechen)) == k]
            out.append(Befund(WARNUNG, tr("Doppelt: {} ({}×) an denselben Flächen").format(k[2], n), nummern))
    rang = {FEHLER: 0, WARNUNG: 1, INFO: 2}
    return sorted(out, key=lambda b: (rang[b.stufe], b.nummern[:1]))


KATEGORIE = {"geometrie": "Geometrie", "pmi": "PMI", "baugruppe": "Baugruppe"}
STATUS = {"geaendert": "geändert", "neu": "neu", "entfernt": "entfernt", "entfallen": "entfallen",
          "geometrie": "Geometrie unter PMI geändert", "verschoben": "verschoben", "grafik": "Darstellung geändert"}
PRUEF = {"offen": "offen", "geprueft": "geprüft", "abgelehnt": "abgelehnt"}
CSV_SPALTEN = ("Nr", "Art", "Merkmal", "Typ", "Name", "Wert", "Nennwert", "Oben", "Unten", "Grenzmaß", "Höchstmaß",
               "Mindestmaß", "Maßtoleranz", "Passung", "Toleranzwert",
               "Zone", "Zonenwert", "Material", "Modifikatoren", "Bezüge", "Flächen", "Flächen (STEP-#ID)",
               "Ansichten", "Semantisch", "Grafisch", "STEP-#ID", "Kategorie", "Status", "Titel", "Beschreibung",
               "Alt", "Neu", "Bezüge alt", "Bezüge neu", "Flächen neu", "Flächen alt", "Prüfstatus", "Kommentar",
               JA, NEIN)


def vergleich_csv(vergleich) -> str:
    zeilen = []
    for a in vergleich.aenderungen:
        alt = a.pmi_alt.wert_text() if a.pmi_alt is not None else ""
        neu = a.pmi_neu.wert_text() if a.pmi_neu is not None else ""
        werte = [("Nr", a.nummer), ("Kategorie", tr(KATEGORIE.get(a.kategorie, a.kategorie))),
                 ("Status", tr(STATUS.get(a.status, a.status))), ("Titel", a.titel), ("Beschreibung", a.beschreibung),
                 ("Alt", alt), ("Neu", neu),
                 ("Bezüge alt", a.pmi_alt.bezug_text() if a.pmi_alt is not None else ""),
                 ("Bezüge neu", a.pmi_neu.bezug_text() if a.pmi_neu is not None else ""),
                 ("Flächen neu", len(a.flaechen_neu)), ("Flächen alt", len(a.flaechen_alt)),
                 ("Prüfstatus", tr(PRUEF.get(a.pruefstatus, a.pruefstatus))), ("Kommentar", a.kommentar)]
        zeilen.append({tr(k): v for k, v in werte})
    return als_csv(zeilen)
