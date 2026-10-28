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
    netz_kanten: dict[int, list] = field(default_factory=dict)  # Flaechenindex -> Randkanten (Netzmodelle)

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
ENDUNGEN_NETZ = (".stl", ".obj", ".gltf", ".glb", ".3mf", ".ply")
ENDUNGEN_QIF = (".qif",)
ENDUNGEN_PRC = (".prc", ".pdf")
ENDUNGEN_STEPZ = (".stpz", ".stepz", ".stp.gz", ".step.gz")
ENDUNGEN_JT = (".jt",)
ENDUNGEN = ENDUNGEN_STEP + ENDUNGEN_IGES + ENDUNGEN_NETZ + ENDUNGEN_QIF + ENDUNGEN_PRC + ENDUNGEN_STEPZ + ENDUNGEN_JT


def jt_version(pfad: str) -> tuple[int, int] | None:
    """(Haupt-, Nebenversion) aus dem JT-Dateikopf ("Version 9.5 JT ..."), None wenn keine JT-Datei."""
    import re
    with open(pfad, "rb") as f:
        kopf = f.read(80).decode("latin-1", "replace")
    m = re.match(r"\s*Version\s+(\d+)\.(\d+)\s+JT", kopf)
    return (int(m.group(1)), int(m.group(2))) if m else None


def jt_wandler() -> str | None:
    """Pfad des JT-Konverters jt2glb (Build-Variante mit TKJT): DG_JT2GLB, neben der gebauten App, extern/."""
    import os
    import sys
    kandidaten = [os.environ.get("DG_JT2GLB", "")]
    name = "jt2glb.exe" if sys.platform == "win32" else "jt2glb"
    basis = getattr(sys, "_MEIPASS", None)
    if basis:
        kandidaten.append(os.path.join(basis, name))
    wurzel = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    kandidaten.append(os.path.join(wurzel, "extern", name))
    return next((k for k in kandidaten if k and os.path.isfile(k) and os.access(k, os.X_OK)), None)


