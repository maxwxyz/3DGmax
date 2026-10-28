"""Dreidimensionale Toleranzkette als Folge von Lagen (PLAN §8.33 Stufe 5, ohne Qt).

Jedes Glied ist eine Lage relativ zum vorigen Glied (z. B. Bauteil auf Bauteil): Verschiebung X/Y/Z und Drehung um
X/Y/Z (Grad, nacheinander um die mitgedrehten Achsen X, dann Y, dann Z), jede der sechs Komponenten mit Abmassen -
die kleinen Abweichungen bilden den Torsor (Small Displacement Torsor) des Glieds. Am Ende der Kette sitzt ein
Funktionspunkt mit Richtung (im Koordinatensystem des letzten Glieds). Schlussgroesse: X-, Y- oder Z-Lage des
Punkts in der Basis, Abstand zu einem Zielpunkt in der Basis, oder Winkel der Punktrichtung zu einer Zielrichtung.

Rechnung wie die 2D-Kette (kern.kette2d): Empfindlichkeiten als zentrale Differenzen, 1D-Glieder mit Faktor und
Linearisierungsrest fuer das 1D-Werkzeug, nichtlineare Monte-Carlo-Rechnung zur Kontrolle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr
from .toleranzkette import Glied

KOMPONENTEN = ("x", "y", "z", "rx", "ry", "rz")
KOMPONENTEN_TEXT = {"x": "Verschiebung X", "y": "Verschiebung Y", "z": "Verschiebung Z", "rx": "Drehung um X",
                    "ry": "Drehung um Y", "rz": "Drehung um Z"}
SCHLUSS = {"x": "X-Lage des Funktionspunkts", "y": "Y-Lage des Funktionspunkts", "z": "Z-Lage des Funktionspunkts",
           "abstand": "Abstand zum Zielpunkt", "winkel": "Winkel zur Zielrichtung (°)"}


@dataclass
class Komponente:
    nenn: float = 0.0
    oben: float = 0.0
    unten: float = 0.0


@dataclass
class Glied3D:
    name: str
    werte: dict = field(default_factory=lambda: {k: Komponente() for k in KOMPONENTEN})
    verteilung: str = "normal"


@dataclass
class Kette3D:
    glieder: list[Glied3D] = field(default_factory=list)
    punkt: tuple = (0.0, 0.0, 0.0)  # Funktionspunkt im letzten Glied
    richtung: tuple = (0.0, 0.0, 1.0)  # Richtung am Funktionspunkt (fuer "winkel")
    schluss: str = "z"
    ziel: tuple = (0.0, 0.0, 0.0)  # Zielpunkt (abstand) bzw. Zielrichtung (winkel) in der Basis


def _drehung(rx: float, ry: float, rz: float) -> np.ndarray:
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    dx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    dy = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    dz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return dx @ dy @ dz


def lagen(k: Kette3D, werte: dict | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """(Drehung 3x3, Ursprung) jedes Glieds in der Basis; werte {(Glied, Komponente): Wert} ersetzt Nennwerte."""
    werte = werte or {}
    r, t, out = np.eye(3), np.zeros(3), []
    for i, g in enumerate(k.glieder):
        w = {c: werte.get((i, c), g.werte[c].nenn) for c in KOMPONENTEN}
        t = t + r @ np.array([w["x"], w["y"], w["z"]])
        r = r @ _drehung(w["rx"], w["ry"], w["rz"])
        out.append((r, t))
    return out


def funktionspunkt(k: Kette3D, werte: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Funktionspunkt und seine Richtung in der Basis."""
    r, t = lagen(k, werte)[-1] if k.glieder else (np.eye(3), np.zeros(3))
    return t + r @ np.array(k.punkt, float), r @ np.array(k.richtung, float)


def schlussgroesse(k: Kette3D, werte: dict | None = None) -> float:
    p, d = funktionspunkt(k, werte)
    if k.schluss in ("x", "y", "z"):
        return float(p["xyz".index(k.schluss)])
    if k.schluss == "abstand":
        return float(np.linalg.norm(p - np.array(k.ziel, float)))
    z = np.array(k.ziel, float)
    z = z / (np.linalg.norm(z) or 1.0)
    d = d / (np.linalg.norm(d) or 1.0)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(d @ z)))))


