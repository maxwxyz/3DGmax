"""Gemeinsames Symbol und beide Wertzeilen eines grafischen Verbundrahmens lesen."""

import numpy as np

from . import pmi_strichschrift as schrift
from .pmi_ableiten import gueltige_rahmenzellen
from .pmi_hinweislinie import doppelte_punktlinie, punkt_hinweislinie
from .pmi_rahmenzusatz import lies_zusatz


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


def _verbundzellen(faecher, maske, *, nur_anordnung=False):
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
    zeilen = [[symbol, *oben], [symbol, *unten]]
    if nur_anordnung:
        return zeilen, ""
    # Auch im freien Bereich neben einer kuerzeren Zeile koennte ein Zusatz stehen.
    rest = maske.copy()
    stege = [unten[0][1]-oben[0][3], oben[0][0]-r, unten[0][0]-r]
    stege.extend(z[0]-a[2] for reihe in (oben, unten) for a, z in zip(reihe, reihe[1:]))
    rand = max(stege)+1
    for x, y, u, v in [symbol, *oben, *unten]:
        rest[max(0,y-rand):v+rand, max(0,x-rand):u+rand] = False
    zusatz = ""
    if rest.any() and not punkt_hinweislinie(rest, symbol, rand):
        zusatz = lies_zusatz(rest, symbol, rand)
        if not zusatz or (rest.any() and not (punkt_hinweislinie(rest, symbol, rand)
                                              or doppelte_punktlinie(rest, symbol, rand))):
            return []
    return zeilen, zusatz


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
    h, w = m.shape
    for x, y in richtungen:
        # Erst die Rahmenlage spiegeln. Nur eine passende Zellfolge braucht Schrifterkennung.
        gespiegelt = []
        for fach in faecher:
            l, t, r, b = fach
            links, rechts = (l, r) if x == 1 else (w-r, w-l)
            oben, unten = (t, b) if y == 1 else (h-b, h-t)
            gespiegelt.append((links, oben, rechts, unten))
        zeilen = _verbundzellen(gespiegelt, m[::y, ::x], nur_anordnung=(x, y) != (1, 1))
        if not zeilen:
            continue
        orientiert, lage = pfade, box
        if (x, y) != (1, 1):
            # Das Rastern gespiegelter Kanten kann um einen Pixel vom gespiegelten Raster abweichen.
            orientiert = [(p * [x, y], voll) for p, voll in pfade]
            bild, lage = schrift._gesamtbild(orientiert, k)
            zeilen = _verbundzellen(schrift._rechteckfaecher(bild, .32), bild)
            if not zeilen:
                continue
        for text in _zeilentexte(orientiert, *zeilen, lage, k):
            yield text, (x, y), rahmenanker(zeilen, lage, k)


def rahmenanker(zeilen, box, k):
    """Rechte untere Symbolecke und Hoehe einer Wertzeile in der Schreibebene."""
    _, t, r, b = zeilen[0][0][0]
    return box[0]+(r-2)/k, box[3]-(b-2)/k, (b-t)/(2*k)


def _zeilentexte(pfade, zeilen, zusatz, box, k):
    lesarten = set()
    # Zwei Rasteraufloesungen trennen duenne Glyphen; jede komplette Lesart muss uebereinstimmen.
    for pixelhoehe in (100, 150):
        lesarten.update(_lese_faecher(pfade, zeilen, box, k, pixelhoehe))
    return {(*paar, zusatz) for paar in lesarten} if zusatz else lesarten


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


def lies_verbund_mit_lage(g):
    """Wortlaut und eindeutige Schreibebene mit Bezugspunkt fuer freistehende Hinweise."""
    if not schrift._lesbar(g):
        return (), None
    ebenen = (g.ebene,) if g.ebene is not None else schrift._rahmenrichtungen(g)
    richtungen = ((1, 1),) if g.ebene is not None else ((1, 1), (-1, 1), (1, -1), (-1, -1))
    gelesen, lagen = (), []
    for ebene in ebenen:
        pfade = schrift._pfade(g, ebene)
        if not pfade:
            continue
        for text, (x, y), anker in _lesarten(pfade, richtungen):
            if gelesen and gelesen != text:
                return (), None
            gelesen = text
            o, u, v, n = ebene
            lagen.append(((o, u*x, v*y, n*x*y), anker))
    return gelesen, lagen[0] if len(lagen) == 1 else None


def lies_verbund(g):
    """Beide Rahmenzeilen und gegebenenfalls ihr gemeinsamer Geltungshinweis."""
    return lies_verbund_mit_lage(g)[0]
