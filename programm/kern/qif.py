"""QIF 3.0 (Quality Information Framework, ANSI/DMSC) lesen: exakte B-Rep und semantische PMI.

Geometrie: Flaechen (Plane23, Cylinder23, Cone23, Sphere23, Torus23, Nurbs23) mit Kanten aus den 3D-Kurven
(Segment13, ArcCircular13, ArcConic13, Nurbs13, Aggregate13); Flaechen werden je Schleife begrenzt, die Parameterkurven
ergaenzt ShapeFix, Naehen verbindet die Flaechen. Laengen in mm (Primaereinheit der Datei umgerechnet).
PMI: CharacteristicNominals/Definitions (Masse, Form- und Lagetoleranzen), Bezuege und Bezugssysteme; die Verknuepfung
zu den Flaechen kommt ueber die FeatureNominals (EntityInternalIds = Flaechen-IDs).
"""

from __future__ import annotations

import math

import numpy as np
from lxml import etree

from .pmi import BEZUG, BezugsRef, HINWEIS, MASS, TOLERANZ, Pmi

NS = "{http://qifstandards.org/xsd/qif3}"


def _k(e) -> str:
    return e.tag.replace(NS, "") if isinstance(e.tag, str) else ""


def _p(pfad: str) -> str:
    return "/".join(NS + teil for teil in pfad.split("/"))


def _zahlen(text: str) -> list[float]:
    return [float(x) for x in text.split()] if text else []


def _vec(e, pfad, faktor=1.0):
    x = e.find(_p(pfad))
    return None if x is None else np.array(_zahlen(x.text)) * faktor


# --- Einheiten ---

def _faktor(wurzel) -> float:
    """Faktor Datei-Laengeneinheit -> mm."""
    lu = wurzel.find(_p("FileUnits/PrimaryUnits/LinearUnit"))
    if lu is None:
        return 1.0
    f = lu.find(_p("UnitConversion/Factor"))
    return float(f.text) * 1000.0 if f is not None else 1000.0 if (lu.findtext(_p("UnitName")) or "") in ("m",
                                                                                                         "meter") else 1.0


# --- Geometrie ---

def _ax2(p, d, x=None):
    from OCC.Core.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt
    if x is not None:
        xs = np.asarray(x, float)
        xs = xs - np.asarray(d) * (xs @ np.asarray(d) / max(np.dot(d, d), 1e-30))
        if np.linalg.norm(xs) > 1e-9:
            return gp_Ax3(gp_Pnt(*p), gp_Dir(*d), gp_Dir(*xs)), gp_Ax2(gp_Pnt(*p), gp_Dir(*d), gp_Dir(*xs))
    return gp_Ax3(gp_Pnt(*p), gp_Dir(*d)), gp_Ax2(gp_Pnt(*p), gp_Dir(*d))


def _knoten(knots: list[float]):
    """Volle Knotenfolge -> (eindeutige Knoten, Vielfachheiten)."""
    werte, mult = [], []
    for k in knots:
        if werte and abs(k - werte[-1]) <= 1e-12 * max(1.0, abs(k)):
            mult[-1] += 1
        else:
            werte.append(k)
            mult.append(1)
    return werte, mult


def _arrays(werte, mult):
    from OCC.Core.TColStd import TColStd_Array1OfInteger, TColStd_Array1OfReal
    w, m = TColStd_Array1OfReal(1, len(werte)), TColStd_Array1OfInteger(1, len(mult))
    for i, (a, b) in enumerate(zip(werte, mult), 1):
        w.SetValue(i, float(a))
        m.SetValue(i, int(b))
    return w, m


