"""Nur grafisch vorhandene PMI auswerten (PLAN §8.18): Art und Werte aus Text oder Markup-Art ableiten.

Quellen: Texte der Grafik (QIF-Texte, Platzhalter mit eigenem Text) und die Art eines PRC-Markups (Mass, GD&T,
Bezug). Das Ergebnis ist nie echte Semantik: die PMI bekommen quelle="abgeleitet", semantisch=False und werden in
der Liste als "aus der Grafik abgeleitet - bitte pruefen" gekennzeichnet.
"""

from __future__ import annotations

import math
import re

from .pmi import BEZUG, MASS, TOL_SYMBOL, TOLERANZ, BezugsRef

ABGELEITET = "abgeleitet"
SYMBOL_ZU_TYP: dict[str, str] = {}
for _typ, _sym in TOL_SYMBOL.items():
    SYMBOL_ZU_TYP.setdefault(_sym, _typ)
_ZAHL = r"(?:\d+(?:[.,]\d+)?|[.,]\d+)"
_MATERIAL = {"Ⓜ": "MaximumMaterialRequirement", "Ⓛ": "LeastMaterialRequirement"}
_GLIED = r"[A-Z]{1,2}[ⓂⓁ]?"
_RAHMENWERT = re.compile(rf"(?P<zone>S?⌀)?\s*(?P<wert>{_ZAHL})(?P<mods>(?:\s*[ⓂⓁⓉⒻ])*)"
                        rf"(?:\s+MAX\s+(?P<maximum>{_ZAHL}))?"
                        rf"(?:\s*Ⓟ\s*(?P<hoehe>{_ZAHL}))?")
_EINHEIT = re.compile(r'(?<=[\d])\s*(mm|inch|in|"|°)(?![A-Za-z])', re.I)
_FAKTOREN = {"mm": 1., "inch": 25.4, "in": 25.4, '"': 25.4, "°": 1.}


def _zahl(text):
    return float(text.replace(",", ".").replace(" ", ""))


def bezugsreferenz(text, stelle):
    """Ein Fach mit getrennten Materialmodifikatoren am einzelnen Mitglied oder an der ganzen Gruppe."""
    if re.fullmatch(rf"\({_GLIED}(?:-{_GLIED})+\)[ⓂⓁ]", text):
        gruppe, mods = text[1:-2], [_MATERIAL[text[-1]]]
    else:
        gruppe, mods = text, []
    if not re.fullmatch(rf"{_GLIED}(?:-{_GLIED})*", gruppe):
        return None
    namen, elemente = [], {}
    for element in gruppe.split("-"):
        name = element.rstrip("ⓂⓁ")
        if name in namen:
            return None
        namen.append(name)
        if element != name:
            elemente[name] = [_MATERIAL[element[-1]]]
    if len(namen) == 1:
        mods = elemente.pop(namen[0], [])
    return BezugsRef("-".join(namen), stelle, mods, elemente)


def gueltige_rahmenwerte(werte):
    """Genau ein Wertfach mit bis zu drei getrennten Bezugsfaechern."""
    return (1 <= len(werte) <= 4 and _RAHMENWERT.fullmatch(werte[0]) is not None
            and all(bezugsreferenz(t, i) is not None for i, t in enumerate(werte[1:], 1)))


def gueltige_rahmenzellen(teile):
    """Vollstaendiger Rahmen mit geometrischem Merkmal im ersten Fach."""
    return bool(teile) and teile[0] in SYMBOL_ZU_TYP and gueltige_rahmenwerte(teile[1:])


def _toleranz(text, typ, faktor):
    art = {"art": TOLERANZ, "typ": typ}
    # Ein zusammengesetzter Rahmen braucht mehrere Toleranzen; keine Einzelzeile als Gesamtergebnis ausgeben.
    m = _RAHMENWERT.match(text)
    if m is None or faktor is None or text[m.end():].lstrip().startswith(("/", "°")):
        return art
    namen = re.findall(r"\S+", re.sub(r"\s*([ⓂⓁ])", r"\1", text[m.end():]))
    if len(namen) > 3:
        return art
    refs = [bezugsreferenz(n, k) for k, n in enumerate(namen, 1)]
    mods = "".join(m["mods"].split())
    if any(b is None for b in refs) or len(set(mods)) != len(mods) or ("Ⓜ" in mods and "Ⓛ" in mods):
        return art
    modifikatoren = {"⌀": ["Diameter"], "S⌀": ["SphericalDiameter"]}.get(m["zone"], [])
    modifikatoren.extend({"Ⓣ": "Tangent_Plane", "Ⓕ": "Free_State"}[m] for m in mods if m in "ⓉⒻ")
    felder = dict(art, wert=faktor * _zahl(m["wert"]), bezuege=refs, modifikatoren=modifikatoren,
                  material="M" if "Ⓜ" in mods else "L" if "Ⓛ" in mods else "")
    if m["hoehe"]:
        felder.update(zone="Projected", zonen_wert=faktor * _zahl(m["hoehe"]))
    if m["maximum"]:
        if not felder["material"] or _zahl(m["maximum"]) <= _zahl(m["wert"]):
            return art
        felder["maximum_toleranz"] = faktor * _zahl(m["maximum"])
    return felder


