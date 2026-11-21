"""Ausgleichsrad mit kurzer Kugelkalotte und balliger Bolzenbohrung am normalen Auswahlbefehl."""

import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from programm.kern import kegel_radkoerper
from tests.conftest import pfad
from tests.test_verzahnung_sonder import _referenz


def _ausgleichsrad(eng, ende=8.4):
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeRevol, BRepPrimAPI_MakeSphere
    from OCC.Core.GC import GC_MakeArcOfCircle
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location

    rad = _referenz(12, 9., 1.7, 14., 0., kegel=.55, tiefenzuwachs=.06, lagen=2)
    kugel = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, -3), 15.).Shape()
    beschnitt = BRepPrimAPI_MakeBox(gp_Pnt(-30, -30, -1), gp_Pnt(30, 30, ende)).Shape()
    rad = BRepAlgoAPI_Common(BRepAlgoAPI_Common(rad, kugel).Shape(), beschnitt).Shape()
    rand = 4 + (1 if eng else -1) * (18 - math.sqrt(18**2 - 6**2))
    a, m, b = gp_Pnt(rand, 0, -2), gp_Pnt(4, 0, 4), gp_Pnt(rand, 0, 10)
    draht = BRepBuilderAPI_MakeWire()
    draht.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a, m, b).Value()).Edge())
    oben, unten = gp_Pnt(0, 0, 10), gp_Pnt(0, 0, -2)
    for p, q in ((b, oben), (oben, unten), (unten, a)):
        draht.Add(BRepBuilderAPI_MakeEdge(p, q).Edge())
    loch = BRepPrimAPI_MakeRevol(BRepBuilderAPI_MakeFace(draht.Wire()).Face(),
                                 gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1))).Shape()
    lage = gp_Trsf()
    lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(1, 2, 0)), 2.4)
    lage.SetTranslationPart(gp_Vec(12., -30., 5.))
    return BRepAlgoAPI_Cut(rad, loch).Shape().Moved(TopLoc_Location(lage))


@pytest.mark.parametrize("format_,eng,ende", [("step", True, 8.4), ("stl", True, 8.4),
                                              ("step", False, 8.4), ("stl", False, 8.4),
                                              ("step", True, 6.5), ("stl", True, 6.85)])
def test_ausgewaehltes_rad_mit_balliger_bohrung(fenster, tmp_path, format_, eng, ende):
    from PySide6 import QtCore, QtTest, QtWidgets
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GeomAbs import GeomAbs_SurfaceOfRevolution, GeomAbs_Torus
    from OCC.Core.StlAPI import StlAPI_Writer
    from programm.kern.laden import _alle_flaechen
    from werkzeuge.zahnrad import speichere

    form = _ausgleichsrad(eng, ende)
    datei = str(tmp_path / f"Ausgleichsrad.{format_}")
    if format_ == "step":
        speichere(form, datei, "Ausgleichsrad")
    else:
        BRepMesh_IncrementalMesh(form, .005, False, .06)
        assert StlAPI_Writer().Write(form, datei)
    fenster.lade(pfad("baugruppe.stp"), warten=True)
    fenster.modell_hinzufuegen(datei, warten=True)
    knoten = list(fenster.erg.baum.blaetter())[-1]
    flaechen = _alle_flaechen(knoten.form)
    if format_ == "step":
        wand = next(f for f in flaechen if BRepAdaptor_Surface(f).GetType() in (GeomAbs_Torus, GeomAbs_SurfaceOfRevolution))
        fenster.ansicht.setze_auswahl([wand], [knoten.nummer])
    else:
        baum = fenster.baum.baum
        item = fenster.baum._knoten[knoten.nummer]
        baum.scrollToItem(item)
        QtTest.QTest.mouseClick(baum.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=baum.visualItemRect(item).center())
    fenster.aktionen["verzahnung"].trigger()
    lader = fenster._verzahnung_lader
    assert lader.wait(30000)
    QtWidgets.QApplication.processEvents()
    assert lader.teilnummern == [knoten.nummer]
    dialog = fenster._verzahnung
    rad, = dialog.liste
    assert (rad.art, rad.z, rad.bandgrenzen) == ("konisch", 12, None)
    daten = json.loads(open(dialog.speichere("json", str(tmp_path / "Rad.json")), encoding="utf-8").read())
    profil, = daten["sonderprofile"]
    assert profil["kalottenradius"] == pytest.approx(15., abs=.06)
    bohrung = profil["bolzenbohrung"]
    assert bohrung["profil"] == ("mittig_eng" if eng else "mittig_weit")
    assert bohrung["balligkeitsradius"] == pytest.approx(18., abs=.12)
    assert bohrung["scheiteldurchmesser"] == pytest.approx(8., abs=.02)
    csv = open(dialog.speichere("csv", str(tmp_path / "Rad.csv")), encoding="utf-8-sig").read()
    assert all(t in csv for t in ("Kegelrad", "Kugelradius der Rückseite", "Balligkeitsradius der Bohrung"))
    dialog.tabelle.selectColumn(0)
    assert fenster.ansicht.auswahl_teile == [knoten.nummer]


