"""Messgroessen zwischen Teilen einer Baugruppe: Spalt und Buendigkeit mit Worst Case, Monte Carlo und Rangfolge
der Beitragenden (ohne Qt), PLAN §8.20 Stufe 4.

Lineares Modell: jedes Teil i hat eine kleine Bewegung x_i = (w, v) um den Ursprung (feste Teile x = 0). Jede
Verbindung begrenzt die Relativbewegung x_teil - x_gegen in ihren gesperrten Richtungen (Baugruppe.zeilen).
Eine Messgroesse ist der Abstand eines Punkts p der Flaeche A (Flaechenschwerpunkt) zur Ebene der Flaeche B entlang
deren Normalen n; ihre Aenderung ist c . (x_A - x_B) mit c = (p x n, n) - die Ebene von B bewegt sich starr mit B.
An Achsen (Bohrung, Zapfen): Achse zu Ebene misst den Achspunkt in der Mitte der Zylinderflaeche (Achse parallel zur
Ebene), Achsabstand zweier paralleler Achsen den Abstand entlang ihrer Verbindungssenkrechten u (linearisiert).
- Worst Case: Extremwerte per linearem Programm ueber alle Verbindungen zugleich; Bewegungen nur im Zeilenraum der
  Verbindungen (freie Freiheitsgrade bleiben in Nennlage, die Messgroesse heisst dann "unbestimmt").
- Monte Carlo: je Verbindung werden die Spielraeume gezogen (normalverteilt, Spielraum = 3 sigma, abgeschnitten;
  koaxial je Eingriffsende ein Punkt in der Kreisscheibe), die Teilbewegungen folgen als gewichteter Ausgleich (Gewicht
  1 / Spielraum je Zeile): bei Ueberbestimmung bestimmt die engere Verbindung die Lage, wie beim Fuegen; keine
  Kontaktrechnung.
- Beitragende: Worst-Case-Bereich, wenn nur diese Verbindung streut (alle anderen in Nennlage), und Varianzanteil
  aus Monte Carlo (Verbindungen unabhaengig).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr

SPALT, BUENDIG, ACHSE_EBENE, ACHSABSTAND = "spalt", "buendig", "achse_ebene", "achsabstand"
ART_TEXT = {SPALT: "Spalt", BUENDIG: "Bündigkeit", ACHSE_EBENE: "Achse zu Ebene", ACHSABSTAND: "Achsabstand"}


@dataclass
class Messgroesse:
    nummer: int
    teil_a: int
    flaeche_a: int
    teil_b: int
    flaeche_b: int
    art: str = SPALT
    soll_min: float | None = None
    soll_max: float | None = None
    name: str = ""


@dataclass
class Beitrag:
    verbindung: int
    bereich: float  # Worst-Case-Breite (max - min), wenn nur diese Verbindung streut
    anteil_wc: float  # Anteil an der Summe der Bereiche
    anteil_var: float  # Varianzanteil aus Monte Carlo


@dataclass
class Ergebnis:
    nenn: float
    wc_min: float
    wc_max: float
    mittel: float
    std: float
    mc_min: float  # 0,135 %-Quantil
    mc_max: float  # 99,865 %-Quantil
    aussen: float | None = None  # Anteil ausserhalb des Solls (0..1)
    cp: float | None = None
    cpk: float | None = None
    unbestimmt: bool = False  # haengt von freien Freiheitsgraden ab
    beitraege: list[Beitrag] = field(default_factory=list)
    proben: np.ndarray | None = None


def ebene(flaeche, lage: np.ndarray | None = None):
    """(Schwerpunkt, Normale aus dem Material) einer ebenen Flaeche in Weltlage oder None."""
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from .verbindung import merkmal
    m = merkmal(flaeche, lage)
    if m is None or m[0] != "ebene":
        return None
    pr = GProp_GProps()
    brepgprop.SurfaceProperties(flaeche, pr)
    c = pr.CentreOfMass()
    p = np.array([c.X(), c.Y(), c.Z()])
    if lage is not None:
        p = lage[:3, :3] @ p + lage[:3, 3]
    return p, m[2]


def achse(flaeche, lage: np.ndarray | None = None):
    """(Punkt in der Mitte der Flaeche auf der Achse, Richtung) einer Zylinder-/Kegelflaeche in Weltlage oder None."""
    from . import toleranzzone as tz
    a = tz._achse([flaeche])
    if a is None:
        return None
    start, d, laenge, _r, _f = a
    p = start + d * laenge / 2
    if lage is not None:
        p, d = lage[:3, :3] @ p + lage[:3, 3], lage[:3, :3] @ d
    return p, d / np.linalg.norm(d)


def art_fuer(fa, fb) -> str | None:
    """Spalt bei gegenueberliegenden, Buendigkeit bei gleichgerichteten parallelen Ebenen, Achse zu Ebene (Achse
    parallel zur Ebene) und Achsabstand (parallele Achsen), sonst None."""
    a, b = ebene(fa), ebene(fb)
    xa, xb = (achse(fa) if a is None else None), (achse(fb) if b is None else None)
    if xa is not None and xb is not None:
        return ACHSABSTAND if abs(abs(float(xa[1] @ xb[1])) - 1) < 1e-3 and \
            np.linalg.norm(np.cross(xa[0] - xb[0], xb[1])) > 1e-6 else None
    if (xa is not None and b is not None) or (a is not None and xb is not None):
        d, n = (xa[1], b[1]) if xa is not None else (xb[1], a[1])
        return ACHSE_EBENE if abs(float(d @ n)) < 1e-3 else None
    if a is None or b is None:
        return None
    cos = float(a[1] @ b[1])
    if abs(abs(cos) - 1) > 1e-3:
        return None
    return SPALT if cos < 0 else BUENDIG


def _empfindlichkeit(punkt: np.ndarray, normale: np.ndarray) -> np.ndarray:
    return np.r_[np.cross(punkt, normale), normale]


class Analyse:
    """Lineares Modell aller Verbindungen einer Baugruppe fuer eine oder mehrere Messgroessen."""

    def __init__(self, baugruppe):
        self.bg = baugruppe
        self.teile = [t for t in baugruppe.teile() if not baugruppe.fest(t)]
        self._spalte = {t: 6 * i for i, t in enumerate(self.teile)}
        self.n = 6 * len(self.teile)
        lp, mc = [], []
        for v in baugruppe.verbindungen:
            for z, lo, hi in baugruppe.zeilen(v):
                lp.append((v.nummer, self._relativ(v, z), lo, hi))
            zeilen, grenzen, ziehen = baugruppe.mc_zeilen(v)
            mc.append((v.nummer, np.array([self._relativ(v, z) for z in zeilen]).reshape(-1, self.n), grenzen, ziehen))
        self.lp = lp
        self.mc = mc
        a = np.array([z for _, z, _, _ in lp]).reshape(-1, self.n)
        if len(a) and self.n:
            _, s, vt = np.linalg.svd(a)
            rang = int((s > 1e-9 * max(1.0, float(s.max()))).sum())
            self.basis = vt[:rang]
        else:
            self.basis = np.zeros((0, self.n))

    def _relativ(self, v, zeile: np.ndarray) -> np.ndarray:
        """Zeile fuer x_teil - x_gegen im Gesamtvektor."""
        out = np.zeros(self.n)
        for teil, vz in ((v.teil, 1.0), (v.gegen_teil, -1.0)):
            if teil in self._spalte:
                out[self._spalte[teil]:self._spalte[teil] + 6] += vz * zeile
        return out

    def vektor(self, m: Messgroesse, fa, fb) -> tuple[float, np.ndarray]:
        """Nennwert und Empfindlichkeit c (Gesamtvektor) der Messgroesse: Abstand des Punkts p (Teil tp) zur Ebene
        bzw. Achse (Teil tq) entlang n; beide Teile wirken am Messpunkt p."""
        la, lb = self.bg.lage(m.teil_a), self.bg.lage(m.teil_b)
        if m.art == ACHSABSTAND:
            pa, _ = achse(fa, la)
            qb, d = achse(fb, lb)
            quer = (pa - qb) - d * float((pa - qb) @ d)
            n = quer / np.linalg.norm(quer)
            p, q, tp, tq = pa, qb, m.teil_a, m.teil_b
        elif m.art == ACHSE_EBENE and ebene(fa) is None:  # A Achse, B Ebene
            p, _ = achse(fa, la)
            q, n = ebene(fb, lb)
            tp, tq = m.teil_a, m.teil_b
        elif m.art == ACHSE_EBENE:  # A Ebene, B Achse: Abstand der Achse von B zur Ebene von A
            p, _ = achse(fb, lb)
            q, n = ebene(fa, la)
            tp, tq = m.teil_b, m.teil_a
        else:
            p, _ = ebene(fa, la)
            q, n = ebene(fb, lb)
            tp, tq = m.teil_a, m.teil_b
        nenn = float(n @ (p - q))
        c = np.zeros(self.n)
        e = _empfindlichkeit(p, n)
        for teil, vz in ((tp, 1.0), (tq, -1.0)):
            if teil in self._spalte:
                c[self._spalte[teil]:self._spalte[teil] + 6] += vz * e
        return nenn, c

    def _extrem(self, c: np.ndarray, nur: int | None = None) -> tuple[float, float]:
        """Min und Max von c . x im Spielraum (nur: nur diese Verbindung streut)."""
        from scipy.optimize import linprog
        if not len(self.basis) or not self.lp:
            return 0.0, 0.0
        a = np.array([z for _, z, _, _ in self.lp]) @ self.basis.T
        lo = np.array([0.0 if nur is not None and nr != nur else u for nr, _, u, _ in self.lp])
        hi = np.array([0.0 if nur is not None and nr != nur else o for nr, _, _, o in self.lp])
        cz = self.basis @ c
        werte = []
        for vz in (1.0, -1.0):
            r = linprog(-vz * cz, A_ub=np.vstack([a, -a]), b_ub=np.r_[hi, -lo], bounds=[(None, None)] * len(cz),
                        method="highs")
            werte.append(float(cz @ r.x) if r.status == 0 else 0.0)
        return werte[1], werte[0]

    def _stichproben(self, anzahl: int, zufall: int) -> list[tuple[int, np.ndarray, np.ndarray, np.ndarray]]:
        """Je Verbindung (Nummer, Zeilen k x n, Spielraeume k, Werte anzahl x k)."""
        rng = np.random.default_rng(zufall)
        return [(nr, zeilen, grenzen, ziehen(rng, anzahl)) for nr, zeilen, grenzen, ziehen in self.mc]

    def berechne(self, m: Messgroesse, fa, fb, proben: int = 20_000, zufall: int = 1) -> Ergebnis:
        nenn, c = self.vektor(m, fa, fb)
        frei = c - self.basis.T @ (self.basis @ c) if len(self.basis) else c
        unbestimmt = bool(np.linalg.norm(frei) > 1e-6 * max(1.0, float(np.linalg.norm(c))))
        lo, hi = self._extrem(c)
        stich = self._stichproben(proben, zufall)
        teile = []
        if stich and self.n:
            gesamt = np.vstack([z for _, z, _, _ in stich])
            grenzen = np.concatenate([gr for _, _, gr, _ in stich])
            gewicht = 1.0 / np.maximum(grenzen, 1e-6 * max(1e-9, float(grenzen.max())))
            g = c @ np.linalg.pinv(gesamt * gewicht[:, None]) * gewicht  # Messgroesse = g . y (gewichteter Ausgleich)
            k = 0
            for nr, zeilen, _, y in stich:
                teile.append((nr, y @ g[k:k + len(zeilen)]))
                k += len(zeilen)
        werte = nenn + (np.sum([t for _, t in teile], axis=0) if teile else np.zeros(proben))
        var = {nr: float(np.var(t)) for nr, t in teile}
        summe_var = sum(var.values()) or 1.0
        bereiche = {v.nummer: max(0.0, float(np.subtract(*self._extrem(c, v.nummer)[::-1])))
                    for v in self.bg.verbindungen}
        summe_wc = sum(bereiche.values()) or 1.0
        beitraege = sorted((Beitrag(nr, b, b / summe_wc, var.get(nr, 0.0) / summe_var) for nr, b in bereiche.items()),
                           key=lambda x: (-x.anteil_var, -x.anteil_wc))
        q = np.quantile(werte, [0.00135, 0.99865])
        e = Ergebnis(nenn, nenn + lo, nenn + hi, float(werte.mean()), float(werte.std()), float(q[0]), float(q[1]),
                     unbestimmt=unbestimmt, beitraege=beitraege, proben=werte)
        _bewerte(e, m.soll_min, m.soll_max)
        return e


def _bewerte(e: Ergebnis, smin: float | None, smax: float | None):
    """Anteil ausserhalb, Cp und Cpk gegen das Soll (einseitig, wenn nur eine Grenze)."""
    if smin is None and smax is None:
        return
    w = e.proben
    aus = np.zeros(len(w), bool)
    if smin is not None:
        aus |= w < smin
    if smax is not None:
        aus |= w > smax
    e.aussen = float(aus.mean())
    s = e.std
    if s <= 1e-15:
        return
    if smin is not None and smax is not None:
        e.cp = (smax - smin) / (6 * s)
    ks = [x for x in ((smax - e.mittel) / (3 * s) if smax is not None else None,
                      (e.mittel - smin) / (3 * s) if smin is not None else None) if x is not None]
    e.cpk = min(ks)


def text(m: Messgroesse, namen: dict) -> str:
    return m.name or "{} {} – {}".format(tr(ART_TEXT[m.art]), namen.get(m.teil_a, m.teil_a),
                                         namen.get(m.teil_b, m.teil_b))


def soll_text(m: Messgroesse) -> str:
    if m.soll_min is None and m.soll_max is None:
        return ""
    lo = "" if m.soll_min is None else f"{m.soll_min:g}"
    hi = "" if m.soll_max is None else f"{m.soll_max:g}"
    return f"{lo} … {hi}"


def lies_soll(s: str) -> tuple[float | None, float | None]:
    """'14.5 … 15.5', '14,5..15,5', '>= 1', '<= 2' oder leer."""
    s = s.strip().replace(",", ".").replace("…", "..")
    if not s:
        return None, None
    if s.startswith((">=", "≥", ">")):
        return float(s.lstrip(">=≥ ")), None
    if s.startswith(("<=", "≤", "<")):
        return None, float(s.lstrip("<=≤ "))
    lo, _, hi = s.partition("..")
    return (float(lo) if lo.strip() else None), (float(hi.lstrip(".")) if hi.strip(". ") else None)
