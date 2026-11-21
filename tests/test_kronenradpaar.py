"""Eingebaute Kronenradstufe im STEP- und Netzimport mit bekanntem Drehsinn."""
import json

import numpy as np
import pytest
from OCC.Core.BRep import BRep_Builder
from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Compound

from programm.kern.getriebe_betrieb import Betriebsmodell
from programm.kern.kronenradpaar import kronenradpaare
from programm.kern.laden import lade_modell
from programm.kern import verzahnung as vz, verzahnung_daten as vd
from tests.conftest import pfad
from werkzeuge.zahnrad import zahnrad


@pytest.fixture(scope="module")
def raeder():
    # Unabhaengiger FreeCAD-Gears-Kranz: 32 Zaehne, Modul 1, Bezugsritzel 15, Radien 16 bis 19 mm.
    return lade_modell(pfad("kronenrad_32.stp.gz")).form, zahnrad(15,1,3)


def _einbau(seite=1, winkel=0., quer=0., axial=15.6, oben=6.58):
    t = gp_Trsf()
    t.SetValues(0,-seite,0,quer, 0,0,seite,axial*seite, -1,0,0,oben)
    dreh = gp_Trsf()
    dreh.SetRotation(gp_Ax1(gp_Pnt(),gp_Dir(0,0,1)), winkel)
    return TopLoc_Location(t.Multiplied(dreh))


def _baugruppe(raeder, lage, drehen=False):
    bauer = BRep_Builder()
    form = TopoDS_Compound()
    bauer.MakeCompound(form)
    bauer.Add(form, raeder[0])
    bauer.Add(form, raeder[1].Moved(lage))
    if drehen:
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(),gp_Dir(0,1,1)), 1.15)
        t.SetTranslationPart(gp_Vec(42,-178,23))
        form = form.Moved(TopLoc_Location(t))
    return form


