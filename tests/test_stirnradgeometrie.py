"""Bemasste Stirnradpaare als STEP-Baugruppe aus der Maschinenelementauslegung."""
import json
from math import pi

import numpy as np
import pytest
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

from programm.i18n import tr
from programm.kern.pmi_lesen import lies_pmi_xcaf
from programm.kern.stirnradgeometrie import schreibe_stirnradpaar
from programm.kern.teilausgabe import _flaechen
from programm.kern.verzahnung import erkenne_koerper, paare
from programm.ui.lader import lade_alles


def _volumen(form):
    g = GProp_GProps()
    brepgprop.VolumePropertiesGK(form,g,1e-8)
    return g.Mass()


def _querschnitt(z, m, alpha):
    # Numerische Integration der unabhaengig aus dem Eingriffswinkel berechneten Zahndicke.
    teil = m*z/2
    rf,ra,rb = teil-1.25*m, teil+m, teil*np.cos(np.deg2rad(alpha))
    r = np.linspace(rf,ra,8193)
    winkel = np.arccos(np.minimum(rb/r,1))
    a = np.deg2rad(alpha)
    dicke = 2*r*(pi/(2*z)+np.tan(a)-a-(np.tan(winkel)-winkel))
    return pi*rf**2 + z*np.trapezoid(dicke,r)


def _pruefe_datei(ziel,z1,z2,m,alpha,b1,b2):
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.gp import gp_Pnt
    e = lade_alles(str(ziel))
    a = m*(z1+z2)/2
    assert "AP242" in e.modell.datei.schema
    gruppe, = e.baum.kinder
    assert gruppe.baugruppe and gruppe.name == tr("Geradverzahntes Stirnradpaar")
    teile = {k.name:k for k in gruppe.blaetter()}
    assert set(teile) == {tr("Ritzel"),tr("Rad")}
    nativ = lies_pmi_xcaf(e.modell)
    assert len(e.pmi) == len(nativ) == len(e.grafik) == 6
    profile = []
    for name,z,x,b in ((tr("Ritzel"),z1,0.,b1),(tr("Rad"),z2,a,b2)):
        form = teile[name].form
        assert BRepCheck_Analyzer(form).IsValid()
        assert _volumen(form) == pytest.approx(b*_querschnitt(z,m,alpha),rel=3e-6)
        ids = {e.modell.flaechen_index(f) for f in _flaechen(form)}
        gemessen, = erkenne_koerper(form,name,steckprofile=True,sonderprofile=True)
        profile.append(gemessen)
        assert gemessen.z == z and gemessen.b == pytest.approx(b,abs=.002)
        assert gemessen.mn == pytest.approx(m,rel=.001)
        np.testing.assert_allclose(gemessen.punkt,[x,0,b1/2],atol=1e-5)
        soll = sorted([(b,"Location_LinearDistance",2),(m*(z+2),"Size_Diameter",z),(m*(z-2.5),"Size_Diameter",z)])
        for quelle in (e.pmi,nativ):
            teilmasse = [p for p in quelle if p.flaechen and p.flaechen <= ids]
            assert sorted((p.nennwert,p.typ,len(p.flaechen)) for p in teilmasse) == soll
        for p in (p for p in e.pmi if p.flaechen <= ids):
            assert p.semantisch and p.grafisch
            grafik, = [g for g in e.grafik.values() if p.step_id in g.pmi_ids]
            assert grafik.linien and grafik.dreiecke and not grafik.erzeugt
            flaechen = [e.modell.flaechen[i] for i in p.flaechen]
            adapter = [BRepAdaptor_Surface(f) for f in flaechen]
            if p.typ == "Size_Diameter":
                assert all(s.GetType() == GeomAbs_Cylinder and 2*s.Cylinder().Radius() == pytest.approx(p.nennwert)
                           for s in adapter)
                spitze = BRepBuilderAPI_MakeVertex(gp_Pnt(*grafik.linien[0][0])).Vertex()
                assert min(BRepExtrema_DistShapeShape(f,spitze).Value() for f in flaechen) < .01
            else:
                assert all(s.GetType() == GeomAbs_Plane for s in adapter)
                assert sorted(s.Plane().Location().Z() for s in adapter) == pytest.approx([(b1-b)/2,(b1+b)/2])
    paar, = paare(profile)
    assert paar.abstand == pytest.approx(a,abs=1e-6) and paar.eps_alpha >= 1
    assert _volumen(BRepAlgoAPI_Common(*(k.form for k in teile.values())).Shape()) < 1e-6
    return e


