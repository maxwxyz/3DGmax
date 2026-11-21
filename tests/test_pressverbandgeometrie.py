"""Pressverband mit zwei Fertigungstoleranzen von der Auslegung bis zur STEP-Ruecklesung."""

import json
from math import pi

import pytest
from PySide6 import QtWidgets
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopAbs import TopAbs_REVERSED

from programm.i18n import tr
from programm.kern.maschinenelemente import SITZGEOMETRIE, berechne
from programm.kern.pmi_lesen import lies_pmi_xcaf
from programm.kern.pressverbandgeometrie import schreibe_pressverband
from programm.kern.teilausgabe import _flaechen
from programm.kern.zylindersitze import erkenne, paare
from programm.ui.lader import lade_alles

REFERENZ = dict(d=20, l=15, da=40, ei_w=20, es_w=30, ei_n=-4, es_n=2, verlust=2,
                ew=200000, nw=.3, en=200000, nn=.3, mu=.2, t=100)


def _geometrie(daten):
    return {k: daten[k] for k in SITZGEOMETRIE}


@pytest.mark.parametrize("daten,geo,effektiv", [
    ({}, (18, 34), (16, 32)),
    (dict(ei_w=-12, es_w=4, ei_n=-6, es_n=0), (-12, 10), (0, 8)),
    (dict(ei_w=-18, es_w=-6, ei_n=-2, es_n=0), (-18, -4), (0, 0)),
    (dict(ei_w=-12, es_w=-8, ei_n=-24, es_n=-20, verlust=0), (8, 16), (8, 16)),
])
def test_fertigungsgrenzen_bis_zur_drehmomentreserve(daten, geo, effektiv):
    e = berechne("sitzgrenzen", {**REFERENZ, **daten})
    assert (e["ug_min"], e["ug_max"]) == geo and (e["umin"], e["umax"]) == effektiv
    # Bei gleichem Werkstoff und Radienverhaeltnis 1:2 ist p = 3 E U / (8 d).
    p1, p2 = (3*200000*(u/1000)/(8*20) for u in effektiv)
    assert e["ug_req"] == pytest.approx(14.14710605+daten.get("verlust", 2))
    kapazitaet = .2*p1*(pi*20*15)*.010
    assert [e[k] for k in ("p1", "p2", "t1", "t_res")] == pytest.approx([p1, p2, kapazitaet, kapazitaet-100])


def _pruefe_assembly(pfad, werte):
    e = lade_alles(str(pfad))
    wurzel, = e.baum.kinder
    assert "AP242" in e.modell.datei.schema and wurzel.name == tr("Pressverband")
    teile = {k.name: k for k in wurzel.blaetter()}
    assert set(teile) == {tr("Welle"), tr("Nabe")}
    nativ = lies_pmi_xcaf(e.modell)
    assert len(nativ) == len(e.pmi) == len(e.grafik) == 5
    sitze = []
    d, da, l = (werte[k] for k in ("d", "da", "l"))
    for name, teil in teile.items():
        assert BRepCheck_Analyzer(teil.form).IsValid()
        ring = name == tr("Nabe")
        g = GProp_GProps()
        brepgprop.VolumeProperties(teil.form, g)
        assert g.Mass() == pytest.approx(pi*l*(da**2-d**2 if ring else d**2)/4)
        sitze.extend(erkenne(teil.form, teil.nummer, name))
        ids = {e.modell.flaechen_index(f) for f in _flaechen(teil.form)}
        for quelle in (e.pmi, nativ):
            masse = [p for p in quelle if p.flaechen and p.flaechen <= ids]
            assert len(masse) == (3 if ring else 2)
            passung, = [p for p in masse if p.grenzmass]
            index, = passung.flaechen
            sitz = e.modell.flaechen[index]
            s = BRepAdaptor_Surface(sitz)
            assert s.GetType() == GeomAbs_Cylinder and 2*s.Cylinder().Radius() == pytest.approx(d)
            assert (sitz.Orientation() == TopAbs_REVERSED) == ring
            suffix = "_n" if ring else "_w"
            assert passung.grenzen() == pytest.approx([d+werte[k+suffix]/1000 for k in ("es", "ei")])
            if quelle is e.pmi:
                assert passung.nennwert == pytest.approx(d)
            laenge, = [p for p in masse if p.typ == "Location_LinearDistance"]
            assert laenge.nennwert == pytest.approx(l) and len(laenge.flaechen) == 2
            assert all(BRepAdaptor_Surface(e.modell.flaechen[i]).GetType() == GeomAbs_Plane for i in laenge.flaechen)
            if ring:
                mantel, = [p for p in masse if p.nennwert == da]
                i, = mantel.flaechen
                assert 2*BRepAdaptor_Surface(e.modell.flaechen[i]).Cylinder().Radius() == pytest.approx(da)
    paar, = paare(sitze)
    assert paar.ueberdeckung_mm == pytest.approx(l) and paar.differenz_mm == pytest.approx(0)
    grafik_ids = set()
    for p in e.pmi:
        assert p.semantisch and p.grafisch
        (gid, g), = [(i, g) for i, g in e.grafik.items() if p.step_id in g.pmi_ids]
        assert g.linien and g.dreiecke and not g.erzeugt
        grafik_ids.add(gid)
    assert len(grafik_ids) == 5


