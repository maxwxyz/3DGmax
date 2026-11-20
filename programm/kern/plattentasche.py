"""Gezeichnete Rechtecktaschen anhand von Lage, Seitenlaengen und Tiefe pruefen."""

from dataclasses import dataclass
import math

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe
from .zeichnungskoerper import Plattentasche, koordinaten, pruefe_tiefe, tiefenmass


@dataclass(frozen=True)
class Taschenkontur:
    box: tuple  # Blattstelle fuer die Markierung
    x: float
    y: float
    breite: float
    hoehe: float


def solltaschen(konturen, zeilen, masse, umfang, bohrungen):
    sx, sy = (p.nennwert for p in masse[:2])
    bx, by = umfang
    taschen = []
    for i, (kontur, zeile) in enumerate(zip(konturen, zeilen, strict=True), 1):
        tx, ty, tb, th, tt = zeile
        mitte = koordinaten(tx, ty)
        if not mitte:
            raise ValueError(tr("Den Mittelpunkt X und Y für Tasche {} angeben.").format(i))
        x, y = mitte
        breite, hoehe = (lese_angabe(text, 1.) for text in (tb, th))
        for p in (breite, hoehe):
            if (not p or p.typ != "Location_LinearDistance" or p.nennwert is None or "Hilfsmass" in p.modifikatoren
                    or not all(math.isfinite(g) and g > 0 for g in (p.nennwert, *p.grenzen()) if g is not None)):
                raise ValueError(tr("Für Tasche {} beide positiven Seitenmaße angeben.").format(i))
        tiefe = None
        if tt is not None:
            tiefe = tiefenmass(tt, 1.)
            if tiefe is None or tiefe.nennwert is None:
                raise ValueError(tr("Die Tiefe zum flachen Grund von Tasche {} angeben.").format(i))
            pruefe_tiefe(tiefe, masse[2])
        a, b = breite.nennwert/2, hoehe.nennwert/2
        if not (a < x < sx-a and b < y < sy-b):
            raise ValueError(tr("Tasche {} erreicht den Plattenrand.").format(i))
        if any(abs(x-t.x) <= a+t.breite.nennwert/2 and abs(y-t.y) <= b+t.hoehe.nennwert/2 for t in taschen):
            raise ValueError(tr("Tasche {} berührt oder schneidet eine andere Tasche.").format(i))
        for bohrung in bohrungen:
            dx, dy = max(0., abs(x-bohrung.x)-a), max(0., abs(y-bohrung.y)-b)
            if math.hypot(dx, dy) <= bohrung.durchmesser.nennwert/2:
                raise ValueError(tr("Tasche {} berührt oder schneidet eine Bohrung.").format(i))
        # Beide gegenueberliegenden Kanten jeder Richtung muessen zum Druckbild passen.
        if (bx*(abs(x/sx-kontur.x)+abs(a/sx-kontur.breite/2)) > 2
                or by*(abs(y/sy-kontur.y)+abs(b/sy-kontur.hoehe/2)) > 2):
            raise ValueError(tr("Lage oder Seitenmaße von Tasche {} widersprechen dem Grundriss.").format(i))
        taschen.append(Plattentasche(x, y, breite, hoehe, tiefe))
    return taschen
