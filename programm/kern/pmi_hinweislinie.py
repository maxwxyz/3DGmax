"""Abgesetzten Zielbogen am radialen Masspfeil von der eigentlichen Schrift trennen."""

import numpy as np


def winkelbeschriftung(pfade, box, skala, labels, objekte):
    """Zwei lange, nicht parallele Hilfslinien mit je einem geschlossenen Pfeilkopf abtrennen."""
    if any(voll for _, voll in pfade) or not 4 <= len(objekte) <= 48:
        return []
    gruppen = {}
    for p, _ in pfade:
        x, y = np.rint((p[0] - [box[0], box[3]]) * [skala, -skala] + 2).astype(int)
        nr = labels[y, x]
        if nr == 0:
            return []
        gruppen.setdefault(nr, []).append(p)
    hoehen = sorted(y.stop - y.start for y, _ in objekte)
    zeichenhoehe = np.median(hoehen[:-2]) / skala
    achsen = []
    schrift = []
    for zuege in gruppen.values():
        schaefte = [p for p in zuege if len(p) == 2 and np.linalg.norm(p[1]-p[0]) > 4*zeichenhoehe]
        if len(schaefte) != 1:
            schrift.extend((p, False) for p in zuege)
            continue
        a, b = schaefte[0]
        koepfe = [p[:3] for p in zuege if len(p) == 4 and np.allclose(p[0], p[-1], rtol=0, atol=1e-6)]
        if len(koepfe) != 1 or not _an_strecke(koepfe[0], a, b, .05*zeichenhoehe).any():
            return []
        kopf = koepfe[0]
        seiten = np.linalg.norm(kopf - np.roll(kopf, 1, axis=0), axis=1)
        flaeche = abs(np.linalg.det(kopf[1:] - kopf[0])) / 2
        if min(seiten) < .08*zeichenhoehe or max(seiten) > 2.5*zeichenhoehe or flaeche < .03*max(seiten)**2:
            return []
        if any(np.linalg.norm(p - kopf.mean(axis=0), axis=1).max() > 3*zeichenhoehe
               for p in zuege if p is not schaefte[0]):
            return []
        achsen.append((b-a) / np.linalg.norm(b-a))
    return schrift if len(achsen) == 2 and abs(achsen[0] @ achsen[1]) < .985 else []


def _kreisbogen(punkte):
    punkte = np.unique(punkte, axis=0)
    if len(punkte) < 10:
        return None
    lokal = punkte - punkte.mean(axis=0)
    _, basis = np.linalg.eigh(lokal.T @ lokal)
    entlang = lokal @ basis[:, 1]
    sehne = np.ptp(entlang)
    if sehne <= 0 or np.ptp(lokal @ basis[:, 0]) > .25 * sehne:
        return None
    # Bei flaechiger Schrift liegen die Ecken auf beiden Seiten des Bogens.
    abschnitt = np.minimum(4, ((entlang - entlang.min()) * 5 / sehne).astype(int))
    if len(np.unique(abschnitt)) != 5:
        return None
    mitte = np.array([punkte[abschnitt == i].mean(axis=0) for i in range(5)])
    q = mitte - mitte.mean(axis=0)
    xy, _, rang, _ = np.linalg.lstsq(np.column_stack((2*q, np.ones(5))), (q*q).sum(axis=1), rcond=None)
    zentrum = mitte.mean(axis=0) + xy[:2]
    radien = np.linalg.norm(mitte - zentrum, axis=1)
    radius = radien.mean()
    if (rang < 3 or not .75*sehne < radius < 8*sehne or np.ptp(radien) > .006*sehne
            or np.max(np.abs(np.linalg.norm(punkte-zentrum, axis=1)-radius)) > .08*sehne):
        return None
    return zentrum, radius, sehne, mitte


