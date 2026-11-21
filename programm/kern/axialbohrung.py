"""Axiale Bohrkanten und konzentrische Ringe einer Wellenzeichnung pruefen."""

from dataclasses import dataclass

import numpy as np


def tintenlaeufe(spur):
    grenzen = np.flatnonzero(np.diff(spur, prepend=False, append=False))
    return grenzen.reshape(-1,2)


def _wand_durchgehend(spur, stift):
    # Gleichmaessige Strichluecken zulassen, groessere Unterbrechungen oder kurze Stummel auslassen.
    laeufe = tintenlaeufe(spur)
    if not len(laeufe):
        return False
    luecken = laeufe[1:,0]-laeufe[:-1,1]
    rand = max(laeufe[0,0], len(spur)-laeufe[-1,1])
    if not len(luecken):
        return rand <= 1
    if len(luecken) < 2 or spur.mean() < .35:
        return False
    normal = np.median(luecken)
    return normal <= 8*stift and max(luecken) <= normal+max(1,.2*normal) and rand <= normal+stift/2+1


@dataclass(frozen=True)
class Sacklochspur:
    durchmesser: float
    tiefe: float
    von_rechts: bool


def _bohrgrenzen(rest, baender, grenzen, wandstift):
    # Alle Kanten ausser den beiden Waenden muessen zum selben ebenen Grund gehoeren.
    if rest[:baender[0,0]].any() or rest[baender[1,1]:].any():
        return ()
    boden = tintenlaeufe(rest.any(axis=0))
    if not len(boden):
        return grenzen[1:-1]
    links, rechts = boden[0,0], boden[-1,1]
    if rechts-links <= wandstift+2:
        if len(boden) == 1:
            reihen = rest[:,links:rechts]
            kern = np.flatnonzero(reihen[reihen.any(axis=1)].all(axis=0))
            return [links+kern.mean()] if len(kern) else ()
        # Die schmale Schulter kann die Mitte eines dickeren Bodenstrichs verdecken.
        return [x for x in grenzen[1:-1] if links < x < rechts]
    return ()


def bohrspur(tinte, erlaubt, grenzen, mitte, radien, stift):
    rest = tinte & ~erlaubt
    if not rest.any():
        return 0., 0.
    baender = tintenlaeufe(rest.sum(axis=1) > 2*(stift+2))
    if len(baender) != 2:
        baender = tintenlaeufe(rest.any(axis=1))
    if len(baender) != 2:
        return None
    striche = baender[:,1]-baender[:,0]
    oben, unten = baender.mean(axis=1)-.5
    radius, wandstift = (unten-oben)/2, max(striche)
    abstand = (stift+wandstift)/2+1
    if np.ptp(striche) > 2 or abs((oben+unten)/2-mitte) > 1 or radius <= abstand:
        return None
    waende = [tinte[lo:hi].any(axis=0) for lo,hi in baender]
    wandpixel = np.flatnonzero(np.logical_or.reduce([rest[lo:hi].any(axis=0) for lo,hi in baender]))

    def reicht_bis(a, b):
        if wandpixel[0] < a-wandstift/2-1 or wandpixel[-1] > b+wandstift/2+1:
            return False
        rand = max(stift,wandstift)/2+1
        start, ende = int(np.floor(a+rand))+1, int(np.ceil(b-rand))
        return ende > start and all(_wand_durchgehend(w[start:ende], wandstift) for w in waende)

    for lo,hi in baender:
        rest[lo:hi] = False
    if not rest.any() and min(radien)-radius > abstand and reicht_bis(grenzen[0],grenzen[-1]):
        return 2*radius, wandstift
    treffer = []
    for x in _bohrgrenzen(rest, baender, grenzen, wandstift):
        if not grenzen[0] < x < grenzen[-1]:
            continue
        senkrecht = tinte[round(oben):round(unten)+1,round(x-stift/2):round(x+stift/2)+1].any(axis=1)
        if not _wand_durchgehend(senkrecht, wandstift):
            continue
        for rechts, eintritt in ((False,grenzen[0]),(True,grenzen[-1])):
            a,b = sorted((eintritt,x))
            beruehrt = [r for l,h,r in zip(grenzen[:-1],grenzen[1:],radien,strict=True) if l < b and a < h]
            if min(beruehrt)-radius > abstand and reicht_bis(a,b):
                treffer.append(Sacklochspur(2*radius, b-a, rechts))
    return (treffer[0], wandstift) if len(treffer) == 1 else None


def stirnringe(bild, box, kreise):
    """Konzentrische Vektorringe gegen den vollstaendigen gedruckten Ansichtsinhalt pruefen."""
    from scipy import ndimage
    h, w = bild.shape[:2]
    l,t,r,b = np.rint(np.clip(box,0,1)*[w,h,w,h]).astype(int)
    kreise = sorted(kreise, key=lambda k: k.r)
    if len(kreise) < 2:
        return ()
    mitte = np.array(kreise[0].mitte)
    if any(np.linalg.norm(mitte-k.mitte) > .5 for k in kreise):
        return ()
    radien = np.array([k.r for k in kreise])
    if min(np.diff(radien)) < 3:
        return ()
    tinte = bild[t:b,l:r,:3].min(axis=2) < 245
    if not tinte.any():
        return ()
    bedeckt = ndimage.maximum_filter(tinte,size=3)
    strich = ndimage.distance_transform_edt(tinte)
    ys,xs = np.nonzero(tinte)
    dx,dy = xs+l-mitte[0], ys+t-mitte[1]
    rho = np.hypot(dx,dy)
    erlaubt = np.zeros(len(xs), dtype=bool)
    strichbreiten = []
    for radius in radien:
        phi = np.linspace(0, 2*np.pi, max(32,int(np.ceil(2*np.pi*radius))), endpoint=False)
        x = np.rint(mitte[0]-l+radius*np.cos(phi)).astype(int)
        y = np.rint(mitte[1]-t+radius*np.sin(phi)).astype(int)
        if min(x) < 1 or min(y) < 1 or max(x) >= r-l-1 or max(y) >= b-t-1 or not bedeckt[y,x].all():
            return ()
        toleranz = max(2.,np.median(strich[y,x])+1.)
        if 2*toleranz >= min(np.diff(radien)) or toleranz >= radius/2:
            return ()
        strichbreiten.append(toleranz)
        erlaubt |= abs(rho-radius) <= toleranz
    erlaubt |= np.minimum(abs(dx),abs(dy)) <= min(strichbreiten)
    return tuple(2*radien) if erlaubt.all() else ()