@pytest.mark.parametrize("z1,z2,m,alpha,b1,b2", [(18,36,1.5,20,8,10),(22,45,2.,25,13,9),(20,20,1.,20,5,5)])
def test_baugruppe_und_massziele(tmp_path,z1,z2,m,alpha,b1,b2):
    ziel = tmp_path/"Getriebe.step"
    assert schreibe_stirnradpaar(ziel,dict(z1=z1,z2=z2,m=m,alpha=alpha),b1,b2) == 6
    _pruefe_datei(ziel,z1,z2,m,alpha,b1,b2)


def test_exportfehler_und_abbruch_schuetzen_die_zieldatei(tmp_path, monkeypatch):
    from programm.kern import step_schreiben
    pfad = tmp_path/"Konstruktion.step"
    pfad.write_bytes(b"vorhanden")
    werte = dict(z1=18,z2=36,m=1.5,alpha=20)
    for daten,b in (({"z1":3},4),({"alpha":85},4),({"z2":18.5},4),({},0),({},np.inf)):
        with pytest.raises(ValueError):
            schreibe_stirnradpaar(pfad,{**werte,**daten},b,6)
        assert pfad.read_bytes() == b"vorhanden"
    def abbruch():
        raise InterruptedError
    with pytest.raises(InterruptedError):
        schreibe_stirnradpaar(pfad,werte,5,5,pruefe=abbruch)
    assert pfad.read_bytes() == b"vorhanden"
    assert list(tmp_path.iterdir()) == [pfad]

    fertig = False
    schreiben = step_schreiben.schreibe

    def nach_pmi(*args):
        nonlocal fertig
        bericht = schreiben(*args)
        fertig = True
        return bericht

    def spaeter_abbruch():
        if fertig:
            raise InterruptedError

    monkeypatch.setattr(step_schreiben, "schreibe", nach_pmi)
    with pytest.raises(InterruptedError):
        schreibe_stirnradpaar(pfad, werte, 5, 5, pruefe=spaeter_abbruch)
    assert fertig and pfad.read_bytes() == b"vorhanden"
    assert list(tmp_path.iterdir()) == [pfad]


def test_auslegungsdialog_mit_alter_datei_und_getrennten_breiten(fenster,app,tmp_path,monkeypatch):
    from PySide6 import QtWidgets
    from programm.ui.maschinenelemente_ui import AuslegungFenster
    quelle = tmp_path/"Entwurf.json"
    quelle.write_text(json.dumps(dict(format="3dgmax-auslegung",version=1,verfahren="stirnrad",
                          eingaben=dict(z1=18,z2=36,m=1.5,alpha=20,t=10))))
    fenster.aktionen["maschinenelement"].trigger()
    dialog, = fenster.findChildren(AuslegungFenster)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getOpenFileName",lambda *a:(str(quelle),""))
    dialog._oeffnen()
    assert dialog.daten["ergebnisse"]["a"] == 40.5 and not dialog.step.isEnabled()
    for k,v in (("b1","8"),("b2","10")):
        dialog.breitenfelder[k].setText(v)
    assert dialog.step.isVisible() and dialog.step.isEnabled()
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(quelle),""))
    dialog._speichern()
    assert json.loads(quelle.read_text())["geometrie"] == {"b1":8.,"b2":10.}
    dialog.breitenfelder["b2"].clear()
    dialog._oeffnen()
    assert float(dialog.breitenfelder["b2"].text()) == 10
    dialog.felder["t"].clear()
    assert dialog.step.isEnabled() and not dialog.speichern.isEnabled()
    ziel = tmp_path/"Stirnradpaar.step"
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(ziel),""))
    fehler = []
    monkeypatch.setattr(QtWidgets.QMessageBox,"warning",lambda *a:fehler.append(a[-1]))
    dialog.step.click()
    assert dialog.paarauftrag.wait(60000)
    app.processEvents()
    assert not fehler and dialog.paarauftrag is None and dialog.step.isEnabled()
    _pruefe_datei(ziel,18,36,1.5,20,8,10)
