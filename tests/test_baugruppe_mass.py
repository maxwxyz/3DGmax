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


def test_toleranz_der_messflaechen():
    """Automatisch aus dem Modell: Lage-/Profiltoleranzen der gemessenen Flaechen (die nicht schon Verbindungsflaechen
    sind) wirken mit halber Zonenbreite entlang der Messrichtung - Worst Case breiter um 2h, eigener Beitragender."""
    from types import SimpleNamespace
    b, f = _baugruppe()
    kopf = b.neue_messgroesse(4, f(4, 17), 17, 3, f(3, 15), 15)
    ohne = bm.Analyse(b).berechne(kopf, *b.mass_formen[kopf.nummer])
    profil = SimpleNamespace(art="toleranz", typ="ProfileOfSurface", wert=0.1, flaechen={17},
                             wert_text=lambda: "⌓ | 0.1 | A")
    mit = bm.Analyse(b, [profil]).berechne(kopf, *b.mass_formen[kopf.nummer])
    assert abs((mit.wc_max - mit.wc_min) - (ohne.wc_max - ohne.wc_min) - 0.1) < 1e-9
    eigen = [x for x in mit.beitraege if x.flaeche == 17]
    assert len(eigen) == 1 and abs(eigen[0].bereich - 0.1) < 1e-12 and "0.1" in bm.beitrag_art(eigen[0], {})
    assert mit.std > ohne.std and abs(sum(x.anteil_var for x in mit.beitraege) - 1) < 1e-9
    verbunden = next(v for v in b.verbindungen)  # Flaeche einer Verbindung: steckt schon im Spielraum
    doppelt = SimpleNamespace(art="toleranz", typ="Position", wert=0.2, flaechen={verbunden.flaeche},
                              wert_text=lambda: "⌖ 0.2")
    m2 = bm.Messgroesse(99, verbunden.teil, verbunden.flaeche, kopf.teil_b, kopf.flaeche_b)
    assert bm.Analyse(b, [doppelt]).flaechen_toleranzen(m2) == []


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


def test_messgroessen_an_achsen():
    """Achsabstand der zwei Schraubenschaefte und Abstand einer Schaftachse zu einer Seitenflaeche der Grundplatte:
    Nennwerte aus der Geometrie, Streuung aus dem radialen Spiel der Bohrungen."""
    b, f = _baugruppe()
    abstand = b.neue_messgroesse(4, f(4, 19), 19, 5, f(5, 19), 19)
    assert abstand.art == bm.ACHSABSTAND
    pa, _ = bm.achse(f(4, 19), b.lage(4))
    pb, d = bm.achse(f(5, 19), b.lage(5))
    soll = np.linalg.norm((pa - pb) - d * ((pa - pb) @ d))
    seite = next(i for i in range(40) if (e := bm.ebene(f(2, i))) is not None and abs(e[1][2]) < 1e-6)
    zur_seite = b.neue_messgroesse(4, f(4, 19), 19, 2, f(2, seite), seite)
    assert zur_seite.art == bm.ACHSE_EBENE
    gedreht = b.neue_messgroesse(2, f(2, seite), seite, 4, f(4, 19), 19)  # Ebene zuerst: gleiche Groesse
    a = bm.Analyse(b)
    e = a.berechne(abstand, *b.mass_formen[abstand.nummer])
    assert abs(e.nenn - soll) < 1e-9 and e.wc_max - e.wc_min > 0 and not e.unbestimmt
    assert {x.verbindung for x in e.beitraege if x.bereich > 0} >= {3, 5}  # beide Schaefte im Spiel
    e1 = a.berechne(zur_seite, *b.mass_formen[zur_seite.nummer])
    e2 = a.berechne(gedreht, *b.mass_formen[gedreht.nummer])
    assert abs(abs(e1.nenn) - abs(e2.nenn)) < 1e-9 and abs((e1.wc_max - e1.wc_min) - (e2.wc_max - e2.wc_min)) < 1e-9


