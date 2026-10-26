"""Testvarianten von NIST CTC-01 fuer den Vergleich erzeugen (gezielte Textaenderungen der STEP-Datei).

Aufruf: pixi run python werkzeuge/testmodelle.py   -> tests/daten/varianten/
- ctc01_pmi.stp      Geometrie gleich, PMI geaendert (Toleranzwert, Abmass, Bezugssystem)
- ctc01_geo.stp      Bohrung Ø20 -> Ø21 (Zylinder, Kreise, Ecken, Naht), PMI gleich
- ctc01_geo_pmi.stp  wie ctc01_geo, dazu Mass 20 -> 21
"""

from __future__ import annotations

import math
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
from programm.kern import p21  # noqa: E402

QUELLE = os.path.join(WURZEL, "tests", "daten", "nist_ctc_01_asme1_ap242-e1.stp")
ZIEL = os.path.join(WURZEL, "tests", "daten", "varianten")
BOHRUNG = (814, 815)  # Flaechen der Bohrung Ø20 (Halbschalen), Achse durch (30, -125, z) in Richtung z
ACHSE = (30.0, -125.0)
R_ALT, R_NEU = 10.0, 10.5


def _ersetze_entitaet(text: str, eid: int, neu: str) -> str:
    """Die Anweisung '#eid=...;' durch 'neu' ersetzen (eine Zeile)."""
    muster = re.compile(rf"^#{eid}=.*?;\s*$", re.M | re.S)
    treffer = muster.search(text)
    if not treffer:
        raise KeyError(eid)
    return text[:treffer.start()] + neu + "\n" + text[treffer.end():].lstrip("\n")


def _zahl(x: float) -> str:
    s = repr(float(x))
    return s if "." in s or "E" in s or "e" in s else s + "."


def _referenzen(d: p21.P21Datei, eid: int, gesehen: set[int]):
    if eid in gesehen:
        return
    gesehen.add(eid)
    e = d.entities[eid]
    for r in p21._refs_in(list(e.parts.values())):
        if d.entities.get(r) is not None and not d.entities[r].is_a("AXIS2_PLACEMENT_3D"):
            _referenzen(d, r, gesehen)


def bohrung_aufweiten(text: str) -> str:
    d = p21.lese_text(text)
    alle: set[int] = set()
    for f in BOHRUNG:
        _referenzen(d, f, alle)
    for eid in sorted(alle):
        e = d.entities[eid]
        if e.is_a("CYLINDRICAL_SURFACE") and abs(e.args()[2] - R_ALT) < 1e-9:
            text = _ersetze_entitaet(text, eid, f"#{eid}=CYLINDRICAL_SURFACE('',#{e.args()[1].id},{_zahl(R_NEU)});")
        elif e.is_a("CIRCLE") and abs(e.args()[2] - R_ALT) < 1e-9:
            text = _ersetze_entitaet(text, eid, f"#{eid}=CIRCLE('{e.args()[0]}',#{e.args()[1].id},{_zahl(R_NEU)});")
        elif e.is_a("CARTESIAN_POINT"):
            x, y, z = e.args()[1]
            dx, dy = x - ACHSE[0], y - ACHSE[1]
            r = math.hypot(dx, dy)
            if abs(r - R_ALT) < 1e-6:
                s = R_NEU / r
                text = _ersetze_entitaet(text, eid, f"#{eid}=CARTESIAN_POINT('{e.args()[0]}',("
                                         f"{_zahl(ACHSE[0] + dx * s)},{_zahl(ACHSE[1] + dy * s)},{_zahl(z)}));")
    return text


def _messwert(text: str, eid: int, neu: float) -> str:
    """Wert in einer (komplexen) MEASURE_WITH_UNIT-Entitaet ersetzen."""
    muster = re.compile(rf"(^#{eid}=.*?(?:LENGTH_MEASURE|POSITIVE_LENGTH_MEASURE)\()([-0-9.Ee+]+)(\))", re.M | re.S)
    t, n = muster.subn(lambda m: m.group(1) + _zahl(neu) + m.group(3), text, count=1)
    if n != 1:
        raise KeyError(eid)
    return t


def pmi_aendern(text: str) -> str:
    d = p21.lese_text(text)
    # 1. Position.1: Toleranzwert 0.75 -> 0.5
    pos = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == "Position.1")
    text = _messwert(text, pos.args("GEOMETRIC_TOLERANCE")[2].id, 0.5)
    # 2. Ø35 0/-0.2: unteres Abmass -0.2 -> -0.3
    tv = d.entities[58]  # TOLERANCE_VALUE(#72 unten, #71 oben) des Masses #120
    text = _messwert(text, tv.args()[0].id, -0.3)
    # 3. Flatness.1 0.2 -> 0.1
    flach = next(e for e in d.entities.values() if e.is_a("FLATNESS_TOLERANCE"))
    text = _messwert(text, flach.args()[2].id, 0.1)
    return text


def mass_20_auf_21(text: str) -> str:
    d = p21.lese_text(text)
    for dim in (122, 123):
        dcr = next(d.entities[r] for r in d.referrers()[dim]
                   if d.entities[r].is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"))
        sdr = d.get(dcr.args()[1])
        for it in sdr.args()[1]:
            e = d.get(it)
            if e.is_a("REPRESENTATION_ITEM") and e.args("REPRESENTATION_ITEM")[0] == "nominal value":
                text = _messwert(text, it.id, 21.0)
    return text


def main():
    os.makedirs(ZIEL, exist_ok=True)
    with open(QUELLE, encoding="latin-1", newline="") as f:
        text = f.read()
    varianten = {"ctc01_pmi.stp": pmi_aendern(text), "ctc01_geo.stp": bohrung_aufweiten(text)}
    varianten["ctc01_geo_pmi.stp"] = mass_20_auf_21(varianten["ctc01_geo.stp"])
    for name, inhalt in varianten.items():
        with open(os.path.join(ZIEL, name), "w", encoding="latin-1", newline="") as f:
            f.write(inhalt)
        print("geschrieben:", name)


if __name__ == "__main__":
    main()
