"""Form- und Laufzeichen im ersten Fach eines gezeichneten Toleranzrahmens."""

from functools import cache

import numpy as np
from scipy import ndimage


def _ring(x, y, radii, r):
    """Jeder Winkelsektor muss denselben geschlossenen Kreiszug tragen."""
    # Auch eine fast geschlossene Klammer belegt alle groben Winkelsektoren.
    maske = np.zeros((int(np.ptp(y))+3, int(np.ptp(x))+3), bool)
    maske[(y-y.min()).astype(int)+1, (x-x.min()).astype(int)+1] = True
    if not ndimage.binary_fill_holes(maske)[maske.shape[0]//2, maske.shape[1]//2]:
        return False
    phi = np.arctan2(y, x)
    sektor = np.floor((phi + np.pi) * 36 / (2*np.pi)).astype(int) % 36
    lo, hi = np.full(36, np.inf), np.zeros(36)
    np.minimum.at(lo, sektor, radii)
    np.maximum.at(hi, sektor, radii)
    if not np.isfinite(lo).all():
        return False
    return np.ptp((lo+hi)/2) <= max(1.5, .055*r) and max(hi-lo) <= max(2., .19*r)


def _profilbogen(glyph):
    """Oberer Halbkreis mit zwei offenen Fuessen, auch als schmaler Strichumriss."""
    h, w = glyph.shape
    if not 1.8*h < w < 2.14*h:
        return False
    y, x = np.nonzero(glyph)
    r = (w-1)/2
    dx, dy = x-r, h-1-y
    radial = np.hypot(dx,dy)/r
    if radial.min() < .82 or radial.max() > 1.1:
        return False
    sektor = np.minimum(23, (np.arctan2(dy,dx)*24/np.pi).astype(int))
    saum = max(2, round(.07*h))
    return (len(np.unique(sektor)) == 24 and glyph[-saum:,:saum].any() and glyph[-saum:,-saum:].any()
            and ndimage.label(glyph, np.ones((3,3)))[1] == 1)


def _kreiszeichen(glyph):
    h, w = glyph.shape
    if abs(w-h) > .06*max(w,h):
        return ""
    y, x = np.nonzero(glyph)
    x, y = x - (w-1)/2, y - (h-1)/2
    radii = np.hypot(x, y)
    r = max(radii)
    if min(radii) >= .81*r:
        return "○" if _ring(x, y, radii, r) else ""
    # Bei zwei Zeichenringen muss dazwischen ein durchgehend freier Kreis liegen.
    sortiert = np.sort(radii)
    i = np.argmax(np.diff(sortiert))
    if not (.4*r < sortiert[i] < .77*r and sortiert[i+1] - sortiert[i] > .10*r):
        return ""
    innen = radii <= sortiert[i]
    if _ring(x[innen], y[innen], radii[innen], r) and _ring(x[~innen], y[~innen], radii[~innen], r):
        return "◎"
    return ""


@cache
def _laufpfeile():
    from .pmi_strichschrift import _bild, _merkmal
    # Umriss, Flaechenfuellung und einzelne Mittelstriche je Symbol.
    einzeln = [(1,1), (.76,.48), (.64,.60), (.04,0), (0,.04), (.60,.64), (.48,.76), (1,1)]
    doppelt = [(1.67,1), (1.43,.48), (1.31,.60), (.71,0), (0,0), (.64,.64),
               (.51,.77), (1.03,1), (.79,.48), (.67,.60), (.12,.05), (.69,.05),
               (1.27,.64), (1.15,.77), (1.67,1)]
    vorlagen = []
    for zeichen, umriss, starts in (("↗", einzeln, [0.]), ("⌰", doppelt, [0., .67])):
        kontur = np.array(umriss)
        formen = [[(kontur, False)], [(kontur, True)]]
        for geschlossen in (True, False):
            zuege = []
            for a in starts:
                spitze = [(.49,.77), (1,1), (.77,.49)]
                if geschlossen:
                    spitze.append(spitze[0])
                zuege.extend([(np.array(zug) + [a,0], False) for zug in ([(0,0),(1,1)], spitze)])
            if len(starts) == 2:
                zuege.append((np.array([(0.,0.), (starts[1],0.)]), False))
            formen.append(zuege)
        for pfade in formen:
            m = _merkmal(_bild(pfade, (0.,0.,1.7,1.), 80.))
            vorlagen.append((zeichen, m, ndimage.distance_transform_edt(~m)))
    return vorlagen


def formzeichen(maske):
    """Nur im Merkmalfach. Ein kurzer Zahlenstrich oder Modifikatorkreis hat dort eine andere Rolle."""
    y, x = np.nonzero(maske)
    if not len(x):
        return ""
    glyph = maske[y.min():y.max()+1, x.min():x.max()+1]
    h, w = glyph.shape
    fach = maske.shape[0] - 5
    if abs(y.mean() - maske.shape[0]/2) > .18*fach:
        return ""
    if .55*fach < w < 1.5*fach and h <= max(2, .085*w):
        # Ein durchgehender Querstrich, auch als schmaler rechteckiger Umriss.
        if glyph.all(axis=1).any() and ndimage.label(glyph, np.ones((3,3)))[1] == 1:
            return "⏤"
    if not .4*fach < h < .94*fach:
        return ""
    if _profilbogen(glyph):
        return "⌒"
    if rund := _kreiszeichen(glyph):
        return rund
    from .pmi_strichschrift import _merkmal
    bild = _merkmal(glyph)
    dist = ndimage.distance_transform_edt(~bild)
    for zeichen, vorlage, abstand in _laufpfeile():
        a, b = dist[vorlage], abstand[bild]
        if max(a.max(), b.max()) <= 2.25 and max(a.mean(), b.mean()) <= .70:
            return zeichen
    return ""


def raumrahmen(g):
    """Schreibebene mit einer raeumlichen Fuehrung zu genau einer parallelen Zielebene."""
    from dataclasses import replace
    from . import pmi_strichschrift as schrift
    from .pmi_hinweislinie import abgesetzte_endlinie

    teile = [p for p in g.linien if len(p) >= 2]
    for xyz, t in g.dreiecke:
        teile.extend(xyz[t])
    if not teile:
        return ""
    punkte = np.vstack(teile)
    if not np.isfinite(punkte).all():
        return ""
    ecken = [np.cross(p[1:-1]-p[0], p[2:]-p[0]) for p in teile if len(p) >= 3]
    if not ecken:
        return ""
    n = np.vstack(ecken)
    n = n[np.linalg.norm(n, axis=1) > 1e-10]
    if not len(n):
        return ""
    n /= np.linalg.norm(n, axis=1)[:, None]
    n *= np.sign(n[np.arange(len(n)), np.argmax(abs(n), axis=1)])[:, None]
    _, gruppen, anzahl = np.unique(np.round(n, 3), axis=0, return_inverse=True, return_counts=True)
    normal = n[gruppen == anzahl.argmax()].mean(axis=0)
    normal /= np.linalg.norm(normal)
    tiefen = punkte @ normal
    tiefe = np.median(tiefen)
    ziel = tiefen[np.abs(tiefen-tiefe) > .001]
    if not len(ziel) or len(ziel) > .25*len(tiefen) or np.ptp(ziel) > .001:
        return ""
    auf, schaft, marke = [], [], []
    for p in teile:
        hier = abs(p @ normal - tiefe) <= .001
        (auf if hier.all() else marke if not hier.any() else schaft).append(p)
    if not schaft or not marke:
        return ""
    # Der raeumliche Schaft muss den Zielpunkt tatsaechlich auf seiner Tiefe erreichen.
    enden = np.vstack([p[abs(p @ normal - tiefe) > .001] for p in schaft])
    zentrum = (np.vstack(marke).min(axis=0)+np.vstack(marke).max(axis=0))/2
    ausdehnung = np.linalg.norm(np.ptp(np.vstack(marke), axis=0))
    if np.linalg.norm(enden.mean(axis=0)-zentrum) > .52*ausdehnung + .001:
        return ""
    lesarten = set()
    for o, x, y, z in schrift._rahmenrichtungen(replace(g, linien=auf, dreiecke=[])):
        for sx, sy in ((1,1), (-1,1), (1,-1), (-1,-1)):
            ebene = o, sx*x, sy*y, z
            pfade = schrift._pfade(g, ebene)
            zellen = schrift._zellen(pfade)
            if not 2 <= len(zellen) <= 5:
                continue
            h = zellen[0][3]-zellen[0][1]
            ausserhalb = (np.vstack([*schaft, *marke])-o) @ ebene[1]
            if not (max(ausserhalb) < zellen[0][0]-.1*h or min(ausserhalb) > zellen[-1][2]+.1*h):
                continue
            if abgesetzte_endlinie(pfade, zellen):
                wort = schrift._rahmentext(pfade, zellen)
                if wort:
                    lesarten.add(wort)
    return lesarten.pop() if len(lesarten) == 1 else ""
