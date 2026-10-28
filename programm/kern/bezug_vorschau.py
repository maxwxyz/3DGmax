"""Vorschau des Bezugssystems aus Funktion -> Tolerierung (ohne Qt): welche Freiheitsgrade A, B und C sperren und
welche offen bleiben - aus der Geometrie gerechnet wie die Verbindungen im Zusammenbau (kern.verbindung): eine
Bezugsebene sperrt wie eine ebene Auflage (Verschiebung entlang der Normalen, Kippen), eine Bezugsachse wie ein
Zylindersitz (Verschiebung quer, Kippen der Achse). Die Reihenfolge A, B, C ergibt den Vorrang: jeder Bezug sperrt
nur, was die vorigen noch offen liessen."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import funktion as fu
from . import verbindung as vb


@dataclass
class Bewegung:
    art: str  # "verschiebung" oder "drehung"
    richtung: np.ndarray
    punkt: np.ndarray | None = None  # Punkt der Drehachse (nur Drehung)


@dataclass
class Vorschau:
    gesperrt: dict[str, int] = field(default_factory=dict)  # Buchstabe -> neu gesperrte Freiheitsgrade
    offen: list[Bewegung] = field(default_factory=list)


def _zeilen(g: dict) -> list[np.ndarray]:
    """Gesperrte kleine Bewegungen eines Bezugselements (Ebene wie ebene Auflage, Achse wie Zylindersitz)."""
    e = np.asarray(g["richtung"], float)
    e = e / np.linalg.norm(e)
    q = np.asarray(g["punkt"], float)
    return vb.bedingungen(vb.EBEN if g["art"] == "ebene" else "zylinder", (g["art"], q, e))


def _rang(zeilen: list[np.ndarray]) -> int:
    return 6 - len(vb.freiheitsgrade(zeilen)) if zeilen else 0


def vorschau(modell, system: fu.Bezugssystem, gruppen: dict | None = None) -> Vorschau:
    """Gesperrte Freiheitsgrade je Bezug (in der Reihenfolge A, B, C) und die offenen Bewegungen."""
    out, zeilen = Vorschau(), []
    for b in sorted(system.bezuege, key=lambda b: b.buchstabe):
        g = fu._geo(modell, b.flaeche, gruppen)
        if g is None:
            continue
        vorher = _rang(zeilen)
        zeilen += _zeilen(g)
        out.gesperrt[b.buchstabe] = _rang(zeilen) - vorher
    for z in vb.freiheitsgrade(zeilen):
        art, richtung, punkt = vb._gerade_ausrichten(z[:3], z[3:])
        out.offen.append(Bewegung(art, richtung, punkt))
    return out
