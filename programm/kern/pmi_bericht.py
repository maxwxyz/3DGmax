"""PMI als Tabelle (CSV) und Plausibilitaetspruefung; Export der Aenderungsliste eines Vergleichs."""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass

from .pmi import BEZUG, HINWEIS, MASS, TOLERANZ, Pmi

# Lage-, Richtungs- und Lauftoleranzen brauchen ein Bezugssystem; Formtoleranzen haben keins
MIT_BEZUG = {"Position", "Perpendicularity", "Parallelism", "Angularity", "Concentricity", "Coaxiality",
             "Symmetry", "CircularRunout", "TotalRunout"}
OHNE_BEZUG = {"Flatness", "Straightness", "CircularityOrRoundness", "Cylindricity"}

FEHLER, WARNUNG, INFO = "Fehler", "Warnung", "Hinweis"


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
        zeilen.append({
            "Nr": p.nummer, "Art": p.art, "Typ": p.typ, "Name": p.name, "Wert": p.wert_text(),
            "Nennwert": _zahl(p.nennwert), "Oben": _zahl(p.oben), "Unten": _zahl(p.unten),
            "Grenzmaß": "ja" if p.grenzmass else "", "Passung": p.passung, "Toleranzwert": _zahl(p.wert),
            "Zone": p.zone, "Zonenwert": _zahl(p.zonen_wert), "Material": p.material,
            "Modifikatoren": ", ".join(p.modifikatoren), "Bezüge": p.bezug_text(), "Flächen": len(p.flaechen),
            "Flächen (STEP-#ID)": " ".join(f"#{s}" for s in step if s),
            "Ansichten": ", ".join(je_pmi.get(p.nummer, [])), "Semantisch": "ja" if p.semantisch else "nein",
            "Grafisch": "ja" if p.grafisch else "nein", "STEP-#ID": f"#{p.step_id}" if p.step_id else ""})
    return zeilen


def als_csv(zeilen: list[dict]) -> str:
    puffer = io.StringIO()
    if not zeilen:
        return ""
    w = csv.DictWriter(puffer, fieldnames=list(zeilen[0]), delimiter=";")
    w.writeheader()
    w.writerows(zeilen)
    return puffer.getvalue()


def pruefe(pmi: list[Pmi], ansichten: list | None = None) -> list[Befund]:
    """Unstimmigkeiten und Unplausibles in der PMI eines Modells."""
    out: list[Befund] = []
    bezuege = {p.name: p for p in pmi if p.art == BEZUG and p.typ == "Datum"}
    benutzt: set[str] = set()
    for p in pmi:
        if p.art != TOLERANZ:
            continue
        namen = {n for b in p.bezuege for n in b.name.split("-")}
        benutzt |= namen
        fehlend = sorted(n for n in namen if n not in bezuege)
        if fehlend:
            out.append(Befund(FEHLER, f"Toleranz verweist auf nicht definierte Bezüge: {', '.join(fehlend)}",
                              [p.nummer]))
        if p.typ in MIT_BEZUG and not p.bezuege and p.typ != "Position":
            out.append(Befund(FEHLER, f"{p.typ}: Richtungs-/Lauftoleranz ohne Bezug", [p.nummer]))
        if p.typ == "Position" and not p.bezuege:
            out.append(Befund(WARNUNG, "Positionstoleranz ohne Bezug (nur als Muster sinnvoll)", [p.nummer]))
        if p.typ in OHNE_BEZUG and p.bezuege:
            out.append(Befund(WARNUNG, f"{p.typ}: Formtoleranz mit Bezug", [p.nummer]))
        if p.wert is not None and p.wert <= 0 and p.material != "M" and p.material != "L":
            out.append(Befund(WARNUNG, "Toleranzwert 0 ohne Materialbedingung", [p.nummer]))
    for name, p in sorted(bezuege.items()):
        if name not in benutzt:
            out.append(Befund(WARNUNG, f"Bezug {name} wird von keiner Toleranz verwendet", [p.nummer]))
    for p in pmi:
        if p.art in (MASS, TOLERANZ, BEZUG) and not p.flaechen and p.typ != "DatumTarget":
            out.append(Befund(WARNUNG, "Keine Fläche zugeordnet", [p.nummer]))
        if p.art == MASS and p.nennwert is None:
            out.append(Befund(WARNUNG, "Maß ohne Wert", [p.nummer]))
        if p.art == HINWEIS:
            out.append(Befund(INFO, "Nur grafisch (Hinweis ohne auswertbare Semantik)", [p.nummer]))
    if ansichten:
        in_ansicht = {nr for a in ansichten for nr in a.pmi_nummern}
        ohne = [p.nummer for p in pmi if p.nummer not in in_ansicht and p.art != BEZUG]
        if ohne:
            out.append(Befund(INFO, f"{len(ohne)} PMI in keiner gespeicherten Ansicht", ohne))
    schluessel = Counter((p.art, p.typ, p.wert_text(), p.bezug_text(), frozenset(p.flaechen))
                         for p in pmi if p.art in (MASS, TOLERANZ) and p.flaechen)
    for k, n in schluessel.items():
        if n > 1:
            nummern = [p.nummer for p in pmi if (p.art, p.typ, p.wert_text(), p.bezug_text(),
                                                 frozenset(p.flaechen)) == k]
            out.append(Befund(WARNUNG, f"Doppelt: {k[2]} ({n}×) an denselben Flächen", nummern))
    rang = {FEHLER: 0, WARNUNG: 1, INFO: 2}
    return sorted(out, key=lambda b: (rang[b.stufe], b.nummern[:1]))


def vergleich_csv(vergleich) -> str:
    zeilen = []
    for a in vergleich.aenderungen:
        alt = a.pmi_alt.wert_text() if a.pmi_alt is not None else ""
        neu = a.pmi_neu.wert_text() if a.pmi_neu is not None else ""
        zeilen.append({"Nr": a.nummer, "Kategorie": a.kategorie, "Status": a.status, "Titel": a.titel,
                       "Beschreibung": a.beschreibung, "Alt": alt, "Neu": neu,
                       "Bezüge alt": a.pmi_alt.bezug_text() if a.pmi_alt is not None else "",
                       "Bezüge neu": a.pmi_neu.bezug_text() if a.pmi_neu is not None else "",
                       "Flächen neu": len(a.flaechen_neu), "Flächen alt": len(a.flaechen_alt),
                       "Prüfstatus": a.pruefstatus, "Kommentar": a.kommentar})
    return als_csv(zeilen)
