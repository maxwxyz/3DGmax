"""Axialteilung und Vorschub aus Beschriftungen fuer den Geometrieabgleich."""

import math
import re
from bisect import bisect_right
from dataclasses import dataclass


_FELD = re.compile(
    r"\b(?P<teilung>Axialteilung|axial[ -]pitch)|"
    r"\b(?P<hub>Vorschub (?:je|pro) (?:Umdrehung|Umlauf)|Ganghöhe|Ganghoehe|"
    r"(?:worm |screw )?lead(?: per (?:revolution|turn))?)", re.I)
_ANFANG = re.compile(r"\b[ \t]*[=:]?[ \t]*(?=[+−-]?(?:\d|[.,]\d))")
_WERT = re.compile(
    r"(?P<zahl>(?:\d+\s+)?\d+/\d+|\d+(?:[.,]\d+)?|[.,]\d+)"
    r'\s*(?P<einheit>mm|cm|µm|μm|inch(?:es)?|in\.?|Zoll|["″])?'
    r"(?:\s*(?:/\s*|per\s+|je\s+|pro\s+)(?P<umlauf>rev(?:olution)?|turn|U(?:mdrehung)?))?", re.I | re.ASCII)
_FAKTOR = {"mm": 1., "cm": 10., "μm": .001, "inch": 25.4, "inches": 25.4, "in": 25.4,
           "in.": 25.4, "zoll": 25.4, '"': 25.4, "″": 25.4}


@dataclass(frozen=True)
class Schraubenmass:
    text: str
    wert: float | None
    faktor: float | None
    eigenstaendig: bool

    def millimeter(self, kontext=None):
        faktor = self.faktor if self.faktor is not None else kontext
        return self.wert * faktor if self.wert is not None and faktor is not None else None


def _zahl(text):
    if "/" not in text:
        return float(text.replace(",", "."))
    zaehler, nenner = text.split("/")
    teile = zaehler.split()
    if float(nenner) == 0:
        return None
    ganz = float(teile[0]) if len(teile) == 2 else 0.
    return ganz + float(teile[-1]) / float(nenner)


def schraubenmasse(text, feldanfaenge):
    """Wert bis zum naechsten Tabellenfeld lesen, unbekannte Einheiten und Zusaetze bleiben offen."""
    felder = [(m, a.end()) for m in _FELD.finditer(text) if (a := _ANFANG.match(text, m.end()))]
    grenzen = sorted({*feldanfaenge, *(m.start() for m, _ in felder), len(text)})
    for m, start in felder:
        ende = grenzen[bisect_right(grenzen, start)]
        roh = re.split(r"[;|\r\n]|,(?=\s)", text[start:ende], maxsplit=1)[0].strip().rstrip(",")
        name = "axialteilung" if m["teilung"] else "vorschub"
        wert, faktor = None, None
        if (w := _WERT.fullmatch(roh)) and (not w["umlauf"] or name == "vorschub"):
            wert = _zahl(w["zahl"])
            if wert is not None and not math.isfinite(wert):
                wert = None
            if w["einheit"]:
                faktor = _FAKTOR[w["einheit"].casefold()]
        yield name, Schraubenmass(roh, wert, faktor, m[0].lower() != "lead")
