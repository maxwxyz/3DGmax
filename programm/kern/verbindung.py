"""Verbindungen zwischen Teilen einer Baugruppe: Fangen und offene Freiheitsgrade (ohne Qt), PLAN §8.20 Stufe 1.

Eine Verbindung bindet eine Flaeche eines beweglichen Teils an eine Flaeche eines anderen Teils:
- eben: Ebene auf Ebene, Normalen gegeneinander, Abstand = Versatz (0: Beruehrung);
- koaxial: Zylinder- oder Kegelachse auf Achse;
- Langloch: Bolzen (Zylinderachse) im Abstand des Radius parallel zu einer Ebene (Linienkontakt, Bolzen in Langloch
  mit einer Flanke gewaehlt);
- Punkt: Kugelmitte im Abstand des Radius ueber einer Ebene (Kugel auf Ebene);
- Kugel: Kugelmitte auf Kugelmitte (Kugel in Kugelpfanne).
Fangen bewegt das Teil so, dass die Verbindung erfuellt ist. Die Freiheitsgrade eines Teils folgen aus den kleinen
Bewegungen (Drehung w, Verschiebung v am Ursprung; ein Punkt p bewegt sich um v + w x p), die alle seine Verbindungen
zulassen: eben verbietet die Verschiebung entlang der Normalen und das Kippen um die zwei Achsen in der Ebene
(3 Bedingungen), koaxial die Querbewegung zweier Achspunkte (4 Bedingungen). Offene Freiheitsgrade = Nullraum,
die Gegenteile gelten dabei als fest.

Toleranzen (Stufe 2, lineares Modell): jede gesperrte Bewegung erhaelt einen Spielraum. Eben: Verschiebung entlang
der Normalen +-h (halbe Summe der Lage-/Profiltoleranzen beider Flaechen), Kippen +-k = Summe aller Flaechentoleranzen
/ Flaechengroesse. Koaxial: radiales Spiel c (Durchmesser aus Geometrie und Masstoleranzen, dazu Positionstoleranzen)
an den zwei Enden der gemeinsamen Laenge - daraus folgt auch das Kippspiel. Die Lagestreuung eines Punkts in einer
Richtung ist im linearen Modell c . A+ y mit y im Quader der Spielraeume; ihr Groesstwert ist die Summe der
Betraege (Worst Case). Freie Freiheitsgrade bleiben dabei aussen vor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..i18n import tr

EBEN, KOAXIAL, LANGLOCH, PUNKT, KUGEL = "eben", "koaxial", "langloch", "punkt", "kugel"
ART_TEXT = {EBEN: "Ebene auf Ebene", KOAXIAL: "koaxial", LANGLOCH: "Bolzen in Langloch (Linie auf Ebene)",
            PUNKT: "Kugel auf Ebene (Punkt)", KUGEL: "Kugel in Kugel"}
MIT_VERSATZ = (EBEN, LANGLOCH, PUNKT)  # Versatz = Abstand zur Ebene (bei Bolzen/Kugel zusaetzlich zum Radius)
ARTEN = {("ebene", "ebene"): EBEN, ("achse", "achse"): KOAXIAL, ("achse", "ebene"): LANGLOCH,
         ("ebene", "achse"): LANGLOCH, ("kugel", "ebene"): PUNKT, ("ebene", "kugel"): PUNKT, ("kugel", "kugel"): KUGEL}


@dataclass
class Verbindung:
    nummer: int
    teil: int  # Knotennummer des bewegten Teils
    flaeche: int  # Flaechenindex am bewegten Teil
    gegen_teil: int
    gegen_flaeche: int
    art: str
    versatz: float = 0.0  # mm, Abstand zur Ebene (eben, Langloch, Punkt)
    toleranz: float = 0.0  # eben/Langloch/Punkt: +-h entlang der Normalen; koaxial/Kugel: radiales Spiel c (mm)
    kippen: float = 0.0  # eben: +-k (rad) Kippen der Flaeche
    quelle: str = ""  # Herkunft der Toleranz (Text)
    eingriff: tuple = ()  # koaxial/Langloch: Eingriffsenden entlang der Achse (ab dem Achspunkt, siehe _eingriff)


def _kugel(flaeche):
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Sphere
    if BRep_Tool.Surface(flaeche) is None:
        return None
    s = BRepAdaptor_Surface(flaeche, True)
    if s.GetType() != GeomAbs_Sphere:
        return None
    c = s.Sphere().Location()
    return np.array([c.X(), c.Y(), c.Z()]), s.Sphere().Radius()


def radius(flaeche) -> float:
    """Radius einer Zylinder- oder Kugelflaeche (sonst 0)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    k = _kugel(flaeche)
    if k is not None:
        return k[1]
    s = BRepAdaptor_Surface(flaeche, True)
    return s.Cylinder().Radius() if s.GetType() == GeomAbs_Cylinder else 0.0


