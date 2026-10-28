"""Wiggle der Schlussflaechen einer Toleranzkette (PLAN §8.33, Punkt 3 der Abendreihe, ohne Qt).

Das Schlussmass liegt zwischen der ersten Flaeche des ersten und der letzten Flaeche des letzten Glieds mit Flaechen.
Fuer die Anzeige pendelt die Endflaeche entlang der Kettenrichtung zwischen Worst-Case-Minimum und -Maximum; die
Bewegung wird ueberhoeht, damit auch Hundertstel sichtbar sind (Faktor in der Beschriftung). Je Bild: Versatz der
Flaeche (mm, ueberhoeht), Wert des Schlussmasses und Bewertung gegen die Anforderung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import toleranzkette as tk

SCHRITTE = 36  # Bilder je Hin und Her


@dataclass
class Schluss:
    start: int  # ruhende Schlussflaeche (Index im Modell)
    ende: int  # bewegte Schlussflaeche
    richtung: np.ndarray  # Einheitsvektor, in dem das Schlussmass waechst


@dataclass
class Bild:
    versatz: np.ndarray  # Verschiebung der Endflaeche (mm, ueberhoeht)
    wert: float  # Schlussmass in diesem Bild
    stufe: str  # "gruen" | "rot" | "" (ohne Anforderung)


def schlussflaechen(glieder: list, modell) -> Schluss | None:
    """Erste Flaeche des ersten und letzte Flaeche des letzten Glieds mit zwei Flaechen; Richtung, in der das
    Schlussmass waechst (von der Start- weg zur Endflaeche); None ohne passende Flaechen."""
    mit = [g for g in glieder if len([i for i in g.flaechen if isinstance(i, int)]) >= 2]
    if not mit:
        return None
    start, ende = mit[0].flaechen[0], mit[-1].flaechen[-1]
    if start == ende or max(start, ende) >= len(modell.flaechen):
        return None
    strecke = tk.glied_strecke(mit[0], modell)
    if strecke is None:
        return None
    n = np.subtract(strecke[1], strecke[0])
    if np.linalg.norm(n) < 1e-12:
        geo = tk._ebene_oder_achse(modell.flaechen[start])
        if geo is None or geo[0] != "ebene":
            return None
        n = np.asarray(geo[2], float)
    n = n / np.linalg.norm(n)
    a, b = tk.lage(modell.flaechen[start], n), tk.lage(modell.flaechen[ende], n)
    if a is None or b is None:
        return None
    return Schluss(start, ende, n if b >= a else -n)


def faktor(e, groesse: float) -> float:
    """Ueberhoehung: der Worst-Case-Bereich soll etwa ein Zwanzigstel der Modellgroesse ausmachen (mindestens 1)."""
    breite = e.wc_max - e.wc_min
    return max(1.0, groesse / 20.0 / breite) if breite > 1e-12 else 1.0


def bilder(schluss: Schluss, e, anforderung: tuple | None, ueberhoehung: float,
           schritte: int = SCHRITTE) -> list[Bild]:
    """Ein Hin und Her zwischen Worst-Case-Minimum und -Maximum (Sinus, verweilt an den Grenzen)."""
    mitte, halb = (e.wc_min + e.wc_max) / 2, (e.wc_max - e.wc_min) / 2
    out = []
    for k in range(schritte):
        wert = mitte + halb * math.sin(2 * math.pi * k / schritte)
        stufe = ""
        if anforderung is not None:
            u, o = anforderung
            ok = (u is None or wert >= u - 1e-12) and (o is None or wert <= o + 1e-12)
            stufe = "gruen" if ok else "rot"
        out.append(Bild(schluss.richtung * (wert - e.nenn) * ueberhoehung, float(wert), stufe))
    return out
