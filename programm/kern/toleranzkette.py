"""Eindimensionale Toleranzkette (Massskette): Schlussmass nach Worst Case, RSS und Monte Carlo (ohne Qt).

Jedes Glied ist ein Mass mit Nennmass, Hoechst- und Mindestmass und Richtung (+1 vergroessert das Schlussmass,
-1 verkleinert es). Statistik: Mittelwert in Toleranzmitte, Standardabweichung = Toleranz / (2 * k) mit k = 3
(Prozessfaehigkeit Cp = 1), Normalverteilung.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass

import numpy as np

from ..i18n import tr


@dataclass
class Glied:
    name: str
    nenn: float
    hoechst: float
    mindest: float
    richtung: int = 1  # +1 / -1
    pmi_nummer: int = 0

    @property
    def mitte(self) -> float:
        return (self.hoechst + self.mindest) / 2

    @property
    def toleranz(self) -> float:
        return self.hoechst - self.mindest


@dataclass
class Ergebnis:
    nenn: float
    wc_min: float
    wc_max: float
    mitte: float
    rss: float  # halbe statistische Toleranzbreite (+-)
    mc_min: float  # 0,135 %-Quantil
    mc_max: float  # 99,865 %-Quantil
    mc_mittel: float
    mc_std: float


def glied_von_pmi(p, richtung: int = 1) -> Glied | None:
    """Kettenglied aus einem Mass mit Grenzen (auch aus ISO-286-Klasse); None ohne Grenzen."""
    if p.art != "mass" or p.nennwert is None:
        return None
    h, m = p.grenzen()
    if h is None or m is None:
        h = m = p.nennwert
    return Glied(f"{p.nummer}: {p.wert_text()}", p.nennwert, h, m, richtung, p.nummer)


def berechne(glieder: list[Glied], k: float = 3.0, proben: int = 200_000, zufall: int = 1) -> Ergebnis:
    if not glieder:
        return Ergebnis(0, 0, 0, 0, 0, 0, 0, 0, 0)
    r = np.array([g.richtung for g in glieder], float)
    nenn = float(sum(g.richtung * g.nenn for g in glieder))
    hi = np.array([g.hoechst for g in glieder])
    lo = np.array([g.mindest for g in glieder])
    wc_max = float(np.sum(np.where(r > 0, hi, lo) * r))
    wc_min = float(np.sum(np.where(r > 0, lo, hi) * r))
    mitte = float(np.sum((hi + lo) / 2 * r))
    sigma = (hi - lo) / (2 * k)
    rss = float(k * math.sqrt(float(np.sum(sigma ** 2))))
    rng = np.random.default_rng(zufall)
    werte = (rng.standard_normal((proben, len(glieder))) * sigma + (hi + lo) / 2) @ r
    q = np.quantile(werte, [0.00135, 0.99865])
    return Ergebnis(nenn, wc_min, wc_max, mitte, rss, float(q[0]), float(q[1]), float(werte.mean()),
                    float(werte.std()))


SPALTEN = ("Glied", "Richtung", "Nennmaß", "Höchstmaß", "Mindestmaß", "Toleranz")


def als_csv(glieder: list[Glied], e: Ergebnis) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    for g in glieder:
        w.writerow([g.name, "+" if g.richtung > 0 else "−"] +
                   [f"{x:.4f}".replace(".", ",") for x in (g.nenn, g.hoechst, g.mindest, g.toleranz)])
    w.writerow([])
    for text, wert in ((tr("Schlussmaß (nominal)"), e.nenn), (tr("Worst Case min"), e.wc_min),
                       (tr("Worst Case max"), e.wc_max), (tr("Statistisch (RSS) ±"), e.rss),
                       (tr("Monte Carlo 0,135 %"), e.mc_min), (tr("Monte Carlo 99,865 %"), e.mc_max)):
        w.writerow([text, "", f"{wert:.4f}".replace(".", ",")])
    return puffer.getvalue()
