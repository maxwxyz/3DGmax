"""Sitzflaechen, Toleranzen und Herkunft vom Getriebebefehl bis zum Entwurf."""

from dataclasses import replace
import json

import pytest
from PySide6 import QtWidgets

from programm.kern.pmi import MASS, Pmi
from programm.kern.pressverbandgeometrie import schreibe_pressverband
from programm.kern.sitzpassung import passungsvorgaben, sitzmasse
from programm.kern.zylindersitze import Sitz
from tests.test_pressverbandgeometrie import REFERENZ, _geometrie, _pruefe_assembly


def _sitze():
    w = Sitz(4, "Teil", False, 20., (0., 0., 5.), (0., 0., 1.), 10., (10, 11))
    n = replace(w, nummer=7, innen=True, flaechen=(12,))
    da = replace(n, innen=False, d_mm=40., flaechen=(13,))
    return w, n, da


def _mass(ids, **kwargs):
    return Pmi(MASS, "Size_Diameter", nennwert=20., flaechen=set(ids), quelle="step", step_id=45, **kwargs)


def test_geteilte_sitzflaeche_passungsklassen_und_grenzmasse():
    w, n, da = _sitze()
    a = _mass(w.flaechen, passung="p6")
    b = _mass(n.flaechen, passung="H7")
    m = sitzmasse([w,n,da], [a,b,_mass([13], unten=0., oben=.2)])
    werte, belege, hinweis = passungsvorgaben(w,n,9.,[w,n,da],m)
    assert not hinweis and werte == dict(d=20., l=9., da=40., ei_w=22., es_w=35., ei_n=0., es_n=21.)
    assert "(#4)" in belege["ei_w"] and "p6" in belege["es_w"]
    assert "(#7)" in belege["ei_n"] and "H7" in belege["es_n"]


@pytest.mark.parametrize("fall", ["doppelt", "andere_rolle", "grafisch", "mehrere_sitze", "ohne_pmi",
                                   "hilfsmass", "ohne_abmass", "nur_oben", "klasse_widerspricht", "falsche_groesse", "vertauschte_grenzen"])
def test_fehlt_oder_unklar_bleibt_editierbar(fall):
    w,n,da = _sitze()
    b = _mass([12], unten=-.01, oben=.002)
    a = _mass([10], unten=.01, oben=.03)
    objekte = {
        "doppelt": [a, replace(a, step_id=55, unten=.015)],
        "andere_rolle": [replace(a, passung="H7")], "grafisch": [replace(a, semantisch=False)],
        "mehrere_sitze": [replace(a, flaechen={10,12})], "ohne_pmi": [],
        "hilfsmass": [replace(a, modifikatoren=["Hilfsmass"])], "ohne_abmass": [_mass([10])],
        "nur_oben": [replace(a, unten=None)], "klasse_widerspricht": [replace(a, passung="p6")],
        "falsche_groesse": [replace(a, nennwert=22.)], "vertauschte_grenzen": [replace(a, oben=-.2)],
    }[fall]
    sitze = [w,n,da]
    werte, _, hinweis = passungsvorgaben(w,n,10.,sitze,sitzmasse(sitze,[*objekte,b]))
    assert hinweis and "ei_w" not in werte and "es_w" not in werte
    if fall != "mehrere_sitze":
        assert (werte["ei_n"],werte["es_n"]) == (-10.,2.)
    else:
        assert "ei_n" not in werte
    assert werte["d"] == 20. and werte["da"] == 40.


def test_unterschiedliche_nennmasse_und_mehrdeutiger_aussenmantel():
    w,n,da = _sitze()
    n = replace(n, d_mm=20.01)
    sitze = [w,n,da,replace(da, d_mm=45., flaechen=(16,))]
    gleich = _mass([10], oben=.015, unten=.002)
    anders = replace(gleich, nennwert=20.01, flaechen={12})
    werte, _, hinweis = passungsvorgaben(w,n,10.,sitze,sitzmasse(sitze,[gleich,anders]))
    assert hinweis and werte == {"d":20., "l":10.}


