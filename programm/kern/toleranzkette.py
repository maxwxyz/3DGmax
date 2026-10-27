"""Eindimensionale Toleranzkette (Massskette): Schlussmass nach Worst Case, RSS und Monte Carlo (ohne Qt).

Jedes Glied ist ein Mass mit Nennmass, Hoechst- und Mindestmass und Richtung (+1 vergroessert das Schlussmass,
-1 verkleinert es). Statistik je Glied: Mittelwert in Toleranzmitte (plus Versatz); Verteilung nach Fertigungsart
(Scholz, Tabelle der Verteilungsfaktoren): normal mit sigma = T / (6 * Cp) (Serie; Cp je Glied oder der Kette),
Dreieck sigma = T / (2 * Wurzel 6) (Kleinserie), Trapez mit flachem Anteil a sigma = T/2 * Wurzel((1 + a^2) / 6),
gleichverteilt sigma = T / (2 * Wurzel 3) (Einzelteil) - T = Toleranzbreite; aus Messwerten (ab zwei Werten):
Normalverteilung mit Mittelwert und Standardabweichung der Stichprobe (Versatz = Mittelwert - Toleranzmitte). Das statistische Ergebnis ist +-3 sigma
des Schlussmasses, der Anteil eines Glieds sein Varianzanteil.

Korrelation: Glieder derselben Gruppe (gleiches Teil, gleiche Aufspannung oder Prozess) streuen gemeinsam mit dem
Korrelationskoeffizienten rho_ij = Wurzel(rho_i * rho_j) (Ein-Faktor-Modell); Varianz des Schlussmasses mit Kovarianzen,
Anteile je Glied als Kovarianzanteil, n_eff = (Spur C)^2 / Spur(C^2); Monte Carlo ueber Rangkorrelation (Iman-Conover).
Das Mittenverschiebungs-Modell und das Verteilen der Toleranzen rechnen ohne Korrelation.

Anwendbarkeit: statistisch erst ab vier wirksamen Beitragsleistern (zentraler Grenzwertsatz); wirksam zaehlt
n_eff = (Summe sigma^2)^2 / Summe sigma^4, ein dominierendes Glied zaehlt also als eines. Darunter gilt das
arithmetische Ergebnis (Worst Case); es wird immer mit ausgegeben.

Aufbau aus der 3D-Auswahl (kette_aus_flaechen): Flaechen in Kettenreihenfolge, Richtung = Normale der ersten ebenen
Flaeche; Lage jeder Flaeche entlang der Richtung (Ebene senkrecht dazu, Zylinderachse quer dazu); je zwei
aufeinanderfolgende Flaechen ein Glied. Werte aus einem PMI-Mass mit Flaechen an beiden Enden und passendem Nennwert
(auch Muster), sonst Allgemeintoleranz ISO 2768-1, sonst ohne Toleranz (gemeldet).
Lagetoleranzen (Position, Symmetrie, Koaxialitaet, Profil mit Bezug) wirken nur an der ersten und letzten Flaeche:
die Lageabweichung einer Zwischenflaeche geht in zwei Glieder mit entgegengesetztem Vorzeichen ein und hebt sich auf.
Je Endflaeche und Toleranz ein Glied mit Nennmass 0 und der Verschiebung entlang der Kette (Profil: Zonengrenzen
mit UZ und Materialseite, sonst +-t/2; Bonus bei Ⓜ/Ⓛ nicht enthalten).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr

VERTEILUNG = {"normal": "Normal (Serie)", "dreieck": "Dreieck (Kleinserie)", "trapez": "Trapez",
              "gleich": "Gleich (Einzelteil)", "messwerte": "Aus Messwerten"}
MINDEST_BEITRAGSLEISTER = 4  # ab hier ist das statistische Ergebnis anwendbar
QUELLE = {"pmi": "PMI", "lage": "Lagetoleranz", "allgemein": "Allgemeintoleranz", "ohne": "ohne Toleranz",
          "bereich": "Längenbereich", "eigen": "eigene Angabe"}
LAGE_TYPEN = {"Position", "Symmetry", "Coaxiality", "Concentricity"}
PROFIL_TYPEN = {"ProfileOfSurface", "ProfileOfLine"}


@dataclass
class Glied:
    name: str
    nenn: float
    hoechst: float
    mindest: float
    richtung: int = 1  # +1 / -1
    pmi_nummer: int = 0
    cp: float | None = None  # None: Cp der Kette
    verteilung: str = "normal"  # Schluessel aus VERTEILUNG
    quelle: str = "pmi"  # Schluessel aus QUELLE
    flaechen: tuple[int, ...] = field(default_factory=tuple)  # Flaechen an den Enden (aus der 3D-Auswahl)
    versatz: float = 0.0  # Mittenversatz des Prozesses gegen die Toleranzmitte (mm), ergibt Cpk < Cp
    form: float = 0.5  # Trapez: Anteil des flachen Teils (0 = Dreieck, 1 = Rechteck)
    teil: str = ""  # Bauteil (fuer den Werkstoff bei der Waermeausdehnung)
    stellglied: bool = False  # Laengenbereich, der zum Einhalten der Anforderung eingestellt wird
    faktor: float = 1.0  # Empfindlichkeit d(Schlussmass)/d(Glied), z. B. Hebelverhaeltnis (Vorzeichen: richtung)
    fest: bool = False  # Toleranz beim Verteilen nicht aendern (z. B. Normteil, Waelzlager)
    messwerte: tuple[float, ...] = field(default_factory=tuple)  # Stichprobe fuer die Verteilung "messwerte"
    gruppe: str = ""  # Korrelationsgruppe (leer: unabhaengig)
    rho: float = 0.0  # Korrelation mit den anderen Gliedern der Gruppe (0 ... 1)

    @property
    def gemessen(self) -> bool:
        """Verteilung aus Messwerten (mindestens zwei Werte)?"""
        return self.verteilung == "messwerte" and len(self.messwerte) >= 2

    @property
    def wirk_versatz(self) -> float:
        """Mittelwert des Prozesses gegen die Toleranzmitte: aus den Messwerten oder der eingegebene Versatz."""
        return float(np.mean(self.messwerte)) - self.mitte if self.gemessen else self.versatz

    @property
    def mitte(self) -> float:
        return (self.hoechst + self.mindest) / 2

    @property
    def toleranz(self) -> float:
        return self.hoechst - self.mindest

    def cpk(self, cp_kette: float = 1.0) -> float | None:
        """Cpk = Cp * (1 - |Versatz| / (T/2)); None bei Gleichverteilung oder ohne Toleranz."""
        if self.verteilung not in ("normal", "messwerte") or self.toleranz <= 0:
            return None
        if self.gemessen:
            return (self.toleranz / 2 - abs(self.wirk_versatz)) / (3 * self.sigma(cp_kette)) if self.sigma() else None
        return (self.cp or cp_kette) * (1 - abs(self.versatz) / (self.toleranz / 2))

    def sigma(self, cp_kette: float = 1.0) -> float:
        t = self.toleranz
        if self.verteilung == "gleich":
            return t / (2 * math.sqrt(3))
        if self.verteilung == "dreieck":
            return t / (2 * math.sqrt(6))
        if self.verteilung == "trapez":
            return t / 2 * math.sqrt((1 + self.form ** 2) / 6)
        if self.gemessen:
            return float(np.std(self.messwerte, ddof=1))
        return t / (6 * (self.cp or cp_kette))

    def ziehe(self, rng, n: int, cp_kette: float = 1.0) -> np.ndarray:
        """n Zufallswerte des Glieds (ohne Richtung)."""
        m, h = self.mitte + self.wirk_versatz, self.toleranz / 2
        if self.verteilung == "gleich":
            return rng.uniform(m - h, m + h, n)
        if self.verteilung == "dreieck":
            return rng.triangular(m - h, m, m + h, n) if h > 0 else np.full(n, m)
        if self.verteilung == "trapez":  # Summe zweier Gleichverteilungen mit Halbbreiten h(1+a)/2 und h(1-a)/2
            a = min(1.0, max(0.0, self.form))
            w1, w2 = h * (1 + a) / 2, h * (1 - a) / 2
            return m + rng.uniform(-w1, w1, n) + rng.uniform(-w2, w2, n)
        return rng.standard_normal(n) * self.sigma(cp_kette) + m


@dataclass
class Ergebnis:
    nenn: float
    wc_min: float
    wc_max: float
    mitte: float
    rss: float  # halbe statistische Toleranzbreite (+-3 sigma)
    mc_min: float  # 0,135 %-Quantil
    mc_max: float  # 99,865 %-Quantil
    mc_mittel: float
    mc_std: float
    anteile: list[float] = field(default_factory=list)  # Varianzanteil je Glied (0..1)
    # nur mit Anforderung an das Schlussmass (untere, obere Grenze):
    cp: float | None = None
    cpk: float | None = None
    ausserhalb: float | None = None  # Anteil ausserhalb (Normalverteilung)
    mc_ausserhalb: float | None = None  # Anteil ausserhalb (Monte Carlo)
    n_eff: float = 0.0  # wirksame Beitragsleister (Summe Varianzen)^2 / Summe Varianzen^2
    proben: np.ndarray | None = None  # Monte-Carlo-Werte des Schlussmasses (fuer das Histogramm)
    bender: float = 0.0  # +- des statistischen Ergebnisses mal Bender-Faktor (modifiziertes RSS)
    verschiebung: float = 0.0  # +- nach dem Mittenverschiebungs-Modell (Verschiebungen arithmetisch, Rest RSS)

    @property
    def statistisch(self) -> bool:
        """Statistisches Ergebnis anwendbar (genug wirksame Beitragsleister)?"""
        return self.n_eff >= MINDEST_BEITRAGSLEISTER - 1e-9


def anwendbar_text(e: Ergebnis) -> str:
    """Begruendung, welches Ergebnis gilt."""
    if e.statistisch:
        return tr("{:.1f} wirksame Beitragsleister (≥ {}) – statistisches Ergebnis anwendbar").format(
            e.n_eff, MINDEST_BEITRAGSLEISTER)
    return tr("nur {:.1f} wirksame Beitragsleister (< {}) – arithmetisches Ergebnis (Worst Case) gilt").format(
        e.n_eff, MINDEST_BEITRAGSLEISTER)


def glied_von_pmi(p, richtung: int = 1) -> Glied | None:
    """Kettenglied aus einem Laengenmass mit Grenzen (auch aus ISO-286-Klasse); None fuer Winkel und ohne Nennmass."""
    if p.art != "mass" or p.nennwert is None or ist_winkel(p):
        return None
    h, m = p.grenzen()
    if h is None or m is None:
        h = m = p.nennwert
    return Glied(f"{p.nummer}: {p.wert_text()}", p.nennwert, h, m, richtung, p.nummer,
                 flaechen=tuple(sorted(p.flaechen)))


def bereich_glied(name: str, mindest: float, hoechst: float, richtung: int = 1, stellglied: bool = False) -> Glied:
    """Laengenbereich (z. B. Feder zwischen kleinster und groesster Einbaulaenge, Passscheibe, Stellschraube):
    gleichverteilt zwischen den Grenzen; als Stellglied wird sein noetiger Bereich berechnet."""
    lo, hi = sorted((float(mindest), float(hoechst)))
    return Glied(name, (lo + hi) / 2, hi, lo, richtung, verteilung="gleich", quelle="bereich", stellglied=stellglied)


def thermisch(glieder: list[Glied], alpha: dict, temperatur: float, je_teil: dict | None = None) -> list[Glied]:
    """Glieder bei einer Temperatur: jede Laenge waechst um alpha * L * (T - 20 °C) (alpha je Bauteil in 1e-6/K;
    je_teil: eigene Temperatur einzelner Bauteile in diesem Fall, z. B. kuehleres Gehaeuse; Glieder ohne Bauteil oder
    ohne Werkstoff und Lagetoleranzen ohne Laenge bleiben)."""
    import copy
    from .werkstoffe import laengenaenderung
    out = []
    for g in glieder:
        x = copy.copy(g)
        a = alpha.get(g.teil)
        if a and g.quelle != "lage":
            t = (je_teil or {}).get(g.teil)
            d = laengenaenderung(a, abs(g.nenn), temperatur if t is None else t)
            x.nenn, x.hoechst, x.mindest = g.nenn + d, g.hoechst + d, g.mindest + d
        out.append(x)
    return out


def stellbereich(glieder: list[Glied], anforderung: tuple[float, float]) -> tuple[float, float] | None:
    """Noetiger Bereich des Stellglieds, damit das Schlussmass im Worst Case die Anforderung haelt; None ohne
    Stellglied. Ergebnis (untere, obere) Grenze; untere > obere heisst: nicht einstellbar."""
    stell = [g for g in glieder if g.stellglied]
    if len(stell) != 1:
        return None
    s = stell[0]
    rest = [g for g in glieder if g is not s]
    k = lambda g: g.richtung * g.faktor  # noqa: E731
    lo = sum(k(g) * (g.mindest if k(g) > 0 else g.hoechst) for g in rest)
    hi = sum(k(g) * (g.hoechst if k(g) > 0 else g.mindest) for g in rest)
    u, o = anforderung
    ks = k(s)
    if abs(ks) < 1e-12:
        return None
    a, b = (u - lo) / ks, (o - hi) / ks
    return (a, b) if ks > 0 else (b, a)


def verteile_toleranzen(glieder: list[Glied], ziel: float, art: str = "varianz", statistisch: bool = True,
                        cp: float = 1.0) -> list[Glied]:
    """Toleranzen der nicht festen Glieder so setzen, dass das Schlussmass die Zielbreite (max - min) erreicht.
    art "varianz": jedes verstellbare Glied bekommt den gleichen Varianzanteil (Toleranzen angleichen, Klein);
    "proportional": alle verstellbaren Toleranzen mit demselben Faktor. statistisch: Ziel als +-3 sigma, sonst Worst
    Case. Mitte jedes Glieds bleibt; liefert Kopien (fuer das Planspiel)."""
    import copy
    neu = [copy.copy(g) for g in glieder]
    frei = [g for g in neu if not g.fest and g.quelle not in ("lage",) and not g.stellglied and not g.gemessen]
    if not frei or ziel <= 0:
        return neu
    frei_ids = {id(g) for g in frei}  # Identitaet: gleiche Werte duerfen nicht verwechselt werden
    k = {id(g): abs(g.richtung * g.faktor) for g in neu}

    def setze(g, t):
        m = g.mitte
        g.hoechst, g.mindest = m + t / 2, m - t / 2

    if statistisch:
        sig = lambda g: g.sigma(cp) * k[id(g)]  # noqa: E731
        rest = ziel ** 2 / 36 - sum(sig(g) ** 2 for g in neu if id(g) not in frei_ids)
        if rest <= 0:
            return neu
        if art == "varianz":
            for g in frei:  # sigma je Glied gleich: sigma_ziel / Wurzel(n); T aus sigma je Verteilung
                s_g = math.sqrt(rest / len(frei)) / (k[id(g)] or 1.0)
                einheits = copy.copy(g)
                setze(einheits, 1.0)
                setze(g, s_g / einheits.sigma(cp))
        else:
            jetzt = math.sqrt(sum(sig(g) ** 2 for g in frei)) or 1.0
            f = math.sqrt(rest) / jetzt
            for g in frei:
                setze(g, g.toleranz * f)
    else:
        rest = ziel - sum(g.toleranz * k[id(g)] for g in neu if id(g) not in frei_ids)
        if rest <= 0:
            return neu
        if art == "varianz":
            for g in frei:
                setze(g, rest / len(frei) / (k[id(g)] or 1.0))
        else:
            jetzt = sum(g.toleranz * k[id(g)] for g in frei) or 1.0
            for g in frei:
                setze(g, g.toleranz * rest / jetzt)
    return neu


def ist_winkel(p) -> bool:
    """Winkelmasse passen nicht in eine Laengenkette."""
    return "Angle" in (p.typ or "") or "°" in p.wert_text()


BENDER = 1.5  # Bender 1962: Zuschlag auf das RSS fuer optimistisch angegebene Toleranzen
VERSCHIEBUNG = 0.2  # Anteil der halben Toleranz, um den sich die Prozessmitte verschieben darf (Mittenverschiebung)


def korrelation(glieder: list[Glied]) -> np.ndarray:
    """Korrelationsmatrix der Glieder: rho_ij = Wurzel(rho_i * rho_j) in derselben Gruppe, sonst 0."""
    n = len(glieder)
    k = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = glieder[i], glieder[j]
            if a.gruppe and a.gruppe == b.gruppe:
                k[i, j] = k[j, i] = math.sqrt(max(0.0, min(1.0, a.rho)) * max(0.0, min(1.0, b.rho)))
    return k


def _korreliere(werte: np.ndarray, glieder: list[Glied], rng) -> np.ndarray:
    """Spalten je Gruppe nach den Raengen korrelierter Normalwerte umsortieren (Iman-Conover, Ein-Faktor-Modell):
    die Verteilung jedes Glieds bleibt, die Rangkorrelation folgt rho."""
    gruppen: dict[str, list[int]] = {}
    for i, g in enumerate(glieder):
        if g.gruppe and g.rho > 0:
            gruppen.setdefault(g.gruppe, []).append(i)
    for spalten in gruppen.values():
        if len(spalten) < 2:
            continue
        gemeinsam = rng.standard_normal(len(werte))
        for i in spalten:
            rho = min(1.0, glieder[i].rho)
            z = math.sqrt(rho) * gemeinsam + math.sqrt(1 - rho) * rng.standard_normal(len(werte))
            werte[:, i] = np.sort(werte[:, i])[np.argsort(np.argsort(z))]
    return werte


def berechne(glieder: list[Glied], cp: float = 1.0, proben: int = 200_000, zufall: int = 1,
             anforderung: tuple[float, float] | None = None, bender: float = BENDER,
             verschiebung: float = VERSCHIEBUNG) -> Ergebnis:
    """Schlussmass; cp: Prozessfaehigkeit der Kette fuer Glieder ohne eigenen Wert; anforderung: (untere, obere)
    Grenze des Schlussmasses fuer Cp, Cpk und Anteil ausserhalb. Empfindlichkeit je Glied: richtung * faktor.
    Zusaetzlich: modifiziertes RSS (mal bender) und Mittenverschiebungs-Modell (Greenwood/Chase, Scholz): je Glied
    darf die Mitte um verschiebung * T/2 wandern (arithmetisch summiert), die uebrige Streuung (1 - verschiebung) * T/2
    als +-3 sigma wird statistisch addiert."""
    if not glieder:
        return Ergebnis(0, 0, 0, 0, 0, 0, 0, 0, 0)
    r = np.array([g.richtung * g.faktor for g in glieder], float)
    nenn = float(sum(g.richtung * g.faktor * g.nenn for g in glieder))
    hi = np.array([g.hoechst for g in glieder])
    lo = np.array([g.mindest for g in glieder])
    wc_max = float(np.sum(np.where(r > 0, hi, lo) * r))
    wc_min = float(np.sum(np.where(r > 0, lo, hi) * r))
    versatz = np.array([g.wirk_versatz for g in glieder])
    mitte = float(np.sum(((hi + lo) / 2 + versatz) * r))
    beitrag = np.array([g.sigma(cp) for g in glieder]) * r  # sigma mit Vorzeichen der Wirkung
    kov = korrelation(glieder) * np.outer(beitrag, beitrag)
    varianz = max(0.0, float(np.sum(kov)))
    rss = float(3.0 * math.sqrt(varianz))  # +-3 sigma des Schlussmasses
    rng = np.random.default_rng(zufall)
    werte = _korreliere(np.column_stack([g.ziehe(rng, proben, cp) for g in glieder]), glieder, rng) @ r
    q = np.quantile(werte, [0.00135, 0.99865])
    anteile = [float(x / varianz) if varianz > 0 else 0.0 for x in kov.sum(axis=1)]
    spur = float(np.trace(kov))
    n_eff = spur ** 2 / float(np.sum(kov * kov)) if varianz > 0 else 0.0
    halbe = (hi - lo) / 2 * np.abs(r)
    schiebung = float(np.sum(verschiebung * halbe)) + 3.0 * math.sqrt(float(np.sum(
        ((1 - verschiebung) * halbe / 3) ** 2)))
    e = Ergebnis(nenn, wc_min, wc_max, mitte, rss, float(q[0]), float(q[1]), float(werte.mean()),
                 float(werte.std()), anteile, n_eff=n_eff, proben=werte, bender=bender * rss, verschiebung=schiebung)
    if anforderung is not None and anforderung[1] > anforderung[0]:
        u, o = anforderung
        s = math.sqrt(varianz)
        if s > 0:
            e.cp = (o - u) / (6 * s)
            e.cpk = min(o - mitte, mitte - u) / (3 * s)
            phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
            e.ausserhalb = phi((u - mitte) / s) + 1 - phi((o - mitte) / s)
        e.mc_ausserhalb = float(np.mean((werte < u) | (werte > o)))
    return e


# --- Kette aus der 3D-Auswahl ---

def _ebene_oder_achse(flaeche):
    """('ebene', Punkt, Normale) oder ('achse', Punkt, Richtung) oder None (andere Flaechen)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    s = BRepAdaptor_Surface(flaeche, True)
    t = s.GetType()
    if t == GeomAbs_Plane:
        ax = s.Plane().Axis()
    elif t in (GeomAbs_Cylinder, GeomAbs_Cone):
        ax = (s.Cylinder() if t == GeomAbs_Cylinder else s.Cone()).Axis()
    else:
        return None
    p, d = ax.Location(), ax.Direction()
    return ("ebene" if t == GeomAbs_Plane else "achse", np.array([p.X(), p.Y(), p.Z()]),
            np.array([d.X(), d.Y(), d.Z()]))


