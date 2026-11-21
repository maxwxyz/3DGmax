"""Gezeichnete Rechtecktaschen anhand von Lage, Seitenlaengen und Tiefe pruefen."""

from dataclasses import dataclass, replace
import math
import re

from ..i18n import tr
from .pmi import MASS, Pmi
from .zeichnungsabgleich import lese_angabe, musteranzahl
from .zeichnungskoerper import Plattentasche, koordinaten, pruefe_tiefe, tiefenmass


@dataclass(frozen=True)
class Taschenkontur:
    box: tuple  # Blattstelle fuer die Markierung
    x: float
    y: float
    breite: float
    hoehe: float
    radius: float = 0.  # Anteil der Plattenbreite
    langloch: bool = False


def eckradiusmass(text, faktor):
    text = re.sub(r"^\s*4\s*[xX×]\s*(?=R)", "", text, flags=re.I)
    if musteranzahl(text):
        return None
    p = lese_angabe(text, faktor)
    if (p and p.typ == "Size_Radius" and not p.passung and not p.modifikatoren
            and p.nennwert is not None and math.isfinite(p.nennwert)):
        return p
    return None


def _eckradius(text, kontur, breite, hoehe, sx, bx):
    if not kontur.radius:
        return None
    p = eckradiusmass(text, 1.)
    if p is None:
        raise ValueError(tr("Den gemeinsamen Eckradius der Tasche mit R angeben."))
    kleinste_seite = min(g for m in (breite, hoehe) for g in (m.nennwert,*m.grenzen()) if g is not None)
    if not all(0 < g < kleinste_seite/2 for g in (p.nennwert,*p.grenzen()) if g is not None):
        raise ValueError(tr("Der Eckradius muss mit seinen Grenzmaßen vier gerade Seiten übrig lassen."))
    if abs(p.nennwert/sx-kontur.radius)*bx > 2:
        raise ValueError(tr("Der Eckradius widerspricht den Rundungen im Grundriss."))
    return p


def _beruehrt(dx, dy, a, b, radien):
    # Abstand der beiden inneren Rechtecke; bei einem Kreis ist das innere Rechteck ein Punkt.
    return math.hypot(max(abs(dx)-a,0.), max(abs(dy)-b,0.)) <= radien


def _positives_mass(text):
    p = lese_angabe(text, 1.)
    if not p or p.typ != "Location_LinearDistance" or p.nennwert is None or "Hilfsmass" in p.modifikatoren:
        return None
    oben, unten = p.grenzen()
    if oben is not None and unten is not None and oben < unten:
        return None
    if all(math.isfinite(g) and g > 0 for g in (p.nennwert, oben, unten) if g is not None):
        return p
    return None


def _nennmasse_abgleichen(gesamt, kurz, achse):
    if math.isclose(gesamt.nennwert, achse.nennwert+kurz.nennwert, abs_tol=1e-7, rel_tol=0):
        return gesamt, kurz, achse
    # Bei gedruckten Grenzmassen ist der Mittelwert nur ein Vorschlag fuer die Geometrie.
    (min_lang, max_lang), (min_kurz, max_kurz), (min_achse, max_achse) = (
        (p.unten, p.oben) if p.grenzmass else (p.nennwert, p.nennwert) for p in (gesamt, kurz, achse))
    unten = max(min_lang, min_kurz+min_achse)
    oben = min(max_lang, max_kurz+max_achse)
    if unten > oben+1e-7:
        raise ValueError(tr("Gesamtlänge und Summe aus Achsabstand und Langlochbreite widersprechen sich."))
    laenge = min(max(gesamt.nennwert,unten),oben)
    breite = min(max(kurz.nennwert, min_kurz, laenge-max_achse), max_kurz, laenge-min_achse)
    return tuple(replace(p,nennwert=wert) if p.grenzmass else p
                 for p, wert in zip((gesamt,kurz,achse), (laenge,breite,laenge-breite), strict=True))


