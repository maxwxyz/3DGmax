"""Gepruefte Zeilen eines gemeinsamen Zeichnungsrahmens mit zwei STEP-Toleranzen vergleichen."""

from dataclasses import dataclass

from .pmi import TOLERANZ
from .pmi_ableiten import SIMULTANHINWEIS
from .zeichnungsabgleich import lese_angabe, modellhinweis, unterschiede


def rahmenzeilen(text, faktor):
    zeilen = text.strip().splitlines()
    if len(zeilen) < 2 or any("|" not in z for z in zeilen[:2]) or any("|" in z for z in zeilen[2:]):
        return None
    oben, unten = (lese_angabe(z, faktor) for z in zeilen[:2])
    if not oben or not unten or oben.art != TOLERANZ or oben.typ != unten.typ:
        return None
    return oben, unten, " ".join(" ".join(zeilen[2:]).split())


class Verbundindex:
    def __init__(self, modelle):
        self.quellen = {}
        self.eltern = {}
        for m in modelle:
            if m.step_id <= 0:
                continue
            self.quellen[m.step_id] = None if m.step_id in self.quellen else m
            for n in m.folgetoleranzen:
                self.eltern.setdefault(n, set()).add(m.step_id)

    def verknuepfung(self, oben, unten):
        a, b = oben.step_id, unten.step_id
        if self.quellen.get(a) is not oben or self.quellen.get(b) is not unten or a == b:
            return "offen"
        if a in unten.folgetoleranzen and b not in oben.folgetoleranzen:
            return "umgekehrt"
        if b not in oben.folgetoleranzen:
            return "fehlt"
        if (set(oben.folgetoleranzen) != {b} or unten.folgetoleranzen or self.eltern.get(a)
                or self.eltern.get(b) != {a}):
            return "weitere"
        return "gleich"


@dataclass(frozen=True)
class Rahmenbefund:
    felder: tuple
    verknuepfung: str
    flaechen: str
    wortlaut: str
    gruppe_offen: bool
    status: str


def pruefe_rahmen(angabe, faktor, index):
    paar = rahmenzeilen(angabe.text, faktor)
    oben, unten = angabe.modell, angabe.unten
    if (paar is None or angabe.grundmass or angabe.zielkonflikt or oben is None or unten is None
            or oben is unten or oben.art != TOLERANZ or unten.art != TOLERANZ):
        return None
    zeile1, zeile2, zusatz = paar
    felder = tuple(tuple(k for k in unterschiede(p, m) if k != "beschreibung")
                   for p,m in ((zeile1, oben), (zeile2, unten)))
    bindung = index.verknuepfung(oben, unten)
    flaechen = ("offen" if not oben.flaechen or not unten.flaechen else
                "gleich" if oben.flaechen == unten.flaechen else "geaendert")
    wortlaut = "gleich" if all(modellhinweis(m) == zusatz for m in (oben, unten)) else "geaendert"
    gruppe = (any(SIMULTANHINWEIS.fullmatch(z.strip()) for z in angabe.text.splitlines()[2:])
              or any(m.simultan_mit or m.simultan_offen or SIMULTANHINWEIS.fullmatch(modellhinweis(m))
                     for m in (oben, unten)))
    status = "gleich"
    if any(felder) or bindung in ("fehlt", "umgekehrt", "weitere") or flaechen == "geaendert" or wortlaut == "geaendert":
        status = "geaendert"
    elif gruppe or "offen" in (bindung, flaechen) or any(p.zone == "Projected" for p in (zeile1, zeile2)):
        status = "offen"
    return Rahmenbefund(felder, bindung, flaechen, wortlaut, bool(gruppe), status)
