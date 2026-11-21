"""STEP-Validierungstext am grafischen Callout fuer die semantische Pruefung lesen."""

import re

from .p21 import Ref
from .pmi import BEZUG, MASS, TOLERANZ, TOL_SYMBOL
from .pmi_ableiten import aus_text, gueltige_rahmenwerte, gueltige_rahmenzellen


def _eltern(datei, nr, typ):
    return (e for i in datei.referrers().get(nr, ()) if (e := datei.get(i)).is_a(typ))


def _texte(datei, nr):
    """Nur Eigenschaften genau dieser Grafik innerhalb ihres Zeichenmodells."""
    from .ansichten import _items
    callout = Ref(nr)
    ebenen = {e.id for e in _eltern(datei, nr, "ANNOTATION_PLANE")
              if e.args("ANNOTATION_PLANE") and isinstance(e.args("ANNOTATION_PLANE")[-1], list)
              and callout in e.args("ANNOTATION_PLANE")[-1]}
    for zu in _eltern(datei, nr, "CHARACTERIZED_ITEM_WITHIN_REPRESENTATION"):
        args = zu.args("CHARACTERIZED_ITEM_WITHIN_REPRESENTATION")
        if len(args) != 4 or args[2] != callout or not isinstance(args[3], Ref):
            continue
        modell = datei.get(args[3])
        if modell is None or not modell.is_a("DRAUGHTING_MODEL"):
            continue
        if not any(isinstance(r, Ref) and (r.id == nr or r.id in ebenen) for r in _items(datei, modell)):
            continue
        for prop in _eltern(datei, zu.id, "PROPERTY_DEFINITION"):
            a = prop.args("PROPERTY_DEFINITION")
            if len(a) == 3 and a[0] == "pmi validation property" and a[2] == Ref(zu.id):
                yield from _eigenschaftstexte(datei, prop.id)


def _eigenschaftstexte(datei, nr):
    for link in _eltern(datei, nr, "PROPERTY_DEFINITION_REPRESENTATION"):
        args = link.args("PROPERTY_DEFINITION_REPRESENTATION")
        if len(args) != 2 or args[0] != Ref(nr) or not isinstance(args[1], Ref):
            continue
        rep = datei.get(args[1])
        if rep is None or not rep.is_a("REPRESENTATION"):
            continue
        a = rep.args("REPRESENTATION")
        if len(a) < 2 or not isinstance(a[1], list):
            continue
        for ref in a[1]:
            e = datei.get(ref) if isinstance(ref, Ref) else None
            if e is not None and e.is_a("DESCRIPTIVE_REPRESENTATION_ITEM"):
                daten = e.args("DESCRIPTIVE_REPRESENTATION_ITEM")
                if len(daten) == 2 and daten[0] == "equivalent unicode string" and isinstance(daten[1], str):
                    yield daten[1]


def _masszeile(text):
    teile = text.split(r"\u")
    if len(teile) == 3 and not teile[2]:
        paar = teile[1].split(r"\n")
        abmass = r"(?:[+−-](?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)|0(?:[.,]0+)?)"
        if len(paar) == 2 and all(re.fullmatch(abmass, wert) for wert in paar):
            return f"{teile[0]} {paar[0]}\n{paar[1]}"
    return text


def _rahmen(zellen, g, bekannt):
    from .pmi_strichschrift import lies_rahmensymbol
    if not gueltige_rahmenwerte(zellen[1:]):
        return None, ""
    quelle = ""
    if not zellen[0]:
        symbol = lies_rahmensymbol(g, len(zellen))
        if symbol:
            zellen[0], quelle = symbol, "grafik"
        elif bekannt and bekannt[0] == TOLERANZ and bekannt[1] in TOL_SYMBOL:
            zellen[0], quelle = TOL_SYMBOL[bekannt[1]], "name"
    if zellen[0] == "⊥":
        zellen[0] = "⟂"
    daten = aus_text(zellen, g.textfaktor) if gueltige_rahmenzellen(zellen) else None
    return daten, quelle


def _lesen(text, g, bekannt):
    art, *zellen = text.split(r"\w")
    if art not in ("DIM", "DTM", "FCF") or not zellen:
        return text, {}, ""
    druck = " | ".join(z or "…" for z in zellen)
    ergaenzung = ""
    if art == "FCF":
        daten, ergaenzung = _rahmen(zellen, g, bekannt)
    elif len(zellen) != 1:
        daten = None
    elif art == "DTM":
        daten = aus_text(zellen, g.textfaktor) if re.fullmatch("[A-Z]{1,2}", druck) else None
    else:
        druck = _masszeile(druck)
        daten = aus_text([druck], g.textfaktor)
    erwartet = {"DTM": BEZUG, "DIM": MASS, "FCF": TOLERANZ}[art]
    if not daten or daten["art"] != erwartet or (bekannt and bekannt[0] != erwartet):
        return druck, {}, ""
    if erwartet == TOLERANZ and "wert" not in daten:
        return druck, {}, ""
    typ = bekannt[1] if bekannt else ""
    if daten["typ"] == "Location_LinearDistance":
        if "Angular" in typ:
            return druck, {}, ""
        daten["typ"] = typ  # Eine nackte Masszahl legt Groesse oder Abstand nicht fest.
    elif typ and daten["typ"] != typ:
        return druck, {}, ""
    return druck, daten, ergaenzung


def _validierungswerte(datei, cid):
    return {w.replace(r"\\", "\\") for w in _texte(datei, cid)}


def validierungsvorschlag(datei, g, bekannt):
    """Zeilentexte zur Anzeige sowie Felder bei einer einzigen eindeutigen Quelle."""
    if datei is None:
        return (), {}, ""
    werte = sorted(_validierungswerte(datei, g.callout_id))
    if not any(w.startswith((r"DIM\w", r"FCF\w", r"DTM\w")) for w in werte):
        return (), {}, ""
    if len(werte) > 1:
        return tuple(werte), {}, ""
    druck, felder, ergaenzung = _lesen(werte[0], g, bekannt)
    return (druck,), felder, ergaenzung


def verbundtext_abgleich(datei, g, zeilen, daten, zusatz=""):
    """Werte beider Zeilen pruefen und einen eindeutig verkuerzten gemeinsamen Hinweis melden."""
    roh = _validierungswerte(datei, g.callout_id) if datei is not None else set()
    if not roh:
        return True, ""
    if len(roh) != 1:
        return False, ""
    quelle = roh.pop().split(r"\n")
    if len(quelle) != len(zeilen):
        return False, ""
    symbol = zeilen[0].split()[0]
    hinweise = set()
    for i, (text, soll) in enumerate(zip(quelle, daten)):
        inhalt, _, hinweis = text.partition(r"\xTXT\w")
        hinweise.add(hinweis)
        zellen = inhalt.split(r"\w")
        if i == 0:
            if zellen.pop(0) != "FCF" or not zellen or zellen.pop(0) not in ("", symbol):
                return False, ""
        zellen.insert(0, symbol)
        if not gueltige_rahmenzellen(zellen) or aus_text(zellen, g.textfaktor) != soll:
            return False, ""
    if hinweise == {zusatz}:
        return True, ""
    if len(hinweise) == 1:
        kurz = hinweise.pop()
        if kurz and zusatz.startswith(kurz + " "):
            return True, kurz
    return False, ""
