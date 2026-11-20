"""Messmerkmaltorsoren an bekannten Geometrien und Bezugssystemen."""

import numpy as np
import pytest

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.gp import gp_Pnt

from programm.kern import baugruppe_mass as bm, kette3d, verbindung as vb
from programm.kern.merkmalstreuung import _rahmenanteile, _zylindrisch
from programm.kern.pmi import BEZUG, MASS, TOLERANZ, BezugsRef, Pmi


def _flaeche(form, richtung=None):
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = ex.Current()
        merkmal = vb.merkmal(f)
        if richtung is None and merkmal[0] == "achse":
            return f
        if richtung is not None and merkmal[0] == "ebene" and np.allclose(merkmal[2], richtung):
            return f
        ex.Next()
    raise AssertionError("Flaeche fehlt")


def _oben(x, laenge=20):
    return _flaeche(BRepPrimAPI_MakeBox(gp_Pnt(x, 0, 0), laenge, 12, 4).Shape(), [0, 0, 1])


def _profil(idx, wert, bezug):
    return Pmi(TOLERANZ, "ProfileOfSurface", wert=wert, flaechen={idx}, bezuege=[BezugsRef(bezug)])


def _datum(idx, name):
    return Pmi(BEZUG, "Datum", name=name, flaechen={idx})


def test_torsor_bezugskette_mit_hebelarm_und_kettenuebergabe():
    # C auf A ist 20 mm breit (x=0..20). Der Messpunkt auf D liegt bei x=35:
    # Grenzneigung von C ist 0.2/20 rad. Am Hebel 25 mm ab Mitte macht das 0.25 mm.
    f, gegen, c, a = _oben(30, 10), _oben(30, 10), _oben(0), _oben(0)
    bg = vb.Baugruppe()
    bg.verbinde(1, a, 4, 2, gegen, 9)
    m = bm.Messgroesse(1, 1, 1, 2, 9)
    pmi = [_profil(1, 0.4, "C"), _datum(2, "C"), _profil(2, 0.2, "A"), _datum(4, "A")]
    lookup = {(1, 2): c}
    analyse = bm.Analyse(bg, pmi, lambda t, i: lookup.get((t, i)))
    e = analyse.berechne(m, f, gegen)
    assert not e.hinweise
    assert sorted((b.flaeche, round(b.bereich, 6)) for b in e.beitraege if b.flaeche is not None) == [(1, .4), (2, .5)]
    assert e.wc_max - e.wc_min == pytest.approx(.9)
    assert abs(sum(b.anteil_var for b in e.beitraege) - 1) < 1e-10
    k = analyse.als_kette3d(m, f, gegen)
    assert kette3d.schlussgroesse(k) == pytest.approx(e.nenn)
    assert sum(g.werte["z"].oben - g.werte["z"].unten for g in k.glieder) == pytest.approx(.9)
    from programm.kern.kette3d_anzeige import teil_bewegungen
    for t in teil_bewegungen(k, {(len(k.glieder) - 1, "z"): .25}).values():
        np.testing.assert_allclose(t, np.eye(4), atol=1e-10)


def test_identische_instanz_hebt_sich_auf_wiederholteile_streuen_getrennt():
    f, ref = _oben(0), _oben(0)
    bg = vb.Baugruppe()
    analyse = bm.Analyse(bg, [_profil(1, .12, "A"), _datum(7, "A")],
                         lambda t, i: ref if i == 7 else None)
    gleich = bm.Messgroesse(1, 1, 1, 1, 1)
    e = analyse.berechne(gleich, f, f)
    assert not e.hinweise and e.wc_min == e.wc_max
    gleich.teil_b = 2
    e = analyse.berechne(gleich, f, f)
    assert not e.hinweise and len(e.beitraege) == 2
    assert {b.teil for b in e.beitraege} == {1, 2}
    assert e.wc_min == pytest.approx(-.12) and e.wc_max == pytest.approx(.12)
    assert abs(sum(b.anteil_var for b in e.beitraege) - 1) < 1e-10