def merkmal(flaeche, lage: np.ndarray | None = None):
    """('ebene', Punkt, Normale aus dem Material), ('achse', Punkt, Richtung) oder ('kugel', Mitte, (0, 0, 1)) in
    Weltlage, sonst None."""
    from .toleranzkette import _aussen_normale, _ebene_oder_achse
    g = _ebene_oder_achse(flaeche)
    if g is None:
        k = _kugel(flaeche)
        if k is None:
            return None
        g = ("kugel", k[0], np.array([0.0, 0.0, 1.0]))
    art, p, d = g
    if art == "ebene":
        d = _aussen_normale(flaeche)
    if lage is not None:
        p = lage[:3, :3] @ p + lage[:3, 3]
        d = lage[:3, :3] @ d
    return art, p, d / np.linalg.norm(d)


def art_fuer(a, b) -> str | None:
    if a is None or b is None:
        return None
    return ARTEN.get((a[0], b[0]))


def _drehung(von: np.ndarray, nach: np.ndarray) -> np.ndarray:
    """Kleinste Drehung, die die Richtung von auf nach dreht (3x3)."""
    von, nach = von / np.linalg.norm(von), nach / np.linalg.norm(nach)
    c = float(von @ nach)
    if c > 1 - 1e-12:
        return np.eye(3)
    if c < -1 + 1e-12:  # Gegenrichtung: 180 Grad um eine Senkrechte
        s = _senkrechte(von)[0]
        return 2 * np.outer(s, s) - np.eye(3)
    k = np.cross(von, nach)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + kx + kx @ kx / (1 + c)


def _senkrechte(n: np.ndarray):
    a = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    t1 = np.cross(n, a)
    t1 /= np.linalg.norm(t1)
    return t1, np.cross(n, t1)


def fangen(m_teil, m_gegen, art: str, versatz: float = 0.0) -> np.ndarray:
    """Bewegung (4x4, Welt) des Teils, die seine Flaeche auf die Gegenflaeche bringt (Merkmale in Weltlage)."""
    a, p, d = m_teil
    b, q, e = m_gegen
    if art in (PUNKT, KUGEL, LANGLOCH):
        return _fangen_kontakt(a, p, d, b, q, e, art, versatz)
    if art == EBEN:
        r = _drehung(d, -e)  # Normalen gegeneinander
    else:
        r = _drehung(d, e if d @ e >= 0 else -e)  # Achse auf Achse, kleinere Drehung
    p2 = r @ p
    if art == EBEN:
        t = e * (float((q - p2) @ e) + versatz)  # nur entlang der Normalen: Lage in der Ebene bleibt
    else:
        quer = (q - p2) - e * float((q - p2) @ e)  # nur quer zur Achse: Lage entlang der Achse bleibt
        t = quer
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = t
    return m


