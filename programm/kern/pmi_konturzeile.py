"""Einzeilige Versalschrift mit ueberlappenden Zeichenbreiten aus ihren Einzelglyphen lesen."""

from functools import lru_cache

import numpy as np
from PySide6 import QtCore, QtGui
from scipy import ndimage
from scipy.cluster.hierarchy import DisjointSet

from . import pmi_strichschrift as schrift
from .pmi_versalmuster import ENGSCHRIFT


@lru_cache(maxsize=1)
def _vorlagen():
    return [(z, bild, ndimage.distance_transform_edt(~bild)) for z, bild in schrift._musterbilder(ENGSCHRIFT)]


def _konturen(pfade):
    """Eine Aussenkontur mit ihren umschlossenen Innenkonturen gruppieren."""
    if len(pfade) > 64 or any(len(p) < 4 or not np.allclose(p[0], p[-1], rtol=0, atol=1e-6) for p in pfade):
        return None
    ringe = [QtGui.QPolygonF([QtCore.QPointF(*xy) for xy in p]) for p in pfade]
    boxen = [ring.boundingRect() for ring in ringe]
    kinder = [[] for _ in ringe]
    wurzeln = []
    for i, ring in enumerate(ringe):
        eltern = [j for j, k in enumerate(ringe) if i != j and boxen[j].contains(boxen[i])
                  and all(k.containsPoint(punkt, QtCore.Qt.FillRule.OddEvenFill) for punkt in ring)]
        if len(eltern) > 1:
            return None
        if eltern:
            kinder[eltern[0]].append(i)
        else:
            wurzeln.append(i)
    return [[(pfade[i], False), *((pfade[j], False) for j in kinder[i])] for i in wurzeln]


def _dreiecksgruppen(dreiecke):
    """Zusammenhaengende Tintenflaechen auch in einem gemeinsamen Dreieckssatz trennen."""
    gruppen = DisjointSet(range(len(dreiecke)))
    kanten = {}
    for i, p in enumerate(dreiecke):
        ab, ac = p[1:] - p[0]
        if ab[0]*ac[1] == ab[1]*ac[0]:
            return None
        a, b, c = map(tuple, p)
        for u, v in ((a, b), (b, c), (c, a)):
            kante = (u, v) if u < v else (v, u)
            if kante in kanten:
                gruppen.merge(i, kanten[kante])
            else:
                kanten[kante] = i
    return [[(dreiecke[i], True) for i in gruppe] for gruppe in gruppen.subsets()]


def _buchstabe(pfade, hoehe):
    bild, _ = schrift._gesamtbild(pfade, 80/hoehe)
    if bild is None or not bild.any():
        return ""
    form = schrift._merkmal(bild)
    dist = ndimage.distance_transform_edt(~form)
    treffer = sorted((abstand[form].mean() + dist[vorlage].mean(), z) for z, vorlage, abstand in _vorlagen())
    (fehler, z), (naechster, _) = treffer[:2]
    if fehler > 1.15 or naechster-fehler < .30:
        return ""
    # Ein fehlendes Loch kann im mittleren Konturabstand fast unsichtbar sein.
    if pfade[0][1]:
        loecher = ndimage.label(~bild)[1]-1
    else:
        loecher = len(pfade)-1
    erwartet = 2 if z in "B8" else int(z in "ADOPQR0469")
    return z if loecher == erwartet else ""


def lies_konturzeile(pfade, unten, oben):
    """Zeichen mit ueberlappender Breite anhand der tatsaechlichen Tintengeometrie trennen."""
    gruppen = _konturen([p for p, voll in pfade if not voll])
    if gruppen is None:
        return ""
    dreiecke = [p for p, voll in pfade if voll]
    if dreiecke:
        fuellungen = _dreiecksgruppen(dreiecke)
        if fuellungen is None:
            return ""
        gruppen.extend(fuellungen)
    if not 1 <= len(gruppen) <= 32:
        return ""
    zeichen = []
    h = oben-unten
    for gruppe in gruppen:
        punkte = np.vstack([p for p, _ in gruppe])
        l, b = punkte.min(axis=0)
        r, t = punkte.max(axis=0)
        if b-unten > .10*h or oben-t > .10*h or not .10*h < r-l < 1.3*h:
            return ""
        buchstabe = _buchstabe(gruppe, t-b)
        if not buchstabe:
            return ""
        zeichen.append((l, r, buchstabe))
    text = ""
    rechts = None
    for l, r, z in sorted(zeichen):
        if rechts is not None:
            abstand = (l-rechts)/h
            if not -.14 < abstand < 1.35:
                return ""
            if abstand > .40:
                text += " "
        text += z
        rechts = r
    return text
