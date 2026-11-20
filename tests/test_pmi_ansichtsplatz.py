"""Anordnung erzeugter PMI in gemeinsam sichtbaren gespeicherten Ansichten."""

from types import SimpleNamespace

import numpy as np
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods

from programm.kern import pmi_erzeugen as pe
from programm.kern.ansichten import Ansicht
from programm.kern.pmi import BEZUG, MASS, Pmi
from programm.kern.praesentation import Grafik


def _wuerfel():
    form = BRepPrimAPI_MakeBox(30, 20, 10).Shape()
    flaechen = []
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        flaechen.append(topods.Face(ex.Current()))
        ex.Next()
    return SimpleNamespace(form=form, flaechen=flaechen)


def _box(punkte, ansicht):
    proj = punkte @ np.column_stack(pe.ansicht_ebene(ansicht)[:2])
    return proj.min(axis=0), proj.max(axis=0)


def _getrennt(a, b):
    return np.any((a[1] < b[0]) | (b[1] < a[0]))


def test_bezugsrahmen_auch_in_zweiter_ansicht_getrennt():
    modell = _wuerfel()
    fl = [i for i, f in enumerate(modell.flaechen) if abs(pe._richtung_element([f])[2]) > 0.99]
    pmi = [Pmi(BEZUG, "Datum", name=name, flaechen={fi}, step_id=i)
           for i, (name, fi) in enumerate(zip(("A", "B"), fl), 1)]
    oben = Ansicht("Oben", 10, pmi_ids={1, 2})
    grafik = pe.ergaenze(pmi, {}, modell, [oben])
    a, b = (g.linien[1][:4] for g in grafik.values())
    assert _getrennt(_box(a, oben), _box(b, oben))
    # Blick entlang der Rahmenmitten: trotz verschiedener Tiefe decken sich die Projektionen.
    blick = b.mean(axis=0) - a.mean(axis=0)
    seite = Ansicht("Schraeg", 11, richtung=tuple(blick / np.linalg.norm(blick)), oben=(0, 1, 0), pmi_ids={1, 2})
    assert not _getrennt(_box(a, seite), _box(b, seite))
    neu = pe.ergaenze(pmi, {}, modell, [oben, seite])
    a, b = (g.linien[1][:4] for g in neu.values())
    assert all(_getrennt(_box(a, ansicht), _box(b, ansicht)) for ansicht in (oben, seite))


def test_masslinie_weicht_sichtbarer_dateigrafik_aus():
    modell = _wuerfel()
    fl = {i for i, f in enumerate(modell.flaechen) if abs(pe._richtung_element([f])[0]) > 0.99}
    mass = Pmi(MASS, "Size_Thickness", nennwert=30, flaechen=fl, step_id=7)
    g = pe.ergaenze([mass], {}, modell)[-1]
    ph = g.platzhalter[0]
    blick = -g.ebene[3]
    ansicht = Ansicht("Breite", 11, richtung=tuple(blick), oben=tuple(ph.y), pmi_ids={7, 8})
    x, y = ph.x * ph.breite, ph.y * ph.hoehe
    ecken = ph.ursprung + np.array([0 * x, x, x + y, y])
    # Der vorhandene Rahmen steht tiefer im Modell, im Bild aber ueber dem Masstext.
    dateigrafik = Grafik(99, linien=[ecken + 40 * blick], fertig=True, pmi_ids={8})
    neu = pe.ergaenze([mass], {99: dateigrafik}, modell, [ansicht])[-1]
    np.testing.assert_allclose(np.linalg.norm(neu.linien[2][1] - neu.linien[2][0]), 30)
    text = neu.platzhalter[0].ursprung + np.array([0 * x, x, x + y, y])
    assert _getrennt(_box(text, ansicht), _box(dateigrafik.linien[0], ansicht))
    ansicht.pmi_ids.remove(8)
    ohne = pe.ergaenze([mass], {99: dateigrafik}, modell, [ansicht])[-1]
    np.testing.assert_allclose(ohne.platzhalter[0].ursprung, ph.ursprung)