def flaeche(e, f: float):
    """QIF-Flaeche -> Geom_Surface."""
    from OCC.Core.Geom import (Geom_BSplineSurface, Geom_ConicalSurface, Geom_CylindricalSurface, Geom_Plane,
                               Geom_SphericalSurface, Geom_ToroidalSurface)
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_Array2OfPnt
    from OCC.Core.TColStd import TColStd_Array2OfReal
    art = _k(e)
    c = e[0] if len(e) else e
    if art == "Plane23":
        u, v = _vec(c, "DirU"), _vec(c, "DirV")
        return Geom_Plane(_ax2(_vec(c, "Origin", f), np.cross(u, v), u)[0])
    if art in ("Cylinder23", "Cone23", "Torus23"):
        ax = c.find(_p("Axis"))
        p, d = _vec(ax, "AxisPoint", f), _vec(ax, "Direction")
        x = _vec(c, "Sweep/DirBeg")
        if x is None:
            x = _vec(c, "LatitudeLongitudeSweep/DirMeridianPrime")
        a3 = _ax2(p, d, x)[0]
        if art == "Cylinder23":
            return Geom_CylindricalSurface(a3, float(c.findtext(_p("Diameter"))) * f / 2)
        if art == "Torus23":
            return Geom_ToroidalSurface(a3, float(c.findtext(_p("DiameterMajor"))) * f / 2,
                                        float(c.findtext(_p("DiameterMinor"))) * f / 2)
        db, dt = float(c.findtext(_p("DiameterBottom"))) * f, float(c.findtext(_p("DiameterTop"))) * f
        laenge = float(c.findtext(_p("Length"))) * f
        winkel = math.atan2((dt - db) / 2, laenge)
        if abs(winkel) < 1e-12:
            return Geom_CylindricalSurface(a3, db / 2)
        return Geom_ConicalSurface(a3, winkel, db / 2)
    if art == "Sphere23":
        d = _vec(c, "LatitudeLongitudeSweep/DirNorthPole")
        x = _vec(c, "LatitudeLongitudeSweep/DirMeridianPrime")
        a3 = _ax2(_vec(c, "Location", f), d if d is not None else np.array([0, 0, 1.0]), x)[0]
        return Geom_SphericalSurface(a3, float(c.findtext(_p("Diameter"))) * f / 2)
    if art == "Nurbs23":
        ou, ov = int(c.findtext(_p("OrderU"))), int(c.findtext(_p("OrderV")))
        ku, kv = _zahlen(c.findtext(_p("KnotsU"))), _zahlen(c.findtext(_p("KnotsV")))
        nu, nv = len(ku) - ou, len(kv) - ov
        pts = np.array(_zahlen(c.findtext(_p("CPs")))).reshape(-1, 3) * f
        gew = _zahlen(c.findtext(_p("Weights")) or "")
        pole = TColgp_Array2OfPnt(1, nu, 1, nv)
        wa = TColStd_Array2OfReal(1, nu, 1, nv)
        for j in range(nv):  # QIF: U laeuft am schnellsten
            for i in range(nu):
                k = j * nu + i
                pole.SetValue(i + 1, j + 1, gp_Pnt(*pts[k]))
                wa.SetValue(i + 1, j + 1, gew[k] if gew else 1.0)
        (uk, um), (vk, vm) = _knoten(ku), _knoten(kv)
        uka, uma = _arrays(uk, um)
        vka, vma = _arrays(vk, vm)
        if gew:
            return Geom_BSplineSurface(pole, wa, uka, vka, uma, vma, ou - 1, ov - 1)
        return Geom_BSplineSurface(pole, uka, vka, uma, vma, ou - 1, ov - 1)
    raise ValueError(f"QIF-Flaeche nicht unterstuetzt: {art}")


