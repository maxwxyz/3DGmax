"""Gemeinsames Symbol und beide Wertzeilen eines grafischen Verbundrahmens lesen."""

import numpy as np

from . import pmi_strichschrift as schrift
from .pmi_ableiten import gueltige_rahmenzellen
from .pmi_hinweislinie import punkt_hinweislinie


def _fachreihe(teile, symbol, grenze):
    rechts = symbol[2]
    reihe = sorted(teile)
    if not 1 <= len(reihe) <= 4 or not 0 < reihe[0][0] - rechts <= grenze:
        return []
    if any(abs(t-reihe[0][1]) > 2 or abs(b-reihe[0][3]) > 2 for _, t, _, b in reihe):
        return []
    if any(not 0 < z[0]-a[2] <= grenze for a, z in zip(reihe, reihe[1:])):
        return []
    return reihe


def _verbundzellen(faecher, maske):
    if len(faecher) < 3:
        return []
    symbol = max(faecher, key=lambda f: f[3]-f[1])
    _, t, r, b = symbol
    h = (b-t)/2
    grenze = max(3, .10*h)
    zeilen = [z for z in faecher if .85*h <= z[3]-z[1] <= 1.15*h]
    oben = _fachreihe([z for z in zeilen if abs(z[1]-t) <= 2], symbol, grenze)
    unten = _fachreihe([z for z in zeilen if abs(z[3]-b) <= 2], symbol, grenze)
    if (not oben or not unten or len(oben)+len(unten) != len(zeilen)
            or not 0 < unten[0][1]-oben[0][3] <= grenze):
        return []
    # Auch im freien Bereich neben einer kuerzeren Zeile koennte ein Zusatz stehen.
    rest = maske.copy()
    stege = [unten[0][1]-oben[0][3], oben[0][0]-r, unten[0][0]-r]
    stege.extend(z[0]-a[2] for reihe in (oben, unten) for a, z in zip(reihe, reihe[1:]))
    rand = max(stege)+1
    for x, y, u, v in [symbol, *oben, *unten]:
        rest[max(0,y-rand):v+rand, max(0,x-rand):u+rand] = False
    if rest.any() and not punkt_hinweislinie(rest, symbol, rand):
        return []
    return [[symbol, *oben], [symbol, *unten]]


def _lesarten(pfade, richtungen):
    p = np.vstack([p for p, _ in pfade])
    dx, dy = np.ptp(p, axis=0)
    if min(dx, dy) <= 0:
        return ()
    k = min(500/dy, 1800/dx)
    m, box = schrift._gesamtbild(pfade, k)
    if m is None:
        return ()
    faecher = schrift._rechteckfaecher(m, .32)
    if len(faecher) < 3:
        return ()
    ergebnisse = set()
    h, w = m.shape
    for x, y in richtungen:
        # Erst die Rahmenlage spiegeln. Nur eine passende Zellfolge braucht Schrifterkennung.
        gespiegelt = []
        for fach in faecher:
            l, t, r, b = fach
            links, rechts = (l, r) if x == 1 else (w-r, w-l)
            oben, unten = (t, b) if y == 1 else (h-b, h-t)
            gespiegelt.append((links, oben, rechts, unten))
        zeilen = _verbundzellen(gespiegelt, m[::y, ::x])
        if not zeilen:
            continue
        if (x, y) == (1, 1):
            ergebnisse.update(_zeilentexte(pfade, zeilen, box, k))
        else:
            # Das Rastern gespiegelter Kanten kann um einen Pixel vom gespiegelten Raster abweichen.
            orientiert = [(p * [x, y], voll) for p, voll in pfade]
            bild, lage = schrift._gesamtbild(orientiert, k)
            faecher_neu = schrift._rechteckfaecher(bild, .32)
            reihen = _verbundzellen(faecher_neu, bild)
            if reihen:
                ergebnisse.update(_zeilentexte(orientiert, reihen, lage, k))
    return ergebnisse


def _zeilentexte(pfade, zeilen, box, k):
    lesarten = set()
    # Zwei Rasteraufloesungen trennen duenne Glyphen; jede komplette Lesart muss uebereinstimmen.
    for pixelhoehe in (100, 150):
        lesarten.update(_lese_faecher(pfade, zeilen, box, k, pixelhoehe))
    return lesarten


def _lese_faecher(pfade, zeilen, box, k, pixelhoehe):
    masken = {}
    for fach in set(zeilen[0]+zeilen[1]):
        l, t, r, b = fach
        fachbox = box[0]+(l-3)/k, box[3]-(b-2)/k, box[0]+(r-2)/k, box[3]-(t-3)/k
        maske = schrift._fachmaske(pfade, fachbox, pixelhoehe)
        if maske is None:
            return ()
        masken[fach] = maske
    lesarten = set()
    for lesen in (schrift._normale_zeile, lambda m: schrift._breite_zeile(m, rahmen=True)):
        zeichen = {f: lesen(m) for f, m in masken.items()}
        reihen = [[zeichen[f] for f in z] for z in zeilen]
        if all(gueltige_rahmenzellen(z) for z in reihen):
            lesarten.add(tuple(" ".join(z) for z in reihen))
    return lesarten


def lies_verbund(g):
    """Beide Rahmenzeilen muessen in allen lesbaren Ausrichtungen uebereinstimmen."""
    if not schrift._lesbar(g):
        return ()
    ebenen = (g.ebene,) if g.ebene is not None else schrift._rahmenrichtungen(g)
    richtungen = ((1, 1),) if g.ebene is not None else ((1, 1), (-1, 1), (1, -1), (-1, -1))
    ergebnisse = set()
    for ebene in ebenen:
        pfade = schrift._pfade(g, ebene)
        if pfade:
            ergebnisse.update(_lesarten(pfade, richtungen))
        if len(ergebnisse) > 1:
            return ()
    return ergebnisse.pop() if ergebnisse else ()
