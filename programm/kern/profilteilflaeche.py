"""Separat getrimmte Flaechen eines STEP-Profilbereichs dem Produkt zuordnen."""

from math import isclose

from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepTools import breptools
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepGProp import BRepGProp_Face, brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.ShapeAnalysis import ShapeAnalysis_Surface
from OCC.Core.gp import gp_Pnt, gp_Vec
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopoDS import topods
from OCC.Core.TopTools import TopTools_ListOfShape

from .ansichten import darstellungskontext
from .p21 import Ref
from .pmi_lesen import geometrieziele_von_aspekt
from .step_schreiben import _Anhang


def _inhalt(form):
    g = GProp_GProps()
    brepgprop.SurfaceProperties(form, g, 1e-7)
    return g.Mass()


def _box(form):
    box = Bnd_Box()
    brepbndlib.Add(form, box, False)
    return box


def _enthaelt(original, teil, inhalt):
    argumente, werkzeuge = TopTools_ListOfShape(), TopTools_ListOfShape()
    argumente.Append(original)
    werkzeuge.Append(teil)
    gemeinsam = BRepAlgoAPI_Common()
    gemeinsam.SetArguments(argumente)
    gemeinsam.SetTools(werkzeuge)
    gemeinsam.SetNonDestructive(True)
    gemeinsam.Build()
    return gemeinsam.IsDone() and isclose(_inhalt(gemeinsam.Shape()), inhalt, rel_tol=1e-8, abs_tol=1e-12)


def _ausgerichtet(flaeche, original, eingebaut):
    lage = eingebaut.Location().Multiplied(original.Location().Inverted())
    teil = topods.Face(flaeche.Moved(lage))
    u0, u1, v0, v1 = breptools.UVBounds(teil)
    punkt, normal = gp_Pnt(), gp_Vec()
    BRepGProp_Face(teil).Normal((u0 + u1)/2, (v0 + v1)/2, punkt, normal)
    traeger = ShapeAnalysis_Surface(BRep_Tool.Surface(eingebaut))
    uv = traeger.ValueOfUV(punkt, 1e-7)
    gegenpunkt, aussen = gp_Pnt(), gp_Vec()
    BRepGProp_Face(eingebaut).Normal(uv.X(), uv.Y(), gegenpunkt, aussen)
    if punkt.Distance(gegenpunkt) > 1e-6 or min(normal.Magnitude(), aussen.Magnitude()) < 1e-12:
        return None
    return topods.Face(teil.Reversed()) if normal.Dot(aussen) < 0 else teil


class Bereichsleser:
    """Eigene Transfersitzung und wiederverwendbare Traegergrenzen waehrend eines Imports."""

    def __init__(self, modell):
        self.modell = modell
        self.reader = STEPControl_Reader()
        self.reader.WS().SetModel(modell._reader.ChangeReader().StepModel())
        self.kontext = _Anhang(modell.datei, modell)
        self.boxen = {}
        self.ergebnisse = {}

    def ausschnitt(self, nr, rep, pds):
        key = (nr, rep, pds)
        if key not in self.ergebnisse:
            self.ergebnisse[key] = self._lies(nr, rep, pds)
        return self.ergebnisse[key]

    def _lies(self, nr, rep, pds):
        rang = self.reader.WS().NumberFromLabel(f"#{nr}")
        if rang <= 0 or not self.reader.TransferOne(rang):
            return None
        form = self.reader.Shape(self.reader.NbShapes())
        if form.IsNull() or form.ShapeType() != TopAbs_FACE or not BRepCheck_Analyzer(form).IsValid():
            return None
        flaeche = topods.Face(form)
        inhalt = _inhalt(flaeche)
        if inhalt <= 1e-12:
            return None
        box = _box(flaeche)
        kontext = darstellungskontext(self.modell.datei.get(rep))
        treffer = []
        for idx, ursprung in self.modell.flaeche_zu_step.items():
            if ursprung not in self.boxen:
                original = self.modell.form_von_step(ursprung)
                self.boxen[ursprung] = (_box(original), original) if original is not None else (None, None)
            grenzen, original = self.boxen[ursprung]
            if grenzen is None or box.IsOut(grenzen) or self.kontext.waehle({idx}):
                continue
            if self.kontext.pds != pds or self.kontext.kontext != kontext:
                continue
            if _enthaelt(original, flaeche, inhalt):
                treffer.append((idx, original))
                if len(treffer) > 1:
                    return None
        if treffer:
            idx, original = treffer[0]
            teil = _ausgerichtet(flaeche, original, self.modell.flaechen[idx])
            if teil is not None:
                return idx, teil
        return None


def lies_ausschnitte(modell, aspekt, p, leser):
    """Nur vollstaendig zugeordnete Bereiche uebernehmen; das Produktmodell bleibt unveraendert."""
    d = modell.datei
    reps = {}
    ziele = geometrieziele_von_aspekt(d, modell, aspekt.id, bereichsdarstellungen=reps)
    unbekannt = (ziele or set()) - modell.step_zu_flaeche.keys()
    if not unbekannt or any(len(reps.get(n, ())) != 1 for n in unbekannt):
        return
    args = aspekt.args("SHAPE_ASPECT") if aspekt.is_a("SHAPE_ASPECT") else aspekt.args("BETWEEN_SHAPE_ASPECT")
    if len(args) < 3 or not isinstance(args[2], Ref):
        return
    # Eigene Transfersitzung nur fuer die Zusatzflaechen; keine zweite Produktwurzel.
    ausschnitte = {}
    try:
        reader = leser()
        for nr in sorted(unbekannt):
            rep, = reps[nr]
            ziel = reader.ausschnitt(nr, rep, args[2].id)
            if ziel is None:
                return
            ausschnitte[nr] = ziel
    except RuntimeError:
        return  # OCCT konnte die getrimmte Geometrie nicht sicher auswerten.
    ganze = {modell.step_zu_flaeche[n] for n in ziele - unbekannt}
    if ganze and (reader.kontext.waehle(ganze) or reader.kontext.pds != args[2].id):
        return
    p.flaechen = ganze
    p.profilausschnitte = ausschnitte