def test_manipulator_rahmen_und_werte():
    """Rahmen des 3D-Manipulators je Verbindungsart und Rueckrechnung einer Manipulator-Bewegung auf die Freiheitsgrade."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    platte = _oben(BRepPrimAPI_MakeBox(100.0, 100.0, 10.0).Shape())
    unten = next(f for f in _flaechen(BRepPrimAPI_MakeBox(gp_Pnt(10, 10, 20), 5, 5, 5).Shape())
                 if (m := vb.merkmal(f)) and m[0] == "ebene" and m[2][2] < -0.99)
    b = vb.Baugruppe()
    b.verbinde(2, unten, 0, 1, platte, 0)  # Klotz auf Platte: zwei Verschiebungen, eine Drehung
    r = vb.manipulator_rahmen(b.freiheitsgrade(2), np.array([12.5, 12.5, 12.5]))
    assert np.allclose(np.abs(r["achsen"][2]), [0, 0, 1]) and r["verschieben"] == [True, True, False]
    assert r["drehen"] == [False, False, True]
    # Rueckrechnung: Verschiebung in der Ebene und Drehung um die Normale durch den Manipulatorpunkt
    basis = b.freiheitsgrade(2)
    m = np.eye(4)
    m[:3, 3] = [3.0, -2.0, 0.0]
    werte = vb.werte_aus_bewegung(m, basis, r["punkt"])
    start = b.lage(2).copy()
    b.bewege_frei(2, werte, start, basis)
    assert np.allclose(b.lage(2)[:3, 3] - start[:3, 3], [3, -2, 0], atol=1e-9) and not b.verletzt()
    # Zapfen in Bohrung: Drehung und Verschiebung entlang der Achse
    bohrung = next(f for f in _flaechen(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(50, 50, 0), gp_Dir(0, 0, 1)), 4, 10)
                                        .Shape()) if vb.merkmal(f)[0] == "achse")
    zapfen = next(f for f in _flaechen(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 30), gp_Dir(0, 0, 1)), 4, 20)
                                       .Shape()) if vb.merkmal(f)[0] == "achse")
    b.verbinde(3, zapfen, 0, 1, bohrung, 0)
    r = vb.manipulator_rahmen(b.freiheitsgrade(3), np.zeros(3))
    assert np.allclose(r["punkt"][:2], [50, 50]) and r["verschieben"] == [False, False, True]
    assert r["drehen"] == [False, False, True]
    # Kugelgelenk: drei Drehungen um die Mitte
    k1 = _flaechen(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 80), 3.0).Shape())[0]
    k2 = _flaechen(BRepPrimAPI_MakeSphere(gp_Pnt(20, 20, 80), 3.0).Shape())[0]
    b.verbinde(4, k1, 0, 1, k2, 0)
    r = vb.manipulator_rahmen(b.freiheitsgrade(4), np.zeros(3))
    assert np.allclose(r["punkt"], [20, 20, 80]) and r["drehen"] == [True] * 3 and r["verschieben"] == [False] * 3
    assert vb.manipulator_rahmen(np.zeros((0, 6)), np.zeros(3)) is None


def test_waermeausdehnung_im_zusammenbau():
    """Stahlsockel (fest, 10 hoch) traegt eine Aluplatte (5 dick): Oberseite der Platte gegen die Unterseite des
    Sockels waechst bei +80 K um 10·11,5e-6·80 + 5·23e-6·80 = 0,0184 mm."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt
    sockel = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 40, 40, 10).Shape()
    platte = BRepPrimAPI_MakeBox(gp_Pnt(5, 5, 10), 30, 30, 5).Shape()
    def flaeche(form, nz, z):
        return next(f for f in _flaechen(form) if (m := vb.merkmal(f)) and m[0] == "ebene"
                    and abs(m[2][2] - nz) < 1e-9 and abs(m[1][2] - z) < 1e-9)
    b = vb.Baugruppe()
    v = b.verbinde(2, flaeche(platte, -1, 10), 0, 1, flaeche(sockel, 1, 10), 0)
    assert not isinstance(v, str)
    mg = b.neue_messgroesse(2, flaeche(platte, 1, 15), 1, 1, flaeche(sockel, -1, 0), 2)
    assert not isinstance(mg, str)
    a = bm.Analyse(b)
    fa, fb = b.mass_formen[mg.nummer]
    dt = a.waermeverschiebung(mg, fa, fb, {1: 11.5, 2: 23.0}, {1: 100.0, 2: 100.0})
    assert abs(abs(dt) - (10 * 11.5e-6 * 80 + 5 * 23e-6 * 80)) < 1e-9
    assert a.waermeverschiebung(mg, fa, fb, {1: 11.5, 2: 23.0}, {}) == 0.0  # 20 °C: keine Dehnung


