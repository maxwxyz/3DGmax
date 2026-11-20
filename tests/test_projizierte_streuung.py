"""Projizierte Zylinderzone in der Baugruppenmessung, auch an den Halbzylindern des FTC-07."""

from dataclasses import replace

import numpy as np
import pytest
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from scipy.spatial.transform import Rotation

from programm.kern import baugruppe_mass as bm, projektionszone, verbindung as vb
from programm.kern.merkmalstreuung import _merkmal
from programm.kern.pmi import BezugsRef, Pmi
from tests.test_merkmalstreuung import _datum, _flaeche


def _zylinder():
    form = BRepPrimAPI_MakeCylinder(3., 20.).Shape()
    return {1: _flaeche(form), 2: _flaeche(form, [0, 0, 1]), 3: _flaeche(form, [0, 0, -1])}


def _rahmen(fuss, h=10., offset=0.):
    return Pmi("toleranz", "Position", wert=.2, modifikatoren=["Diameter"], flaechen={1}, bezuege=[BezugsRef("A")],
               zone="Projected", zonen_wert=h, projektionsflaechen=[fuss], projektionsversatz=offset)


@pytest.mark.parametrize("fuss,z,offset,bereich", [(2, 25, 0, .2), (2, 0, 0, 1.), (3, 0, 0, .2),
                                                 (2, 20, 5, .4), (3, 20, 5, 1.2)])
def test_projizierte_position_am_messort_und_in_kette(fuss, z, offset, bereich):
    formen = _zylinder()
    # A ist die feste Bezugsachse; als Messgroesse dient der radiale Abstand eines Punkts von der tolerierten Achse.
    bezug = _flaeche(BRepPrimAPI_MakeCylinder(1., 4.).Shape())
    bg = vb.Baugruppe()
    lage = np.eye(4)
    lage[:3, :3] = Rotation.from_rotvec([.4, .2, -.8]).as_matrix()
    lage[:3, 3] = [37., -9., 82.]
    bg.lagen.update({1: lage.copy(), 2: lage.copy()})
    m = bm.Messgroesse(1, 2, 8, 1, 1, art=bm.PUNKT_ACHSE, punkt=[4., 0., z])
    analyse = bm.Analyse(bg, [_rahmen(fuss, offset=offset), _datum(7, "A")],
                         lambda t, i: bezug if t == 1 and i == 7 else formen.get(i) if t == 1 else None)
    e = analyse.berechne(m, bezug, formen[1], proben=600)
    assert not e.hinweise and len(e.beitraege) == 1
    assert e.beitraege[0].bereich == pytest.approx(bereich)
    assert (e.wc_min, e.wc_max) == pytest.approx((4 - bereich / 2, 4 + bereich / 2))
    assert e.wc_min < e.mc_min < e.mc_max < e.wc_max
    kette = analyse.als_kette3d(m, bezug, formen[1])
    assert not kette.hinweise
    assert sum(g.werte["z"].oben - g.werte["z"].unten for g in kette.glieder) == pytest.approx(bereich)


@pytest.mark.parametrize("fehler", ["keine", "beide", "fremd", "hoehe", "offset", "gemischt", "verschieden"])
def test_ungeklaerte_projektion_unterdrueckt_sollbewertung(fehler):
    formen = _zylinder()
    p = _rahmen(2)
    angaben = [p]
    if fehler == "keine":
        p.projektionsflaechen = []
    elif fehler == "beide":
        p.projektionsflaechen = [2, 3]
    elif fehler == "fremd":
        formen[2] = _zylinder()[2]  # Abstand und Normale stimmen, aber keine gemeinsame Kante.
    elif fehler == "hoehe":
        p.zonen_wert = float("nan")
    elif fehler == "offset":
        p.projektionsversatz = None
    elif fehler == "gemischt":
        angaben.append(replace(p, typ="Parallelism", zone="", zonen_wert=None, projektionsflaechen=[]))
    else:
        angaben.append(replace(p, zonen_wert=11., wert=.1))
    m = bm.Messgroesse(1, 2, 8, 1, 1, art=bm.PUNKT_ACHSE, punkt=[4., 0., 5.], soll_min=0., soll_max=8.)
    a = bm.Analyse(vb.Baugruppe(), [*angaben, _datum(7, "A")], lambda t, i: formen.get(i) if t == 1 else None)
    e = a.berechne(m, formen[2], formen[1], proben=60)
    assert e.hinweise and not bm.bewertung(e, m)[0]
    assert a.als_kette3d(m, formen[2], formen[1]).hinweise == e.hinweise