def _kurve_kern(c, art: str, f: float):
    """Kern einer 3D-Kurve -> (Geom_Curve, u0, u1)."""
    from OCC.Core.Geom import Geom_BSplineCurve, Geom_Circle, Geom_Ellipse
    from OCC.Core.GC import GC_MakeSegment
    from OCC.Core.gp import gp_Circ, gp_Elips, gp_Pnt
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.TColStd import TColStd_Array1OfReal
    dom = _zahlen(c.get("domain", "0 1"))
    if art == "Segment13":
        a, b = _vec(c, "StartPoint", f), _vec(c, "EndPoint", f)
        # Parameter 0..1 laeuft von Start- zu Endpunkt; die Kante nutzt oft nur einen Teil davon
        a, b = a + dom[0] * (b - a), a + dom[1] * (b - a)
        seg = GC_MakeSegment(gp_Pnt(*a), gp_Pnt(*b)).Value()
        return seg, seg.FirstParameter(), seg.LastParameter()
    if art == "ArcCircular13":
        a2 = _ax2(_vec(c, "Center", f), _vec(c, "Normal"), _vec(c, "DirBeg"))[1]
        return Geom_Circle(gp_Circ(a2, float(c.findtext(_p("Radius"))) * f)), dom[0], dom[1]
    if art == "ArcConic13":
        if c.get("form", "ELLIPSE") != "ELLIPSE":
            raise ValueError("Kegelschnitt nicht unterstuetzt")
        a2 = _ax2(_vec(c, "Center", f), _vec(c, "Normal"), _vec(c, "DirBeg"))[1]
        ga, gb = float(c.findtext(_p("A"))) * f, float(c.findtext(_p("B"))) * f
        if gb > ga:  # OCCT verlangt grosse Halbachse zuerst: um 90 Grad drehen
            from OCC.Core.gp import gp_Ax1
            a2 = a2.Rotated(gp_Ax1(a2.Location(), a2.Direction()), math.pi / 2)
            ga, gb = gb, ga
            dom = [dom[0] - math.pi / 2, dom[1] - math.pi / 2]
        return Geom_Ellipse(gp_Elips(a2, ga, gb)), dom[0], dom[1]
    if art == "Nurbs13":
        ordnung = int(c.findtext(_p("Order")))
        knots = _zahlen(c.findtext(_p("Knots")))
        pts = np.array(_zahlen(c.findtext(_p("CPs")))).reshape(-1, 3) * f
        gew = _zahlen(c.findtext(_p("Weights")) or "")
        pole = TColgp_Array1OfPnt(1, len(pts))
        for i, q in enumerate(pts, 1):
            pole.SetValue(i, gp_Pnt(*q))
        kk, km = _arrays(*_knoten(knots))
        if gew:
            wa = TColStd_Array1OfReal(1, len(gew))
            for i, w in enumerate(gew, 1):
                wa.SetValue(i, w)
            kurve = Geom_BSplineCurve(pole, wa, kk, km, ordnung - 1)
        else:
            kurve = Geom_BSplineCurve(pole, kk, km, ordnung - 1)
        u0, u1 = max(dom[0], kurve.FirstParameter()), min(dom[1], kurve.LastParameter())
        return kurve, u0, u1
    raise ValueError(f"QIF-Kurve nicht unterstuetzt: {art}")


def kurven(e, f: float) -> list:
    """QIF-3D-Kurve -> Liste von (Geom_Curve, u0, u1); Aggregate werden in Teilkurven zerlegt."""
    art = _k(e)
    if art == "Aggregate13":
        out = []
        for sub in e.iter(NS + "SubCurve"):
            kern = sub[0]
            teil = _kurve_kern(kern, _k(kern).replace("Core", ""), f)
            if sub.get("turned") == "true":
                kurve, u0, u1 = teil
                umgedreht = kurve.Reversed()
                teil = (umgedreht, umgedreht.ReversedParameter(u1), umgedreht.ReversedParameter(u0))
            out.append(teil)
        return out
    return [_kurve_kern(e[0], art, f)]


