"""Wiggle der Schlussflaechen einer Toleranzkette (PLAN §8.33, Punkt 3 der Abendreihe, ohne Qt).

Das Schlussmass liegt zwischen dem Anfang des ersten und dem Ende des letzten Glieds, wenn die Glieder mit ihren
Flaechen entlang der Kettenrichtung hintereinander liegen (schluss_oder_grund, sonst ein Grund fuer den Nutzer).
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
    """Schlussflaechen der Kette (siehe schluss_oder_grund); None ohne passende Flaechen."""
    return schluss_oder_grund(glieder, modell)[0]


def schluss_oder_grund(glieder: list, modell) -> tuple[Schluss | None, str]:
    """(Schlussflaechen, "") oder (None, Grund fuer den Nutzer). Zuerst ueber die Lagen: die Glieder laufen entlang
    der Kettenrichtung hintereinander (jedes beginnt, wo das vorige endet; Musterflaechen gleicher Lage zaehlen als
    eine), Anfang des ersten und Ende des letzten Glieds sind die Schlussflaechen. Die fruehere Regel (erste Flaeche
    des ersten, letzte des letzten Glieds) traf je nach Reihenfolge der Flaechen im Glied die falsche Flaeche."""
    from ..i18n import tr
    if modell is None:
        return None, tr("Wiggle braucht das Modell der Kette")
    if not any(len(_flaechen(g, modell)) >= 2 for g in glieder):
        return None, tr("Die Glieder haben keine Modellflächen (aus einer 2D-/3D-Kette übernommen oder von Hand "
                        "angelegt) – der Wiggle braucht eine Kette aus Modellflächen („Aus 3D-Auswahl“); eine 3D-Kette "
                        "zeigt ihren Wiggle im Fenster 3D-Toleranzkette")
    masse = [g for g in glieder if g.quelle != "lage" and abs(g.nenn) > 1e-9]
    if not masse:
        return None, tr("Wiggle braucht Maßglieder mit Modellflächen")
    s = _ueber_lagen(masse, modell)
    if s is not None:
        return s, ""
    return None, tr("Die Flächen der Glieder liegen nicht in Kettenreihenfolge hintereinander (z. B. Maße aus der "
                    "PMI-Liste) – „Richtungen aus Schlussmaß“ ordnet die Kette, oder Flächen mit „Aus 3D-Auswahl“")


def _flaechen(g, modell) -> list[int]:
    return [i for i in g.flaechen if isinstance(i, int) and i < len(modell.flaechen)]


def _richtung(glieder: list, modell) -> np.ndarray | None:
    """Kettenrichtung: Normale der ersten ebenen Gliedflaeche."""
    for g in glieder:
        for i in _flaechen(g, modell):
            geo = tk._ebene_oder_achse(modell.flaechen[i])
            if geo is not None and geo[0] == "ebene":
                return np.asarray(geo[2], float) / np.linalg.norm(geo[2])
    return None


def _ueber_lagen(glieder: list, modell) -> Schluss | None:
    """Kette ablaufen: Schritt je Glied Richtung x Nennmass x Faktor; ein Glied mit Flaechen muss an der aktuellen
    Lage beginnen und an der neuen enden. Glieder ohne Flaechen gehen nur rechnerisch weiter."""
    n = _richtung(glieder, modell)
    if n is None:
        return None
    orte = []
    for g in glieder:
        o = {}
        for i in _flaechen(g, modell):
            x = tk.lage(modell.flaechen[i], n)
            if x is None:
                return None  # Flaeche nicht quer zur Kettenrichtung
            o.setdefault(round(x, 3), i)
        orte.append(o)
    for vz in (1.0, -1.0):
        p, start, ende = None, None, None
        for g, o in zip(glieder, orte):
            schritt = vz * g.richtung * g.nenn * g.faktor
            if len(o) < 2 or g.faktor != 1:
                if p is None:
                    break  # Anfang ohne Flaeche (oder Mittelebene): nicht bestimmbar
                p += schritt
                continue
            if p is None:
                p = next((a for a in o if _bei(o, a + schritt) is not None), None)
                if p is None:
                    break
                start = o[p]
            elif _bei(o, p) is None or _bei(o, p + schritt) is None:
                break
            p += schritt
            ende = _bei(o, p)
        else:
            if start is not None and ende is not None and start != ende:
                return Schluss(start, ende, n * vz)
    return None


def _bei(orte: dict, x: float) -> int | None:
    """Flaeche an der Lage x (auf 1/1000 mm)."""
    return next((i for a, i in orte.items() if abs(a - x) < 2e-3), None)


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
