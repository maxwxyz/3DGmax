"""Geaenderte PMI-Werte verlustfrei in eine Kopie der STEP-Datei schreiben (PLAN §8.28, Stufe 1, ohne Qt).

Der Rueckweg ueber OCCT (XCAF lesen, AP242 schreiben) verliert Teile der semantischen PMI (Versuch an NIST FTC-10:
81 -> 69 PMI, Bezugsstellen fehlen). Deshalb bleibt die Originaldatei Zeichen fuer Zeichen erhalten; ersetzt wird nur
die Zahl der Mess-Entitaet, die ein bearbeiteter Wert in der Datei hat:
- Toleranzwert: Betrag der GEOMETRIC_TOLERANCE (magnitude),
- Nennmass, Grenzmasse: MEASURE_REPRESENTATION_ITEM 'nominal value' / 'upper limit' / 'lower limit' der
  DIMENSIONAL_CHARACTERISTIC_REPRESENTATION,
- Abmasse: TOLERANCE_VALUE (unteres, oberes) der PLUS_MINUS_TOLERANCE,
in der Einheit der Datei. Nicht geschrieben (im Bericht): Passung, Materialbedingung, Werte ohne Entsprechung in der
Datei (z. B. ein neu angegebenes Abmass), Mess-Entitaeten, die mehrere PMI teilen, und eigene PMI.
Die grafische Darstellung (Polylinien) zeigt weiter die alten Werte - der Bericht nennt die betroffenen PMI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..i18n import tr
from . import p21
from .p21 import Ref

ZAHLEN_FELDER = ("nennwert", "oben", "unten", "wert")
MASS_ART = r"(?:POSITIVE_)?(?:LENGTH|PLANE_ANGLE)_MEASURE|RATIO_MEASURE|PARAMETER_VALUE"


@dataclass
class Bericht:
    geschrieben: list[tuple[int, str]] = field(default_factory=list)  # (PMI-Nummer, Feld)
    uebersprungen: list[tuple[int, str, str]] = field(default_factory=list)  # (Nummer, Feld, Grund)
    grafik_veraltet: list[int] = field(default_factory=list)  # PMI mit Darstellung der alten Werte


def _messwert(datei, ref) -> int | None:
    return ref.id if isinstance(ref, Ref) and datei.get(ref) is not None else None


def ziele(datei: p21.P21Datei, p) -> dict[str, int]:
    """Feld -> Id der Mess-Entitaet, die den Wert der PMI in der Datei traegt."""
    out: dict[str, int] = {}
    e = datei.entities.get(p.step_id)
    if e is None:
        return out
    if p.art == "toleranz":
        grund = e.args("GEOMETRIC_TOLERANCE") if e.is_a("GEOMETRIC_TOLERANCE") else e.args()
        if len(grund) >= 3 and _messwert(datei, grund[2]):
            out["wert"] = grund[2].id
        return out
    if p.art != "mass":
        return out
    namen = {"nominal value": "nennwert", "upper limit": "oben", "lower limit": "unten"}
    for rid in datei.referrers().get(p.step_id, []):
        r = datei.entities[rid]
        if r.is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"):
            darst = datei.get(r.args()[1])
            items = list(darst.args(next(iter(darst.parts)))[1] or []) if darst is not None else []
            while items:
                it = items.pop()
                ie = datei.get(it)
                if ie is None:
                    continue
                if ie.is_a("COMPOUND_REPRESENTATION_ITEM"):
                    teil = ie.args("COMPOUND_REPRESENTATION_ITEM")[0]
                    items += list(getattr(teil, "args", [teil])[0] or [])
                    continue
                name = ie.args("REPRESENTATION_ITEM")[0] if ie.is_a("REPRESENTATION_ITEM") else ""
                feld = namen.get(name or "nominal value")
                if feld == "nennwert" or (feld and p.grenzmass):
                    out.setdefault(feld, it.id)
        elif r.is_a("PLUS_MINUS_TOLERANCE") and not p.grenzmass:
            bereich = datei.get(r.args("PLUS_MINUS_TOLERANCE")[0])
            if bereich is not None and bereich.is_a("TOLERANCE_VALUE"):
                unten, oben = bereich.args("TOLERANCE_VALUE")[:2]
                for feld, ref in (("unten", unten), ("oben", oben)):
                    if _messwert(datei, ref):
                        out[feld] = ref.id
    return out


def _faktor(datei, mess_id: int) -> float:
    """Dateiwert * Faktor = Wert in 3DGmax (mm bzw. Grad)."""
    from .pmi_step import einheit_mm, messwert_roh
    _, einheit = messwert_roh(datei, Ref(mess_id))
    e = datei.get(einheit) if isinstance(einheit, Ref) else None
    text = " ".join(datei.entities[mess_id].parts)
    if "PLANE_ANGLE" in text:
        return 57.29577951308232 if e is not None and e.is_a("SI_UNIT") else 1.0
    return einheit_mm(datei, einheit)


def _real(x: float) -> str:
    """REAL nach ISO 10303-21: immer mit Dezimalpunkt."""
    t = f"{x:.12g}"
    return t if ("." in t or "E" in t.upper()) else t + "."


def _anweisung(text: str, eid: int) -> tuple[int, int]:
    """Anfang und Ende (nach ';') der Anweisung #eid im Dateitext."""
    m = re.search(rf"(?<![\w#])#{eid}\s*=", text)
    if m is None:
        raise KeyError(eid)
    in_str = False
    for i in range(m.end(), len(text)):
        if text[i] == "'":
            in_str = not in_str
        elif text[i] == ";" and not in_str:
            return m.start(), i + 1
    raise KeyError(eid)