def _radialpfeil(kanten, kreis, hoehe):
    zentrum, radius, sehne, bogen = kreis
    if not len(kanten):
        return False
    laengen = np.linalg.norm(kanten[:, 1] - kanten[:, 0], axis=1)
    schaft = kanten[laengen.argmax()]
    if laengen.max() < 3.5*hoehe:
        return False
    beine = kanten[(laengen > .18*hoehe) & (laengen < 1.8*hoehe)]
    for spitze, ende in (schaft, schaft[::-1]):
        achse = (ende-spitze) / np.linalg.norm(ende-spitze)
        quer = np.array([-achse[1], achse[0]])
        # Die Spitze liegt auf demselben Kreis, der Schaft auf seinem Radius.
        if (np.linalg.norm(bogen-spitze, axis=1).min() > 2.5*sehne
                or abs(np.linalg.norm(zentrum-spitze)-radius) > .06*sehne
                or abs((zentrum-spitze) @ quer) > .10*sehne):
            continue
        am_kopf = np.concatenate((beine, beine[:, ::-1]))
        am_kopf = am_kopf[np.linalg.norm(am_kopf[:, 0]-spitze, axis=1) < .04*hoehe]
        v = am_kopf[:, 1] - am_kopf[:, 0]
        vor = v @ achse
        v = v[vor > 0]
        neigung = (v @ quer) / vor[vor > 0]
        if np.any((neigung > .08) & (neigung < .5)) and np.any((neigung < -.08) & (neigung > -.5)):
            return True
    return False


