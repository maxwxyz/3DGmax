"""Zwei Modelle in dasselbe Koordinatensystem bringen.

1. Gleiche Lage pruefen (die meisten Staende liegen schon richtig).
2. Sonst Bestpassung: Hauptachsen als Startwert (24 Orientierungen), dann robustes ICP (schlechteste Punkte
   werden ignoriert, damit geaenderte Bereiche die Passung nicht verziehen).
3. Von Hand: drei (oder mehr) Punktpaare, Loesung nach Kabsch.
Ergebnis ist eine 4x4-Matrix, die Modell B (neu) auf Modell A (alt) abbildet.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from threading import Lock

import numpy as np

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Plane
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FORWARD
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods
from OCC.Core.gp import gp_Translation


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


@dataclass
class _Netzspeicher:
    # Je Grundflaeche das feinste berechnete Netz, gemeinsam fuer ihre Einbaulagen.
    flaechen: dict = field(default_factory=dict)
    sperre: Lock = field(default_factory=Lock)


_ERSTMESH = Lock()


def _geradlinige_ebene(f):
    if BRepAdaptor_Surface(f).GetType() != GeomAbs_Plane:
        return False
    ex = TopExp_Explorer(f, TopAbs_EDGE)
    while ex.More():
        kante = topods.Edge(ex.Current())
        if not BRep_Tool.Degenerated(kante):
            try:
                if BRepAdaptor_Curve(kante).GetType() != GeomAbs_Line:
                    return False
            except RuntimeError:
                return False  # Ohne auswertbare Raumkurve ist die Sehne nicht verifiziert.
        ex.Next()
    return True


def _analysenetz(f, tri, loc, feinheit, speicher):
    parameter = tri.Parameters()
    if (parameter is not None and parameter.HasDeflection() and parameter.Deflection() <= feinheit
            and (tri.Deflection() <= feinheit or parameter.HasAngle() and parameter.Angle() <= 0.5)):
        return tri, loc
    # Ein reines Netz ist die Originalgeometrie. Bei ebenen Polygonen sind die Sehnen exakt.
    if BRep_Tool.Surface(f) is None or _geradlinige_ebene(f):
        return tri, loc
    basis = topods.Face(f.Located(TopLoc_Location()).Oriented(TopAbs_FORWARD))
    with speicher.sperre:
        eintrag = speicher.flaechen.get(basis)
        if eintrag is None or eintrag[0] != tri or eintrag[1] > feinheit:
            # Eigene Topologie: eine Analyse darf die Zeichnung und deren Kantenpolygone nicht umnetzen.
            kopie = topods.Face(BRepBuilderAPI_Copy(basis, False, False).Shape())
            BRepMesh_IncrementalMesh(kopie, feinheit, False, 0.5, True)
            ort = TopLoc_Location()
            netz = BRep_Tool.Triangulation(kopie, ort)
            if netz is None:
                from ..i18n import tr
                raise ValueError(tr("Eine CAD-Fläche konnte für die Analyse nicht verfeinert werden."))
            eintrag = speicher.flaechen[basis] = (tri, feinheit, netz, ort)
    return eintrag[2], f.Location().Multiplied(eintrag[3])


def tesselliere(flaechen, feinheit: float = 0.1, *, modell=None):
    """Dreiecksnetze in Modellkoordinaten; mit Modell bleiben feinere Analysenetze wiederverwendbar."""
    speicher = _Netzspeicher() if modell is None else vars(modell).setdefault("_analysenetze", _Netzspeicher())
    out, instanzen = [], {}
    for i, f in enumerate(flaechen):
        loc = TopLoc_Location()
        # Lesen und erstes Schreiben der nativen Triangulierung synchronisieren.
        with _ERSTMESH:
            tri = BRep_Tool.Triangulation(f, loc)
            if tri is None and BRep_Tool.Surface(f) is not None:
                BRepMesh_IncrementalMesh(f, feinheit, False, 0.5, True)
                tri = BRep_Tool.Triangulation(f, loc)
        if tri is None:
            out.append((np.zeros((0, 3)), np.zeros((0, 3), dtype=int)))
            continue
        tri, loc = _analysenetz(f, tri, loc, feinheit, speicher)
        out.append(None)
        instanzen.setdefault(tri, []).append((i, loc))
    # OCCT teilt das lokale Netz platzierter Flaechen. Knoten und Indizes je Netz nur einmal auslesen.
    for tri, lagen in instanzen.items():
        lokal = tri.MapNodeArray().to_numpy_array() if tri.NbNodes() else np.empty((0, 3))
        dreiecke = tri.MapTriangleArray().to_numpy_array() - 1 if tri.NbTriangles() else np.empty((0, 3), int)
        for j, (i, loc) in enumerate(lagen):
            if loc.IsIdentity():
                punkte = lokal.copy() if j else lokal
            else:
                punkte = _netz_in_lage(lokal, loc.Transformation())
            out[i] = (punkte, dreiecke.copy() if j else dreiecke)
    return out


def _netz_in_lage(punkte, trsf):
    versatz = trsf.TranslationPart().Coord()
    if trsf.Form() == gp_Translation:
        return punkte + versatz
    matrix = np.array([[trsf.Value(r, s) for s in (1, 2, 3)] for r in (1, 2, 3)])
    return punkte @ matrix.T + versatz


def abtasten(netze, anzahl: int = 6000, zufall: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Gleichmaessig verteilte Punkte auf der Oberflaeche (nach Flaeche gewichtet) und ihr Flaechenindex."""
    netze = list(netze)
    enden = np.cumsum([len(tri) for _, tri in netze], dtype=np.intp)
    if len(enden) == 0 or enden[-1] == 0:
        return np.zeros((0, 3)), np.zeros(0, dtype=int)
    ecken = np.empty((enden[-1], 3, 3))
    start = 0
    for (pts, tri), ende in zip(netze, enden):
        if ende > start:
            ecken[start:ende] = pts[tri]
        start = ende
    # Flaecheninhalte blockweise berechnen, auch fuer Netze mit Millionen Dreiecken.
    w = np.empty(len(ecken))
    for start in range(0, len(ecken), 65536):
        block = ecken[start:start + 65536]
        a, b, c = block.transpose(1, 0, 2)
        w[start:start + len(block)] = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    gesamt = w.sum()
    if gesamt == 0:
        return np.zeros((0, 3)), np.zeros(0, dtype=int)
    rng = np.random.default_rng(zufall)
    wahl = rng.choice(len(w), size=anzahl, p=w / gesamt)
    a, b, c = ecken[wahl].transpose(1, 0, 2)
    r1, r2 = rng.random(anzahl), rng.random(anzahl)
    s = np.sqrt(r1)
    punkte = (1 - s)[:, None] * a + (s * (1 - r2))[:, None] * b + (s * r2)[:, None] * c
    return punkte, np.searchsorted(enden, wahl, side="right")


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
        from scipy.spatial import cKDTree  # erst bei Bedarf: scipy beim Programmstart zu laden kostet ~0.5 s
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

    def in_der_naehe(self, punkte: np.ndarray, grenze: float) -> np.ndarray:
        """Maske der Punkte, die hoechstens etwa 'grenze' vom Netz entfernt sein koennen (schnelle Vorauswahl)."""
        abst, _ = self.baum.query(np.asarray(punkte, float), k=1, distance_upper_bound=grenze + self.rmax)
        return np.isfinite(abst)

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