def _schreiben(form, ziel):
    if ziel.suffix == ".stl":
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.StlAPI import StlAPI_Writer
        BRepMesh_IncrementalMesh(form,.009,False,.08)
        assert StlAPI_Writer().Write(form,str(ziel))
    else:
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
        writer = STEPControl_Writer()
        assert writer.Transfer(form,STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(str(ziel)) == IFSelect_RetDone


def _erkennen(form):
    return list(vz.erkenne_koerper(form,"Stufe",steckprofile=True,sonderprofile=True))


@pytest.mark.parametrize("endung,seite,drehen", [("step",1,False),("stl",1,False),("step",-1,True),("stl",-1,True)])
def test_kronenstufe_aus_baugruppe(raeder,tmp_path,endung,seite,drehen):
    ziel = tmp_path/f"Kronenstufe.{endung}"
    _schreiben(_baugruppe(raeder,_einbau(seite),drehen),ziel)
    liste = _erkennen(lade_modell(str(ziel)).form)
    paar, = kronenradpaare(liste)
    assert (paar.a.z,paar.b.z) == (32,15)
    assert paar.messbereich[0] < 16.6 < 18 < paar.messbereich[1]
    modell = Betriebsmodell(liste, [])
    op = modell.betrieb()
    stufe, = op.kronenstufen
    ka, ri = stufe["wellen"]
    # Die positive Wellenachse bleibt bei dieser Testdrehung fuer +Y und +Z positiv orientiert.
    werte = op.auswerten({ri:320},[])["wellen"]
    assert werte[ka]["drehzahl"] == pytest.approx(150*seite)
    index = next(i for i,v in enumerate(liste) if v is paar.b)
    daten = vd.datenblatt(liste,[],index)
    assert daten["kronenradpaar_kandidaten"] == [paar.als_dict()]
    zug, = daten["kraftfluss"]["zuege"]
    assert zug["stufen"][0]["u"] == pytest.approx(32/15)
    assert zug["wellenwerte"][str(ka)]["i"] == pytest.approx(32/15)


def test_kronenstufe_braucht_eingriff_am_zahnband(raeder):
    krone, = _erkennen(raeder[0])
    assert not kronenradpaare([krone])
    # Rueckseite, axial frei, radial frei, Achsversatz, falsche Zahnstellung, parallele Wellen.
    for lage in (_einbau(oben=-8.5),_einbau(oben=7.6),_einbau(axial=20),_einbau(quer=.75),
                 _einbau(winkel=np.pi/15),TopLoc_Location()):
        rad, = _erkennen(raeder[1].Moved(lage))
        assert not kronenradpaare([krone,rad])
        assert not Betriebsmodell([krone,rad],[]).betrieb().kronenstufen


def test_gegenprobe_durchdringung_an_den_exakten_volumen(raeder):
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps

    for phase in (0, np.pi/15):
        schnitt = BRepAlgoAPI_Common(raeder[0], raeder[1].Moved(_einbau(winkel=phase)))
        assert schnitt.IsDone()
        masse = GProp_GProps()
        brepgprop.VolumeProperties(schnitt.Shape(),masse)
        if phase:
            assert masse.Mass() > 9
        else:
            assert masse.Mass() < 1e-7


def test_kronenrad_und_stirnradstufe_mit_zwischenwelle(raeder):
    liste = _erkennen(_baugruppe(raeder,_einbau()))
    for z,x in ((20,0),(40,30)):
        lage = gp_Trsf()
        lage.SetTranslation(gp_Vec(x,0,-12))
        liste.extend(_erkennen(zahnrad(z,1,3).Moved(TopLoc_Location(lage))))
    indizes = {v.z:i for i,v in enumerate(liste)}
    paare = vz.paare(liste)
    daten = vd.datenblatt(liste,paare,indizes[15])["kraftfluss"]
    zug, = daten["zuege"]
    aus = next(i for i,g in enumerate(daten["wellen"]) if indizes[40] in g)
    assert [s["u"] for s in zug["stufen"]] == pytest.approx([32/15,2])
    assert zug["wellenwerte"][str(aus)]["i"] == pytest.approx(64/15)
    modell = Betriebsmodell(liste,paare)
    b = modell.betrieb()
    werte = b.auswerten({modell.welle[indizes[15]]:320},[])["wellen"]
    assert werte[modell.welle[indizes[40]]]["drehzahl"] == pytest.approx(-75)


def test_getriebebefehl_kronenstufe_auswaehlen_und_exportieren(raeder,tmp_path,fenster,app):
    from pypdf import PdfReader
    from tests.test_betriebspunkt_ui import _vorgabe

    eingang = tmp_path/"Kronenstufe.step"
    _schreiben(_baugruppe(raeder,_einbau()),eingang)
    fenster.lade(str(eingang),warten=True)
    fenster.aktionen["getriebe"].trigger()
    assert fenster._verzahnung_lader.wait(30000)
    app.processEvents()
    f = fenster._verzahnung
    assert f.paar_tabelle.columnCount() == 1
    f.paar_tabelle.selectColumn(0)
    assert fenster.baum.gewaehlte_blaetter() == set(f.quellen.values())
    stufe, = f.betriebspunkt.betrieb.kronenstufen
    ka, ri = stufe["wellen"]
    _vorgabe(f.betriebspunkt,ri,320)
    ziel = f.speichere("json",str(tmp_path/"bericht.json"))
    with open(ziel,encoding="utf-8") as datei:
        daten = json.load(datei)
    assert daten["kronenradpaar_kandidaten"][0]["i_ritzel_kronenrad"] == pytest.approx(32/15)
    assert daten["betriebspunkt"]["wellen"][ka]["drehzahl"] == pytest.approx(150)
    assert daten["betriebspunkt"]["wellen"][ka]["rollen"] == ["kronenrad"]
    csv = f.speichere("csv",str(tmp_path/"bericht.csv"))
    with open(csv,encoding="utf-8-sig") as datei:
        text = datei.read()
    assert "Mögliche Kronenradstufe" in text and "150" in text
    pdf = PdfReader(f.speichere("pdf",str(tmp_path/"bericht.pdf")))
    assert any("150" in s.extract_text() and "Kronenrad" in s.extract_text() for s in pdf.pages)