@pytest.mark.parametrize("zweite,z,breite", [
    ({"zonen_wert": 15.}, 0., .2 * 55/15),                            # 20..30 und 20..35
    ({"projektionsversatz": 15.}, 0., .52),                            # 20..30 und 35..45
    ({"projektionsflaechen": [3]}, -30., .4),                          # -10..0 und 20..30
    ({"zone": "Diameter", "projektionsflaechen": []}, 0., .2),        # 0..20 und 20..30
])
def test_gleiche_positionsdurchmesser_auf_mehreren_abschnitten(zweite, z, breite):
    formen = _zylinder()
    formen[7] = _flaeche(BRepPrimAPI_MakeCylinder(1., 4.).Shape())
    p = _rahmen(2)
    m = bm.Messgroesse(1, 2, 8, 1, 1, art=bm.PUNKT_ACHSE, punkt=[4., 0., z])
    bg = vb.Baugruppe()
    lage = np.eye(4)
    lage[:3, :3] = Rotation.from_rotvec([.5, -.7, .1]).as_matrix()
    lage[:3, 3] = [17., 4., -92.]
    bg.lagen.update({1: lage.copy(), 2: lage.copy()})
    for angaben in ([p, replace(p, **zweite)], [replace(p, **zweite), p]):
        a = bm.Analyse(bg, [*angaben, _datum(7, "A")], lambda t, i: formen.get(i) if t == 1 else None)
        e = a.berechne(m, formen[7], formen[1])
        assert not e.hinweise and len(e.beitraege) == 1
        assert (e.wc_min, e.wc_max) == pytest.approx((4 - breite/2, 4 + breite/2))
        kette = a.als_kette3d(m, formen[7], formen[1])
        assert not kette.hinweise
        assert sum(g.werte["z"].oben - g.werte["z"].unten for g in kette.glieder) == pytest.approx(breite)


def test_positionsabschnitte_teilen_materialbonus_und_deckel():
    formen = _zylinder()
    formen[7] = _flaeche(BRepPrimAPI_MakeCylinder(1., 4.).Shape())
    p = replace(_rahmen(2), material="M", maximum_toleranz=.4)
    mass = Pmi("mass", "Size_Diameter", nennwert=6., unten=-.2, oben=.2, flaechen={1})
    m = bm.Messgroesse(1, 2, 8, 1, 1, art=bm.PUNKT_ACHSE, punkt=[4., 0., 0.])
    def analyse(zweiter):
        return bm.Analyse(vb.Baugruppe(), [p, zweiter, mass, _datum(7, "A")],
                          lambda t, i: formen.get(i) if t == 1 else None)

    zweiter = replace(p, projektionsversatz=15.)
    a = analyse(zweiter)
    e = a.berechne(m, formen[7], formen[1])
    assert not e.hinweise and len(e.beitraege) == 1
    assert e.wc_max - e.wc_min == pytest.approx(.4 * 2.6)
    assert e.wc_min <= e.mc_min < e.mc_max <= e.wc_max
    kette = a.als_kette3d(m, formen[7], formen[1])
    assert not kette.hinweise
    assert sum(g.werte["z"].oben - g.werte["z"].unten for g in kette.glieder) == pytest.approx(.4 * 2.6)
    for anders in (replace(zweiter, maximum_toleranz=None), replace(zweiter, material="L")):
        assert analyse(anders).berechne(m, formen[7], formen[1]).hinweise


def test_ftc07_projektionsursprung_an_geteilter_zylinderwand(ftc07):
    from programm.kern.pmi_lesen import lies_pmi
    p = next(p for p in lies_pmi(ftc07) if p.typ == "Position" and p.zone == "Projected" and len(p.flaechen) == 2)
    lookup = ftc07.flaechen.__getitem__
    assert p.zonen_wert == pytest.approx(10.795) and len(p.projektionsflaechen) == 1
    for idx in p.flaechen:
        f = lookup(idx)
        assert projektionszone.einzelachse(p, f, lookup)
        ziel, hinweis = projektionszone.messmerkmal([p], f, _merkmal(f, np.eye(4)), np.eye(4), lookup)
        assert not hinweis
        _, mitte, achse, laenge = ziel
        np.testing.assert_allclose(mitte, [142.875, 18.0975, 98.425], atol=1e-7)
        np.testing.assert_allclose(achse, [0, 1, 0], atol=1e-7)
        assert laenge == pytest.approx(10.795)
    # Weitere Bohrungsachsen im selben Rahmen sind kein einziges geteiltes Merkmal.
    muster = next(p for p in lies_pmi(ftc07) if p.zone == "Projected" and len(p.flaechen) == 4)
    assert not projektionszone.einzelachse(muster, lookup(min(muster.flaechen)), lookup)


@pytest.mark.parametrize("modell,breite", [("material", 3.), ("richtung", .4)])
def test_projektion_mit_materialbonus_oder_richtungstoleranz(modell, breite):
    formen = _zylinder()
    p = _rahmen(2)
    bezug = _flaeche(BRepPrimAPI_MakeCylinder(1., 4.).Shape())
    formen[7] = bezug
    pmi = [p, _datum(7, "A")]
    if modell == "material":
        p.material = "M"
        pmi.append(Pmi("mass", "Size_Diameter", nennwert=6., unten=-.2, oben=.2, flaechen={1}))
    else:
        pmi.append(replace(p, typ="Parallelism", wert=.05))
    # z=0 liegt 20 mm ausserhalb der Zone 20..30. Am Zapfen kann der Bonusdurchmesser 0.4 mm
    # erreichen. Im zweiten Fall begrenzt die Orientierung die Neigung auf 0.05 / 10.
    m = bm.Messgroesse(1, 2, 8, 1, 1, art=bm.PUNKT_ACHSE, punkt=[4., 0., 0.])
    a = bm.Analyse(vb.Baugruppe(), pmi, lambda t, i: formen.get(i) if t == 1 else None)
    e = a.berechne(m, bezug, formen[1])
    assert not e.hinweise and len(e.beitraege) == 1
    assert e.wc_max - e.wc_min == pytest.approx(breite)
