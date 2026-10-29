"""Messgroessen zwischen Teilen einer Baugruppe: Spalt und Buendigkeit mit Worst Case, Monte Carlo und Rangfolge
der Beitragenden (ohne Qt), PLAN §8.20 Stufe 4.

Lineares Modell: jedes Teil i hat eine kleine Bewegung x_i = (w, v) um den Ursprung (feste Teile x = 0). Jede
Verbindung begrenzt die Relativbewegung x_teil - x_gegen in ihren gesperrten Richtungen (Baugruppe.zeilen).
Eine Messgroesse ist der Abstand eines Punkts p der Flaeche A (Flaechenschwerpunkt) zur Ebene der Flaeche B entlang
deren Normalen n; ihre Aenderung ist c . (x_A - x_B) mit c = (p x n, n) - die Ebene von B bewegt sich starr mit B.
An Achsen (Bohrung, Zapfen): Achse zu Ebene misst den Achspunkt in der Mitte der Zylinderflaeche (Achse parallel zur
Ebene), Achsabstand zweier paralleler Achsen den Abstand entlang ihrer Verbindungssenkrechten u (linearisiert).
Am Punkt: statt des Flaechenschwerpunkts misst ein angeklickter Punkt auf A (beliebige Flaeche) zur Ebene von B
(Normale) bzw. zur Achse von B (radial) - z. B. der Spalt an einer Ecke.
- Worst Case: Extremwerte per linearem Programm ueber alle Verbindungen zugleich; Bewegungen nur im Zeilenraum der
  Verbindungen (freie Freiheitsgrade bleiben in Nennlage, die Messgroesse heisst dann "unbestimmt").
- Monte Carlo: je Verbindung werden die Spielraeume gezogen (normalverteilt, Spielraum = 3 sigma, abgeschnitten;
  koaxial je Eingriffsende ein Punkt in der Kreisscheibe), die Teilbewegungen folgen als gewichteter Ausgleich (Gewicht
  1 / Spielraum je Zeile): bei Ueberbestimmung bestimmt die engere Verbindung die Lage, wie beim Fuegen; keine
  Kontaktrechnung.
- Beitragende: Worst-Case-Bereich, wenn nur diese Verbindung streut (alle anderen in Nennlage), und Varianzanteil
  aus Monte Carlo (Verbindungen unabhaengig).
- Ⓜ/Ⓛ-Bonus und Bezugsverschiebung einer Verbindung (Verbindung.bonus) sind ein eigener Beitragender auf denselben
  Zeilen: Worst Case voller Bonus (Spielraum + Bonus), Monte Carlo mit gezogenem Istmass (Verbindung.mc_bonus).
- Waermeausdehnung (deterministisch, je Temperaturfall): jedes Teil dehnt sich um seinen Fixierpunkt aus (Mitte
  seiner Verbindungsmerkmale; feste Teile: Mitte der Merkmale, an denen andere Teile haengen) mit
  u_i(x) = u_gegen(o_i) + alpha_i * (T_i - 20 °C) * (x - o_i); der Fixierpunkt folgt dem Gegenteil (Verbindungsbaum).
  Die Messgroesse aendert sich um n . (u_A(p) - u_B(q)) mit q = Fusspunkt von p auf der Ebene bzw. Achse von B.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr

SPALT, BUENDIG, ACHSE_EBENE, ACHSABSTAND = "spalt", "buendig", "achse_ebene", "achsabstand"
PUNKT_EBENE, PUNKT_ACHSE = "punkt_ebene", "punkt_achse"
ART_TEXT = {SPALT: "Spalt", BUENDIG: "Bündigkeit", ACHSE_EBENE: "Achse zu Ebene", ACHSABSTAND: "Achsabstand",
            PUNKT_EBENE: "Punkt zu Ebene", PUNKT_ACHSE: "Punkt zu Achse"}


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
    punkt: list[float] | None = None  # Messpunkt auf A in Dateilage des Teils (None: Flaechenschwerpunkt)
    freigabe: dict = field(default_factory=dict)  # manuelle Freigabe {"geprueft", "name", "datum", "kommentar"}


@dataclass
class Beitrag:
    verbindung: int
    bereich: float  # Worst-Case-Breite (max - min), wenn nur diese Verbindung streut
    anteil_wc: float  # Anteil an der Summe der Bereiche
    anteil_var: float  # Varianzanteil aus Monte Carlo
    bonus: bool = False  # Ⓜ/Ⓛ-Bonus bzw. Bezugsverschiebung der Verbindung statt ihres Spielraums


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
    waerme: float | None = None  # Aenderung durch Waermeausdehnung (mm) beim gewaehlten Temperaturfall
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


def art_fuer(fa, fb, am_punkt: bool = False) -> str | None:
    """Spalt bei gegenueberliegenden, Buendigkeit bei gleichgerichteten parallelen Ebenen, Achse zu Ebene (Achse
    parallel zur Ebene) und Achsabstand (parallele Achsen), sonst None. Am Punkt: Spalt/Buendigkeit bei parallelen
    Ebenen, sonst Punkt zu Ebene bzw. Punkt zu Achse (A beliebig)."""
    a, b = ebene(fa), ebene(fb)
    if am_punkt:
        if b is not None:
            return art_fuer(fa, fb) if a is not None and art_fuer(fa, fb) else PUNKT_EBENE
        return PUNKT_ACHSE if achse(fb) is not None else None
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
            mit = baugruppe.zeilen(v)
            for (z, lo, hi), (_, _, o) in zip(baugruppe.zeilen(v, bonus=False), mit):
                lp.append((v.nummer, self._relativ(v, z), lo, hi, o - hi))  # letzte Spalte: Bonus der Zeile
            zeilen, grenzen, ziehen = baugruppe.mc_zeilen(v)
            mc.append((v.nummer, np.array([self._relativ(v, z) for z in zeilen]).reshape(-1, self.n), grenzen, ziehen,
                       baugruppe.mc_bonus(v)))
        self.lp = lp
        self.mc = mc
        a = np.array([z for _, z, *_ in lp]).reshape(-1, self.n)
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

    def _geometrie(self, m: Messgroesse, fa, fb):
        """Messpunkt p (Teil tp), Bezugspunkt q (Teil tq) und Messrichtung n in der Zusammenbaulage."""
        la, lb = self.bg.lage(m.teil_a), self.bg.lage(m.teil_b)
        if m.punkt is not None:
            p = la[:3, :3] @ np.asarray(m.punkt, float) + la[:3, 3]
            if m.art == PUNKT_ACHSE:
                q, d = achse(fb, lb)
                quer = (p - q) - d * float((p - q) @ d)
                n = quer / np.linalg.norm(quer)
            else:
                q, n = ebene(fb, lb)
            return p, q, n, m.teil_a, m.teil_b
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
        return p, q, n, tp, tq

    def vektor(self, m: Messgroesse, fa, fb) -> tuple[float, np.ndarray]:
        """Nennwert und Empfindlichkeit c (Gesamtvektor) der Messgroesse: Abstand des Punkts p (Teil tp) zur Ebene
        bzw. Achse (Teil tq) entlang n; beide Teile wirken am Messpunkt p."""
        p, q, n, tp, tq = self._geometrie(m, fa, fb)
        nenn = float(n @ (p - q))
        c = np.zeros(self.n)
        e = _empfindlichkeit(p, n)
        for teil, vz in ((tp, 1.0), (tq, -1.0)):
            if teil in self._spalte:
                c[self._spalte[teil]:self._spalte[teil] + 6] += vz * e
        return nenn, c

    def _fixierpunkt(self, teil: int) -> np.ndarray:
        """Mitte der Verbindungsmerkmale, mit denen das Teil haengt (feste Teile: an denen andere haengen)."""
        punkte = []
        for v in self.bg.verbindungen:
            if v.nummer not in self.bg.formen:
                continue
            mt, mg = self.bg.merkmale(v)
            if v.teil == teil and mt is not None:
                punkte.append(np.asarray(mt[1], float))
            elif v.gegen_teil == teil and mg is not None and (self.bg.fest(teil) or not punkte):
                punkte.append(np.asarray(mg[1], float))
        return np.mean(punkte, axis=0) if punkte else np.zeros(3)

    def _waerme_weg(self, teil: int, x: np.ndarray, dehnung: dict, tiefe: int = 0) -> np.ndarray:
        """Verschiebung des Punkts x des Teils durch Waermeausdehnung (siehe Modulbeschreibung)."""
        e = dehnung.get(teil, 0.0)
        o = self._fixierpunkt(teil)
        eigen = e * (np.asarray(x, float) - o)
        v = next((v for v in self.bg.verbindungen if v.teil == teil), None)
        if v is None or self.bg.fest(teil) or tiefe > 20:
            return eigen
        return self._waerme_weg(v.gegen_teil, o, dehnung, tiefe + 1) + eigen

    def waermeverschiebung(self, m: Messgroesse, fa, fb, alpha: dict, temperatur: dict) -> float:
        """Aenderung der Messgroesse (mm) bei Teiltemperaturen; alpha: Teil -> 1e-6/K, temperatur: Teil -> °C
        (fehlend: 20 °C, also keine Dehnung)."""
        from .werkstoffe import REFERENZ
        p, q, n, tp, tq = self._geometrie(m, fa, fb)
        dehnung = {t: (alpha.get(t) or 0.0) * 1e-6 * (temperatur.get(t, REFERENZ) - REFERENZ)
                   for t in set(alpha) | set(temperatur)}
        fuss = p - n * float(n @ (p - q))  # Fusspunkt von p auf B
        return float(n @ (self._waerme_weg(tp, p, dehnung) - self._waerme_weg(tq, fuss, dehnung)))

    def _mutter(self, teil: int) -> int | None:
        """Gegenteil der ersten Verbindung des Teils (Verbindungsbaum), None fuer feste Teile."""
        return next((v.gegen_teil for v in self.bg.verbindungen if v.teil == teil), None)

    def _pfad(self, teil: int) -> list[int]:
        out = [teil]
        while (m := self._mutter(out[-1])) is not None and m not in out:
            out.append(m)
        return out

    def _kettenpunkt(self, teil: int) -> np.ndarray:
        """Ursprung des Kettenglieds: Merkmalspunkt am Gegenteil der ersten Verbindung (dort sind Verschiebung und
        Kippen der Zeilen entkoppelt, der Kasten um den Spielraum bleibt eng)."""
        v = next(v for v in self.bg.verbindungen if v.teil == teil)
        return np.asarray(self.bg.merkmale(v)[1][1], float)

    def _torsor_grenzen(self, teil: int, mitte: np.ndarray) -> list[tuple[float, float]]:
        """Min/Max je Komponente (w, v um mitte) der Bewegung des Teils gegen seine Gegenteile (die in Nennlage
        bleiben), aus den Spielraeumen der Verbindungen des Teils; freie Freiheitsgrade 0."""
        from .verbindung import Baugruppe
        zeilen = [z for v in self.bg.verbindungen if v.teil == teil for z in self.bg.zeilen(v, mitte)]
        if not zeilen:
            return [(0.0, 0.0)] * 6
        a = np.array([z for z, _, _ in zeilen])
        _, sv, vt = np.linalg.svd(a)
        basis = vt[:int((sv > 1e-9 * max(1.0, float(sv.max()))).sum())]
        ab, lo, hi = a @ basis.T, np.array([u for _, u, _ in zeilen]), np.array([o for _, _, o in zeilen])
        out = []
        for k in range(6):
            c = basis[:, k]
            ext = [Baugruppe._extrem(ab, lo, hi, vz * c) for vz in (1.0, -1.0)]
            werte = [float(c @ z) for z in ext if z is not None]
            out.append((min(werte, default=0.0), max(werte, default=0.0)))
        return out

    def als_kette3d(self, m: Messgroesse, fa, fb, namen: dict | None = None):
        """3D-Toleranzkette (kern.kette3d) der Messgroesse: Basis in der Bezugsebene bzw. -richtung von B (Z = n),
        je Teil auf dem Verbindungsweg von B zu A ein Glied mit der kleinen Bewegung um seinen Fixierpunkt
        (Komponentengrenzen aus den Spielraeumen gegen die Gegenteile, Teile auf der B-Seite umgekehrt);
        Schlussgroesse Z des Messpunkts. Komponenten unabhaengig (Kasten um den Spielraum): konservativ gegenueber
        der Baugruppenanalyse."""
        import math
        from . import kette3d as k3
        namen = namen or {}
        p, q, n, tp, tq = self._geometrie(m, fa, fb)
        weg_a, weg_b = self._pfad(tp), self._pfad(tq)
        gemeinsam = next((t for t in weg_a if t in weg_b), None)
        seite_b = weg_b[:weg_b.index(gemeinsam)] if gemeinsam in weg_b else weg_b
        seite_a = list(reversed(weg_a[:weg_a.index(gemeinsam)] if gemeinsam in weg_a else weg_a))
        r = _rahmen(n)  # Spalten: Achsen der Basis in Welt
        weg = [(t, vz) for t, vz in [(t, -1.0) for t in seite_b] + [(t, 1.0) for t in seite_a] if not self.bg.fest(t)]
        ursprung = self._kettenpunkt(weg[0][0]) if weg else p  # Bezugsglied endet am ersten Teil, nicht in 0,0,0
        glieder = [k3.glied(tr("Bezug"), **_lage_komponenten(r.T, r.T @ (ursprung - q)))]
        for teil, vz in weg:
            o = self._kettenpunkt(teil)
            grenzen = self._torsor_grenzen(teil, o)
            g = k3.Glied3D(tr("{} (umgekehrt)").format(namen.get(teil, teil)) if vz < 0 else
                           str(namen.get(teil, teil)))
            for i, c in enumerate(("rx", "ry", "rz", "x", "y", "z")):
                lo, hi = grenzen[i]
                lo, hi = (-hi, -lo) if vz < 0 else (lo, hi)
                if c.startswith("r"):
                    lo, hi = math.degrees(lo), math.degrees(hi)
                nenn = float((o - ursprung)["xyz".index(c)]) if not c.startswith("r") else 0.0
                g.werte[c] = k3.Komponente(nenn, hi, lo)
            glieder.append(g)
            ursprung = o
        basis = np.eye(4)
        basis[:3, :3], basis[:3, 3] = r, q
        return k3.Kette3D(glieder, tuple(float(x) for x in p - ursprung), (0.0, 0.0, 1.0), "z",
                          basis=basis.tolist())

    def glied_fuer_teil(self, teil: int, vorher: np.ndarray, name: str = ""):
        """3D-Kettenglied eines Teils im Zusammenbau (wie in als_kette3d): Verschiebung vom vorigen Kettenpunkt zum
        Fixierpunkt des Teils (Welt, ohne Nenndrehung), Grenzen der sechs Komponenten aus den Spielraeumen gegen seine
        Gegenteile. Ergebnis (Glied3D, neuer Kettenpunkt); None fuer ein festes Teil oder ohne Verbindung."""
        import math
        from . import kette3d as k3
        if self.bg.fest(teil) or not any(v.teil == teil for v in self.bg.verbindungen):
            return None
        o = self._kettenpunkt(teil)
        grenzen = self._torsor_grenzen(teil, o)
        g = k3.Glied3D(name or str(teil))
        for i, c in enumerate(("rx", "ry", "rz", "x", "y", "z")):
            lo, hi = grenzen[i]
            if c.startswith("r"):
                lo, hi = math.degrees(lo), math.degrees(hi)
            nenn = 0.0 if c.startswith("r") else float((o - np.asarray(vorher, float))["xyz".index(c)])
            g.werte[c] = k3.Komponente(nenn, hi, lo)
        return g, o

    def _extrem(self, c: np.ndarray, nur: int | None = None, bonus: bool = False) -> tuple[float, float]:
        """Min und Max von c . x im Spielraum samt Bonus (nur: nur diese Verbindung streut, mit bonus nur ihr
        Ⓜ/Ⓛ-Bonus, sonst nur ihr Spielraum)."""
        from scipy.optimize import linprog
        if not len(self.basis) or not self.lp:
            return 0.0, 0.0
        a = np.array([z for _, z, *_ in self.lp]) @ self.basis.T
        grenzen = [(u - b, o + b) if nur is None else (0.0, 0.0) if nr != nur else (-b, b) if bonus else (u, o)
                   for nr, _, u, o, b in self.lp]
        lo, hi = np.array([g[0] for g in grenzen]), np.array([g[1] for g in grenzen])
        cz = self.basis @ c
        werte = []
        for vz in (1.0, -1.0):
            r = linprog(-vz * cz, A_ub=np.vstack([a, -a]), b_ub=np.r_[hi, -lo], bounds=[(None, None)] * len(cz),
                        method="highs")
            werte.append(float(cz @ r.x) if r.status == 0 else 0.0)
        return werte[1], werte[0]

    def _stichproben(self, anzahl: int, zufall: int) -> list[tuple]:
        """Je Verbindung (Nummer, Zeilen k x n, Spielraeume k, Werte anzahl x k, Bonuswerte anzahl x k oder None)."""
        rng = np.random.default_rng(zufall)
        return [(nr, zeilen, grenzen, ziehen(rng, anzahl), None if bonus is None else bonus(rng, anzahl))
                for nr, zeilen, grenzen, ziehen, bonus in self.mc]

    def berechne(self, m: Messgroesse, fa, fb, proben: int = 20_000, zufall: int = 1) -> Ergebnis:
        nenn, c = self.vektor(m, fa, fb)
        frei = c - self.basis.T @ (self.basis @ c) if len(self.basis) else c
        unbestimmt = bool(np.linalg.norm(frei) > 1e-6 * max(1.0, float(np.linalg.norm(c))))
        lo, hi = self._extrem(c)
        stich = self._stichproben(proben, zufall)
        teile = []  # ((Verbindung, Bonus?), Beitrag je Probe)
        if stich and self.n:
            gesamt = np.vstack([z for _, z, *_ in stich])
            grenzen = np.concatenate([gr for _, _, gr, *_ in stich])
            gewicht = 1.0 / np.maximum(grenzen, 1e-6 * max(1e-9, float(grenzen.max())))
            g = c @ np.linalg.pinv(gesamt * gewicht[:, None]) * gewicht  # Messgroesse = g . y (gewichteter Ausgleich)
            k = 0
            for nr, zeilen, _, y, yb in stich:
                teile.append(((nr, False), y @ g[k:k + len(zeilen)]))
                if yb is not None:  # Bonus wirkt auf dieselben Zeilen (y + yb)
                    teile.append(((nr, True), yb @ g[k:k + len(zeilen)]))
                k += len(zeilen)
        werte = nenn + (np.sum([t for _, t in teile], axis=0) if teile else np.zeros(proben))
        var = {schluessel: float(np.var(t)) for schluessel, t in teile}
        summe_var = sum(var.values()) or 1.0
        bereiche = {(v.nummer, bonus): max(0.0, float(np.subtract(*self._extrem(c, v.nummer, bonus)[::-1])))
                    for v in self.bg.verbindungen for bonus in ((False, True) if v.bonus > 0 else (False,))}
        summe_wc = sum(bereiche.values()) or 1.0
        beitraege = sorted((Beitrag(nr, b, b / summe_wc, var.get((nr, bonus), 0.0) / summe_var, bonus)
                            for (nr, bonus), b in bereiche.items()), key=lambda x: (-x.anteil_var, -x.anteil_wc))
        q = np.quantile(werte, [0.00135, 0.99865])
        e = Ergebnis(nenn, nenn + lo, nenn + hi, float(werte.mean()), float(werte.std()), float(q[0]), float(q[1]),
                     unbestimmt=unbestimmt, beitraege=beitraege, proben=werte)
        _bewerte(e, m.soll_min, m.soll_max)
        return e


def _rahmen(n: np.ndarray) -> np.ndarray:
    """Orthonormale Achsen (Spalten) mit Z = n."""
    from .verbindung import _senkrechte
    t1, t2 = _senkrechte(n)
    if np.linalg.det(np.c_[t1, t2, n]) < 0:
        t1, t2 = t2, t1
    return np.c_[t1, t2, n]


def _lage_komponenten(r: np.ndarray, t: np.ndarray) -> dict:
    """Komponenten x..rz eines Glieds (kern.kette3d: erst verschieben, dann Drehung um X, Y, Z) fuer Drehung r und
    Verschiebung t."""
    import math
    b = math.asin(max(-1.0, min(1.0, float(r[0, 2]))))
    if abs(math.cos(b)) > 1e-9:
        a, c = math.atan2(-r[1, 2], r[2, 2]), math.atan2(-r[0, 1], r[0, 0])
    else:  # kardanische Sperre
        a, c = math.atan2(r[2, 1], r[1, 1]), 0.0
    return {"x": float(t[0]), "y": float(t[1]), "z": float(t[2]), "rx": math.degrees(a), "ry": math.degrees(b),
            "rz": math.degrees(c)}


def bewertung(e: Ergebnis, m: Messgroesse) -> tuple[str, str]:
    """Ampel wie bei der Toleranzkette ("gruen" | "gelb" | "rot" | ""): gruen, wenn der Worst-Case-Bereich (samt
    Waermeausdehnung) im Soll liegt; gelb (knapp), wenn Monte Carlo hoechstens 0,27 % ausserhalb sieht; sonst rot."""
    from .toleranzkette import GRENZE_RISIKO
    if m.soll_min is None and m.soll_max is None:
        return "", ""
    d = e.waerme or 0.0
    lo, hi = e.wc_min + d, e.wc_max + d
    u = m.soll_min if m.soll_min is not None else -np.inf
    o = m.soll_max if m.soll_max is not None else np.inf
    if u <= lo and hi <= o:
        return "gruen", tr("Worst Case im Soll")
    if (e.aussen or 0.0) <= GRENZE_RISIKO:
        return "gelb", tr("knapp: Worst Case verlässt das Soll, Monte Carlo {:.0f} ppm außerhalb").format(
            (e.aussen or 0.0) * 1e6)
    return "rot", tr("nicht eingehalten: {:.2%} außerhalb (Monte Carlo)").format(e.aussen or 0.0)


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


def beitrag_art(b: Beitrag, arten: dict) -> str:
    """Art des Beitragenden: Verbindungsart, beim Bonus "Bonus Ⓜ/Ⓛ / Bezugsverschiebung (Art)"."""
    from .verbindung import ART_TEXT as VERBINDUNG_ART
    art = tr(VERBINDUNG_ART.get(arten.get(b.verbindung), ""))
    return tr("Bonus Ⓜ/Ⓛ / Bezugsverschiebung ({})").format(art) if b.bonus else art


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
