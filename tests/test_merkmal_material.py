"""Materialbonus und Mantelversatz derselben Bohrung bzw. desselben Zapfens in der 3D-Messung."""

import numpy as np
import pytest
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCC.Core.gp import gp_Pnt

from programm.kern import baugruppe_mass as bm, verbindung as vb
from programm.kern.pmi import BezugsRef, Pmi
from tests.test_merkmalstreuung import _datum, _flaeche


def _fall(innen, material, wert=.2, mantel=True):
    block = BRepPrimAPI_MakeBox(gp_Pnt(-10, -10, 0), 20, 20, 20).Shape()
    zapfen = BRepPrimAPI_MakeCylinder(3., 20.).Shape()
    f = _flaeche(BRepAlgoAPI_Cut(block, zapfen).Shape() if innen else zapfen)
    gegen = _flaeche(block, [1, 0, 0])
    bg = vb.Baugruppe()
    bg.verbinde(1, f, 7, 2, f, 8)
    m = bm.Messgroesse(1, 1, 1, 2, 2, art=bm.ACHSE_EBENE,
                        punkt=[3., 0., 10.] if mantel else None, soll_min=-100., soll_max=100.)
    pos = Pmi("toleranz", "Position", wert=wert, zone="Diameter", material=material,
              bezuege=[BezugsRef("A")], flaechen={1})
    mass = Pmi("mass", "Size_Diameter", nennwert=6., oben=.2, unten=-.2, flaechen={1})
    return bg, m, f, gegen, [pos, mass, _datum(7, "A")]


@pytest.mark.parametrize(("innen", "mat", "lo", "hi"),
                         [(False, "M", -.4, .2), (True, "L", -.4, .2),
                          (False, "L", -.2, .4), (True, "M", -.2, .4)])
def test_gemeinsames_istmass_fuer_bonus_und_mantel(innen, mat, lo, hi):
    bg, m, f, gegen, pmi = _fall(innen, mat)
    analyse = bm.Analyse(bg, pmi)
    e = analyse.berechne(m, f, gegen, zufall=5)
    assert not e.hinweise and bm.bewertung(e, m)[0] == "gruen"
    assert (e.wc_min - e.nenn, e.wc_max - e.nenn) == pytest.approx((lo, hi))
    anteil, = [b for b in e.beitraege if b.flaeche == 1]
    assert anteil.bereich == pytest.approx(hi - lo)
    # Analytische Einzelproben: dasselbe Istmass bestimmt radialen Versatz und den Bonus.
    rng = np.random.default_rng(12)
    d = np.clip(rng.normal(6., .4 / 6., len(e.proben)), 5.8, 6.2)
    bonus = d - 5.8 if (mat == "M") == innen else 6.2 - d
    erwartet = (d - 6.)/2 + np.clip(rng.standard_normal(len(d)), -3., 3.) * ((.2 + bonus) / 6)
    np.testing.assert_allclose(e.proben - e.nenn, erwartet, atol=1e-12)
    glied = analyse.als_kette3d(m, f, gegen).glieder[-1]
    assert (glied.werte["z"].unten, glied.werte["z"].oben) == pytest.approx((lo, hi))


def test_nulltoleranz_mit_materialbedingung_und_obergrenze():
    bg, m, f, gegen, pmi = _fall(True, "M", wert=0., mantel=False)
    pmi[0].maximum_toleranz = .16
    pmi[0].modifikatoren = ["Maximum_Material_Requirement"]
    e = bm.Analyse(bg, pmi).berechne(m, f, gegen)
    assert not e.hinweise
    assert (e.wc_min - e.nenn, e.wc_max - e.nenn) == pytest.approx((-.08, .08))


def test_gekoppelte_verteilung_nach_uebergabe_und_json_rundlauf_der_kette():
    import json
    from programm.kern import kette3d
    bg, m, f, gegen, pmi = _fall(False, "L")
    analyse = bm.Analyse(bg, pmi)
    e = analyse.berechne(m, f, gegen, proben=500, zufall=3)
    gespeichert = json.loads(json.dumps(kette3d.als_dict(analyse.als_kette3d(m, f, gegen))))
    kette = kette3d.von_dict(gespeichert)
    np.testing.assert_allclose(kette3d.monte_carlo(kette, 500, zufall=10), e.proben, atol=1e-12)
    # Geaenderte Eingaben der Kette haben Vorrang vor dem importierten Materialmodell.
    kette.glieder[-1].werte["z"].unten = kette.glieder[-1].werte["z"].oben = 0.
    np.testing.assert_allclose(kette3d.monte_carlo(kette, 30), e.nenn)


def test_simultane_maximal_und_minimalmaterial_bedingungen_werden_bei_mittlerem_mass_kritisch():
    from dataclasses import replace
    bg, m, f, gegen, pmi = _fall(False, "L", mantel=False)
    pmi.append(replace(pmi[0], material="M"))
    e = bm.Analyse(bg, pmi).berechne(m, f, gegen)
    # Beide Zonen haben bei D=6 je 0.2 Grundtoleranz und 0.2 Bonus.
    assert not e.hinweise and e.wc_max - e.wc_min == pytest.approx(.4)


@pytest.mark.parametrize("fehler", ["groesse_fehlt", "falsches_mass", "widerspruch", "obergrenze", "bezugsgrenze"])
def test_materialbedingung_offen_bei_ungeklaerten_eingaben(fehler):
    bg, m, f, gegen, pmi = _fall(True, "M")
    if fehler == "groesse_fehlt":
        del pmi[1]
    elif fehler == "falsches_mass":
        pmi[1].nennwert = 8.
    elif fehler == "widerspruch":
        pmi[1].oben = -.3
    elif fehler == "obergrenze":
        pmi[0].maximum_toleranz = .05
    else:
        pmi[0].bezuege[0].modifikatoren = ["MaximumMaterialRequirement"]
    analyse = bm.Analyse(bg, pmi)
    e = analyse.berechne(m, f, gegen)
    assert e.hinweise and not bm.bewertung(e, m)[0]
    assert analyse.als_kette3d(m, f, gegen).hinweise == e.hinweise
