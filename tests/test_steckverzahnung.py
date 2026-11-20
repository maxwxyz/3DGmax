"""Steckprofile von Welle und Nabe an geometrisch bekannten Beispielen."""

import json

import numpy as np
import pytest

from programm.kern import passverzahnung as pv
from programm.kern import verzahnung as vz
from werkzeuge import zahnrad as zr


@pytest.mark.parametrize("winkel,innen,rund", [(30, False, 0.0), (37.5, True, 0.0), (45, False, 0.18)])
def test_evolventen_steckprofil(winkel, innen, rund):
    kontur = zr.evolventen_steck(24, 1.25, winkel, 0.0, 31.2, 28.5, rund=rund)
    profil = vz.erkenne(zr.steckteil(kontur, 8.0, innen=innen), "E", steckprofile=True)
    assert isinstance(profil, pv.Steckprofil) and profil.art == "evolvente"
    assert profil.innen == innen and profil.z == 24 and profil.alpha == winkel
    assert profil.modul == pytest.approx(1.25, abs=0.002)
    assert profil.db == pytest.approx(30*np.cos(np.radians(winkel)), abs=0.02)
    assert profil.b == pytest.approx(8.0, abs=0.01)
    assert profil.fussform == ("gerundet" if rund else "flach")


def test_kerbprofil_und_zahnrad_trennen():
    kerbe = zr.steckteil(zr.kerb_steck(27, 33.0, 30.0, 60.0), 6.0, innen=True)
    profil = vz.erkenne(kerbe, "Nabe", steckprofile=True)
    assert isinstance(profil, pv.Steckprofil) and profil.art == "kerb"
    assert profil.z == 27 and profil.innen and profil.winkel == pytest.approx(60.0, abs=0.1)
    assert profil.modul is None
    rad = vz.erkenne(zr.zahnrad(23, 2.0, 10.0), "Rad", steckprofile=True)
    assert isinstance(rad, vz.Verzahnung) and rad.mn == pytest.approx(2.0, abs=.002)


def test_keilpaar_lader_fenster_und_export(app, tmp_path):
    from dataclasses import replace
    from programm.ui.verzahnung_ui import VerzahnungFenster, VerzahnungLader
    w = zr.steckteil(zr.keil_steck(6, 23.0, 26.0, 6.0), 8.0)
    n = zr.steckteil(zr.keil_steck(6, 23.2, 26.25, 6.0), 7.0, innen=True)
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0.2, 0.8, 0.5)), 0.7)
    t.SetTranslationPart(gp_Vec(140, 35, -52))
    w, n = w.Moved(TopLoc_Location(t)), n.Moved(TopLoc_Location(t))
    lader = VerzahnungLader([("W", w), ("N", n)])
    liste = []
    lader.fertig.connect(liste.extend)
    lader.run()
    assert len(liste) == 2
    welle, nabe = liste
    assert welle.art == nabe.art == "keil" and not welle.innen and nabe.innen
    assert welle.keilbreite == pytest.approx(6.0, abs=0.003)
    paar, = pv.paare(liste)
    assert paar.flanke == pytest.approx(0, abs=0.005)
    assert paar.innen == pytest.approx(0.2, abs=0.015)
    assert paar.aussen == pytest.approx(0.25, abs=0.005)
    assert paar.zentrierung == "flanke"
    assert not pv.paare([welle, replace(nabe, mitte=nabe.mitte+20*nabe.achse)])
    assert not pv.paare([welle, replace(nabe, z=8)])
    f = VerzahnungFenster(liste, str(tmp_path / "paar"))
    try:
        assert f.paar_tabelle.columnCount() == 1 and not f.rexs.isEnabled()
        assert f.paar_tabelle.rowCount() >= 6
        f.speichere("json", str(tmp_path/"paar.json"))
        daten = json.loads((tmp_path/"paar.json").read_text())
        assert not daten["zahnraeder"] and len(daten["steckprofile"]) == 2 and len(daten["steckpaare"]) == 1
        assert daten["steckpaare"][0]["zentrierung"] == "flanke"
        assert len(daten["auslegungsbefunde"]) == 3
        f.speichere("csv", str(tmp_path/"paar.csv"))
        assert "Steckverbindung" in (tmp_path/"paar.csv").read_text(encoding="utf-8-sig")
    finally:
        f.close()


@pytest.mark.parametrize("d_min,d_max,erwartet", [(23.0, 26.25, "innen"), (23.2, 26.0, "aussen"),
                                                (23.2, 26.25, "offen"), (23.2, 25.9, "uebermass")])
def test_durchmesserzentrierung_und_unklare_spiele(d_min, d_max, erwartet):
    welle = vz.erkenne(zr.steckteil(zr.keil_steck(6, 23.0, 26.0, 6.0), 8.0), steckprofile=True)
    nabe = vz.erkenne(zr.steckteil(zr.keil_steck(6, d_min, d_max, 6.1), 8.0, innen=True), steckprofile=True)
    paar, = pv.paare([welle, nabe])
    assert paar.zentrierung == erwartet