def test_achszone_am_hebel_und_groesse_nur_am_mantel():
    a = _flaeche(BRepPrimAPI_MakeCylinder(3, 20).Shape())
    # Zylinderachse parallel zur Ebene x=0. Primaerbezug ist eine gleichgerichtete Achse.
    b = _flaeche(BRepPrimAPI_MakeBox(10, 10, 20).Shape(), [-1, 0, 0])
    pos = Pmi(TOLERANZ, "Position", wert=.2, modifikatoren=["Diameter"], flaechen={1}, bezuege=[BezugsRef("A")])
    mass = Pmi(MASS, "Size_Diameter", nennwert=6., oben=.12, unten=-.04, flaechen={1})
    analyse = bm.Analyse(vb.Baugruppe(), [pos, mass, _datum(7, "A")], lambda t, i: a if t == 1 and i == 7 else None)
    m = bm.Messgroesse(1, 1, 1, 2, 2, art=bm.ACHSE_EBENE)
    e = analyse.berechne(m, a, b)
    assert not e.hinweise and len(e.beitraege) == 1
    assert e.wc_max - e.wc_min == pytest.approx(.2)
    m.punkt = [3., 0., 10.]
    e = analyse.berechne(m, a, b)
    assert not e.hinweise and len(e.beitraege) == 2
    assert (e.wc_min - e.nenn, e.wc_max - e.nenn) == pytest.approx((-.16, .12))
    # Punkt auf A misst zur Achse B ausserhalb ihrer Laenge: beide Enden koennen gegensinnig ausweichen.
    m = bm.Messgroesse(2, 2, 2, 1, 1, art=bm.PUNKT_ACHSE, punkt=[3, 0, 40])
    e = analyse.berechne(m, b, a)
    assert not e.hinweise and len(e.beitraege) == 1
    assert e.wc_max - e.wc_min == pytest.approx(.6)


def test_ebenen_projektion_und_unvollstaendige_angaben():
    a = _flaeche(BRepPrimAPI_MakeBox(10, 10, 20).Shape(), [1, 0, 0])
    b = _oben(0)
    m = bm.Messgroesse(1, 1, 1, 2, 2, art=bm.PUNKT_EBENE, punkt=[10, 5, 10], soll_min=-20, soll_max=20)
    pmi = [_profil(1, .5, "A"), _datum(8, "A")]
    analyse = bm.Analyse(vb.Baugruppe(), pmi, lambda t, i: a if i == 8 else None)
    e = analyse.berechne(m, a, b)
    assert not e.hinweise and e.wc_max == e.wc_min  # Toleranz in X, gemessen in Z
    e = bm.Analyse(vb.Baugruppe(), [_profil(1, .5, "X")]).berechne(m, a, b)
    assert any("X" in h for h in e.hinweise)
    assert not bm.bewertung(e, m)[0]


def test_richtungszone_an_der_kante_und_uz_vorzeichen():
    f = _oben(0)
    datum = _datum(3, "A")
    ref = lambda teil, idx: f if idx == 3 else None
    parallel = Pmi(TOLERANZ, "Parallelism", wert=.2, flaechen={1}, bezuege=[BezugsRef("A")])
    m = bm.Messgroesse(1, 1, 1, 2, 2, art=bm.PUNKT_EBENE, punkt=[20, 6, 4])
    analyse = bm.Analyse(vb.Baugruppe(), [parallel, datum], ref)
    e = analyse.berechne(m, f, f)
    # Die Richtungstoleranz begrenzt das Kippen, nicht die Lage des Merkmals.
    assert e.wc_max - e.wc_min == pytest.approx(.2)
    assert any("Lage" in h for h in e.hinweise)
    k = analyse.als_kette3d(m, f, f)
    assert kette3d.von_dict(kette3d.als_dict(k)).hinweise == e.hinweise
    alt = kette3d.als_dict(k)
    del alt["hinweise"]
    assert not kette3d.von_dict(alt).hinweise
    # UZ verschiebt die Zone zum Materialaussenraum. Auf der Gegenseite kehrt das Vorzeichen um.
    profil = _profil(2, .4, "A")
    profil.modifikatoren = ["UZ 0.05"]
    e = bm.Analyse(vb.Baugruppe(), [profil, datum], ref).berechne(m, f, f)
    assert (e.wc_min - e.nenn, e.wc_max - e.nenn) == pytest.approx((-.25, .15))


def test_bezugssystem_rangfolge_inverser_transformation():
    punkt = np.array([4., 2., 3.])
    daten = [(i, ("ebene", np.zeros(3), d, 0.)) for i, d in enumerate(np.eye(3)[::-1])]
    for messung in np.eye(6):
        anteile, rest = _rahmenanteile(daten, punkt, messung)
        assert rest < 1e-9
        np.testing.assert_allclose(sum(anteile.values()), messung, atol=1e-9)
    # Rotation um X ist durch den primaeren Bezug (Z-Normale) gesperrt.
    anteile, _ = _rahmenanteile(daten, punkt, np.eye(6)[0])
    np.testing.assert_allclose(anteile[0], np.eye(6)[0], atol=1e-9)
    np.testing.assert_allclose(anteile[1], np.zeros(6), atol=1e-9)


