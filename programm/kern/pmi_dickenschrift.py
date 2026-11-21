"""Wiederholtes Dickenmass zwischen einer Ebene und mehreren getrennten Auflagen lesen."""

import re

import numpy as np

from .baugruppe_mass import ebene
from .koplanare_ziele import pruefe_koplanar
from .pmi_ableiten import LINEARMASS, aus_text
from . import pmi_strichschrift as schrift


def _verknuepft(g, modell, ids):
    from .pmi_lesen import geometrieziele_von_aspekt
    from .step_schreiben import randkanten

    datei = getattr(modell, "datei", None)
    if datei is None:
        return False
    ziele = set()
    for nr in g.pmi_ids:
        aspekt = datei.get(nr)
        if aspekt and aspekt.is_a("SHAPE_ASPECT"):
            gruppe = geometrieziele_von_aspekt(datei, modell, nr)
            if not gruppe:
                return False
            ziele.update(gruppe)
    flaechen = ziele & modell.step_zu_flaeche.keys()
    if {modell.step_zu_flaeche[nr] for nr in flaechen} != set(ids):
        return False
    kanten = ziele - flaechen
    return not kanten or kanten <= set().union(*(randkanten(datei, f) for f in flaechen))


def auflagenlage(modell, ids):
    """Normale, unteres Niveau, Abstand und Zahl getrennter Auflagen auf der Gegenseite."""
    from OCC.Core.BRep import BRep_Tool
    if not 2 <= len(ids) <= 100 or any(i < 0 or i >= len(modell.flaechen) for i in ids):
        return None
    if any(BRep_Tool.Surface(modell.flaechen[i]) is None for i in ids):
        return None
    lagen = [(i, ebene(modell.flaechen[i])) for i in ids]
    if any(e is None for _, e in lagen):
        return None
    normale = lagen[0][1][1]
    if any(np.linalg.norm(np.cross(e[1], normale)) > 1e-8 for _, e in lagen):
        return None
    hoehen = sorted((float(e[0] @ normale), i) for i, e in lagen)
    unten = [i for h, i in hoehen if h - hoehen[0][0] <= 1e-7]
    oben = [i for h, i in hoehen if hoehen[-1][0] - h <= 1e-7]
    if len(unten) + len(oben) != len(ids) or min(len(unten), len(oben)) != 1:
        return None
    gruppe = oben if len(unten) == 1 else unten
    if pruefe_koplanar(len(gruppe), gruppe, modell).status != "gleich":
        return None
    return normale, hoehen[0][0], hoehen[-1][0] - hoehen[0][0], len(gruppe)


def _baender(pfade):
    """Pfade nach ueberlappenden Hoehen gruppieren, damit keine Nebenangabe verschwindet."""
    baender = []
    ende = -np.inf
    for p, voll in sorted(pfade, key=lambda paar: paar[0][:, 1].min()):
        unten, oben = p[:, 1].min(), p[:, 1].max()
        if unten > ende + 1e-6:
            baender.append([])
        baender[-1].append((p, voll))
        ende = max(ende, oben)
    return baender