def test_messgroessen_am_punkt():
    b, f = _baugruppe()
    a = bm.Analyse(b)
    flaeche = b.neue_messgroesse(4, f(4, 17), 17, 3, f(3, 15), 15)
    p0, _ = bm.ebene(f(4, 17), b.lage(4))
    mitte = b.neue_messgroesse(4, f(4, 17), 17, 3, f(3, 15), 15, punkt=p0)
    rand = b.neue_messgroesse(4, f(4, 17), 17, 3, f(3, 15), 15, punkt=p0 + [3.0, 0.0, 0.0])
    assert mitte.art == rand.art == bm.BUENDIG and mitte.punkt is not None
    e0, e1, e2 = (a.berechne(m, *b.mass_formen[m.nummer]) for m in (flaeche, mitte, rand))
    assert abs(e1.nenn - e0.nenn) < 1e-9 and abs(e1.wc_max - e0.wc_max) < 1e-9
    assert abs(e2.nenn - 4.0) < 1e-9 and e2.wc_max - e2.wc_min > e1.wc_max - e1.wc_min  # Kippen wirkt mit Hebel
    # beliebige Flaeche am Punkt: Schaftmantel zur Deckeloberseite, Deckeloberseite zur Schaftachse
    q, d = bm.achse(f(4, 19), b.lage(4))
    seite = np.cross(d, [1.0, 0.0, 0.0])
    seite /= np.linalg.norm(seite)
    pe = b.neue_messgroesse(4, f(4, 19), 19, 3, f(3, 15), 15, punkt=q + seite * 1.0)
    assert pe.art == bm.PUNKT_EBENE
    pa = b.neue_messgroesse(3, f(3, 15), 15, 4, f(4, 19), 19, punkt=q + seite * 7.0)
    assert pa.art == bm.PUNKT_ACHSE and abs(a.berechne(pa, *b.mass_formen[pa.nummer]).nenn - 7.0) < 1e-6
    b2 = vb.Baugruppe()
    b2.lade(b.als_dict(), f)
    assert b2.masse[2].punkt == rand.punkt


def test_messgroesse_als_3d_kette():
    from programm.kern import kette3d as k3
    b, f = _baugruppe()
    a = bm.Analyse(b)
    for args in ((4, 17, 3, 15), (4, 17, 5, 17), (3, 15, 2, 2)):  # Kopf zu Deckel, Koepfe, Deckel zu Platte
        m = b.neue_messgroesse(args[0], f(args[0], args[1]), args[1], args[2], f(args[2], args[3]), args[3])
        e = a.berechne(m, *b.mass_formen[m.nummer])
        k = a.als_kette3d(m, *b.mass_formen[m.nummer], {4: "S1", 5: "S2"})
        assert abs(k3.schlussgroesse(k) - e.nenn) < 1e-9
        from programm.kern import toleranzkette as tk
        e1 = tk.berechne(k3.als_glieder(k), proben=2000)
        assert abs(e1.nenn - e.nenn) < 1e-9 and abs(e1.wc_max - e.wc_max) < 1e-6  # Uebergabe an 1D stimmt
        wc = sum(g.faktor * (g.hoechst - g.mindest) / 2 for g in k3.als_glieder(k))
        assert abs(wc - (e.wc_max - e.wc_min) / 2) < 1e-6  # hier entkoppelt: gleich der Baugruppenanalyse
    assert [g.name for g in k.glieder] == ["Bezug", "3"]
    m = b.masse[1]
    namen = [g.name for g in a.als_kette3d(m, *b.mass_formen[m.nummer], {4: "S1", 5: "S2"}).glieder]
    assert namen == ["Bezug", "S2 (umgekehrt)", "S1"]
    # Basis im Modell: Funktionspunkt in Weltlage = Messpunkt
    basis = np.asarray(k.basis)
    p, _ = k3.funktionspunkt(k)
    assert np.allclose(basis[:3, :3] @ p + basis[:3, 3], bm.ebene(f(3, 15), b.lage(3))[0])
    assert k3.von_dict(k3.als_dict(k)).basis == k.basis


def test_lage_komponenten_rueckwaerts():
    from programm.kern import kette3d as k3
    rng = np.random.default_rng(3)
    for _ in range(20):
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        q *= np.sign(np.linalg.det(q))
        w = bm._lage_komponenten(q, np.array([1.0, 2.0, 3.0]))
        assert np.allclose(k3._drehung(w["rx"], w["ry"], w["rz"]), q, atol=1e-9)


