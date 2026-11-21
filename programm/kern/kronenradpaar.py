"""Kronenrad und Stirnritzel an ihren eingebauten Zahnbaendern abrollen."""

from dataclasses import dataclass

import numpy as np

from ..i18n import tr
from .stirnzahnband import Stirnzahnband
from .verzahnung import Verzahnung, _basis


@dataclass
class Kronenradpaar:
    a: Stirnzahnband
    b: Verzahnung
    messbereich: tuple
    seite: int

    def drehsinn(self, kronenachse, ritzelachse):
        """Relativer Drehsinn bezogen auf die positiven Wellenachsen."""
        orientierung = (self.a.richtung @ kronenachse) * (self.b.richtung @ ritzelachse)
        return self.seite if orientierung > 0 else -self.seite

    def zeilen(self):
        return [(tr("Zuordnung"), tr("Mögliche Kronenradstufe")),
                (tr("Gemeinsamer radialer Messbereich"),
                 f"{self.messbereich[0]:.3f} – {self.messbereich[1]:.3f} mm"),
                (tr("Übersetzung Ritzel → Kronenrad"), f"{self.a.z/self.b.z:.5g}")]

    def als_dict(self):
        return {"teile": [self.a.teil, self.b.teil], "messradien_mm": list(self.messbereich),
                "i_ritzel_kronenrad": self.a.z/self.b.z, "einstufung": "kandidat"}


def _abrollen(krone, ritzel, seite):
    """Radiale Konturabstaende bei neun gekoppelten Drehstellungen ueber eine Zahnteilung."""
    band = krone.kronenmessung
    u, v = _basis(ritzel.richtung)
    basis = np.array([u, v, ritzel.richtung]).T
    normal = krone.richtung
    kreis = band.richtungen @ basis
    tangente = np.cross(normal, band.richtungen) @ basis
    radius = band.radien[:, None, None]
    niveau = ((krone.punkt-ritzel.punkt) @ basis
              + band.hoehen[:, :, None] * (normal @ basis))
    umfang = len(ritzel.r_mitte)
    kontur_r = np.append(ritzel.r_mitte, ritzel.r_mitte[0])
    raster = np.arange(umfang+1)
    spielraum = .09 * krone.relief
    for schritt in range(9):
        phase = 2*np.pi * schritt/9
        winkel = phase/krone.z
        punkte = niveau + radius * (np.cos(winkel)*kreis + np.sin(winkel)*tangente)
        im_band = abs(punkte[:, :, 2]) <= ritzel.b/2
        if np.count_nonzero(im_band.any(axis=1)) < 2:
            return False
        x, y, _ = punkte[im_band].T
        phi = np.arctan2(y, x) - seite*phase/ritzel.z
        index = ((phi/(2*np.pi)+.5) % 1)*umfang
        kontur = np.interp(index, raster, kontur_r)
        # Zu tiefes Eindringen oder durchgehender Abstand widersprechen dem Eingriff.
        mindestabstand = np.min(np.hypot(x, y)-kontur)
        if not -spielraum <= mindestabstand <= spielraum:
            return False
    return True


def _paar(krone, ritzel):
    band = krone.kronenmessung
    normal, achse = krone.richtung, ritzel.richtung
    if abs(normal @ achse) > np.sin(np.deg2rad(.5)):
        return None
    if krone.koerper_id is not None and krone.koerper_id == ritzel.koerper_id:
        return None
    abstand = ritzel.punkt - krone.punkt
    if abs(abstand @ np.cross(normal, achse)) > .025*krone.relief:
        return None
    hoehe = abstand @ normal
    if not (band.fuss-.1*krone.relief < hoehe-ritzel.da/2 < band.fuss+.5*krone.relief
            and band.kopf-.1*krone.relief < hoehe-ritzel.df/2 < band.kopf+.6*krone.relief):
        return None
    axial = abstand @ achse
    innen, aussen = abs(axial)-ritzel.b/2, abs(axial)+ritzel.b/2
    if innen <= -band.radien[0]:
        return None  # Ein Ritzel ueber beide Eingriffsseiten liefert keine eindeutige Stufe.
    auswahl = (band.radien >= innen) & (band.radien <= aussen)
    if np.count_nonzero(auswahl) < 2:
        return None
    gemeinsam = band.radien[auswahl]
    seite = 1 if axial > 0 else -1
    if _abrollen(krone, ritzel, seite):
        return Kronenradpaar(krone, ritzel, (float(gemeinsam[0]), float(gemeinsam[-1])), seite)
    return None


def kronenradpaare(liste):
    """Nur gerade Aussenritzel mit gemessenem Evolventenprofil pruefen."""
    kronen = [v for v in liste if isinstance(v, Stirnzahnband) and v.kronenmessung is not None]
    ritzel = [v for v in liste if isinstance(v, Verzahnung) and not (v.innen or v.welle or v.hand)
              and v.beta < .05 and v.db > 0 and v.r_mitte is not None]
    return [paar for krone in kronen for rad in ritzel if (paar := _paar(krone, rad)) is not None]
