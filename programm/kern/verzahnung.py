"""Verzahnungsdaten aus vorhandenen Modellen (PLAN §8.27, Stufe 1: Stirnraeder aussen und innen, gerade und schraeg).

Achse: Hauptachse der Traegheit mit dem abweichenden Moment (rotationssymmetrische Teile), Zylinderachsen gehen
vor, wenn sie dazu parallel sind. Stirnschnitte senkrecht zur Achse (exakt oder ueber Dreiecke, kern.schnitt):
der Radius r(theta) jeder geschlossenen Kontur ist periodisch, die staerkste Harmonische ergibt die Zaehnezahl z.
- da, df aus Kopf- und Fusskreis (innen vertauscht), Breite b aus den verzahnten Schnitten (Grenzen halbiert).
- Schraegungswinkel beta und Steigungsrichtung aus der Drehung des Zahnmusters entlang der Achse
  (tan beta = d/2 * dtheta/ds; dtheta/ds > 0 um die Achse: rechtssteigend).
- Grundkreis db aus einem Evolventen-Fit der Flankenpunkte im mittleren Stirnschnitt (theta = theta0 +- inv(alpha_r),
  cos alpha_r = rb / r), getrennt fuer beide Flankenseiten.
- Abgeleitet nach ISO 21771: fuer jeden ueblichen Normaleingriffswinkel alpha_n ergibt db mit beta ein Normalmodul
  mn; gewaehlt wird das Paar, dessen mn einem Normmodul (ISO 54) am naechsten liegt (Mehrdeutigkeit wird gemeldet).
  Profilverschiebung x aus der Zahndicke (innen: Lueckenweite) am Teilkreis, Zahnweite Wk ueber k Zaehne berechnet.
Genauigkeit: die Messwerte etwa bis zur Abtastung (Schnittkonturen), die abgeleiteten Werte haengen davon ab, dass
das Modell eine Evolventenverzahnung ohne Flankenkorrekturen ist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr

EINGRIFFSWINKEL = (20.0, 14.5, 15.0, 17.5, 22.5, 25.0, 30.0)
NORMMODULE = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.125, 1.25, 1.375, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 4.5,
              5.0, 5.5, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 28.0, 32.0, 36.0,
              40.0, 45.0, 50.0)
ABTASTUNG = 8192  # Winkelschritte je Umlauf fuer r(theta)
MIN_AMPLITUDE = 0.02  # verzahnt: Amplitude der Zahnharmonischen mindestens 2 % des mittleren Radius
MIN_PERIODISCH = 0.9  # verzahnt: Anteil der Schwankung von r(theta) in Vielfachen der Zahnharmonischen
MIN_ZAEHNE = 5
ZAHNHOEHE = (1.5, 3.0)  # Zahnhoehe in Vielfachen von mn (Bezugsprofil ISO 53: 2,25)
MAX_FIT = 0.03  # Evolventen-Fit: mittlere Abweichung hoechstens 3 % der Zahnhoehe, sonst keine Evolventenverzahnung


@dataclass
class Verzahnung:
    teil: str
    punkt: np.ndarray  # Achse
    richtung: np.ndarray
    innen: bool
    z: int
    da: float
    df: float
    b: float
    beta: float = 0.0  # Grad
    hand: str = ""  # rechts | links | "" (gerade)
    db: float = 0.0
    mn: float = 0.0
    alpha_n: float = 0.0
    x: float = 0.0
    d: float = 0.0
    k: int = 0
    wk: float = 0.0
    fit_fehler: float = 0.0  # mittlere Abweichung des Evolventen-Fits (mm, in Umfangsrichtung)
    hinweise: list[str] = field(default_factory=list)

    def zeilen(self) -> list[tuple[str, str, str]]:
        """(Groesse, Wert, Herkunft) fuer Tabelle und Export."""
        g = lambda w, n=4: f"{w:.{n}f}".rstrip("0").rstrip(".")  # noqa: E731
        hand = {"rechts": tr("rechtssteigend"), "links": tr("linkssteigend")}.get(self.hand, tr("gerade"))
        return [(tr("Art"), tr("Innenverzahnung") if self.innen else tr("Außenverzahnung"), tr("Schnittkontur")),
                (tr("Zähnezahl z"), str(self.z), tr("Harmonische von r(θ)")),
                (tr("Kopfkreis da"), g(self.da, 3), tr("gemessen")),
                (tr("Fußkreis df"), g(self.df, 3), tr("gemessen")),
                (tr("Zahnbreite b"), g(self.b, 3), tr("gemessen")),
                (tr("Schrägungswinkel β"), f"{g(self.beta, 3)}° {hand}", tr("Drehung entlang der Achse")),
                (tr("Grundkreis db"), g(self.db, 3), tr("Evolventen-Fit")),
                (tr("Normalmodul mn"), g(self.mn), tr("aus db, β und Normmodul")),
                (tr("Eingriffswinkel αn"), f"{g(self.alpha_n, 2)}°", tr("aus db, β und Normmodul")),
                (tr("Teilkreis d"), g(self.d, 3), "z · mn / cos β"),
                (tr("Profilverschiebung x"), g(self.x, 3), tr("Zahndicke am Teilkreis")),
                (tr("Zahnweite Wk"), f"W{self.k} = {g(self.wk, 3)}" if self.k else "–", tr("berechnet"))]

    def als_dict(self) -> dict:
        return {"teil": self.teil, "innen": self.innen, "z": self.z, "da": self.da, "df": self.df, "b": self.b,
                "beta": self.beta, "hand": self.hand, "db": self.db, "mn": self.mn, "alpha_n": self.alpha_n,
                "d": self.d, "x": self.x, "k": self.k, "wk": self.wk, "fit_fehler": self.fit_fehler,
                "achse": {"punkt": [float(v) for v in self.punkt], "richtung": [float(v) for v in self.richtung]},
                "hinweise": list(self.hinweise)}


def _inv(a):
    return np.tan(a) - a


def _achse(form):
    """(Punkt, Richtung) der Drehachse: Hauptachse mit dem abweichenden Traegheitsmoment, Zylinderachse bevorzugt."""
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from . import toleranzzone as tz
    g = GProp_GProps()
    brepgprop.VolumeProperties(form, g)
    if g.Mass() <= 1e-9:
        brepgprop.SurfaceProperties(form, g)
    c = g.CentreOfMass()
    m = g.MatrixOfInertia()
    j = np.array([[m.Value(i, k) for k in (1, 2, 3)] for i in (1, 2, 3)])
    w, v = np.linalg.eigh(j)
    abw = [abs(w[i] - np.mean(np.delete(w, i))) for i in range(3)]
    richtung = v[:, int(np.argmax(abw))]
    punkt = np.array([c.X(), c.Y(), c.Z()])
    flaechen, ex = [], TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        flaechen.append(ex.Current())
        ex.Next()
    try:
        achsen = tz._achsen(flaechen)
    except Exception:  # noqa: BLE001 - reine Netze haben keine Flaechengeometrie
        achsen = []
    for start, d, _laenge, _r, _f in sorted(achsen, key=lambda a: -a[2]):
        q = punkt - start
        if abs(d @ richtung) > 0.999 and np.linalg.norm(q - d * (q @ d)) < 1e-3 * max(1.0, np.linalg.norm(q)):
            return start + d * ((punkt - start) @ d), d / np.linalg.norm(d)
    return punkt, richtung / np.linalg.norm(richtung)


def _basis(n):
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, a)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


class _Schnitte:
    """Feines Dreiecksnetz der Form (einmal) fuer schnelle Stirnschnitte; Konturen als Punktwolken je
    zusammenhaengendem Linienzug, 2D relativ zur Achse."""

    def __init__(self, form, punkt, n):
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopLoc import TopLoc_Location
        from OCC.Core.TopoDS import topods
        box = Bnd_Box()
        brepbndlib.Add(form, box)
        x0, y0, z0, x1, y1, z1 = box.Get()
        groesse = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) or 1.0
        BRepMesh_IncrementalMesh(form, groesse * 5e-5, False, 0.05, True)
        a, b, c = [], [], []
        ex = TopExp_Explorer(form, TopAbs_FACE)
        while ex.More():
            f = topods.Face(ex.Current())
            ex.Next()
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation(f, loc)
            if tri is None:
                continue
            t = loc.Transformation()
            p = np.array([(lambda q: (q.X(), q.Y(), q.Z()))(tri.Node(i).Transformed(t))
                          for i in range(1, tri.NbNodes() + 1)])
            ix = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1
            a.append(p[ix[:, 0]]); b.append(p[ix[:, 1]]); c.append(p[ix[:, 2]])
        u, v = _basis(n)
        m = np.column_stack([u, v, n])
        self.a, self.b, self.c = ((np.vstack(x) - punkt) @ m for x in (a, b, c))  # Achse = z
        self.r_max = float(np.hypot(*np.vstack([self.a, self.b, self.c])[:, :2].T).max())

    def konturen(self, s: float) -> list[np.ndarray]:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        da, db, dc = self.a[:, 2] - s, self.b[:, 2] - s, self.c[:, 2] - s
        sel = (np.minimum(np.minimum(da, db), dc) < 0) & (np.maximum(np.maximum(da, db), dc) > 0)
        if not sel.any():
            return []
        ecken = [(self.a[sel], da[sel]), (self.b[sel], db[sel]), (self.c[sel], dc[sel])]
        punkte = []
        for (p, dp), (q, dq) in ((ecken[0], ecken[1]), (ecken[1], ecken[2]), (ecken[2], ecken[0])):
            kreuzt = (dp < 0) != (dq < 0)
            t = np.where(kreuzt, dp / np.where(kreuzt, dp - dq, 1.0), np.nan)
            punkte.append(np.where(kreuzt[:, None], p + (q - p) * t[:, None], np.nan)[:, :2])
        punkte = np.stack(punkte, axis=1)  # Dreieck x Kante x 2 (nan: Kante nicht geschnitten)
        gut = ~np.isnan(punkte[..., 0])
        stuecke = np.array([pp[g][:2] for pp, g in zip(punkte, gut) if g.sum() >= 2])
        if not len(stuecke):
            return []
        # Linienstuecke ueber gemeinsame Endpunkte zu Konturen gruppieren
        eps = self.r_max * 1e-7
        schluessel = np.round(stuecke.reshape(-1, 2) / eps).astype(np.int64)
        _, idx = np.unique(schluessel, axis=0, return_inverse=True)
        idx = idx.reshape(-1, 2)
        n = int(idx.max()) + 1
        graph = coo_matrix((np.ones(len(idx)), (idx[:, 0], idx[:, 1])), shape=(n, n))
        _, gruppe = connected_components(graph, directed=False)
        out = []
        schritt = 2 * np.pi * self.r_max / (4 * ABTASTUNG)
        for g in np.unique(gruppe[idx[:, 0]]):
            teil = stuecke[gruppe[idx[:, 0]] == g]
            if len(teil) < 8:
                continue
            laenge = np.linalg.norm(teil[:, 1] - teil[:, 0], axis=1)
            k = np.maximum(1, np.ceil(laenge / schritt)).astype(int)
            t = np.concatenate([np.arange(kk) / kk for kk in k])
            j = np.repeat(np.arange(len(teil)), k)
            out.append(teil[j, 0] + (teil[j, 1] - teil[j, 0]) * t[:, None])
        return out


def _r_theta(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """r(theta) einer Kontur (Punktwolke) auf einem gleichmaessigen Winkelraster."""
    th = np.arctan2(q[:, 1], q[:, 0])
    r = np.hypot(q[:, 0], q[:, 1])
    raster = np.linspace(-np.pi, np.pi, ABTASTUNG, endpoint=False)
    reihenfolge = np.argsort(th)
    return raster, np.interp(raster, th[reihenfolge], r[reihenfolge], period=2 * np.pi)


def _zahn_harmonische(r: np.ndarray) -> tuple[int, complex, float]:
    """(z, komplexe Amplitude der z-ten Harmonischen, relative Amplitude); relative Amplitude 0, wenn r(theta)
    nicht mit 2 pi / z periodisch ist (z. B. Rechteck, Langloch)."""
    f = np.fft.rfft(r - r.mean()) / len(r)
    leistung = np.abs(f[1:len(f) // 4]) ** 2
    k = int(np.argmax(leistung)) + 1
    vielfache = leistung[k - 1::k].sum() / max(leistung.sum(), 1e-300)
    if k < MIN_ZAEHNE or vielfache < MIN_PERIODISCH:
        return k, complex(f[k]), 0.0
    return k, complex(f[k]), float(2 * abs(f[k]) / r.mean())


def _verzahnt(schnitte: _Schnitte, s: float):
    """(Kontur, r(theta), z, Harmonische, innen) der verzahnten Kontur bei s oder None."""
    konturen = schnitte.konturen(s)
    beste = None
    for q in konturen:
        _, r = _r_theta(q)
        z, h, rel = _zahn_harmonische(r)
        if rel >= MIN_AMPLITUDE and (beste is None or rel > beste[4]):
            beste = (q, r, z, h, rel)
    if beste is None:
        return None
    q, r, z, h, _ = beste
    # innen: eine andere Kontur liegt weiter aussen (Hohlrad) -> die verzahnte ist eine Bohrung
    innen = any(np.hypot(*k.T).max() > np.hypot(*q.T).max() * 1.01 for k in konturen if k is not q)
    return q, r, z, h, innen


def _evolventen_fit(r: np.ndarray, z: int, r_lo: float, r_hi: float) -> tuple[float, float]:
    """(Grundkreisradius, mittlere Abweichung in mm) aus r(theta) zwischen r_lo und r_hi, je Flankenseite."""
    th = np.linspace(-np.pi, np.pi, len(r), endpoint=False)
    dr = np.gradient(r)
    teil = 2 * np.pi / z
    ergebnisse = []
    for seite in (1, -1):
        sel = (r > r_lo) & (r < r_hi) & (np.sign(dr) == seite)
        if sel.sum() < 10:
            continue
        rr, tt = r[sel], th[sel]

        def streuung(rb):
            nutz = rr > rb * 1.0005  # unterhalb des Grundkreises gibt es keine Evolvente
            if nutz.sum() < 10:
                return float("inf")
            a = np.arccos(rb / rr[nutz])
            rest = np.mod(tt[nutz] - seite * _inv(a), teil)
            mittel = np.angle(np.exp(1j * rest * z).mean()) / z  # Kreismittel ueber die Teilung
            abw = np.mod(rest - mittel + teil / 2, teil) - teil / 2
            return float(np.sqrt(np.mean(abw ** 2))) * float(np.mean(rr[nutz]))
        gitter = np.linspace(0.3 * r_hi, 0.9999 * r_hi, 200)
        werte = [streuung(x) for x in gitter]
        i = int(np.argmin(werte))
        lo, hi = gitter[max(i - 1, 0)], gitter[min(i + 1, len(gitter) - 1)]
        for _ in range(40):  # Goldener Schnitt
            a, b = lo + 0.382 * (hi - lo), lo + 0.618 * (hi - lo)
            if streuung(a) < streuung(b):
                hi = b
            else:
                lo = a
        rb = (lo + hi) / 2
        ergebnisse.append((rb, streuung(rb)))
    if not ergebnisse:
        return 0.0, float("inf")
    return float(np.mean([e[0] for e in ergebnisse])), float(np.mean([e[1] for e in ergebnisse]))


def _breite(schnitte: _Schnitte, s0, s1, schritte: int = 12):
    """Achsbereich der verzahnten Schnitte [a, b] (Grenzen durch Halbieren) und die Schnitte dazwischen."""
    werte = np.linspace(s0, s1, schritte + 2)[1:-1]
    treffer = [(s, _verzahnt(schnitte, s)) for s in werte]
    an = [s for s, t in treffer if t is not None]
    if not an:
        return None
    grenzen = []
    for innen_s, aussen_s in ((min(an), s0), (max(an), s1)):
        for _ in range(10):
            mitte = (innen_s + aussen_s) / 2
            if _verzahnt(schnitte, mitte) is not None:
                innen_s = mitte
            else:
                aussen_s = mitte
        grenzen.append((innen_s + aussen_s) / 2)
    return grenzen[0], grenzen[1], [(s, t) for s, t in treffer if t is not None]


def _ableiten(v: Verzahnung, rb: float, q: np.ndarray, r_raster: np.ndarray):
    """mn, alpha_n, d, x und Wk aus db, beta und z (Normmodul nach ISO 54 bevorzugt)."""
    cb = math.cos(math.radians(v.beta))
    kandidaten = []
    for an in EINGRIFFSWINKEL:
        at = math.atan(math.tan(math.radians(an)) / cb)
        d = 2 * rb / math.cos(at)
        mn = d * cb / v.z
        norm = min(NORMMODULE, key=lambda m: abs(m - mn) / m)
        kandidaten.append((abs(norm - mn) / norm, an, mn, d, at, norm))
    kandidaten.sort()
    fehler, an, mn, d, at, norm = kandidaten[0]
    if len(kandidaten) > 1 and kandidaten[1][0] < 0.003:
        v.hinweise.append(tr("Mehrdeutig: auch αn = {:g}° mit mn = {:.4g} passt").format(kandidaten[1][1],
                                                                                         kandidaten[1][2]))
    if fehler > 0.01:
        v.hinweise.append(tr("Kein Normmodul in der Nähe (nächstes {:g}) – αn unsicher").format(norm))
    v.alpha_n, v.mn, v.d = an, mn, d
    # Zahndicke (innen: Lueckenweite) am Teilkreis aus r(theta)
    material = r_raster > d / 2 if not v.innen else r_raster < d / 2
    anteil = float(material.mean())  # Anteil des Umfangs mit Zahn am Teilkreis
    mt = mn / cb
    s_t = anteil * math.pi * d / v.z
    v.x = (s_t / mt - math.pi / 2) / (2 * math.tan(at)) * (-1 if v.innen else 1)
    if not v.innen:
        k = max(2, int(round(v.z * at / math.pi + 0.5)))
        v.k = k
        v.wk = mn * math.cos(math.radians(an)) * ((k - 0.5) * math.pi + v.z * float(_inv(at))) + \
            2 * v.x * mn * math.sin(math.radians(an))


def erkenne(form, teil: str = "") -> Verzahnung | None:
    """Verzahnung eines Teils oder None (keine verzahnte Kontur gefunden)."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    punkt, n = _achse(form)
    box = Bnd_Box()
    brepbndlib.Add(form, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    ecken = np.array([[x, y, zz] for x in (x0, x1) for y in (y0, y1) for zz in (z0, z1)])
    s = (ecken - punkt) @ n
    schnitte_netz = _Schnitte(form, punkt, n)
    breite = _breite(schnitte_netz, float(s.min()), float(s.max()))
    if breite is None:
        return None
    a, b, schnitte = breite
    mitte_s = (a + b) / 2
    mitte = _verzahnt(schnitte_netz, mitte_s) or schnitte[len(schnitte) // 2][1]
    q, r, z, _h, innen = mitte
    radien = np.hypot(q[:, 0], q[:, 1])
    rmin, rmax = float(radien.min()), float(radien.max())
    da, df = (2 * rmin, 2 * rmax) if innen else (2 * rmax, 2 * rmin)
    v = Verzahnung(teil, punkt, n, innen, z, da, df, b - a)
    # Schraegung: Phase der Zahnharmonischen entlang der Achse
    if len(schnitte) >= 2:
        ss = np.array([x for x, _ in schnitte])
        phase = np.unwrap(np.array([np.angle(t[3]) for _, t in schnitte]))
        steigung = float(np.polyfit(ss, phase, 1)[0])  # rad Phase je mm; Drehung = -Phase / z
        dreh = -steigung / z
    else:
        dreh = 0.0
    h = rmax - rmin
    rb, fit = _evolventen_fit(r, z, rmin + 0.15 * h, rmax - 0.15 * h)
    v.db, v.fit_fehler = 2 * rb, fit
    beta = 0.0
    for _ in range(3):  # beta am Teilkreis haengt von d ab, d von beta
        d = 2 * rb / math.cos(math.atan(math.tan(math.radians(20.0)) / math.cos(beta))) if rb else (rmin + rmax)
        beta = math.atan(abs(dreh) * d / 2)
    v.beta = math.degrees(beta)
    if v.beta < 0.05:
        v.beta, v.hand = 0.0, ""
    else:
        v.hand = "rechts" if dreh > 0 else "links"
    if rb > 0:
        _ableiten(v, rb, q, r)
        # beta mit dem endgueltigen Teilkreis
        v.beta = math.degrees(math.atan(abs(dreh) * v.d / 2)) if v.hand else 0.0
        if v.hand:
            _ableiten(v, rb, q, r)
    if not rb or fit > MAX_FIT * h:
        return None  # periodisch, aber keine Evolventenflanken (Sechskant, Keilwelle mit geraden Flanken ...)
    if not ZAHNHOEHE[0] <= h / v.mn <= ZAHNHOEHE[1] or abs(v.x) > 1.5:
        return None  # Zahnhoehe passt nicht zum Modul (z. B. Vielkant, Rändel)
    if fit > 0.01 * h:
        v.hinweise.append(tr("Flanken weichen von der Evolvente ab ({:.3f} mm)").format(fit))
    return v


@dataclass
class Paar:
    """Radpaar mit parallelen Achsen (aussen-aussen oder Ritzel im Hohlrad)."""
    a: Verzahnung
    b: Verzahnung
    abstand: float  # gemessener Achsabstand
    abstand_soll: float  # spielfrei aus den Profilverschiebungen (ISO 21771)
    alpha_wt: float  # Betriebseingriffswinkel (Grad) beim gemessenen Achsabstand
    eps_alpha: float  # Profilueberdeckung
    eps_beta: float  # Sprungueberdeckung
    spiel: float  # Normalflankenspiel aus dem Achsabstandsunterschied (mm), < 0: Ueberdeckung der Zaehne
    hinweise: list[str] = field(default_factory=list)

    def zeilen(self) -> list[tuple[str, str]]:
        g = lambda w, n=4: f"{w:.{n}f}".rstrip("0").rstrip(".")  # noqa: E731
        return [(tr("Achsabstand a"), g(self.abstand, 3)), (tr("Achsabstand spielfrei"), g(self.abstand_soll, 3)),
                (tr("Betriebseingriffswinkel αwt"), f"{g(self.alpha_wt, 3)}°"),
                (tr("Profilüberdeckung εα"), g(self.eps_alpha, 3)), (tr("Sprungüberdeckung εβ"), g(self.eps_beta, 3)),
                (tr("Normalflankenspiel aus a"), g(self.spiel, 4))]


def _paar(a: Verzahnung, b: Verzahnung) -> Paar | None:
    """Paar, wenn die Achsen parallel sind, Modul, Eingriffswinkel und Schraegung passen und der Abstand nahe der
    Summe (aussen) bzw. Differenz (Hohlrad) der Teilkreisradien liegt."""
    if a.innen and b.innen or abs(a.richtung @ b.richtung) < 0.9999:
        return None
    if abs(a.mn - b.mn) > 0.01 * a.mn or abs(a.alpha_n - b.alpha_n) > 0.1 or abs(a.beta - b.beta) > 0.2:
        return None
    if b.innen:
        a, b = b, a  # a: Hohlrad
    q = b.punkt - a.punkt
    abstand = float(np.linalg.norm(q - a.richtung * (q @ a.richtung)))
    innen = a.innen
    z1, z2 = (b.z, -a.z) if innen else (a.z, b.z)  # Hohlrad mit negativer Zaehnezahl (ISO 21771)
    x1, x2 = (b.x, a.x) if innen else (a.x, b.x)
    soll0 = abs(a.d - b.d) / 2 if innen else (a.d + b.d) / 2
    if abs(abstand - soll0) > 0.2 * soll0:
        return None
    if innen and abstand < 1e-6:
        return None
    if a.beta and b.beta and not innen and a.hand == b.hand:
        hinweis = [tr("Gleiche Steigungsrichtung bei Außenradpaar – kämmt nicht (gegenläufig nötig)")]
    else:
        hinweis = []
    cb = math.cos(math.radians(a.beta))
    at = math.atan(math.tan(math.radians(a.alpha_n)) / cb)
    inv_wt = float(_inv(at)) + 2 * math.tan(math.radians(a.alpha_n)) * (x1 + x2) / (z1 + z2)
    lo, hi = 1e-6, 1.4  # inv ist monoton: alpha_wt durch Halbieren
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if float(_inv(m)) < inv_wt else (lo, m)
    awt_soll = (lo + hi) / 2
    a_soll = soll0 * math.cos(at) / math.cos(awt_soll)
    awt = math.acos(min(1.0, soll0 * math.cos(at) / abstand))
    mt = a.mn / cb
    ra = {id(v): (v.da / 2) for v in (a, b)}
    rb = {id(v): (v.db / 2) for v in (a, b)}
    strecke = lambda v: math.sqrt(max(ra[id(v)] ** 2 - rb[id(v)] ** 2, 0.0))  # noqa: E731
    if innen:  # Hohlrad: Kopfkreis innen, die Eingriffsstrecke zaehlt negativ
        g = strecke(b) - strecke(a) + abstand * math.sin(awt)
    else:
        g = strecke(a) + strecke(b) - abstand * math.sin(awt)
    eps_a = g / (math.pi * mt * math.cos(at))
    breite = min(a.b, b.b)
    eps_b = breite * math.sin(math.radians(a.beta)) / (math.pi * a.mn)
    spiel = 2 * (abstand - a_soll) * math.sin(math.radians(a.alpha_n))
    if eps_a < 1.0:
        hinweis.append(tr("Profilüberdeckung unter 1 – kein stetiger Eingriff"))
    return Paar(a, b, abstand, a_soll, math.degrees(awt), eps_a, eps_b, spiel, hinweis)


def paare(liste: list[Verzahnung]) -> list[Paar]:
    """Alle kaemmenden Radpaare einer Liste (Achsen parallel, Abstand passend)."""
    out = []
    for i, a in enumerate(liste):
        for b in liste[i + 1:]:
            p = _paar(a, b)
            if p is not None:
                out.append(p)
    return out


def als_csv(liste: list[Verzahnung]) -> str:
    import csv
    import io
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr("Größe")] + [v.teil for v in liste] + [tr("Herkunft")])
    zeilen = [v.zeilen() for v in liste]
    for i, (name, _wert, herkunft) in enumerate(zeilen[0] if zeilen else []):
        w.writerow([name] + [z[i][1] for z in zeilen] + [herkunft])
    return puffer.getvalue()
