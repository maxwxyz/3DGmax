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
    spitzenhoehe: float = 0.


@dataclass(frozen=True)
class Gegenbohrungen:
    links: tuple
    rechts: tuple
    kern: object = None  # Durchmesser der gemeinsamen Kernbohrung

    spitzen: tuple = (None, None)  # Im Bild Kegelhoehen, beim Export gepruefte Bohrspitzen

    @property
    def stufen(self):
        return self.links+self.rechts+(((self.kern,None),) if self.kern is not None else ())


def bohrdurchmesser_am_absatz(spur, x, grenzen):
    if isinstance(spur,Gegenbohrungen):
        a = bohrdurchmesser_am_absatz(Stufenbohrspur(spur.links,False,spur.spitzen[0] or 0.),x,grenzen)
        b = bohrdurchmesser_am_absatz(Stufenbohrspur(spur.rechts,True,spur.spitzen[1] or 0.),x,grenzen)
        return max(a[0],b[0],spur.kern or 0.),max(a[1],b[1],spur.kern or 0.)
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
            if isinstance(spur,Stufenbohrspur) and i+1 == len(stufen) and spur.spitzenhoehe:
                return dm, dm
            return dm, stufen[i+1][0] if i+1 < len(stufen) else 0.
    if isinstance(spur,Stufenbohrspur) and spur.spitzenhoehe:
        dm,tiefe = stufen[-1]
        innen = dm*max(0.,1.-(lage-tiefe)/spur.spitzenhoehe)
        return innen,innen
    return 0., 0.


def _strichluecke(spur, breite):
    laeufe = tintenlaeufe(spur)
    pausen = laeufe[1:,0]-laeufe[:-1,1]
    if len(pausen) >= 2:
        luecke = np.median(pausen)
        if luecke <= 8*breite:
            return luecke
    return None


def _absatzkante(spur, breite, luecke):
    if _wand_durchgehend(spur,breite):
        return True
    # Kurze Schultern enthalten oft nur eine Luecke des Strichmusters der Wand.
    laeufe = tintenlaeufe(spur)
    if luecke is None or len(laeufe) != 2 or spur.mean() < .35:
        return False
    pause = laeufe[1,0]-laeufe[0,1]
    return abs(pause-luecke) <= max(1,.2*luecke) and max(laeufe[0,0],len(spur)-laeufe[-1,1]) <= luecke+1


def _geteilter_grund(spalte, oben, unten, achse, breite, luecke):
    # Zwei zum Zentrum gezeichnete Halbkanten koennen dort in einer Strichpause enden.
    if luecke is None:
        return False
    for halb in (spalte[oben-1:achse+1],spalte[achse:unten+1][::-1]):
        laeufe = tintenlaeufe(halb)
        if len(laeufe) < 2 or len(halb)-laeufe[-1,1] > luecke+breite/2+1:
            return False
        if not _absatzkante(halb[:laeufe[-1,1]],breite,luecke):
            return False
    return True


def _stufenspuren(tinte, rest, baender, grenzen, mitte, stift, spitze):
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
    luecke = None
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
        luecke = _strichluecke(bild[0][pixel[0]:pixel[-1]+1],breite) or luecke
        if not innen and spitze is not None:
            kern,ende,_ = spitze
            if abs(dm-kern) > 1 or rand.any():
                return ()
            stufen.append((dm,breite,bild,pixel,[ende]))
            continue
        lagen = []
        for x in _bodenlagen(rand,grenzen,breite):
            spalte = tinte[:,round(x-stift/2):round(x+stift/2)+1].any(axis=1)
            belegt = all(_absatzkante(spalte[lo-1:hi+1],breite,luecke) for lo,hi in flanken)
            if not belegt and not innen:
                belegt = _geteilter_grund(spalte,o[1],u[0],round(mitte),breite,luecke)
            if belegt:
                lagen.append(x)
        if not innen and not rand.any():
            lagen.extend((grenzen[0],grenzen[-1]))
        stufen.append((dm,breite,bild,pixel,lagen))
    return stufen


