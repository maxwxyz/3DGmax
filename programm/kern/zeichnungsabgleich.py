"""Gepruefte Zeichnungsangaben mit den semantischen Modell-PMI vergleichen."""

from dataclasses import dataclass
import math
import re

from . import pmi_ableiten
from .pmi import BEZUG, MASS, Pmi


@dataclass(eq=False)
class Blattangabe:
    seite: int
    box: tuple  # relative Koordinaten auf dem sichtbaren Blatt, Ursprung links oben
    text: str
    grundmass: bool = False
    modell: Pmi | None = None
    nur_zeichnung: bool = False


def lese_angabe(text, faktor, grundmass=False):
    # Eine Anzahl gehoert zur Anforderung und braucht eine gesonderte Musterzuordnung.
    if re.match(r"\s*\d+\s*[xX×]", text):
        return None
    if "|" in text:
        teile = [t.strip().translate(str.maketrans({"Ø": "⌀", "∅": "⌀"})) for t in text.split("|")]
        if len(teile) >= 2:
            teile[1] = pmi_ableiten._EINHEIT.sub("", teile[1]).strip()
        if not pmi_ableiten.gueltige_rahmenzellen(teile):
            return None
    daten = pmi_ableiten.aus_text([text], faktor or 1.)
    if not daten:
        return None
    p = Pmi(**daten)
    if p.art == BEZUG:
        return p if re.fullmatch(r"\s*\[[A-Z]{1,2}\]\s*", text) else None
    if p.wert is None and p.nennwert is None:
        return None
    if faktor is None and not re.search(r'(?<=\d)\s*(?:mm|inch|in\b|"|°)', text, re.I):
        return None
    if grundmass and p.art == MASS:
        p.modifikatoren.append("Theoretisch")
    return p


def _felder(p):
    mods = set(p.modifikatoren)
    if p.art == MASS:
        oben, unten = p.grenzen()
        return {"typ": p.typ, "nennwert": p.nennwert, "maximum": oben, "minimum": unten,
                "passung": p.passung, "modifikatoren": sorted(mods)}
    if p.art == BEZUG:
        return {"typ": p.typ, "name": p.name}
    zone = p.zone
    if zone in ("Diameter", "SphericalDiameter"):
        mods.add(zone)
        zone = ""
    # Material kann aus STEP sowohl als eigenes Feld als auch als zusaetzlicher Modifikator vorliegen.
    if p.material == "M":
        mods.discard("Maximum_Material_Requirement")
    if p.material == "L":
        mods.discard("Least_Material_Requirement")
    return {"typ": p.typ, "wert": p.wert, "zone": zone, "zonen_wert": p.zonen_wert,
            "material": p.material, "maximum_toleranz": p.maximum_toleranz,
            "modifikatoren": sorted(mods), "bezuege": [(b.stelle, b.name, sorted(b.modifikatoren),
                {k: sorted(v) for k, v in b.element_modifikatoren.items()})
                for b in sorted(p.bezuege, key=lambda b: b.stelle)],
            "projektionsversatz": p.projektionsversatz if zone == "Projected" else None}


def unterschiede(zeichnung, modell):
    if zeichnung.art != modell.art:
        return ["art"]
    a, b = _felder(zeichnung), _felder(modell)
    if zeichnung.grenzmass:
        a.pop("nennwert", None)  # Die Zeichnung gibt nur die beiden Grenzen an.
    return [k for k, v in a.items() if not (math.isclose(v, b[k], abs_tol=1e-7, rel_tol=0.)
            if isinstance(v, (int, float)) and isinstance(b[k], (int, float)) else v == b[k])]


def kandidaten(zeichnung, modell_pmi):
    if zeichnung is None:
        return []
    passend = [p for p in modell_pmi if p.art == zeichnung.art and p.typ == zeichnung.typ]
    return sorted(passend, key=lambda p: len(unterschiede(zeichnung, p)))


def grenzen_vertauscht(p):
    oben, unten = p.grenzen()
    return oben is not None and unten is not None and unten > oben


def befund(angabe, faktor):
    p = lese_angabe(angabe.text, faktor, angabe.grundmass)
    if p is None:
        return "offen"
    if angabe.nur_zeichnung:
        return "zeichnung"
    if angabe.modell is None or grenzen_vertauscht(angabe.modell):
        return "offen"
    if unterschiede(p, angabe.modell):
        return "geaendert"
    if p.zone == "Projected":
        return "offen"  # Projektionsursprung auf dem Blatt noch nicht geometrisch zugeordnet.
    return "gleich"
