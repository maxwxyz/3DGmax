"""Sichtbare Bohrungsringe einer Plattenansicht mit den Bemassungen abgleichen."""

from dataclasses import dataclass
import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe, musteranzahl
from .zeichnungsansicht import Blattkreis
from .zeichnungskoerper import Plattenbohrung, koordinatenmasse, massbereich, pruefe_tiefe, tiefenmass, tintenrechteck
from .plattentasche import Taschenkontur
from .rundkontur import passende_rundung


@dataclass(frozen=True)
class Plattenring:
    """Mitte relativ zur Plattenbreite und -hoehe, Radius relativ zur Breite."""
    kreis: Blattkreis
    x: float
    y: float
    r: float
    kern: int | None = None


def _ist_ring(maske, kreis, x, y):
    # Jedes Pixel der Komponente muss an der Kreislinie liegen. Der Ring muss ein Loch umschliessen.
    ys, xs = np.nonzero(maske)
    abstand = np.hypot(xs + x - kreis.x, ys + y - kreis.y)
    if np.max(np.abs(abstand-kreis.r)) > max(1.75, .09*kreis.r):
        return False
    gefuellt = ndimage.binary_fill_holes(maske, structure=np.ones((3, 3), dtype=bool))
    return gefuellt[maske.shape[0]//2, maske.shape[1]//2]


def _ringgruppen(ringe, links, unten, breite, hoehe):
    bohrungen = []
    if not ringe:
        return bohrungen
    # Nur deckungsgleiche Vektormitten gruppieren. Die zwei Pixel fuer die Rasterpruefung
    # waeren zu grob und koennten einen exzentrischen Ring zur Stufe machen.
    baum = cKDTree([k.mitte for k in ringe])
    gesehen = set()
    for i in sorted(range(len(ringe)), key=lambda j: (ringe[j].x, -ringe[j].y)):
        if i in gesehen:
            continue
        gruppe = baum.query_ball_point(ringe[i].mitte, .05)
        if gesehen.intersection(gruppe) or any(math.dist(ringe[j].mitte, ringe[n].mitte) > .05
                                               for j in gruppe for n in gruppe):
            return None
        gesehen.update(gruppe)
        kern = len(bohrungen)
        for n, j in enumerate(sorted(gruppe, key=lambda j: ringe[j].r)):
            k = ringe[j]
            bohrungen.append(Plattenring(k, (k.x-links)/breite, (unten-k.y)/hoehe, k.r/breite,
                                         kern if n else None))
    return bohrungen


def plattenumriss(bild, box, kreise, rundungen=()):
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
    rundmitten = cKDTree([(q[:2]+q[2:4])/2 for q in rundungen]) if len(rundungen) else None
    for i, (yy, xx) in enumerate(teile, 1):
        if i == aussen:
            continue
        x = l+(xx.start+xx.stop-1)/2
        y = t+(yy.start+yy.stop-1)/2
        radius = (xx.stop-xx.start+yy.stop-yy.start)/4
        nahe = (kreise[j] for j in zentren.query_ball_point((x,y), 1.75)) if zentren is not None else ()
        kandidaten = [k for k in nahe if abs(radius-k.r) <= max(2., .10*k.r)]
        teil = labels[yy, xx] == i
        if len(kandidaten) > 1:
            ys, xs = np.nonzero(teil)
            # Bei nahen Radien die Mitte der gedruckten Strichstaerke auswerten.
            def radienfehler(k):
                abstand = np.hypot(l+xx.start+xs-k.x, t+yy.start+ys-k.y)
                return abs((abstand.min()+abstand.max())/2-k.r)
            kandidaten = [k for k in kandidaten if radienfehler(k) <= 1.]
        if len(kandidaten) == 1 and _ist_ring(teil, kandidaten[0], l+xx.start, t+yy.start):
            ringe.append(kandidaten[0])
            continue
        rund = None
        if rundmitten is not None:
            nachbarn = rundmitten.query_ball_point((x, y), 3., p=np.inf)
            rund = passende_rundung(teil, l+xx.start, t+yy.start, (rundungen[j] for j in nachbarn))
        langloch = False
        if rund is None:
            rand = tintenrechteck(np.pad(teil, 1), l+xx.start-1, t+yy.start-1)
            if rand is None:
                return None
            radius = 0.
        else:
            rand = rund[:4]
            langloch = abs(min(rand[2:]-rand[:2])/2-rund[4]) < 1e-6
            radius = 0. if langloch else rund[4]/breite
        x1, y1, x2, y2 = rand
        taschen.append(Taschenkontur((x1/w,y1/h,x2/w,y2/h), ((x1+x2)/2-links)/breite,
                                    (unten-(y1+y2)/2)/hoehe, (x2-x1)/breite, (y2-y1)/hoehe, radius, langloch))
    bohrungen = _ringgruppen(ringe, links, unten, breite, hoehe)
    if bohrungen is None:
        return None
    if any(not (0 < q.x-q.r < q.x+q.r < 1 and 0 < q.y-q.r*breite/hoehe < q.y+q.r*breite/hoehe < 1)
           for q in bohrungen):
        return None
    return (breite, hoehe), bohrungen, sorted(taschen, key=lambda q: (q.x, q.y))


def kegelwinkelmass(text, _faktor=1.):
    p = lese_angabe(text.strip().removeprefix("⌵").strip(), 1.)
    if not p or p.typ != "Size_Angular" or p.nennwert is None or p.modifikatoren or p.passung:
        return None
    oben, unten = p.grenzen()
    if oben is not None and unten is not None and oben < unten:
        return None
    return p if all(0 < g < 180 for g in (p.nennwert, oben, unten) if g is not None) else None


def _zylindertiefe(tiefe, radius_max, spitze, gesamt, dicke):
    """Kleinste zylindrische Tiefe, auch unter einer anschliessenden Senkung."""
    zusatz = radius_max/math.tan(math.radians(massbereich(spitze)[0])/2)
    minimum, maximum = massbereich(tiefe)
    if gesamt:
        minimum -= zusatz
        if minimum <= 0:
            raise ValueError(tr("Die Gesamttiefe lässt mit ihren Grenzmaßen keinen zylindrischen Abschnitt übrig."))
    elif maximum+zusatz >= massbereich(dicke)[0]:
        raise ValueError(tr("Die Bohrspitze erreicht mit ihren Grenzmaßen die Plattenunterseite."))
    return minimum


def sollbohrungen(ringe, werte, masse, umfang, *, tiefen=None, senkwinkel=None, spitzenwinkel=None, bis_spitze=()):
    breite, hoehe, _ = [p.nennwert for p in masse]
    bx, by = umfang
    if tiefen is None:
        tiefen = [None] * len(ringe)
    senkwinkel = senkwinkel or {}
    spitzenwinkel = spitzenwinkel or {}
    bohrungen = []
    letzte_zylindertiefe = None
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
        mitte = (bohrungen[ring.kern].lagemasse if ring.kern is not None else koordinatenmasse(tx, ty))
        if not mitte:
            raise ValueError(tr("X und Y für Bohrung {} als Koordinaten angeben.").format(index))
        x, y = (p.nennwert for p in mitte)
        r = pmi.nennwert/2
        # Auch am Toleranzrand muss der vollstaendige Ring innerhalb der Platte liegen.
        radius_max = massbereich(pmi)[1]/2
        for lage, seite in zip(mitte, masse[:2], strict=True):
            rand = massbereich(seite)[0]
            if any(not radius_max < g < rand-radius_max for g in (lage.nennwert, *lage.grenzen()) if g is not None):
                raise ValueError(tr("Bohrung {} reicht über den Plattenrand.").format(index))
        fremd = (b for j, b in enumerate(bohrungen) if ring.kern is None or (j != ring.kern and b.kern != ring.kern))
        if any(math.hypot(x-b.x, y-b.y) <= r+b.durchmesser.nennwert/2 for b in fremd):
            raise ValueError(tr("Bohrung {} berührt oder schneidet eine andere Bohrung.").format(index))
        if (math.hypot((x/breite-ring.x)*bx, (y/hoehe-ring.y)*by) > 2.
                or abs((r/breite-ring.r)*bx) > 2.):
            raise ValueError(tr("Lage oder Durchmesser von Bohrung {} widerspricht dem Grundriss.").format(index))
        tiefe = None
        if tiefentext is not None:
            tiefe = tiefenmass(tiefentext, 1.)
            if tiefe is None or tiefe.nennwert is None:
                if index-1 in spitzenwinkel:
                    raise ValueError(tr("Die Bohrtiefe für Bohrung {} angeben.").format(index))
                raise ValueError(tr("Die Tiefe bis zum flachen Grund von Bohrung {} angeben.").format(index))
            pruefe_tiefe(tiefe, masse[2])
        winkel = None
        if index-1 in senkwinkel:
            winkel = kegelwinkelmass(senkwinkel[index-1])
            if winkel is None:
                raise ValueError(tr("Den eingeschlossenen Senkwinkel mit Gradzeichen angeben (größer als 0° und kleiner als 180°)."))
            if ring.kern is None or (index < len(ringe) and ringe[index].kern == ring.kern) or tiefe is not None:
                raise ValueError(tr("Die Kegelsenkung von oben benötigt den äußersten Ring einer Bohrung."))
        if ring.kern is not None:
            innen = bohrungen[-1]
            if (tiefe is None and winkel is None) or massbereich(pmi)[0] <= massbereich(innen.durchmesser)[1]:
                raise ValueError(tr("Für jede äußere Stufe einen größeren Durchmesser und eine Tiefe von oben angeben."))
            if winkel:
                differenz = massbereich(pmi)[1]-massbereich(innen.durchmesser)[0]
                tiefste = differenz/(2*math.tan(math.radians(massbereich(winkel)[0])/2))
            else:
                tiefste = massbereich(tiefe)[1]
            if tiefste >= letzte_zylindertiefe:
                raise ValueError(tr("Die äußere Stufe muss auch mit Toleranz flacher als die innere Bohrung sein."))
        gesamt = index-1 in bis_spitze
        spitze = None
        letzte_zylindertiefe = massbereich(tiefe or masse[2])[0]
        if index-1 in spitzenwinkel:
            spitze = kegelwinkelmass(spitzenwinkel[index-1])
            if ring.kern is not None or tiefe is None or spitze is None:
                raise ValueError(tr("Für eine Bohrspitze die Bohrtiefe und den eingeschlossenen Spitzenwinkel mit Gradzeichen angeben."))
            letzte_zylindertiefe = _zylindertiefe(tiefe, radius_max, spitze, gesamt, masse[2])
        bohrungen.append(Plattenbohrung(x, y, pmi, tiefe, mitte if ring.kern is None else None, ring.kern,
                                        winkel, spitze, gesamt))
    return bohrungen
