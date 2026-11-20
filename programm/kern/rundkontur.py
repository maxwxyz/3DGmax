"""Geschlossene PDF-Konturen mit tangentialen Viertel- oder Halbkreisen pruefen."""

import numpy as np
from scipy import ndimage


def _abstand(p, mitte, halb, radius):
    q = np.abs(p-mitte)-(halb-radius)
    return np.linalg.norm(np.maximum(q, 0.), axis=1)+np.minimum(q.max(axis=1), 0.)-radius


def rundrechteck(p):
    """Linker/oberer und rechter/unterer Rand plus gemeinsamer Radius in Blattpixeln."""
    if len(p) < 16 or np.linalg.norm(p[0]-p[-1]) > .25:
        return None
    lo, hi = p.min(axis=0), p.max(axis=0)
    halb, mitte = (hi-lo)/2, (hi+lo)/2
    ab = np.minimum(p-lo, hi-p)
    innen = ab.min(axis=1) > .08
    x, y = ab[innen].T
    if len(x) < 8:
        return None
    # (r-x)^2+(r-y)^2=r^2, jeweils gemessen von der Ecke des Begrenzungsrechtecks.
    r = np.median(x+y+np.sqrt(2*x*y))
    if r < 2:
        return None
    toleranz = max(.12, .012*r)
    if min(halb)-r < 1:
        # Beim Langloch fallen die Viertelkreise an beiden Enden paarweise zusammen.
        achse = int(np.argmax(halb))
        if max(halb)-min(halb) < 1 or abs(min(halb)-r) > toleranz:
            return None
        for ende in (lo[achse], hi[achse]):
            extrem = p[np.abs(p[:,achse]-ende) < .001, 1-achse]
            if np.ptp(extrem) > .05:
                return None
        r = min(halb)
    for sx in (-1,1):
        for sy in (-1,1):
            ecke = p[innen & ((p[:,0]-mitte[0])*sx > 0) & ((p[:,1]-mitte[1])*sy > 0)]
            if len(ecke) < 2:
                return None
    # Auch die Sehnenmitten pruefen, damit abgeschraegte Ecken nicht als Rundung gelten.
    proben = np.vstack((p, (p[:-1]+p[1:])/2))
    if np.abs(_abstand(proben, mitte, halb, r)).max() > toleranz:
        return None
    return np.array([*lo, *hi, r])


def druckrand(raender, alternativ):
    """Zwei entgegengesetzte Raender eines gefuellten Strichs auf die Mittellinie reduzieren."""
    if len(raender) != 2:
        return None
    (a, sinn), (b, gegensinn) = sorted(raender, key=lambda paar: paar[0][4])
    if sinn == gegensinn and not alternativ:
        return None
    strich = b[4]-a[4]
    if not 0 < strich < min(6., .45*b[4]):
        return None
    if np.max(np.abs((b-a)[:4] - strich*np.array([-1,-1,1,1]))) > .25:
        return None
    return (a+b)/2


def passende_rundung(teil, x0, y0, konturen):
    h, w = teil.shape
    box = np.array([x0, y0, x0+w-1, y0+h-1])
    kandidaten = [q for q in konturen if np.max(np.abs(q[:4]-box)) <= 3]
    if len(kandidaten) != 1 or teil[h//2,w//2]:
        return None
    q, = kandidaten
    lo, hi, r = q[:2], q[2:4], q[4]
    ys, xs = np.nonzero(teil)
    abstand = _abstand(np.column_stack((x0+xs,y0+ys)), (hi+lo)/2, (hi-lo)/2, r)
    if np.abs(abstand).max() > 3:
        return None
    gefuellt = ndimage.binary_fill_holes(teil, structure=np.ones((3,3), bool))
    return q if gefuellt[h//2,w//2] else None
