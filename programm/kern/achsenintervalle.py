"""Stuetzfunktion einer starren Achse in mehreren koaxialen Zylindertoleranzen."""

from itertools import combinations

import numpy as np


def _hub(kraft, moment, radius, kippung2, skalar):
    """Optimale Drehung zweier Radialvektoren bei vorgegebenen Laengen und Skalarprodukt."""
    produkt = radius * np.sqrt(np.maximum(kippung2, 0.))
    skalar = np.clip(skalar, -produkt, produkt)
    flaeche = np.sqrt(np.maximum(0., (produkt - skalar) * (produkt + skalar)))
    quadrat = ((kraft @ kraft) * radius**2 + (moment @ moment) * kippung2
               + 2 * ((kraft @ moment) * skalar + np.linalg.norm(np.cross(kraft, moment)) * flaeche))
    return np.sqrt(np.maximum(0., quadrat))


def _paarhub(kraft, moment, positionen, si, sj, kippgrenze):
    """Zwei aktive Positionskreise. Der quadratische Verlauf des Radialabstands bindet alle anderen."""
    ri, rj = positionen[si], positionen[sj]
    ds = sj - si
    last_j = moment / ds
    last_i = kraft - last_j
    # q = Quadrat der Kippung. In dieser Koordinate bleiben auch dicht benachbarte Endlagen auswertbar.
    unten = ((ri - rj) / ds)**2
    oben = np.minimum(((ri + rj) / ds)**2, kippgrenze**2)
    steigung = (rj - ri) * (rj + ri) / ds
    for s, r in positionen.items():
        if s == si or s == sj:
            continue
        faktor = (s - si) * (s - sj)
        grenze = ((r - ri) * (r + ri) - steigung * (s - si)) / faktor
        if faktor > 0:
            oben = np.minimum(oben, grenze)
        else:
            unten = np.maximum(unten, grenze)
    ni, nj = np.linalg.norm(last_i), np.linalg.norm(last_j)
    sehne2 = np.sum((last_i / ni - last_j / nj)**2) if ni and nj else 0.
    ideal = ((ri - rj)**2 + ri * rj * sehne2) / ds**2
    q = np.maximum(0., np.clip(ideal, unten, oben))
    wert = _hub(kraft, moment, ri, q, (steigung - ds * q) / 2)
    return np.where(unten <= oben + 32 * np.finfo(float).eps * unten, wert, 0.)


def _kipphub(kraft, moment, positionen, si, kippgrenze):
    """Kippgrenze und ein Positionskreis aktiv; andere Kreise begrenzen ihr Skalarprodukt."""
    ri = positionen[si]
    produkt = ri * kippgrenze
    unten, oben = -produkt, produkt
    for s, r in positionen.items():
        if s == si:
            continue
        ds = s - si
        grenze = ((r - ri) * (r + ri) - (ds * kippgrenze)**2) / (2 * ds)
        if ds > 0:
            oben = np.minimum(oben, grenze)
        else:
            unten = np.maximum(unten, grenze)
    norm = np.linalg.norm(kraft) * np.linalg.norm(moment)
    ideal = produkt * (kraft @ moment) / norm if norm else 0.
    wert = _hub(kraft, moment, ri, kippgrenze**2, np.clip(ideal, unten, oben))
    return np.where(unten <= oben + 32 * np.finfo(float).eps * produkt, wert, 0.)


def intervallhub(radial, winkel, intervalle, durchmesser, richtungen):
    """Hub am Messort; Durchmesser duerfen Arrays der Istmass-Stichproben sein.

    Radialversatz am normierten Ort s ist u+s*v. Positionszonen binden an beiden Enden,
    frei verschiebbare Richtungszonen nur die Differenz ihrer Endverschiebungen.
    """
    positionen, kippgrenze = {}, None
    for (lo, hi), t, richtung in zip(intervalle, durchmesser, richtungen, strict=True):
        if richtung:
            grenze = t / (hi - lo)
            kippgrenze = grenze if kippgrenze is None else np.minimum(kippgrenze, grenze)
        else:
            for s in (lo, hi):
                positionen[s] = np.minimum(positionen.get(s, np.inf), t / 2)
    if not positionen:
        return kippgrenze * np.linalg.norm(winkel)

    # Parallele Lasten: Streifenschnitt in zwei Skalaren, das LP-Dual braucht hoechstens zwei Zeilen.
    # Bei unabhaengigen Lasten traegt ein einzelner aktiver Kreis nicht beide Kraefte.
    parallel = np.linalg.norm(np.cross(radial, winkel)) <= (
        8 * np.finfo(float).eps * np.linalg.norm(radial) * np.linalg.norm(winkel))
    obergrenze, maximum = np.inf, 0.
    for si, sj in combinations(sorted(positionen), 2):
        moment = winkel - si * radial
        am_ende = moment / (sj - si)
        grenze = np.linalg.norm(radial - am_ende) * positionen[si] + np.linalg.norm(am_ende) * positionen[sj]
        obergrenze = np.minimum(obergrenze, grenze)
        if not parallel:
            maximum = np.maximum(maximum, _paarhub(radial, moment, positionen, si, sj,
                                                   np.inf if kippgrenze is None else kippgrenze))
    if kippgrenze is not None:
        for si, ri in positionen.items():
            moment = winkel - si * radial
            obergrenze = np.minimum(obergrenze, np.linalg.norm(radial) * ri + np.linalg.norm(moment) * kippgrenze)
            if not parallel:
                maximum = np.maximum(maximum, _kipphub(radial, moment, positionen, si, kippgrenze))
    return obergrenze if parallel else np.minimum(obergrenze, maximum)
