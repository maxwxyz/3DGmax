"""Gezeichnete Geltungshinweise unter einem Verbundrahmen."""

from functools import lru_cache

import numpy as np
from scipy import ndimage

from .pmi_ableiten import geltungshinweis
from .pmi_strichschrift import _breite_zeile, _gruppen

# Strichzuege der Grossbuchstaben und der Null, auf 16 Einheiten Versalhoehe gerundet (FTC-07).
_ZUEGE = {
    "0": [[(10,16),(14,14),(16,9),(16,6),(14,1),(10,0),(6,0),(2,1),(0,6),(0,9),(2,14),(6,16),(10,16)]],
    "4": [[(15,9),(0,9),(11,0),(11,16)]],
    "C": [[(15,13),(11,16),(4,16),(0,13),(0,3),(4,0),(11,0),(15,3)]],
    "P": [[(0,16),(0,0),(11,0),(15,1),(15,6),(11,8),(0,8)]],
    "A": [[(0,16),(8,0),(15,16)],[(4,8),(11,8)]],
    "D": [[(0,16),(11,16),(15,13),(15,3),(11,0),(0,0),(0,16)]],
    "E": [[(15,16),(0,16),(0,0),(15,0)],[(11,8),(0,8)]],
    "F": [[(0,16),(0,0),(15,0)],[(9,6),(0,6)]],
    "G": [[(8,8),(15,8),(15,13),(12,16),(4,16),(0,13),(0,3),(4,0),(11,0),(15,3)]],
    "I": [[(0,16),(4,16)],[(2,0),(2,16)],[(0,0),(4,0)]],
    "L": [[(0,0),(0,16),(15,16)]],
    "M": [[(0,16),(0,0),(8,16),(16,0),(16,16)]],
    "N": [[(0,16),(0,0),(15,16),(15,0)]],
    "O": [[(4,16),(12,16),(15,13),(15,3),(12,0),(4,0),(0,3),(0,13),(4,16)]],
    "Q": [[(12,13),(14,14),(10,16),(6,16),(2,14),(0,11),(0,5),(2,1),(6,0),(10,0),
           (14,1),(16,5),(16,11),(14,14),(16,16)]],
    "R": [[(0,16),(0,0),(11,0),(15,1),(15,6),(11,8),(0,8)],[(15,16),(11,8)]],
    "S": [[(0,14),(4,16),(12,16),(16,14),(16,9),(12,8),(4,8),(0,6),(0,1),(4,0),(12,0),(16,1)]],
    "T": [[(8,0),(8,16)],[(15,0),(0,0)]],
    "U": [[(0,0),(0,13),(4,16),(11,16),(15,13),(15,0)]],
    "V": [[(0,0),(8,16),(15,0)]],
    "W": [[(0,0),(4,16),(7,0),(11,16),(15,0)]],
}


@lru_cache(maxsize=1)
def _vorlagen():
    bilder = {}
    for buchstabe, zuege in _ZUEGE.items():
        bild = np.zeros((35, 35), bool)
        for zug in zuege:
            for a, b in zip(zug, zug[1:]):
                x, y = np.rint(1 + 2*np.linspace(a, b, 65)).astype(int).T
                bild[y, x] = True
        bilder[buchstabe] = bild, ndimage.distance_transform_edt(~bild)
    return bilder


def _buchstabe(teil, nummer=False):
    y, x = np.nonzero(teil)
    dx, dy = np.ptp(x), np.ptp(y)
    if dy < 8 or not .12 <= dx/dy <= 1.3:
        return ""
    bild = np.zeros((35, 35), bool)
    # Eine leichte Breitenskalierung gehoert zur Schrift, die schmale Form des I bleibt erhalten.
    breite = 8 if dx/dy < .45 else 31
    bild[1+np.rint(32*(y-y.min())/dy).astype(int), 1+np.rint(breite*(x-x.min())/dx).astype(int)] = True
    dist = ndimage.distance_transform_edt(~bild)
    treffer = {}
    for z, (vorlage, abstand) in _vorlagen().items():
        if (z == "I") != (breite == 8) or (z.isdigit() and not nummer):
            continue
        abweichung = max(dist[vorlage].max(), abstand[bild].max())
        if abweichung <= 3.2:
            treffer[z] = abweichung
    if len(treffer) == 1:
        return next(iter(treffer))
    if nummer and treffer.keys() == {"0", "O"}:
        # Bei der Null sind die geraden Flanken kuerzer. Maximum und Mittel muessen dieselbe Form stuetzen.
        besser, schlechter = sorted(treffer, key=treffer.get)
        if treffer[schlechter] - treffer[besser] >= .75:
            def mittel(z):
                vorlage, abstand = _vorlagen()[z]
                return (dist[vorlage].mean() + abstand[bild].mean()) / 2
            if mittel(schlechter) - mittel(besser) > .25:
                return besser
    return "?" if nummer and treffer else ""


def lies_hinweiszeile(zeile, *, anzahl=False):
    gruppen = _gruppen(zeile)
    zeichen = []
    rechts = gruppen[0][0]
    for links, r in gruppen:
        wortabstand = (links-rechts)/len(zeile)
        if wortabstand > 1.35:
            return None
        if wortabstand > .44:
            zeichen.append(" ")
        teil = zeile[:, links:r]
        ys = np.nonzero(teil)[0]
        if ys.min() > .09*len(zeile) or ys.max()+1 < .91*len(zeile):
            return None
        bisher = "".join(zeichen)
        nummer = bisher.startswith("SIM REQT ") or (anzahl and (not bisher or bisher.isdigit()))
        z = _buchstabe(teil, nummer)
        if not z and nummer:
            # Die Null braucht den Formvergleich mit O; I und Q koennen ebenfalls wie Ziffern aussehen.
            ziffer = _breite_zeile(teil, rahmen=True)
            if len(ziffer) == 1 and ziffer in "123456789":
                z = ziffer
        if not z:
            return None
        zeichen.append(z)
        rechts = r
    return "".join(zeichen)


def lies_zusatz(rest, symbol, rand):
    """Vollstaendige bekannte Hinweise lesen und nur ihre tatsaechlichen Textzeilen freistellen."""
    l, t, _, b = symbol
    h = b-t
    x = max(0, l-rand-2)
    y = b+rand
    ausschnitt = rest[y:, x:]
    texte, bereiche = [], []
    ende = 0
    for oben, unten in _gruppen(ausschnitt.T):
        if oben-ende > .22*h:
            break
        zeile = ausschnitt[oben:unten]
        gruppen = _gruppen(zeile)
        if not (.17*h < unten-oben < .36*h and gruppen[0][0] <= 2*rand+3 and len(gruppen) <= 40):
            return None
        text = lies_hinweiszeile(zeile)
        if not text:
            return None
        texte.append(text)
        bereiche.append((y+oben, y+unten))
        ende = unten
    text = geltungshinweis(" ".join(texte))
    if not text:
        return None
    for oben, unten in bereiche:
        rest[oben:unten, x:] = False
    return text