def _kante(kante):
    """('kante', Punkt, Richtung) einer geraden Kante oder ('achse', Mitte, Normale) einer Kreiskante, sonst None."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    c = BRepAdaptor_Curve(kante)
    if c.GetType() == GeomAbs_Line:
        ax = c.Line().Position()
        art = "kante"
    elif c.GetType() == GeomAbs_Circle:
        ax = c.Circle().Axis()
        art = "achse"
    else:
        return None
    p, d = ax.Location(), ax.Direction()
    return art, np.array([p.X(), p.Y(), p.Z()]), np.array([d.X(), d.Y(), d.Z()])


def _element(form):
    """Flaeche (Ebene/Achse) oder Kante (gerade/Kreis) als (Art, Punkt, Richtung) oder None."""
    from OCC.Core.TopAbs import TopAbs_EDGE
    return _kante(form) if form.ShapeType() == TopAbs_EDGE else _ebene_oder_achse(form)


def lage(form, richtung) -> float | None:
    """Lage entlang der Richtung: Ebene senkrecht zur Richtung, Achse (auch Kreiskante) und gerade Kante quer dazu;
    sonst None."""
    g = _element(form)
    if g is None:
        return None
    art, p, d = g
    c = abs(float(d @ richtung))
    if (art == "ebene" and c < 0.9999) or (art in ("achse", "kante") and c > 1e-4):
        return None
    return float(p @ richtung)


def _passendes_mass(pmi, lagen: dict[int, float], a: float, b: float):
    """PMI-Laengenmass mit Flaechen an beiden Lagen und passendem Nennwert (auch Muster), sonst None."""
    abstand = abs(b - a)
    for p in pmi:
        if p.art != "mass" or p.nennwert is None or ist_winkel(p) or abs(p.nennwert - abstand) > 1e-3:
            continue
        orte = [lagen[i] for i in p.flaechen if i in lagen]
        if any(abs(o - a) < 1e-4 for o in orte) and any(abs(o - b) < 1e-4 for o in orte):
            return p
    return None


def _aussen_normale(flaeche):
    """Normale aus dem Material in Flaechenmitte."""
    from OCC.Core.BRepGProp import BRepGProp_Face
    from OCC.Core.gp import gp_Pnt, gp_Vec
    gf = BRepGProp_Face(flaeche)
    u0, u1, v0, v1 = gf.Bounds()
    p, n = gp_Pnt(), gp_Vec()
    gf.Normal((u0 + u1) / 2, (v0 + v1) / 2, p, n)
    v = np.array([n.X(), n.Y(), n.Z()])
    return v / (np.linalg.norm(v) or 1.0)


def lage_glieder(modell, pmi, flaeche: int, richtung, vorzeichen: int, lagen: dict[int, float]):
    """Glieder der Lagetoleranzen einer Endflaeche (vorzeichen -1: erste, +1: letzte Flaeche); (Glieder, Hinweise)."""
    from .toleranzzone import _grenzen_aussen_innen, _groesse, bezugsverschiebung
    glieder, hinweise = [], []
    ort = lagen.get(flaeche)
    art = (_element(modell.flaechen[flaeche]) or ("",))[0]
    gleiche_art = {}  # Muster nur aus Elementen gleicher Art (Achse mit Achse, Ebene mit Ebene)

    def passt(i: int) -> bool:
        if i not in gleiche_art:
            gleiche_art[i] = i < len(modell.flaechen) and (_element(modell.flaechen[i]) or ("",))[0] == art
        return gleiche_art[i] and i in lagen and abs(lagen[i] - ort) < 1e-4
    for p in pmi:
        if p.art != "toleranz" or p.wert is None or (p.wert <= 0 and not p.material):  # 0 Ⓜ: Zone nur Bonus
            continue
        if not (p.typ in LAGE_TYPEN or (p.typ in PROFIL_TYPEN and p.bezuege)):
            continue
        # gilt fuer die Flaeche selbst oder fuer ein Muster gleicher Lage (z. B. zwei Halbschalen, Lochbild)
        if flaeche not in p.flaechen and not any(passt(i) for i in p.flaechen):
            continue
        t = float(p.wert)
        if p.typ in PROFIL_TYPEN and lage(modell.flaechen[flaeche], richtung) is not None \
                and _ebene_oder_achse(modell.flaechen[flaeche])[0] == "ebene":
            aussen, innen = _grenzen_aussen_innen(p, t)
            s = float(np.sign(_aussen_normale(modell.flaechen[flaeche]) @ richtung)) or 1.0
            werte = sorted((vorzeichen * aussen * s, vorzeichen * innen * s))
        else:
            werte = [-t / 2, t / 2]
        name = f"{p.nummer}: {p.wert_text()}"
        if p.material in ("M", "L"):
            # Bonus: die Zone waechst bis um die Groessentoleranz des Elements (Worst Case: voller Bonus)
            dmin, dmax = _groesse(p, pmi, 0.0)
            if dmax > dmin:
                werte = [werte[0] - (dmax - dmin) / 2, werte[1] + (dmax - dmin) / 2]
                name += " " + tr("+ Bonus bis {:g}").format(dmax - dmin)
            else:
                hinweise.append(tr("{}: Bonus bei Ⓜ/Ⓛ ohne Maß am Element nicht bestimmbar").format(name))
        glieder.append(Glied(name, 0.0, werte[1], werte[0], 1, p.nummer, quelle="lage", flaechen=(flaeche,)))
        for bezug, mat, weg in bezugsverschiebung(p, pmi):
            # Bezug mit Ⓜ/Ⓛ: die Zone darf sich mit dem Bezugselement um dessen Groessentoleranz verschieben
            glieder.append(Glied(f"{p.nummer}: " + tr("Bezugsverschiebung {} ({})").format(bezug, mat), 0.0,
                                 weg / 2, -weg / 2, 1, p.nummer, quelle="lage", flaechen=(flaeche,)))
    return glieder, hinweise


def _index(modell, e) -> int | None:
    """Flaechenindex eines Ketteneintrags (Index oder Form); Kanten: None."""
    from OCC.Core.TopAbs import TopAbs_FACE
    if isinstance(e, int):
        return e
    return modell.flaechen_index(e) if e.ShapeType() == TopAbs_FACE else None


def kette_aus_flaechen(modell, flaechen: list, pmi, allgemein: str = "",
                       lagetoleranzen: bool = True) -> tuple[list[Glied], tuple, list[str]]:
    """Glieder aus Flaechen in Kettenreihenfolge (siehe Modulbeschreibung); (Glieder, Richtung, Hinweise).
    Eintraege: Flaechenindex oder Form (Flaeche oder Kante; Kanten bekommen keine PMI, nur Allgemeintoleranz)."""
    from .toleranzzone import iso2768_laenge
    hinweise = []
    if len(flaechen) < 2:
        return [], (0.0, 0.0, 0.0), [tr("Mindestens zwei Flächen in Kettenreihenfolge wählen")]
    formen = [modell.flaechen[e] if isinstance(e, int) else e for e in flaechen]
    flaechen = [_index(modell, e) for e in flaechen]
    erste = next((g for g in map(_element, formen) if g is not None and g[0] == "ebene"), None)
    if erste is None:
        return [], (0.0, 0.0, 0.0), [tr("Die Kettenrichtung braucht eine ebene Fläche in der Auswahl")]
    richtung = erste[2] / np.linalg.norm(erste[2])
    orte = [lage(f, richtung) for f in formen]
    if None in orte:
        k = orte.index(None)
        return [], tuple(richtung), [tr("Element {} liegt nicht quer zur Kettenrichtung").format(k + 1)]
    if orte[-1] < orte[0]:  # Schlussmass positiv: Richtung von der ersten zur letzten Flaeche
        richtung, orte = -richtung, [-o for o in orte]
    # Lagen aller ebenen/zylindrischen Flaechen quer zur Richtung fuer die PMI-Zuordnung (Muster, geteilte Flaechen)
    lagen = {}
    for i, f in enumerate(modell.flaechen):
        o = lage(f, richtung)
        if o is not None:
            lagen[i] = o
    glieder = []
    for (fa, a), (fb, b) in zip(zip(flaechen, orte), zip(flaechen[1:], orte[1:])):
        nenn = abs(b - a)
        if nenn < 1e-6:
            continue  # gleiche Lage: kein Glied
        r = 1 if b > a else -1
        ende = tuple(i for i in (fa, fb) if i is not None)
        p = _passendes_mass(pmi, lagen, a, b) if None not in (fa, fb) else None
        if p is not None:
            h, m = p.grenzen()
            h, m = (p.nennwert, p.nennwert) if h is None or m is None else (h, m)
            glieder.append(Glied(f"{p.nummer}: {p.wert_text()}", nenn, nenn + h - p.nennwert,
                                 nenn + m - p.nennwert, r, p.nummer, flaechen=ende))
            continue
        t = iso2768_laenge(allgemein, nenn) if allgemein else None
        if t:
            glieder.append(Glied(f"{nenn:.4g} ±{t:g} (ISO 2768-{allgemein})", nenn, nenn + t, nenn - t, r,
                                 quelle="allgemein", flaechen=ende))
        else:
            glieder.append(Glied(f"{nenn:.4g}", nenn, nenn, nenn, r, quelle="ohne", flaechen=ende))
            hinweise.append(tr("Glied {:.4g} mm ohne Toleranz (keine PMI, keine Allgemeintoleranz)").format(nenn))
    if lagetoleranzen and glieder:
        for f, vorzeichen in ((flaechen[0], -1), (flaechen[-1], 1)):
            if f is None or f not in lagen:
                continue  # Kante: keine PMI
            g, h = lage_glieder(modell, pmi, f, richtung, vorzeichen, lagen)
            glieder.extend(g)
            hinweise.extend(h)
    return glieder, tuple(float(x) for x in richtung), hinweise


SPALTEN = ("Glied", "Richtung", "Nennmaß", "Höchstmaß", "Mindestmaß", "Toleranz", "Quelle", "Verteilung", "Cp / Form",
           "Versatz", "Faktor", "Anteil")


def als_csv(glieder: list[Glied], e: Ergebnis, cp: float = 1.0) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    zahl = lambda x: f"{x:.4f}".replace(".", ",")  # noqa: E731
    for g, anteil in zip(glieder, e.anteile or [0.0] * len(glieder)):
        w.writerow([g.name, "+" if g.richtung > 0 else "−"] +
                   [zahl(x) for x in (g.nenn, g.hoechst, g.mindest, g.toleranz)] +
                   [tr(QUELLE[g.quelle]), tr(VERTEILUNG[g.verteilung]),
                    zahl(g.cp or cp) if g.verteilung == "normal" else
                    f"a = {zahl(g.form)}" if g.verteilung == "trapez" else
                    f"n = {len(g.messwerte)}, σ = {zahl(g.sigma(cp))}" if g.gemessen else "", zahl(g.wirk_versatz),
                    zahl(g.faktor),
                    f"{anteil:.1%}".replace(".", ",")])
    w.writerow([])
    zeilen = [(tr("Schlussmaß (nominal)"), e.nenn), (tr("Worst Case min"), e.wc_min), (tr("Worst Case max"), e.wc_max),
              (tr("Statistisch (RSS) ±"), e.rss), (tr("Monte Carlo 0,135 %"), e.mc_min),
              (tr("Monte Carlo 99,865 %"), e.mc_max)]
    if e.cp is not None:
        zeilen += [("Cp", e.cp), ("Cpk", e.cpk), (tr("Anteil außerhalb (Normalverteilung)"), e.ausserhalb),
                   (tr("Anteil außerhalb (Monte Carlo)"), e.mc_ausserhalb)]
    zeilen.append((tr("Wirksame Beitragsleister"), e.n_eff))
    for text, wert in zeilen:
        w.writerow([text, "", zahl(wert)])
    w.writerow([tr("Anwendbar"), "", tr("statistisch") if e.statistisch else tr("arithmetisch"), anwendbar_text(e)])
    return puffer.getvalue()


def messwerte_aus_text(text: str, spalte: int = 0) -> list[float]:
    """Zahlen aus eingefuegtem Text oder CSV: eine Zeile -> alle Zahlen; mehrere Zeilen -> je Zeile die Zahl der
    Spalte (1 = erste, 0 = letzte Zahl der Zeile). Dezimalkomma wird erkannt; Zeilen ohne Zahl (Kopf) entfallen."""
    import re

    def zahlen(zeile):
        out = []
        for teil in re.split(r"[;\t ]+|,(?=\s)", zeile.strip()):
            teil = teil.strip()
            if "," in teil and "." not in teil:
                teil = teil.replace(",", ".")
            try:
                out.append(float(teil))
            except ValueError:
                continue
        return out
    zeilen = [z for z in text.splitlines() if z.strip()]
    if len(zeilen) == 1:
        return zahlen(zeilen[0])
    out = []
    for z in zeilen:
        werte = zahlen(z)
        if werte and (spalte == 0 or spalte <= len(werte)):
            out.append(werte[spalte - 1] if spalte else werte[-1])
    return out


def richtungen_aus_schlussmass(glieder: list[Glied], modell, flaeche_a: int, flaeche_b: int):
    """Vorzeichen und Reihenfolge der Glieder aus dem Schlussmass zwischen zwei Flaechen (erste: Ebene, gibt die
    Kettenrichtung vor): die Lagen aller Gliedflaechen entlang der Richtung bilden einen Graphen, der Weg von a nach b
    ergibt die Glieder mit dem Vorzeichen ihrer Laufrichtung. Rueckgabe (Glieder in Kettenreihenfolge, Hinweise);
    Glieder ausserhalb des Wegs und Lagetoleranzen bleiben unveraendert dahinter."""
    from collections import deque
    hinweise: list[str] = []
    erste = _ebene_oder_achse(modell.flaechen[flaeche_a])
    if erste is None or erste[0] != "ebene":
        return glieder, [tr("Die erste Fläche des Schlussmaßes muss eben sein (sie gibt die Richtung vor)")]
    richtung = erste[2] / np.linalg.norm(erste[2])
    pa, pb = lage(modell.flaechen[flaeche_a], richtung), lage(modell.flaechen[flaeche_b], richtung)
    if pb is None:
        return glieder, [tr("Die zweite Fläche liegt nicht quer zur Kettenrichtung")]
    if pb < pa:  # Schlussmass positiv: Richtung von a nach b
        richtung, pa, pb = -richtung, -pa, -pb
    knoten = lambda x: round(x, 4)  # noqa: E731
    kanten: dict[float, list[tuple[float, int]]] = {}
    for i, g in enumerate(glieder):
        if g.quelle == "lage":
            continue
        orte = sorted({knoten(o) for f in g.flaechen if f < len(modell.flaechen)
                       for o in [lage(modell.flaechen[f], richtung)] if o is not None})
        paar = [(a, b) for a in orte for b in orte if b > a and (g.nenn <= 0 or abs(b - a - abs(g.nenn)) < 1e-3)]
        if len(paar) != 1:
            hinweise.append(tr("{}: Lage der Flächen entlang der Kette nicht eindeutig").format(g.name))
            continue
        a, b = paar[0]
        kanten.setdefault(a, []).append((b, i))
        kanten.setdefault(b, []).append((a, i))
    start, ziel = knoten(pa), knoten(pb)
    vorher: dict[float, tuple[float, int]] = {start: (start, -1)}
    offen = deque([start])
    while offen and ziel not in vorher:
        x = offen.popleft()
        for y, i in kanten.get(x, []):
            if y not in vorher:
                vorher[y] = (x, i)
                offen.append(y)
    if ziel not in vorher:
        return glieder, hinweise + [tr("Kein geschlossener Weg vom ersten zum zweiten Schlussmaß-Element über die "
                                       "Glieder")]
    weg = []
    x = ziel
    while x != start:
        y, i = vorher[x]
        weg.append((i, 1 if x > y else -1))
        x = y
    weg.reverse()
    for i, r in weg:
        glieder[i].richtung = r
    auf_weg = {i for i, _ in weg}
    rest = [g for i, g in enumerate(glieder) if i not in auf_weg]
    for g in rest:
        if g.quelle != "lage":
            hinweise.append(tr("{}: nicht auf dem Weg des Schlussmaßes").format(g.name))
    return [glieder[i] for i, _ in weg] + rest, hinweise


def glied_strecke(g: Glied, modell) -> tuple[tuple, tuple] | None:
    """Strecke eines Glieds fuer die Anzeige: vom Schwerpunkt der ersten Flaeche entlang der Kettenrichtung bis zur
    Lage der zweiten (Ebene senkrecht bzw. Achse quer zur Richtung); None ohne zwei passende Flaechen."""
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    flaechen = [modell.flaechen[i] for i in g.flaechen if isinstance(i, int) and i < len(modell.flaechen)]
    if len(flaechen) < 2:
        return None
    ebene = next((x for x in map(_ebene_oder_achse, flaechen) if x is not None and x[0] == "ebene"), None)
    if ebene is None:
        return None
    n = ebene[2] / np.linalg.norm(ebene[2])
    orte = [lage(f, n) for f in flaechen[:2]]
    if None in orte:
        return None
    pr = GProp_GProps()
    brepgprop.SurfaceProperties(flaechen[0], pr)
    c = pr.CentreOfMass()
    start = np.array([c.X(), c.Y(), c.Z()]) + n * (orte[0] - float(np.array([c.X(), c.Y(), c.Z()]) @ n))
    ende = start + n * (orte[1] - orte[0])
    return tuple(float(x) for x in start), tuple(float(x) for x in ende)