def test_bonus_und_bezugsverschiebung_in_verbindung():
    """Bolzen ⌀9,9 in Bohrung ⌀10 H8 mit Position ⌀0,1 Ⓜ: Spiel (10,022 - 9,9) / 2 + 0,1 / 2 = 0,111, Bonus bei LMC
    ⌀0,022 -> 0,011 radial (Positionszone bis ⌀0,122, virtuelle Bedingung ⌀9,9 = Bolzen); Bezug Ⓜ mit ⌀±0,05 verschiebt
    um weitere ⌀0,1. Achse zu Ebene: Worst Case ±(0,111 + 0,011), Bonus als eigener Beitragender."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern.pmi import BezugsRef, Pmi
    loch_form = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, 0), gp_Dir(0, 0, 1)), 5.0, 10.0).Shape()
    platte = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(40.0, 40.0, 10.0).Shape(), loch_form).Shape()
    loch = next(f for f in _flaechen(platte) if vb.merkmal(f)[0] == "achse")
    seite = next(f for f in _flaechen(platte) if (m := vb.merkmal(f)) and m[0] == "ebene" and m[2][0] < -0.99)
    bolzen = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, 0), gp_Dir(0, 0, 1)), 4.95, 10.0).Shape()
    mantel = next(f for f in _flaechen(bolzen) if vb.merkmal(f)[0] == "achse")
    b = vb.Baugruppe()
    v = b.verbinde(2, mantel, 0, 1, loch, 7)
    pos = Pmi("toleranz", "Position", wert=0.1, material="M", flaechen={7}, bezuege=[BezugsRef("A")])
    pmi = [Pmi("mass", "Size_Diameter", nennwert=10.0, passung="H8", flaechen={7}), pos]
    vb.toleranz_aus_pmi(b, v, None, pmi)
    assert abs(v.toleranz - 0.111) < 1e-9 and abs(v.bonus - 0.011) < 1e-9 and "Bonus" in v.bonus_quelle
    assert all(abs(o - 0.122) < 1e-9 for _, _, o in b.zeilen(v))  # Wiggle/Streuung mit vollem Bonus
    zeilen, grenzen, _ = b.mc_zeilen(v)
    yb = b.mc_bonus(v)(np.random.default_rng(1), 5000)
    assert np.allclose(grenzen, 0.111) and yb.shape == (5000, len(zeilen))
    r = np.linalg.norm(yb[:, :2], axis=1)  # Betrag = Abstand des Istmasses vom MMC, hoechstens der volle Bonus
    assert r.max() <= 0.011 + 1e-12 and abs(r.mean() - 0.0055) < 3e-4
    m = b.neue_messgroesse(2, mantel, 0, 1, seite, 3)
    assert m.art == bm.ACHSE_EBENE
    e = bm.Analyse(b).berechne(m, mantel, seite, proben=20_000)
    # Normale aus dem Material: Abstand -20
    assert abs(e.nenn + 20.0) < 1e-9 and abs(e.wc_max + 19.878) < 1e-6 and abs(e.wc_min + 20.122) < 1e-6
    spiel, bonus = (next(x for x in e.beitraege if x.bonus == mit) for mit in (False, True))
    assert abs(spiel.bereich - 0.222) < 1e-6 and abs(bonus.bereich - 0.022) < 1e-6
    assert 0 < bonus.anteil_var < spiel.anteil_var and e.mc_max < e.wc_max
    assert "Bezugsverschiebung" in bm.beitrag_art(bonus, {v.nummer: v.art})
    # Bezug A mit Ⓜ an einer Bohrung ⌀8 ±0,05: Zone verschiebt sich um bis zu ⌀0,1 (0,05 radial)
    pos.bezuege = [BezugsRef("A", modifikatoren=["MaximumMaterialRequirement"])]
    pmi += [Pmi("bezug", "Datum", name="A", flaechen={9}),
            Pmi("mass", "Size_Diameter", nennwert=8.0, oben=0.05, unten=-0.05, flaechen={9})]
    vb.toleranz_aus_pmi(b, v, None, pmi)
    assert abs(v.bonus - 0.061) < 1e-9 and "Bezugsverschiebung A Ⓜ" in v.bonus_quelle
    b.setze_toleranz(v.nummer, 0.0)  # ohne Spiel bleibt nur der Bonus
    e = bm.Analyse(b).berechne(m, mantel, seite, proben=2000)
    assert abs(e.wc_max + 19.939) < 1e-6 and [x.bonus for x in e.beitraege if x.bereich > 0] == [True]