def test_getriebebefehl_passung_bis_zum_erneuten_step(fenster,app,tmp_path,monkeypatch):
    pfad = tmp_path/"Original.step"
    schreibe_pressverband(pfad, **_geometrie(REFERENZ))
    fenster.lade(str(pfad), warten=True)
    fenster.aktionen["getriebe"].trigger()
    assert fenster._verzahnung_lader.wait(30000)
    app.processEvents()
    t = fenster._verzahnung.sitzseite
    t.tabelle.selectRow(1)
    assert not t.pressverband.isEnabled()
    t.tabelle.selectRow(0)
    assert t.pressverband.isEnabled() and fenster.baum.gewaehlte_blaetter() == {2,3}
    from programm.ui.maschinenelemente_ui import AuslegungFenster
    t.pressverband.click()
    f, = t.findChildren(AuslegungFenster)
    assert f.art == "sitzgrenzen" and f.step.isEnabled() and not f.speichern.isEnabled()
    assert f.messwerte == _geometrie(REFERENZ)
    for k in ("ei_w", "ei_n"):
        assert "STEP #" in f.felder[k].toolTip()
    assert f.feldquellen["ei_n"] != f.feldquellen["ei_w"]
    for k, v in REFERENZ.items():
        if k not in f.messwerte:
            f.felder[k].setText(str(v))
    assert f.daten["ergebnisse"]["t_res"] == pytest.approx(13.09733553)
    f.felder["ei_n"].setText("-3")
    ziel = tmp_path/"Entwurf.json"
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(ziel),""))
    f.speichern.click()
    daten = json.loads(ziel.read_text())
    assert daten["eingaben"]["ei_n"] == -3 and daten["uebernommene_masse"]["ei_n"] == -4
    assert daten["feldquellen"]["ei_n"] == f.feldquellen["ei_n"]
    f.felder["ei_n"].clear()
    monkeypatch.setattr(QtWidgets.QFileDialog,"getOpenFileName",lambda *a:(str(ziel),""))
    f._oeffnen()
    assert f.daten == daten and "STEP #" in f.felder["ei_n"].toolTip()
    ziel = tmp_path/"Aenderung.step"
    f.step.click()
    _pruefe_assembly(ziel, {**REFERENZ, "ei_n":-3})


def test_zwei_eingebaute_vorkommen_geteilter_sitzflaechen():
    from math import pi
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from programm.kern.laden import StepModell
    from programm.kern.teilausgabe import _flaechen
    from programm.kern.zylindersitze import erkenne

    achsen = [gp_Ax2(gp_Pnt(), gp_Dir(0, 0, 1), gp_Dir(s, 0, 0)) for s in (1,-1)]
    halb = [BRepPrimAPI_MakeCylinder(achse, 10., 10., pi).Shape() for achse in achsen]
    welle = BRepAlgoAPI_Fuse(*halb).Shape()
    modell = StepModell("", None, None, welle, list(_flaechen(welle)))
    modell._baue_index()
    lage = gp_Trsf()
    lage.SetTranslation(gp_Vec(50., 20., -10.))
    a, = erkenne(welle, 1, "Welle", flaechen_index=modell.flaechen_index)
    b, = erkenne(welle.Moved(TopLoc_Location(lage)), 2, "Welle", flaechen_index=modell.flaechen_index)
    assert a.flaechen == b.flaechen and len(a.flaechen) == 2
    assert b.mitte_mm == pytest.approx((50,20,-5))
    alle = sitzmasse([a,b], [_mass(a.flaechen, passung="p6")])
    assert alle[a] == alle[b]
    _,n,da = _sitze()
    n = replace(n, mitte_mm=b.mitte_mm)
    _, belege, _ = passungsvorgaben(b,n,10,[a,b,n,da],alle)
    assert "(#2)" in belege["es_w"] and "(#1)" not in belege["es_w"]
