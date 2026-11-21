"""Gepruefte Zeichnungsangaben mit den semantischen Modell-PMI vergleichen."""

from dataclasses import dataclass
import math
import re

from . import pmi_ableiten
from .pmi import BEZUG, MASS, Pmi


@dataclass(frozen=True)
class Musterziel:
    ort: tuple
    flaechen: frozenset
    modell: Pmi | None = None
    nur_zeichnung: bool = False
    tauschgruppe: frozenset = frozenset()

    @property
    def mitte(self):
        return self.ort[:2]


@dataclass(eq=False)
class Blattangabe:
    seite: int
    box: tuple  # relative Koordinaten auf dem sichtbaren Blatt, Ursprung links oben
    text: str
    grundmass: bool = False
    modell: Pmi | None = None
    nur_zeichnung: bool = False
    zielkonflikt: bool = False
    blattziel: tuple | None = None  # x/Breite, y/Hoehe, r/Breite; bei Ellipsen zusaetzlich b/Breite und Winkel
    musterziele: tuple[Musterziel, ...] = ()
    einzelpruefung: bool = False

    def zugeordnete_pmi(self):
        if self.einzelpruefung:
            return [z.modell for z in self.musterziele if z.modell is not None]
        return [self.modell] if self.modell is not None else []


_MENGE = re.compile(r"^\s*([1-9][0-9]{0,3})\s*[xX×]\s*(?=[Ø∅⌀])")


def musteranzahl(text):
    m = _MENGE.match(text)
    return int(m[1]) if m else 0


def muster_deckt(anzahl, ziele, modell):
    if not ziele or modell is None or modell.typ != "Size_Diameter" or len(ziele) != anzahl:
        return False
    if len({z.mitte for z in ziele}) != anzahl:
        return False
    waende = [z.flaechen for z in ziele if not z.tauschgruppe]
    gruppen = {}
    for z in ziele:
        if z.tauschgruppe:
            gruppen[z.tauschgruppe] = gruppen.get(z.tauschgruppe, 0)+1
    for gruppe, gewaehlt in gruppen.items():
        if len(gruppe) != gewaehlt:
            return False
        waende.extend(gruppe)
    erfasst = set()
    for wand in waende:
        anteil = wand & modell.flaechen
        if not anteil or anteil & erfasst:
            return False
        erfasst.update(anteil)
    return erfasst == modell.flaechen


def lese_angabe(text, faktor, grundmass=False):
    if m := _MENGE.match(text):
        text = text[m.end():]
    elif re.match(r"\s*\d+\s*[xX×]", text):
        return None
    # Bei zwei aufsteigenden Durchmessergrenzen kann der Plotter einen Bindestrich ausgeben.
    zahl = r"(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)"
    grenzen = re.fullmatch(rf'([⌀Ø∅]\s*)({zahl})\s*-\s*({zahl})(\s*(?:mm|in|inch|")?)\s*', text, re.I)
    if grenzen and float(grenzen[2].replace(",", ".")) < float(grenzen[3].replace(",", ".")):
        text = f"{grenzen[1]}{grenzen[2]}–{grenzen[3]}{grenzen[4]}"
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


def wertebefund(p, modell):
    if p is None or modell is None or grenzen_vertauscht(modell):
        return "offen"
    if unterschiede(p, modell):
        return "geaendert"
    if p.zone == "Projected":
        return "offen"  # Projektionsursprung auf dem Blatt noch nicht geometrisch zugeordnet.
    return "gleich"


def einzelbefund(p, ziel):
    if p is None:
        return "offen"
    if ziel.nur_zeichnung and ziel.modell is None:
        return "zeichnung"
    m = ziel.modell
    if m is None or m.art != p.art or m.typ != p.typ or not m.flaechen or not m.flaechen <= ziel.flaechen:
        return "offen"
    return wertebefund(p, m)


def befund(angabe, faktor):
    p = lese_angabe(angabe.text, faktor, angabe.grundmass)
    if p is None or angabe.zielkonflikt:
        return "offen"
    if angabe.nur_zeichnung:
        return "zeichnung"
    anzahl = musteranzahl(angabe.text)
    if angabe.einzelpruefung:
        ziele = angabe.musterziele
        if not anzahl or len(ziele) != anzahl or len({z.flaechen for z in ziele}) != anzahl:
            return "offen"
        modelle = angabe.zugeordnete_pmi()
        if len({id(m) for m in modelle}) != len(modelle):
            return "offen"
        befunde = {einzelbefund(p, z) for z in ziele}
        if "offen" in befunde:
            return "offen"
        return befunde.pop() if len(befunde) == 1 else "geaendert"
    if anzahl and not muster_deckt(anzahl, angabe.musterziele, angabe.modell):
        return "offen"
    return wertebefund(p, angabe.modell)
