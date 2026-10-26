"""Grenzabmasse aus ISO-286-Toleranzklassen (z. B. H7, g6, JS9) fuer Nennmasse bis 500 mm.

Grundlage ISO 286-1: Grundtoleranzen IT1..IT18 (Tabelle) und Grundabmasse der Buchstaben; Bohrungen aus den
Wellenwerten nach den Regeln der Norm (Spiegelung, Delta-Regel fuer K, M, N bis IT8 und P, R, S bis IT7).
Abgeglichen mit unabhaengigen Tabellen (Test). Werte in Mikrometern, Ergebnis in mm.
Unterstuetzt: Wellen c d e f g h js k m n p r s, Bohrungen C D E F G H JS K M N P R S.
"""

from __future__ import annotations

import bisect
import re

# Nennmassbereiche "ueber .. bis einschliesslich" (Hauptbereiche)
HAUPT = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]
# Grundtoleranzen in um je Hauptbereich
IT = {
    1: [0.8, 1, 1, 1.2, 1.5, 1.5, 2, 2.5, 3.5, 4.5, 6, 7, 8],
    2: [1.2, 1.5, 1.5, 2, 2.5, 2.5, 3, 4, 5, 7, 8, 9, 10],
    3: [2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15],
    4: [3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20],
    5: [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6: [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7: [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8: [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9: [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
    12: [100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630],
    13: [140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970],
    14: [250, 300, 360, 430, 520, 620, 740, 870, 1000, 1150, 1300, 1400, 1550],
    15: [400, 480, 580, 700, 840, 1000, 1200, 1400, 1600, 1850, 2100, 2300, 2500],
    16: [600, 750, 900, 1100, 1300, 1600, 1900, 2200, 2500, 2900, 3200, 3600, 4000],
    17: [1000, 1200, 1500, 1800, 2100, 2500, 3000, 3500, 4000, 4600, 5200, 5700, 6300],
    18: [1400, 1800, 2200, 2700, 3300, 3900, 4600, 5400, 6300, 7200, 8100, 8900, 9700],
}
# Grundabmasse der Wellen in um je Hauptbereich: oberes Abmass es (negativ) fuer d..g, unteres ei fuer k..p
WELLE = {
    "d": [-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230],
    "e": [-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135],
    "f": [-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68],
    "g": [-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20],
    "h": [0] * 13,
    "k": [0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5],  # nur IT4..IT7, sonst 0
    "m": [2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
    "n": [4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40],
    "p": [6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68],
}
# Buchstaben mit feiner unterteilten Bereichen
FEIN = [3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450,
        500]
WELLE_FEIN = {
    "c": [-60, -70, -80, -95, -95, -110, -110, -120, -130, -140, -150, -170, -180, -200, -210, -230, -240, -260,
          -280, -300, -330, -360, -400, -440, -480],
    "r": [10, 15, 19, 23, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108, 114, 126, 132],
    "s": [14, 19, 23, 28, 28, 35, 35, 43, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140, 158, 170, 190, 208, 232,
          252],
}
OBEN_ART = set("cdefgh")  # Grundabmass ist das obere Abmass
BUCHSTABEN = set(WELLE) | set(WELLE_FEIN) | {"js"}
_KLASSE = re.compile(r"^\s*([A-Za-z]{1,2})\s*(\d{1,2})\s*$")


def _bereich(d: float, grenzen: list) -> int | None:
    if d <= 0 or d > grenzen[-1]:
        return None
    return bisect.bisect_left(grenzen, d)


def it(grad: int, nennmass: float) -> float | None:
    """Grundtoleranz in um oder None (Grad oder Mass ausserhalb)."""
    i = _bereich(nennmass, HAUPT)
    if i is None or grad not in IT:
        return None
    return float(IT[grad][i])


def _grundabmass_welle(b: str, grad: int, d: float) -> float | None:
    if b in WELLE_FEIN:
        i = _bereich(d, FEIN)
        return None if i is None else float(WELLE_FEIN[b][i])
    i = _bereich(d, HAUPT)
    if i is None:
        return None
    if b == "k" and not 4 <= grad <= 7:
        return 0.0
    return float(WELLE[b][i])


def _delta(grad: int, d: float) -> float:
    """Delta = IT(n) - IT(n-1) fuer n = 3..8, bei Nennmassen bis 3 mm null."""
    if d <= 3 or not 3 <= grad <= 8:
        return 0.0
    return it(grad, d) - it(grad - 1, d)


def abmasse_um(klasse: str, nennmass: float) -> tuple[float, float] | None:
    """(oberes, unteres) Abmass in um fuer z. B. 'H7', 'g6', 'JS9'; None wenn nicht unterstuetzt."""
    m = _KLASSE.match(klasse or "")
    if not m:
        return None
    buchstabe, grad = m.group(1), int(m.group(2))
    bohrung = buchstabe[0].isupper()
    b = buchstabe.lower()
    if b not in BUCHSTABEN or (buchstabe != buchstabe.upper() and buchstabe != buchstabe.lower()):
        return None
    t = it(grad, nennmass)
    if t is None:
        return None
    if b == "js":
        return t / 2, -t / 2
    fd = _grundabmass_welle(b, grad, nennmass)
    if fd is None:
        return None
    if not bohrung:
        return (fd, fd - t) if b in OBEN_ART else (fd + t, fd)
    # Bohrungen: A..H gespiegelt (EI = -es), K..S ueber ES = -ei (+ Delta bis IT8 bzw. IT7)
    if b in OBEN_ART:
        return -fd + t, -fd
    if b == "k":
        kfd = _grundabmass_welle("k", 6, nennmass)  # Wert fuer IT4..IT7
        es = -kfd + _delta(grad, nennmass) if grad <= 8 else 0.0
    elif b == "m":
        es = -fd + _delta(grad, nennmass) if grad <= 8 else -fd
        if grad == 6 and 250 < nennmass <= 315:
            es = -9.0  # Sonderfall der Norm (statt -11)
    elif b == "n":
        es = -fd + _delta(grad, nennmass) if grad <= 8 else (0.0 if nennmass > 3 else -fd)
    else:  # p, r, s
        es = -fd + _delta(grad, nennmass) if grad <= 7 else -fd
    return es, es - t


def grenzabmasse(klasse: str, nennmass: float) -> tuple[float, float] | None:
    """(oberes, unteres) Abmass in mm."""
    a = abmasse_um(klasse, nennmass)
    return None if a is None else (a[0] / 1000.0, a[1] / 1000.0)