def _mass(text, faktor, winkel, gestapelt):
    hilfsmass = text.startswith("(") and text.endswith(")")
    if hilfsmass:
        text = text[1:-1].strip()
    modifikatoren = ["Hilfsmass"] if hilfsmass else []
    for ende, mod in (("⟨ST⟩", "StatisticalTolerance"), ("Ⓔ", "Envelope"),
                      ("controlled radius", "ControlledRadius")):
        if text.lower().endswith(ende.lower()):
            modifikatoren.append(mod)
            text = text[:-len(ende)].strip()
    text = re.sub(r"^[1-9]\d*\s*[xX×]\s*(?=(?:S?[⌀R]|CR))", "", text)
    m = re.match(rf"^(S⌀|⌀|SR|R|CR)?\s*([+-]?{_ZAHL})", text)
    if not m or faktor is None:
        return None
    # Ziffern in Artikelnummern, Notizen, Gewindebezeichnungen oder weiteren Massen nicht als Mass uebernehmen.
    art = {"⌀": "Size_Diameter", "S⌀": "Size_SphericalDiameter", "R": "Size_Radius",
           "SR": "Size_SphericalRadius", "CR": "Size_Radius"}.get(m[1], "Size_Angular" if winkel else "Location_LinearDistance")
    nenn = _zahl(m[2]) * faktor
    if nenn < 0 and art.startswith("Size_"):
        return None
    rest = text[m.end():].strip()
    felder = {"art": MASS, "typ": art, "nennwert": nenn}
    if m[1] == "CR" and "ControlledRadius" not in modifikatoren:
        modifikatoren.append("ControlledRadius")
    if modifikatoren:
        felder["modifikatoren"] = modifikatoren
    if not rest:
        return felder
    if (v := re.fullmatch(rf"±\s*({_ZAHL})", rest)):
        t = faktor * _zahl(v[1])
        return dict(felder, oben=t, unten=-t)
    if (v := re.fullmatch(rf"([+-]\s*{_ZAHL}|0(?:[.,]0+)?)\s*[/\s]\s*([+-]\s*{_ZAHL}|0(?:[.,]0+)?)", rest)):
        o, u = (faktor * _zahl(w) for w in v.groups())
        if o >= u:
            return dict(felder, oben=o, unten=u)
        return None
    if (gestapelt or rest.startswith(("/", "–"))) and (v := re.fullmatch(rf"[/–]?\s*({_ZAHL})", rest)):
        grenze = faktor * _zahl(v[1])
        return dict(felder, oben=max(nenn, grenze), unten=min(nenn, grenze), grenzmass=True, nennwert=(nenn + grenze) / 2)
    if re.fullmatch(r"(?:[A-HJKM-NPRSTUVXYZ]|JS|Z[ABC]|[a-hjkm-nprstuvxyz]|js|z[abc])(?:0[01]|[1-9]|1[0-8])", rest):
        return dict(felder, passung=rest)
    return None


def aus_text(zeilen: list[str], faktor: float = 1.) -> dict | None:
    """Eindeutige Angaben in mm bzw. Grad; die explizite Texteinheit geht der Datei-PMI-Einheit vor."""
    roh = "\n".join(zeilen).translate(str.maketrans({"Ø": "⌀", "∅": "⌀", "−": "-", "|": " "}))
    text = " ".join(roh.split())
    if not text:
        return None
    einheiten = {m.lower() for m in _EINHEIT.findall(text)}
    faktoren = {_FAKTOREN[e] for e in einheiten}
    if len(faktoren) > 1 or ("°" in einheiten and len(einheiten) > 1):
        return None
    if faktoren:
        faktor = faktoren.pop()
        text = _EINHEIT.sub("", text).strip()
    if any(not math.isfinite(_zahl(n)) for n in re.findall(_ZAHL, text)):
        return None
    typ = SYMBOL_ZU_TYP.get(text[0])
    if typ:
        return _toleranz(text[1:].strip(), typ, None if "°" in einheiten else faktor)
    buchstabe = re.fullmatch(r"(?:\[([A-Z]{1,2})\]|([A-Z]{1,2}))", text)
    if buchstabe:
        return {"art": BEZUG, "typ": "Datum", "name": buchstabe[1] or buchstabe[2]}
    gestapelt = bool(re.search(r"\d[ \t]*\n\s*(?:\d|[.,]\d)", _EINHEIT.sub("", roh)))
    return _mass(text, faktor, "°" in einheiten, gestapelt)


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
        if "radial" in name.lower() and typ == "Location_LinearDistance":
            typ = ""
        return {"art": MASS, "typ": typ}
    if art == "Datum":
        m = re.search(r"\b([A-Z]{1,2})\s*(\(\d+\))?\s*$", name)
        return {"art": BEZUG, "typ": "Datum", "name": m.group(1) if m else ""}
    return None


def ableiten(grafik) -> dict | None:
    """Felder fuer eine Grafik ohne Semantik: zuerst aus ihren Texten, sonst aus der Markup-Art."""
    texte = [ph.text for ph in grafik.platzhalter if ph.text]
    faktor = getattr(grafik, "textfaktor", 1.)
    felder = aus_text(texte, faktor) if texte else None
    markup = getattr(grafik, "markup", None)
    art = aus_markup(*markup, grafik.name) if markup is not None else None
    if texte and (not art or re.fullmatch(r".+\.\d+", grafik.name or "")):
        from .pmi_reparieren import aus_name
        kennung = aus_name(grafik.name)
        if kennung:
            art = {"art": kennung[0], "typ": kennung[1]}
    if art is None:
        return felder
    # Bei CAD-Text plus gezeichnetem Rahmensymbol stammt der Merkmalstyp oft allein aus dem Callout-Namen.
    symbol = TOL_SYMBOL.get(art.get("typ"))
    if symbol and texte and (felder is None or felder["art"] == MASS):
        return aus_text([symbol, *texte], faktor)
    if felder is None or felder["art"] != art["art"]:
        return art
    if art["art"] == MASS and felder["typ"] == "Location_LinearDistance":
        if art["typ"] in ("Size_Angular", "Location_Angular"):
            return art  # Winkel ohne lesbare Einheit nicht als Laenge umrechnen.
        felder["typ"] = art["typ"]
    return felder