class QifDokument:
    def __init__(self, pfad: str):
        self.pfad = pfad
        self.wurzel = etree.parse(pfad, etree.XMLParser(resolve_entities=False, no_network=True,
                                                        huge_tree=True)).getroot()
        self.faktor = _faktor(self.wurzel)
        self.ids: dict[str, object] = {}
        for e in self.wurzel.iter():
            i = e.get("id") if isinstance(e.tag, str) else None
            if i is not None:
                self.ids[i] = e

    def laenge(self, e) -> float | None:
        """Laengenwert in mm; die Einheit steht am Wert (linearUnit), sonst gilt die Primaereinheit."""
        if e is None or e.text is None:
            return None
        einheit = e.get("linearUnit")
        k = EINHEITEN.get(einheit.lower(), self.faktor) if einheit else self.faktor
        return float(e.text) * k

    def ref(self, e, pfad: str):
        x = e.find(_p(pfad))
        return None if x is None or x.text is None else self.ids.get(x.text.strip())

    # --- B-Rep ---

    def baue_form(self):
        """Alle Koerper als OCCT-Form; Rueckgabe (form, {QIF-Flaechen-ID: TopoDS_Face}, Namen je Koerper)."""
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing
        from OCC.Core.ShapeExtend import ShapeExtend_WireData
        from OCC.Core.ShapeFix import ShapeFix_Wire
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopoDS import topods
        f = self.faktor
        kanten: dict[str, list] = {}
        flaechen: dict[str, object] = {}
        fehler = 0
        for kante in self.wurzel.iter(NS + "Edge"):
            kurve = self.ref(kante, "Curve/Id")
            if kurve is None:
                continue
            try:
                kanten[kante.get("id")] = [BRepBuilderAPI_MakeEdge(c, u0, u1).Edge() for c, u0, u1 in kurven(kurve, f)]
            except Exception:  # noqa: BLE001 - einzelne Kante auslassen, Naehen/ShapeFix fangen Luecken
                fehler += 1
        for fl in self.wurzel.iter(NS + "Face"):
            if fl.getparent() is None or _k(fl.getparent()) != "FaceSet":
                continue
            fid = fl.get("id")
            try:
                geom = flaeche(self.ref(fl, "Surface/Id"), f)
            except Exception:  # noqa: BLE001
                fehler += 1
                continue
            draehte = []
            for lid in fl.iter(NS + "Id"):
                if _k(lid.getparent()) != "LoopIds":
                    continue
                schleife = self.ids.get(lid.text.strip())
                if schleife is None:
                    continue
                daten = ShapeExtend_WireData()
                for co in schleife.iter(NS + "CoEdge"):
                    ori = co.find(_p("EdgeOriented"))
                    teile = kanten.get(ori.findtext(_p("Id")).strip(), [])
                    if ori.get("turned") == "true":
                        teile = [t.Reversed() for t in reversed(teile)]
                    for t in teile:
                        daten.Add(topods.Edge(t))
                if daten.NbEdges():
                    # Kantenenden liegen nicht immer exakt aufeinander: ShapeFix verbindet sie
                    roh = BRepBuilderAPI_MakeFace(geom, 1e-6).Face()
                    fw = ShapeFix_Wire()
                    fw.Load(daten)
                    fw.SetFace(roh)
                    fw.SetPrecision(1e-4 * max(f, 1.0))
                    fw.FixConnected()
                    fw.FixClosed()
                    draht = fw.WireAPIMake()
                    if not draht.IsNull():
                        draehte.append((schleife.get("form", "OUTER"), draht))
            aussen = [d for art, d in draehte if art == "OUTER"] or [d for _, d in draehte[:1]]
            if aussen:
                mf = BRepBuilderAPI_MakeFace(geom, aussen[0], True)
                for art, d in draehte:
                    if d is not aussen[0]:
                        mf.Add(d)
            else:
                mf = BRepBuilderAPI_MakeFace(geom, 1e-6)
            if not mf.IsDone():
                fehler += 1
                continue
            flaeche_neu = _repariere(mf.Face())
            if not _gut(flaeche_neu) and draehte:
                # Schleifen gegen die Flaechenrichtung: mit umgedrehten Draehten neu aufbauen
                umgedreht = BRepBuilderAPI_MakeFace(geom, aussen[0].Reversed(), True) if aussen else None
                if umgedreht is not None and umgedreht.IsDone():
                    for art, d in draehte:
                        if d is not aussen[0]:
                            umgedreht.Add(d.Reversed())
                    zweite = _repariere(umgedreht.Face())
                    if _gut(zweite):
                        flaeche_neu = zweite
            flaechen[fid] = flaeche_neu
        naht = BRepBuilderAPI_Sewing(1e-3 * f if f > 1 else 1e-3)
        for fl in flaechen.values():
            naht.Add(fl)
        zuordnung = {}
        try:
            naht.Perform()
            form = naht.SewedShape()
            # QIF-ID -> Flaeche im genaehten Ergebnis (Naehen ersetzt Flaechen durch neue)
            for fid, fl in flaechen.items():
                zuordnung[fid] = topods.Face(naht.Modified(fl)) if naht.IsModified(fl) else fl
        except Exception:  # noqa: BLE001 - Naehen gescheitert: Flaechen einzeln (ohne gemeinsame Kanten)
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.TopoDS import TopoDS_Compound
            form = TopoDS_Compound()
            bb = BRep_Builder()
            bb.MakeCompound(form)
            for fid, fl in flaechen.items():
                bb.Add(form, fl)
                zuordnung[fid] = fl
        self.fehler = fehler
        self.anzahl_flaechen = sum(1 for _ in _alle(form, TopAbs_FACE, TopExp_Explorer))
        return form, zuordnung

    # --- PMI ---

    def merkmale(self, flaeche_index) -> list[Pmi]:
        """Semantische PMI; flaeche_index(qif_flaechen_id) -> Index im Modell oder None."""
        bezug_namen = {}
        out = []
        for d in self.wurzel.iter(NS + "DatumDefinition"):
            name = d.findtext(_p("DatumLabel")) or "?"
            bezug_namen[d.get("id")] = name
            out.append(Pmi(BEZUG, "Datum", name, flaechen=self._flaechen(d, flaeche_index), quelle="qif",
                           step_id=int(d.get("id"))))
        drf = {}
        for r in self.wurzel.iter(NS + "DatumReferenceFrame"):
            refs = []
            for dat in r.iter(NS + "Datum"):
                stelle = {"PRIMARY": 1, "SECONDARY": 2, "TERTIARY": 3}.get(dat.findtext(_p("Precedence/PrecedenceEnum")),
                                                                         len(refs) + 1)
                namen = [bezug_namen.get(x.text.strip(), "?") for x in dat.iter(NS + "DatumDefinitionId")]
                mods = [m.text for m in dat.iter(NS + "MaterialModifier") if m.text and m.text != "NONE"]
                refs.append(BezugsRef("-".join(namen), stelle, ["MaximumMaterialRequirement" if m == "MAXIMUM" else
                                                                "LeastMaterialRequirement" for m in mods]))
            drf[r.get("id")] = refs
        nominale = self.wurzel.find(_p("Characteristics/CharacteristicNominals"))
        for n in (nominale if nominale is not None else []):
            art = _k(n).replace("CharacteristicNominal", "")
            definition = self.ids.get((n.findtext(_p("CharacteristicDefinitionId")) or "").strip())
            if definition is None or art not in QIF_ARTEN:
                continue
            pmi_art, typ = QIF_ARTEN[art]
            p = Pmi(pmi_art, typ, n.findtext(_p("Name")) or art, quelle="qif", step_id=int(n.get("id")),
                    flaechen=self._flaechen(n, flaeche_index))
            winkel = typ in WINKEL
            wert_von = (lambda x: None if x is None or x.text is None else float(x.text)) if winkel else self.laenge
            if pmi_art == MASS:
                ziel = n.find(_p("TargetValue"))
                if ziel is not None:
                    p.nennwert = wert_von(ziel)
                    if ziel.get("decimalPlaces"):
                        p.dezimalen = int(ziel.get("decimalPlaces"))
                tol = definition.find(_p("Tolerance"))
                if tol is not None:
                    p.oben = wert_von(tol.find(_p("MaxValue")))
                    p.unten = wert_von(tol.find(_p("MinValue")))
                    p.grenzmass = (tol.findtext(_p("DefinedAsLimit")) or "false") == "true"
            else:
                p.wert = self.laenge(definition.find(_p("ToleranceValue")))
                mat = definition.findtext(_p("MaterialCondition")) or "NONE"
                p.material = {"MAXIMUM": "M", "LEAST": "L"}.get(mat, "")
                if definition.find(_p("ZoneShape/DiametricalZone")) is not None:
                    p.modifikatoren.append("Diameter")
                ref = definition.findtext(_p("DatumReferenceFrameId"))
                if ref:
                    p.bezuege = list(drf.get(ref.strip(), []))
            out.append(p)
        for note in self.wurzel.iter(NS + "Note"):
            text = note.findtext(_p("NoteText")) or note.findtext(_p("NoteText/Text")) or ""
            if text.strip():
                out.append(Pmi(HINWEIS, "Note", note.findtext(_p("Name")) or "Note", nur_grafik_text=text.strip(),
                               quelle="qif", step_id=int(note.get("id")), semantisch=False))
        bezuege = [p for p in out if p.art == BEZUG]
        rest = [p for p in out if p.art != BEZUG]
        liste = rest + bezuege  # wie bei STEP: Masse/Toleranzen zuerst, Bezuege danach
        for i, p in enumerate(liste, 1):
            p.nummer = i
        return liste

    def _flaechen(self, e, flaeche_index) -> set[int]:
        out = set()
        for fid in e.iter(NS + "Id"):
            if _k(fid.getparent()) != "FeatureNominalIds":
                continue
            feat = self.ids.get(fid.text.strip())
            if feat is None:
                continue
            for ent in feat.iter(NS + "Id"):
                if _k(ent.getparent()) == "EntityInternalIds":
                    idx = flaeche_index(ent.text.strip())
                    if idx is not None:
                        out.add(idx)
        return out

    def norm_text(self) -> str:
        teile = []
        for s in self.wurzel.iter(NS + "Standard"):
            teile.append(f"{s.findtext(_p('Organization/StandardsOrganizationEnum')) or ''} "
                         f"{s.findtext(_p('Designator')) or ''}".strip())
        return "; ".join(t for t in teile if t)


