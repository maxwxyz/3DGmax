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


def _bodenlagen(rest, grenzen, wandstift):
    # Alle Kanten ausser den beiden Waenden muessen zum selben ebenen Grund gehoeren.
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


@dataclass(frozen=True)
class Stufenbohrspur:
    stufen: tuple  # (Durchmesser, Tiefe ab Eintritt), durchgehender Kern ohne Tiefe
    von_rechts: bool


def bohrdurchmesser_am_absatz(spur, x, grenzen):
    if isinstance(spur,Sacklochspur):
        stufen = ((spur.durchmesser,spur.tiefe),)
    elif isinstance(spur,Stufenbohrspur):
        stufen = spur.stufen
    else:
        return spur, spur
    lage = grenzen[-1]-x if spur.von_rechts else x-grenzen[0]
    for i,(dm,tiefe) in enumerate(stufen):
        if tiefe is None or lage < tiefe-.5:
            return dm, dm
        if abs(lage-tiefe) <= .5:
            return dm, stufen[i+1][0] if i+1 < len(stufen) else 0.
    return 0., 0.


def _absatzkante(spur, breite, luecke):
    if _wand_durchgehend(spur,breite):
        return True
    # Kurze Schultern enthalten oft nur eine Luecke des Strichmusters der Wand.
    laeufe = tintenlaeufe(spur)
    if luecke is None or len(laeufe) != 2 or spur.mean() < .35:
        return False
    pause = laeufe[1,0]-laeufe[0,1]
    return abs(pause-luecke) <= max(1,.2*luecke) and max(laeufe[0,0],len(spur)-laeufe[-1,1]) <= luecke+1


def _stufenspuren(tinte, rest, baender, grenzen, mitte, stift):
    # Zwischen zwei Wandpaaren muss auf beiden Seiten derselbe ebene Absatz liegen.
    haelfte = len(baender)//2
    paare = list(zip(baender[:haelfte],baender[haelfte:][::-1],strict=True))
    waende = []
    for oben, unten in paare:
        o,u = oben.mean()-.5, unten.mean()-.5
        obenbreite, untenbreite = oben[1]-oben[0], unten[1]-unten[0]
        breite = max(obenbreite,untenbreite)
        if abs((o+u)/2-mitte) > 1 or abs(obenbreite-untenbreite) > 2:
            return ()
        bild = [tinte[lo:hi].any(axis=0) for lo,hi in (oben,unten)]
        pixel = np.flatnonzero(rest[slice(*oben)].any(axis=0) | rest[slice(*unten)].any(axis=0))
        waende.append((u-o,breite,bild,pixel))
        rest[slice(*oben)] = False
        rest[slice(*unten)] = False
    if rest[:baender[0,0]].any() or rest[baender[-1,1]:].any():
        return ()
    stufen = []
    for i, (dm,breite,bild,pixel) in enumerate(waende):
        innen = waende[i+1][0] if i+1 < len(waende) else 0.
        if (dm-innen)/2 <= (breite+stift)/2+1:
            return ()
        o,u = paare[i]
        if innen:
            o2,u2 = paare[i+1]
            flanken = [(o[1],o2[0]),(u2[1],u[0])]
        else:
            flanken = [(o[1],u[0])]
        rand = np.vstack([rest[lo:hi] for lo,hi in flanken])
        laeufe = tintenlaeufe(bild[0][pixel[0]:pixel[-1]+1])
        pausen = laeufe[1:,0]-laeufe[:-1,1]
        luecke = np.median(pausen) if len(pausen) >= 2 else None
        lagen = []
        for x in _bodenlagen(rand,grenzen,breite):
            spalte = tinte[:,round(x-stift/2):round(x+stift/2)+1].any(axis=1)
            if all(_absatzkante(spalte[lo-1:hi+1],breite,luecke) for lo,hi in flanken):
                lagen.append(x)
        if not innen and not rand.any():
            lagen.extend((grenzen[0],grenzen[-1]))
        stufen.append((dm,breite,bild,pixel,lagen))
    return stufen


def bohrspur(tinte, erlaubt, grenzen, mitte, radien, stift):
    rest = tinte & ~erlaubt
    if not rest.any():
        return 0., 0.
    baender = tintenlaeufe(rest.sum(axis=1) > 2*(stift+2))
    if len(baender) < 2:
        baender = tintenlaeufe(rest.any(axis=1))
    if not len(baender) or len(baender)%2:
        return None
    stufen = _stufenspuren(tinte,rest,baender,grenzen,mitte,stift)
    if not stufen:
        return None
    treffer = []
    for rechts, eintritt in ((False,grenzen[0]),(True,grenzen[-1])):
        profil = []
        start = eintritt
        for dm,breite,bild,pixel,lagen in stufen:
            passend = []
            rand = max(stift,breite)/2+1
            for x in lagen:
                a,b = sorted((x,start))
                weg = start-x if rechts else x-start
                if weg <= 2*rand or pixel[0] < a-rand or pixel[-1] > b+rand:
                    continue
                beruehrt = [r for l,h,r in zip(grenzen[:-1],grenzen[1:],radien,strict=True) if l < b and a < h]
                if not beruehrt or min(beruehrt)-dm/2 <= (stift+breite)/2+1:
                    continue
                l,h = int(np.floor(a+rand))+1, int(np.ceil(b-rand))
                if all(_wand_durchgehend(w[l:h],breite) for w in bild):
                    passend.append(x)
            if len(passend) != 1:
                break
            start, = passend
            tiefe = None if start in (grenzen[0],grenzen[-1]) else abs(start-eintritt)
            profil.append((dm,tiefe))
        if len(profil) == len(stufen):
            treffer.append(Stufenbohrspur(tuple(profil),rechts))
    breite = max(s[1] for s in stufen)
    if len(stufen) == 1 and treffer:
        dm,tiefe = treffer[0].stufen[0]
        if all(p.stufen == ((dm,None),) for p in treffer):
            return dm, breite
        if len(treffer) == 1:
            return Sacklochspur(dm,tiefe,treffer[0].von_rechts), breite
    return (treffer[0],breite) if len(treffer) == 1 else None


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
