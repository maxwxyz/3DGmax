"""Zahnflanken ueber Rollradius und Zahnbreite gegen die angepasste Evolvente messen."""

from __future__ import annotations

import math

import numpy as np


def _flankenwinkel(kontur, radius, z, innen):
    """Kreismittel und Spannweite der Flankenlagen um die gleichmaessige Zahnteilung."""
    a = np.asarray(kontur)
    b = np.roll(a, -1)
    material = a < radius if innen else a > radius
    danach = np.roll(material, -1)
    phasen, spannweiten = [], []
    teilung = 2 * math.pi / z
    for k in (np.flatnonzero(~material & danach), np.flatnonzero(material & ~danach)):
        if len(k) != z:
            return None
        theta = -math.pi + (k + (radius - a[k]) / (b[k] - a[k])) * (2 * math.pi / len(a))
        mittel = np.exp(1j * z * theta).mean()
        if abs(mittel) < 0.95:
            return None
        phase = np.angle(mittel) / z
        sektoren = np.rint((theta - phase) / teilung)
        if np.any(np.diff(sektoren) != 1):
            return None  # Ein fehlender und ein doppelter Durchgang koennen sich in der Anzahl aufheben.
        phasen.append(phase)
        spannweiten.append(np.ptp(theta - sektoren * teilung))
    return np.asarray(phasen), np.asarray(spannweiten)


def spannweite_am_teilkreis(rad, profil):
    """Groesste Links-/Rechts-Spannweite am Teilkreis ueber die auswertbaren Stirnschnitte."""
    if profil is None or not profil.radien[0] <= rad.d / 2 <= profil.radien[-1]:
        return None
    werte = []
    for _, kontur in rad.r_schnitte:
        messung = _flankenwinkel(kontur, rad.d / 2, rad.z, rad.innen)
        if messung is not None:
            werte.append(messung[1] * profil.grundradius)
    return np.max(werte, axis=0) if werte else None


def karte(rad, profil):
    """Mittel und Zahn-zu-Zahn-Spannweite je Flanke in mm; unmessbare Felder bleiben leer."""
    if profil is None or not rad.r_schnitte or rad.d <= 0:
        return None
    rb = profil.grundradius
    radien = np.unique(np.append(profil.radien[::6], profil.radien[-1]))
    radien = radien[radien <= profil.dff / 2 if rad.innen else radien >= profil.dff / 2]
    if len(radien) < 4:
        return None
    alpha = np.arccos(np.clip(rb / radien, 0, 1))
    inv = (np.tan(alpha) - alpha) * (-1 if rad.innen else 1)
    ideal = np.column_stack([inv, -inv])
    # Phasenlage beider idealen Flanken am unmodifizierten mittleren Profil verankern.
    ref = []
    for i in range(len(radien) // 3, 2 * len(radien) // 3):
        ist = _flankenwinkel(rad.r_mitte, radien[i], rad.z, rad.innen)
        if ist is not None:
            ref.append(np.exp(1j * rad.z * (ist[0] - ideal[i])))
    if not ref:
        return None
    ideal += np.angle(np.mean(ref, axis=0)) / rad.z
    dreh = math.tan(math.radians(rad.beta)) / (rad.d / 2) * (-1 if rad.hand == "links" else 1)
    karten = {k: [] for k in ("links_mm", "rechts_mm", "spannweite_links_mm", "spannweite_rechts_mm")}
    for ort, kontur in rad.r_schnitte:
        for reihen in karten.values():
            reihen.append([])
        for i, radius in enumerate(radien):
            ist = _flankenwinkel(kontur, radius, rad.z, rad.innen)
            if ist is None:
                for reihen in karten.values():
                    reihen[-1].append(None)
                continue
            phasen, spannweiten = ist
            delta = np.angle(np.exp(1j * rad.z * (phasen - ideal[i] - ort * dreh))) / rad.z
            karten["links_mm"][-1].append(float(delta[0] * rb))
            karten["rechts_mm"][-1].append(float(-delta[1] * rb))
            karten["spannweite_links_mm"][-1].append(float(spannweiten[0] * rb))
            karten["spannweite_rechts_mm"][-1].append(float(spannweiten[1] * rb))
    return {"axial_mm": [float(s) for s, _ in rad.r_schnitte], "radius_mm": radien.tolist(),
            **karten}
