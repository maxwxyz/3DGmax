"""Ansichten als Zeichnung: verdeckte Kanten berechnen (HLR) und als SVG, PDF oder DXF ausgeben (ohne Qt).

projiziere(): sichtbare und verdeckte Kanten einer Form fuer eine Blickrichtung als 2D-Polylinien (mm in der
Bildebene). blatt(): Drei-Tafel-Projektion plus Iso, Anordnung nach Norm (ISO: Projektionsmethode 1 / E,
ASME: Methode 3 / A). Schnittansichten mit Schraffur in kern.schnitt. Ausgabe als SVG und DXF (R12, LINE) hier,
PDF ueber Qt in ui.berichte.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SICHTBAR, VERDECKT, PMI, SCHRAFFUR = "sichtbar", "verdeckt", "pmi", "schraffur"


@dataclass
class Ansicht2D:
    name: str
    linien: dict[str, list[np.ndarray]] = field(default_factory=lambda: {SICHTBAR: [], VERDECKT: [], PMI: [],
                                                                         SCHRAFFUR: []})
    versatz: tuple[float, float] = (0.0, 0.0)  # Lage auf dem Blatt (mm)
    pmi_flaechen: list[np.ndarray] = field(default_factory=list)  # gefuellte Dreiecke (Pfeile, Schrift) 2D
    texte: list[tuple] = field(default_factory=list)  # (Ort 2D, Winkel Grad, Hoehe, Text) aus Platzhaltern
    schrift_farbe: str = "#1d4ed8"  # Texte der Ansicht (PMI blau, Schriftfeld schwarz)
    blatt: tuple[float, float] | None = None  # Blattgroesse (mm), wenn dies der Zeichnungsrahmen ist

    def grenzen(self):
        alle = [p for art in self.linien.values() for p in art if len(p)]
        if not alle:
            return np.zeros(2), np.zeros(2)
        a = np.vstack(alle)
        return a.min(axis=0), a.max(axis=0)


def _polylinien(form, abweichung: float) -> list[np.ndarray]:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    out = []
    if form is None or form.IsNull():
        return out
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    while ex.More():
        try:
            c = BRepAdaptor_Curve(topods.Edge(ex.Current()))
            d = GCPnts_QuasiUniformDeflection(c, abweichung)
            if d.IsDone() and d.NbPoints() >= 2:
                out.append(np.array([[d.Value(i).X(), d.Value(i).Y()] for i in range(1, d.NbPoints() + 1)]))
        except Exception:  # noqa: BLE001 - einzelne Kante ohne Kurve auslassen
            pass
        ex.Next()
    return out


def _achsen(richtung, oben):
    """Bildebene: Normale n (zum Betrachter), x nach rechts, y nach oben (wie der HLR-Projektor)."""
    n = -np.asarray(richtung, float)
    n = n / (np.linalg.norm(n) or 1.0)
    o = np.asarray(oben, float)
    x = np.cross(o, n)
    if np.linalg.norm(x) < 1e-9:
        x = np.cross([0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0], n)
    x = x / np.linalg.norm(x)
    return n, x, np.cross(n, x)


def pmi_hinzu(a: "Ansicht2D", grafiken: list, pmi_text: dict, richtung, oben):
    """Grafische PMI (Linien, Flaechen, Platzhaltertexte) in die Bildebene projizieren; liegen immer obenauf."""
    _, x, y = _achsen(richtung, oben)
    m = np.column_stack([x, y])
    for g in grafiken:
        for linie in g.linien:
            if len(linie) >= 2:
                a.linien[PMI].append(np.asarray(linie, float) @ m)
        for punkte, tris in g.dreiecke:
            p2 = np.asarray(punkte, float) @ m
            a.pmi_flaechen += [p2[list(t)] for t in tris]
        if g.platzhalter and not g.doppelt:
            text = "  ".join(pmi_text[i] for i in sorted(g.pmi_ids) if i in pmi_text) or g.name
            for ph in g.platzhalter:
                ort = np.asarray(ph.ursprung, float) @ m
                richtung_x = np.asarray(ph.x, float) @ m
                winkel = float(np.degrees(np.arctan2(richtung_x[1], richtung_x[0]))) if any(richtung_x) else 0.0
                a.texte.append((ort, winkel, float(ph.hoehe) * 0.8, ph.text or text))
    return a


def _netze(form) -> list[tuple[np.ndarray, np.ndarray]]:
    """(Punkte, Dreiecke) aller Flaechen ohne Geometrie (reine Netze); leer, wenn eine Flaeche exakt ist."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    out = []
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        if BRep_Tool.Surface(f) is not None:
            return []
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        pts = []
        for i in range(1, tri.NbNodes() + 1):
            p = tri.Node(i).Transformed(trsf)
            pts.append((p.X(), p.Y(), p.Z()))
        tris = [tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]
        out.append((np.asarray(pts, float), np.asarray(tris, int) - 1))
    return out


