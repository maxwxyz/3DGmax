"""Schnellmessung: Kennwerte der aktuellen Auswahl fuer die Statusleiste (ohne Qt).

info(formen) liefert eine Liste (schluessel, text). Der Schluessel ist die Gruppe, die der Nutzer ausblenden
kann (siehe GRUPPEN); Texte sind schon uebersetzt.
"""

from __future__ import annotations

import math

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepTools import breptools
from OCC.Core.GeomAbs import (GeomAbs_Circle, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Ellipse, GeomAbs_Line,
                              GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus)
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods

from ..i18n import tr
from .messen import _richtung, art_von

# Gruppen, die sich einzeln ausblenden lassen (Anzeige ueber tr())
GRUPPEN = {"art": "Elementart", "laenge": "Länge", "rund": "Durchmesser/Radius", "flaeche": "Flächeninhalt",
           "abstand": "Abstand", "winkel": "Winkel", "achse": "Achsabstand", "koordinaten": "Koordinaten",
           "pmi": "PMI"}
VOLL = 2 * math.pi - 1e-6


def _z(x: float) -> str:
    return f"{x:.3f}"


def _laenge(kante) -> float:
    p = GProp_GProps()
    brepgprop.LinearProperties(kante, p)
    return p.Mass()


def _inhalt(flaeche) -> float:
    p = GProp_GProps()
    brepgprop.SurfaceProperties(flaeche, p)
    return p.Mass()


def _kante(form) -> list[tuple[str, str]]:
    k = topods.Edge(form)
    if BRep_Tool.Degenerated(k):
        return []
    c = BRepAdaptor_Curve(k)
    typ = c.GetType()
    laenge = _laenge(k)
    if typ == GeomAbs_Circle:
        r = c.Circle().Radius()
        spanne = abs(c.LastParameter() - c.FirstParameter())
        if spanne >= VOLL or BRep_Tool.IsClosed(k):
            return [("art", tr("Kreis")), ("rund", f"⌀ {_z(2 * r)}"), ("laenge", tr("Umfang {}").format(_z(laenge)))]
        return [("art", tr("Bogen")), ("rund", f"R {_z(r)}"),
                ("winkel", f"{math.degrees(spanne):.2f}°"), ("laenge", tr("Bogenlänge {}").format(_z(laenge)))]
    if typ == GeomAbs_Line:
        return [("art", tr("Gerade")), ("laenge", tr("Länge {}").format(_z(laenge)))]
    if typ == GeomAbs_Ellipse:
        e = c.Ellipse()
        return [("art", tr("Ellipse")), ("rund", f"a {_z(e.MajorRadius())}  b {_z(e.MinorRadius())}"),
                ("laenge", tr("Länge {}").format(_z(laenge)))]
    return [("art", tr("Kante")), ("laenge", tr("Länge {}").format(_z(laenge)))]


def _flaeche(form) -> list[tuple[str, str]]:
    f = topods.Face(form)
    if BRep_Tool.Surface(f) is None:
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        n = tri.NbTriangles() if tri is not None else 0
        return [("art", tr("Netz")), ("flaeche", tr("{} Dreiecke").format(n)),
                ("flaeche", tr("Fläche {} mm²").format(f"{_inhalt(f):.2f}"))]
    s = BRepAdaptor_Surface(f, True)
    typ = s.GetType()
    out = [("art", tr(art_von(f)))]
    umin, umax, _, _ = breptools.UVBounds(f)
    geschlossen = (umax - umin) >= VOLL
    if typ == GeomAbs_Cylinder:
        r = s.Cylinder().Radius()
        out.append(("rund", f"⌀ {_z(2 * r)}" if geschlossen else f"R {_z(r)}"))
    elif typ == GeomAbs_Sphere:
        out.append(("rund", f"S⌀ {_z(2 * s.Sphere().Radius())}"))
    elif typ == GeomAbs_Cone:
        out.append(("winkel", tr("Kegelwinkel {:.2f}°").format(2 * math.degrees(abs(s.Cone().SemiAngle())))))
    elif typ == GeomAbs_Torus:
        t = s.Torus()
        out.append(("rund", f"R {_z(t.MajorRadius())} / r {_z(t.MinorRadius())}"))
    out.append(("flaeche", tr("Fläche {} mm²").format(f"{_inhalt(f):.2f}")))
    return out


def _achse(form):
    """gp_Ax1 von Zylinder, Kegel, Kreis, Gerade oder None."""
    t = form.ShapeType()
    if t == TopAbs_FACE and BRep_Tool.Surface(topods.Face(form)) is None:
        return None
    if t == TopAbs_FACE:
        s = BRepAdaptor_Surface(topods.Face(form), True)
        if s.GetType() == GeomAbs_Cylinder:
            return s.Cylinder().Axis()
        if s.GetType() == GeomAbs_Cone:
            return s.Cone().Axis()
    if t == TopAbs_EDGE:
        c = BRepAdaptor_Curve(topods.Edge(form))
        if c.GetType() == GeomAbs_Circle:
            return c.Circle().Axis()
        if c.GetType() == GeomAbs_Line:
            from OCC.Core.gp import gp_Ax1
            lin = c.Line()
            return gp_Ax1(lin.Location(), lin.Direction())
    return None


