"""Einseitige ebene Anschlaege im linearen Modell der Baugruppen-Messgroessen."""

import numpy as np
import pytest
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.TopoDS import topods
from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt

from programm.kern import baugruppe_mass as bm
from programm.kern import verbindung as vb


def _flaechen():
    pl = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    ebene = BRepBuilderAPI_MakeFace(pl, -1., 1., -1., 1.).Face()
    return topods.Face(ebene.Reversed()), ebene


def _auflage(spalt=0., kippen=0.):
    a, b = _flaechen()
    bg = vb.Baugruppe()
    v = bg.verbinde(2, a, 0, 1, b, 1, spalt)
    bg.setze_toleranz(v.nummer, .3, kippen)
    m = bg.neue_messgroesse(2, a, 0, 1, b, 1)
    return bg, v, m, a, b


def test_kontakt_worst_case_und_erstanschlag():
    bg, v, m, a, b = _auflage(.1)
    frei = bm.Analyse(bg).berechne(m, a, b)
    assert frei.wc_min == pytest.approx(-.2)
    v.einseitig = True
    analyse = bm.Analyse(bg)
    assert not analyse.kontakt_hinweise and len(analyse.kontakte[v.nummer]) == 4
    e = analyse.berechne(m, a, b)
    assert (e.wc_min, e.wc_max) == pytest.approx((0., .4))
    np.testing.assert_allclose(e.proben, np.maximum(0., frei.proben), atol=1e-12)
    assert e.beitraege[0].bereich == pytest.approx(.4)
    assert e.beitraege[0].anteil_var == pytest.approx(1.)
    v.bonus = .1
    mit = bm.Analyse(bg).berechne(m, a, b)
    assert (mit.wc_min, mit.wc_max) == pytest.approx((0., .5))
    assert mit.proben.min() >= -1e-12
    assert next(x.bereich for x in mit.beitraege if x.bonus) == pytest.approx(.2)


def test_kippende_auflage_spalt_an_jeder_ecke():
    bg, v, m, a, b = _auflage(kippen=.1)
    v.einseitig = True
    analyse = bm.Analyse(bg)
    ecken = [bg.neue_messgroesse(2, a, 0, 1, b, 1, punkt=np.array([x, y, 0.]))
             for x in (-1., 1.) for y in (-1., 1.)]
    for messung in ecken:
        e = analyse.berechne(messung, a, b, proben=5000)
        # Nennspalt 0, Maximum = 0.3 + 0.1 * 1 + 0.1 * 1 an der Ecke.
        assert (e.wc_min, e.wc_max) == pytest.approx((0., .5))
        assert e.proben.min() >= -1e-12
    daten = bg.als_dict()
    bg.lade(daten, lambda teil, _: a if teil == 2 else b)
    assert bg.verbindungen[0].einseitig
    del daten["verbindungen"][0]["einseitig"]
    bg.lade(daten, lambda teil, _: a if teil == 2 else b)
    assert not bg.verbindungen[0].einseitig


def test_kontakt_am_gemeinsamen_sockel_bremst_nur_das_zugehoerige_teil():
    bg, v, m, a, b = _auflage()
    anderes = bg.verbinde(3, a, 2, 1, b, 1, .2)
    bg.setze_toleranz(anderes.nummer, .1)
    m2 = bg.neue_messgroesse(3, a, 2, 1, b, 1)
    ohne = bm.Analyse(bg).berechne(m2, a, b, proben=2000)
    v.einseitig = True
    mit = bm.Analyse(bg).berechne(m2, a, b, proben=2000)
    np.testing.assert_array_equal(mit.proben, ohne.proben)


def test_kontakt_begrenzt_nur_die_gemeinsame_auflage():
    bg, v, _, a, b = _auflage(kippen=.1)
    pl = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    rechts = BRepBuilderAPI_MakeFace(pl, 0., 1., -1., 1.).Face()
    bg.formen[v.nummer] = (a, rechts)
    v.einseitig = True
    # Am linken Ende ragt die Platte ueber die Unterlage hinaus und darf unter deren Ebene kippen.
    m = bg.neue_messgroesse(2, a, 0, 1, rechts, 1, punkt=np.array([-1., 0., 0.]))
    e = bm.Analyse(bg).berechne(m, a, rechts)
    assert e.wc_min == pytest.approx(-.1)
    links = BRepBuilderAPI_MakeFace(pl, -5., -4., -1., 1.).Face()
    bg.formen[v.nummer] = (a, links)
    assert bm.Analyse(bg).kontakt_hinweise


def test_messgroesse_ohne_verbindungen_ist_unbestimmt():
    a, b = _flaechen()
    bg = vb.Baugruppe()
    m = bg.neue_messgroesse(2, a, 0, 1, b, 1)
    e = bm.Analyse(bg).berechne(m, a, b)
    assert e.unbestimmt and e.wc_min == e.wc_max == e.nenn
    m.teil_b = m.teil_a
    assert not bm.Analyse(bg).berechne(m, a, b).unbestimmt
    bg.verbinde(2, a, 0, 1, b, 1)
    bg.verbinde(4, a, 2, 3, b, 3)
    m.teil_b = 4
    assert bm.Analyse(bg).berechne(m, a, b).unbestimmt