def _kanten_netz(punkte, dreiecke, n) -> list[tuple[int, int]]:
    """Flaechenrand (Kante nur in einem Dreieck) und Umriss (Nachbardreiecke zeigen zu/weg vom Betrachter)."""
    a, b, c = (punkte[dreiecke[:, k]] for k in range(3))
    vorne = np.cross(b - a, c - a) @ n > 0
    kanten: dict[tuple[int, int], list[int]] = {}
    for t, (i, j, k) in enumerate(dreiecke):
        for u, v in ((i, j), (j, k), (k, i)):
            kanten.setdefault((min(u, v), max(u, v)), []).append(t)
    return [k for k, ts in kanten.items() if len(ts) == 1 or (len(ts) == 2 and vorne[ts[0]] != vorne[ts[1]])]


class _Tiefenpuffer:
    """Einfache Rasterung der Dreiecke (Tiefe = Abstand zum Betrachter, groesser = naeher)."""

    def __init__(self, netze2d, aufloesung=1024):
        alle = np.vstack([p[:, :2] for p, _ in netze2d])
        self.lo = alle.min(axis=0)
        groesse = float((alle.max(axis=0) - self.lo).max()) or 1.0
        self.f = (aufloesung - 1) / groesse
        self.z = np.full((aufloesung, aufloesung), -np.inf)
        for p, tris in netze2d:
            q = (p[:, :2] - self.lo) * self.f
            for t in tris:
                self._dreieck(q[t], p[t, 2])

    def _dreieck(self, q, d):
        x0, y0 = np.floor(q.min(axis=0)).astype(int)
        x1, y1 = np.ceil(q.max(axis=0)).astype(int)
        n = self.z.shape[0]
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, n - 1), min(y1, n - 1)
        if x1 < x0 or y1 < y0:
            return
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        (ax, ay), (bx, by), (cx, cy) = q
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            return
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        l3 = 1 - l1 - l2
        innen = (l1 >= -1e-3) & (l2 >= -1e-3) & (l3 >= -1e-3)
        tiefe = l1 * d[0] + l2 * d[1] + l3 * d[2]
        feld = self.z[y0:y1 + 1, x0:x1 + 1]
        np.maximum(feld, np.where(innen, tiefe, -np.inf), out=feld)

    def sichtbar(self, p2, d, toleranz) -> np.ndarray:
        q = np.clip(np.rint((p2 - self.lo) * self.f).astype(int), 0, self.z.shape[0] - 1)
        umgebung = np.max([self.z[np.clip(q[:, 1] + dy, 0, self.z.shape[0] - 1),
                                  np.clip(q[:, 0] + dx, 0, self.z.shape[0] - 1)]
                           for dx in (-1, 0, 1) for dy in (-1, 0, 1)], axis=0)
        return d >= umgebung - toleranz


