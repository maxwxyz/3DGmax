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
    from programm.kern.getriebe_betrieb import Betriebsmodell
    modell = Betriebsmodell(raeder, [], getrennte_wellen=True)
    assert modell.gruppen == [[0, 1]] and not modell.trennbar
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


def test_zahnflanken_mit_eigenen_step_hinweisen(doppelrad, tmp_path, fenster):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from programm.kern import pmi_bericht
    from programm.kern.pmi_darstellung import Praesentation
    from programm.kern.praesentation import Grafik
    from programm.kern.step_schreiben import _Anhang
    from programm.ui.lader import lade_alles

    pfad = tmp_path / "Zahnbaender.stp"
    writer = STEPControl_Writer()
    schema = Interface_Static.CVal("write.step.schema")
    try:
        assert Interface_Static.SetCVal("write.step.schema", "AP242DIS")
        assert writer.Transfer(doppelrad, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(str(pfad)) == IFSelect_RetDone
    finally:
        Interface_Static.SetCVal("write.step.schema", schema)
    m = lade_alles(str(pfad)).modell
    flanken = {}
    for i, f in enumerate(m.flaechen):
        box = Bnd_Box()
        brepbndlib.Add(f, box)
        x, y, z, xx, yy, zz = box.Get()
        if xx-x < 2 and yy-y < 2:
            for zahl, start, breite in [(14, 1.1, .7), (21, 28., 6.)]:
                if abs(z-start) < .001 and abs(zz-z-breite) < .001:
                    flanken.setdefault(zahl, i)
    assert flanken.keys() == {14, 21}
    anhang = _Anhang(m.datei, m)
    darst = Praesentation(anhang, m)
    noten = [("z = 14", {flanken[14]}), ("z = 15", {flanken[14]}), ("z = 14", {flanken[21]}),
             ("z = 20", set(flanken.values())), ("DEBURR", {flanken[14]})]
    for text, fl in noten:
        assert anhang.waehle(fl) is None
        grafik = Grafik(0, name=text, linien=[np.array([[0., 0., 0.], [1., 2., 0.]])])
        assert darst.callout(grafik, anhang.aspekt(fl), fl)
    darst.abschliessen()
    text = pfad.read_text()
    pos = text.rindex("ENDSEC;")
    pfad.write_text(text[:pos] + "\n".join(anhang.zeilen) + "\n" + text[pos:])
    fenster.lade(str(pfad), warten=True)
    erg = fenster.erg
    assert len(erg.pmi) == 5 and all(p.art == "hinweis" for p in erg.pmi)
    dialog = fenster.pruefe_pmi()
    befunde = [b for b in dialog.befunde if b.kategorie == "geometrie"]
    for b in befunde:
        nummer, = b.nummern
        quelle = erg.pmi[nummer-1]
        assert b.flaechen == noten[nummer-1][1]
        dialog.tabelle.cellDoubleClicked.emit(dialog.befunde.index(b), 0)
        assert fenster.pmi.gewaehlte() == [quelle] and fenster.ansicht.hervor == b.flaechen
        if b.stufe == pmi_bericht.FEHLER:
            assert quelle.name in ("z = 15", "z = 14")
            assert ("14" if quelle.name == "z = 15" else "21") in b.text.split(",")[-1]
        else:
            assert b.stufe == pmi_bericht.INFO and quelle.name == "z = 20"
    assert [b.nummern for b in befunde] == [[2], [3], [4]]


def test_zahnkranz_aus_einer_obj_flaeche_des_stufenrads(doppelrad, tmp_path):
    from programm.kern.ausrichten import tesselliere
    from programm.kern.laden import _alle_flaechen
    from programm.kern.plausibilitaet import verzahnung
    from programm.kern.pmi import Pmi
    from programm.kern.pmi_bericht import FEHLER, INFO
    from tests.test_verzahnung_mesh import _schreibe

    # Zwei einzelne Flanken und die uebrige Oberflaeche gehoeren zum selben geschlossenen Netz.
    gruppen = [[], [], []]
    for punkte, ix in tesselliere(_alle_flaechen(doppelrad)):
        dx, dy, dz = np.ptp(punkte, axis=0)
        ziel = 2
        for i, breite in enumerate((.7, 6.)):
            if not gruppen[i] and max(dx, dy) < 2 and abs(dz - breite) < .001:
                ziel = i
                break
        gruppen[ziel].append(punkte[ix])
    netze = []
    for g in gruppen:
        punkte = np.vstack(g).reshape(-1, 3)
        netze.append((punkte, np.arange(len(punkte)).reshape(-1, 3)))
    modell = _schreibe(tmp_path / "Stufenrad.obj", netze, getrennt=True)
    notizen = [Pmi("hinweis", name="z = 15", nummer=i+1, flaechen={i}) for i in range(3)]
    klein, gross, rest = verzahnung(notizen, modell)
    assert (klein.stufe, gross.stufe, rest.stufe) == (FEHLER, FEHLER, INFO)
    assert "14" in klein.text.split(",")[-1] and "21" in gross.text.split(",")[-1]
    assert (klein.flaechen, gross.flaechen, rest.flaechen) == ({0}, {1}, {2})
