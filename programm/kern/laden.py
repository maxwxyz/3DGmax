"""STEP-Datei in ein XCAF-Dokument laden und Flaechen eindeutig nummerieren.

Ergebnis ist ein StepModell mit
- doc/shape_tool (XCAF, inkl. PMI und gespeicherten Ansichten),
- form (alle freien Formen als Compound),
- flaechen (Index 0..n-1, stabile Nummer innerhalb eines geladenen Modells),
- Zuordnung STEP-#ID <-> Flaechenindex (fuer PMI-Ergaenzung aus der Datei).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from OCC.Core.BRep import BRep_Builder, BRep_Tool
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.StepData import StepData_StepModel
from OCC.Core.TDF import TDF_LabelSequence
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Shape, topods
from OCC.Core.TransferBRep import transferbrep
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

from . import p21


class LadeFehler(Exception):
    pass


@dataclass
class StepModell:
    pfad: str
    doc: TDocStd_Document
    shape_tool: object
    form: TopoDS_Shape
    flaechen: list = field(default_factory=list)
    step_zu_flaeche: dict[int, int] = field(default_factory=dict)
    flaeche_zu_step: dict[int, int] = field(default_factory=dict)
    datei: p21.P21Datei | None = None
    ladezeit: float = 0.0

    def flaechen_index(self, face) -> int | None:
        """Index einer Flaeche (Lage wird ignoriert), None wenn unbekannt."""
        return self._index.get(_schluessel(face))

    def form_von_step(self, eid: int):
        """OCCT-Form, in die eine STEP-Entitaet uebertragen wurde (oder None)."""
        ws = self._reader.ChangeReader().WS()
        num = ws.NumberFromLabel(f"#{eid}")
        if num <= 0:
            return None
        sh = transferbrep.ShapeResult(ws.TransferReader().TransientProcess(), ws.Model().Value(num))
        return None if sh is None or sh.IsNull() else sh

    def _baue_index(self):
        self._index = {_schluessel(f): i for i, f in enumerate(self.flaechen)}


def _schluessel(shape) -> int:
    # Gleiche TShape + Orientierung egal + Lage egal -> gleicher Schluessel
    return shape.Located(TopLoc_Location()).Oriented(0).__hash__()


def _neuer_reader() -> STEPCAFControl_Reader:
    r = STEPCAFControl_Reader()
    for modus in ("SetColorMode", "SetNameMode", "SetLayerMode", "SetGDTMode",
                  "SetViewMode", "SetPropsMode", "SetSHUOMode", "SetMatMode"):
        getattr(r, modus)(True)
    return r


def _freie_formen(shape_tool) -> TopoDS_Shape:
    seq = TDF_LabelSequence()
    shape_tool.GetFreeShapes(seq)
    comp = TopoDS_Compound()
    bb = BRep_Builder()
    bb.MakeCompound(comp)
    for i in range(1, seq.Length() + 1):
        bb.Add(comp, shape_tool.GetShape(seq.Value(i)))
    return comp


def _alle_flaechen(form) -> list:
    """Flaechen in Durchlaufreihenfolge, jede TShape nur einmal."""
    gesehen, out = set(), []
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        k = _schluessel(f)
        if k not in gesehen:
            gesehen.add(k)
            out.append(f)
        ex.Next()
    return out


def _step_flaechen(reader, datei: p21.P21Datei, modell: StepModell):
    """Verknuepft ADVANCED_FACE-#IDs der Datei mit den Flaechenindizes."""
    ws = reader.ChangeReader().WS()
    model = ws.Model()
    tp = ws.TransferReader().TransientProcess()
    for ent in datei.of_type("ADVANCED_FACE") + datei.of_type("FACE_SURFACE"):
        num = ws.NumberFromLabel(f"#{ent.id}")
        if num <= 0:
            continue
        sh = transferbrep.ShapeResult(tp, model.Value(num))
        if sh.IsNull():
            continue
        idx = modell.flaechen_index(sh)
        if idx is not None:
            modell.step_zu_flaeche[ent.id] = idx
            modell.flaeche_zu_step.setdefault(idx, ent.id)


def lade_step(pfad: str) -> StepModell:
    t0 = time.perf_counter()
    reader = _neuer_reader()
    if reader.ReadFile(pfad) != IFSelect_RetDone:
        raise LadeFehler(f"STEP-Datei nicht lesbar: {pfad}")
    doc = TDocStd_Document("XmlXCAF")
    if not reader.Transfer(doc):
        raise LadeFehler(f"Uebertragung fehlgeschlagen: {pfad}")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    form = _freie_formen(st)
    modell = StepModell(pfad, doc, st, form, _alle_flaechen(form))
    modell._baue_index()
    modell._reader = reader
    modell.datei = p21.lese(pfad)
    _step_flaechen(reader, modell.datei, modell)
    modell.ladezeit = time.perf_counter() - t0
    return modell


def step_ident(reader, ent) -> int:
    """#ID einer Entitaet des OCCT-Modells (fuer Fehlersuche)."""
    model = StepData_StepModel.DownCast(reader.ChangeReader().WS().Model())
    return model.IdentLabel(ent)


# --- weitere Formate (ohne PMI) ---

ENDUNGEN_STEP = (".stp", ".step", ".p21")
ENDUNGEN_IGES = (".igs", ".iges")
ENDUNGEN_NETZ = (".stl", ".obj", ".gltf", ".glb", ".3mf")
ENDUNGEN = ENDUNGEN_STEP + ENDUNGEN_IGES + ENDUNGEN_NETZ


def _modell_aus_doc(pfad: str, doc, t0: float) -> StepModell:
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    form = _freie_formen(st)
    modell = StepModell(pfad, doc, st, form, _alle_flaechen(form))
    modell._baue_index()
    modell._reader = None
    if not modell.flaechen:
        raise LadeFehler(f"Keine Flächen in der Datei: {pfad}")
    modell.ladezeit = time.perf_counter() - t0
    return modell