def projiziere_netz(netze, richtung, oben, name: str = "", verdeckt: bool = True) -> Ansicht2D:
    """Projektion reiner Netze: Flaechenraender und Umrisse, Verdeckung ueber einen Tiefenpuffer."""
    n, x, y = _achsen(richtung, oben)
    m = np.column_stack([x, y, n])
    netze2d = [(p @ m, t) for p, t in netze if len(t)]
    a = Ansicht2D(name)
    if not netze2d:
        return a
    puffer = _Tiefenpuffer(netze2d)
    toleranz = 3.0 / puffer.f
    for (p3, t), (p, _) in zip([(p, t) for p, t in netze if len(t)], netze2d):
        for i, j in _kanten_netz(p3, t, n):
            laenge = float(np.linalg.norm(p[j, :2] - p[i, :2])) * puffer.f
            k = max(2, min(200, int(laenge / 2) + 2))
            s = np.linspace(0.0, 1.0, k)[:, None]
            stuecke = p[i] * (1 - s) + p[j] * s
            sicht = puffer.sichtbar(stuecke[:, :2], stuecke[:, 2], toleranz)
            start = 0
            for e in range(1, k + 1):
                if e == k or sicht[e] != sicht[start]:
                    teil = stuecke[max(start - 1, 0) if start else 0:e, :2]
                    if len(teil) >= 2:
                        if sicht[start]:
                            a.linien[SICHTBAR].append(teil)
                        elif verdeckt:
                            a.linien[VERDECKT].append(teil)
                    start = e
    return a


def projiziere(form, richtung, oben, name: str = "", verdeckt: bool = True, abweichung: float = 0.05,
               schnell: bool = False) -> Ansicht2D:
    """Blick in 'richtung' (vom Betrachter ins Modell), 'oben' zeigt nach oben. Exakte HLR, Kanten und Umrisse.

    Reine Netze (STL, PRC, ...) haben keine Kurven fuer HLR; sie laufen ueber projiziere_netz(). schnell: HLR auf der
    Triangulierung (HLRBRep_PolyAlgo) - fuer Vorschaubilder; FTC-10 0,03 s statt 0,1 s, unter Last bis 1 s, und die
    HLR haelt die Python-Sperre (die Oberflaeche ruckelt so lange).
    """
    netze = _netze(form)
    if netze:
        return projiziere_netz(netze, richtung, oben, name, verdeckt)
    if schnell:
        return _projiziere_poly(form, richtung, oben, name, verdeckt, abweichung)
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.HLRAlgo import HLRAlgo_Projector
    from OCC.Core.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    d, x, _ = _achsen(richtung, oben)  # Projektor schaut entlang -Z seines Systems
    ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*d), gp_Dir(*x))
    algo = HLRBRep_Algo()
    algo.Add(form)
    algo.Projector(HLRAlgo_Projector(ax))
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    a = Ansicht2D(name)
    for teil in (h.VCompound(), h.OutLineVCompound(), h.Rg1LineVCompound()):
        a.linien[SICHTBAR] += _polylinien(teil, abweichung)
    if verdeckt:
        for teil in (h.HCompound(), h.OutLineHCompound()):
            a.linien[VERDECKT] += _polylinien(teil, abweichung)
    return a


