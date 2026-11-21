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


def punkt_hinweislinie(rest, symbol, rand):
    """Eine zweigliedrige Hinweislinie vom Symbolfach zu einem gefuellten oder schraffierten Punkt."""
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
