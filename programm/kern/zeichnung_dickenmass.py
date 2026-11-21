"""Projizierte lineare Masse zwischen Pfeil und Nullkreis oder zwei Gegenpfeilen im PDF."""

import numpy as np
from scipy.spatial import cKDTree

from .pmi_ableiten import LINEARMASS
from .pmi_strichschrift import _gruppen, _lineare_masszahl, _masszeile
from .schriftstreifen import Schriftstreifen
from .zeichnungsabgleich import Blattangabe, wiederholtes_linearmass
from .zeichnungsansicht import _sichtbar


def _masslinien(linien, quer, entlang, laenge, pfeilhoehen, tinte):
    """Beide Hilfslinien schneiden die Massachse, beide Schaefte laufen nach aussen."""
    hilfen = []
    for niveau, sinn, hoehe in ((0., -1, pfeilhoehen[0]), (laenge, 1, pfeilhoehen[1])):
        hilfslinien = ((np.ptp(entlang, axis=1) < .65) & (abs(entlang.mean(1)-niveau) < .65)
                       & (quer.min(1) <= .65) & (quer.max(1) >= -.65) & (np.ptp(quer, axis=1) > .6*laenge))
        anschluss = abs(entlang-niveau).min(1) < .75
        anschluss |= abs(entlang-(niveau+sinn*hoehe)).min(1) < .75
        schaefte = anschluss & (abs(quer).max(1) < .8) & (((entlang-niveau)*sinn).max(1) > .25*laenge)
        sichtbar = [linie for linie in linien[hilfslinien] if _sichtbar(tinte, np.linspace(*linie, 11))]
        if len(sichtbar) != 1 or not any(_sichtbar(tinte, np.linspace(*linie, 11)) for linie in linien[schaefte]):
            return None
        hilfen.append(sichtbar[0])
    return hilfen


def _auf_ring(punkte, ring):
    phi = np.deg2rad(ring.winkel)
    u = np.array([np.cos(phi), np.sin(phi)])
    v = np.array([-u[1], u[0]])
    kurz = ring.kurz or ring.r
    delta = punkte - ring.mitte
    radius = np.hypot((delta @ u)/ring.r, (delta @ v)/kurz)
    return np.all(abs(radius-1)*kurz <= .85)


def _linke_klammer(feld):
    ys = np.flatnonzero(feld.any(1))
    feld = feld[ys[0]:ys[-1]+1]
    h,w = feld.shape
    if h < 14 or not .12 < w/h < .36 or not feld.any(1).all():
        return False
    links = np.argmax(feld,axis=1)
    rechts = w-1-np.argmax(feld[:,::-1],axis=1)
    if not np.array_equal(rechts-links+1, feld.sum(1)):
        return False
    # Beide Spitzen laufen nach innen, der durchgehende Bogen ist in der Mitte flacher.
    mitte = (links+rechts+1)/(2*w)
    a,b,c,d,e,f,g = (teil.mean() for teil in np.array_split(mitte,7))
    return (min(a,g)-d > .37 and abs(a-g) < .17 and max(c,e)-d < .13
            and a-b > b-c > .04 and g-f > f-e > .04)


def _linearwort(feld):
    from .zeichnung_musterzeile import _masswort
    from .zeichnungsblatt import _zeile

    spalten = _gruppen(feld)
    if not spalten:
        return ""
    links,rechts = (feld[:,l:r] for l,r in (spalten[0],spalten[-1]))
    geklammert = _linke_klammer(links)
    if geklammert != _linke_klammer(rechts[:,::-1]):
        return ""
    lesungen = {_masszeile(feld), _zeile(feld)} - {""}
    if geklammert:
        if len(spalten) < 3:
            return ""
        feld = feld[:,spalten[1][0]:spalten[-2][1]]
    ys = np.flatnonzero(feld.any(axis=1))
    feld = feld[ys[0]:ys[-1]+1]
    for zahl in (_masswort(feld, linear=True), _zeile(feld)):
        if LINEARMASS.fullmatch(zahl):
            lesungen.add("("+zahl+")" if geklammert else zahl)
    if len(lesungen) != 1:
        return ""
    wort = lesungen.pop()
    zahl = wort[1:-1] if geklammert and wort.startswith("(") and wort.endswith(")") else wort
    if len(_gruppen(feld)) != len(zahl) or not _lineare_masszahl(feld, zahl):
        return ""
    # Zwei entgegengesetzte Lesarten ohne unterscheidbare Grundlinie offenlassen.
    if all(z in "01689" for z in zahl) and zahl != zahl[::-1].translate(str.maketrans("69","96")):
        return ""
    return wort


