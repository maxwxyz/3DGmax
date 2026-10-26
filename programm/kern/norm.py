"""Normsystem eines Modells: ISO GPS oder ASME Y14.5 (erkannt aus Hinweisen, Modifikatoren, Dateiname).

Die Semantik in STEP AP242 ist fuer beide gleich; die Datei nennt die Norm selten ausdruecklich. Gewichtung:
ausdrueckliche Nennung in Text (stark) > normtypische Modifikatoren (mittel) > Dateiname (schwach).
Ohne Hinweis gilt ISO GPS.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

ISO, ASME = "iso", "asme"
NAME = {ISO: "ISO GPS", ASME: "ASME Y14.5"}

# (Muster, Norm, Gewicht)
_TEXT = [
    (r"ASME\s*Y\s*14\.5M?(?:[-:\s]\d{4})?", ASME, 10), (r"ANSI\s*Y\s*14\.5", ASME, 10), (r"ASME\s*Y\s*14\.41", ASME, 2),
    (r"ISO\s*8015", ISO, 10), (r"ISO\s*1101", ISO, 10), (r"ISO\s*GPS", ISO, 10), (r"ISO\s*14405", ISO, 10),
    (r"ISO\s*2768(?:-\w{1,2})?", ISO, 8), (r"ISO\s*22081", ISO, 8), (r"ISO\s*5459", ISO, 8), (r"ISO\s*16792", ISO, 2),
]
# Groessenmodifikatoren nach ISO 14405 (gibt es so nur in ISO GPS) und ASME-typische
_ISO_MODS = {"TwoPointSize", "LocalSizeDefinedBySphere", "LeastSquaresAssociationCriterion",
             "MaximumInscribedAssociation", "MinimumCircumscribedAssociation", "CircumferenceDiameter",
             "AreaDiameter", "VolumeDiameter", "RangeOfSizes", "MaximumSize", "MinimumSize", "AverageSize",
             "MedianSize", "MidRangeSize", "AnyCrossSection", "SpecificFixedCrossSection", "CommonTolerance"}
_ASME_MODS = {"ControlledRadius", "ContinuousFeature"}


@dataclass
class Norm:
    art: str  # iso | asme
    grund: str  # Fundstelle fuer die Anzeige ("" = Standard ohne Hinweis)
    erkannt: bool  # False = Rueckfall ISO GPS

    @property
    def name(self) -> str:
        return NAME[self.art]


def _dateitext(pfad: str, grenze: int = 60_000_000) -> str:
    try:
        if os.path.getsize(pfad) > grenze:
            with open(pfad, encoding="latin-1") as f:
                return f.read(grenze)
        with open(pfad, encoding="latin-1") as f:
            return f.read()
    except OSError:
        return ""


def erkenne(pfad: str, pmi: list | None = None, text: str | None = None) -> Norm:
    """Norm aus Texten der Datei, Modifikatoren der PMI und dem Dateinamen; Rueckfall ISO GPS."""
    text = _dateitext(pfad) if text is None else text
    punkte = {ISO: 0, ASME: 0}
    gruende = {ISO: "", ASME: ""}
    # Empfohlene Praxis AP242: DOCUMENT('<Norm>','Geometric Tolerancing Standard', ...) nennt die Norm ausdruecklich
    for treffer in re.finditer(r"DOCUMENT\s*\(\s*'([^']*)'\s*,\s*'Geometric Tolerancing Standard'", text, re.I):
        name = treffer.group(1)
        art = ASME if re.search(r"ASME|ANSI", name, re.I) else (ISO if re.search(r"ISO|DIN", name, re.I) else None)
        if art:
            punkte[art] += 20
            gruende[art] = gruende[art] or f"{name} (Geometric Tolerancing Standard)"
    for muster, art, gewicht in _TEXT:
        treffer = re.search(muster, text, re.I)
        if treffer:
            punkte[art] += gewicht
            gruende[art] = gruende[art] or treffer.group(0).strip()
    mods = {m for p in (pmi or []) for m in p.modifikatoren}
    if mods & _ISO_MODS:
        punkte[ISO] += 5
        gruende[ISO] = gruende[ISO] or sorted(mods & _ISO_MODS)[0]
    if mods & _ASME_MODS:
        punkte[ASME] += 3
        gruende[ASME] = gruende[ASME] or sorted(mods & _ASME_MODS)[0]
    name = os.path.basename(pfad).lower()
    if re.search(r"(^|[_\-.])asme", name):
        punkte[ASME] += 1
        gruende[ASME] = gruende[ASME] or os.path.basename(pfad)
    elif re.search(r"(^|[_\-.])iso([_\-.]|$)", name):
        punkte[ISO] += 1
        gruende[ISO] = gruende[ISO] or os.path.basename(pfad)
    if punkte[ASME] > punkte[ISO]:
        return Norm(ASME, gruende[ASME], True)
    if punkte[ISO] > 0:
        return Norm(ISO, gruende[ISO], True)
    return Norm(ISO, "", False)


def setze(pmi: list, art: str):
    """Norm an alle PMI eines Modells weitergeben (Begriffe, Regeln)."""
    for p in pmi:
        p.norm = art