def _zylinderspur(tinte, rest, grenzen, mitte, radien, stift, spitze=None):
    baender = tintenlaeufe(rest.sum(axis=1) > 2*(stift+2))
    if len(baender) < 2:
        baender = tintenlaeufe(rest.any(axis=1))
    if not len(baender) or len(baender)%2:
        return None
    stufen = _stufenspuren(tinte,rest,baender,grenzen,mitte,stift,spitze)
    if not stufen:
        return None
    treffer = []
    for rechts, eintritt in ((False,grenzen[0]),(True,grenzen[-1])):
        if spitze is not None and (spitze[2] < spitze[1]) != rechts:
            continue
        profil = []
        luecke = None
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
                if all(_absatzkante(w[l:h],breite,luecke) for w in bild):
                    passend.append(x)
            if len(passend) != 1:
                break
            ziel, = passend
            a,b = sorted((round(start),round(ziel)))
            luecke = _strichluecke(bild[0][a:b+1],breite) or luecke
            start = ziel
            tiefe = None if start in (grenzen[0],grenzen[-1]) else abs(start-eintritt)
            profil.append((dm,tiefe))
        if len(profil) == len(stufen):
            treffer.append(Stufenbohrspur(tuple(profil),rechts,abs(spitze[2]-spitze[1]) if spitze else 0.))
    breite = max(s[1] for s in stufen)
    if len(stufen) == 1 and treffer and spitze is None:
        dm,tiefe = treffer[0].stufen[0]
        if all(p.stufen == ((dm,None),) for p in treffer):
            return dm, breite
        if len(treffer) == 1:
            return Sacklochspur(dm,tiefe,treffer[0].von_rechts), breite
    return (treffer[0],breite) if len(treffer) == 1 else None


def _flanke(zentren, abstand, radius, breite):
    # Mitten der gedruckten Striche zwischen Zylinderwand und Achse.
    maske = np.isfinite(zentren) & (abstand > breite+1) & (abstand < radius-breite-1)
    y,x = abstand[maske],zentren[maske]
    if len(y) < 2 or np.ptp(y) < radius/2:
        return None
    steigung, scheitel = np.polyfit(y,x,1)
    if np.max(abs(x-scheitel-y*steigung)) > 1+breite*np.hypot(1,steigung)/2:
        return None
    return scheitel+steigung*radius, scheitel


def _kernbaender(belegung, mitte, stift):
    # Je Schwelle nur ein neues symmetrisches Wandpaar untersuchen.
    versucht = set()
    for schwelle in np.unique(belegung[belegung > 2*(stift+2)]):
        baender = tintenlaeufe(belegung >= schwelle)
        oben = baender[baender[:,1] < mitte]
        unten = baender[baender[:,0] > mitte]
        if len(oben) and len(unten):
            o,u = oben[-1],unten[0]
            paar = (*o,*u)
            if paar not in versucht and abs((o.mean()+u.mean()-1)/2-mitte) <= 1:
                versucht.add(paar)
                yield o,u


def _spitzenlage(tinte, zentren, mitte, radius, breite, grenzen):
    abstand = np.arange(len(tinte))-mitte
    flanken = [_flanke(zentren,s*abstand,radius,breite) for s in (-1,1)]
    if any(f is None for f in flanken) or np.max(np.ptp(flanken,axis=0)) > 2:
        return None
    ende,scheitel = np.mean(flanken,axis=0)
    if abs(ende-scheitel) <= breite+2 or not grenzen[0] < min(ende,scheitel) < max(ende,scheitel) < grenzen[-1]:
        return None
    n = int(np.ceil(np.hypot(radius,ende-scheitel)))+1
    x = np.rint(np.linspace(ende,scheitel,n)).astype(int)
    for s in (-1,1):
        y = np.rint(np.linspace(mitte+s*radius,mitte,n)).astype(int)
        anfang = grenzen[-1] if scheitel < ende else grenzen[0]
        a,b = sorted((round(anfang),round(ende)))
        luecke = _strichluecke(tinte[round(mitte+s*radius),a:b+1],breite)
        if not _absatzkante(tinte[y,x],breite,luecke):
            return None
    return ende,scheitel


def _kegelspur(tinte, rest, grenzen, mitte, radien, stift):
    belegung = rest.sum(axis=1)
    links = np.argmax(rest,axis=1)
    rechts = rest.shape[1]-1-np.argmax(rest[:,::-1],axis=1)
    zentren = np.where(belegung,(links+rechts)/2,np.nan)
    for o,u in _kernbaender(belegung,mitte,stift):
        radius = (u.mean()-o.mean())/2
        breite = max(o[1]-o[0],u[1]-u[0])
        lage = _spitzenlage(tinte,zentren,mitte,radius,breite,grenzen)
        if lage is None:
            continue
        ende,scheitel = lage
        y,x = np.nonzero(rest)
        distanz = abs(y-mitte)
        steigung = (ende-scheitel)/radius
        soll = scheitel+steigung*distanz
        kegel = (distanz <= radius+breite/2+1) & (abs(x-soll) <= (breite/2+1)*np.hypot(1,steigung))
        bereinigt = rest.copy()
        bereinigt[y[kegel],x[kegel]] = False
        # Die zylindrischen Wandenden bleiben bis zum Ansatz erhalten.
        zylinder = slice(None,round(ende)+1) if scheitel > ende else slice(round(ende),None)
        for lo,hi in (o,u):
            bereinigt[lo:hi,zylinder] = rest[lo:hi,zylinder]
        spur = _zylinderspur(tinte,bereinigt,grenzen,mitte,radien,stift,(2*radius,ende,scheitel))
        if spur:
            return spur
    return None


