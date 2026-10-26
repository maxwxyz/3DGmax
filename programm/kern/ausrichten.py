"""Zwei Modelle in dasselbe Koordinatensystem bringen.

1. Gleiche Lage pruefen (die meisten Staende liegen schon richtig).
2. Sonst Bestpassung: Hauptachsen als Startwert (24 Orientierungen), dann robustes ICP (schlechteste Punkte
   werden ignoriert, damit geaenderte Bereiche die Passung nicht verziehen).
3. Von Hand: drei (oder mehr) Punktpaare, Loesung nach Kabsch.
Ergebnis ist eine 4x4-Matrix, die Modell B (neu) auf Modell A (alt) abbildet.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.TopLoc import TopLoc_Location


@dataclass
class Ausrichtung:
    matrix: np.ndarray  # 4x4, B -> A
    methode: str  # "gleich", "bestpassung", "punkte"
    mittel: float  # Median des Abstands Punkt-Oberflaeche (mm)
    anteil: float  # Anteil der Punkte innerhalb der Toleranz

    def wende_an(self, punkte: np.ndarray) -> np.ndarray:
        return punkte @ self.matrix[:3, :3].T + self.matrix[:3, 3]

    def gp_trsf(self):
        from OCC.Core.gp import gp_Trsf
        m = self.matrix
        t = gp_Trsf()
        t.SetValues(*m[0, :4], *m[1, :4], *m[2, :4])
        return t


def tesselliere(flaechen, feinheit: float = 0.1):
    """Dreiecksnetz je Flaeche: Liste von (punkte (n,3), dreiecke (m,3)) in Modellkoordinaten."""
    out = []
    for f in flaechen:
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        if tri is None:
            BRepMesh_IncrementalMesh(f, feinheit, False, 0.5, True)
            tri = BRep_Tool.Triangulation(f, loc)
        if tri is None:
            out.append((np.zeros((0, 3)), np.zeros((0, 3), dtype=int)))
            continue
        trsf = loc.Transformation()
        pts = np.array([_xyz(tri.Node(i).Transformed(trsf)) for i in range(1, tri.NbNodes() + 1)])
        dreiecke = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)], dtype=int) - 1
        out.append((pts, dreiecke))
    return out


def _xyz(p):
    return (p.X(), p.Y(), p.Z())


def abtasten(netze, anzahl: int = 6000, zufall: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Gleichmaessig verteilte Punkte auf der Oberflaeche (nach Flaeche gewichtet) und ihr Flaechenindex."""
    pts_all, flaeche_all, gewicht = [], [], []
    for idx, (pts, tri) in enumerate(netze):
        if len(tri) == 0:
            continue
        a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
        inhalt = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        pts_all.append((a, b, c))
        flaeche_all.append(np.full(len(tri), idx))
        gewicht.append(inhalt)
    if not gewicht:
        return np.zeros((0, 3)), np.zeros(0, dtype=int)
    a = np.vstack([x[0] for x in pts_all])
    b = np.vstack([x[1] for x in pts_all])
    c = np.vstack([x[2] for x in pts_all])
    fl = np.concatenate(flaeche_all)
    w = np.concatenate(gewicht)
    rng = np.random.default_rng(zufall)
    wahl = rng.choice(len(w), size=anzahl, p=w / w.sum())
    r1, r2 = rng.random(anzahl), rng.random(anzahl)
    s = np.sqrt(r1)
    punkte = (1 - s)[:, None] * a[wahl] + (s * (1 - r2))[:, None] * b[wahl] + (s * r2)[:, None] * c[wahl]
    return punkte, fl[wahl]


