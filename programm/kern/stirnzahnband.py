"""Stirnseitiges konisches Zahnband aus dem axialen Hoehenprofil konzentrischer Messkreise."""

from dataclasses import dataclass

import numpy as np

from ..i18n import tr


@dataclass
class Stirnzahnband:
    teil: str
    z: int
    punkt: np.ndarray
    richtung: np.ndarray
    radien: tuple
    relief: float
    neigung: float
    koerper: str | None = None
    koerper_id: object = None
    art = "kegelrad_stirnseitig"

    def als_dict(self):
        return {"art": self.art, "teil": self.teil, "anzahl": self.z,
                "achse": {"punkt": self.punkt.tolist(), "richtung": self.richtung.tolist()},
                "messradien_mm": list(self.radien), "axiale_zahnhoehe_mitte_mm": self.relief,
                "neigung_mittelflaeche_grad": self.neigung, "einstufung": "kandidat"}

    def zeilen(self):
        quelle = tr("Axiale Höhenprofile auf Messkreisen")
        return [(tr("Art"), tr("Kegelrad-Kandidat mit stirnseitiger Verzahnung"), quelle),
                (tr("Zähnezahl z"), str(self.z), quelle),
                (tr("Radialer Messbereich"), f"{self.radien[0]:.3f} – {self.radien[1]:.3f} mm", quelle),
                (tr("Axiale Zahnhöhe am mittleren Messkreis"), f"{self.relief:.3f} mm", quelle),
                (tr("Neigung der mittleren Zahnfläche zur Radialebene"), f"{self.neigung:.2f}°", quelle)]


def _hoehen(netz, punkte):
    """Je Messpunkt die vorderste und hinterste belegte Dreieckshoehe. Loecher bleiben offen."""
    a, b, c = netz.a, netz.b, netz.c
    u, v = b-a, c-a
    det = u[:, 0]*v[:, 1] - u[:, 1]*v[:, 0]
    zellbreite = netz.r_max / 8
    lo = np.floor(np.minimum(np.minimum(a[:, :2], b[:, :2]), c[:, :2])/zellbreite).astype(int)
    hi = np.floor(np.maximum(np.maximum(a[:, :2], b[:, :2]), c[:, :2])/zellbreite).astype(int)
    zellen, inverse = np.unique(np.floor(punkte/zellbreite).astype(int), axis=0, return_inverse=True)
    hoehen = np.full((2, len(punkte)), np.nan)
    regulaer = abs(det) > 1e-14 * netz.r_max**2
    vorher = None
    for k, (spalte, zeile) in enumerate(zellen):
        if spalte != vorher:
            streifen = np.flatnonzero(regulaer & (lo[:, 0] <= spalte) & (hi[:, 0] >= spalte))
            vorher = spalte
        ix = streifen[(lo[streifen, 1] <= zeile) & (hi[streifen, 1] >= zeile)]
        if not len(ix):
            continue
        ids = np.flatnonzero(inverse == k)
        for start in range(0, len(ids), max(1, 250000//len(ix))):
            teil = ids[start:start+max(1, 250000//len(ix))]
            delta = punkte[teil, None, :] - a[ix, :2]
            x, y = delta[..., 0], delta[..., 1]
            e = (x*v[ix, 1] - y*v[ix, 0])/det[ix]
            f = (u[ix, 0]*y - u[ix, 1]*x)/det[ix]
            innen = (e >= -1e-8) & (f >= -1e-8) & (e+f <= 1+1e-8)
            z = a[ix, 2] + e*u[ix, 2] + f*v[ix, 2]
            da = innen.any(axis=1)
            hoehen[0, teil[da]] = np.where(innen, z, -np.inf).max(axis=1)[da]
            hoehen[1, teil[da]] = np.where(innen, z, np.inf).min(axis=1)[da]
    return hoehen


def erkenne(netz, teil, punkt, achse):
    from itertools import groupby
    from .verzahnung import _zahn_harmonische
    radien = np.linspace(.40, .96, 17) * netz.r_max
    winkel = (np.arange(360) + .37) * (2*np.pi/360)
    kreis = np.column_stack([np.cos(winkel), np.sin(winkel)])
    punkte = (radien[:, None, None] * kreis).reshape(-1, 2)
    seiten = _hoehen(netz, punkte).reshape(2, len(radien), -1)
    for seite, sinn in enumerate((1, -1)):
        profil = sinn * seiten[seite]
        signatur = []
        for vorne, hinten, r in zip(profil, seiten[1-seite], radien):
            z = 0
            if np.isfinite(vorne).all() and np.ptp(vorne) > .025*r and np.ptp(hinten) < .25*np.ptp(vorne):
                # Der Periodizitaetstest erwartet einen positiven Bezugsradius.
                z, _, amplitude = _zahn_harmonische(vorne - vorne.mean() + r)
                if amplitude < .025 or z > len(vorne)//8:
                    z = 0
            signatur.append(z)
        for z, gruppe in groupby(range(len(radien)), key=signatur.__getitem__):
            ids = list(gruppe)
            if not z or len(ids) < 4:
                continue
            r, ringe = radien[ids], profil[ids]
            kopf, fuss = np.percentile(ringe, (97, 3), axis=1)
            mitte = (kopf+fuss)/2
            m, b = np.polyfit(r, mitte, 1)
            hub = float((kopf-fuss)[len(ids)//2])
            if abs(m)*np.ptp(r) < max(.12*hub, .025*netz.r_max) or max(abs(mitte-(m*r+b))) > .12*hub:
                continue
            h = np.fft.rfft(ringe, axis=1)[:, z]
            if max(abs(np.angle(h[1:]/h[:-1]))) > .5:
                continue
            return Stirnzahnband(teil, z, punkt.copy(), sinn*achse, (float(r[0]), float(r[-1])),
                                 hub, float(np.degrees(np.arctan(abs(m)))))
    return None
