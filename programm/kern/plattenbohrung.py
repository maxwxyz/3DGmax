"""Sichtbare Bohrungsringe einer Plattenansicht mit den Bemassungen abgleichen."""

from dataclasses import dataclass
import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe, musteranzahl
from .zeichnungsansicht import Blattkreis
from .zeichnungskoerper import Plattenbohrung, koordinaten, pruefe_tiefe, tiefenmass, tintenrechteck
from .plattentasche import Taschenkontur


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
    h, w = bild.shape[:2]
    l, t, r, b = np.rint(np.clip(box, 0., 1.)*[w, h, w, h]).astype(int)
    maske = bild[t:b, l:r, :3].min(axis=2) < 245
    if not maske.any():
        return None
    labels, _ = ndimage.label(maske)
    teile = ndimage.find_objects(labels)
    ys, xs = np.nonzero(maske)
    aussenbox = (slice(ys.min(), ys.max()+1), slice(xs.min(), xs.max()+1))
    if aussenbox not in teile:
        return None
    aussen = teile.index(aussenbox)+1
    grenzen = tintenrechteck(labels == aussen, l, t)
    if grenzen is None:
        return None
    links, oben, rechts, unten = grenzen
    breite, hoehe = rechts-links, unten-oben
    ringe, taschen = [], []
    zentren = cKDTree([(k.x, k.y) for k in kreise]) if kreise else None
    for i, (yy, xx) in enumerate(teile, 1):
        if i == aussen:
            continue
        x = l+(xx.start+xx.stop-1)/2
        y = t+(yy.start+yy.stop-1)/2
        radius = (xx.stop-xx.start+yy.stop-yy.start)/4
        nahe = (kreise[j] for j in zentren.query_ball_point((x,y), 1.75)) if zentren is not None else ()
        kandidaten = [k for k in nahe if abs(radius-k.r) <= max(2., .10*k.r)]
        teil = labels[yy, xx] == i
        if len(kandidaten) == 1 and _ist_ring(teil, kandidaten[0], l+xx.start, t+yy.start):
            ringe.append(kandidaten[0])
            continue
        rand = tintenrechteck(np.pad(teil, 1), l+xx.start-1, t+yy.start-1)
        if rand is None:
            return None
        x1, y1, x2, y2 = rand
        taschen.append(Taschenkontur((x1/w,y1/h,x2/w,y2/h), ((x1+x2)/2-links)/breite,
                                    (unten-(y1+y2)/2)/hoehe, (x2-x1)/breite, (y2-y1)/hoehe))
    bohrungen = [Plattenring(k, (k.x-links)/breite, (unten-k.y)/hoehe, k.r/breite) for k in ringe]
    if any(not (0 < q.x-q.r < q.x+q.r < 1 and 0 < q.y-q.r*breite/hoehe < q.y+q.r*breite/hoehe < 1)
           for q in bohrungen):
        return None
    return (breite, hoehe), sorted(bohrungen, key=lambda q: (q.x, q.y)), sorted(taschen, key=lambda q: (q.x, q.y))


def sollbohrungen(ringe, werte, masse, umfang, *, tiefen=None):
    breite, hoehe, _ = [p.nennwert for p in masse]
    bx, by = umfang
    if tiefen is None:
        tiefen = [None] * len(ringe)
    bohrungen = []
    for index, (ring, zeile, tiefentext) in enumerate(zip(ringe, werte, tiefen, strict=True), 1):
        tx, ty, td = zeile
        pmi = lese_angabe(td, 1.)
        if pmi and pmi.typ == "Location_LinearDistance":
            pmi.typ = "Size_Diameter"
        if (not pmi or pmi.typ != "Size_Diameter" or not pmi.nennwert or not math.isfinite(pmi.nennwert)
                or pmi.nennwert <= 0 or musteranzahl(td) > 1 or "Hilfsmass" in pmi.modifikatoren):
            raise ValueError(tr("Den Durchmesser von Bohrung {} angeben.").format(index))
        if any(g is not None and (not math.isfinite(g) or g <= 0) for g in pmi.grenzen()):
            raise ValueError(tr("Die Grenzmaße für Bohrung {} müssen positiv sein.").format(index))
        mitte = koordinaten(tx, ty)
        if not mitte:
            raise ValueError(tr("X und Y für Bohrung {} als Koordinaten angeben.").format(index))
        x, y = mitte
        r = pmi.nennwert/2
        if not (r < x < breite-r and r < y < hoehe-r):
            raise ValueError(tr("Bohrung {} reicht über den Plattenrand.").format(index))
        if any(math.hypot(x-b.x, y-b.y) <= r+b.durchmesser.nennwert/2 for b in bohrungen):
            raise ValueError(tr("Bohrung {} berührt oder schneidet eine andere Bohrung.").format(index))
        if (math.hypot((x/breite-ring.x)*bx, (y/hoehe-ring.y)*by) > 2.
                or abs((r/breite-ring.r)*bx) > 2.):
            raise ValueError(tr("Lage oder Durchmesser von Bohrung {} widerspricht dem Grundriss.").format(index))
        tiefe = None
        if tiefentext is not None:
            tiefe = tiefenmass(tiefentext, 1.)
            if tiefe is None or tiefe.nennwert is None:
                raise ValueError(tr("Die Tiefe bis zum flachen Grund von Bohrung {} angeben.").format(index))
            pruefe_tiefe(tiefe, masse[2])
        bohrungen.append(Plattenbohrung(x, y, pmi, tiefe))
    return bohrungen
