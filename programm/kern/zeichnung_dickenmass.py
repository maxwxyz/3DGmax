"""Wiederholte lineare Masse zwischen Pfeil und Nullkreis im projizierten PDF."""

import numpy as np
from scipy.spatial import cKDTree

from .pmi_strichschrift import _gruppen
from .schriftstreifen import Schriftstreifen
from .zeichnungsabgleich import Blattangabe, wiederholtes_linearmass
from .zeichnungsansicht import _sichtbar


def _masslinien(linien, quer, entlang, laenge, pfeilhoehe, tinte):
    """Beide Hilfslinien schneiden die Massachse, beide Schaefte laufen nach aussen."""
    for niveau, sinn in ((0., -1), (laenge, 1)):
        hilfslinien = ((np.ptp(entlang, axis=1) < .65) & (abs(entlang.mean(1)-niveau) < .65)
                       & (quer.min(1) <= .65) & (quer.max(1) >= -.65) & (np.ptp(quer, axis=1) > .6*laenge))
        anschluss = abs(entlang-niveau).min(1) < .75
        if niveau == 0:
            anschluss |= abs(entlang+pfeilhoehe).min(1) < .75
        schaefte = anschluss & (abs(quer).max(1) < .8) & (((entlang-niveau)*sinn).max(1) > .25*laenge)
        if not all(any(_sichtbar(tinte, np.linspace(*linie, 11)) for linie in linien[auswahl])
                   for auswahl in (hilfslinien, schaefte)):
            return False
    return True


def _auf_ring(punkte, ring):
    phi = np.deg2rad(ring.winkel)
    u = np.array([np.cos(phi), np.sin(phi)])
    v = np.array([-u[1], u[0]])
    kurz = ring.kurz or ring.r
    delta = punkte - ring.mitte
    radius = np.hypot((delta @ u)/ring.r, (delta @ v)/kurz)
    return np.all(abs(radius-1)*kurz <= .85)


def _schriftfeld(streifen, abstand, aufloesung, ring):
    from .zeichnungsblatt import _zeile
    from .zeichnung_musterzeile import _masswort

    # In der Mitte liegt der Masswert. Hilfslinien und Endmarken koennen den Rand schneiden.
    m = streifen._maske(np.array([-7., .08, 7., .92])*abstand, aufloesung/abstand, 185)
    mitte = m.shape[1]//2
    baender = [b for b in _gruppen(m[:, mitte-aufloesung//2:mitte+aufloesung//2].T)
               if b[0] < len(m)/2 < b[1]]
    if len(baender) != 1:
        return None
    t,b = baender[0]
    if t <= 1 or b >= len(m)-1:
        return None
    zeile = m[t:b]
    # Zusammenhaengende Schrift beidseits des Massschafts verfolgen.
    gruppen = []
    for l,r in _gruppen(zeile):
        if gruppen and l-gruppen[-1][1] <= .85*(b-t):
            gruppen[-1][1] = r
        else:
            gruppen.append([l,r])
    for l,r in gruppen:
        if not 1 < l < mitte < r < m.shape[1]-1:
            continue
        # Tinte neben der Zeile darf nur zum bereits vermessenen Nullkreis gehoeren.
        ys,xs = np.nonzero(m[:,l:r])
        aussen = (ys < t) | (ys >= b)
        uv = (np.column_stack((xs[aussen]+l+.5,ys[aussen]+.5))/aufloesung+[-7,.08])*abstand
        if not _auf_ring(streifen.ort + uv @ streifen.achsen, ring):
            continue
        glyphen = zeile[:,l:r]
        funde = []
        for drehen, feld in enumerate((glyphen, glyphen[::-1,::-1])):
            lesungen = {_zeile(feld), _masswort(feld, linear=True)} - {""}
            if len(lesungen) == 1 and wiederholtes_linearmass(wort := lesungen.pop()):
                fenster = (np.array([l,t,r,b])/aufloesung + [-7,.08,-7,.08])*abstand
                ecken = streifen.blattecken(fenster)
                if ecken:
                    funde.append((wort, ecken[2:]+ecken[:2] if drehen else ecken))
        return funde[0] if len(funde) == 1 else None
    return None


def _pfeilachsen(dreiecke):
    """Spitze, Hoehe und projizierte Achsen der schlanken, gefuellten Dreiecke."""
    for dreieck in dreiecke:
        kanten = np.roll(dreieck,-1,axis=0)-dreieck
        laengen = np.linalg.norm(kanten,axis=1)
        i = int(np.argmin(laengen))
        if laengen[i] <= 1 or laengen.max() >= 48 or laengen[i] >= .65*laengen.max():
            continue
        spitze = dreieck[(i+2)%3]
        richtung = spitze - (dreieck[i]+dreieck[(i+1)%3])/2
        hoehe = np.linalg.norm(richtung)
        if hoehe <= 2:
            continue
        achse = richtung/hoehe
        quer = kanten[i]/laengen[i]
        det = quer[0]*achse[1]-quer[1]*achse[0]
        if abs(det) < .45:
            continue
        quer = quer if det > 0 else -quer
        yield spitze, hoehe, achse, quer


def wiederholte_masse(blatt):
    from .zeichnungsblatt import _box

    _, linien, dreiecke, ringe = blatt.massgeometrie
    if not ringe or not len(linien):
        return
    baum = cKDTree([r.mitte for r in ringe])
    tinte = blatt.bild.min(2) < 230
    richtungen = linien[:,1]-linien[:,0]
    laengen_l = np.linalg.norm(richtungen,axis=1)
    einheiten = richtungen / laengen_l[:,None]
    funde = {}
    for spitze, hoehe, achse, quer in _pfeilachsen(dreiecke):
        for j in baum.query_ball_point(spitze, min(240,14*hoehe)):
            delta = np.asarray(ringe[j].mitte) - spitze
            abstand = delta @ achse
            if (abstand < 1.6*hoehe or np.linalg.norm(delta-abstand*achse) > 1.
                    or not .035*abstand < ringe[j].r < .36*abstand):
                continue
            # Die Mitte der Endmarke ist genauer als die kurze Basis des gedruckten Pfeils.
            abstand = np.linalg.norm(delta)
            lage = spitze-linien[:,0]
            entlang = np.sum(lage*einheiten,axis=1)
            querabstand = abs(lage[:,0]*einheiten[:,1]-lage[:,1]*einheiten[:,0])
            treffer = np.flatnonzero((querabstand < .65) & (entlang >= -.65) & (entlang <= laengen_l+.65)
                                      & (laengen_l > .6*abstand) & (abs(einheiten @ quer) > .996))
            if len(treffer) != 1:
                continue
            x = einheiten[treffer[0]]
            streifen = Schriftstreifen(blatt, spitze, x*np.sign(x @ quer), delta/abstand)
            lokal = (linien-spitze) @ streifen.basis.T
            if not _masslinien(linien,lokal[:,:,0],lokal[:,:,1],abstand,hoehe,tinte):
                continue
            a = _schriftfeld(streifen,abstand,140,ringe[j])
            if not a or not a[1]:
                continue
            b = _schriftfeld(streifen,abstand,180,ringe[j])
            if b and b[0] == a[0]:
                wort,ecken = a
                box = _box(ecken)
                funde[box] = Blattangabe(blatt.nummer,box,wort,zeilenecken=ecken)
    yield from funde.values()
