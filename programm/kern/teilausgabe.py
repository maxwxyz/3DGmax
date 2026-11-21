"""Baumauswahl mit Einbaulagen und Namen als STEP oder Dreiecksnetz ausgeben."""

from pathlib import Path
from tempfile import TemporaryDirectory

from OCC.Core.BRep import BRep_Builder, BRep_Tool
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Compound, topods

from ..i18n import tr


def _flaechen(form):
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        yield topods.Face(ex.Current())
        ex.Next()


def enthaelt_netz(knoten):
    return any(BRep_Tool.Surface(f) is None for k in knoten for f in _flaechen(k.form))


def _compound():
    form = TopoDS_Compound()
    BRep_Builder().MakeCompound(form)
    return form


def speichere(ziel, wurzel, nummern, lagen, modell, farben):
    """Nur belegte Zweige schreiben. Ein Fehler laesst eine vorhandene Zieldatei intakt."""
    ziel = Path(ziel)
    gewaehlt = {k.nummer: k.form.Moved(lagen[k.nummer]) if k.nummer in lagen else k.form
                for k in wurzel.blaetter() if k.nummer in nummern}
    if not gewaehlt:
        raise ValueError(tr("Zuerst Elemente im Strukturbaum auswählen."))
    with TemporaryDirectory(dir=ziel.parent) as tmp:
        datei = Path(tmp) / ("selection" + ziel.suffix)
        if ziel.suffix.lower() == ".stl":
            from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
            from OCC.Core.StlAPI import StlAPI_Writer
            form = _compound()
            bb = BRep_Builder()
            for teil in gewaehlt.values():
                if not TopExp_Explorer(teil, TopAbs_FACE).More():
                    raise ValueError(tr("STL benötigt Flächen für jedes gewählte Element."))
                bb.Add(form, teil)
            BRepMesh_IncrementalMesh(form, .05, False, .20, True)
            writer = StlAPI_Writer()
            writer.SetASCIIMode(False)
            ok = writer.Write(form, str(datei))
        elif ziel.suffix.lower() in (".step", ".stp"):
            if enthaelt_netz(k for k in wurzel.blaetter() if k.nummer in gewaehlt):
                raise ValueError(tr("Für eine Auswahl mit Netzflächen das Format STL verwenden."))
            ok = _step(datei, wurzel, gewaehlt, modell, farben)
        else:
            raise ValueError(tr("Eine STEP- oder STL-Dateiendung wählen."))
        if not ok or not datei.is_file() or not datei.stat().st_size:
            raise ValueError(tr("Die gewählte Geometrie konnte nicht exportiert werden."))
        datei.replace(ziel)
    return str(ziel)


def _step(datei, wurzel, gewaehlt, modell, farben):
    from OCC.Core.DESTEP import DESTEP_Parameters
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
    doc = TDocStd_Document("MDTV-XCAF")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    farbtool = XCAFDoc_DocumentTool.ColorTool(doc.Main())
    ident = TopLoc_Location()
    prototypen = {}

    def kopiere(k):
        if k.kinder:
            kinder = [eintrag for kind in k.kinder if (eintrag := kopiere(kind)) is not None]
            if not kinder:
                return None
            label = st.AddShape(_compound(), True)
            for ref, lage in kinder:
                st.AddComponent(label, ref, lage)
            lage = ident
        elif k.nummer in gewaehlt:
            form = gewaehlt[k.nummer]
            basis, lage = form.Located(ident), form.Location()
            key = (basis, k.name)
            if key in prototypen:
                return prototypen[key], lage
            label = st.NewShape()
            st.SetShape(label, basis)
            prototypen[key] = label
            if farben:
                for f in _flaechen(basis):
                    rgb = farben.get(modell.flaechen_index(f))
                    if rgb is not None:
                        sub = st.AddSubShape(label, f)
                        if not sub.IsNull():
                            farbtool.SetColor(sub, Quantity_Color(*rgb, Quantity_TOC_sRGB), XCAFDoc_ColorSurf)
        else:
            return None
        TDataStd_Name.Set(label, TCollection_ExtendedString(k.name, True))
        return label, lage

    ref, lage = kopiere(wurzel)
    if not lage.IsIdentity():
        gruppe = st.AddShape(_compound(), True)
        st.AddComponent(gruppe, ref, lage)
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    parameter = DESTEP_Parameters()
    parameter.WriteSchema = parameter.WriteMode_StepSchema_AP242DIS
    return writer.Transfer(doc, parameter) and writer.Write(str(datei)) == IFSelect_RetDone
