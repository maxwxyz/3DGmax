"""Zahnmittellinie aus beiden Flanken einer konischen Verzahnung."""

from dataclasses import dataclass

import numpy as np


def _mittenphase(r, radius, z, referenz):
    """Zahnmitten am Schnittkreis; Phasenlage der gesamten Kontur loest die Zahnteilung auf."""
    aussen = r > radius
    kanten = np.flatnonzero(aussen != np.roll(aussen, -1))
    if len(kanten) != 2 * z:
        return None
    folge = (kanten + 1) % len(r)
    lage = kanten + (radius - r[kanten]) / (r[folge] - r[kanten])
    # Erst aufsteigende Flanke, dann absteigende Flanke desselben Zahns.
    if aussen[kanten[0]]:
        lage = np.append(lage[1:], lage[0] + len(r))
    mitten = (lage[::2] + lage[1::2]) * (np.pi / len(r)) - np.pi
    differenzen = np.angle(np.exp(1j * z * (mitten - referenz)))
    mittel = np.angle(np.exp(1j * differenzen).mean())
    if np.max(np.abs(np.angle(np.exp(1j * (differenzen - mittel))))) > .15 or abs(mittel) > np.pi / 2:
        return None
    return referenz + mittel / z


@dataclass
class Kegelspur:
    stationen: np.ndarray  # Axialpositionen ab Beginn des Messbereichs, vom kleinen zum grossen Ende
    konturen: list
    phasen: np.ndarray  # Entfaltete Winkel der Zahnharmonischen in der Basis des Schnittnetzes
    achssinn: int  # Orientierung der Schnittbasis gegen die Achse zum grossen Ende
    z: int

    def winkel(self, radien):
        werte = [_mittenphase(r, radius, self.z, phi)
                 for r, radius, phi in zip(self.konturen, radien, self.phasen, strict=True)]
        if all(v is not None for v in werte):
            return self.achssinn * np.asarray(werte)

    def richtung(self):
        """Am Einzelrad die Hand nur aus uebereinstimmenden Spuren auf mehreren Zahnhoehen."""
        richtungen, spuren = set(), []
        for anteil in (.25, .5, .75):
            radien = [r.min() + anteil * np.ptp(r) for r in self.konturen]
            phi = self.winkel(radien)
            if phi is None:
                return None
            spuren.append(phi)
            weg = (phi[-1] - phi[0]) * self.z
            if np.ptp(phi) * self.z < .01:
                richtungen.add("gerade")
            elif abs(weg) > .04 and np.all(np.diff(phi) * self.z * np.sign(weg) >= -.01):
                richtungen.add("rechts" if weg > 0 else "links")
            else:
                return None
        if richtungen == {"gerade"} and np.ptp(spuren) * self.z >= .01:
            return None
        if len(richtungen) == 1:
            return richtungen.pop()

    def spiralwinkel(self, spitze, delta, mitte):
        """Lokale Tangente in Zahnmitte am mittleren Kegelabstand, tan(beta) = r * d(phi)/dR."""
        r = (self.stationen - spitze) * np.tan(delta)
        phi = self.winkel(r)
        if phi is None:
            return None
        abstand = self.stationen - mitte
        # Zwei ineinanderliegende Umgebungen: die Ableitung muss lokal stabil sein.
        nah = np.argsort(abs(abstand))
        if len(nah) < 6:
            return None
        r_m = (mitte - spitze) * np.tan(delta)
        winkel = []
        for ind in (nah[:6], nah[:4]):
            x = abstand[ind]
            if min(x) >= 0 or max(x) <= 0:
                return None
            fit = np.polyfit(x, phi[ind] - phi[ind[0]], 2)
            if np.max(abs(np.polyval(fit, x) - (phi[ind] - phi[ind[0]]))) * self.z > .025:
                return None
            winkel.append(float(np.degrees(np.arctan(r_m * np.cos(delta) * fit[1]))))
        if abs(winkel[1] - winkel[0]) <= .5:
            return winkel[1]
