"""Gepruefte Zeichnungsangaben mit den semantischen Modell-PMI vergleichen."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import math
import re

from . import pmi_ableiten
from .pmi_ableiten import SIMULTANHINWEIS, simultantext
from .pmi import BEZUG, MASS, TOLERANZ, Pmi
from .vergleich_pmi import simultangruppen


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
    hinweisenden: tuple = ()  # Freie Strichenden der automatisch gefundenen Angabe in Blattkoordinaten
    zeilenecken: tuple = ()  # Vier Ecken einer geneigten Zeile in Leserichtung

    rahmenbox: tuple | None = None  # Urspruengliche Rahmenkante fuer die Hinweislinie bei Text darunter
    simultan: Blattgruppe | None = None

    verbundrahmen: bool = False
    unten: Pmi | None = None

    @property
    def gruppenzeilen(self):
        return self._verbundzeilen if self.verbundrahmen else (self,)

    @cached_property
    def _verbundzeilen(self):
        return Rahmenzeile(self, 0), Rahmenzeile(self, 1)

    def setze_text(self, text):
        if text == self.text:
            return
        alt, neu = self.text.splitlines(), text.splitlines()
        if self.verbundrahmen and min(len(alt), len(neu)) >= 2 and alt[2:] == neu[2:]:
            loese_blattgruppen(z for z in self.gruppenzeilen if alt[z.rang] != neu[z.rang])
        else:
            loese_blattgruppen(self.gruppenzeilen)
        self.text = text

    def zugeordnete_pmi(self):
        if self.verbundrahmen:
            return [p for p in (self.modell, self.unten) if p is not None]
        if self.einzelpruefung:
            return [z.modell for z in self.musterziele if z.modell is not None]
        return [self.modell] if self.modell is not None else []


@dataclass(eq=False)
class Rahmenzeile:
    rahmen: Blattangabe
    rang: int
    simultan: Blattgruppe | None = None

    @property
    def modell(self):
        return self.rahmen.unten if self.rang else self.rahmen.modell

    @property
    def text(self):
        zeilen = self.rahmen.text.strip().splitlines()
        if len(zeilen) < 2:
            return ""
        zusatz = (simultantext(z) or z.strip() for z in zeilen[2:])
        hinweise = [z for z in zusatz if z.startswith("SIM")]
        return "\n".join([zeilen[self.rang], *hinweise])


def fundort(zeile):
    return zeile.rahmen if isinstance(zeile, Rahmenzeile) else zeile


def gruppenschluessel(zeile):
    nummer = gruppenkennung(zeile.text)
    return (zeile.rang if isinstance(zeile, Rahmenzeile) else None, nummer) if nummer else None


def gruppenangabe(zeile, faktor):
    if isinstance(zeile, Rahmenzeile):
        from .blattverbund import rahmenzeilen
        if zeile.rahmen.grundmass or not rahmenzeilen(zeile.rahmen.text, faktor):
            return None
    return lese_angabe(zeile.text, faktor, fundort(zeile).grundmass)


@dataclass(frozen=True)
class Blattgruppe:
    zeilen: frozenset[Blattangabe | Rahmenzeile]
    alle_blaetter: bool


@dataclass(frozen=True)
class Gruppenbefund:
    status: str
    blatt_ids: frozenset[int]
    modell_ids: frozenset[int]
    grund: str = ""


def gruppenkennung(text):
    """Nur eine vollstaendige nummerierte Angabe am Toleranzrahmen identifiziert Partner."""
    _, _, zusatz = text.strip().partition("\n")
    m = SIMULTANHINWEIS.fullmatch(" ".join(zusatz.split()))
    return (m[1] or "") if m else ""


def loese_blattgruppen(zeilen):
    for alt in {a.simultan for a in zeilen if a.simultan}:
        for a in alt.zeilen:
            a.simultan = None


def setze_blattgruppe(zeilen, alle_blaetter):
    gruppe = Blattgruppe(frozenset(zeilen), alle_blaetter)
    loese_blattgruppen(gruppe.zeilen)
    for a in gruppe.zeilen:
        a.simultan = gruppe


def _pruefgrund(gruppe, ids, nummeriert, faktor, nach_id):
    if not gruppe.alle_blaetter:
        return "blaetter"
    zeilen = gruppe.zeilen
    kennungen = {k for a in zeilen if (k := gruppenschluessel(a))}
    if len({nummer for _, nummer in kennungen}) > 1 or any(not z.simultan or not z.simultan.alle_blaetter
                                 for k in kennungen for z in nummeriert.get(k, set()) - zeilen):
        return "kennung"
    for a in zeilen:
        p = gruppenangabe(a, faktor)
        ort = fundort(a)
        doppelte_rolle = ort.verbundrahmen and ort.modell is not None and ort.modell is ort.unten
        if not p or p.art != TOLERANZ or ort.zielkonflikt or doppelte_rolle:
            return "zuordnung"
        if a.modell is None and not ort.nur_zeichnung:
            return "zuordnung"
        if a.modell and (a.modell.step_id <= 0 or nach_id.get(a.modell.step_id) is not a.modell
                         or a.modell.art != TOLERANZ or a.modell.typ != p.typ):
            return "zuordnung"
        if len(zeilen) == 1 and SIMULTANHINWEIS.fullmatch(p.beschreibung):
            return "partner"
    return "doppelt" if len(ids) != sum(a.modell is not None for a in zeilen) else ""


def gruppenbefunde(angaben, modelle, faktor):
    """Gepruefte Blattzeilen mit den zusammenhaengenden STEP-Gruppen vergleichen."""
    angaben = [z for a in angaben for z in a.gruppenzeilen]
    gruppen = {a.simultan for a in angaben if a.simultan}
    if not gruppen:
        return {}
    erwartet = simultangruppen(modelle)
    nach_id = {}
    for p in modelle:
        nach_id[p.step_id] = None if p.step_id in nach_id else p
    unklar = set()
    for p in modelle:
        offen = [n for n in p.simultan_mit if nach_id.get(n) is None or p.step_id not in nach_id[n].simultan_mit]
        if offen or p.simultan_offen:
            unklar.update((p.step_id, *offen, *p.simultan_offen))
    nummeriert = {}
    for a in angaben:
        if kennung := gruppenschluessel(a):
            nummeriert.setdefault(kennung, set()).add(a)
    ergebnis = {}
    for gruppe in gruppen:
        zeilen = gruppe.zeilen
        ids = frozenset(a.modell.step_id for a in zeilen if a.modell and a.modell.step_id > 0)
        blattgrund = _pruefgrund(gruppe, ids, nummeriert, faktor, nach_id)
        for a in zeilen:
            m = a.modell
            soll = erwartet.get(m.step_id, frozenset({m.step_id})) if m and m.step_id > 0 else frozenset()
            grund = blattgrund
            if not grund and (ids & unklar or soll & unklar):
                grund = "bezug"
            if not grund and m and m.step_id not in erwartet and simultantext(modellhinweis(m)):
                grund = "modellpartner"
            status = "offen" if grund or not m else "gleich" if soll == ids and len(ids) == len(zeilen) else "geaendert"
            ergebnis[a] = Gruppenbefund(status, ids, soll, grund)
    return ergebnis


_MENGE = re.compile(r"^\s*([1-9][0-9]{0,3})\s*[xX×]\s*(?=(?:[Ø∅⌀]|C?R)\s*[0-9.,])")


def musteranzahl(text):
    m = _MENGE.match(text)
    return int(m[1]) if m else 0


def muster_deckt(anzahl, ziele, modell, typ="Size_Diameter"):
    if (not ziele or len(ziele) != anzahl or modell is None
            or modell.typ != typ or typ not in ("Size_Diameter", "Size_Radius")):
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
    # Bei zwei aufsteigenden Groessengrenzen kann der Plotter einen Bindestrich ausgeben.
    zahl = r"(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)"
    grenzen = re.fullmatch(rf'((?:[⌀Ø∅]|C?R)\s*)({zahl})\s*-\s*({zahl})(\s*(?:mm|in|inch|")?)\s*', text, re.I)
    if grenzen and float(grenzen[2].replace(",", ".")) < float(grenzen[3].replace(",", ".")):
        text = f"{grenzen[1]}{grenzen[2]}–{grenzen[3]}{grenzen[4]}"
    zusatz = ""
    if "|" in text:
        kopf, _, folge = text.strip().partition("\n")
        zusatz = pmi_ableiten.geltungshinweis(folge)
        if zusatz:
            text = kopf
        teile = [t.strip().translate(str.maketrans({"Ø": "⌀", "∅": "⌀"})) for t in text.split("|")]
        if len(teile) >= 2:
            teile[1] = pmi_ableiten._EINHEIT.sub("", teile[1]).strip()
        if not pmi_ableiten.gueltige_rahmenzellen(teile):
            return None
    daten = pmi_ableiten.aus_text([text], faktor or 1.)
    if not daten:
        return None
    p = Pmi(**daten, beschreibung=zusatz)
    if p.art == BEZUG:
        return p if re.fullmatch(r"\s*\[[A-Z]{1,2}\]\s*", text) else None
    if p.wert is None and p.nennwert is None:
        return None
    if faktor is None and not re.search(r'(?<=\d)\s*(?:mm|inch|in\b|"|°)', text, re.I):
        return None
    if grundmass and p.art == MASS:
        p.modifikatoren.append("Theoretisch")
    return p


def modellhinweis(p):
    """Sichtbarer Wortlaut ohne den generischen STEP-Exporttext in NIST D2MI-904."""
    text = " ".join(p.beschreibung.split())
    return "" if text.casefold() == "geometric tolerance for feature" else text


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
    return {"typ": p.typ, "beschreibung": modellhinweis(p), "wert": p.wert, "zone": zone, "zonen_wert": p.zonen_wert,
            "material": p.material, "maximum_toleranz": p.maximum_toleranz,
            "einheitslaenge": p.einheitslaenge, "einheitsbreite": p.einheitsbreite,
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


def wertunterschiede(p, modell, gruppe=None):
    felder = unterschiede(p, modell)
    gedruckt = SIMULTANHINWEIS.fullmatch(p.beschreibung)
    pruefen = gruppe or modell.simultan_mit or modell.simultan_offen or (gedruckt and gedruckt[1])
    if (pruefen and "beschreibung" in felder and (not p.beschreibung or gedruckt)
            and (not modellhinweis(modell) or SIMULTANHINWEIS.fullmatch(modellhinweis(modell)))):
        felder.remove("beschreibung")  # Der Gruppenbefund prueft diese Anforderung.
    return felder


def gruppe_zu_pruefen(p, modell):
    return bool(modell.simultan_mit or modell.simultan_offen or simultantext(p.beschreibung) or simultantext(modellhinweis(modell)))


def wertebefund(p, modell, gruppe=None):
    if p is None or modell is None or grenzen_vertauscht(modell):
        return "offen"
    if gruppe and gruppe.status == "geaendert":
        return "geaendert"
    felder = wertunterschiede(p, modell, gruppe)
    if felder == ["beschreibung"] and (hinweis := modellhinweis(modell)) and not pmi_ableiten.geltungshinweis(hinweis):
        return "offen"
    if felder:
        return "geaendert"
    if (gruppe and gruppe.status == "offen") or (not gruppe and gruppe_zu_pruefen(p, modell)):
        return "offen"  # Die einzelne Blattzeile belegt keine Verknuepfung zu einer anderen Toleranz.
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


def befund(angabe, faktor, gruppe=None, verbundindex=None):
    if angabe.verbundrahmen:
        from .blattverbund import pruefe_rahmen, rahmenzeilen
        if angabe.nur_zeichnung and not angabe.zielkonflikt and not angabe.grundmass and rahmenzeilen(angabe.text, faktor):
            return "zeichnung"
        ergebnis = pruefe_rahmen(angabe, faktor, verbundindex, gruppe) if verbundindex is not None else None
        return ergebnis.status if ergebnis else "offen"
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
    if anzahl and not muster_deckt(anzahl, angabe.musterziele, angabe.modell, p.typ):
        return "offen"
    return wertebefund(p, angabe.modell, gruppe)
