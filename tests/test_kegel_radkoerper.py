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