def _teile_dreiecke(a, b, c, laenge: float):
    """Grosse Dreiecke teilen, bis alle Kanten kuerzer als 'laenge' sind (fuer die Naechste-Suche)."""
    fertig_a, fertig_b, fertig_c, fertig_i = [], [], [], []
    idx = np.arange(len(a))
    for _ in range(12):
        lang = np.maximum.reduce([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1),
                                  np.linalg.norm(a - c, axis=1)]) > laenge
        fertig_a.append(a[~lang]); fertig_b.append(b[~lang]); fertig_c.append(c[~lang]); fertig_i.append(idx[~lang])
        if not lang.any():
            break
        a, b, c, idx = a[lang], b[lang], c[lang], idx[lang]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        a, b, c = (np.vstack([a, ab, ca, ab]), np.vstack([ab, b, bc, bc]), np.vstack([ca, bc, c, ca]))
        idx = np.concatenate([idx] * 4)
    else:
        fertig_a.append(a); fertig_b.append(b); fertig_c.append(c); fertig_i.append(idx)
    return np.vstack(fertig_a), np.vstack(fertig_b), np.vstack(fertig_c), np.concatenate(fertig_i)


def _punkt_dreieck(p, a, b, c):
    """Naechster Punkt auf Dreiecken (vektorisiert, Ericson 'Real-Time Collision Detection' 5.1.5)."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.einsum("ij,ij->i", ab, ap), np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3, d4 = np.einsum("ij,ij->i", ab, bp), np.einsum("ij,ij->i", ac, bp)
    cp = p - c
    d5, d6 = np.einsum("ij,ij->i", ab, cp), np.einsum("ij,ij->i", ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    nenner = va + vb + vc
    nenner = np.where(np.abs(nenner) < 1e-30, 1e-30, nenner)
    v, w = vb / nenner, vc / nenner
    q = a + ab * v[:, None] + ac * w[:, None]  # im Inneren
    with np.errstate(divide="ignore", invalid="ignore"):
        # Kanten
        t_ab = np.clip(d1 / (d1 - d3), 0, 1)
        t_ac = np.clip(d2 / (d2 - d6), 0, 1)
        t_bc = np.clip((d4 - d3) / ((d4 - d3) + (d5 - d6)), 0, 1)
    kanten = [(vc <= 0) & (d1 >= 0) & (d3 <= 0), (vb <= 0) & (d2 >= 0) & (d6 <= 0),
              (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)]
    q = np.where(kanten[0][:, None], a + ab * np.nan_to_num(t_ab)[:, None], q)
    q = np.where(kanten[1][:, None], a + ac * np.nan_to_num(t_ac)[:, None], q)
    q = np.where(kanten[2][:, None], b + (c - b) * np.nan_to_num(t_bc)[:, None], q)
    # Ecken
    q = np.where(((d1 <= 0) & (d2 <= 0))[:, None], a, q)
    q = np.where(((d3 >= 0) & (d4 <= d3))[:, None], b, q)
    q = np.where(((d6 >= 0) & (d5 <= d6))[:, None], c, q)
    return q


class NetzAbstand:
    """Abstand von Punkten zur Oberflaeche eines Netzes (schnell, genau bis etwa zur Netzfeinheit).

    Grosse Dreiecke werden geteilt (Kantenlaenge <= L), Kandidaten kommen aus einem KD-Baum ueber die
    Dreiecksmitten, der Abstand je Kandidat ist exakt. Selten wird ein Nachbardreieck statt des richtigen
    gefunden; der Fehler bleibt dann in der Groessenordnung der Netzabweichung. Fuer exakte Werte rechnet
    vergleich_geo die kritischen Punkte gegen die B-Rep-Flaeche nach.
    """

    def __init__(self, netze, k: int = 16, teilung: float = 80.0):
        a_l, b_l, c_l, f_l = [], [], [], []
        for idx, (pts, tri) in enumerate(netze):
            if len(tri):
                a_l.append(pts[tri[:, 0]]); b_l.append(pts[tri[:, 1]]); c_l.append(pts[tri[:, 2]])
                f_l.append(np.full(len(tri), idx))
        a, b, c = np.vstack(a_l), np.vstack(b_l), np.vstack(c_l)
        flaeche = np.concatenate(f_l)
        alle = np.vstack([a, b, c])
        diag = float(np.linalg.norm(alle.max(axis=0) - alle.min(axis=0)))
        a, b, c, i = _teile_dreiecke(a, b, c, max(diag / teilung, 1e-6))
        self.a, self.b, self.c, self.flaeche = a, b, c, flaeche[i]
        mitte = (a + b + c) / 3
        self.rmax = float(max(np.linalg.norm(a - mitte, axis=1).max(), np.linalg.norm(b - mitte, axis=1).max(),
                              np.linalg.norm(c - mitte, axis=1).max()))
        self.baum = cKDTree(mitte)
        self.k = min(k, len(a))

    def _naechste(self, punkte, kand):
        beste_d = np.full(len(punkte), np.inf)
        beste_q = np.zeros_like(punkte)
        beste_t = np.zeros(len(punkte), dtype=int)
        for j in range(kand.shape[1]):
            t = kand[:, j]
            q = _punkt_dreieck(punkte, self.a[t], self.b[t], self.c[t])
            d = np.linalg.norm(punkte - q, axis=1)
            besser = d < beste_d
            beste_d[besser], beste_q[besser], beste_t[besser] = d[besser], q[besser], t[besser]
        self.letzte_dreiecke = beste_t
        return beste_d, beste_q, self.flaeche[beste_t]

    def normalen(self, dreiecke: np.ndarray) -> np.ndarray:
        n = np.cross(self.b[dreiecke] - self.a[dreiecke], self.c[dreiecke] - self.a[dreiecke])
        return n / np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]

    def abfrage(self, punkte: np.ndarray):
        """(Abstand, naechster Punkt, Flaechenindex) je Punkt."""
        punkte = np.asarray(punkte, float)
        abst, kand = self.baum.query(punkte, k=self.k)
        kand = kand.reshape(len(punkte), -1)
        abst = abst.reshape(len(punkte), -1)
        d, q, f = self._naechste(punkte, kand)
        return d, q, f


def _matrix(rot: np.ndarray, verschiebung: np.ndarray) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = rot
    m[:3, 3] = verschiebung
    return m


def kabsch(von: np.ndarray, nach: np.ndarray) -> np.ndarray:
    """Starre Abbildung (Rotation + Verschiebung), die 'von' bestmoeglich auf 'nach' legt."""
    cv, cn = von.mean(axis=0), nach.mean(axis=0)
    h = (von - cv).T @ (nach - cn)
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    rot = vt.T @ np.diag([1, 1, d]) @ u.T
    return _matrix(rot, cn - rot @ cv)


def guete(b_punkte: np.ndarray, netz: NetzAbstand, matrix: np.ndarray, toleranz: float) -> tuple[float, float]:
    d, _, _ = netz.abfrage(b_punkte @ matrix[:3, :3].T + matrix[:3, 3])
    return float(np.median(d)), float(np.mean(d <= toleranz))


def icp(b: np.ndarray, netz: NetzAbstand, start: np.ndarray, schritte: int = 40,
        behalten: float = 0.85) -> np.ndarray:
    """Robustes ICP Punkt zu Oberflaeche; nur der beste Anteil 'behalten' der Paare zaehlt je Schritt."""
    m = start.copy()
    vorher = np.inf
    for _ in range(schritte):
        bt = b @ m[:3, :3].T + m[:3, 3]
        d, q, _ = netz.abfrage(bt)
        grenze = np.quantile(d, behalten)
        auswahl = d <= grenze
        schritt = kabsch(bt[auswahl], q[auswahl])
        m = schritt @ m
        mittel = float(d[auswahl].mean())
        if abs(vorher - mittel) < 1e-7:
            break
        vorher = mittel
    return m


def _drehung(rx, ry, rz) -> np.ndarray:
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    return (np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
            @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]))


def icp_ebene(b: np.ndarray, netz: NetzAbstand, start: np.ndarray, schritte: int = 30,
              behalten: float = 0.9) -> np.ndarray:
    """Punkt-zu-Ebene-ICP (linearisiert): genau auch bei grossen ebenen Flaechen."""
    m = start.copy()
    for _ in range(schritte):
        bt = b @ m[:3, :3].T + m[:3, 3]
        d, q, _ = netz.abfrage(bt)
        n = netz.normalen(netz.letzte_dreiecke)
        auswahl = d <= np.quantile(d, behalten)
        p, q, n = bt[auswahl], q[auswahl], n[auswahl]
        a = np.hstack([np.cross(p, n), n])
        rechts = np.einsum("ij,ij->i", n, q - p)
        x, *_ = np.linalg.lstsq(a, rechts, rcond=None)
        schritt = _matrix(_drehung(*x[:3]), x[3:])
        m = schritt @ m
        if np.linalg.norm(x) < 1e-10:
            break
    return m


def _orientierungen():
    """Die 24 eigentlichen Drehungen, die Achsen auf Achsen abbilden."""
    out = []
    for perm in itertools.permutations(range(3)):
        for vz in itertools.product((1, -1), repeat=3):
            r = np.zeros((3, 3))
            for zeile, (spalte, s) in enumerate(zip(perm, vz)):
                r[zeile, spalte] = s
            if np.linalg.det(r) > 0:
                out.append(r)
    return out


def _hauptachsen(p: np.ndarray):
    c = p.mean(axis=0)
    w, v = np.linalg.eigh(np.cov((p - c).T))
    v = v[:, np.argsort(w)[::-1]]
    if np.linalg.det(v) < 0:
        v[:, 2] *= -1
    return c, v


def richte_aus(flaechen_a, flaechen_b, toleranz: float = 0.05, anzahl: int = 6000) -> Ausrichtung:
    """Automatisch: gleiche Lage, sonst Bestpassung."""
    netze_a = tesselliere(flaechen_a)
    a, _ = abtasten(netze_a, anzahl)
    b, _ = abtasten(tesselliere(flaechen_b), anzahl, zufall=2)
    netz = NetzAbstand(netze_a)
    # Lage gilt als gleich, wenn mindestens die Haelfte der Punkte schon exakt aufliegt: dann teilen beide Staende
    # das Koordinatensystem, und eine Bestpassung wuerde geaenderte Bereiche nur auf alles verteilen
    mittel, anteil = guete(b, netz, np.eye(4), toleranz)
    if anteil > 0.5:
        return Ausrichtung(np.eye(4), "gleich", mittel, anteil)
    ca, va = _hauptachsen(a)
    cb, vb = _hauptachsen(b)
    kandidaten = []
    probe = b[:: max(1, len(b) // 1500)]
    for o in _orientierungen():
        rot = va @ o @ vb.T
        start = _matrix(rot, ca - rot @ cb)
        m = icp(probe, netz, start, schritte=15)
        kandidaten.append((guete(probe, netz, m, toleranz)[0], m))
    kandidaten.sort(key=lambda k: k[0])
    beste = icp(b, netz, kandidaten[0][1], schritte=20)
    beste = icp_ebene(b, netz, beste)
    mittel, anteil = guete(b, netz, beste, toleranz)
    return Ausrichtung(beste, "bestpassung", mittel, anteil)


def richte_nach_punkten(paare_b: list, paare_a: list) -> Ausrichtung:
    """Von Hand: mindestens drei Punktpaare (B -> A)."""
    b, a = np.asarray(paare_b, float), np.asarray(paare_a, float)
    if len(a) < 3 or len(a) != len(b):
        raise ValueError("Mindestens drei Punktpaare nötig")
    m = kabsch(b, a)
    rest = np.linalg.norm(b @ m[:3, :3].T + m[:3, 3] - a, axis=1)
    return Ausrichtung(m, "punkte", float(rest.mean()), float(np.mean(rest < 0.05)))


# --- Manuell: Elementpaare (Punkt, Ebene, Achse) ---

PUNKT, EBENE, ACHSE = "punkt", "ebene", "achse"


def element_von(form, punkt, gefangen: bool = False):
    """Element fuer die Ausrichtung: gefangener Punkt -> Punkt, ebene Flaeche -> Ebene,
    Zylinder/Kegel/Kreiskante -> Achse, sonst Punkt (Klickpunkt). Rueckgabe (art, ort (3,), richtung (3,)|None)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
    from OCC.Core.TopoDS import topods
    p = np.asarray(punkt, float)
    if gefangen or form is None:
        return PUNKT, p, None
    if form.ShapeType() == TopAbs_FACE:
        from OCC.Core.BRep import BRep_Tool
        if BRep_Tool.Surface(topods.Face(form)) is None:
            return PUNKT, p, None  # Netzflaeche: nur der Klickpunkt
        s = BRepAdaptor_Surface(topods.Face(form))
        if s.GetType() == GeomAbs_Plane:
            n = s.Plane().Axis().Direction()
            v = np.array([n.X(), n.Y(), n.Z()])
            return EBENE, p, (-v if form.Orientation() == TopAbs_REVERSED else v)
        if s.GetType() in (GeomAbs_Cylinder, GeomAbs_Cone):
            ax = (s.Cylinder() if s.GetType() == GeomAbs_Cylinder else s.Cone()).Axis()
            o, d = ax.Location(), ax.Direction()
            return ACHSE, np.array([o.X(), o.Y(), o.Z()]), np.array([d.X(), d.Y(), d.Z()])
    if form.ShapeType() == TopAbs_EDGE:
        c = BRepAdaptor_Curve(topods.Edge(form))
        if c.GetType() == GeomAbs_Circle:
            ax = c.Circle().Axis()
            o, d = ax.Location(), ax.Direction()
            return ACHSE, np.array([o.X(), o.Y(), o.Z()]), np.array([d.X(), d.Y(), d.Z()])
    return PUNKT, p, None