def richte_aus(flaechen_a, flaechen_b, toleranz: float = 0.05, anzahl: int = 6000,
               punkte_b: np.ndarray | None = None, *, modell_a=None, modell_b=None) -> Ausrichtung:
    """Automatisch: gleiche Lage, sonst Bestpassung. punkte_b: Punktwolke statt der Flaechen von B."""
    netze_a = tesselliere(flaechen_a, modell=modell_a)
    a, _ = abtasten(netze_a, anzahl)
    if punkte_b is not None:
        b = punkte_b if len(punkte_b) <= anzahl else \
            punkte_b[np.random.default_rng(2).choice(len(punkte_b), anzahl, replace=False)]
    else:
        b, _ = abtasten(tesselliere(flaechen_b, modell=modell_b), anzahl, zufall=2)
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
        mittel, anteil = guete(probe, netz, m, toleranz)
        kandidaten.append((mittel, anteil, len(kandidaten), m))
    # Die kurze Probe-ICP reicht nicht immer zur Entscheidung: bei fast symmetrischen Teilen hat eine gedrehte oder
    # gespiegelte Lage oft den gleichen Median, aber deutlich weniger passende Punkte. Daher die besten Kandidaten
    # nach Median und nach Anteil vollstaendig einpassen und dann nach Anteil (gerundet), sonst Median waehlen.
    nach_median = sorted(kandidaten, key=lambda k: (k[0], k[2]))[:3]
    nach_anteil = sorted(kandidaten, key=lambda k: (-k[1], k[0], k[2]))[:3]
    gewaehlt = {k[2]: k for k in nach_median + nach_anteil}.values()
    fertig = []
    for _, _, nr, m in gewaehlt:
        m = icp_ebene(b, netz, icp(b, netz, m, schritte=20))
        mittel, anteil = guete(b, netz, m, toleranz)
        fertig.append((-round(anteil, 2), mittel, nr, m))
    _, mittel, _, beste = min(fertig, key=lambda k: k[:3])
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