def _ist_ebene(form) -> bool:
    return form.ShapeType() == TopAbs_FACE and BRep_Tool.Surface(topods.Face(form)) is not None and \
        BRepAdaptor_Surface(topods.Face(form), True).GetType() == GeomAbs_Plane


def _zwei(a, b) -> list[tuple[str, str]]:
    from OCC.Core.gp import gp_Lin
    out = []
    ext = BRepExtrema_DistShapeShape(a, b)
    ext.Perform()
    if ext.IsDone() and ext.NbSolution():
        p1, p2 = ext.PointOnShape1(1), ext.PointOnShape2(1)
        out.append(("abstand", tr("Abstand {}").format(_z(ext.Value()))))
        out.append(("abstand", f"dX {_z(p2.X() - p1.X())}  dY {_z(p2.Y() - p1.Y())}  dZ {_z(p2.Z() - p1.Z())}"))
    ra, rb = _richtung(a), _richtung(b)
    if ra is not None and rb is not None:
        w = math.degrees(ra[0].Angle(rb[0]))
        parallel = min(w, 180 - w) < 1e-6
        if _ist_ebene(a) and _ist_ebene(b) and parallel:
            # parallele Ebenen: Abstand senkrecht zur Ebene
            pa = BRepAdaptor_Surface(topods.Face(a), True).Plane()
            q = BRepAdaptor_Surface(topods.Face(b), True).Plane().Location()
            out.append(("abstand", tr("Ebenenabstand {}").format(_z(pa.Distance(q)))))
        elif parallel:
            out.append(("winkel", tr("parallel")))
        else:
            out.append(("winkel", f"{w:.2f}°"))
    xa, xb = _achse(a), _achse(b)
    if xa is not None and xb is not None:
        la, lb = gp_Lin(xa), gp_Lin(xb)
        if la.Direction().IsParallel(lb.Direction(), 1e-6):
            out.append(("achse", tr("Achsabstand {}").format(_z(la.Distance(lb.Location())))))
        else:
            from OCC.Core.Extrema import Extrema_ExtElC
            e = Extrema_ExtElC(la, lb, 1e-9)
            if e.IsDone() and e.NbExt():
                out.append(("achse", tr("Achsabstand {}").format(_z(math.sqrt(min(e.SquareDistance(i)
                                                                          for i in range(1, e.NbExt() + 1)))))))
    return out


def info(formen: list) -> list[tuple[str, str]]:
    """Kennwerte fuer 1 oder 2 gewaehlte Elemente; bei mehr nur Anzahl und Summen."""
    formen = [f for f in formen if f is not None]
    if not formen:
        return []
    try:
        if len(formen) == 1:
            f = formen[0]
            t = f.ShapeType()
            if t == TopAbs_EDGE:
                return _kante(f)
            if t == TopAbs_FACE:
                return _flaeche(f)
            if t == TopAbs_VERTEX:
                p = BRep_Tool.Pnt(topods.Vertex(f))
                return [("art", tr("Punkt")), ("koordinaten", f"X {_z(p.X())}  Y {_z(p.Y())}  Z {_z(p.Z())}")]
            return []
        if len(formen) == 2:
            return [("art", f"{tr(art_von(formen[0]))} – {tr(art_von(formen[1]))}")] + _zwei(*formen)
        out = [("art", tr("{} Elemente").format(len(formen)))]
        kanten = [f for f in formen if f.ShapeType() == TopAbs_EDGE]
        flaechen = [f for f in formen if f.ShapeType() == TopAbs_FACE]
        if kanten:
            out.append(("laenge", tr("Länge Σ {}").format(_z(sum(_laenge(k) for k in kanten)))))
        if flaechen:
            out.append(("flaeche", tr("Fläche Σ {} mm²").format(f"{sum(_inhalt(f) for f in flaechen):.2f}")))
        return out
    except Exception:  # noqa: BLE001 - Schnellinfo darf nie stoeren
        return []


def pmi_info(pmi: list) -> list[tuple[str, str]]:
    """Kurzinfo zu gewaehlter PMI: Art/Merkmal, Wert, Grenzmasse, Bezuege."""
    if not pmi:
        return []
    if len(pmi) > 1:
        return [("pmi", tr("{} PMI gewählt").format(len(pmi)))]
    p = pmi[0]
    teile = [f"{p.nummer}: {tr(p.merkmal())}", p.wert_text()]
    h, m = p.grenzen()
    if h is not None and m is not None:
        teile.append(f"{tr('max')} {h:.4g} / {tr('min')} {m:.4g}")
    if p.bezuege:
        teile.append(tr("Bezüge {}").format(p.bezug_text()))
    return [("pmi", "  ·  ".join(t for t in teile if t))]