def _rotation(v: np.ndarray) -> np.ndarray:
    """Rodrigues: Drehvektor -> Drehmatrix."""
    w = float(np.linalg.norm(v))
    if w < 1e-15:
        return np.eye(3)
    k = v / w
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(w) * kx + (1 - np.cos(w)) * kx @ kx


def _reste(x, paare, gewicht_richtung=50.0):
    r, t = _rotation(x[:3]), x[3:]
    out = []
    for art, (ob, db), (oa, da) in paare:
        pb = r @ ob + t
        if art == PUNKT:
            out += list(pb - oa)
        elif art == EBENE:
            out.append(float(da @ (pb - oa)))
            out += list(gewicht_richtung * (r @ db - da))
        else:  # Achse: Richtung (Vorzeichen egal) und Abstand des Achspunkts zur Gegenachse
            rb = r @ db
            rb = rb if rb @ da >= 0 else -rb
            out += list(gewicht_richtung * (rb - da))
            d = pb - oa
            out += list(d - da * (d @ da))
    return np.array(out)


def richte_nach_elementen(paare: list) -> Ausrichtung:
    """paare: [(art, (ort_b, richtung_b), (ort_a, richtung_a))] mit B im Originalsystem.
    Loest die starre Abbildung B -> A; ValueError, wenn die Elemente die Lage nicht eindeutig festlegen."""
    from scipy.optimize import least_squares
    if not paare:
        raise ValueError("Ausrichtung nicht eindeutig – weitere Elemente wählen")
    pkt = [(ob, oa) for art, (ob, _), (oa, _) in paare if art == PUNKT]
    start = np.zeros(6)
    if len(pkt) >= 3:
        m = kabsch(np.array([b for b, _ in pkt]), np.array([a for _, a in pkt]))
        from scipy.spatial.transform import Rotation
        start[:3] = Rotation.from_matrix(m[:3, :3]).as_rotvec()
        start[3:] = m[:3, 3]
    ergebnis = None
    for versuch in range(8):  # mehrere Startwerte gegen Nebenminima (z. B. 180 Grad gedreht)
        x0 = start.copy() if versuch == 0 else np.concatenate([np.random.default_rng(versuch).normal(size=3) * 1.5,
                                                               start[3:]])
        loes = least_squares(_reste, x0, args=(paare,), method="lm" if len(_reste(x0, paare)) >= 6 else "trf")
        if ergebnis is None or loes.cost < ergebnis.cost:
            ergebnis = loes
        if loes.cost < 1e-12:
            break
    rang = np.linalg.matrix_rank(ergebnis.jac, tol=1e-6)
    if rang < 6:
        raise ValueError("Ausrichtung nicht eindeutig – weitere Elemente wählen")
    m = _matrix(_rotation(ergebnis.x[:3]), ergebnis.x[3:])
    rest = float(np.sqrt(2 * ergebnis.cost / max(len(ergebnis.fun), 1)))
    return Ausrichtung(m, "punkte", rest, 1.0 if rest < 0.05 else 0.0)