WINKEL = {"Location_Angular", "Size_Angular"}
EINHEITEN = {"mm": 1.0, "millimeter": 1.0, "cm": 10.0, "m": 1000.0, "meter": 1000.0, "inch": 25.4, "in": 25.4,
             "ft": 304.8, "micron": 0.001, "um": 0.001}
QIF_ARTEN = {
    "Diameter": (MASS, "Size_Diameter"), "Radius": (MASS, "Size_Radius"),
    "SphericalDiameter": (MASS, "Size_SphericalDiameter"), "SphericalRadius": (MASS, "Size_SphericalRadius"),
    "Length": (MASS, "Size_CurveLength"), "Width": (MASS, "Size_Thickness"), "Height": (MASS, "Size_Thickness"),
    "Depth": (MASS, "Size_Thickness"), "Thickness": (MASS, "Size_Thickness"),
    "DistanceBetween": (MASS, "Location_LinearDistance"), "DistanceFrom": (MASS, "Location_LinearDistance"),
    "Angle": (MASS, "Size_Angular"), "AngleBetween": (MASS, "Location_Angular"), "AngleFrom": (MASS, "Location_Angular"),
    "Position": (TOLERANZ, "Position"), "SurfaceProfile": (TOLERANZ, "ProfileOfSurface"),
    "LineProfile": (TOLERANZ, "ProfileOfLine"), "Flatness": (TOLERANZ, "Flatness"),
    "Straightness": (TOLERANZ, "Straightness"), "Circularity": (TOLERANZ, "CircularityOrRoundness"),
    "Cylindricity": (TOLERANZ, "Cylindricity"), "Perpendicularity": (TOLERANZ, "Perpendicularity"),
    "Parallelism": (TOLERANZ, "Parallelism"), "Angularity": (TOLERANZ, "Angularity"),
    "Concentricity": (TOLERANZ, "Concentricity"), "Symmetry": (TOLERANZ, "Symmetry"),
    "CircularRunout": (TOLERANZ, "CircularRunout"), "TotalRunout": (TOLERANZ, "TotalRunout"),
}


