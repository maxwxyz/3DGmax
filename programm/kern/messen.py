"""Messen an B-Rep-Geometrie: Abstand, Winkel, Radius/Durchmesser, Wandstaerke, Koordinaten, Fangpunkte.

Alle Werte in mm bzw. Grad. Ohne Qt nutzbar (Tests, spaeter Berichte).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import BRepGProp_Face
from OCC.Core.GeomAbs import (GeomAbs_Circle, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Plane,
                              GeomAbs_Sphere, GeomAbs_Torus)
from OCC.Core.gp import gp_Dir, gp_Lin, gp_Pnt, gp_Vec
from OCC.Core.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCC.Core.ShapeAnalysis import ShapeAnalysis_Surface
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED, TopAbs_VERTEX
from OCC.Core.TopoDS import topods

ARTEN = ("abstand", "winkel", "radius", "wandstaerke", "koordinaten")
# Woerter, die in Beschreibungen vorkommen (die Oberflaeche uebersetzt sie)
WOERTER = ("Netz", "Netz ohne exakte Fläche", "Ebene", "Zylinder", "Kegel", "Kugel", "Torus", "Fläche", "Gerade", "Kreis", "Kante", "Punkt",
           "Element", "Endpunkt", "Mitte", "Kreismitte", "Gegenfläche", "auf", "Ergänzung")
ELEMENTE_NOETIG = {"abstand": 2, "winkel": 2, "radius": 1, "wandstaerke": 1, "koordinaten": 1}


@dataclass
class Messung:
    art: str
    wert: float
    einheit: str = "mm"
    punkte: list[tuple[float, float, float]] = field(default_factory=list)  # fuer die Anzeige
    elemente: str = ""  # Beschreibung der gewaehlten Elemente
    zusatz: str = ""  # z. B. "Ø 35.000" bei Radius, dx/dy/dz bei Abstand
    nummer: int = 0

    def text(self) -> str:
        if self.art == "koordinaten":
            x, y, z = self.punkte[0]
            return f"X {x:.3f}  Y {y:.3f}  Z {z:.3f}"
        wert = f"{self.wert:.3f}" if self.einheit == "mm" else f"{self.wert:.2f}"
        return f"{wert} {self.einheit}" + (f"  ({self.zusatz})" if self.zusatz else "")


def _p(pnt: gp_Pnt) -> tuple[float, float, float]:
    return (pnt.X(), pnt.Y(), pnt.Z())


def hat_geometrie(form) -> bool:
    """False fuer Netzflaechen (STL, OBJ, glTF, 3MF): nur Dreiecke, keine exakte Flaeche."""
    return form.ShapeType() != TopAbs_FACE or BRep_Tool.Surface(topods.Face(form)) is not None


def art_von(form) -> str:
    """Kurzbeschreibung eines Elements: Ebene, Zylinder, Kreis, Gerade, Punkt ..."""
    t = form.ShapeType()
    if t == TopAbs_FACE and not hat_geometrie(form):
        return "Netz"
    if t == TopAbs_FACE:
        typ = BRepAdaptor_Surface(topods.Face(form)).GetType()
        return {GeomAbs_Plane: "Ebene", GeomAbs_Cylinder: "Zylinder", GeomAbs_Cone: "Kegel",
                GeomAbs_Sphere: "Kugel", GeomAbs_Torus: "Torus"}.get(typ, "Fläche")
    if t == TopAbs_EDGE:
        typ = BRepAdaptor_Curve(topods.Edge(form)).GetType()
        return {GeomAbs_Line: "Gerade", GeomAbs_Circle: "Kreis"}.get(typ, "Kante")
    if t == TopAbs_VERTEX:
        return "Punkt"
    return "Element"


# --- Fang ---

def fangpunkte(form) -> list[tuple[str, gp_Pnt]]:
    """Ausgezeichnete Punkte eines Elements: Endpunkte, Mitte, Kreismitte; Ebene/Zylinder: Mittelpunkt."""
    t = form.ShapeType()
    if t == TopAbs_VERTEX:
        return [("Punkt", BRep_Tool.Pnt(topods.Vertex(form)))]
    if t == TopAbs_EDGE:
        c = BRepAdaptor_Curve(topods.Edge(form))
        a, b = c.FirstParameter(), c.LastParameter()
        out = [("Endpunkt", c.Value(a)), ("Endpunkt", c.Value(b)), ("Mitte", c.Value((a + b) / 2))]
        if c.GetType() == GeomAbs_Circle:
            out.append(("Kreismitte", c.Circle().Location()))
        return out
    return []


def fange(form, punkt: gp_Pnt, toleranz: float) -> tuple[str, gp_Pnt]:
    """Naechster Fangpunkt innerhalb der Toleranz (mm), sonst der Punkt auf dem Element."""
    beste = None
    for art, p in fangpunkte(form):
        d = p.Distance(punkt)
        if d <= toleranz and (beste is None or d < beste[0]):
            beste = (d, art, p)
    if beste:
        return beste[1], beste[2]
    return ("auf " + art_von(form), punkt)


# --- Messungen ---

def abstand(a, b) -> Messung:
    """Kuerzester Abstand zwischen zwei Elementen (Punkte als Vertex uebergeben)."""
    ext = BRepExtrema_DistShapeShape(a, b)
    ext.Perform()
    if not ext.IsDone() or ext.NbSolution() == 0:
        raise ValueError("Abstand nicht berechenbar")
    p1, p2 = ext.PointOnShape1(1), ext.PointOnShape2(1)
    d = ext.Value()
    zusatz = f"dX {p2.X() - p1.X():.3f}  dY {p2.Y() - p1.Y():.3f}  dZ {p2.Z() - p1.Z():.3f}"
    return Messung("abstand", d, "mm", [_p(p1), _p(p2)], f"{art_von(a)} – {art_von(b)}", zusatz)


def punkt_abstand(p1: gp_Pnt, p2: gp_Pnt) -> Messung:
    return abstand(BRepBuilderAPI_MakeVertex(p1).Vertex(), BRepBuilderAPI_MakeVertex(p2).Vertex())


def _richtung(form) -> tuple[gp_Dir, str] | None:
    """Richtung eines Elements: Normale einer Ebene, Achse von Zylinder/Kegel, Richtung einer Geraden."""
    t = form.ShapeType()
    if t == TopAbs_FACE and not hat_geometrie(form):
        return None
    if t == TopAbs_FACE:
        s = BRepAdaptor_Surface(topods.Face(form))
        typ = s.GetType()
        if typ == GeomAbs_Plane:
            n = s.Plane().Axis().Direction()
            if form.Orientation() == TopAbs_REVERSED:
                n.Reverse()
            return n, "Normale"
        if typ == GeomAbs_Cylinder:
            return s.Cylinder().Axis().Direction(), "Achse"
        if typ == GeomAbs_Cone:
            return s.Cone().Axis().Direction(), "Achse"
    if t == TopAbs_EDGE:
        c = BRepAdaptor_Curve(topods.Edge(form))
        if c.GetType() == GeomAbs_Line:
            return c.Line().Direction(), "Richtung"
        if c.GetType() == GeomAbs_Circle:
            return c.Circle().Axis().Direction(), "Achse"
    return None


def winkel(a, b) -> Messung:
    """Winkel zwischen zwei ebenen Flaechen, Achsen oder Geraden (0..180 Grad)."""
    ra, rb = _richtung(a), _richtung(b)
    if ra is None or rb is None:
        raise ValueError("Winkel nur zwischen Ebenen, Achsen und Geraden")
    w = math.degrees(ra[0].Angle(rb[0]))
    zusatz = f"Ergänzung {180 - w:.2f}°"
    mitte = _mittelpunkt(a), _mittelpunkt(b)
    return Messung("winkel", w, "°", [_p(mitte[0]), _p(mitte[1])], f"{art_von(a)} – {art_von(b)}", zusatz)


def radius(form) -> Messung:
    """Radius von Kreis/Bogen, Zylinder, Kegel (am Bezugsradius), Kugel, Torus (kleiner Radius)."""
    t = form.ShapeType()
    if t == TopAbs_EDGE:
        c = BRepAdaptor_Curve(topods.Edge(form))
        if c.GetType() != GeomAbs_Circle:
            raise ValueError("Kante ist kein Kreis")
        k = c.Circle()
        r, mitte = k.Radius(), k.Location()
    elif t == TopAbs_FACE:
        if not hat_geometrie(form):
            raise ValueError("Netz ohne exakte Fläche")
        s = BRepAdaptor_Surface(topods.Face(form))
        typ = s.GetType()
        if typ == GeomAbs_Cylinder:
            r, mitte = s.Cylinder().Radius(), _mittelpunkt(form)
        elif typ == GeomAbs_Sphere:
            r, mitte = s.Sphere().Radius(), s.Sphere().Location()
        elif typ == GeomAbs_Cone:
            r, mitte = s.Cone().RefRadius(), s.Cone().Location()
        elif typ == GeomAbs_Torus:
            r, mitte = s.Torus().MinorRadius(), _mittelpunkt(form)
        else:
            raise ValueError("Fläche ist nicht rund")
    else:
        raise ValueError("Radius nur an Kreisen und runden Flächen")
    return Messung("radius", r, "mm", [_p(mitte)], art_von(form), f"Ø {2 * r:.3f}")


def _mittelpunkt(form) -> gp_Pnt:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    props = GProp_GProps()
    if form.ShapeType() == TopAbs_FACE:
        brepgprop.SurfaceProperties(form, props)
    elif form.ShapeType() == TopAbs_EDGE:
        brepgprop.LinearProperties(form, props)
    else:
        return BRep_Tool.Pnt(topods.Vertex(form))
    return props.CentreOfMass()


def normale_innen(flaeche, punkt: gp_Pnt) -> gp_Dir:
    """Richtung ins Material an einem Punkt der Flaeche (Gegenrichtung der aeusseren Normale)."""
    f = topods.Face(flaeche)
    if BRep_Tool.Surface(f) is None:
        raise ValueError("Netz ohne exakte Fläche")
    sas = ShapeAnalysis_Surface(BRep_Tool.Surface(f))
    uv = sas.ValueOfUV(punkt, 1e-6)
    p, n = gp_Pnt(), gp_Vec()
    BRepGProp_Face(f).Normal(uv.X(), uv.Y(), p, n)
    if n.Magnitude() < 1e-12:
        raise ValueError("Keine Normale an dieser Stelle")
    return gp_Dir(n.Reversed())


def wandstaerke(koerper, flaeche, punkt: gp_Pnt) -> Messung:
    """Abstand von der Stelle auf der Flaeche bis zur naechsten Gegenflaeche ins Material hinein."""
    r = normale_innen(flaeche, punkt)
    schnitt = IntCurvesFace_ShapeIntersector()
    schnitt.Load(koerper, 1e-6)
    schnitt.Perform(gp_Lin(punkt, r), 1e-4, 1e9)
    if not schnitt.IsDone() or schnitt.NbPnt() == 0:
        raise ValueError("Keine Gegenfläche gefunden")
    beste = min(range(1, schnitt.NbPnt() + 1), key=schnitt.WParameter)
    gegen = schnitt.Pnt(beste)
    return Messung("wandstaerke", punkt.Distance(gegen), "mm", [_p(punkt), _p(gegen)],
                   art_von(flaeche) + " → Gegenfläche")


def koordinaten(punkt: gp_Pnt, beschreibung: str = "") -> Messung:
    return Messung("koordinaten", 0.0, "mm", [_p(punkt)], beschreibung)


def als_csv(messungen: list[Messung]) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow(["Nr", "Art", "Wert", "Einheit", "Zusatz", "Elemente", "Punkte"])
    for m in messungen:
        punkte = " | ".join(f"{x:.4f}, {y:.4f}, {z:.4f}" for x, y, z in m.punkte)
        wert = "" if m.art == "koordinaten" else f"{m.wert:.4f}".replace(".", ",")
        w.writerow([m.nummer, m.art, wert, m.einheit, m.zusatz, m.elemente, punkte])
    return puffer.getvalue()
