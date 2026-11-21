"""Gepruefte Zeilen eines gemeinsamen Zeichnungsrahmens mit zwei STEP-Toleranzen vergleichen."""

from collections import Counter
from dataclasses import dataclass
from functools import cached_property

from .koplanare_ziele import Koplanarbefund, pruefe_koplanar, zielanzahl
from .merkmalstext import toleranzziel, texte_am_aspekt
from .pmi import TOLERANZ
from .pmi_ableiten import SIMULTANHINWEIS, simultantext
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
    def __init__(self, modelle, geometrie=None):
        self.geometrie = geometrie
        self.koplanare_ziele = {}
        self.auflagen = {}
        self.texte_je_aspekt = {}
        self.quellen = {}
        self.eltern = {}
        for m in modelle:
            if m.step_id <= 0:
                continue
            self.quellen[m.step_id] = None if m.step_id in self.quellen else m
            for n in m.folgetoleranzen:
                self.eltern.setdefault(n, set()).add(m.step_id)

    @cached_property
    def mehrfach_verbaut(self):
        # Erst bei einer geometrischen Pruefung alle Vorkommen mit ihrer Lage aufloesen.
        from .vergleich_geo import _instanzen
        if self.geometrie is None:
            return set()
        _, basis = _instanzen(self.geometrie)
        return {i for i,n in Counter(basis).items() if n > 1} if basis is not None else set()

    def koplanar(self, text, oben, unten):
        soll = zielanzahl(text)
        if soll is None:
            return None
        if oben.flaechen != unten.flaechen:
            return Koplanarbefund(soll, None, "geometrie")
        return self.flaechenanzahl(soll, oben.flaechen)

    def flaechenanzahl(self, soll, flaechen):
        if self.mehrfach_verbaut & flaechen:
            return Koplanarbefund(soll, None, "vorkommen")
        schluessel = (soll, frozenset(flaechen))
        if schluessel not in self.koplanare_ziele:
            self.koplanare_ziele[schluessel] = pruefe_koplanar(soll, flaechen, self.geometrie)
        return self.koplanare_ziele[schluessel]

    def auflagenanzahl(self, soll, flaechen):
        from .pmi_dickenschrift import auflagenlage
        if self.geometrie is None or self.mehrfach_verbaut & flaechen:
            return Koplanarbefund(soll, None, "vorkommen" if self.geometrie else "geometrie")
        ids = frozenset(flaechen)
        if ids not in self.auflagen:
            self.auflagen[ids] = auflagenlage(self.geometrie, ids)
        lage = self.auflagen[ids]
        if lage is None:
            return Koplanarbefund(soll, None, "geometrie")
        anzahl = lage[3]
        return Koplanarbefund(soll, anzahl, "getrennt" if soll == anzahl else "anzahl")

    def merkmalstexte(self, oben, unten):
        datei = getattr(self.geometrie, "datei", None)
        if datei is None or any(self.quellen.get(p.step_id) is not p for p in (oben, unten)):
            return ()
        aspekt = toleranzziel(datei, oben.step_id)
        if aspekt is None or aspekt != toleranzziel(datei, unten.step_id):
            return ()
        if aspekt not in self.texte_je_aspekt:
            self.texte_je_aspekt[aspekt] = tuple(texte_am_aspekt(datei, aspekt))
        return self.texte_je_aspekt[aspekt]

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
    koplanar: Koplanarbefund | None
    merkmalstexte: tuple
    gruppe_offen: bool
    zusatz_offen: bool
    status: str


def pruefe_rahmen(angabe, faktor, index, gruppen=None):
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
    gedruckt = any(simultantext(z) for z in angabe.text.splitlines()[2:])
    gruppenstatus = []
    for m, befund in zip((oben, unten), gruppen or (None, None), strict=True):
        benoetigt = gedruckt or m.simultan_mit or m.simultan_offen or simultantext(modellhinweis(m))
        gruppenstatus.append(befund.status if befund else "offen" if benoetigt else "")
    koplanar = index.koplanar(angabe.text, oben, unten)
    weitere_zeilen = [z.strip() for z in angabe.text.splitlines()[2:] if z.strip() and not SIMULTANHINWEIS.fullmatch(z.strip())]
    zusatz_offen = len(weitere_zeilen) > int(koplanar is not None)
    geometrie = koplanar.status if koplanar else ""
    status = "gleich"
    if any(felder) or bindung in ("fehlt", "umgekehrt", "weitere") or "geaendert" in (flaechen, wortlaut, geometrie, *gruppenstatus):
        status = "geaendert"
    elif zusatz_offen or "offen" in (bindung, flaechen, geometrie, *gruppenstatus) or any(p.zone == "Projected" for p in (zeile1, zeile2)):
        status = "offen"
    texte = tuple((t, t.vergleich(angabe.text.splitlines()[2:])) for t in index.merkmalstexte(oben, unten))
    return Rahmenbefund(felder, bindung, flaechen, wortlaut, koplanar, texte, "offen" in gruppenstatus, zusatz_offen, status)