def _parameter(k: Kette3D):
    return [(i, c) for i in range(len(k.glieder)) for c in KOMPONENTEN]


def empfindlichkeiten(k: Kette3D, schritt: float = 1e-5) -> dict:
    out = {}
    for key in _parameter(k):
        i, c = key
        nenn = k.glieder[i].werte[c].nenn
        h = schritt * max(1.0, abs(nenn))
        out[key] = (schlussgroesse(k, {key: nenn + h}) - schlussgroesse(k, {key: nenn - h})) / (2 * h)
    return out


def als_glieder(k: Kette3D) -> list[Glied]:
    """Linearisierte Kette fuer das 1D-Werkzeug (wie kette2d.als_glieder): je tolerierte Komponente ein Glied mit
    Faktor |dS/dp| und Richtung sign(dS/dp), dazu der Linearisierungsrest ohne Toleranz."""
    e = empfindlichkeiten(k)
    glieder, linear = [], 0.0
    for (i, c), d in e.items():
        g = k.glieder[i]
        w = g.werte[c]
        linear += d * w.nenn
        if abs(d) < 1e-12 or w.oben == w.unten == 0:
            continue
        einheit = "°" if c.startswith("r") else ""
        glieder.append(Glied(f"{g.name} – {tr(KOMPONENTEN_TEXT[c])} {w.nenn:g}{einheit}", w.nenn, w.nenn + w.oben,
                             w.nenn + w.unten, 1 if d > 0 else -1, verteilung=g.verteilung, quelle="eigen",
                             faktor=abs(d)))
    rest = schlussgroesse(k) - linear
    glieder.append(Glied(tr("Linearisierung (Nennlage)"), rest, rest, rest, 1, quelle="eigen"))
    return glieder


def monte_carlo(k: Kette3D, proben: int = 20_000, cp: float = 1.0, zufall: int = 1) -> np.ndarray:
    """Schlussgroesse nichtlinear: alle Komponenten ausgewuerfelt, Kette je Probe exakt ausgewertet."""
    rng = np.random.default_rng(zufall)
    ziehungen = {}
    for i, c in _parameter(k):
        g = k.glieder[i]
        w = g.werte[c]
        gl = Glied("", w.nenn, w.nenn + w.oben, w.nenn + w.unten, verteilung=g.verteilung)
        ziehungen[(i, c)] = gl.ziehe(rng, proben, cp) if gl.toleranz > 0 else None
    out = np.empty(proben)
    for n in range(proben):
        out[n] = schlussgroesse(k, {key: v[n] for key, v in ziehungen.items() if v is not None})
    return out


def als_dict(k: Kette3D) -> dict:
    from dataclasses import asdict
    return {"glieder": [asdict(g) for g in k.glieder], "punkt": list(k.punkt), "richtung": list(k.richtung),
            "schluss": k.schluss, "ziel": list(k.ziel)}


def von_dict(d: dict) -> Kette3D:
    glieder = [Glied3D(g["name"], {c: Komponente(**g["werte"][c]) for c in KOMPONENTEN}, g.get("verteilung", "normal"))
               for g in d.get("glieder", [])]
    return Kette3D(glieder, tuple(d.get("punkt", (0, 0, 0))), tuple(d.get("richtung", (0, 0, 1))),
                   d.get("schluss", "z"), tuple(d.get("ziel", (0, 0, 0))))


def glied(name: str, **komponenten) -> Glied3D:
    """Glied aus Angaben wie x=(10, 0.1, -0.1), rz=(90, 0.2, -0.2) oder rz=90 (ohne Toleranz)."""
    g = Glied3D(name)
    for c, v in komponenten.items():
        g.werte[c] = Komponente(*v) if isinstance(v, tuple) else Komponente(float(v))
    return g