def _projiziere_poly(form, richtung, oben, name: str, verdeckt: bool, abweichung: float) -> Ansicht2D:
    """Polygonale HLR auf der Triangulierung (vernetzt bei Bedarf grob nach der Groesse)."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.HLRAlgo import HLRAlgo_Projector
    from OCC.Core.HLRBRep import HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape
    box = Bnd_Box()
    brepbndlib.Add(form, box)
    if not box.IsVoid():
        x0, y0, z0, x1, y1, z1 = box.Get()
        BRepMesh_IncrementalMesh(form, max(x1 - x0, y1 - y0, z1 - z0) * 2e-3, False, 0.5, True)
    d, x, _ = _achsen(richtung, oben)
    algo = HLRBRep_PolyAlgo()
    algo.Load(form)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*d), gp_Dir(*x))))
    algo.Update()
    h = HLRBRep_PolyHLRToShape()
    h.Update(algo)
    a = Ansicht2D(name)
    for teil in (h.VCompound(), h.OutLineVCompound(), h.Rg1LineVCompound()):
        a.linien[SICHTBAR] += _polylinien(teil, abweichung)
    if verdeckt:
        for teil in (h.HCompound(), h.OutLineHCompound()):
            a.linien[VERDECKT] += _polylinien(teil, abweichung)
    return a


# Blickrichtung (ins Modell) und oben je Normansicht
RICHTUNGEN = {"vorne": ((0, 1, 0), (0, 0, 1)), "oben": ((0, 0, -1), (0, 1, 0)), "links": ((1, 0, 0), (0, 0, 1)),
              "rechts": ((-1, 0, 0), (0, 0, 1)), "unten": ((0, 0, 1), (0, -1, 0)), "hinten": ((0, -1, 0), (0, 0, 1)),
              "iso": ((-1, 1, -1), (0, 0, 1))}


def blatt(form, norm: str = "iso", verdeckt: bool = True, abstand: float = 20.0) -> list[Ansicht2D]:
    """Vorderansicht mit Draufsicht und Seitenansicht nach Projektionsmethode, dazu eine Iso-Ansicht."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    box = Bnd_Box()
    brepbndlib.Add(form, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    abweichung = max(x1 - x0, y1 - y0, z1 - z0) * 2e-4
    ansichten = {n: projiziere(form, *RICHTUNGEN[n], name=n, verdeckt=verdeckt and n != "iso", abweichung=abweichung)
                 for n in ("vorne", "oben", "links", "rechts", "iso")}
    vorne = ansichten["vorne"]
    vlo, vhi = vorne.grenzen()
    if norm == "asme":  # Methode 3: Draufsicht ueber, rechte Seitenansicht rechts der Vorderansicht
        anordnung = {"oben": "darueber", "rechts": "rechts"}
    else:  # ISO Methode 1: Draufsicht unter, linke Seitenansicht rechts der Vorderansicht
        anordnung = {"oben": "darunter", "links": "rechts"}
    ergebnis = [vorne]
    for name, lage in anordnung.items():
        a = ansichten[name]
        lo, hi = a.grenzen()
        if lage == "darueber":
            a.versatz = (0.0, vhi[1] + abstand - lo[1])
        elif lage == "darunter":
            a.versatz = (0.0, vlo[1] - abstand - hi[1])
        else:
            a.versatz = (vhi[0] + abstand - lo[0], 0.0)
        ergebnis.append(a)
    iso = ansichten["iso"]
    lo, hi = iso.grenzen()
    rechts = max(a.versatz[0] + a.grenzen()[1][0] for a in ergebnis)
    oben_y = max(a.versatz[1] + a.grenzen()[1][1] for a in ergebnis)
    iso.versatz = (rechts + abstand - lo[0], oben_y - hi[1])
    ergebnis.append(iso)
    return ergebnis


def _alle(ansichten):
    for a in ansichten:
        for art, linien in a.linien.items():
            for p in linien:
                yield a, art, p + np.asarray(a.versatz)


def _texte(ansichten, farbe: bool = False):
    for a in ansichten:
        for ort, winkel, hoehe, text in a.texte:
            yield (ort + np.asarray(a.versatz), winkel, hoehe, text) + ((a.schrift_farbe,) if farbe else ())


def rahmen(ansichten, rand: float = 10.0):
    blatt = next((a.blatt for a in ansichten if a.blatt), None)
    if blatt:  # Zeichnung auf einem Blatt: genau das Blatt
        return np.zeros(2), np.asarray(blatt, float)
    pts = [p for _, _, p in _alle(ansichten)]
    for o, winkel, hoehe, text in _texte(ansichten):  # Textkasten grob: Breite ~ 0.6 x Hoehe je Zeichen
        w = np.radians(winkel)
        ex, ey = np.array([np.cos(w), np.sin(w)]), np.array([-np.sin(w), np.cos(w)])
        b = 0.6 * hoehe * len(text)
        pts.append(np.array([o, o + ex * b, o + ey * hoehe, o + ex * b + ey * hoehe]))
    if not pts:
        return np.zeros(2), np.ones(2)
    a = np.vstack(pts)
    return a.min(axis=0) - rand, a.max(axis=0) + rand


def als_svg(ansichten: list[Ansicht2D], titel: str = "") -> str:
    lo, hi = rahmen(ansichten)
    b, h = hi - lo
    teile = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{b:.1f}mm" height="{h:.1f}mm" '
             f'viewBox="0 0 {b:.3f} {h:.3f}">', f"<title>{_xml(titel)}</title>",
             '<g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round">']
    for a, art, p in _alle(ansichten):
        q = np.column_stack([p[:, 0] - lo[0], hi[1] - p[:, 1]])  # SVG: y nach unten
        stil = {SICHTBAR: 'stroke-width="0.35"', VERDECKT: 'stroke-width="0.18" stroke-dasharray="2 1"',
                PMI: 'stroke-width="0.18" stroke="#1d4ed8"', SCHRAFFUR: 'stroke-width="0.13"'}[art]
        punkte = " ".join(f"{x:.3f},{y:.3f}" for x, y in q)
        teile.append(f'<polyline {stil} points="{punkte}"/>')
    teile.append("</g>")
    flaechen = [(tri + np.asarray(a.versatz)) for a in ansichten for tri in a.pmi_flaechen]
    if flaechen:
        teile.append('<g fill="#1d4ed8" stroke="none">')
        for tri in flaechen:
            punkte = " ".join(f"{x - lo[0]:.3f},{hi[1] - y:.3f}" for x, y in tri)
            teile.append(f'<polygon points="{punkte}"/>')
        teile.append("</g>")
    for ort, winkel, hoehe, text, farbe in _texte(ansichten, True):
        x, y = ort[0] - lo[0], hi[1] - ort[1]
        teile.append(f'<text x="{x:.3f}" y="{y:.3f}" font-family="Helvetica, Arial, sans-serif" '
                     f'font-size="{max(hoehe, 0.5):.3f}" fill="{farbe}" '
                     f'transform="rotate({-winkel:.2f} {x:.3f} {y:.3f})">{_xml(text)}</text>')
    teile.append("</svg>")
    return "\n".join(teile)