def _zeilenbreite(zeile, mitte):
    gruppen = []
    for l,r in _gruppen(zeile):
        if gruppen and l-gruppen[-1][1] <= .85*len(zeile):
            gruppen[-1][1] = r
        else:
            gruppen.append([l,r])
    return next(((l,r) for l,r in gruppen if 1 < l < mitte < r < zeile.shape[1]-1), None)


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
    umfang = _zeilenbreite(m[t:b], mitte)
    if umfang is None:
        return None
    l,r = umfang
    if ring is None:
        # Klammern reichen ober- und unterhalb der Ziffern. Getrennte Zusatzzeilen offenlassen.
        baender = _gruppen(m[:,l:r].T)
        if len(baender) != 1:
            return None
        t,b = baender[0]
        if t < 1 or b >= len(m)-1 or _zeilenbreite(m[t:b], mitte) != umfang:
            return None
        # Hochgestellte Angaben koennen neben der letzten Klammer ausserhalb der Grundzeile liegen.
        rand = int(np.ceil(.85*(b-t)))
        if m[:,max(0,l-rand):l].any() or m[:,r:r+rand].any():
            return None
    # Tinte neben der Zeile darf nur zum bereits vermessenen Nullkreis gehoeren.
    ys,xs = np.nonzero(m[:,l:r])
    aussen = (ys < t) | (ys >= b)
    uv = (np.column_stack((xs[aussen]+l+.5,ys[aussen]+.5))/aufloesung+[-7,.08])*abstand
    if len(uv) and (ring is None or not _auf_ring(streifen.ort + uv @ streifen.achsen, ring)):
        return None
    glyphen = m[t:b,l:r]
    funde = []
    for drehen, feld in enumerate((glyphen, glyphen[::-1,::-1])):
        if ring is None:
            wort = _linearwort(feld)
        else:
            lesungen = {_zeile(feld), _masswort(feld, linear=True)} - {""}
            wort = lesungen.pop() if len(lesungen) == 1 else ""
            if not wiederholtes_linearmass(wort):
                continue
        if wort:
            fenster = (np.array([l,t,r,b])/aufloesung + [-7,.08,-7,.08])*abstand
            ecken = streifen.blattecken(fenster)
            if ecken:
                funde.append((wort, ecken[2:]+ecken[:2] if drehen else ecken))
    return funde[0] if len({wort for wort,_ in funde}) == 1 else None


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


def _endpaare(pfeile, ringe):
    """Zweite Endmarke auf der Achse des ersten Pfeils suchen."""
    spitzen = cKDTree([p[0] for p in pfeile])
    kreise = cKDTree([r.mitte for r in ringe]) if ringe else None
    for i, pfeil in enumerate(pfeile):
        spitze, hoehe, achse, quer = pfeil
        reichweite = min(240, 14*hoehe)
        if kreise is not None:
            for j in kreise.query_ball_point(spitze, reichweite):
                ring = ringe[j]
                delta = np.asarray(ring.mitte) - spitze
                abstand = delta @ achse
                if (abstand >= 1.6*hoehe and np.linalg.norm(delta-abstand*achse) <= 1.
                        and .035*abstand < ring.r < .36*abstand):
                    yield pfeil, delta, 0., ring
        for j in spitzen.query_ball_point(spitze, reichweite):
            if j <= i:
                continue
            ende, gegenhoehe, gegenachse, gegenquer = pfeile[j]
            delta = ende-spitze
            if (delta @ achse >= 1.6*max(hoehe,gegenhoehe) and -delta @ gegenachse > 0
                    and abs(quer @ gegenquer) > .996
                    and np.linalg.norm(delta-(delta @ achse)*achse) <= 1.
                    and np.linalg.norm(delta-(delta @ gegenachse)*gegenachse) <= 1.):
                yield pfeil, delta, gegenhoehe, None


def projizierte_linearmasse(blatt):
    from .zeichnungsblatt import _box

    _, linien, dreiecke, ringe = blatt.massgeometrie
    if not len(linien):
        return
    # Nur Pfeilspitzen mit einer anschliessenden Linie als Paarungskandidaten verwenden.
    enden = cKDTree(linien.reshape(-1,2))
    pfeile = [p for p in _pfeilachsen(dreiecke) if
              min(enden.query([p[0], p[0]-p[1]*p[2]], distance_upper_bound=1.2)[0]) <= 1.2]
    if not pfeile:
        return
    tinte = blatt.bild.min(2) < 230
    richtungen = linien[:,1]-linien[:,0]
    laengen = np.linalg.norm(richtungen,axis=1)
    einheiten = richtungen / laengen[:,None]
    funde = {}
    for (spitze, hoehe, _, quer), delta, gegenhoehe, ring in _endpaare(pfeile, ringe):
        abstand = np.linalg.norm(delta)
        lage = spitze-linien[:,0]
        entlang = np.sum(lage*einheiten,axis=1)
        querabstand = abs(lage[:,0]*einheiten[:,1]-lage[:,1]*einheiten[:,0])
        treffer = np.flatnonzero((querabstand < .65) & (entlang >= -.65) & (entlang <= laengen+.65)
                                 & (laengen > .6*abstand) & (abs(einheiten @ quer) > .996))
        if len(treffer) != 1:
            continue
        x = einheiten[treffer[0]]
        streifen = Schriftstreifen(blatt, spitze, x*np.sign(x @ quer), delta/abstand)
        lokal = (linien-spitze) @ streifen.basis.T
        hilfen = _masslinien(linien,lokal[:,:,0],lokal[:,:,1],abstand,(hoehe,gegenhoehe),tinte)
        if not hilfen:
            continue
        a = _schriftfeld(streifen,abstand,140,ring)
        if not a:
            continue
        b = _schriftfeld(streifen,abstand,180,ring)
        if b and b[0] == a[0]:
            wort,ecken = a
            box = _box(ecken)
            segmente = tuple(tuple((x,y) for x,y in linie/streifen.blattpixel) for linie in hilfen)
            funde[box] = Blattangabe(blatt.nummer,box,wort,zeilenecken=ecken,hilfslinien=segmente)
    yield from funde.values()
