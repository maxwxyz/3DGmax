"""Zweidimensionale Toleranzkette als Vektorzug (PLAN §8.33 Stufe 4, ohne Qt).

Die Kette ist ein Zug von Segmenten in einer Ebene: jedes Segment hat eine Laenge und einen Winkel zum vorigen
Segment (das erste zur X-Achse), beide mit Abmassen und Verteilung. Die Schlussgroesse ist eine Funktion des Zugs:
Abstand vom Ende zum Anfang, X- oder Y-Anteil dieses Schlussvektors, oder die Richtung des letzten Segments.

Rechnung nach der Direkten Linearisierungsmethode (Vektorzug, Chase/Gao/Magleby): Empfindlichkeit jeder Groesse als
zentrale Differenz am Nennwert; daraus 1D-Glieder mit Faktor = |Empfindlichkeit| und Richtung = Vorzeichen, plus ein
Glied ohne Toleranz fuer den Linearisierungsrest, so dass das 1D-Werkzeug (Worst Case, RSS, Monte Carlo, Ampel,
Kostenoptimierung) die linearisierte Kette rechnet. Die nichtlineare Monte-Carlo-Rechnung (alle Groessen
ausgewuerfelt, Schlussgroesse exakt) prueft die Linearisierung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr
from .toleranzkette import Glied

SCHLUSS = {"abstand": "Abstand Ende – Anfang", "x": "X-Anteil des Schlussvektors",
           "y": "Y-Anteil des Schlussvektors", "winkel": "Richtung des letzten Segments (°)"}


@dataclass
class Segment:
    name: str
    laenge: float
    laenge_oben: float = 0.1
    laenge_unten: float = -0.1
    winkel: float = 0.0  # Grad zum vorigen Segment (erstes: zur X-Achse)
    winkel_oben: float = 0.0
    winkel_unten: float = 0.0
    verteilung: str = "normal"  # Schluessel aus toleranzkette.VERTEILUNG (fuer beide Groessen)


@dataclass
class Kette2D:
    segmente: list[Segment] = field(default_factory=list)
    schluss: str = "abstand"


def _parameter(k: Kette2D) -> list[tuple[int, str]]:
    """(Segment, "laenge" | "winkel") je Groesse mit Toleranz oder Nennwert."""
    return [(i, g) for i in range(len(k.segmente)) for g in ("laenge", "winkel")]


def punkte(k: Kette2D, werte: dict | None = None) -> np.ndarray:
    """Eckpunkte des Zugs (n+1 x 2) ab dem Ursprung; werte: {(i, groesse): Wert} ersetzt Nennwerte."""
    werte = werte or {}
    p, richtung, out = np.zeros(2), 0.0, [np.zeros(2)]
    for i, s in enumerate(k.segmente):
        richtung += math.radians(werte.get((i, "winkel"), s.winkel))
        lang = werte.get((i, "laenge"), s.laenge)
        p = p + lang * np.array([math.cos(richtung), math.sin(richtung)])
        out.append(p)
    return np.array(out)


def schlussgroesse(k: Kette2D, werte: dict | None = None) -> float:
    pts = punkte(k, werte)
    if k.schluss == "winkel":
        richtung = sum(werte.get((i, "winkel"), s.winkel) if werte else s.winkel for i, s in enumerate(k.segmente))
        return (richtung + 180.0) % 360.0 - 180.0
    v = pts[0] - pts[-1]  # Schlussvektor vom Ende zurueck zum Anfang
    return float(np.linalg.norm(v)) if k.schluss == "abstand" else float(v[0] if k.schluss == "x" else v[1])


def empfindlichkeiten(k: Kette2D, schritt: float = 1e-5) -> dict:
    """d(Schlussgroesse)/d(Groesse) je (Segment, Groesse) als zentrale Differenz."""
    out = {}
    for key in _parameter(k):
        i, g = key
        nenn = getattr(k.segmente[i], g)
        h = schritt * max(1.0, abs(nenn))
        out[key] = (schlussgroesse(k, {key: nenn + h}) - schlussgroesse(k, {key: nenn - h})) / (2 * h)
    return out


def als_glieder(k: Kette2D) -> list[Glied]:
    """Linearisierte Kette fuer das 1D-Werkzeug: je tolerierte Groesse ein Glied mit Faktor |dS/dp| und Richtung
    sign(dS/dp), dazu der Linearisierungsrest S(Nenn) - Summe(dS/dp * p) als Glied ohne Toleranz."""
    e = empfindlichkeiten(k)
    glieder, linear = [], 0.0
    for (i, g), d in e.items():
        s = k.segmente[i]
        nenn = getattr(s, g)
        oben, unten = getattr(s, g + "_oben"), getattr(s, g + "_unten")
        if abs(d) < 1e-12 or oben == unten == 0:
            continue  # untolerierte Groessen stecken im Linearisierungsrest
        linear += d * nenn
        einheit = "°" if g == "winkel" else ""
        name = f"{s.name} – {tr('Winkel') if g == 'winkel' else tr('Länge')} {nenn:g}{einheit}"
        glieder.append(Glied(name, nenn, nenn + oben, nenn + unten, 1 if d > 0 else -1, verteilung=s.verteilung,
                             quelle="eigen", faktor=abs(d)))
    rest = schlussgroesse(k) - linear
    glieder.append(Glied(tr("Linearisierung (Nennlage)"), rest, rest, rest, 1, quelle="eigen"))
    return glieder


def monte_carlo(k: Kette2D, proben: int = 50_000, cp: float = 1.0, zufall: int = 1) -> np.ndarray:
    """Schlussgroesse nichtlinear: alle Groessen nach ihrer Verteilung ausgewuerfelt, Zug exakt ausgewertet."""
    rng = np.random.default_rng(zufall)
    ziehungen = {}
    for i, g in _parameter(k):
        s = k.segmente[i]
        nenn = getattr(s, g)
        gl = Glied("", nenn, nenn + getattr(s, g + "_oben"), nenn + getattr(s, g + "_unten"), verteilung=s.verteilung)
        ziehungen[(i, g)] = gl.ziehe(rng, proben, cp) if gl.toleranz > 0 else np.full(proben, nenn)
    # vektorisiert: Richtungen kumulieren, Punkte summieren
    richtung = np.cumsum(np.radians(np.array([ziehungen[(i, "winkel")] for i in range(len(k.segmente))])), axis=0)
    laengen = np.array([ziehungen[(i, "laenge")] for i in range(len(k.segmente))])
    x = np.sum(laengen * np.cos(richtung), axis=0)
    y = np.sum(laengen * np.sin(richtung), axis=0)
    if k.schluss == "winkel":
        return (np.degrees(richtung[-1]) + 180.0) % 360.0 - 180.0
    if k.schluss == "abstand":
        return np.hypot(x, y)
    return -x if k.schluss == "x" else -y


def als_dict(k: Kette2D) -> dict:
    from dataclasses import asdict
    return {"schluss": k.schluss, "segmente": [asdict(s) for s in k.segmente]}


def von_dict(d: dict) -> Kette2D:
    felder = set(Segment.__dataclass_fields__)
    return Kette2D([Segment(**{a: b for a, b in s.items() if a in felder}) for s in d.get("segmente", [])],
                   d.get("schluss", "abstand"))
