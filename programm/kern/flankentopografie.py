"""Zahnflanken ueber Rollradius und Zahnbreite gegen die angepasste Evolvente messen."""

from __future__ import annotations

import math

import numpy as np


def _flankenwinkel(kontur, radius, z, innen):
    """Kreismittel der linken und rechten Materialgrenze aller Zaehne auf einem Messkreis."""
    a = np.asarray(kontur)
    b = np.roll(a, -1)
    material = a < radius if innen else a > radius
    danach = np.roll(material, -1)
    out = []
    for k in (np.flatnonzero(~material & danach), np.flatnonzero(material & ~danach)):
        if len(k) != z:
            return None
        theta = -math.pi + (k + (radius - a[k]) / (b[k] - a[k])) * (2 * math.pi / len(a))
        mittel = np.exp(1j * z * theta).mean()
        if abs(mittel) < 0.95:
            return None
        out.append(np.angle(mittel) / z)
    return np.asarray(out)


def karte(rad, profil):
    """Stirnschnitt-Abweichung je Flanke in mm, ueber die Zaehne gemittelt; unmessbare Felder bleiben leer."""
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
            ref.append(np.exp(1j * rad.z * (ist - ideal[i])))
    if not ref:
        return None
    ideal += np.angle(np.mean(ref, axis=0)) / rad.z
    dreh = math.tan(math.radians(rad.beta)) / (rad.d / 2) * (-1 if rad.hand == "links" else 1)
    links, rechts = [], []
    for ort, kontur in rad.r_schnitte:
        l, r = [], []
        for i, radius in enumerate(radien):
            ist = _flankenwinkel(kontur, radius, rad.z, rad.innen)
            if ist is None:
                l.append(None)
                r.append(None)
            else:
                delta = np.angle(np.exp(1j * rad.z * (ist - ideal[i] - ort * dreh))) / rad.z
                l.append(float(delta[0] * rb))
                r.append(float(-delta[1] * rb))
        links.append(l)
        rechts.append(r)
    return {"axial_mm": [float(s) for s, _ in rad.r_schnitte], "radius_mm": radien.tolist(),
            "links_mm": links, "rechts_mm": rechts}
