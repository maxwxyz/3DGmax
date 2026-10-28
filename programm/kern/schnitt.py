"""Schnittkonturen: Schnitt einer Form mit einer oder mehreren Ebenen als Linienzuege (3D und in der Ebene).

kontur() schneidet exakt (BRepAlgoAPI_Section) und tastet die Schnittkanten ab; Netzmodelle ohne Geometrie
werden ueber ihre Dreiecke geschnitten. blatt() legt die Konturen mehrerer Ebenen nebeneinander auf ein Blatt,
schnittansichten() die Schnittansichten (Rest hinter der Ebene als Kantenansicht, Schnittflaeche schraffiert, ISO
128-50: 45 Grad, schmale Linie); die Ausgabe als SVG/DXF uebernimmt kern.zeichnung.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import zeichnung


@dataclass
class Ebene:
    punkt: np.ndarray
    normale: np.ndarray  # zeigt zur weggeschnittenen Seite
    name: str = ""

    def achsen(self) -> tuple[np.ndarray, np.ndarray]:
        """x, y in der Ebene (Blick auf die Schnittflaeche von der weggeschnittenen Seite, y moeglichst nach +Z)."""
        _, x, y = zeichnung._achsen(-np.asarray(self.normale, float), _oben(self.normale))
        return x, y


def _oben(n) -> np.ndarray:
    n = np.asarray(n, float)
    return np.array([0.0, 1.0, 0.0]) if abs(n[2]) > 0.9 else np.array([0.0, 0.0, 1.0])


def _verketten(stuecke: list[np.ndarray], eps: float) -> list[np.ndarray]:
    """Linienstuecke mit gemeinsamen Endpunkten zu moeglichst langen Linienzuegen verbinden."""
    offen = [np.asarray(s, float) for s in stuecke if len(s) >= 2]
    out = []
    while offen:
        kette = offen.pop()
        gefunden = True
        while gefunden:
            gefunden = False
            for i, s in enumerate(offen):
                if np.linalg.norm(kette[-1] - s[0]) <= eps:
                    kette = np.vstack([kette, s[1:]])
                elif np.linalg.norm(kette[-1] - s[-1]) <= eps:
                    kette = np.vstack([kette, s[::-1][1:]])
                elif np.linalg.norm(kette[0] - s[-1]) <= eps:
                    kette = np.vstack([s, kette[1:]])
                elif np.linalg.norm(kette[0] - s[0]) <= eps:
                    kette = np.vstack([s[::-1], kette[1:]])
                else:
                    continue
                offen.pop(i)
                gefunden = True
                break
        out.append(kette)
    return out


def _kanten_3d(form, abweichung: float) -> list[np.ndarray]:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    out = []
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    while ex.More():
        try:
            c = BRepAdaptor_Curve(topods.Edge(ex.Current()))
            d = GCPnts_QuasiUniformDeflection(c, abweichung)
            if d.IsDone() and d.NbPoints() >= 2:
                out.append(np.array([[d.Value(i).X(), d.Value(i).Y(), d.Value(i).Z()]
                                     for i in range(1, d.NbPoints() + 1)]))
        except Exception:  # noqa: BLE001 - Kante ohne Kurve auslassen
            pass
        ex.Next()
    return out


def _netz_schnitt(netze, punkt, n) -> list[np.ndarray]:
    """Schnitt von Dreiecksnetzen mit der Ebene: je geschnittenem Dreieck ein Linienstueck."""
    out = []
    for p, t in netze:
        if not len(t):
            continue
        d = (p - punkt) @ n
        for tri in t:
            dd = d[tri]
            if dd.min() > 0 or dd.max() < 0:
                continue
            q = []
            for i, j in ((0, 1), (1, 2), (2, 0)):
                a, b = dd[i], dd[j]
                if (a < 0) != (b < 0) and a != b:
                    s = a / (a - b)
                    q.append(p[tri[i]] * (1 - s) + p[tri[j]] * s)
            if len(q) == 2:
                out.append(np.array(q))
    return out


def kontur(form, ebene: Ebene, abweichung: float | None = None) -> list[np.ndarray]:
    """Schnittlinien der Form mit der Ebene als 3D-Linienzuege (mm)."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    box = Bnd_Box()
    brepbndlib.Add(form, box)
    if box.IsVoid():
        return []
    x0, y0, z0, x1, y1, z1 = box.Get()
    groesse = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) or 1.0
    abweichung = abweichung or groesse * 2e-4
    n = np.asarray(ebene.normale, float)
    n = n / np.linalg.norm(n)
    netze = zeichnung._netze(form)
    if netze:
        stuecke = _netz_schnitt(netze, np.asarray(ebene.punkt, float), n)
    else:
        schnitt = BRepAlgoAPI_Section(form, gp_Pln(gp_Pnt(*map(float, ebene.punkt)), gp_Dir(*map(float, n))), True)
        if not schnitt.IsDone():
            return []
        stuecke = _kanten_3d(schnitt.Shape(), abweichung)
    return _verketten(stuecke, groesse * 1e-6)