@pytest.mark.parametrize("profil", ["zylinder", "doppelkonus", "stufe", "blind", "ohne"])
def test_bolzenbohrung_braucht_durchgang_und_bogen(profil):
    ecken = np.array([[0., 0., -4.], [0., 0., 4.]])
    phi = np.linspace(0., 2*np.pi, 160, endpoint=False)
    kreis = np.column_stack([np.cos(phi), np.sin(phi)])
    def schnitt(x):
        if profil == "ohne" or (profil == "blind" and x < -2.):
            return [8 * kreis]
        r = {"zylinder": 3., "doppelkonus": 3. + .2*abs(x), "stufe": 3. + (abs(x) > 2),
             "blind": 21. - np.sqrt(18**2 - x**2)}[profil]
        return [r * kreis, 8 * kreis]
    netz = SimpleNamespace(a=ecken, b=ecken, c=ecken, konturen=schnitt)
    assert kegel_radkoerper.bolzenbohrung(netz) is None

def test_konische_rueckseite_mit_gekappten_zaehnen_ist_keine_kalotte():
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
    from programm.kern import verzahnung as vz

    rad = _referenz(12, 9., 1.7, 14., 0., kegel=.55, tiefenzuwachs=.06, lagen=2)
    konus = BRepPrimAPI_MakeCone(17., 3., 17.).Shape()
    form = BRepAlgoAPI_Common(rad, konus).Shape()
    ergebnisse = list(vz.erkenne_koerper(form, "Kontrolle", steckprofile=True, sonderprofile=True))
    assert all(getattr(v, "kalottenradius", None) is None for v in ergebnisse)


def test_kalotte_hinter_unbeschnittenem_zahnband():
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere
    from OCC.Core.gp import gp_Pnt
    from programm.kern import verzahnung as vz

    rad = _referenz(12, 9., 1.7, 8., 0., kegel=.55, tiefenzuwachs=.06, lagen=2)
    radius = math.hypot(10., 10.9)
    kugel = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, -2), radius).Shape()
    hinten = BRepPrimAPI_MakeBox(gp_Pnt(-20, -20, 7.99), gp_Pnt(20, 20, 13)).Shape()
    form = BRepAlgoAPI_Fuse(rad, BRepAlgoAPI_Common(kugel, hinten).Shape()).Shape()
    v = vz.erkenne(form, steckprofile=True, sonderprofile=True)
    assert v.art == "konisch" and v.z == 12 and v.bolzenbohrung is None
    assert v.kalottenradius == pytest.approx(radius, abs=.02)
    assert v.bandgrenzen[1] - v.bandgrenzen[0] == pytest.approx(8., abs=.001)


def _rad_und_anlaufscheibe(ballig=True):
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCC.Core.GC import GC_MakeArcOfCircle
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCC.Core.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt

    def zyl(r, z, l):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), r, l).Shape()

    def kugel(r):
        return BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, -3), r).Shape()

    rad = _referenz(10, 9, 1.9, 11, 0, kegel=.66, tiefenzuwachs=.07, lagen=2)
    rad = BRepAlgoAPI_Common(rad, kugel(15)).Shape()
    rad = BRepAlgoAPI_Common(rad, BRepPrimAPI_MakeCone(7.35, 34, 12).Shape()).Shape()
    rad = BRepAlgoAPI_Cut(rad, zyl(8, 7.3, 15)).Shape()
    rad = BRepAlgoAPI_Cut(rad, zyl(5.1, 4.7, 15)).Shape()
    if ballig:
        # Ballige Bohrungswand bis zum hinteren Absatz. Scheitel in der tragenden Laenge.
        rand = 4 + 18 - math.sqrt(18**2 - 4**2)
        a, m, b = gp_Pnt(rand, 0, -1.8), gp_Pnt(4, 0, 2.2), gp_Pnt(rand, 0, 6.2)
        draht = BRepBuilderAPI_MakeWire()
        draht.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a, m, b).Value()).Edge())
        oben, unten = gp_Pnt(0, 0, 6.2), gp_Pnt(0, 0, -1.8)
        for p, q in ((b, oben), (oben, unten), (unten, a)):
            draht.Add(BRepBuilderAPI_MakeEdge(p, q).Edge())
        loch = BRepPrimAPI_MakeRevol(BRepBuilderAPI_MakeFace(draht.Wire()).Face(),
                                     gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1))).Shape()
    else:
        loch = zyl(4, -1, 17)
    rad = BRepAlgoAPI_Cut(rad, loch).Shape()
    schale = BRepAlgoAPI_Common(BRepAlgoAPI_Cut(kugel(16), kugel(15.03)).Shape(), zyl(10.8, 6, 8)).Shape()
    scheibe = BRepAlgoAPI_Fuse(schale, zyl(7.98, 7.31, 3.59)).Shape()
    scheibe = BRepAlgoAPI_Fuse(scheibe, zyl(5.08, 4.72, 2.61)).Shape()
    return rad, BRepAlgoAPI_Cut(scheibe, zyl(4.01, 4, 12)).Shape()


