"""Eindimensionale Toleranzkette (Massskette): Schlussmass nach Worst Case, RSS und Monte Carlo (ohne Qt).

Jedes Glied ist ein Mass mit Nennmass, Hoechst- und Mindestmass und Richtung (+1 vergroessert das Schlussmass,
-1 verkleinert es). Statistik je Glied: Mittelwert in Toleranzmitte; normalverteilt mit sigma = Toleranz / (6 * Cp)
(Cp je Glied oder der Kette, Cp = 1: Toleranz = +-3 sigma) oder gleichverteilt ueber die Toleranz
(sigma = Toleranz / (2 * Wurzel 3)). Das statistische Ergebnis ist +-3 sigma des Schlussmasses, der Anteil eines
Glieds sein Varianzanteil.

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

VERTEILUNG = {"normal": "Normal", "gleich": "Gleichverteilt"}
QUELLE = {"pmi": "PMI", "lage": "Lagetoleranz", "allgemein": "Allgemeintoleranz", "ohne": "ohne Toleranz"}
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

    @property
    def mitte(self) -> float:
        return (self.hoechst + self.mindest) / 2

    @property
    def toleranz(self) -> float:
        return self.hoechst - self.mindest

    def sigma(self, cp_kette: float = 1.0) -> float:
        if self.verteilung == "gleich":
            return self.toleranz / (2 * math.sqrt(3))
        return self.toleranz / (6 * (self.cp or cp_kette))


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


def glied_von_pmi(p, richtung: int = 1) -> Glied | None:
    """Kettenglied aus einem Laengenmass mit Grenzen (auch aus ISO-286-Klasse); None fuer Winkel und ohne Nennmass."""
    if p.art != "mass" or p.nennwert is None or ist_winkel(p):
        return None
    h, m = p.grenzen()
    if h is None or m is None:
        h = m = p.nennwert
    return Glied(f"{p.nummer}: {p.wert_text()}", p.nennwert, h, m, richtung, p.nummer)


def ist_winkel(p) -> bool:
    """Winkelmasse passen nicht in eine Laengenkette."""
    return "Angle" in (p.typ or "") or "°" in p.wert_text()


def berechne(glieder: list[Glied], cp: float = 1.0, proben: int = 200_000, zufall: int = 1) -> Ergebnis:
    """Schlussmass; cp: Prozessfaehigkeit der Kette fuer Glieder ohne eigenen Wert."""
    if not glieder:
        return Ergebnis(0, 0, 0, 0, 0, 0, 0, 0, 0)
    r = np.array([g.richtung for g in glieder], float)
    nenn = float(sum(g.richtung * g.nenn for g in glieder))
    hi = np.array([g.hoechst for g in glieder])
    lo = np.array([g.mindest for g in glieder])
    wc_max = float(np.sum(np.where(r > 0, hi, lo) * r))
    wc_min = float(np.sum(np.where(r > 0, lo, hi) * r))
    mitte = float(np.sum((hi + lo) / 2 * r))
    sigma = np.array([g.sigma(cp) for g in glieder])
    varianz = float(np.sum(sigma ** 2))
    rss = float(3.0 * math.sqrt(varianz))  # +-3 sigma des Schlussmasses
    rng = np.random.default_rng(zufall)
    gleich = np.array([g.verteilung == "gleich" for g in glieder])
    proben_je = rng.standard_normal((proben, len(glieder))) * sigma + (hi + lo) / 2
    if gleich.any():
        proben_je[:, gleich] = rng.uniform(lo[gleich], hi[gleich], (proben, int(gleich.sum())))
    werte = proben_je @ r
    q = np.quantile(werte, [0.00135, 0.99865])
    anteile = [float(s ** 2 / varianz) if varianz > 0 else 0.0 for s in sigma]
    return Ergebnis(nenn, wc_min, wc_max, mitte, rss, float(q[0]), float(q[1]), float(werte.mean()),
                    float(werte.std()), anteile)


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


def lage(flaeche, richtung) -> float | None:
    """Lage entlang der Richtung: Ebene senkrecht zur Richtung, Achse quer dazu; sonst None."""
    g = _ebene_oder_achse(flaeche)
    if g is None:
        return None
    art, p, d = g
    c = abs(float(d @ richtung))
    if (art == "ebene" and c < 0.9999) or (art == "achse" and c > 1e-4):
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
    from .toleranzzone import _grenzen_aussen_innen
    glieder, hinweise = [], []
    ort = lagen.get(flaeche)
    for p in pmi:
        if p.art != "toleranz" or p.wert is None or p.wert <= 0:
            continue
        if not (p.typ in LAGE_TYPEN or (p.typ in PROFIL_TYPEN and p.bezuege)):
            continue
        # gilt fuer die Flaeche selbst oder fuer ein Muster gleicher Lage (z. B. zwei Halbschalen, Lochbild)
        if flaeche not in p.flaechen and not any(i in lagen and abs(lagen[i] - ort) < 1e-4 for i in p.flaechen):
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
        glieder.append(Glied(name, 0.0, werte[1], werte[0], 1, p.nummer, quelle="lage", flaechen=(flaeche,)))
        if p.material:
            hinweise.append(tr("{}: Bonus bei Ⓜ/Ⓛ nicht enthalten (Worst Case ohne Bonus)").format(name))
    return glieder, hinweise


def kette_aus_flaechen(modell, flaechen: list[int], pmi, allgemein: str = "",
                       lagetoleranzen: bool = True) -> tuple[list[Glied], tuple, list[str]]:
    """Glieder aus Flaechen in Kettenreihenfolge (siehe Modulbeschreibung); (Glieder, Richtung, Hinweise)."""
    from .toleranzzone import iso2768_laenge
    hinweise = []
    if len(flaechen) < 2:
        return [], (0.0, 0.0, 0.0), [tr("Mindestens zwei Flächen in Kettenreihenfolge wählen")]
    erste = next((_ebene_oder_achse(modell.flaechen[i]) for i in flaechen
                  if (_ebene_oder_achse(modell.flaechen[i]) or ("",))[0] == "ebene"), None)
    if erste is None:
        return [], (0.0, 0.0, 0.0), [tr("Die Kettenrichtung braucht eine ebene Fläche in der Auswahl")]
    richtung = erste[2] / np.linalg.norm(erste[2])
    orte = [lage(modell.flaechen[i], richtung) for i in flaechen]
    if None in orte:
        i = flaechen[orte.index(None)]
        return [], tuple(richtung), [tr("Fläche {} liegt nicht quer zur Kettenrichtung").format(i)]
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
        p = _passendes_mass(pmi, lagen, a, b)
        if p is not None:
            h, m = p.grenzen()
            h, m = (p.nennwert, p.nennwert) if h is None or m is None else (h, m)
            glieder.append(Glied(f"{p.nummer}: {p.wert_text()}", nenn, nenn + h - p.nennwert,
                                 nenn + m - p.nennwert, r, p.nummer, flaechen=(fa, fb)))
            continue
        t = iso2768_laenge(allgemein, nenn) if allgemein else None
        if t:
            glieder.append(Glied(f"{nenn:.4g} ±{t:g} (ISO 2768-{allgemein})", nenn, nenn + t, nenn - t, r,
                                 quelle="allgemein", flaechen=(fa, fb)))
        else:
            glieder.append(Glied(f"{nenn:.4g}", nenn, nenn, nenn, r, quelle="ohne", flaechen=(fa, fb)))
            hinweise.append(tr("Glied {:.4g} mm ohne Toleranz (keine PMI, keine Allgemeintoleranz)").format(nenn))
    if lagetoleranzen and glieder:
        for f, vorzeichen in ((flaechen[0], -1), (flaechen[-1], 1)):
            g, h = lage_glieder(modell, pmi, f, richtung, vorzeichen, lagen)
            glieder.extend(g)
            hinweise.extend(h)
    return glieder, tuple(float(x) for x in richtung), hinweise


SPALTEN = ("Glied", "Richtung", "Nennmaß", "Höchstmaß", "Mindestmaß", "Toleranz", "Quelle", "Verteilung", "Cp",
           "Anteil")


def als_csv(glieder: list[Glied], e: Ergebnis, cp: float = 1.0) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    zahl = lambda x: f"{x:.4f}".replace(".", ",")  # noqa: E731
    for g, anteil in zip(glieder, e.anteile or [0.0] * len(glieder)):
        w.writerow([g.name, "+" if g.richtung > 0 else "−"] +
                   [zahl(x) for x in (g.nenn, g.hoechst, g.mindest, g.toleranz)] +
                   [tr(QUELLE[g.quelle]), tr(VERTEILUNG[g.verteilung]),
                    zahl(g.cp or cp) if g.verteilung == "normal" else "", f"{anteil:.1%}".replace(".", ",")])
    w.writerow([])
    for text, wert in ((tr("Schlussmaß (nominal)"), e.nenn), (tr("Worst Case min"), e.wc_min),
                       (tr("Worst Case max"), e.wc_max), (tr("Statistisch (RSS) ±"), e.rss),
                       (tr("Monte Carlo 0,135 %"), e.mc_min), (tr("Monte Carlo 99,865 %"), e.mc_max)):
        w.writerow([text, "", zahl(wert)])
    return puffer.getvalue()