def _achsgrenzen(a, b, sehne):
    # Schiefe Raumachse, beliebiger Radius und mehrere Zonen. Nur radiale Anteile wirken.
    u = np.array([.6, .8, 0.])
    v = np.array([0., 0., 1.])
    d = np.cross(u, v)
    radius, laenge = .23, 17.
    aa, bb = (x * u + y * v for x, y in (a, b))
    kraft = aa + bb + .7 * d
    moment = laenge / 2 * np.cross(d, bb - aa) - 2 * d
    zonen = [(-1., 1.), (-radius, radius)]
    return np.array(_zylindrisch(d, laenge, kraft, moment, zonen, [2., sehne * radius])) / radius


@pytest.mark.parametrize(("a", "b", "sehne", "erwartet"), [
    ((1, 0), (0, 1), 1., 2 * np.cos(np.pi / 12)),  # Beide Enden am Rand, Winkel 60 Grad
    ((1, 0), (0, 1), 1.5, 2.),                      # Freie Endlagen genuegen
    ((1, 0), (-3, .5), .4, np.hypot(2., .5) + .4),  # Erstes Ende im Inneren
    ((-3, .5), (1, 0), .4, np.hypot(2., .5) + .4),  # Zweites Ende im Inneren
    ((2, 0), (-2, 0), .7, 1.4),                     # Reines Kippen
    ((1, 0), (2, 0), .1, 3.),                       # Reine gemeinsame Verschiebung genuegt
    ((0, 0), (-2, 1), .1, np.sqrt(5.)),              # Ein Ende ohne Empfindlichkeit
    ((1, 0), (0, 1), 0., np.sqrt(2.)),               # Beide Enden bewegen sich gleich
])
def test_kombinierte_achszone_analytisch(a, b, sehne, erwartet):
    np.testing.assert_allclose(_achsgrenzen(a, b, sehne), [-erwartet, erwartet], atol=1e-12)


def test_kombinierte_achszone_in_der_baugruppenmessung():
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.gp import gp_Dir, gp_Pln
    achse = _flaeche(BRepPrimAPI_MakeCylinder(10, 20).Shape())
    pl = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 1))
    ebene = BRepBuilderAPI_MakeFace(pl, -20., 20., -20., 20.).Face()
    pmi = [Pmi(TOLERANZ, typ, wert=wert, zone="Diameter", flaechen={1}, bezuege=[BezugsRef("A")])
           for typ, wert in (("Position", .2), ("Parallelism", .1))]
    analyse = bm.Analyse(vb.Baugruppe(), pmi + [_datum(7, "A")], lambda t, i: achse if i == 7 else None)
    m = bm.Messgroesse(1, 1, 1, 2, 2, art=bm.PUNKT_EBENE, punkt=[0., 10., 10.])
    e = analyse.berechne(m, achse, ebene)
    # Kraft und Hebelarm ergeben zwei orthogonale Endempfindlichkeiten mit Betrag 1/2.
    h = .1 * np.cos(np.pi / 12)
    assert not e.hinweise and len(e.beitraege) == 1
    assert (e.wc_min - e.nenn, e.wc_max - e.nenn) == pytest.approx((-h, h))


def test_kombinierte_achszone_zwischen_unabhaengigen_polygonalen_schranken():
    from scipy.optimize import linprog
    # Jeweils ein 256-Eck um jeden Kreis. Skalieren mit dem Kosinus ergibt ein einbeschriebenes Polygon.
    n = 256
    phi = np.arange(n) * (2 * np.pi / n)
    normal = np.column_stack((np.cos(phi), np.sin(phi)))
    null = np.zeros_like(normal)
    matrix = np.block([[normal, null], [null, normal], [normal, -normal]])
    rng = np.random.default_rng(2168)
    for sehne in (1e-4, .15, .7, 1.4, 1.98):
        for _ in range(6):
            a, b = rng.normal(size=(2, 2))
            grenze = np.repeat([1., 1., sehne], n)
            lp = linprog(-np.r_[a, b], A_ub=matrix, b_ub=grenze, bounds=(None, None), method="highs")
            assert lp.success
            oben = -lp.fun
            unten = oben * np.cos(np.pi / n)
            klein, gross = _achsgrenzen(a, b, sehne)
            assert unten - 1e-9 <= gross <= oben + 1e-9
            assert klein == pytest.approx(-gross)
