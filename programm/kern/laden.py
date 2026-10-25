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

from OCC.Core.BRep import BRep_Builder
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
    modell.datei = p21.lese(pfad)
    _step_flaechen(reader, modell.datei, modell)
    modell.ladezeit = time.perf_counter() - t0
    return modell


def step_ident(reader, ent) -> int:
    """#ID einer Entitaet des OCCT-Modells (fuer Fehlersuche)."""
    model = StepData_StepModel.DownCast(reader.ChangeReader().WS().Model())
    return model.IdentLabel(ent)
