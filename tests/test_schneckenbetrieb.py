"""Drehzahlen am Schneckenpaar aus Einbaulage und Hand, auch im mehrstufigen Betriebspunkt."""

import csv
import json
import math

import numpy as np
import pytest

from programm.kern import verzahnung as vz
from programm.kern.getriebe_betrieb import Betriebsmodell
from programm.kern.verzahnung_sonder import Sonderprofil, Taillenrad


def _paar(hand=1, seite=1):
    # Die Schnecke liegt parallel X auf der Seite +/-Y des Rads, die Radachse liegt parallel Z.
    hub, r1 = 14., 4.2
    r2 = 18 * hub / (4 * math.pi)
    schnecke = Sonderprofil("Schraube", "schraube", 2, np.array([-14., seite * (r1 + r2), 4.]),
                            np.array([1., 0, 0]), 28., (5.2, 5.2), (3.1, 3.1), hand * 4 * math.pi)
    rad = Taillenrad("Rad", 18, np.array([0., 0., 4.]), np.array([0., 0, 1.]), 8., r2 + .9, r2 - .9,
                     .8, hand * hub / (2 * math.pi * r1 * r2))
    return schnecke, rad


@pytest.mark.parametrize("hand,seite", [(1, 1), (-1, 1), (1, -1), (-1, -1)])
def test_schneckenhand_eingriffsseite_und_stirnradabtrieb(hand, seite):
    from tests.test_getriebezug import _rad
    schnecke, rad = _paar(hand, seite)
    # Das Stirnritzel sitzt auf der Welle des Schneckenrads.
    teile = [schnecke, rad, _rad("Ritzel", 16, 0, 30), _rad("Abtrieb", 32, 24, 30)]
    modell = Betriebsmodell(teile, vz.paare(teile))
    b = modell.betrieb()
    w, r, zwischen, aus = (modell.welle[i] for i in range(4))
    assert zwischen == r and set(b.ports) == {w, r, aus}
    # Rechte Schraube um +X: Kamm wandert nach -X. Am oberen Rand (+Y) dreht das Rad damit um +Z.
    erwartet = hand * seite * 100
    def drehzahlen(vorgabe):
        return {v["id"]: v["drehzahl"] for v in b.auswerten(vorgabe, [])["wellen"]}
    assert drehzahlen({w: 900}) == {w: 900, r: erwartet, aus: -erwartet / 2}
    assert drehzahlen({aus: erwartet / 2}) == {w: -900, r: -erwartet, aus: erwartet / 2}
    assert all(n is None for n in drehzahlen({}).values())
    assert all(v["status"] == "widerspruch" for v in b.auswerten({w: 900, r: -erwartet}, [])["wellen"])


def test_koordinatensystem_und_achsdefinition():
    from scipy.spatial.transform import Rotation
    w, r = _paar()
    # Die gedrehte X-Achse hat eine negative Hauptkomponente, die gedrehte Z-Achse eine positive.
    drehen = Rotation.from_euler("zyx", [140., 15., 28.], degrees=True)
    for v in (w, r):
        v.richtung = drehen.apply(v.richtung)
        v.punkt = drehen.apply(v.punkt) + [218., -754., 86.]
    # Andere Wahl der Rohachsen (Schrauben-Messstrecke vom anderen Ende aus). Die Hand bleibt rechts.
    w.punkt += w.breite * w.richtung
    w.richtung *= -1
    r.richtung *= -1
    b = Betriebsmodell([r, w], []).betrieb()
    assert b.positive_achse(1) @ drehen.apply([1., 0, 0]) < -.999
    assert b.positive_achse(0) @ drehen.apply([0., 0, 1.]) > .999
    assert b.auswerten({1: 900}, [])["wellen"][0]["drehzahl"] == -100


def test_ungepaarte_schraube_und_unpassende_hand():
    w, r = _paar()
    assert not Betriebsmodell([w], []).betrieb().ports
    r.spursteigung *= -1
    assert not Betriebsmodell([w, r], []).betrieb().ports


@pytest.fixture(scope="module")
def schneckenbaugruppe():
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from tests.test_verzahnung_sonder import _referenz

    w, r = _paar(hand=-1)
    schraube = _referenz(w.z, w.kopf[0], 2.1, w.breite, w.phase / w.breite, lagen=80, kerbe=True)
    rad = _referenz(r.z, r.kopf, 1.8, r.breite, r.spursteigung, lagen=17, kehle=.075)
    lage = gp_Trsf()
    lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 1, 0)), math.pi / 2)
    lage.SetTranslationPart(gp_Vec(*w.punkt))
    form = TopoDS_Compound()
    bauer = BRep_Builder()
    bauer.MakeCompound(form)
    bauer.Add(form, schraube.Moved(TopLoc_Location(lage)))
    bauer.Add(form, rad)
    return form


@pytest.mark.parametrize("endung", ["step", "stl"])
def test_importierter_linker_schneckentrieb(schneckenbaugruppe, tmp_path, endung):
    from programm.kern.laden import lade_modell
    pfad = str(tmp_path / f"schneckenstufe.{endung}")
    if endung == "step":
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
        writer = STEPControl_Writer()
        assert writer.Transfer(schneckenbaugruppe, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(pfad) == IFSelect_RetDone
    else:
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.StlAPI import StlAPI_Writer
        BRepMesh_IncrementalMesh(schneckenbaugruppe, .01)
        assert StlAPI_Writer().Write(schneckenbaugruppe, pfad)
    teile = list(vz.erkenne_koerper(lade_modell(pfad).form, "Getriebe", steckprofile=True, sonderprofile=True))
    assert sorted(v.z for v in teile) == [2, 18]
    b = Betriebsmodell(teile, vz.paare(teile)).betrieb()
    stufe, = b.schneckenstufen
    assert stufe["hand"] == "links"
    w, r = stufe["wellen"]
    werte = {v["id"]: v["drehzahl"] for v in b.auswerten({w: 900}, [])["wellen"]}
    assert werte == {w: 900, r: -100}


def test_betriebspunkt_richtungen_im_export(tmp_path, app):
    from pypdf import PdfReader
    from programm.ui.verzahnung_ui import VerzahnungFenster
    from tests.test_betriebspunkt_ui import _vorgabe

    f = VerzahnungFenster(_paar(hand=-1), "")
    seite = f.betriebspunkt
    assert f.reiter.isTabVisible(f.reiter.indexOf(seite))
    assert "n2/n1 = -0.111111111" in seite.schneckenhinweis.text()
    _vorgabe(seite, 0, 900)
    f.speichere("json", str(tmp_path / "paar.json"))
    export = json.loads((tmp_path / "paar.json").read_text())["betriebspunkt"]
    assert export["schneckenstufen"][0]["n_rad_durch_n_schnecke"] == pytest.approx(-1 / 9)
    assert not export["schneckenstufen_ausgenommen"]
    assert [(w["rollen"], w["drehzahl"], w["positive_achse"]) for w in export["wellen"]] == [
        (["schnecke"], 900., [1, 0, 0]), (["schneckenrad"], -100., [0, 0, 1])]
    f.speichere("csv", str(tmp_path / "paar.csv"))
    with (tmp_path / "paar.csv").open(encoding="utf-8-sig") as datei:
        zeilen = list(csv.reader(datei, delimiter=";"))
    assert any("Schneckenrad" in z[0] and "-100" in z for z in zeilen if z)
    pdf = PdfReader(f.speichere("pdf", str(tmp_path / "paar.pdf")))
    assert any("Betriebspunkt" in (s := seite.extract_text()) and "-100" in s and "Schneckenrad" in s for seite in pdf.pages)
    f.close()
