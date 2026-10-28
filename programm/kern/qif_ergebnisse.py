"""Messergebnisse aus QIF 3.0 (MeasurementResults) lesen und den Merkmalen des Modells zuordnen (ohne Qt).

Je Messung (*CharacteristicMeasurement): Wert, Status der Datei (PASS/FAIL/...), Verweis auf das CharacteristicItem
mit Kennung (CharacteristicDesignator/Designator, in der Praxis die Ballonnummer des Pruefplans) und Name.
Zuordnung zu unseren Merkmalen: Kennung = Ballonnummer, sonst Name = PMI-Name, sonst (Modell aus derselben QIF-Datei)
CharacteristicNominalId = PMI-Kennung. Eigene Bewertung gegen die Grenzen der Merkmalsliste: Masse zwischen Mindest-
und Hoechstmass, Form/Lage zwischen 0 und t, Profil an Punkten (vorzeichenbehaftet) innerhalb +-t/2.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

NS = "{http://qifstandards.org/xsd/qif3}"
GUT, SCHLECHT, OFFEN = "gut", "schlecht", ""


@dataclass
class Messwert:
    messung: int  # Id der Messung
    art: str  # z. B. Diameter, Position, PointProfile
    wert: float | None
    status: str  # Status laut Datei (PASS, FAIL, BASIC_OR_TED ...)
    kennung: str = ""  # Designator (Ballonnummer)
    name: str = ""
    nominal: int = 0  # CharacteristicNominalId


def _text(e, pfad: str) -> str:
    x = e.find("/".join(NS + t for t in pfad.split("/")))
    return (x.text or "").strip() if x is not None else ""


def lies(pfad: str) -> tuple[list[Messwert], dict]:
    """(Messwerte, Angaben: Teil, Seriennummern, Gesamtstatus) einer QIF-Datei mit Ergebnissen."""
    wurzel = etree.parse(pfad).getroot()
    items = {}
    for e in wurzel.iter():
        if isinstance(e.tag, str) and e.tag.endswith("CharacteristicItem") and e.get("id"):
            items[e.get("id")] = (_text(e, "CharacteristicDesignator/Designator"), _text(e, "Name"),
                                  int(_text(e, "CharacteristicNominalId") or 0))
    out = []
    for e in wurzel.iter():
        if not (isinstance(e.tag, str) and e.tag.endswith("CharacteristicMeasurement") and e.get("id")):
            continue
        kennung, name, nominal = items.get(_text(e, "CharacteristicItemId"), ("", "", 0))
        wert = _text(e, "Value")
        try:
            zahl = float(wert) if wert else None
        except ValueError:
            zahl = None
        out.append(Messwert(int(e.get("id")), e.tag.replace(NS, "").replace("CharacteristicMeasurement", ""), zahl,
                            _text(e, "Status/CharacteristicStatusEnum"), kennung, name, nominal))
    teil = wurzel.find(f"{NS}Product/{NS}PartSet/{NS}Part")
    angaben = {"teil": teil.get("label", "") if teil is not None else "",
               "seriennummern": [x.text.strip() for x in wurzel.iter(f"{NS}SerialNumber") if x.text],
               "status": _text(wurzel, "Results/MeasurementResultsSet/MeasurementResults/InspectionStatus/"
                                       "InspectionStatusEnum")}
    return out, angaben


def zuordnen(messwerte: list[Messwert], merkmale: list) -> dict[int, list[Messwert]]:
    """Ballonnummer -> Messwerte (Kennung, sonst Name, sonst Nominal-Id bei QIF-Modellen)."""
    je_ballon = {str(m.ballon): m for m in merkmale}
    je_name = {m.pmi.name: m for m in merkmale if m.pmi.name}
    je_id = {m.pmi.step_id: m for m in merkmale if getattr(m.pmi, "quelle", "") == "qif"}
    out: dict[int, list[Messwert]] = {}
    for w in messwerte:
        m = je_ballon.get(w.kennung) or je_name.get(w.name) or je_id.get(w.nominal)
        if m is not None:
            out.setdefault(m.ballon, []).append(w)
    return out


def massgebend(merkmal, werte: list[Messwert]) -> tuple[Messwert | None, str]:
    """(Messwert, Bewertung) des Merkmals: der erste schlechte, sonst der mit der groessten Abweichung."""
    bewertet = [(w, bewertung(merkmal, w)) for w in werte if w.wert is not None]
    if not bewertet:
        return (werte[0] if werte else None), OFFEN
    schlecht = [x for x in bewertet if x[1] == SCHLECHT]
    if schlecht:
        return schlecht[0]
    if all(b == OFFEN for _, b in bewertet):
        return bewertet[0][0], OFFEN
    return max(bewertet, key=lambda x: abs(x[0].wert))[0], GUT


def bewertung(merkmal, w: Messwert) -> str:
    """Eigene Bewertung gegen die Grenzen des Merkmals (OFFEN ohne Wert oder Grenzen, z. B. theoretische Masse)."""
    if w.wert is None or w.status == "BASIC_OR_TED":
        return OFFEN
    oben, unten = merkmal.grenzen()
    if oben is None or unten is None:
        return OFFEN
    p = merkmal.pmi
    if p.art == "toleranz" and w.art.startswith("Point"):  # Abweichung eines Punkts: Zone symmetrisch
        return GUT if abs(w.wert) <= oben / 2 + 1e-12 else SCHLECHT
    return GUT if unten - 1e-12 <= w.wert <= oben + 1e-12 else SCHLECHT
