"""Durchgehende Bohrkanten und konzentrische Ringe einer Wellenzeichnung pruefen."""

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


def bohrspur(tinte, erlaubt, grenzen, mitte, aussenradius, stift):
    rest = tinte & ~erlaubt
    baender = tintenlaeufe(rest.any(axis=1))
    if not len(baender):
        return 0., 0.
    if len(baender) != 2:
        return None
    striche = baender[:,1]-baender[:,0]
    if np.ptp(striche) > 2:
        return None
    wandstift = max(striche)
    oben, unten = baender.mean(axis=1)-.5
    radius = (unten-oben)/2
    if abs((oben+unten)/2-mitte) > 1 or min(radius,aussenradius-radius) <= (stift+wandstift)/2+1:
        return None
    start = int(np.floor(grenzen[0]+stift/2+1))+1
    ende = int(np.ceil(grenzen[-1]-stift/2-1))
    if rest[:,:max(0,round(grenzen[0]-wandstift/2-1))].any() or rest[:,round(grenzen[-1]+wandstift/2+1):].any() or ende <= start:
        return None
    for y1,y2 in baender:
        if not _wand_durchgehend(tinte[y1:y2,start:ende].any(axis=0), wandstift):
            return None
    return 2*radius, wandstift


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
