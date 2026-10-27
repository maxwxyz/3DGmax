"""Nur grafisch vorhandene PMI auswerten (PLAN §8.18): Art und Werte aus Text oder Markup-Art ableiten.

Quellen: Texte der Grafik (QIF-Texte, Platzhalter mit eigenem Text) und die Art eines PRC-Markups (Mass, GD&T,
Bezug). Das Ergebnis ist nie echte Semantik: die PMI bekommen quelle="abgeleitet", semantisch=False und werden in
der Liste als "aus der Grafik abgeleitet - bitte pruefen" gekennzeichnet.
"""

from __future__ import annotations

import re

from .pmi import BEZUG, MASS, TOL_SYMBOL, TOLERANZ, BezugsRef

ABGELEITET = "abgeleitet"
SYMBOL_ZU_TYP: dict[str, str] = {}
for _typ, _sym in TOL_SYMBOL.items():
    SYMBOL_ZU_TYP.setdefault(_sym, _typ)
_ZAHL = re.compile(r"[-+±]?\s*\d*[.,]?\d+")
_BEZUG = re.compile(r"^[A-Z]{1,2}(-[A-Z]{1,2})?[ⓂⓁ]?$")
_RADIUS = re.compile(r"^(\d+X\s*)?(S?R|CR)\s*[.\d]")


def _zahl(text: str) -> float | None:
    m = _ZAHL.search(text)
    if m is None:
        return None
    t = m.group(0).replace(" ", "").replace(",", ".").replace("±", "")
    try:
        return float(t)
    except ValueError:
        return None


def aus_text(zeilen: list[str]) -> dict | None:
    """Felder einer PMI aus ihren Textzeilen (Toleranzrahmen, Bezug, Mass); None, wenn nichts erkennbar ist."""
    teile = [t.strip() for z in zeilen for t in z.split() if t.strip()]
    if not teile:
        return None
    for i, t in enumerate(teile):
        typ = SYMBOL_ZU_TYP.get(t[:1])
        if typ is None:
            continue
        rest = teile[i + 1:] if len(t) == 1 else [t[1:]] + teile[i + 1:]
        werte = [r for r in rest if _zahl(r) is not None]
        if not werte:
            return {"art": TOLERANZ, "typ": typ}
        w = werte[0]
        felder = {"art": TOLERANZ, "typ": typ, "wert": abs(_zahl(w)), "modifikatoren": [], "material": ""}
        if "⌀" in w or "Ø" in w:
            felder["modifikatoren"].append("Diameter")
        if "Ⓜ" in w:
            felder["material"] = "M"
        elif "Ⓛ" in w:
            felder["material"] = "L"
        bezuege = [r for r in rest[rest.index(w) + 1:] if _BEZUG.match(r)]
        felder["bezuege"] = [BezugsRef(b.rstrip("ⓂⓁ"), k, ["MaximumMaterialRequirement"] if b.endswith("Ⓜ") else
                                       ["LeastMaterialRequirement"] if b.endswith("Ⓛ") else [])
                             for k, b in enumerate(bezuege[:3], 1)]
        return felder
    if len(teile) == 1 and _BEZUG.match(teile[0].strip("[]")):
        return {"art": BEZUG, "typ": "Datum", "name": teile[0].strip("[]").rstrip("ⓂⓁ")}
    text = " ".join(teile)
    zahlen = [m.group(0) for m in _ZAHL.finditer(text)]
    if not zahlen:
        return None
    felder = {"art": MASS, "typ": "Location_LinearDistance", "nennwert": abs(_zahl(zahlen[0]))}
    if "S⌀" in text or "SØ" in text:
        felder["typ"] = "Size_SphericalDiameter"
    elif "⌀" in text or "Ø" in text:
        felder["typ"] = "Size_Diameter"
    elif _RADIUS.match(text):
        felder["typ"] = "Size_Radius"
    elif "°" in text:
        felder["typ"] = "Size_Angular"
    if "±" in text and len(zahlen) > 1:
        t = abs(_zahl(zahlen[1]))
        felder["oben"], felder["unten"] = t, -t
    elif len(zahlen) > 2 and zahlen[1].lstrip().startswith(("+", "-")):
        felder["oben"], felder["unten"] = _zahl(zahlen[1]), _zahl(zahlen[2])
    elif len(zahlen) == 2 and not zahlen[1].lstrip().startswith(("+", "-")):  # Grenzmass 35.20 / 34.80
        a, b = abs(_zahl(zahlen[0])), abs(_zahl(zahlen[1]))
        felder.update(oben=max(a, b), unten=min(a, b), grenzmass=True, nennwert=(a + b) / 2)
    return felder


# PRC-Markup-Arten (KEPRCMarkupType) und Unterarten der Masse (KEPRCMarkupSubType_Dimension_*)
_MASS_UNTERART = {7: "Size_Radius", 8: "Size_Radius", 9: "Size_Radius", 10: "Size_Radius", 11: "Size_Diameter",
                  12: "Size_Diameter", 13: "Size_Diameter", 14: "Size_Diameter", 15: "Size_Diameter",
                  19: "Size_Angular"}


def aus_markup(art: str, unterart: int, name: str) -> dict | None:
    """Art einer PMI aus der Markup-Art einer PRC-Datei (ohne Werte, wenn der Text nur aus Strichen besteht).

    CAD-Exporte ordnen nicht immer passend ein (NX: Bezugssymbole als GD&T); der Name des Markups geht vor."""
    m = re.match(r"\s*Datum (Feature )?Symbol\s+([A-Z]{1,2})\b", name)
    if m:
        return {"art": BEZUG, "typ": "Datum", "name": m.group(2)}
    if re.match(r"\s*(Radial )?Hole", name):
        return {"art": MASS, "typ": "Size_Diameter"}
    if re.match(r"\s*(Linear|Ordinate|Chain) Dimension", name):
        return {"art": MASS, "typ": "Location_LinearDistance"}
    if art == "Gdt":
        return {"art": TOLERANZ, "typ": ""}
    if art == "Dimension":
        typ = _MASS_UNTERART.get(unterart, "Location_LinearDistance")
        if "Radial" in name and typ == "Location_LinearDistance":
            typ = "Size_Radius"
        return {"art": MASS, "typ": typ}
    if art == "Datum":
        m = re.search(r"\b([A-Z]{1,2})\s*(\(\d+\))?\s*$", name)
        return {"art": BEZUG, "typ": "Datum", "name": m.group(1) if m else ""}
    return None


def ableiten(grafik) -> dict | None:
    """Felder fuer eine Grafik ohne Semantik: zuerst aus ihren Texten, sonst aus der Markup-Art."""
    texte = [ph.text for ph in grafik.platzhalter if ph.text]
    felder = aus_text(texte) if texte else None
    markup = getattr(grafik, "markup", None)
    if markup is not None:
        art = aus_markup(*markup, grafik.name)
        if felder is None or (art is not None and felder["art"] != art["art"] and not texte):
            felder = art
    return felder
