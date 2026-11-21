"""Parallel projizierte Bohrungsraender mit ihren dreidimensionalen Modelllagen vergleichen."""

import math

import numpy as np
from scipy.spatial import cKDTree


def schraegbild(kreise):
    if not all(k.kurz for k in kreise):
        return None
    radien = np.array([k.r for k in kreise])
    kurz = np.array([k.kurz for k in kreise])
    winkel = np.deg2rad([k.winkel for k in kreise])
    q = (radien @ kurz)/(radien @ radien)
    phi = np.angle(np.sum((radien-kurz)**2*np.exp(2j*winkel)))/2
    if max(abs(kurz-q*radien)) > .5 or max((radien-kurz)*abs(np.sin(winkel-phi))) > .5:
        return None
    ort = np.array([complex(k.x,k.y) for k in kreise])*np.exp(-1j*phi)
    return ort-ort.mean(),radien,q


def _projektion(xy, z, f, ursprung, q, neigung):
    p = f*xy
    return ursprung+p.real+1j*(q*p.imag+abs(f)*neigung*z)


def _nachpassen(xy, z, blatt, q, neigung, faktor):
    # Massstab und Drehung fuer die aufgrund der beiden Anker vorgeschlagenen Paare verfeinern.
    ort = blatt.mean()
    x,y = xy.real-xy.real.mean(),xy.imag-xy.imag.mean()
    zmittel = z.mean()
    z = z-zmittel
    for _ in range(4):
        f = faktor/abs(faktor)
        m = np.vstack((np.column_stack((x,-y)),np.column_stack((q*y+neigung*f.real*z,q*x+neigung*f.imag*z))))
        rest = blatt-_projektion(x+1j*y,z,faktor,ort,q,neigung)
        delta = np.linalg.lstsq(m,np.r_[rest.real,rest.imag],rcond=None)[0]
        faktor += complex(*delta)
        if abs(faktor) < 1e-12:
            return None
        if np.linalg.norm(delta) < 1e-9*abs(faktor):
            break
    ursprung = ort-_projektion(xy.mean(),zmittel,faktor,0.,q,neigung)
    return faktor,ursprung


def _massstaebe(delta, abstand, versatz, minimum, maximum):
    # Fuer t=1/Massstab gilt |t*delta-i*versatz| = Abstand der beiden Modellachsen.
    norm = abs(delta)**2
    diskr = norm*abstand**2-(delta.real*versatz)**2
    wurzel = np.sqrt(np.maximum(diskr,0))
    basis = delta.imag*versatz
    for zaehler in (basis+wurzel,basis-wurzel):
        t = zaehler/norm
        gut = (t > 0) & (t*minimum <= 1) & (t*maximum >= 1) & (abstand > 1e-8)
        ids = np.flatnonzero(gut)
        if len(ids):
            yield ids,1/t[ids]


def _kandidaten(plan, z, r, blatt, radien, q, neigung, i, js, skalen, delta, dz, a, pruefe):
    # Mehrere Lagen gemeinsam pruefen; der Speicher bleibt auch fuer grosse Modelle begrenzt.
    block = max(1,32768//len(plan))
    for start in range(0,len(js),block):
        pruefe()
        jj = js[start:start+block]
        f = (delta-1j*skalen[start:start+block]*dz[jj])/(plan[jj]-plan[i])
        skala = abs(f)
        gut = np.flatnonzero(skala > 1e-12)
        ort = _projektion(plan[None,:]-plan[i],z[None,:]-z[i],f[:,None],blatt[a],q,neigung)
        radius = skala[:,None]*r
        zuordnung = np.empty((len(f),len(blatt)),dtype=int)
        for k,(punkt,rad) in enumerate(zip(blatt,radien,strict=True)):
            if not len(gut):
                break
            dist = abs(ort[gut]-punkt)**2+(radius[gut]-rad)**2
            nah = dist.argmin(axis=1)
            zuordnung[gut,k] = nah
            gut = gut[dist[np.arange(len(gut)),nah] <= 36.]
        for g in gut:
            ids = zuordnung[g]
            if len(set(ids)) == len(ids):
                yield f[g],ids


def _passung(xy, z, r, blatt, radien, q, neigung, faktor, ids, versucht):
    schluessel = tuple(ids)
    if schluessel in versucht:
        return None
    versucht.add(schluessel)
    if len(versucht)*len(ids) > 65536:
        versucht.clear()
    punkte = xy[ids]
    abstand = punkte-punkte.mean()
    streuung = np.linalg.svd(np.column_stack((abstand.real,abstand.imag)),compute_uv=False)
    if streuung[1]*abs(faktor) < max(2.,.01*streuung[0]*abs(faktor)):
        return None
    tiefen = z[ids]
    fit = _nachpassen(punkte,tiefen,blatt,q,neigung,faktor)
    if fit is None:
        return None
    f,u = fit
    ort = _projektion(xy,z,f,u,q,neigung)
    baum = cKDTree(np.column_stack((ort.real,ort.imag,r*abs(f))))
    ziele = np.column_stack((blatt.real,blatt.imag,radien))
    nachbarn = baum.query_ball_point(ziele,.85)
    if any(i not in treffer for i,treffer in zip(ids,nachbarn,strict=True)):
        return None
    return nachbarn


def schraegpassungen(gruppe, bild, pruefe):
    # Die groesste Trennung entlang der grossen Halbachse kann nicht allein aus der Tiefe stammen.
    blatt,radien,q = bild
    a,b = np.argmin(blatt.real),np.argmax(blatt.real)
    delta = blatt[b]-blatt[a]
    if delta.real < 3:
        return
    delta = complex(delta.real,delta.imag/q)
    raender = [(complex(k.x,k.y),z,k.r,wand) for k in gruppe for z,wand in k.raender]
    if len(raender) < len(blatt):
        return
    xy,z,r,waende = zip(*raender,strict=True)
    xy,z,r = np.asarray(xy),np.asarray(z),np.asarray(r)
    sinus = math.sqrt(1-q*q)
    for neigung in (sinus,-sinus):
        for plan in (xy,xy.conj()):
            versucht = set()
            for i in range(len(r)):
                pruefe()
                minimum = np.maximum((radien[a]-.85)/r[i],(radien[b]-.85)/r)
                maximum = np.minimum((radien[a]+.85)/r[i],(radien[b]+.85)/r)
                dz = (z-z[i])*neigung/q
                for js,skalen in _massstaebe(delta,abs(plan-plan[i]),dz,minimum,maximum):
                    for f,ids in _kandidaten(plan,z,r,blatt,radien,q,neigung,i,js,skalen,delta,dz,a,pruefe):
                        nachbarn = _passung(plan,z,r,blatt,radien,q,neigung,f,ids,versucht)
                        if nachbarn is not None:
                            paare = []
                            for n,treffer in enumerate(nachbarn):
                                wand = {waende[k] for k in treffer}
                                paare.append((n,wand.pop() if len(wand) == 1 else frozenset()))
                            yield (len(blatt),len(blatt)),paare
