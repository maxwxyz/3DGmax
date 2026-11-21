"""Abgesetzten Zielbogen am radialen Masspfeil von der eigentlichen Schrift trennen."""

import numpy as np


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
