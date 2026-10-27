"""Baugruppenvariation: weitere Verbindungsarten, Messgroessen mit Worst Case, Monte Carlo und Beitragenden."""

import numpy as np

from programm.kern import baugruppe_mass as bm
from programm.kern import verbindung as vb
from tests.conftest import pfad


def _flaechen(form):
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    ex, out = TopExp_Explorer(form, TopAbs_FACE), []
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def _oben(form):
    """Obere Deckflaeche (Normale +z) eines Quaders."""
    return next(f for f in _flaechen(form) if (m := vb.merkmal(f)) and m[0] == "ebene" and m[2][2] > 0.99)


def test_kugel_langloch_punkt():
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    platte = _oben(BRepPrimAPI_MakeBox(100.0, 100.0, 10.0).Shape())
    kugel = _flaechen(BRepPrimAPI_MakeSphere(gp_Pnt(20, 20, 30), 2.0).Shape())[0]
    b = vb.Baugruppe()
    v = b.verbinde(2, kugel, 0, 1, platte, 0)
    assert v.art == vb.PUNKT and abs(v.versatz - 2.0) < 1e-9 and not b.verletzt()
    assert np.allclose(vb.merkmal(kugel, b.lage(2))[1], [20, 20, 12]) and len(b.freiheitsgrade(2)) == 5
    pfanne = _flaechen(BRepPrimAPI_MakeSphere(gp_Pnt(50, 50, 50), 2.0).Shape())[0]
    v = b.verbinde(3, pfanne, 0, 2, kugel, 0)
    assert v.art == vb.KUGEL and not b.verletzt() and len(b.freiheitsgrade(3)) == 3
    # Bolzen schraeg ueber der Platte: Achse wird parallel gedreht, Abstand = Radius
    zyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10, 10, 40), gp_Dir(1, 0, 0.2)), 1.5, 30.0).Shape()
    mantel = next(f for f in _flaechen(zyl) if vb.merkmal(f)[0] == "achse")
    v = b.verbinde(4, mantel, 0, 1, platte, 0)
    _, p, d = vb.merkmal(mantel, b.lage(4))
    assert v.art == vb.LANGLOCH and abs(d[2]) < 1e-9 and abs(p[2] - 11.5) < 1e-9 and not b.verletzt()
    assert len(b.freiheitsgrade(4)) == 4 and v.eingriff and v.eingriff[1] - v.eingriff[0] > 20
    b.setze_toleranz(v.nummer, 0.1)
    zeilen, _, ziehen = b.mc_zeilen(v)
    y = ziehen(np.random.default_rng(1), 1000)
    assert len(zeilen) == 2 and y.shape == (1000, 2) and abs(y).max() <= 0.1 + 1e-12
    # Ebene am Bolzen fangen (Teil traegt die Ebene)
    b2 = vb.Baugruppe()
    b2.verbinde(1, platte, 0, 4, mantel, 0)
    assert not b2.verletzt()


def _baugruppe():
    from programm.ui.lader import lade_alles
    erg = lade_alles(pfad("baugruppe.stp"))
    knoten = {k.nummer: k for k in erg.baum.blaetter()}
    f = lambda t, i: vb.flaeche_im_teil(knoten[t].form, i, erg.modell)  # noqa: E731
    b = vb.Baugruppe()
    b.verbinde(3, f(3, 14), 14, 2, f(2, 2), 2)  # Deckel auf Grundplatte
    for schraube, loch in ((4, 6), (5, 7)):
        b.verbinde(schraube, f(schraube, 18), 18, 3, f(3, 15), 15)  # Kopf auf Deckel
        b.verbinde(schraube, f(schraube, 19), 19, 2, f(2, loch), loch)  # Schaft in Bohrung
    for x in b.verbindungen:
        vb.toleranz_aus_pmi(b, x, erg.modell, erg.pmi, "m")
    b.setze_toleranz(1, 0.05, 0.0005)
    for nr in (2, 4):
        b.setze_toleranz(nr, 0.02, 0.001)
    return b, f


