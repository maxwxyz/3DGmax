"""Kraftfluss ueber Zwischenwellen, getrennte Zuege und gemischte Stufen."""

import math

import numpy as np
import pytest

from programm.kern import verzahnung_daten as vd
from programm.kern.verzahnung import Paar, Verzahnung, paare
from programm.kern.verzahnung_sonder import Sonderprofil


def _rad(name, z, x, ort=0., y=0.):
    return Verzahnung(name, np.array([x, y, ort]), np.array([0., 0., 1.]), False,
                      z, z + 2., z - 2.5, 4., mn=1., d=float(z), alpha_n=20.,
                      db=z * math.cos(math.radians(20)))


def test_kraftfluss_mit_zwei_zuegen_und_bezugswechsel(tmp_path, app):
    from programm.ui.verzahnung_ui import VerzahnungFenster
    liste = [_rad("Abtrieb", 36, 47), _rad("Zwischenritzel", 12, 23), _rad("Eingang", 16, 0, 8),
             _rad("Zwischenrad", 30, 23, 8), _rad("Nebenritzel", 10, 200), _rad("Nebenrad", 20, 215)]
    p = paare(liste)
    d = vd.datenblatt(liste, p)["kraftfluss"]
    assert len(d["zuege"]) == 2
    k = next(z for z in d["zuege"] if len(z["stufen"]) == 2)
    assert d["wellen"][k["bezugswelle"]] == [2]
    assert k["wellenwerte"]["0"] == {"i": 5.625, "richtung": 1}
    f = VerzahnungFenster(liste, str(tmp_path / "getriebe"))
    f.bezugswelle.setCurrentIndex(f.bezugswelle.findData(0))
    import json
    daten = json.loads(open(f.speichere("json", str(tmp_path / "antrieb.json"))).read())
    k = next(z for z in daten["kraftfluss"]["zuege"] if len(z["stufen"]) == 2)
    assert k["bezugswelle"] == 0 and k["wellenwerte"]["2"]["i"] == pytest.approx(1/5.625)
    from pypdf import PdfReader
    pdf = PdfReader(f.speichere("pdf", str(tmp_path / "antrieb.pdf")))
    assert "0.17778" in " ".join(s.extract_text() for s in pdf.pages)
    assert "0.17778" in open(f.speichere("csv", str(tmp_path / "antrieb.csv")), encoding="utf-8-sig").read()
    f.close()


def test_verzweigte_und_widerspruechliche_kraftfluesse():
    from programm.kern.verzahnung_auslegung import getriebe_befunde
    raeder = [_rad("A", 12, 0), _rad("B", 24, 18), _rad("C", 24, -18), _rad("D", 24, 0, y=18)]
    def paar(i, j):
        return Paar(raeder[i], raeder[j], 18., 18., 20., 1.5, 0., 0.)
    stern = [paar(0, j) for j in (1, 2, 3)]
    assert not any(b.thema == "Stufenaufteilung" for b in getriebe_befunde(raeder, stern))
    zyklus = stern + [paar(1, 2)]
    daten = vd.datenblatt(raeder, zyklus)["kraftfluss"]["zuege"][0]
    assert daten["widerspruch"] and not daten["wellenwerte"]


def test_kegel_und_stirnradstufe_gemeinsam():
    def kegel(name, z, r, n):
        delta = math.atan(r)
        richtung = np.array(n, dtype=float)
        axial = 18 * math.cos(delta)
        kopf = 18 * math.sin(delta) + .9
        breite = 7 * math.cos(delta)
        return Sonderprofil(name, "konisch", z, richtung * axial, richtung, breite,
                            (kopf, kopf + r * breite), (kopf - 1.8, kopf - 1.8 + r * breite), 0.)
    a, b = kegel("Kegelritzel", 12, .5, [1,0,0]), kegel("Kegelrad", 24, 2., [0,0,1])
    liste = [a, b, _rad("Ritzel", 16, 0, 30), _rad("Rad", 32, 24, 30)]
    d = vd.datenblatt(liste, paare(liste), 0)["kraftfluss"]
    zug = d["zuege"][0]
    assert len(zug["stufen"]) == 2 and not zug["widerspruch"]
    assert zug["wellenwerte"]["2"] == {"i": 4., "richtung": None}


def test_menue_getriebe_und_einzelrad_aus_mesh(fenster, tmp_path, app):
    from tests.test_verzahnung_mesh import _radnetz, _schreibe
    pfad = tmp_path / "Zwei_Stufen.obj"
    _schreibe(pfad, [_radnetz(14), _radnetz(20, 34), _radnetz(16, 34, 10), _radnetz(24, 74, 10)])
    einzel = tmp_path / "Einzelrad.stl"
    _schreibe(einzel, [_radnetz(17)])
    fenster.lade(str(pfad), warten=True)
    fenster.modell_hinzufuegen(str(einzel), warten=True)
    knoten = list(fenster.erg.baum.blaetter())[-1]
    fenster.baum.zeige_knoten(knoten.nummer)
    assert fenster.baum.gewaehlte_blaetter() == {knoten.nummer}
    for aktion, zaehne in (("verzahnung", [17]), ("getriebe", [14, 16, 17, 20, 24])):
        fenster.aktionen[aktion].trigger()
        assert fenster._verzahnung_lader.wait(30000)
        app.processEvents()
        dialog = fenster._verzahnung
        assert sorted(v.z for v in dialog.liste) == zaehne
        if aktion == "getriebe":
            assert dialog.reiter.currentWidget() is dialog.getriebeseite
            assert dialog.getriebe_tabelle.rowCount() == 5
        else:
            assert dialog.reiter.currentWidget() is dialog.tabelle
        dialog.close()