def _lade_jt(pfad: str) -> "StepModell":
    """JT 8 bis 10 ueber TKJT (externer Konverter nach GLB, dann wie glTF)."""
    import os
    import shutil
    import subprocess
    import tempfile
    from ..i18n import tr
    version = jt_version(pfad)
    if version is None:
        raise LadeFehler(tr("Keine JT-Datei: {}").format(os.path.basename(pfad)))
    wandler = jt_wandler()
    if wandler is None:
        raise LadeFehler(tr("JT braucht die Programmvariante mit dem JT-Leser TKJT (packaging/jt/bauen.sh)"))
    ordner = tempfile.mkdtemp(prefix="3dgmax_jt_")
    try:
        ziel = os.path.join(ordner, os.path.splitext(os.path.basename(pfad))[0] + ".glb")
        r = subprocess.run([wandler, pfad, ziel], capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not os.path.isfile(ziel):
            raise LadeFehler(tr("JT-Datei nicht lesbar: {}").format((r.stderr or r.stdout).strip()[-300:]))
        modell = lade_modell(ziel)
        modell.pfad = pfad
        return modell
    finally:
        shutil.rmtree(ordner, ignore_errors=True)


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


_PLY_TYPEN = {"char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1", "short": "i2", "int16": "i2", "ushort": "u2",
              "uint16": "u2", "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4", "float": "f4",
              "float32": "f4", "double": "f8", "float64": "f8"}


def lies_ply(pfad: str):
    """PLY (ASCII oder binaer): (Punkte (n,3), Dreiecke (m,3)); Vielecke werden in Dreiecke zerlegt."""
    import numpy as np
    with open(pfad, "rb") as f:
        if f.readline().strip() != b"ply":
            raise LadeFehler(f"Keine PLY-Datei: {pfad}")
        format_, elemente, aktuell = "", [], None
        while True:
            zeile = f.readline()
            if not zeile:
                raise LadeFehler("PLY-Kopf ohne end_header")
            teile = zeile.decode("ascii", "replace").split()
            if not teile:
                continue
            if teile[0] == "format":
                format_ = teile[1]
            elif teile[0] == "element":
                aktuell = {"name": teile[1], "n": int(teile[2]), "props": []}
                elemente.append(aktuell)
            elif teile[0] == "property" and aktuell is not None:
                aktuell["props"].append(teile[1:])
            elif teile[0] == "end_header":
                break
        rest = f.read()
    punkte, dreiecke = np.zeros((0, 3)), []
    if format_ == "ascii":
        werte = rest.decode("ascii", "replace").split()
        pos = 0
        for el in elemente:
            for _ in range(el["n"]):
                if el["name"] == "vertex":
                    namen = [p[-1] for p in el["props"]]
                    zeile = werte[pos:pos + len(namen)]
                    pos += len(namen)
                    el.setdefault("daten", []).append([float(zeile[namen.index(a)]) for a in "xyz"])
                else:
                    for p in el["props"]:
                        if p[0] == "list":
                            k = int(werte[pos])
                            idx = [int(x) for x in werte[pos + 1:pos + 1 + k]]
                            pos += 1 + k
                            if el["name"] == "face":
                                dreiecke += [(idx[0], idx[j], idx[j + 1]) for j in range(1, k - 1)]
                        else:
                            pos += 1
        punkte = np.array(next((e.get("daten", []) for e in elemente if e["name"] == "vertex"), []), float)
    else:
        ende = "<" if "little" in format_ else ">"
        puffer, pos = memoryview(rest), 0
        for el in elemente:
            if all(p[0] != "list" for p in el["props"]):
                dt = np.dtype([(p[-1], ende + _PLY_TYPEN[p[0]]) for p in el["props"]])
                daten = np.frombuffer(puffer[pos:pos + dt.itemsize * el["n"]], dtype=dt)
                pos += dt.itemsize * el["n"]
                if el["name"] == "vertex":
                    punkte = np.column_stack([daten[a].astype(float) for a in "xyz"])
                continue
            # Flaechen: Liste je Element; schneller Weg fuer reine Dreiecke
            p = next(q for q in el["props"] if q[0] == "list")
            zt, it = np.dtype(ende + _PLY_TYPEN[p[1]]), np.dtype(ende + _PLY_TYPEN[p[2]])
            andere = [q for q in el["props"] if q is not p]
            if not andere:
                probe = np.frombuffer(puffer[pos:pos + zt.itemsize], dtype=zt)[0] if el["n"] else 0
                dt3 = np.dtype([("k", zt), ("i", it, (int(probe),))])
                if el["n"] and int(probe) == 3 and len(puffer) - pos >= dt3.itemsize * el["n"]:
                    daten = np.frombuffer(puffer[pos:pos + dt3.itemsize * el["n"]], dtype=dt3)
                    if np.all(daten["k"] == 3):
                        dreiecke = daten["i"].astype(int).tolist()
                        pos += dt3.itemsize * el["n"]
                        continue
            for _ in range(el["n"]):
                for q in el["props"]:
                    if q[0] == "list":
                        k = int(np.frombuffer(puffer[pos:pos + zt.itemsize], dtype=zt)[0])
                        pos += zt.itemsize
                        idx = np.frombuffer(puffer[pos:pos + it.itemsize * k], dtype=it).astype(int)
                        pos += it.itemsize * k
                        if el["name"] == "face":
                            dreiecke += [(idx[0], idx[j], idx[j + 1]) for j in range(1, k - 1)]
                    else:
                        pos += np.dtype(_PLY_TYPEN[q[0]]).itemsize
    if not len(punkte) or not dreiecke:
        raise LadeFehler(f"PLY ohne Dreiecksnetz (nur Punkte werden noch nicht unterstützt): {pfad}")
    return punkte, np.asarray(dreiecke, int)


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


def _lade_qif(pfad: str, doc, t0: float) -> StepModell:
    """QIF: exakte B-Rep aus der Datei; PMI liest kern.pmi_lesen ueber modell.qif."""
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from .qif import NS, QifDokument
    q = QifDokument(pfad)
    if q.wurzel.find(f".//{NS}Face") is None and q.wurzel.find(f".//{NS}FaceSet") is None:
        raise LadeFehler("QIF-Datei ohne Geometrie (z. B. nur Messergebnisse) – erst das Modell öffnen, dann "
                         "Werkzeuge › Messergebnisse (QIF) einlesen")
    form, zuordnung = q.baue_form()
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    lab = st.AddShape(form, False)
    teil = q.wurzel.find(f".//{NS}Part")
    name = (teil.get("label") if teil is not None else "") or "QIF"
    TDataStd_Name.Set(lab, TCollection_ExtendedString(name, True))
    modell = _modell_aus_doc(pfad, doc, t0)
    modell.qif = q
    modell.qif_flaechen = zuordnung
    return modell


def _entpacke_stepz(pfad: str) -> str:
    """STEPZ (ZIP mit einer Part-21-Datei, oder gzip) in eine temporaere STEP-Datei entpacken; Pfad dorthin."""
    import gzip
    import os
    import shutil
    import tempfile
    import zipfile
    ordner = tempfile.mkdtemp(prefix="3dgmax_stepz_")
    basis = os.path.basename(pfad)
    for e in ENDUNGEN_STEPZ:
        if basis.lower().endswith(e):
            basis = basis[:-len(e)]
    ziel = os.path.join(ordner, basis + ".stp")
    if zipfile.is_zipfile(pfad):
        with zipfile.ZipFile(pfad) as z:
            namen = [n for n in z.namelist() if n.lower().endswith(ENDUNGEN_STEP) and not n.endswith("/")]
            if not namen:
                raise LadeFehler(f"Keine STEP-Datei im Archiv: {pfad}")
            with z.open(namen[0]) as quelle, open(ziel, "wb") as f:
                shutil.copyfileobj(quelle, f)
    else:
        try:
            with gzip.open(pfad, "rb") as quelle, open(ziel, "wb") as f:
                shutil.copyfileobj(quelle, f)
        except OSError as e:
            raise LadeFehler(f"STEPZ nicht lesbar: {pfad}") from e
    return ziel


def _lade_prc(pfad: str, doc, t0: float) -> StepModell:
    """PRC oder 3D-PDF: Flaechennetze je Tessellationsflaeche; Markups und Ansichten liest prc.py."""
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Face
    from . import prc
    try:
        m = prc.lies_datei(pfad)
    except prc.PrcFehler as e:
        raise LadeFehler(f"PRC nicht lesbar: {e}") from e
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    bb = BRep_Builder()
    farben, kanten = [], []
    for k in prc.koerper(m):
        if k.hilfsgeometrie:
            continue
        comp = TopoDS_Compound()
        bb.MakeCompound(comp)
        for i, (punkte, dreiecke, farbe) in enumerate(k.flaechen):
            f = TopoDS_Face()
            bb.MakeFace(f, _poly(punkte, dreiecke))
            bb.Add(comp, f)
            farben.append((f, farbe))
            if i < len(k.kanten) and k.kanten[i]:
                kanten.append((f, k.kanten[i]))
        lab = st.AddShape(comp, False)
        TDataStd_Name.Set(lab, TCollection_ExtendedString(k.name, True))
    if not farben:
        raise LadeFehler(f"Keine Flächennetze in der PRC-Datei (B-Rep oder komprimierte Tessellation "
                         f"werden noch nicht gelesen): {pfad}")
    modell = _modell_aus_doc(pfad, doc, t0)
    modell.prc = m
    modell.prc_farben = {}
    for f, farbe in farben:
        idx = modell.flaechen_index(f)
        if idx is not None and farbe is not None:
            modell.prc_farben[idx] = tuple(float(c) for c in farbe)
    for f, linien in kanten:
        idx = modell.flaechen_index(f)
        if idx is not None:
            modell.netz_kanten[idx] = linien
    return modell


def lade_modell(pfad: str) -> StepModell:
    """Modell nach Endung laden: STEP (mit PMI), IGES, STL, OBJ, glTF/GLB, 3MF (Netze, ohne PMI). Laengen in mm."""
    import os
    if pfad.lower().endswith(ENDUNGEN_STEPZ):
        entpackt = _entpacke_stepz(pfad)
        try:
            modell = lade_step(entpackt)
        finally:
            import shutil
            shutil.rmtree(os.path.dirname(entpackt), ignore_errors=True)
        modell.pfad = pfad
        return modell
    endung = os.path.splitext(pfad)[1].lower()
    if endung in ENDUNGEN_STEP or endung not in ENDUNGEN:
        return lade_step(pfad)
    if endung in ENDUNGEN_JT:
        return _lade_jt(pfad)
    t0 = time.perf_counter()
    from OCC.Core.XCAFApp import XCAFApp_Application
    doc = TDocStd_Document("XmlXCAF")
    XCAFApp_Application.GetApplication().InitDocument(doc)
    if endung in ENDUNGEN_QIF:
        return _lade_qif(pfad, doc, t0)
    if endung in ENDUNGEN_PRC:
        return _lade_prc(pfad, doc, t0)
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
    elif endung == ".ply":
        punkte, dreiecke = lies_ply(pfad)
        _netz_flaeche(_poly(punkte, dreiecke), os.path.splitext(os.path.basename(pfad))[0], doc)
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
