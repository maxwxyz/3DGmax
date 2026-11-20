"""Gemeinsames Istmass fuer Mantelversatz und Materialbonus eines starren Zylinders."""

from dataclasses import dataclass

import numpy as np

from . import toleranzzone as tz


def _achsenden_maximum(a, b, summe, sehne):
    """Maximiere a*x + b*y fuer zwei Punkte im Einheitskreis mit Abstand <= sehne."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return na + nb
    ua, ub = a / na, b / nb
    ns = np.linalg.norm(summe)
    if ns == 0:
        return sehne * na
    # Nur ein Ende auf dem Kreis: y = Richtung(summe), x = y + sehne * ua (bzw. umgekehrt).
    richtung = summe / ns
    # Beide Enden auf dem Kreis, ihr Abstand ist aktiv. Die halbe Sehne liegt
    # senkrecht zur Mitte. Beide Drehsinne pruefen und gemeinsam optimal drehen.
    sinus = sehne / 2
    cosinus = np.sqrt((1 - sinus) * (1 + sinus))
    differenz = a - b
    wert = np.sqrt((cosinus * ns)**2 + (sinus * np.linalg.norm(differenz))**2
                   + 2 * cosinus * sinus * np.linalg.norm(np.cross(summe, differenz)))
    for u, n in ((ua, na), (ub, nb)):
        wert = np.where(richtung @ u <= -sehne / 2, ns + sehne * n, wert)
    return np.where(np.linalg.norm(ua - ub) <= sehne, na + nb, wert)


def achsenhub(rad, winkel, lagezonen, neigung):
    """Stuetzfunktion der radialen Versatze und Kippungen; Zahlen oder Arrays von Zonengroessen."""
    from functools import reduce
    if not lagezonen:
        h = reduce(np.minimum, neigung) * np.linalg.norm(winkel)
    else:
        radius = reduce(np.minimum, (o for _, o in lagezonen))
        a, b = rad / 2 - winkel, rad / 2 + winkel
        if neigung:
            sehne = np.minimum(2., reduce(np.minimum, neigung) / np.where(radius > 0., radius, 1.))
            h = radius * _achsenden_maximum(a, b, rad, sehne)
        else:
            h = radius * (np.linalg.norm(a) + np.linalg.norm(b))
    return h


@dataclass(frozen=True)
class Zylindermass:
    nenn: float
    klein: float
    gross: float
    innen: bool


def zylindermass(form, masse, einzelachse):
    """Geometrisch zugeordnete, vollstaendige Durchmessergrenzen; Masse in mm."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    from OCC.Core.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED
    if form.Orientation() not in (TopAbs_FORWARD, TopAbs_REVERSED) or BRepAdaptor_Surface(form).GetType() != GeomAbs_Cylinder:
        return None
    start, d, _, r, _ = tz._achse([form])
    nenn = 2 * r
    grenzen = []
    for p in masse:
        gross, klein = p.grenzen()
        if gross is None and klein is None and not p.passung:
            continue
        if (gross is None or klein is None or not p.semantisch or p.modifikatoren or not einzelachse(p)
                or not np.isfinite([gross, klein]).all() or not 0 < klein <= gross):
            return None
        faktor = 2. if p.typ == "Size_Radius" else 1.
        if p.nennwert is not None and not np.isclose(faktor * p.nennwert, nenn, rtol=1e-7, atol=1e-6):
            return None
        grenzen.append((faktor * klein, faktor * gross))
    if grenzen:
        klein, gross = max(k for k, _ in grenzen), min(g for _, g in grenzen)
        if klein <= gross:
            return Zylindermass(nenn, klein, gross, tz._ist_innen(form, start, d))
    return None


@dataclass
class Materialstreuung:
    mass: Zylindermass
    durchmesserfaktor: float
    radial: tuple
    winkel: tuple
    zonen: list  # (Grundtoleranz, Materialbedingung, Obergrenze, reine Richtungszone)

    @classmethod
    def von_dict(cls, daten):
        return cls(**{**daten, "mass": Zylindermass(**daten["mass"])})

    def _hub(self, d):
        lage, neigung = [], []
        for grund, material, deckel, richtung in self.zonen:
            t = grund + tz._bonus(material, self.mass.innen, d, self.mass.klein, self.mass.gross)
            if deckel is not None:
                t = np.minimum(t, deckel)
            if richtung:
                neigung.append(t)
            else:
                lage.append((-t / 2, t / 2))
        return achsenhub(np.asarray(self.radial), np.asarray(self.winkel), lage, neigung)

    def _intervall(self, anteil):
        d = self.mass.klein + anteil * (self.mass.gross - self.mass.klein)
        versatz = self.durchmesserfaktor * (d - self.mass.nenn)
        hub = self._hub(d)
        return versatz - hub, versatz + hub

    def grenzen(self):
        """Die zulaessigen Zylindertorsoren und Durchmesser bilden eine konvexe Menge."""
        from scipy.optimize import minimize_scalar
        u0, o0 = self._intervall(0.)
        if self.mass.klein == self.mass.gross:
            return u0, o0
        u1, o1 = self._intervall(1.)
        # Bei mehreren simultanen Toleranzen kann das Extrem zwischen den Grenzmassen liegen.
        opt = {"xatol": 1e-13}
        lo = minimize_scalar(lambda s: self._intervall(s)[0], bounds=(0., 1.), method="bounded", options=opt)
        hi = minimize_scalar(lambda s: -self._intervall(s)[1], bounds=(0., 1.), method="bounded", options=opt)
        return min(u0, u1, lo.fun), max(o0, o1, -hi.fun)

    def ziehe(self, rng, proben, cp=1.):
        # Erst Istmass ziehen, danach die projizierte Merkmalsabweichung in genau dieser Zone.
        anteil = np.clip(rng.normal(.5, 1 / (6 * cp), proben), 0., 1.)
        unten, oben = self._intervall(anteil)
        standard = np.clip(rng.standard_normal(proben) / cp, -3., 3.)
        return (unten + oben) / 2 + standard * ((oben - unten) / 6)
