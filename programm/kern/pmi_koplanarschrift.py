"""Einzelner Profilrahmen mit direkt darunter gesetztem Geltungshinweis."""

from functools import lru_cache
import re

import numpy as np
from scipy import ndimage

from . import pmi_strichschrift as schrift
from .pmi_rahmenzusatz import lies_hinweiszeile

_HINWEIS = re.compile(r"[1-9][0-9]{0,3} COPLANAR SURFACES")


@lru_cache(maxsize=1)
def _vorlagen():
    from .pmi_versalmuster import MUSTER
    return [(z, maske, ndimage.distance_transform_edt(~maske)) for z, maske in schrift._musterbilder(MUSTER)]


def _konturzeile(zeile):
    wort = ""
    rechts = None
    for l, r in schrift._gruppen(zeile):
        teil = zeile[:, l:r]
        y = np.nonzero(teil)[0]
        if y.min() > .09*len(zeile) or y.max()+1 < .91*len(zeile):
            return ""
        form = schrift._merkmal(teil)
        dist = ndimage.distance_transform_edt(~form)
        treffer = sorted((abstand[form].mean() + dist[maske].mean(), z)
                         for z, maske, abstand in _vorlagen())
        if treffer[0][0] > 1.45 or treffer[1][0]-treffer[0][0] < .15:
            return ""
        if rechts is not None:
            luecke = (l-rechts)/len(zeile)
            if luecke > 1.35:
                return ""
            if luecke > .40:
                wort += " "
        wort += treffer[0][1]
        rechts = r
    return wort


def _beschriftung(pfade, links, unten, h):
    punkte = np.vstack([p for p, _ in pfade])
    x, y = punkte.min(axis=0)
    r, t = punkte.max(axis=0)
    if not (-.12*h <= x-links <= .35*h and .04*h < unten-t < .9*h and
            unten-y < 3*h and 2*h < r-x < 20*h and t > y):
        return ""
    maske, _ = schrift._gesamtbild(pfade, 80/(t-y))
    if maske is None:
        return ""
    zeilen = schrift._gruppen(maske.T)
    if not 1 <= len(zeilen) <= 2:
        return ""
    lesarten = []
    for a, b in zeilen:
        zeile = maske[a:b]
        gruppen = schrift._gruppen(zeile)
        if not (4 <= len(gruppen) <= 20 and gruppen[0][0] < .4*(b-a)):
            return ""
        lesarten.append((lies_hinweiszeile(zeile, anzahl=True, null_pruefen=True) or "", _konturzeile(zeile)))
    texte = {" ".join(lesung) for lesung in zip(*lesarten) if all(lesung)}
    if len(texte) != 1:
        return ""
    text = texte.pop()
    return text if _HINWEIS.fullmatch(text) else ""


def _lesung(pfade):
    zellen = schrift._zellen(pfade) if pfade else []
    if len(zellen) != 2:
        return None
    l, b, _, t = zellen[0]
    h = t-b
    zusatz, rahmen = [], []
    for p, voll in pfade:
        ziel = zusatz if p[:, 1].max() < b-.03*h and p[:, 0].min() >= l-.12*h else rahmen
        ziel.append((p, voll))
    if zusatz and (text := _beschriftung(zusatz, l, b, h)):
        wert = schrift._rahmentext(rahmen, zellen)
        if wert.startswith("⌓ "):
            return wert, text
    return None


def profil_mit_hinweis(g):
    from .pmi_freier_hinweis import _in_ebene
    if g.erzeugt or g.platzhalter or not schrift._lesbar(g) or not (g.linien or g.dreiecke):
        return None
    if g.ebene is not None:
        if not _in_ebene(g, g.ebene):
            return None
        return _lesung(schrift._pfade(g, g.ebene))
    funde = set()
    for ebene in schrift._rahmenrichtungen(g):
        pfade = schrift._pfade(g, ebene)
        if not pfade:
            continue
        for achsen in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            if fund := _lesung([(p*achsen, voll) for p, voll in pfade]):
                funde.add(fund)
    return funde.pop() if len(funde) == 1 else None


def passende_flaechen(g, anzahl, indices, modell, datei=None):
    from .koplanare_ziele import pruefe_koplanar
    from .pmi_lesen import geometrieziele_von_aspekt
    datei = datei if datei is not None else getattr(modell, "datei", None)
    if not g or datei is None:
        return False
    ziele = set()
    for nr in g.pmi_ids:
        aspekt = datei.get(nr)
        if aspekt and aspekt.is_a("SHAPE_ASPECT"):
            gruppe = geometrieziele_von_aspekt(datei, modell, nr)
            if not gruppe or not gruppe <= modell.step_zu_flaeche.keys():
                return False
            ziele.update(modell.step_zu_flaeche[n] for n in gruppe)
    return ziele == set(indices) and pruefe_koplanar(anzahl, ziele, modell).status == "gleich"


def passt_zur_quelle(p, modell, datei):
    """Bei der STEP-Ausgabe Grafik und Zielverweise nochmals aus der Quelldatei lesen."""
    from .praesentation import lies_grafik
    if p.art != "toleranz" or p.typ != "ProfileOfSurface" or not p.callout:
        return False
    g = lies_grafik(datei, ids={p.callout}).get(p.callout)
    fund = profil_mit_hinweis(g) if g else None
    return bool(fund and fund[1] == p.beschreibung and int(fund[1].split()[0]) == p.koplanare_anzahl
                and passende_flaechen(g, p.koplanare_anzahl, p.flaechen, modell, datei))