@pytest.mark.parametrize("abmasse", [{}, dict(ei_w=-12, es_w=-8, ei_n=-24, es_n=-20)])
def test_flaechenbezogene_grenzen_je_bauteil(tmp_path, abmasse):
    daten = {**REFERENZ, **abmasse}
    ziel = tmp_path/"Pressverband.step"
    assert schreibe_pressverband(ziel, **_geometrie(daten)) == 5
    _pruefe_assembly(ziel, daten)


def test_ungueltige_grenzen_erhalten_datei(tmp_path):
    assert berechne("sitzgrenzen", {**REFERENZ, "t": 0})["ug_req"] == 0
    ziel = tmp_path/"Sitz.step"
    ziel.write_bytes(b"vorhanden")
    for diff in (dict(da=20), dict(ei_w=50), dict(es_n=-10), dict(ei_n=-21000),
                 dict(es_n=21000), dict(ei_w=float("nan")), dict(l=0)):
        with pytest.raises(ValueError):
            schreibe_pressverband(ziel, **_geometrie({**REFERENZ, **diff}))
        assert ziel.read_bytes() == b"vorhanden"
    assert list(tmp_path.iterdir()) == [ziel]
    with pytest.raises(ValueError, match="verlust"):
        berechne("sitzgrenzen", {**REFERENZ, "verlust": -.01})


def test_auslegung_ohne_modell_speichern_und_step(fenster, tmp_path, monkeypatch):
    from programm.ui.maschinenelemente_ui import AuslegungFenster
    fenster.aktionen["maschinenelement"].trigger()
    f, = fenster.findChildren(AuslegungFenster)
    f.wahl.setCurrentIndex(f.wahl.findData("sitzgrenzen"))
    assert f.step.isVisible() and not f.step.isEnabled()
    for k, v in _geometrie(REFERENZ).items():
        f.felder[k].setText(str(v))
    assert f.step.isEnabled() and not f.speichern.isEnabled()
    ziel = tmp_path/"Sitzpaar.step"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a: (str(ziel), ""))
    f.step.click()
    _pruefe_assembly(ziel, REFERENZ)
    for k, v in REFERENZ.items():
        f.felder[k].setText(str(v).replace(".", ","))
    assert f.daten["ergebnisse"]["t_res"] == pytest.approx(13.09733553)
    ziel = tmp_path/"Entwurf.json"
    f._speichern()
    gespeichert = json.loads(ziel.read_text())
    f.felder["es_n"].setText("-10")
    assert f.daten is None and not f.step.isEnabled()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a: (str(ziel), ""))
    f._oeffnen()
    assert f.daten == gespeichert and f.daten["eingaben"] == REFERENZ
    f.felder["t"].setText("125")
    assert f.daten["ergebnisse"]["t_res"] == pytest.approx(-11.90266447)
    assert tr("Am unteren Passungsgrenzfall reicht das Reibmoment für das geforderte Drehmoment nicht aus.") in f.ergebnis.text()