def test_messgroessen_worst_case_monte_carlo():
    b, f = _baugruppe()
    assert isinstance(b.neue_messgroesse(4, f(4, 17), 17, 4, f(4, 18), 18), str)  # gleiches Teil
    assert isinstance(b.neue_messgroesse(4, f(4, 19), 19, 3, f(3, 15), 15), str)  # Zylinder
    kopf = b.neue_messgroesse(4, f(4, 17), 17, 3, f(3, 15), 15)
    koepfe = b.neue_messgroesse(4, f(4, 17), 17, 5, f(5, 17), 17)
    spalt = b.neue_messgroesse(3, f(3, 13), 13, 9, f(9, 22), 22)
    assert kopf.art == koepfe.art == bm.BUENDIG and spalt.art == bm.SPALT
    koepfe.soll_min, koepfe.soll_max = bm.lies_soll("-0,05 … 0,05")
    a = bm.Analyse(b)
    e = a.berechne(kopf, *b.mass_formen[kopf.nummer])
    assert abs(e.nenn - 4.0) < 1e-9 and not e.unbestimmt
    assert e.wc_min < e.mc_min <= e.mittel <= e.mc_max < e.wc_max and e.wc_max - e.wc_min < 1.0
    assert e.beitraege[0].verbindung == 2  # Kopfauflage der ersten Schraube dominiert
    e2 = a.berechne(koepfe, *b.mass_formen[koepfe.nummer])
    assert abs(e2.nenn) < 1e-9 and e2.aussen is not None and e2.cp is not None and e2.cpk <= e2.cp + 1e-12
    assert {x.verbindung for x in e2.beitraege if x.anteil_var > 0.05} >= {2, 4}
    assert abs(sum(x.anteil_var for x in e2.beitraege) - 1) < 1e-9
    # Deckel ist in der Ebene frei verschiebbar: der Spalt zum Winkel ist unbestimmt
    e3 = a.berechne(spalt, *b.mass_formen[spalt.nummer])
    assert abs(e3.nenn - 15.0) < 1e-9 and e3.unbestimmt
    # Speichern und Laden
    b2 = vb.Baugruppe()
    b2.lade(b.als_dict(), f)
    assert [m.nummer for m in b2.masse] == [1, 2, 3] and b2.masse[1].soll_max == 0.05


def test_soll_text():
    assert bm.lies_soll("14,5 … 15,5") == (14.5, 15.5)
    assert bm.lies_soll(">= 1") == (1.0, None) and bm.lies_soll("≤ 2") == (None, 2.0)
    assert bm.lies_soll("") == (None, None)
    m = bm.Messgroesse(1, 1, 1, 2, 2, soll_min=1.0)
    assert bm.soll_text(m) == "1 … "


def test_umkehren_und_tauschen():
    b, f = _baugruppe()
    # Verbindung 3: Schaft der Schraube 4 koaxial in der Bohrung der Grundplatte
    _, p0, d0 = vb.merkmal(f(4, 19), b.lage(4))
    assert b.umkehren(3) is None
    _, p1, d1 = vb.merkmal(f(4, 19), b.lage(4))
    assert np.allclose(d1, -d0, atol=1e-9) and np.linalg.norm(np.cross(p1 - p0, d0)) < 1e-6  # Ende gegen Ende, gleiche Achse
    v3 = next(v for v in b.verbindungen if v.nummer == 3)
    assert vb.erfuellt(v3.art, *b.merkmale(v3))  # weiter koaxial
    kopf = next(v for v in b.verbindungen if v.nummer == 2)
    assert not vb.erfuellt(kopf.art, *b.merkmale(kopf), kopf.versatz)  # Kopf jetzt auf der anderen Seite
    assert isinstance(b.umkehren(99), str)
    # Tauschen: Deckel/Grundplatte – danach bewegt sich die Grundplatte, die Verbindung bleibt erfuellt
    v1 = next(v for v in b.verbindungen if v.nummer == 1)
    assert (v1.teil, v1.gegen_teil) == (3, 2) and b.tauschen(1) is None
    assert (v1.teil, v1.gegen_teil) == (2, 3) and vb.erfuellt(v1.art, *b.merkmale(v1), v1.versatz)
    assert not b.fest(2)


def test_bewegen_nur_in_offenen_freiheitsgraden():
    b, f = _baugruppe()
    teil = 4  # Schraube: offen nur die Drehung um die eigene Achse
    basis = b.freiheitsgrade(teil)
    assert len(basis) == 1
    start = b.lage(teil).copy()
    b.bewege_frei(teil, [90.0], start, basis)
    assert not b.verletzt()  # Verbindungen bleiben erfuellt
    assert not np.allclose(b.lage(teil), start)
    b.bewege_frei(teil, [0.0], start, basis)
    assert np.allclose(b.lage(teil), start)
