"""Getrennte Zahnbaender auf einer durchgehenden Welle mit bekannter Lage und Breite."""

import numpy as np
import pytest

from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCC.Core.TopAbs import TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.gp import gp_Vec

from programm.kern import verzahnung as vz
from werkzeuge.zahnrad import _draht, stirnschnitt


def _stufenwelle(baender):
    welle = BRepPrimAPI_MakeCylinder(3., 43.).Shape()
    for z, start, breite in baender:
        kontur = stirnschnitt(z, 1.5)
        stirn = BRepBuilderAPI_MakeFace(_draht(kontur, start)).Face()
        rad = BRepPrimAPI_MakePrism(stirn, gp_Vec(0., 0., breite)).Shape()
        welle = BRepAlgoAPI_Fuse(welle, rad).Shape()
    ex = TopExp_Explorer(welle, TopAbs_SOLID)
    solid = ex.Current()
    ex.Next()
    assert not ex.More()
    return solid


@pytest.fixture(scope="module")
def doppelrad():
    # Schmaler erster Bund zwischen zwei Punkten des regulaeren 12er-Suchrasters.
    return _stufenwelle([(14, 1.1, .7), (21, 28., 6.)])


@pytest.mark.parametrize("netz", [False, True])
def test_zwei_arbeitsbereiche_auf_einem_koerper(doppelrad, netz, tmp_path):
    form = doppelrad
    startpunkt, richtung = np.zeros(3), np.array([0., 0., 1.])
    if netz:
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCC.Core.StlAPI import StlAPI_Writer
        from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
        from programm.kern.laden import lade_modell
        lage = gp_Trsf()
        lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(1., 0., 0.)), .7)
        startpunkt = np.array([31., -16., 4.])
        richtung = np.array([0., -np.sin(.7), np.cos(.7)])
        lage.SetTranslationPart(gp_Vec(*startpunkt))
        form = BRepBuilderAPI_Transform(form, lage).Shape()
        BRepMesh_IncrementalMesh(form, .002, False, .05, True)
        pfad = str(tmp_path / "Doppelrad.stl")
        writer = StlAPI_Writer()
        writer.SetASCIIMode(False)
        assert writer.Write(form, pfad)
        form = lade_modell(pfad).form
    raeder = sorted(vz.erkenne_koerper(form, "Welle", steckprofile=True, sonderprofile=True), key=lambda v: v.z)
    assert [v.z for v in raeder] == [14, 21]
    assert {v.teil for v in raeder} == {"Welle [1/2]", "Welle [2/2]"}
    for v, start, breite in zip(raeder, [1.1, 28.], [.7, 6.]):
        assert v.als_dict()["koerper"] == "Welle"
        assert abs(v.richtung @ richtung) == pytest.approx(1.)
        assert v.b == pytest.approx(breite, abs=.001)
        assert v.punkt == pytest.approx(startpunkt + richtung * (start + breite / 2), abs=.001)
        assert v.mn == pytest.approx(1.5, abs=.004)
        assert v.beta == 0.
        for offset, r in v.r_schnitte:
            assert abs(offset) < breite / 2
            assert np.argmax(abs(np.fft.rfft(r))[1:]) + 1 == v.z


def test_einzelnes_zahnband_zwischen_glatten_wellenenden():
    form = _stufenwelle([(17, 18., 3.5)])
    v, = vz.erkenne_koerper(form, "einfach")
    assert v.z == 17 and v.b == pytest.approx(3.5, abs=.001)
    assert v.punkt[2] == pytest.approx(19.75, abs=.001)
    assert v.teil == "einfach" and v.koerper is None


def test_zahnzahlwechsel_an_gemeinsamer_schulter():
    form = _stufenwelle([(16, 12., 4.), (23, 16., 6.)])
    raeder = sorted(vz.erkenne_koerper(form, "Stufe"), key=lambda v: v.z)
    assert [v.z for v in raeder] == [16, 23]
    assert [v.b for v in raeder] == pytest.approx([4., 6.], abs=.001)
    assert [v.punkt[2] for v in raeder] == pytest.approx([14., 19.], abs=.001)


def test_hinweis_am_doppelrad_hat_keinen_eindeutigen_zahnbezug(doppelrad):
    from types import SimpleNamespace
    from programm.kern import plausibilitaet
    from programm.kern.pmi import Pmi
    from programm.kern.pmi_bericht import INFO
    assert vz.erkenne(doppelrad) is None
    hinweis = Pmi("hinweis", nur_grafik_text="z = 21, mn = 1.5", nummer=1)
    befund, = plausibilitaet.verzahnung([hinweis], SimpleNamespace(form=doppelrad))
    assert befund.stufe == INFO