def _netz_flaeche(tri, name: str, doc):
    """Dreiecksnetz als Flaeche ohne Geometrie (nur Triangulation) ins Dokument legen."""
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TopoDS import TopoDS_Face
    flaeche = TopoDS_Face()
    BRep_Builder().MakeFace(flaeche, tri)
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    lab = st.AddShape(flaeche, False)
    TDataStd_Name.Set(lab, TCollection_ExtendedString(name, True))
    return lab


def _poly(punkte, dreiecke):
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.Poly import Poly_Triangle, Poly_Triangulation
    tri = Poly_Triangulation(len(punkte), len(dreiecke), False)
    for i, p in enumerate(punkte, 1):
        tri.SetNode(i, gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
    for i, (a, b, c) in enumerate(dreiecke, 1):
        tri.SetTriangle(i, Poly_Triangle(int(a) + 1, int(b) + 1, int(c) + 1))
    return tri


def _lies_3mf(pfad: str, doc):
    """3MF (ZIP mit 3D/3dmodel.model): Objekte mit Netzen, Bauteile mit Transformation, Einheit -> mm."""
    import zipfile
    import numpy as np
    from lxml import etree
    faktor = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0, "inch": 25.4, "foot": 304.8, "meter": 1000.0}
    with zipfile.ZipFile(pfad) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(".model")), None)
        if name is None:
            raise LadeFehler(f"Kein 3D-Modell in der 3MF-Datei: {pfad}")
        wurzel = etree.fromstring(z.read(name), etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {"m": wurzel.nsmap.get(None, "http://schemas.microsoft.com/3dmanufacturing/core/2015/02")}
    f = faktor.get(wurzel.get("unit", "millimeter"), 1.0)
    objekte = {}
    for obj in wurzel.iterfind(".//m:resources/m:object", ns):
        netz = obj.find("m:mesh", ns)
        if netz is None:
            continue
        pts = np.array([[float(v.get(a)) for a in "xyz"] for v in netz.iterfind("m:vertices/m:vertex", ns)]) * f
        tri = [[int(t.get(a)) for a in ("v1", "v2", "v3")] for t in netz.iterfind("m:triangles/m:triangle", ns)]
        objekte[obj.get("id")] = (obj.get("name") or f"Objekt {obj.get('id')}", pts, tri)
    teile = wurzel.findall(".//m:build/m:item", ns) or [None]
    for item in teile:
        ids = [item.get("objectid")] if item is not None else list(objekte)
        for oid in ids:
            if oid not in objekte:
                continue
            name, pts, tri = objekte[oid]
            if item is not None and item.get("transform"):
                # 3MF: Zeilenvektor-Konvention, 4x3-Matrix m00 m01 m02 m10 .. m32
                m = [float(x) for x in item.get("transform").split()]
                if len(m) == 12:
                    pts = pts @ np.array(m[:9]).reshape(3, 3) + np.array(m[9:12]) * f
            _netz_flaeche(_poly(pts, tri), name, doc)


def lade_modell(pfad: str) -> StepModell:
    """Modell nach Endung laden: STEP (mit PMI), IGES, STL, OBJ, glTF/GLB, 3MF (Netze, ohne PMI). Laengen in mm."""
    import os
    endung = os.path.splitext(pfad)[1].lower()
    if endung in ENDUNGEN_STEP or endung not in ENDUNGEN:
        return lade_step(pfad)
    t0 = time.perf_counter()
    from OCC.Core.XCAFApp import XCAFApp_Application
    doc = TDocStd_Document("XmlXCAF")
    XCAFApp_Application.GetApplication().InitDocument(doc)
    if endung in ENDUNGEN_IGES:
        from OCC.Core.IGESCAFControl import IGESCAFControl_Reader
        r = IGESCAFControl_Reader()
        r.SetColorMode(True)
        r.SetNameMode(True)
        r.SetLayerMode(True)
        if r.ReadFile(pfad) != IFSelect_RetDone or not r.Transfer(doc):
            raise LadeFehler(f"IGES-Datei nicht lesbar: {pfad}")
    elif endung == ".stl":
        from OCC.Core.RWStl import rwstl
        tri = rwstl.ReadFile(pfad)
        if tri is None or tri.NbTriangles() == 0:
            raise LadeFehler(f"STL-Datei nicht lesbar: {pfad}")
        _netz_flaeche(tri, os.path.splitext(os.path.basename(pfad))[0], doc)
    elif endung == ".3mf":
        _lies_3mf(pfad, doc)
    else:
        from OCC.Core.Message import Message_ProgressRange
        from OCC.Core.TCollection import TCollection_AsciiString
        if endung == ".obj":
            from OCC.Core.RWObj import RWObj_CafReader
            r = RWObj_CafReader()
            r.SetFileLengthUnit(0.001)  # OBJ hat keine Einheit: mm angenommen
        else:
            from OCC.Core.RWGltf import RWGltf_CafReader
            r = RWGltf_CafReader()  # glTF ist in Metern
        r.SetSystemLengthUnit(0.001)
        r.SetDocument(doc)
        if not r.Perform(TCollection_AsciiString(pfad), Message_ProgressRange()):
            raise LadeFehler(f"Datei nicht lesbar: {pfad}")
    return _modell_aus_doc(pfad, doc, t0)


def ist_netz(modell) -> bool:
    """True, wenn das Modell nur aus Netzflaechen ohne Geometrie besteht (STL, OBJ, glTF, 3MF)."""
    return bool(modell.flaechen) and all(BRep_Tool.Surface(f) is None for f in modell.flaechen[:20])