def _massende(band, niveau):
    from .pmi_hinweislinie import _gefuellte_endteile

    teile = [p for p, voll in band if not voll]
    gefuellt = [p for p, voll in band if voll]
    if gefuellt:
        rekonstruiert = _gefuellte_endteile(gefuellt)
        if not rekonstruiert:
            return None
        teile.extend(rekonstruiert)
    if len(teile) != 3:
        return None
    linien = [p for p in teile if len(p) == 2]
    if len(linien) != 2:
        return None
    quer, schaft = sorted(linien, key=lambda p: -np.ptp(p[:, 0]))
    achse = schaft[:, 0].mean()
    if (max(abs(quer[:, 1]-niveau)) > .002 or np.ptp(quer[:, 0]) < .25
            or not quer[:, 0].min() <= achse <= quer[:, 0].max()
            or np.ptp(schaft[:, 0]) > .002 or not schaft[:, 1].min() < niveau < schaft[:, 1].max()):
        return None
    rand = next(p for p in teile if len(p) != 2)
    if len(rand) < 4 or np.linalg.norm(rand[0]-rand[-1]) > .002:
        return None
    relativ = rand[:-1] - (achse, niveau)
    if len(relativ) == 3:
        spitze = np.linalg.norm(relativ, axis=1).argmin()
        a, b = np.delete(relativ, spitze, axis=0)
        if (np.linalg.norm(relativ[spitze]) <= .002 and a[0]*b[0] < 0 and abs(a[0]+b[0]) < .002
                and abs(a[1]-b[1]) < .002 and .01 < (2*niveau-1)*a[1] < .5):
            return achse
    elif len(relativ) >= 8:
        radien = np.linalg.norm(relativ, axis=1)
        winkel = np.unwrap(np.arctan2(relativ[:, 1], relativ[:, 0]))
        schritte = np.diff(np.r_[winkel, winkel[0] + np.sign(winkel[-1]-winkel[0])*2*np.pi])
        if (.01 < radien.mean() < .3 and np.ptp(radien) < .015*radien.mean()
                and (np.all(schritte > 0) or np.all(schritte < 0)) and max(abs(schritte)) < np.pi/3):
            return achse
    return None


def _massangabe(band, anzahl, abstand, faktor):
    punkte = np.vstack([p for p, _ in band])
    hoehe = np.ptp(punkte[:, 1])
    if hoehe <= 0:
        return None
    maske, _ = schrift._gesamtbild(band, 120/hoehe)
    if maske is None:
        return None
    lesungen = set()
    for bild in (maske, maske[::-1], maske[:, ::-1], maske[::-1, ::-1]):
        wort = schrift._masszeile(bild)
        menge, trenner, mass = wort.partition("X")
        if trenner and re.fullmatch(r"[1-9][0-9]{0,3}", menge) and LINEARMASS.fullmatch(mass):
            lesungen.add((wort, int(menge), mass))
    if len(lesungen) != 1:
        return None
    wort, menge, mass = lesungen.pop()
    if menge != anzahl:
        return None
    daten = aus_text([mass], faktor)
    nominal = mass.split("±")[0].replace(",", ".")
    rundung = .5*faktor*10**-len(nominal.partition(".")[2])
    if not daten or abs(daten["nennwert"] - abstand) > rundung + 1e-7:
        return None
    return wort, dict(daten, typ="Size_Thickness")


def dickenmass(g, modell, ids):
    """Nur vollstaendige Masslinien auf den verknuepften Ebenen und den gedruckten Wert vorschlagen."""
    if not schrift._lesbar(g) or not _verknuepft(g, modell, ids) or not (lagen := auflagenlage(modell, ids)):
        return None
    normale, unten, abstand, anzahl = lagen
    rahmen = g.ebene if g.ebene is not None else next(schrift._rahmenrichtungen(g), None)
    if rahmen is None or abs(rahmen[3] @ normale) > 1e-6:
        return None
    o, _, _, z = rahmen
    punkte = [*g.linien, *(p for p, _ in g.dreiecke)]
    if not punkte or any(np.any(abs((p-o) @ z) > .001*abstand) for p in punkte):
        return None
    o = o + (unten-o@normale)*normale
    pfade = schrift._pfade(g, (o, np.cross(normale, z)/abstand, normale/abstand, z))
    baender = _baender(pfade)
    if len(baender) != 3:
        return None
    achse_unten = _massende(baender[0], 0)
    achse_oben = _massende(baender[2], 1)
    if achse_unten is None or achse_oben is None or abs(achse_unten-achse_oben) > .002:
        return None
    mitte = np.vstack([p for p, _ in baender[1]])
    if not mitte[:, 0].min() <= achse_unten <= mitte[:, 0].max():
        return None
    return _massangabe(baender[1], anzahl, abstand, g.textfaktor)