def _repariere(flaeche):
    from OCC.Core.ShapeFix import ShapeFix_Face
    fix = ShapeFix_Face(flaeche)
    fix.Perform()
    return fix.Face()


def _gut(flaeche) -> bool:
    """Flaeche mit positivem Inhalt und erfolgreich vernetzt (sonst sind die Schleifen falsch orientiert)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopLoc import TopLoc_Location
    g = GProp_GProps()
    brepgprop.SurfaceProperties(flaeche, g)
    if g.Mass() <= 0:
        return False
    BRepMesh_IncrementalMesh(flaeche, 0.1, False, 0.5, True)
    tri = BRep_Tool.Triangulation(flaeche, TopLoc_Location())
    return tri is not None and tri.NbTriangles() > 0


def _alle(form, art, explorer):
    ex = explorer(form, art)
    while ex.More():
        yield ex.Current()
        ex.Next()


def _zuordnen(flaechen: dict, form) -> dict:
    """QIF-Flaechen-ID -> Flaeche in 'form' (Naehen erzeugt neue Flaechen): gleicher Schwerpunkt und Inhalt."""
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from scipy.spatial import cKDTree

    def kennung(fl):
        g = GProp_GProps()
        brepgprop.SurfaceProperties(fl, g)
        c = g.CentreOfMass()
        return (c.X(), c.Y(), c.Z()), g.Mass()

    ziel = list(_alle(form, TopAbs_FACE, TopExp_Explorer))
    if not ziel:
        return {}
    werte = [kennung(z) for z in ziel]
    baum = cKDTree(np.array([w[0] for w in werte]))
    out = {}
    for fid, fl in flaechen.items():
        c, a = kennung(fl)
        d, i = baum.query(c, k=min(4, len(ziel)))
        for dj, ij in zip(np.atleast_1d(d), np.atleast_1d(i)):
            if dj < 1e-3 * max(1.0, math.sqrt(abs(a))) and abs(werte[ij][1] - a) <= 1e-3 * max(1.0, abs(a)):
                out[fid] = ziel[ij]
                break
    return out