def in_ebene(linien: list[np.ndarray], ebene: Ebene) -> list[np.ndarray]:
    """3D-Linienzuege in 2D-Koordinaten der Ebene."""
    x, y = ebene.achsen()
    m = np.column_stack([x, y])
    o = np.asarray(ebene.punkt, float)
    return [(np.asarray(l, float) - o) @ m for l in linien]


def blatt(form, ebenen: list[Ebene], abstand: float = 20.0) -> list:
    """Je Ebene eine 2D-Ansicht der Schnittkontur, nebeneinander angeordnet (fuer zeichnung.als_svg/als_dxf)."""
    out, x = [], 0.0
    for i, e in enumerate(ebenen, 1):
        a = zeichnung.Ansicht2D(e.name or f"Schnitt {i}")
        a.linien[zeichnung.SICHTBAR] = in_ebene(kontur(form, e), e)
        lo, hi = a.grenzen()
        a.versatz = (x - lo[0], -lo[1])
        x += float(hi[0] - lo[0]) + abstand
        out.append(a)
    return out


def schraffur(konturen: list[np.ndarray], abstand: float, winkel: float = 45.0) -> list[np.ndarray]:
    """Schraffurlinien in den geschlossenen 2D-Konturen (gerade/ungerade: Loecher bleiben frei)."""
    w = np.radians(winkel)
    r = np.array([[np.cos(w), np.sin(w)], [-np.sin(w), np.cos(w)]])  # Linienrichtung -> x
    stuecke = []
    for k in konturen:
        k = np.asarray(k, float) @ r.T
        if len(k) >= 3 and np.linalg.norm(k[0] - k[-1]) > 1e-9:
            k = np.vstack([k, k[:1]])  # schliessen
        if len(k) >= 2:
            stuecke.append((k[:-1], k[1:]))
    if not stuecke:
        return []
    a = np.vstack([s[0] for s in stuecke])
    b = np.vstack([s[1] for s in stuecke])
    y0, y1 = min(a[:, 1].min(), b[:, 1].min()), max(a[:, 1].max(), b[:, 1].max())
    out = []
    for y in np.arange(np.floor(y0 / abstand) * abstand + abstand / 2, y1, abstand):
        kreuzt = (a[:, 1] <= y) != (b[:, 1] <= y)  # halboffen: Ecken zaehlen einmal
        if not kreuzt.any():
            continue
        t = (y - a[kreuzt, 1]) / (b[kreuzt, 1] - a[kreuzt, 1])
        xs = np.sort(a[kreuzt, 0] + t * (b[kreuzt, 0] - a[kreuzt, 0]))
        for x_a, x_b in zip(xs[0::2], xs[1::2]):
            if x_b - x_a > 1e-9:
                out.append(np.array([[x_a, y], [x_b, y]]) @ r)
    return out


def _rest(form, ebene: Ebene):
    """Form ohne die weggeschnittene Seite (Normalenrichtung) oder None (Netz, Fehler)."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    n = np.asarray(ebene.normale, float)
    n = n / np.linalg.norm(n)
    p = np.asarray(ebene.punkt, float)
    flaeche = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*map(float, p)), gp_Dir(*map(float, n)))).Face()
    weg = BRepPrimAPI_MakeHalfSpace(flaeche, gp_Pnt(*map(float, p + n))).Solid()
    schnitt = BRepAlgoAPI_Cut(form, weg)
    return schnitt.Shape() if schnitt.IsDone() and not schnitt.Shape().IsNull() else None


def schnittansicht(form, ebene: Ebene, verdeckt: bool = False, abstand: float | None = None):
    """Ansicht auf die Schnittflaeche (von der weggeschnittenen Seite): Kanten des Rests, Schnittkontur und
    Schraffur (Abstand nach Groesse, etwa 1/40 der Konturbreite, 0,5 ... 5 mm)."""
    n = np.asarray(ebene.normale, float)
    richtung, oben = -n, _oben(n)
    rest = _rest(form, ebene) if not zeichnung._netze(form) else None
    if rest is not None:
        a = zeichnung.projiziere(rest, richtung, oben, ebene.name, verdeckt)
    else:
        a = zeichnung.Ansicht2D(ebene.name)
    _, x, y = zeichnung._achsen(richtung, oben)
    m = np.column_stack([x, y])
    konturen = [np.asarray(k, float) @ m for k in kontur(form, ebene)]
    a.linien[zeichnung.SICHTBAR] += konturen
    if konturen:
        alle = np.vstack(konturen)
        breite = float(max(np.ptp(alle[:, 0]), np.ptp(alle[:, 1])))
        a.linien[zeichnung.SCHRAFFUR] = schraffur(konturen, abstand or min(5.0, max(0.5, breite / 40)))
    return a


def schnittansichten(form, ebenen: list[Ebene], abstand: float = 20.0) -> list:
    """Je Ebene eine Schnittansicht, nebeneinander (fuer zeichnung.als_svg/als_dxf)."""
    out, x = [], 0.0
    for e in ebenen:
        a = schnittansicht(form, e)
        lo, hi = a.grenzen()
        a.versatz = (x - lo[0], -lo[1])
        x += float(hi[0] - lo[0]) + abstand
        out.append(a)
    return out
