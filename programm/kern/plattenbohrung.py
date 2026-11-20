"""Sichtbare Bohrungsringe einer Plattenansicht mit den Bemassungen abgleichen."""

from dataclasses import dataclass
import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe, musteranzahl
from .zeichnungsansicht import Blattkreis
from .zeichnungskoerper import rechteckgrenzen


@dataclass(frozen=True)
class Plattenring:
    """Mitte relativ zur Plattenbreite und -hoehe, Radius relativ zur Breite."""
    kreis: Blattkreis
    x: float
    y: float
    r: float


def _ist_ring(maske, kreis, x, y):
    # Jedes Pixel der Komponente muss an der Kreislinie liegen. Der Ring muss ein Loch umschliessen.
    ys, xs = np.nonzero(maske)
    abstand = np.hypot(xs + x - kreis.x, ys + y - kreis.y)
    if np.max(np.abs(abstand-kreis.r)) > max(1.75, .09*kreis.r):
        return False
    gefuellt = ndimage.binary_fill_holes(maske, structure=np.ones((3, 3), dtype=bool))
    return gefuellt[maske.shape[0]//2, maske.shape[1]//2]


def plattenumriss(bild, box, kreise):
    if not kreise:
        return None
    h, w = bild.shape[:2]
    l, t, r, b = np.rint(np.clip(box, 0., 1.)*[w, h, w, h]).astype(int)
    raster = bild[t:b, l:r, :3].copy()
    if not raster.size:
        return None
    maske = raster.min(axis=2) < 245
    labels, _ = ndimage.label(maske)
    ringe = []
    zentren = cKDTree([(k.x, k.y) for k in kreise])
    for i, (yy, xx) in enumerate(ndimage.find_objects(labels), 1):
        x = l+(xx.start+xx.stop-1)/2
        y = t+(yy.start+yy.stop-1)/2
        radius = (xx.stop-xx.start+yy.stop-yy.start)/4
        nahe = (kreise[j] for j in zentren.query_ball_point((x, y), 1.75))
        kandidaten = [k for k in nahe if abs(radius-k.r) <= max(2., .10*k.r)]
        if len(kandidaten) != 1:
            continue
        k = kandidaten[0]
        teil = labels[yy, xx] == i
        if _ist_ring(teil, k, l+xx.start, t+yy.start):
            raster[yy, xx][teil] = 255
            ringe.append(k)
    grenzen = rechteckgrenzen(raster, (0, 0, 1, 1))
    if grenzen is None:
        return None
    links, oben, rechts, unten = grenzen
    breite, hoehe = rechts-links, unten-oben
    bohrungen = [Plattenring(k, (k.x-l-links)/breite, (t+unten-k.y)/hoehe, k.r/breite) for k in ringe]
    if any(not (0 < q.x-q.r < q.x+q.r < 1 and 0 < q.y-q.r*breite/hoehe < q.y+q.r*breite/hoehe < 1)
           for q in bohrungen):
        return None
    return (breite, hoehe), sorted(bohrungen, key=lambda q: (q.x, q.y))


def sollbohrungen(ringe, werte, masse, umfang):
    breite, hoehe, _ = [p.nennwert for p in masse]
    bx, by = umfang
    bohrungen = []
    for index, (ring, zeile) in enumerate(zip(ringe, werte, strict=True), 1):
        tx, ty, td = zeile
        pmi = lese_angabe(td, 1.)
        if pmi and pmi.typ == "Location_LinearDistance":
            pmi.typ = "Size_Diameter"
        if (not pmi or pmi.typ != "Size_Diameter" or not pmi.nennwert or not math.isfinite(pmi.nennwert)
                or pmi.nennwert <= 0 or musteranzahl(td) > 1 or "Hilfsmass" in pmi.modifikatoren):
            raise ValueError(tr("Den Durchmesser von Bohrung {} angeben.").format(index))
        if any(g is not None and (not math.isfinite(g) or g <= 0) for g in pmi.grenzen()):
            raise ValueError(tr("Die Grenzmaße für Bohrung {} müssen positiv sein.").format(index))
        koord = [lese_angabe(text, 1.) for text in (tx, ty)]
        if any(not q or q.typ != "Location_LinearDistance" or q.nennwert is None or not math.isfinite(q.nennwert)
               or q.oben is not None or q.unten is not None or q.passung or q.modifikatoren for q in koord):
            raise ValueError(tr("X und Y für Bohrung {} als Koordinaten angeben.").format(index))
        x, y = (q.nennwert for q in koord)
        r = pmi.nennwert/2
        if not (r < x < breite-r and r < y < hoehe-r):
            raise ValueError(tr("Bohrung {} reicht über den Plattenrand.").format(index))
        if any(math.hypot(x-a, y-b) <= r+q.nennwert/2 for a, b, q in bohrungen):
            raise ValueError(tr("Bohrung {} berührt oder schneidet eine andere Bohrung.").format(index))
        if (math.hypot((x/breite-ring.x)*bx, (y/hoehe-ring.y)*by) > 2.
                or abs((r/breite-ring.r)*bx) > 2.):
            raise ValueError(tr("Lage oder Durchmesser von Bohrung {} widerspricht dem Grundriss.").format(index))
        bohrungen.append((x, y, pmi))
    return bohrungen
