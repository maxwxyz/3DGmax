"""3D-Toleranzkette im Modell: Linien der Lagen und Wiggle der Glieder in ihren Grenzen (PLAN §8.33 Stufe 5, ohne Qt).

Anzeige: Linienzug von der Basis ueber die Ursprunge der Glieder (Name in der Streckenmitte; Glieder ohne Versatz
stehen gemeinsam am Achsenkreuz), Achsenkreuz je Lage (X rot, Y gruen, Z blau, Achsbuchstaben an der Basis),
Funktionspunkt als Stern mit Beschriftung, bei "abstand" der Zielpunkt, bei "winkel" Punkt- und Zielrichtung.

Wiggle: die tolerierten (unabhaengigen) Komponenten pendeln als Sinus zwischen ihren Grenzen - "wc" alle zugleich in
der Richtung, die die Schlussgroesse vergroessert (Worst-Case-Kombination), "glieder" Glied fuer Glied. Je Bild der
exakte Wert der Schlussgroesse (nichtlinear, freie Komponenten geschlossen) und die Bewertung gegen die Anforderung;
die Anzeige ueberhoeht die Abweichungen um einen Faktor. Glieder mit einem Teil des Zusammenbaus bewegen das Teil
mit ihrer Lage (relativ zur Basis).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..i18n import tr
from . import kette3d as k3

SCHRITTE = 48  # Bilder je Hin und Her
FARBEN = {"glied": (0.13, 0.42, 0.85), "x": (0.75, 0.22, 0.17), "y": (0.18, 0.62, 0.28), "z": (0.13, 0.42, 0.85),
          "punkt": (0.90, 0.55, 0.10), "ziel": (0.55, 0.27, 0.75), "gruen": (0.18, 0.62, 0.28),
          "rot": (0.85, 0.20, 0.15)}


@dataclass
class Bild:
    werte: dict  # {(Glied, Komponente): Wert} der bewegten Komponenten, 1:1
    wert: float  # Schlussgroesse in diesem Bild
    glied: int  # bewegtes Glied, -1: alle (Worst Case)
    stufe: str  # "gruen" | "rot" | "" (ohne Anforderung)


def tolerierte(k: k3.Kette3D) -> list[tuple[int, str]]:
    """Unabhaengige Komponenten mit Toleranz (sie bewegt der Wiggle)."""
    return [(i, c) for i, c in k3._parameter(k) if k.glieder[i].werte[c].oben != k.glieder[i].werte[c].unten]


def grund(k: k3.Kette3D) -> str:
    """Warum kein Wiggle moeglich ist ("" = moeglich)."""
    if not k.glieder:
        return tr("Noch keine Glieder")
    fehler = k3.pruefe(k)
    if fehler:
        return fehler
    if not tolerierte(k):
        return tr("Keine Komponente hat Abmaße – nichts zu bewegen")
    return ""


def _wert(k: k3.Kette3D, key: tuple[int, str], s: float) -> float:
    """Komponente bei s in [-1, 1]: -1 unteres, +1 oberes Abmass."""
    w = k.glieder[key[0]].werte[key[1]]
    return w.nenn + (w.oben + w.unten) / 2 + s * (w.oben - w.unten) / 2


def _stufe(wert: float, anforderung: tuple | None) -> str:
    if anforderung is None:
        return ""
    u, o = anforderung
    ok = (u is None or wert >= u - 1e-12) and (o is None or wert <= o + 1e-12)
    return "gruen" if ok else "rot"


def bilder(k: k3.Kette3D, art: str = "wc", schritte: int = SCHRITTE) -> list[Bild]:
    """Ein Hin und Her je Gruppe ("wc": alle Komponenten, "glieder": je Glied seine Komponenten); jede Komponente
    bewegt sich in die Richtung, in der sie die Schlussgroesse vergroessert."""
    keys = tolerierte(k)
    if not keys or k3.pruefe(k):
        return []
    e = k3.empfindlichkeiten(k)
    vz = {key: 1.0 if e.get(key, 0.0) >= 0 else -1.0 for key in keys}
    gruppen = [(-1, keys)] if art == "wc" else \
        [(i, [x for x in keys if x[0] == i]) for i in range(len(k.glieder))]
    out = []
    for i, gruppe in gruppen:
        if not gruppe:
            continue
        for n in range(schritte):
            s = math.sin(2 * math.pi * n / schritte)
            werte = {key: _wert(k, key, s * vz[key]) for key in gruppe}
            wert = k3.schlussgroesse(k, werte)
            out.append(Bild(werte, wert, i, _stufe(wert, k.anforderung)))
    return out


def bereich(k: k3.Kette3D) -> tuple[float, float]:
    """Schlussgroesse an den beiden Worst-Case-Ecken des Wiggles (alle Komponenten an der Grenze), nichtlinear."""
    keys = tolerierte(k)
    e = k3.empfindlichkeiten(k)
    werte = [k3.schlussgroesse(k, {key: _wert(k, key, s * (1.0 if e.get(key, 0.0) >= 0 else -1.0))
                                   for key in keys}) for s in (-1.0, 1.0)]
    return min(werte), max(werte)


def anzeige_werte(k: k3.Kette3D, werte: dict | None, faktor: float = 1.0) -> dict:
    """Werte fuer die Anzeige: Abweichungen um faktor ueberhoeht, freie Komponenten danach geschlossen."""
    aus = {}
    for (i, c), v in (werte or {}).items():
        nenn = k.glieder[i].werte[c].nenn
        aus[(i, c)] = nenn + faktor * (v - nenn)
    return k3._schliesse(k, aus) if k3.freie(k) else aus


def _punkte(k: k3.Kette3D, werte: dict) -> list[np.ndarray]:
    """Ursprung jedes Glieds und Funktionspunkt in der Basis."""
    p, _ = k3.funktionspunkt(k, werte)
    return [t for _, t in k3.lagen(k, werte)] + [p]


def groesse(k: k3.Kette3D) -> float:
    """Ausdehnung der Kette (Diagonale ueber Basis, Ursprunge und Funktionspunkt), mindestens 1 mm."""
    if not k.glieder:
        return 1.0
    pts = np.array([np.zeros(3)] + _punkte(k, anzeige_werte(k, {})))
    return max(1.0, float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))))


def faktor(k: k3.Kette3D) -> float:
    """Ueberhoehung: die groesste Bewegung eines Kettenpunkts zwischen den Worst-Case-Ecken soll etwa ein Zwanzigstel
    der Kettengroesse ausmachen (1 bis 1000)."""
    keys = tolerierte(k)
    if not keys:
        return 1.0
    ecken = [_punkte(k, anzeige_werte(k, {key: _wert(k, key, s) for key in keys})) for s in (-1.0, 1.0)]
    weg = max(float(np.linalg.norm(a - b)) for a, b in zip(*ecken))
    return min(1000.0, max(1.0, groesse(k) / 20.0 / weg)) if weg > 1e-12 else 1.0


def _hom(r: np.ndarray, t: np.ndarray) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3], m[:3, 3] = r, t
    return m


def teil_bewegungen(k: k3.Kette3D, werte: dict) -> dict:
    """Bewegung (4x4, Modell) je Teil des Zusammenbaus: die Lage seines Glieds mit den Anzeigewerten gegen die
    Nennlage - das Teil haengt starr an seinem Glied."""
    if not any(g.teil is not None for g in k.glieder):
        return {}
    b = k3.basis(k)
    nenn, jetzt = k3.lagen(k, anzeige_werte(k, {})), k3.lagen(k, werte)
    out = {}
    for g, (r0, t0), (r1, t1) in zip(k.glieder, nenn, jetzt):
        if g.teil is not None:
            out[g.teil] = b @ _hom(r1, t1) @ np.linalg.inv(_hom(r0, t0)) @ np.linalg.inv(b)
    return out


def _stern(p: np.ndarray, a: float, farbe, breite: float = 2.0) -> list:
    return [(tuple(p - v * a), tuple(p + v * a), "", farbe, breite)
            for v in (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0]))]


def linien(k: k3.Kette3D, werte: dict | None = None, punkt_text: str = "", punkt_farbe=None) -> list:
    """Linien fuer die 3D-Ansicht (Start, Ende, Text, Farbe, Breite) im Modell; werte: Anzeigewerte (sonst Nennlage).
    Eintraege mit Start = Ende tragen nur eine Beschriftung."""
    if not k.glieder:
        return []
    werte = anzeige_werte(k, {}) if werte is None else werte
    a = 0.08 * groesse(k)
    lagen = k3.lagen(k, werte)
    out = []
    for achse, name in enumerate("xyz"):  # Basis mit Achsbuchstaben
        out.append(((0.0, 0.0, 0.0), tuple(np.eye(3)[achse] * a * 1.4), "", FARBEN[name], 1.5))
        out.append((tuple(np.eye(3)[achse] * a * 1.5),) * 2 + (name.upper(), FARBEN[name], 1.5))
    vorher, gemeinsam = np.zeros(3), [tr("Basis")]
    for g, (r, t) in zip(k.glieder, lagen):
        if np.linalg.norm(t - vorher) > 1e-9:
            out.append(((tuple(vorher),) * 2 + (" / ".join(gemeinsam), FARBEN["glied"], 1.0)))
            out.append((tuple(vorher), tuple(t), "", FARBEN["glied"], 3.0))
            out.append((tuple((vorher + t) / 2),) * 2 + (g.name, FARBEN["glied"], 1.0))
            gemeinsam = []
        else:
            gemeinsam.append(g.name)  # ohne Versatz: Name am Achsenkreuz (mehrere Glieder am selben Ort)
        for achse, name in enumerate("xyz"):
            out.append((tuple(t), tuple(t + r[:, achse] * a), "", FARBEN[name], 1.5))
        vorher = t
    if gemeinsam:
        out.append(((tuple(vorher),) * 2 + (" / ".join(gemeinsam), FARBEN["glied"], 1.0)))
    p, d = k3.funktionspunkt(k, werte)
    farbe = punkt_farbe or FARBEN["punkt"]
    if np.linalg.norm(p - vorher) > 1e-9:
        out.append((tuple(vorher), tuple(p), "", farbe, 1.5))
    out += _stern(p, a * 0.35, farbe)
    out.append((tuple(p + np.array([0, 0, a * 0.4])),) * 2 + (
        tr("Funktionspunkt") + (f"  {punkt_text}" if punkt_text else ""), farbe, 1.0))
    if k.schluss == "abstand":
        z = np.asarray(k.ziel, float)
        out += _stern(z, a * 0.35, FARBEN["ziel"])
        out.append((tuple(p), tuple(z), "", FARBEN["ziel"], 1.0))
        out.append((tuple(z),) * 2 + (tr("Zielpunkt"), FARBEN["ziel"], 1.0))
    elif k.schluss == "winkel":
        z = np.asarray(k.ziel, float)
        for v, text, f in ((d, tr("Richtung"), farbe), (z, tr("Zielrichtung"), FARBEN["ziel"])):
            n = float(np.linalg.norm(v))
            if n > 1e-12:
                out.append((tuple(p), tuple(p + v / n * a * 2), "", f, 2.0))
                out.append((tuple(p + v / n * a * 2.2),) * 2 + (text, f, 1.0))
    b = k3.basis(k)
    if k.basis is None:
        return out
    welt = lambda x: tuple(b[:3, :3] @ np.asarray(x, float) + b[:3, 3])  # noqa: E731
    return [(welt(s), welt(e), *rest) for s, e, *rest in out]