def als_dxf(ansichten: list[Ansicht2D]) -> str:
    """DXF R12 (ASCII): Linien auf den Layern SICHTBAR und VERDECKT (Linientyp DASHED)."""
    z = ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LTYPE", "70", "1",
         "0", "LTYPE", "2", "DASHED", "70", "0", "3", "Dashed", "72", "65", "73", "2", "40", "3.0", "49", "2.0",
         "49", "-1.0", "0", "ENDTAB", "0", "TABLE", "2", "LAYER", "70", "4",
         "0", "LAYER", "2", "SICHTBAR", "70", "0", "62", "7", "6", "CONTINUOUS",
         "0", "LAYER", "2", "VERDECKT", "70", "0", "62", "8", "6", "DASHED",
         "0", "LAYER", "2", "PMI", "70", "0", "62", "5", "6", "CONTINUOUS",
         "0", "LAYER", "2", "SCHRAFFUR", "70", "0", "62", "9", "6", "CONTINUOUS", "0", "ENDTAB", "0", "ENDSEC",
         "0", "SECTION", "2", "ENTITIES"]
    for _, art, p in _alle(ansichten):
        layer = {SICHTBAR: "SICHTBAR", VERDECKT: "VERDECKT", PMI: "PMI", SCHRAFFUR: "SCHRAFFUR"}[art]
        for (xa, ya), (xb, yb) in zip(p[:-1], p[1:]):
            z += ["0", "LINE", "8", layer, "10", f"{xa:.4f}", "20", f"{ya:.4f}", "30", "0.0",
                  "11", f"{xb:.4f}", "21", f"{yb:.4f}", "31", "0.0"]
    for ort, winkel, hoehe, text in _texte(ansichten):
        z += ["0", "TEXT", "8", "PMI", "10", f"{ort[0]:.4f}", "20", f"{ort[1]:.4f}", "30", "0.0",
              "40", f"{max(hoehe, 0.5):.4f}", "1", text.encode("ascii", "replace").decode(), "50", f"{winkel:.3f}"]
    z += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(z) + "\n"