def _ersetze_zahl(text: str, eid: int, wert: float) -> str:
    a, b = _anweisung(text, eid)
    stueck = text[a:b]
    neu, n = re.subn(rf"((?:{MASS_ART})\s*\(\s*)[-+0-9.Ee]+(\s*\))", lambda m: m.group(1) + _real(wert) + m.group(2),
                     stueck, count=1)
    if n == 0:  # ohne Typangabe: MEASURE_WITH_UNIT(0.1,#5)
        neu, n = re.subn(r"(MEASURE_WITH_UNIT\s*\(\s*)[-+0-9.Ee]+", lambda m: m.group(1) + _real(wert), stueck,
                         count=1)
    if n == 0:
        raise ValueError(eid)
    return text[:a] + neu + text[b:]


def schreibe(quelle: str, ziel: str, pmi: list) -> Bericht:
    """Kopie von 'quelle' mit den bearbeiteten Werten der PMI nach 'ziel'."""
    with open(quelle, "rb") as f:
        roh = f.read()
    try:
        text, kodierung = roh.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        text, kodierung = roh.decode("latin-1"), "latin-1"
    datei = p21.lese_text(text)
    bericht = Bericht()
    verweise = datei.referrers()
    for p in pmi:
        if not p.bearbeitet or not p.original or p.quelle == "eigen":
            continue
        felder = ziele(datei, p)
        for feld, alt in p.original.items():
            neu = getattr(p, feld, None)
            if neu == alt:
                continue
            if feld not in ZAHLEN_FELDER:
                bericht.uebersprungen.append((p.nummer, feld, tr("nicht schreibbar")))
                continue
            eid = felder.get(feld)
            if eid is None or neu is None:
                bericht.uebersprungen.append((p.nummer, feld, tr("keine Entsprechung in der Datei")))
                continue
            if len(verweise.get(eid, [])) > 1:
                bericht.uebersprungen.append((p.nummer, feld, tr("Wert wird von mehreren PMI geteilt")))
                continue
            try:
                text = _ersetze_zahl(text, eid, float(neu) / _faktor(datei, eid))
            except (KeyError, ValueError):
                bericht.uebersprungen.append((p.nummer, feld, tr("Zahl nicht gefunden")))
                continue
            bericht.geschrieben.append((p.nummer, feld))
        if any(n == p.nummer for n, _ in bericht.geschrieben) and p.grafisch:
            bericht.grafik_veraltet.append(p.nummer)
    with open(ziel, "w", encoding=kodierung, newline="") as f:
        f.write(text)
    return bericht