def _parallel(d: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Richtung d in die Ebene mit der Normalen n gedreht (kleinste Drehung)."""
    x = d - n * float(d @ n)
    return x / np.linalg.norm(x) if np.linalg.norm(x) > 1e-9 else _senkrechte(n)[0]


def _fangen_kontakt(a, p, d, b, q, e, art: str, versatz: float) -> np.ndarray:
    """Fangen fuer Langloch, Punkt und Kugel (a/b: Merkmalsart des Teils bzw. der Gegenflaeche)."""
    m = np.eye(4)
    if art == KUGEL:
        m[:3, 3] = q - p
        return m
    if art == LANGLOCH:  # Achse parallel zur Ebene bzw. Ebenennormale senkrecht zur Achse drehen
        r = _drehung(d, _parallel(d, e))
        m[:3, :3] = r
        p, d = r @ p, r @ d
    if b == "ebene":  # Teil traegt Bolzen/Kugel, Mitte in den Abstand versatz ueber die Gegenebene
        m[:3, 3] = e * (float((q - p) @ e) + versatz)
    else:  # Teil traegt die Ebene: Ebene so, dass die Gegenmitte im Abstand versatz darueber liegt
        n = d / np.linalg.norm(d)
        m[:3, 3] = n * (float((q - p) @ n) - versatz)
    return m


def _kontakt(art: str, m_teil, m_gegen):
    """(Achse/Mitte, Richtung, Ebenennormale, Ebenenpunkt) fuer Langloch und Punkt, gleich welche Seite die Ebene
    traegt."""
    eb, ax = (m_gegen, m_teil) if m_gegen[0] == "ebene" else (m_teil, m_gegen)
    return ax[1], ax[2], eb[2], eb[1], eb is m_teil


def bedingungen(art: str, m_gegen, m_teil=None) -> list[np.ndarray]:
    """Zeilen (w, v) der gesperrten kleinen Bewegungen fuer ein Teil an dieser Verbindung."""
    _, q, e = m_gegen
    t1, t2 = _senkrechte(e)
    if art == EBEN:
        return [np.r_[np.cross(q, e), e], np.r_[np.cross(t1, e), 0, 0, 0], np.r_[np.cross(t2, e), 0, 0, 0]]
    if art == KUGEL:
        return [np.r_[np.cross(q, u), u] for u in np.eye(3)]
    if art in (LANGLOCH, PUNKT):
        c, d, n, _, _ = _kontakt(art, m_teil, m_gegen)
        punkte = (c, c + d) if art == LANGLOCH else (c,)
        return [np.r_[np.cross(p, n), n] for p in punkte]
    return [np.r_[np.cross(p, u), u] for p in (q, q + e) for u in (t1, t2)]


def freiheitsgrade(zeilen: list[np.ndarray]) -> np.ndarray:
    """Basis der offenen Bewegungen (k x 6, je Zeile w, v)."""
    if not zeilen:
        return np.eye(6)
    _, s, vt = np.linalg.svd(np.array(zeilen))
    rang = int((s > 1e-9 * max(1.0, float(s.max()))).sum())
    return vt[rang:]


def _gerade_ausrichten(w: np.ndarray, v: np.ndarray):
    """Offene Bewegung lesbar machen: reine Verschiebung oder Drehung um eine Achse (Richtung, Punkt)."""
    if np.linalg.norm(w) < 1e-9:
        return "verschiebung", v / np.linalg.norm(v), None
    a = w / np.linalg.norm(w)
    punkt = np.cross(w, v) / float(w @ w)  # Punkt der Drehachse (v = -w x p)
    return "drehung", a, punkt


def beschreibe(basis: np.ndarray) -> list[str]:
    """Kurztexte der offenen Freiheitsgrade, z. B. 'Drehung um (0, 0, 1)'."""
    out = []
    for z in basis:
        art, richtung, _ = _gerade_ausrichten(z[:3], z[3:])
        r = ", ".join(f"{x:.2g}" for x in np.round(richtung, 3) + 0.0)
        out.append((tr("Verschiebung entlang ({})") if art == "verschiebung" else tr("Drehung um ({})")).format(r))
    return out


def bewegung(z: np.ndarray, betrag: float, um: np.ndarray | None = None) -> np.ndarray:
    """4x4 der Bewegung entlang eines Freiheitsgrads: Verschiebung in mm bzw. Drehung in Grad um ihre Achse."""
    art, richtung, punkt = _gerade_ausrichten(z[:3], z[3:])
    m = np.eye(4)
    if art == "verschiebung":
        m[:3, 3] = richtung * betrag
        return m
    phi = np.radians(betrag)
    k = np.array([[0, -richtung[2], richtung[1]], [richtung[2], 0, -richtung[0]], [-richtung[1], richtung[0], 0]])
    r = np.eye(3) + np.sin(phi) * k + (1 - np.cos(phi)) * k @ k
    m[:3, :3] = r
    m[:3, 3] = punkt - r @ punkt
    return m


def _bereich_entlang(flaeche, lage, punkt, richtung) -> tuple[float, float]:
    """Ausdehnung einer Flaeche entlang einer Richtung (Ecken des Huellquaders, Weltlage)."""
    import itertools
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(flaeche, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    ecken = np.array(list(itertools.product((x0, x1), (y0, y1), (z0, z1))))
    if lage is not None:
        ecken = ecken @ lage[:3, :3].T + lage[:3, 3]
    s = (ecken - punkt) @ richtung
    return float(s.min()), float(s.max())


def _groesse(flaeche) -> float:
    """Typische Laenge einer Flaeche (Diagonale des Huellquaders) fuer das Kippspiel."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(flaeche, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    return float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) or 1.0


def bewegung_klein(x: np.ndarray, s: float = 1.0, mitte=None) -> np.ndarray:
    """4x4 einer kleinen Bewegung (w, v) mal s um den Punkt mitte: Drehung um w (Rodrigues), Verschiebung v."""
    w, v = np.asarray(x[:3], float) * s, np.asarray(x[3:], float) * s
    phi = float(np.linalg.norm(w))
    m = np.eye(4)
    if phi > 1e-15:
        a = w / phi
        k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
        m[:3, :3] = np.eye(3) + np.sin(phi) * k + (1 - np.cos(phi)) * k @ k
    c = np.zeros(3) if mitte is None else np.asarray(mitte, float)
    m[:3, 3] = v + c - m[:3, :3] @ c
    return m


def erfuellt(art: str, m_teil, m_gegen, versatz: float = 0.0, tol: float = 1e-4) -> bool:
    """Verbindung in der aktuellen Lage erfuellt (Richtungen und Abstand)?"""
    _, p, d = m_teil
    _, q, e = m_gegen
    if art == EBEN:
        return float(d @ e) < -1 + 1e-6 and abs(float((p - q) @ e) - versatz) < tol
    if art == KUGEL:
        return float(np.linalg.norm(p - q)) < tol
    if art in (LANGLOCH, PUNKT):
        c, d, n, q, _ = _kontakt(art, m_teil, m_gegen)
        richtung = art == PUNKT or abs(float(d @ n)) < 1e-6
        return richtung and abs(float((c - q) @ n) - versatz) < tol
    quer = (p - q) - e * float((p - q) @ e)
    return abs(abs(float(d @ e)) - 1) < 1e-6 and float(np.linalg.norm(quer)) < tol


class Baugruppe:
    """Verbindungen und Lagen der Teile (Knotennummer -> 4x4 relativ zur Lage in der Datei)."""

    def __init__(self):
        self.verbindungen: list[Verbindung] = []
        self.lagen: dict[int, np.ndarray] = {}
        self.formen: dict[int, tuple] = {}  # Nummer der Verbindung -> (Flaeche am Teil, Gegenflaeche), Dateilage
        self.masse: list = []  # Messgroessen (kern.baugruppe_mass.Messgroesse)
        self.mass_formen: dict[int, tuple] = {}  # Nummer der Messgroesse -> (Flaeche A, Flaeche B), Dateilage

    def lage(self, teil: int) -> np.ndarray:
        return self.lagen.get(teil, np.eye(4))

    def merkmale(self, v: Verbindung):
        fa, fb = self.formen[v.nummer]
        return merkmal(fa, self.lage(v.teil)), merkmal(fb, self.lage(v.gegen_teil))

    def verbinde(self, teil: int, flaeche, index: int, gegen_teil: int, gegen_flaeche, gegen_index: int,
                 versatz: float = 0.0) -> Verbindung | str:
        """Teil an die Gegenflaeche fangen und die Verbindung merken; Fehlertext bei unpassender Auswahl."""
        if teil == gegen_teil:
            return tr("Die zwei Flächen müssen zu verschiedenen Teilen gehören")
        ma, mb = merkmal(flaeche, self.lage(teil)), merkmal(gegen_flaeche, self.lage(gegen_teil))
        art = art_fuer(ma, mb)
        if art is None:
            return tr("Verbinden geht für zwei Ebenen, zwei Zylinder-/Kegelflächen, Zylinder und Ebene, Kugel und "
                      "Ebene oder zwei Kugeln")
        if art in (LANGLOCH, PUNKT):  # Abstand der Achse/Mitte zur Ebene: Radius plus Versatz
            versatz += radius(flaeche if ma[0] != "ebene" else gegen_flaeche)
        self.lagen[teil] = fangen(ma, mb, art, versatz) @ self.lage(teil)
        v = Verbindung(max((x.nummer for x in self.verbindungen), default=0) + 1, teil, index, gegen_teil,
                       gegen_index, art, versatz if art in MIT_VERSATZ else 0.0)
        self.verbindungen.append(v)
        self.formen[v.nummer] = (flaeche, gegen_flaeche)
        self._eingriff(v)
        return v

    def _achse(self, v: Verbindung):
        """Achspunkt und Richtung, ab denen der Eingriff gemessen wird: koaxial die Gegenachse, Langloch der Bolzen."""
        ma, mb = self.merkmale(v)
        if v.art == LANGLOCH:
            ax = ma if ma[0] == "achse" else mb
            return ax[1], ax[2]
        return mb[1], mb[2]

    def _eingriff(self, v: Verbindung):
        """Koaxial/Langloch: gemeinsame Laenge beider Flaechen entlang der Achse (Enden ab dem Achspunkt)."""
        if v.art not in (KOAXIAL, LANGLOCH):
            return
        fa, fb = self.formen[v.nummer]
        q, e = self._achse(v)
        a0, a1 = _bereich_entlang(fa, self.lage(v.teil), q, e)
        b0, b1 = _bereich_entlang(fb, self.lage(v.gegen_teil), q, e)
        lo, hi = max(a0, b0), min(a1, b1)
        v.eingriff = (lo, hi) if hi > lo + 1e-9 else (b0, b1)

    def zeilen(self, v: Verbindung, mitte=None, achteck: bool = True) -> list[tuple[np.ndarray, float, float]]:
        """Gesperrte Relativbewegungen einer Verbindung (Zeile w, v um mitte; untere, obere Grenze).
        Radiales Spiel als Achteck (vier Richtungen, hoechstens 8 % groesser als der Kreis), ohne achteck nur die
        zwei Querrichtungen; Kugel: drei Achsrichtungen."""
        mitte = np.zeros(3) if mitte is None else np.asarray(mitte, float)
        ma, mb = self.merkmale(v)
        _, q, e = mb
        t1, t2 = _senkrechte(e)
        h = v.toleranz
        if v.art == EBEN:
            return [(np.r_[np.cross(q - mitte, e), e], -h, h)] + \
                [(np.r_[np.cross(t, e), 0, 0, 0], -v.kippen, v.kippen) for t in (t1, t2)]
        if v.art == KUGEL:
            return [(np.r_[np.cross(q - mitte, u), u], -h, h) for u in np.eye(3)]
        if v.art == PUNKT:
            c, _, n, _, _ = _kontakt(v.art, ma, mb)
            return [(np.r_[np.cross(c - mitte, n), n], -h, h)]
        if not v.eingriff:
            self._eingriff(v)
        qa, ea = self._achse(v)
        if v.art == LANGLOCH:
            _, _, n, _, _ = _kontakt(v.art, ma, mb)
            return [(np.r_[np.cross(qa + ea * s - mitte, n), n], -h, h) for s in v.eingriff]
        richtungen = (t1, t2, (t1 + t2) / np.sqrt(2), (t1 - t2) / np.sqrt(2)) if achteck else (t1, t2)
        return [(np.r_[np.cross(qa + ea * s - mitte, u), u], -h, h) for s in v.eingriff for u in richtungen]

    def mc_zeilen(self, v: Verbindung):
        """(Zeilen, Spielraeume, ziehen) fuer Monte Carlo: ziehen(rng, n) liefert n x k Werte der Zeilen (normalverteilt,
        Spielraum = 3 sigma, abgeschnitten; radiales Spiel als Punkt in der Kreisscheibe bzw. Kugel)."""
        zeilen = self.zeilen(v, achteck=False)
        grenzen = np.array([o for _, _, o in zeilen])
        gruppe = 2 if v.art == KOAXIAL else 3 if v.art == KUGEL else 1

        def ziehen(rng, n):
            y = rng.standard_normal((n, len(zeilen))) * grenzen / 3
            if gruppe == 1:
                return np.clip(y, -grenzen, grenzen)
            for k in range(0, len(zeilen), gruppe):  # radial: Betrag auf das Spiel begrenzen
                b = np.linalg.norm(y[:, k:k + gruppe], axis=1, keepdims=True)
                y[:, k:k + gruppe] *= np.minimum(1.0, grenzen[k] / np.maximum(b, 1e-300))
            return y
        return [z for z, _, _ in zeilen], grenzen, ziehen

    def spielraeume(self, teil: int, mitte=None) -> list[tuple[np.ndarray, float, float]]:
        """Gesperrte Bewegungen des Teils mit Spielraum gegen seine (festen) Partner (Zeile w, v um mitte)."""
        return [z for v in self.verbindungen if teil in (v.teil, v.gegen_teil) for z in self.zeilen(v, mitte)]

    def _lp(self, teil: int, mitte=None):
        """(Zeilen in reduzierten Koordinaten, untere, obere Grenze, Basis) der gesperrten Bewegungen oder None."""
        zeilen = self.spielraeume(teil, mitte)
        if not zeilen:
            return None
        a = np.array([z for z, _, _ in zeilen])
        _, sv, vt = np.linalg.svd(a)
        rang = int((sv > 1e-9 * max(1.0, float(sv.max()))).sum())
        basis = vt[:rang]  # nur gesperrte Richtungen; freie Freiheitsgrade bleiben aussen vor
        lo = np.array([u for _, u, _ in zeilen])
        hi = np.array([o for _, _, o in zeilen])
        return a @ basis.T, lo, hi, basis, 6 - rang

    @staticmethod
    def _extrem(ab, lo, hi, c) -> np.ndarray | None:
        """z mit groesstem c . z unter lo <= ab z <= hi (lineares Programm)."""
        from scipy.optimize import linprog
        r = linprog(-c, A_ub=np.vstack([ab, -ab]), b_ub=np.r_[hi, -lo], bounds=[(None, None)] * len(c),
                    method="highs")
        return r.x if r.status == 0 else None

    def streuung(self, teil: int, punkte: np.ndarray, mitte=None) -> tuple[np.ndarray, int]:
        """Worst-Case-Verschiebung der Punkte je Achse X, Y, Z (groesster Betrag) und Zahl freier Freiheitsgrade."""
        mitte = np.zeros(3) if mitte is None else np.asarray(mitte, float)
        lp = self._lp(teil, mitte)
        if lp is None:
            return np.zeros(3), 6
        ab, lo, hi, basis, frei = lp
        out = np.zeros(3)
        for p in np.atleast_2d(punkte) - mitte:
            for k, u in enumerate(np.eye(3)):
                c = basis @ np.r_[np.cross(p, u), u]
                for vz in (1, -1):
                    z = self._extrem(ab, lo, hi, vz * c)
                    if z is not None:
                        out[k] = max(out[k], abs(float(c @ z)))
        return out, frei

    def grenzlagen(self, teil: int, mitte=None) -> list[np.ndarray]:
        """Kleine Bewegungen (w, v um mitte) an den Grenzen des Spielraums, je gesperrter Richtung (Toleranz-Wiggle)."""
        lp = self._lp(teil, mitte)
        if lp is None:
            return []
        ab, lo, hi, basis, _ = lp
        out = []
        for c in np.eye(len(basis)):
            z = self._extrem(ab, lo, hi, c)
            x = basis.T @ z if z is not None else None
            if x is not None and np.linalg.norm(x) > 1e-12 and not any(np.allclose(x, o, atol=1e-12)
                                                                      or np.allclose(x, -o, atol=1e-12) for o in out):
                out.append(x)
        return out
    def verletzt(self) -> list[Verbindung]:
        """Verbindungen, die in der aktuellen Lage nicht (mehr) erfuellt sind."""
        return [v for v in self.verbindungen if not erfuellt(v.art, *self.merkmale(v), v.versatz)]

    def freiheitsgrade(self, teil: int) -> np.ndarray:
        """Offene Bewegungen des Teils gegen seine (als fest angenommenen) Verbindungspartner."""
        zeilen = []
        for v in self.verbindungen:
            if teil not in (v.teil, v.gegen_teil):
                continue
            ma, mb = self.merkmale(v)
            zeilen += bedingungen(v.art, mb if v.teil == teil else ma, ma if v.teil == teil else mb)
        return freiheitsgrade(zeilen)

    def teile(self) -> list[int]:
        return sorted({t for v in self.verbindungen for t in (v.teil, v.gegen_teil)})

    def fest(self, teil: int) -> bool:
        """Bezugsteil: nur Gegenteil, nie bewegt."""
        return all(v.teil != teil for v in self.verbindungen)

    def entferne(self, nummer: int):
        self.verbindungen = [v for v in self.verbindungen if v.nummer != nummer]
        self.formen.pop(nummer, None)

    def _verbindung(self, nummer: int) -> Verbindung | None:
        return next((v for v in self.verbindungen if v.nummer == nummer), None)

    def umkehren(self, nummer: int) -> str | None:
        """Bewegtes Teil an der Verbindung um 180° drehen: Zylinder Ende gegen Ende (Achse quer durch die Mitte des
        Eingriffs), Bolzen im Langloch und Teil auf Ebene um die Normale; Fehlertext, wenn nicht sinnvoll."""
        v = self._verbindung(nummer)
        if v is None:
            return tr("Verbindung nicht gefunden")
        ma, mb = self.merkmale(v)
        if v.art == KUGEL:
            return tr("Ein Kugelgelenk lässt sich nicht umkehren")
        if v.art in (KOAXIAL, LANGLOCH):
            if not v.eingriff:
                self._eingriff(v)
            q, e = self._achse(v)
            mitte = q + e * (sum(v.eingriff) / 2 if v.eingriff else 0.0)
            achse = _senkrechte(e)[0] if v.art == KOAXIAL else _kontakt(v.art, ma, mb)[2]
        elif v.art == PUNKT:
            mitte, _, achse, _, _ = _kontakt(v.art, ma, mb)
        else:
            mitte, achse = ma[1], mb[2]
        m = bewegung(np.r_[achse, -np.cross(achse, mitte)], 180.0)  # Drehung um die Achse durch mitte
        self.lagen[v.teil] = m @ self.lage(v.teil)
        v.eingriff = ()
        self._eingriff(v)
        return None

    def tauschen(self, nummer: int) -> str | None:
        """Rollen tauschen: das Gegenteil wird zum bewegten Teil (aendert Bezugsteil und Freiheitsgrade)."""
        v = self._verbindung(nummer)
        if v is None:
            return tr("Verbindung nicht gefunden")
        v.teil, v.gegen_teil = v.gegen_teil, v.teil
        v.flaeche, v.gegen_flaeche = v.gegen_flaeche, v.flaeche
        fa, fb = self.formen[nummer]
        self.formen[nummer] = (fb, fa)
        v.eingriff = ()
        self._eingriff(v)
        return None

    def neue_messgroesse(self, teil_a: int, fa, ia: int, teil_b: int, fb, ib: int):
        """Spalt oder Buendigkeit zwischen zwei parallelen Ebenen verschiedener Teile; Fehlertext sonst."""
        from . import baugruppe_mass as bm
        if teil_a == teil_b:
            return tr("Die zwei Flächen müssen zu verschiedenen Teilen gehören")
        art = bm.art_fuer(fa, fb)
        if art is None:
            return tr("Messgrößen gehen zwischen zwei parallelen Ebenen (Spalt oder Bündigkeit)")
        m = bm.Messgroesse(max((x.nummer for x in self.masse), default=0) + 1, teil_a, ia, teil_b, ib, art)
        self.masse.append(m)
        self.mass_formen[m.nummer] = (fa, fb)
        return m

    def entferne_messgroesse(self, nummer: int):
        self.masse = [m for m in self.masse if m.nummer != nummer]
        self.mass_formen.pop(nummer, None)

    def zuruecksetzen(self):
        self.verbindungen, self.lagen, self.formen = [], {}, {}
        self.masse, self.mass_formen = [], {}

    def als_dict(self) -> dict:
        from dataclasses import asdict
        return {"verbindungen": [asdict(v) for v in self.verbindungen],
                "lagen": {str(k): np.asarray(m).tolist() for k, m in self.lagen.items()},
                "masse": [asdict(m) for m in self.masse]}

    def setze_toleranz(self, nummer: int, toleranz: float, kippen: float | None = None, quelle: str = ""):
        for v in self.verbindungen:
            if v.nummer == nummer:
                v.toleranz = max(0.0, float(toleranz))
                if kippen is not None:
                    v.kippen = max(0.0, float(kippen))
                v.quelle = quelle

    def lade(self, d: dict, flaeche_von):
        """Aus als_dict(); flaeche_von(teil, index) liefert die Flaeche der Instanz in Dateilage."""
        self.zuruecksetzen()
        self.lagen = {int(k): np.array(m) for k, m in d.get("lagen", {}).items()}
        for x in d.get("verbindungen", []):
            v = Verbindung(**{**x, "eingriff": tuple(x.get("eingriff", ()))})
            fa, fb = flaeche_von(v.teil, v.flaeche), flaeche_von(v.gegen_teil, v.gegen_flaeche)
            if fa is not None and fb is not None:
                self.verbindungen.append(v)
                self.formen[v.nummer] = (fa, fb)
        from .baugruppe_mass import Messgroesse
        for x in d.get("masse", []):
            m = Messgroesse(**x)
            fa, fb = flaeche_von(m.teil_a, m.flaeche_a), flaeche_von(m.teil_b, m.flaeche_b)
            if fa is not None and fb is not None:
                self.masse.append(m)
                self.mass_formen[m.nummer] = (fa, fb)


def flaeche_im_teil(form, index: int, modell):
    """Flaeche mit diesem Index in der Form einer Teil-Instanz (mit deren Lage) oder None."""
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        if modell.flaechen_index(ex.Current()) == index:
            return ex.Current()
        ex.Next()
    return None


ORT_TYPEN = {"Position", "Symmetry", "Coaxiality", "Concentricity", "ProfileOfSurface", "ProfileOfLine"}
FLAECHE_TYPEN = ORT_TYPEN | {"Flatness", "Parallelism", "Perpendicularity", "Angularity"}


def toleranz_aus_pmi(baugruppe: Baugruppe, v: Verbindung, modell, pmi, allgemein: str = "") -> None:
    """Spielraum der Verbindung aus Geometrie und PMI beider Flaechen setzen (Allgemeintoleranz fuer fehlende
    Durchmesser); Quelle als Text."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    from .toleranzzone import _ist_innen, iso2768_laenge
    fa, fb = baugruppe.formen[v.nummer]
    flaechen = (v.flaeche, v.gegen_flaeche)
    an = [[p for p in pmi if i in p.flaechen] for i in flaechen]
    teile = []
    if v.art in (LANGLOCH, PUNKT, KUGEL):  # Spiel aus Lagetoleranzen; Langlochbreite bei Bedarf von Hand
        ort = [p for liste in an for p in liste if p.art == "toleranz" and p.typ in ORT_TYPEN and p.wert]
        teile = [p.wert_text() for p in ort]
        baugruppe.setze_toleranz(v.nummer, sum(float(p.wert) for p in ort) / 2, None,
                                 ", ".join(teile) if teile else tr("keine Toleranz an den Flächen"))
        return
    if v.art == EBEN:
        ort = [p for liste in an for p in liste if p.art == "toleranz" and p.typ in ORT_TYPEN and p.wert]
        alle = [p for liste in an for p in liste if p.art == "toleranz" and p.typ in FLAECHE_TYPEN and p.wert]
        h = sum(float(p.wert) for p in ort) / 2
        k = sum(float(p.wert) for p in alle) / min(_groesse(fa), _groesse(fb))
        teile = [p.wert_text() for p in alle]
        baugruppe.setze_toleranz(v.nummer, h, k, ", ".join(teile) if teile else tr("keine Toleranz an den Flächen"))
        return
    radien = []
    for f in (fa, fb):
        s = BRepAdaptor_Surface(f, True)
        radien.append(s.Cylinder().Radius() if s.GetType() == GeomAbs_Cylinder else None)
    if None in radien:  # Kegel: nur Positionstoleranzen
        radien = [0.0, 0.0]
    _, q, e = merkmal(fb)
    innen = [_ist_innen(f, q, e) for f in (fa, fb)]
    if innen[0] == innen[1]:
        loch, welle = (0, 1) if radien[0] >= radien[1] else (1, 0)
    else:
        loch, welle = (0, 1) if innen[0] else (1, 0)
    durchm = []
    for j, gross in ((loch, True), (welle, False)):
        d = 2 * radien[j]
        mass = next((p for p in an[j] if p.art == "mass" and "Diameter" in (p.typ or "") and p.nennwert), None)
        if mass is not None and None not in mass.grenzen():
            h, m = mass.grenzen()
            durchm.append(d + ((h if gross else m) - mass.nennwert))
            teile.append(mass.wert_text())
        elif allgemein and d > 0 and iso2768_laenge(allgemein, d):
            t = iso2768_laenge(allgemein, d)
            durchm.append(d + (t if gross else -t))
            teile.append(f"⌀{d:g} ±{t:g} (ISO 2768-{allgemein})")
        else:
            durchm.append(d)
    c = max(0.0, (durchm[0] - durchm[1]) / 2)
    lage = [p for liste in an for p in liste if p.art == "toleranz" and p.typ in ORT_TYPEN and p.wert]
    c += sum(float(p.wert) for p in lage) / 2
    teile += [p.wert_text() for p in lage]
    quelle = (tr("Geometrie") + (", " + ", ".join(teile) if teile else "")) if c > 0 else tr("ohne Spiel")
    baugruppe.setze_toleranz(v.nummer, c, None, quelle)