def _langlochmasse(gesamttext, kurz, achstext):
    achsmass = _positives_mass(achstext) if achstext else None
    if achstext and (achsmass is None or achsmass.passung):
        raise ValueError(tr("Für den Achsabstand ein positives Längenmaß mit gültigen Grenzen angeben."))
    if kurz is None:
        raise ValueError(tr("Die Breite zwischen den geraden Langlochwänden angeben."))
    if not gesamttext and achsmass:
        return Pmi(MASS, typ="Location_LinearDistance", nennwert=achsmass.nennwert+kurz.nennwert), kurz, achsmass
    gesamt = _positives_mass(gesamttext)
    if gesamt is None:
        raise ValueError(tr("Die Gesamtlänge oder den Achsabstand des Langlochs angeben."))
    if achsmass is None and min(g for g in (gesamt.nennwert,*gesamt.grenzen()) if g is not None) <= max(
            g for g in (kurz.nennwert,*kurz.grenzen()) if g is not None):
        raise ValueError(tr("Die Gesamtlänge des Langlochs muss auch bei Grenzmaß größer als die Breite sein."))
    if achsmass:
        gesamt, kurz, achsmass = _nennmasse_abgleichen(gesamt, kurz, achsmass)
        # Nur wenn alle drei Toleranzintervalle vorliegen, ist deren Schnitt pruefbar.
        grenzen = [p.grenzen() for p in (gesamt, achsmass, kurz)]
        if all(None not in paar for paar in grenzen):
            (max_lang, min_lang), (max_achse, min_achse), (max_kurz, min_kurz) = grenzen
            if max_lang < min_achse+min_kurz-1e-7 or min_lang > max_achse+max_kurz+1e-7:
                raise ValueError(tr("Die Grenzmaße für Gesamtlänge, Achsabstand und Langlochbreite sind unvereinbar."))
    return gesamt, kurz, achsmass


def solltaschen(konturen, zeilen, masse, umfang, bohrungen):
    sx, sy = (p.nennwert for p in masse[:2])
    bx, by = umfang
    taschen = []
    for i, (kontur, zeile) in enumerate(zip(konturen, zeilen, strict=True), 1):
        tx, ty, tb, th, tt = zeile[:5]
        mitte = koordinaten(tx, ty)
        if not mitte:
            raise ValueError(tr("Den Mittelpunkt X und Y für Tasche {} angeben.").format(i))
        x, y = mitte
        achsmass, abgeleitet = None, False
        if kontur.langloch:
            quer = kontur.breite*bx > kontur.hoehe*by
            gesamttext = (tb if quer else th).strip()
            achstext = zeile[6].strip() if len(zeile) > 6 else ""
            kurz = _positives_mass(th if quer else tb)
            gesamt, kurz, achsmass = _langlochmasse(gesamttext, kurz, achstext)
            breite, hoehe = (gesamt, kurz) if quer else (kurz, gesamt)
            abgeleitet = not gesamttext
        else:
            breite, hoehe = _positives_mass(tb), _positives_mass(th)
            if breite is None or hoehe is None:
                raise ValueError(tr("Für Tasche {} beide positiven Seitenmaße angeben.").format(i))
        tiefe = None
        if tt is not None:
            tiefe = tiefenmass(tt, 1.)
            if tiefe is None or tiefe.nennwert is None:
                raise ValueError(tr("Die Tiefe zum flachen Grund von Tasche {} angeben.").format(i))
            pruefe_tiefe(tiefe, masse[2])
        radius = _eckradius(zeile[5] if len(zeile) > 5 else "", kontur, breite, hoehe, sx, bx)
        tasche = Plattentasche(x, y, breite, hoehe, tiefe, radius, kontur.langloch, achsmass, abgeleitet)
        r = tasche.rundungsradius
        a, b = breite.nennwert/2, hoehe.nennwert/2
        if not (a < x < sx-a and b < y < sy-b):
            raise ValueError(tr("Tasche {} erreicht den Plattenrand.").format(i))
        for t in taschen:
            rt = t.rundungsradius
            if _beruehrt(x-t.x, y-t.y, a-r+t.breite.nennwert/2-rt, b-r+t.hoehe.nennwert/2-rt, r+rt):
                raise ValueError(tr("Tasche {} berührt oder schneidet eine andere Tasche.").format(i))
        for bohrung in bohrungen:
            if _beruehrt(x-bohrung.x, y-bohrung.y, a-r, b-r, r+bohrung.durchmesser.nennwert/2):
                raise ValueError(tr("Tasche {} berührt oder schneidet eine Bohrung.").format(i))
        # Beide gegenueberliegenden Kanten jeder Richtung muessen zum Druckbild passen.
        if (bx*(abs(x/sx-kontur.x)+abs(a/sx-kontur.breite/2)) > 2
                or by*(abs(y/sy-kontur.y)+abs(b/sy-kontur.hoehe/2)) > 2):
            raise ValueError(tr("Lage oder Seitenmaße von Tasche {} widersprechen dem Grundriss.").format(i))
        taschen.append(tasche)
    return taschen