def _scheibenpaar_step(pfad):
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.STEPControl import STEPControl_AsIs
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    doc = TDocStd_Document("MDTV-XCAF")
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    leer = TopoDS_Compound()
    BRep_Builder().MakeCompound(leer)
    baugruppe = st.AddShape(leer, True)
    lage = gp_Trsf()
    lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(1, 2, 0)), 2.4)
    lage.SetTranslationPart(gp_Vec(12, -30, 5))
    for form, name in zip(_rad_und_anlaufscheibe(), ("Rad", "Anlaufscheibe")):
        teil = st.AddShape(form, False)
        TDataStd_Name.Set(teil, TCollection_ExtendedString(name))
        st.AddComponent(baugruppe, teil, TopLoc_Location(lage))
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_AsIs)
    assert writer.Write(str(pfad)) == IFSelect_RetDone


def test_rad_mit_eingesetzter_kragenscheibe(fenster, tmp_path):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    from programm.kern.laden import _alle_flaechen
    from PySide6 import QtWidgets

    pfad = tmp_path / "Bolzenrad.step"
    _scheibenpaar_step(pfad)
    fenster.lade(str(pfad), warten=True)
    rad, scheibe = fenster.erg.baum.blaetter()
    wand = next(f for f in _alle_flaechen(rad.form) if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
                and abs(BRepAdaptor_Surface(f).Cylinder().Radius() - 5.1) < 1e-4)
    fenster.ansicht.setze_auswahl([wand], [rad.nummer])
    for aktion in ("verzahnung", "getriebe"):
        fenster.aktionen[aktion].trigger()
        lader = fenster._verzahnung_lader
        assert lader.wait(30000)
        QtWidgets.QApplication.processEvents()
        dialog = fenster._verzahnung
        v, = dialog.liste
        assert dialog.quellen[id(v)] == rad.nummer
        assert (v.art, v.z) == ("konisch", 10)
        assert v.kalottenradius == pytest.approx(15, abs=.05)
        assert [s["durchmesser_mm"] for s in v.ruecksitze] == pytest.approx([10.2, 16], abs=.005)
        assert v.ruecksitze[0]["laenge_mm"] == pytest.approx(2.6, abs=.002)
        assert v.bolzenbohrung["balligkeitsradius"] == pytest.approx(18, abs=.18)
        daten = json.loads(open(dialog.speichere("json", str(tmp_path / "rad.json"))).read())
        assert len(daten["sonderprofile"][0]["rueckseitige_senkungen"]) == 2
        if aktion == "getriebe":
            kragen, = daten["wellen_und_sitze"]["kragensitze"]
            assert kragen["zapfen"]["nummer"] == scheibe.nummer and kragen["bohrung"]["nummer"] == rad.nummer
            assert kragen["ueberdeckung_mm"] == pytest.approx(2.58, abs=.02)
        dialog.close()


def test_kragensitz_im_netz(tmp_path):
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.StlAPI import StlAPI_Writer
    from programm.kern.laden import lade_modell
    from programm.kern.verzahnung import erkenne_koerper

    rad, scheibe = _rad_und_anlaufscheibe(False)
    for form, name in ((rad, "Rad"), (scheibe, "Scheibe")):
        pfad = str(tmp_path / (name + ".stl"))
        BRepMesh_IncrementalMesh(form, .005, False, .05)
        assert StlAPI_Writer().Write(form, pfad)
        profile = list(erkenne_koerper(lade_modell(pfad).form, name, steckprofile=True, sonderprofile=True))
        if name == "Rad":
            v, = profile
            assert (v.art, v.z) == ("konisch", 10)
            assert [s["durchmesser_mm"] for s in v.ruecksitze] == pytest.approx([10.2, 16], abs=.01)
            assert v.bolzenbohrung is None
        else:
            assert not profile
