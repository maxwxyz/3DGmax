"""Stirnseitiges konisches oder ebenes Zahnband aus dem axialen Hoehenprofil konzentrischer Messkreise."""

from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr


@dataclass
class Kronenmessung:
    radien: np.ndarray
    richtungen: np.ndarray
    hoehen: np.ndarray
    fuss: float
    kopf: float


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
    art: str = "kegelrad_stirnseitig"
    kronenmessung: Kronenmessung | None = field(default=None, repr=False, compare=False)

    def als_dict(self):
        daten = {"art": self.art, "teil": self.teil, "koerper": self.koerper, "anzahl": self.z,
                "achse": {"punkt": self.punkt.tolist(), "richtung": self.richtung.tolist()},
                "messradien_mm": list(self.radien), "axiale_zahnhoehe_mitte_mm": self.relief,
                "neigung_mittelflaeche_grad": self.neigung, "einstufung": "kandidat"}
        if self.kronenmessung:
            daten.update(zahnfuss_axial_mm=self.kronenmessung.fuss, zahnkopf_axial_mm=self.kronenmessung.kopf)
        return daten

    def zeilen(self):
        quelle = tr("Axiale Höhenprofile auf Messkreisen")
        art = tr("Kronenrad-Kandidat") if self.art == "kronenrad" else tr("Kegelrad-Kandidat mit stirnseitiger Verzahnung")
        zeilen = [(tr("Art"), art, quelle),
                (tr("Zähnezahl z"), str(self.z), quelle),
                (tr("Radialer Messbereich"), f"{self.radien[0]:.3f} – {self.radien[1]:.3f} mm", quelle),
                (tr("Axiale Zahnhöhe am mittleren Messkreis"), f"{self.relief:.3f} mm", quelle),
                (tr("Neigung der mittleren Zahnfläche zur Radialebene"), f"{self.neigung:.2f}°", quelle)]
        if self.kronenmessung:
            zeilen.append((tr("Zahnfuß und Zahnkopf ab Achspunkt"),
                           f"{self.kronenmessung.fuss:.3f} / {self.kronenmessung.kopf:.3f} mm", quelle))
        return zeilen


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


def _messband(r, ringe, z, aussenradius):
    """Breitestes zusammenhaengendes Zahnband vor dem verrundeten Uebergang zum Innenbund."""
    kopf, fuss = np.percentile(ringe, (97, 3), axis=1)
    mitte = (kopf + fuss) / 2
    phase = np.fft.rfft(ringe, axis=1)[:, z]
    for start in range(min(len(r) // 3, len(r) - 4) + 1):
        radien = r[start:]
        m, b = np.polyfit(radien, mitte[start:], 1)
        hub = float((kopf-fuss)[start + len(radien)//2])
        if abs(m)*np.ptp(radien) < max(.12*hub, .025*aussenradius):
            continue
        if max(abs(mitte[start:] - (m*radien + b))) > .12*hub:
            continue
        if start:
            # Auch in der aeusseren Haelfte steigen Kopf und Fuss zum selben Kegelende.
            h = start + len(radien)//2
            if min(np.sign(m)*(kopf[-1]-kopf[h]), np.sign(m)*(fuss[-1]-fuss[h])) < .05*hub:
                continue
        if max(abs(np.angle(phase[start+1:]/phase[start:-1]))) <= .5:
            return (float(radien[0]), float(radien[-1])), hub, float(np.degrees(np.arctan(abs(m))))
    return None


def _kronenband(r, ringe, z):
    """Ebener Zahngrund mit nach aussen schmaler werdenden Koepfen und geneigten Flanken."""
    kopf, fuss = np.percentile(ringe, (97, 3), axis=1)
    hub = kopf - fuss
    hoehe = float(np.median(hub))
    if min(hub) < .75 * hoehe or np.ptp(fuss) > .12 * hoehe or np.ptp(kopf) > .25 * hoehe:
        return None
    phase = np.fft.rfft(ringe, axis=1)[:, z]
    if max(abs(np.angle(phase / phase[0]))) > .45:
        return None
    norm = (ringe - fuss[:, None]) / hub[:, None]
    # Auf dem Messkreis die Laenge oberhalb der Schwelle zwischen den Stuetzpunkten interpolieren.
    def anteil(grenze):
        a, b = norm - grenze, np.roll(norm, -1, axis=1) - grenze
        bruch = np.divide(a, a-b, out=np.zeros_like(a), where=(a > 0) != (b > 0))
        return np.where(a > 0, np.where(b > 0, 1., bruch), np.where(b > 0, 1.-bruch, 0.)).mean(axis=1)
    breit = anteil(.85)
    flanke = anteil(.15) - breit
    if min(flanke) < .15 or breit[0]-breit[-1] < .065 or flanke[-1]-flanke[0] < .045:
        return None
    if max(np.diff(breit)) > .035:
        return None
    steigung = np.polyfit(r, (kopf+fuss)/2, 1)[0]
    return (float(r[0]), float(r[-1])), float(hub[len(r)//2]), float(np.degrees(np.arctan(abs(steigung))))


def erkenne(netz, teil, punkt, achse):
    from itertools import groupby
    from .verzahnung import _zahn_harmonische
    radien = np.linspace(.40, .995, 35) * netz.r_max
    winkel = (np.arange(720) + .37) * (2*np.pi/720)
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
            krone = _kronenband(radien[ids], profil[ids], z)
            if krone:
                from .verzahnung import _basis
                richtungen = kreis @ np.array(_basis(achse))
                hoehen = profil[ids]
                fuss, kopf = np.median(np.percentile(hoehen, (3, 97), axis=1), axis=1)
                messung = Kronenmessung(radien[ids], richtungen, hoehen, float(fuss), float(kopf))
                return Stirnzahnband(teil, z, punkt.copy(), sinn*achse, *krone,
                                     art="kronenrad", kronenmessung=messung)
            # Bisherige Messkreise fuer das konische Band. Der aeusserste Rundungsbereich entfaellt.
            ids = [i for i in ids if i % 2 == 0 and i <= 32]
            if len(ids) < 4:
                continue
            messung = _messband(radien[ids], profil[ids], z, netz.r_max)
            if messung:
                return Stirnzahnband(teil, z, punkt.copy(), sinn*achse, *messung)
    return None