# Blattformate ISO 5457 (quer, mm) und Massstaebe ISO 5455
FORMATE = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0),
           "A0": (1189.0, 841.0)}
MASSSTAEBE = (50.0, 20.0, 10.0, 5.0, 2.0, 1.0, 1 / 2, 1 / 5, 1 / 10, 1 / 20, 1 / 50, 1 / 100, 1 / 200, 1 / 500,
              1 / 1000)
SCHRIFTFELD = (180.0, 36.0)  # Breite, Hoehe (ISO 7200: 180 mm breit)


def massstab_text(m: float) -> str:
    return f"{m:g}:1" if m >= 1 else f"1:{1 / m:g}"


def skaliere(a: Ansicht2D, k: float) -> Ansicht2D:
    """Kopie der Ansicht im Massstab k (Linien, PMI-Flaechen, Texte, Lage)."""
    import copy
    b = copy.copy(a)
    b.linien = {art: [p * k for p in linien] for art, linien in a.linien.items()}
    b.pmi_flaechen = [t * k for t in a.pmi_flaechen]
    b.texte = [(np.asarray(o) * k, w, h * k, t) for o, w, h, t in a.texte]
    b.versatz = (a.versatz[0] * k, a.versatz[1] * k)
    return b


def auf_blatt(ansichten: list[Ansicht2D], format: str = "A3", massstab: float | None = None, titel: str = "",
              zeile: str = "") -> tuple[list[Ansicht2D], float]:
    """Ansichten im groessten passenden Normmassstab mittig auf ein Blatt mit Rahmen (Heftrand links 20 mm, sonst
    10 mm) und Schriftfeld unten rechts. Rueckgabe (Ansichten mit Rahmen zuerst, Massstab)."""
    b, h = FORMATE[format]
    sb, sh = SCHRIFTFELD
    links, unten, rechts, oben = 25.0, 10.0 + sh + 5.0, b - 15.0, h - 15.0  # freie Flaeche fuer die Ansichten
    lo, hi = rahmen(ansichten, 0.0)
    w, hoehe = max(hi[0] - lo[0], 1e-9), max(hi[1] - lo[1], 1e-9)
    if massstab is None:
        massstab = next((m for m in MASSSTAEBE if w * m <= rechts - links and hoehe * m <= oben - unten),
                        MASSSTAEBE[-1])
    out = [skaliere(a, massstab) for a in ansichten]
    mitte = np.array([(links + rechts) / 2, (unten + oben) / 2]) - (lo + hi) / 2 * massstab
    for a in out:
        a.versatz = (a.versatz[0] + mitte[0], a.versatz[1] + mitte[1])
    r = Ansicht2D("Blatt", blatt=(b, h), schrift_farbe="#000")
    ecke = lambda x0, y0, x1, y1: np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]])  # noqa: E731
    r.linien[SCHRAFFUR] = [ecke(0, 0, b, h)]  # Beschnitt (schmal)
    x0, y0 = b - 10 - sb, 10.0
    r.linien[SICHTBAR] = [ecke(20, 10, b - 10, h - 10), ecke(x0, y0, b - 10, y0 + sh),
                          np.array([[x0, y0 + sh / 2], [b - 10, y0 + sh / 2]]),
                          np.array([[x0 + 120, y0], [x0 + 120, y0 + sh / 2]])]
    r.texte = [(np.array([x0 + 3, y0 + sh / 2 + 6]), 0.0, 6.0, titel),
               (np.array([x0 + 3, y0 + 7]), 0.0, 2.5, zeile),
               (np.array([x0 + 123, y0 + 10]), 0.0, 3.5, f"{massstab_text(massstab)}   {format}")]
    return [r] + out, massstab


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