def _teilprofil(tinte, rest, grenzen, mitte, radien, stift, rechts, im_steg):
    erg = _zylinderspur(tinte,rest.copy(),grenzen,mitte,radien,stift)
    if not erg and im_steg:
        erg = _kegelspur(tinte,rest,grenzen,mitte,radien,stift)
    if erg:
        spur,breite = erg
        if isinstance(spur,(Stufenbohrspur,Sacklochspur)) and spur.von_rechts == rechts:
            stufen = spur.stufen if isinstance(spur,Stufenbohrspur) else ((spur.durchmesser,spur.tiefe),)
            return stufen,breite,getattr(spur,"spitzenhoehe",0.) or None
    return None


def _gemeinsamer_kern(tinte, mitte, grenzen, links, rechts, breite):
    dm = links[-1][0]
    if abs(dm-rechts[-1][0]) > 1 or len(links) < 2 or len(rechts) < 2:
        return None
    a = int(np.ceil(grenzen[0]+links[-2][1]+breite/2+1))
    b = int(np.floor(grenzen[-1]-rechts[-2][1]-breite/2-1))
    for y in (mitte-dm/2,mitte+dm/2):
        lo,hi = int(np.ceil(y-breite/2)),int(np.floor(y+breite/2))+1
        if not _wand_durchgehend(tinte[lo:hi,a:b+1].any(axis=0),breite):
            return None
    return Gegenbohrungen(links[:-1],rechts[:-1],dm)


def _gegenspur(tinte, rest, grenzen, mitte, radien, stift):
    # Zwischen zwei Absatzen muss entweder ein durchgehender Zylinder oder ein Materialsteg liegen.
    waende = rest.sum(axis=1) > 2*(stift+2)
    from scipy.ndimage import minimum_filter1d
    laenge = int(np.ceil(2*(stift+2)))+1
    senkrecht = minimum_filter1d(rest,size=laenge,axis=0,mode="constant").any(axis=0)
    lagen = [*tintenlaeufe(rest[~waende].any(axis=0)),*tintenlaeufe(senkrecht)]
    stationen = sorted(set(grenzen) | {b.mean()-.5 for b in lagen if grenzen[0] < b.mean()-.5 < grenzen[-1]})
    # Ein zusammenhaengender Materialsteg trennt auch ungleich tiefe Spitzen eindeutig.
    stegmitten = set()
    schnitte = {round((a+b)/2) for a,b in zip(stationen,stationen[1:]) if b-a > 2*stift+4}
    for a,b in tintenlaeufe(~rest.any(axis=0)):
        if grenzen[0] < a < b < grenzen[-1] and b-a > 2*stift+4:
            schnitte.difference_update(range(a,b))
            stegmitten.add((a+b)//2)
    treffer = {}
    for schnitt in sorted(schnitte | stegmitten):
        im_steg = schnitt in stegmitten
        k = int(np.searchsorted(grenzen,schnitt))
        # Blattkoordinaten in beiden Teilbildern beibehalten bzw. um den Schnitt verschieben.
        l = _teilprofil(tinte[:,:schnitt+1],rest[:,:schnitt+1],[*grenzen[:k],schnitt],
                        mitte,radien[:k],stift,False,im_steg)
        if not l:
            continue
        r = _teilprofil(tinte[:,schnitt:],rest[:,schnitt:],[0,*[x-schnitt for x in grenzen[k:]]],
                        mitte,radien[k-1:],stift,True,im_steg)
        if not r:
            continue
        links,wl,sl = l
        rechts,wr,sr = r
        breite = max(wl,wr)
        if links[-1][1] is None and rechts[-1][1] is None:
            erg = _gemeinsamer_kern(tinte,mitte,grenzen,links,rechts,breite)
        elif links[-1][1] is not None and rechts[-1][1] is not None:
            erg = Gegenbohrungen(links,rechts,spitzen=(sl,sr))
        else:
            continue
        if erg:
            treffer[erg] = breite
    return next(iter(treffer.items())) if len(treffer) == 1 else None


def bohrspur(tinte, erlaubt, grenzen, mitte, radien, stift):
    rest = tinte & ~erlaubt
    if not rest.any():
        return 0., 0.
    return (_zylinderspur(tinte,rest.copy(),grenzen,mitte,radien,stift)
            or _kegelspur(tinte,rest,grenzen,mitte,radien,stift)
            or _gegenspur(tinte,rest,grenzen,mitte,radien,stift))


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
        toleranz = max(2.,np.median(strich[y,x])+1.)+np.sqrt(.5)
        if 2*toleranz >= min(np.diff(radien)) or toleranz >= radius/2:
            return ()
        strichbreiten.append(toleranz)
        erlaubt |= abs(rho-radius) <= toleranz
    erlaubt |= np.minimum(abs(dx),abs(dy)) <= min(strichbreiten)
    return tuple(2*radien) if erlaubt.all() else ()