def zielbogen(pfade, box, skala, labels, objekte, fuehrung, hoehe):
    """Index des isolierten Zielbogens, falls Bogen und zwei Pfeilflanken zusammenpassen."""
    kandidaten = []
    for i, (y, x) in enumerate(objekte):
        if i == fuehrung or max(y.stop-y.start, x.stop-x.start) > .65*hoehe:
            continue
        # Jeder Schriftzug neben dem Zeichen koennte fachlich dazugehoeren.
        if any(np.hypot(max(0, x.start-u.stop, u.start-x.stop), max(0, y.start-v.stop, v.start-y.stop))
               < 2.5*hoehe for j, (v, u) in enumerate(objekte) if j not in (i, fuehrung)):
            continue
        kandidaten.append(i)
    if len(kandidaten) != 1:
        return None
    i, = kandidaten
    y, x = objekte[i]
    # In Rasterkoordinaten gelten die gleichen Grenzen fuer Striche und Dreiecke.
    ursprung = np.array([box[0], box[3]])
    bogen, kanten = [], []
    for p, voll in pfade:
        bild = (p - ursprung) * [skala, -skala] + 2
        if (np.all((bild[:, 0] >= x.start-1) & (bild[:, 0] <= x.stop))
                and np.all((bild[:, 1] >= y.start-1) & (bild[:, 1] <= y.stop))):
            bogen.append(bild)
        if voll:
            bild = np.vstack((bild, bild[0]))
        kanten.append(np.stack((bild[:-1], bild[1:]), axis=1))
    kreis = _kreisbogen(np.vstack(bogen)) if bogen else None
    if kreis is None:
        return None
    kanten = np.concatenate(kanten)
    x, y = np.rint(kanten.mean(axis=1)).astype(int).T
    am_pfeil = np.logical_or.reduce([labels[y+dy, x+dx] == fuehrung+1
                                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    return i if _radialpfeil(kanten[am_pfeil], kreis, hoehe) else None


def _an_strecke(punkte, start, ende, toleranz):
    richtung = ende - start
    anteil = np.clip((punkte-start) @ richtung / (richtung @ richtung), 0, 1)
    return np.linalg.norm(punkte - (start + anteil[:, None]*richtung), axis=1) <= toleranz


def _punktradien(punkte, zentrum, radius):
    """In jedem Viertel des Endpunkts muss Tinte stehen, auch bei Schraffur."""
    lokal = punkte - zentrum
    radien = np.linalg.norm(lokal, axis=1)
    kern = lokal[radien < .75*radius]
    viertel = np.pi*(.75*radius)**2/4
    if any(np.sum((a*kern[:, 0] > 0) & (b*kern[:, 1] > 0)) < .30*viertel
           for a in (-1, 1) for b in (-1, 1)):
        return None
    return radien


def hat_rundmarke(rest, hoehe):
    """Einen runden Kopf neben dem Rahmen auch bei durchgehender Hinweislinie pruefen."""
    from scipy import ndimage
    if not rest.any():
        return False
    innen = np.pad(ndimage.binary_fill_holes(rest), 1)
    abstand = ndimage.distance_transform_edt(innen)
    cy, cx = np.unravel_index(abstand.argmax(), abstand.shape)
    radius = abstand[cy, cx]
    if not .045*hoehe < radius < .19*hoehe:
        return False
    # Um den Kopf darf nur der schmale Schaft ueber den Kreis hinausreichen.
    phi = np.arange(24) * (2*np.pi/24)
    richtung = np.column_stack((np.cos(phi), np.sin(phi)))
    x, y = np.rint([cx, cy] + 1.25*radius*richtung).astype(int).T
    im = (x >= 0) & (x < innen.shape[1]) & (y >= 0) & (y < innen.shape[0])
    return np.count_nonzero(innen[y[im], x[im]]) <= 4


def punkt_hinweislinie(rest, symbol, rand, *, rundes_ziel=False):
    """Eine zweigliedrige Hinweislinie vom Symbolfach zu einem Punkt oder einem Kreis am Ziel."""
    from scipy import ndimage
    y, x = np.nonzero(rest)
    links, oben, _, unten = symbol
    h = unten - oben
    if len(y) < 10 or not 0 < links-x.max() <= rand+2:
        return False
    # Zusatzzeichen, Verzweigungen und mehrere Ziele duerfen nicht verschwinden.
    ausschnitt = rest[y.min():y.max()+1, x.min():x.max()+1]
    if ndimage.label(ausschnitt, np.ones((3, 3)))[1] != 1:
        return False
    ende = y[x == x.max()]
    anschluss = np.array([x.max(), ende.mean()])
    breite = max(1.6, np.ptp(ende)+1)
    if abs(anschluss[1]-(oben+unten-1)/2) > max(2, .025*h) or breite > .08*h:
        return False
    innen = ndimage.binary_fill_holes(np.pad(ausschnitt, 1))
    abstand = ndimage.distance_transform_edt(innen)
    cy, cx = np.unravel_index(abstand.argmax(), abstand.shape)
    radius = abstand[cy, cx]
    if not .045*h < radius < .19*h:
        return False
    zentrum = np.array([cx+x.min()-1, cy+y.min()-1])
    punkte = np.column_stack((x, y))
    if rundes_ziel:
        # Ein Zielkreis sitzt am Ende der Linie. Ein Ring am Knick kann eine Rundumangabe sein.
        luft = ndimage.distance_transform_edt(~ausschnitt)
        phi = np.arange(24) * (2*np.pi/24)
        kreis = zentrum + (radius-.5)*np.column_stack((np.cos(phi), np.sin(phi)))
        k = np.rint(kreis - [x.min(), y.min()]).astype(int)
        if np.any(k < 0) or np.any(k >= ausschnitt.shape[::-1]) or luft[k[:, 1], k[:, 0]].max() > 2:
            return False
        # Der Schaft darf an der nahen Kreislinie oder erst im Mittelpunkt enden.
        radien = np.linalg.norm(punkte-zentrum, axis=1)
    else:
        radien = _punktradien(punkte, zentrum, radius)
        if radien is None:
            return False
    schaft = punkte[(radien > radius+breite+1.5) & (np.abs(y-anschluss[1]) > 2*breite)]
    if len(schaft) < 3 or np.linalg.norm(zentrum-anschluss) < 1.2*h:
        return False
    achsen = np.linalg.eigh((schaft-schaft.mean(axis=0)).T @ (schaft-schaft.mean(axis=0)))[1]
    achse = achsen[:, 1]
    if abs(achse[1]) < .2:
        return False
    knick = zentrum + achse*((anschluss[1]-zentrum[1])/achse[1])
    if not .05*h < anschluss[0]-knick[0] < 2*h:
        return False
    if np.linalg.norm(knick-zentrum) < radius:
        return False
    toleranz = breite + 1.5
    return bool(np.all((radien <= radius+1.5) | _an_strecke(punkte, zentrum, knick, toleranz)
                       | _an_strecke(punkte, knick, anschluss, toleranz)))


def doppelte_punktlinie(rest, symbol, rand):
    """Zwei belegte Zielpunkte an einem gemeinsamen, bis ans Rahmenfach reichenden Knick."""
    from scipy import ndimage
    y, x = np.nonzero(rest)
    l, oben, _, unten = symbol
    h = unten-oben
    mitte = (oben+unten-1)/2
    if not len(y) or ndimage.label(rest, np.ones((3, 3)))[1] != 1:
        return False
    # Am Anschluss muss genau ein kurzer waagerechter Schaft ankommen.
    anschluss = (abs(y-mitte) <= .04*h) & (abs(x-l) <= rand+2)
    if not anschluss.any():
        return False
    ende = np.array([x[anschluss].max(), y[anschluss].mean()])
    breite = max(1.5, np.ptp(y[anschluss])+1)
    band = abs(y-ende[1]) <= breite
    knick = np.array([x[band].min(), ende[1]])
    if not .05*h < ende[0]-knick[0] < 2*h:
        return False
    abstand = ndimage.distance_transform_edt(ndimage.binary_fill_holes(rest))
    marken, anzahl = ndimage.label(abstand > .045*h)
    if anzahl != 2:
        return False
    punkte = np.column_stack((x, y))
    gedeckt = _an_strecke(punkte, knick, ende, breite+1.5)
    luft = ndimage.distance_transform_edt(~rest)
    for i in (1, 2):
        cy, cx = ndimage.maximum_position(abstand, labels=marken, index=i)
        radius = abstand[cy, cx]
        zentrum = np.array([cx, cy])
        if radius >= .19*h or np.linalg.norm(zentrum-knick) <= h:
            return False
        radien = _punktradien(punkte, zentrum, radius)
        if radien is None:
            return False
        # Auch jeder erwartete Strahl muss vom Knick bis zum Punkt durchgehend gezeichnet sein.
        sx, sy = np.rint(np.linspace(knick, zentrum, int(np.linalg.norm(zentrum-knick))+1)).astype(int).T
        if luft[sy, sx].max() > breite+1.5:
            return False
        gedeckt |= (radien <= radius+1.5) | _an_strecke(punkte, knick, zentrum, breite+1.5)
    return bool(gedeckt.all())


def _gefuellte_endteile(dreiecke):
    """Dreiecke mit gemeinsamer Ecke gruppieren. Nur vollstaendig ausgefuellte konvexe Teile zulassen."""
    from scipy.spatial import ConvexHull, QhullError
    von_ecke = {}
    nachbarn = [set() for _ in dreiecke]
    for i, dreieck in enumerate(dreiecke):
        for p in dreieck:
            key = tuple(np.round(p, 6))
            j = von_ecke.setdefault(key, i)
            nachbarn[i].add(j)
            nachbarn[j].add(i)
    offen = set(range(len(dreiecke)))
    teile = []
    while offen:
        gruppe = {offen.pop()}
        stapel = list(gruppe)
        while stapel:
            andere = nachbarn[stapel.pop()] & offen
            offen.difference_update(andere)
            gruppe.update(andere)
            stapel.extend(andere)
        t = np.array([dreiecke[i] for i in gruppe])
        punkte = t.reshape(-1, 2)
        try:
            huelle = ConvexHull(punkte)
        except QhullError:
            return []
        flaeche = abs(np.linalg.det(t[:, 1:] - t[:, :1])).sum()/2
        if abs(flaeche-huelle.volume) > .001*huelle.volume:
            return []
        rand = punkte[huelle.vertices]
        if len(rand) == 4:
            # Duenner rechteckiger Strich mit zwei kurzen gegenueberliegenden Endkanten.
            diff = np.roll(rand, -1, axis=0) - rand
            k = np.linalg.norm(diff, axis=1).argmin()
            kurz, lang = diff[k], diff[(k+1)%4]
            if (np.linalg.norm(kurz) < .08 and abs(kurz @ lang) < .01*np.linalg.norm(kurz)*np.linalg.norm(lang)
                    and np.linalg.norm(kurz + diff[(k+2)%4]) < .002):
                mitte = (rand + np.roll(rand, -1, axis=0))/2
                teile.append(mitte[[k, (k+2)%4]])
                continue
        teile.append(np.vstack((rand, rand[0])))
    return teile


def abgesetzte_endlinie(pfade, zellen):
    """Kurzer waagerechter Ansatz, schraeger Schaft und genau eine Endmarke ausserhalb des Rahmens."""
    l, b, _, t = zellen[0]
    r, h = zellen[-1][2], t-b
    teile = []
    for p, voll in pfade:
        if (p[:, 0].min() >= l-.03*h and p[:, 0].max() <= r+.03*h and
                p[:, 1].min() >= b-.03*h and p[:, 1].max() <= t+.03*h):
            continue
        teile.append((p, voll))
    return endlinie_neben_schrift(teile, (l, b, r, t))


def endlinie_neben_schrift(teile, schriftbox):
    """Den vollstaendigen Linienzug an Lage und Hoehe der Beschriftung pruefen."""
    l, b, r, t = schriftbox
    h = t-b
    if not 3 <= len(teile) <= 256:
        return False
    links = all(p[:, 0].max() < l-.1*h for p, _ in teile)
    if not links and not all(p[:, 0].min() > r+.1*h for p, _ in teile):
        return False
    formen = [(p - [l if links else r, (b+t)/2])*[(-1 if links else 1)/h, 1/h] for p, _ in teile]
    if all(voll for _, voll in teile):
        formen = _gefuellte_endteile(formen)
    elif any(voll for _, voll in teile):
        return False
    if len(formen) != 3:
        return False
    geraden = sorted((p[np.argsort(p[:, 0])] for p in formen if len(p) == 2), key=lambda p: p[0, 0])
    if len(geraden) != 2:
        return False
    (start, knick), (anschluss, ende) = geraden
    if not (.1 < start[0] < 1 and .08 < knick[0]-start[0] < 2 and max(abs(start[1]), abs(knick[1])) < .026
            and np.linalg.norm(knick-anschluss) < .022 and abs(ende[1]-knick[1]) > .25):
        return False
    rand, = [p for p in formen if len(p) != 2]
    if len(rand) < 4 or np.linalg.norm(rand[0]-rand[-1]) > .005:
        return False
    q = rand[:-1]-ende
    if len(q) == 3:
        i = np.linalg.norm(q, axis=1).argmin()
        if np.linalg.norm(q[i]) > .022:
            return False
        v = np.delete(q, i, axis=0)
        richtung = (knick-ende)/np.linalg.norm(knick-ende)
        laengs = v @ richtung
        quer = v @ [-richtung[1], richtung[0]]
        return bool(min(laengs) > .15 and max(laengs) < .85 and np.ptp(laengs) < .07
                    and quer.min() < -.04 and quer.max() > .04 and abs(quer.sum()) < .07)
    radien = np.linalg.norm(q, axis=1)
    phi = np.sort(np.arctan2(q[:, 1], q[:, 0]))
    return bool(len(q) >= 8 and .019 < np.mean(radien) < .21 and np.ptp(radien) < .08*np.mean(radien)
                and np.diff(phi, append=phi[0]+2*np.pi).max() < .85)
