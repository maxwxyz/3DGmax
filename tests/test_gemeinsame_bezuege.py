"""Gemeinsame Bezuege in der Baugruppenmessung mit eingelesener Getriebewelle und ebenen Auflagen."""

from dataclasses import replace

import numpy as np
import pytest
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
from scipy.spatial.transform import Rotation

from programm.kern import baugruppe_mass as bm, beispiele, kette3d, step_schreiben, verbindung as vb
from programm.kern.pmi import TOLERANZ, BezugsRef, Pmi
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_merkmalstreuung import _datum, _flaeche, _oben, _profil


@pytest.fixture(scope="module")
def bezugswelle(tmp_path_factory):
    quelle = pfad(beispiele.WELLE)
    modell = lade_alles(quelle).modell
    rollen = beispiele.welle_rollen(modell)

    def sitze(rolle):
        idx = [i for i, r in rollen if r == rolle]
        return sorted(idx, key=lambda i: bm.achse(modell.flaechen[i])[0][0])

    a, b = sitze("lagersitz")
    c, = sitze("dichtsitz")
    aussen, innen = sitze("nabensitz")
    pmi = [_datum(i, name) for i, name in ((a, "A"), (b, "B"), (c, "C"))]
    for idx, breite, bezug in ((a, .24, "C"), (b, .12, "C"), (innen, .2, "A-B"), (aussen, .2, "B-A")):
        pmi.append(Pmi(TOLERANZ, "Position", wert=breite, modifikatoren=["Diameter"],
                       flaechen={idx}, bezuege=[BezugsRef(bezug)]))
    for nr, p in enumerate(pmi, 1):
        p.quelle, p.nummer, p.step_id = "eigen", nr, -nr
    datei = str(tmp_path_factory.mktemp("bezugswelle") / "Welle.stp")
    export = step_schreiben.schreibe(quelle, datei, pmi, modell)
    assert len(export.neu) == len(pmi) and not export.uebersprungen
    geladen = lade_alles(datei)
    assert {r.name for p in geladen.pmi for r in p.bezuege} == {"C", "A-B", "B-A"}
    return geladen, (a, b, c), (innen, aussen)


def _radialmessung(welle, sitz, x):
    geladen, (_, _, c), _ = welle
    flaechen = geladen.modell.flaechen
    bg = vb.Baugruppe()
    # Gegenlager am Dichtsitz C. Der Messpunkt liegt auf der Y-Achse seines Querschnitts.
    bg.verbinde(1, flaechen[c], c, 2, flaechen[c], 1001)
    gegen = _flaeche(BRepPrimAPI_MakeBox(gp_Pnt(-10., -20., -20.), 180., 40., 40.).Shape(), [0, 1, 0])
    radius = vb.radius(flaechen[sitz])
    m = bg.neue_messgroesse(1, flaechen[sitz], sitz, 2, gegen, 1002, punkt=[x, radius, 0.])
    m.soll_min, m.soll_max = -100., 100.
    return bg, m, flaechen[sitz], gegen


@pytest.mark.parametrize(("wahl", "x"), [(0, 98.), (1, 18.5)])
def test_gemeinsame_lagerachse_im_step_mit_inter_und_extrapolation(bezugswelle, wahl, x):
    geladen, (a, b, _), sitze = bezugswelle
    sitz = sitze[wahl]
    bg, m, f, gegen = _radialmessung(bezugswelle, sitz, x)
    if wahl:
        lage = np.eye(4)
        lage[:3, :3] = Rotation.from_rotvec([.7, -.35, .4]).as_matrix()
        lage[:3, 3] = [51., -16., 83.]
        bg.lagen.update({1: lage.copy(), 2: lage.copy()})
    analyse = bm.Analyse(bg, geladen.pmi, lambda t, i: geladen.modell.flaechen[i] if t == 1 else None)
    ergebnis = analyse.berechne(m, f, gegen, proben=2000)
    # Radialer Versatz am Messquerschnitt: (1-t)*A + t*B. Jeder Sitz hat seinen eigenen Spielraum.
    t = (x - 62.) / (126.5 - 62.)
    breite = {sitz: .2, a: .24 * abs(1 - t), b: .12 * abs(t)}
    beitraege = {k.flaeche: k.bereich for k in ergebnis.beitraege if k.flaeche is not None}
    assert not ergebnis.hinweise and bm.bewertung(ergebnis, m)[0] == "gruen"
    assert beitraege == pytest.approx(breite)
    halb = sum(breite.values()) / 2
    assert (ergebnis.wc_min, ergebnis.wc_max) == pytest.approx((ergebnis.nenn - halb, ergebnis.nenn + halb))
    assert ergebnis.wc_min < ergebnis.mc_min < ergebnis.mc_max < ergebnis.wc_max
    kette = analyse.als_kette3d(m, f, gegen)
    assert not kette.hinweise and kette3d.schlussgroesse(kette) == pytest.approx(ergebnis.nenn)
    assert sum(g.werte["z"].oben - g.werte["z"].unten for g in kette.glieder) == pytest.approx(2 * halb)


def test_bezugsfach_und_rangfolge_bleiben_unterscheidbar(bezugswelle):
    geladen, (a, b, _), (innen, _) = bezugswelle
    bg, m, f, gegen = _radialmessung(bezugswelle, innen, 98.)
    pos = next(p for p in geladen.pmi if p.typ == "Position" and innen in p.flaechen)
    aufloesen = lambda t, i: geladen.modell.flaechen[i] if t == 1 else None
    # Zwei gleichzeitig geltende Toleranzen verwenden dieselbe Gruppe in verschiedener Reihenfolge.
    parallel = replace(pos, typ="Parallelism", wert=.1, bezuege=[BezugsRef("B-A")])
    e = bm.Analyse(bg, [*geladen.pmi, parallel], aufloesen).berechne(m, f, gegen)
    assert not e.hinweise and {k.flaeche for k in e.beitraege} >= {a, b, innen}
    # Getrennte Faecher: Der primaere Zylinder A bestimmt die Ausrichtung alleine.
    einzeln = replace(pos, bezuege=[BezugsRef("A", 1), BezugsRef("B", 2)])
    pmi = [einzeln if p is pos else p for p in geladen.pmi]
    e = bm.Analyse(bg, pmi, aufloesen).berechne(m, f, gegen)
    assert not e.hinweise
    # A erstreckt sich 16 mm um x=62. Messung 36 mm neben seiner Mitte.
    assert {k.flaeche: k.bereich for k in e.beitraege if k.flaeche is not None} == pytest.approx(
        {a: .24 * 36 / 8, innen: .2})


def test_drei_lagersitze_mit_festem_drittem_sitz(bezugswelle):
    geladen, (a, b, _), (innen, _) = bezugswelle
    bg, m, f, gegen = _radialmessung(bezugswelle, innen, 98.)
    pmi = [replace(p, bezuege=[BezugsRef("C-A-B")]) if p.typ == "Position" and innen in p.flaechen else p
           for p in geladen.pmi]
    analyse = bm.Analyse(bg, pmi, lambda t, i: geladen.modell.flaechen[i] if t == 1 else None)
    e = analyse.berechne(m, f, gegen, proben=1000)
    # Gleich gewichtete Ausgleichsgerade durch A, B und den fest mit dem Gegenlager verbundenen Sitz C.
    x = np.array([62., 126.5, 44.75])
    matrix = np.column_stack((np.ones(3), x))
    ga, gb, _ = [1., 98.] @ np.linalg.pinv(matrix)
    assert not e.hinweise
    assert {k.flaeche: k.bereich for k in e.beitraege if k.flaeche is not None} == pytest.approx(
        {a: abs(ga) * .24, b: abs(gb) * .12, innen: .2})


@pytest.mark.parametrize("fall", ["fehlt", "doppelt", "versetzt", "schief", "gemischt"])
def test_unsichere_gemeinsame_lagerachse_unterdrueckt_bewertung(bezugswelle, fall):
    geladen, (a, b, _), (innen, _) = bezugswelle
    bg, m, f, gegen = _radialmessung(bezugswelle, innen, 98.)
    flaechen = geladen.modell.flaechen
    ersatz = {"fehlt": None, "doppelt": flaechen[a], "gemischt": gegen}
    if fall in ("versetzt", "schief"):
        achse = gp_Ax2(gp_Pnt(118, .1, 0), gp_Dir(1, 0, 0)) if fall == "versetzt" else (
            gp_Ax2(gp_Pnt(118, 0, 0), gp_Dir(1, .02, 0)))
        ersatz[fall] = _flaeche(BRepPrimAPI_MakeCylinder(achse, 15., 17.).Shape())

    def form(teil, i):
        if teil == 1 and i == b:
            return ersatz[fall]
        return flaechen[i] if teil == 1 else None

    analyse = bm.Analyse(bg, geladen.pmi, form)
    ergebnis = analyse.berechne(m, f, gegen, proben=100)
    assert ergebnis.hinweise and not ergebnis.unbestimmt and not bm.bewertung(ergebnis, m)[0]
    assert analyse.als_kette3d(m, f, gegen).hinweise == ergebnis.hinweise


@pytest.mark.parametrize(("fall", "x"), [("koplanar", 25.), ("koplanar", 36.25),
                                         ("doppelt", 25.), ("versetzt", 25.)])
def test_gemeinsame_ebene_aus_zwei_auflagen(fall, x):
    # A x=0..10, B x=25..45, gleiche Tiefe. Flaechengewichte 1:2, gemeinsamer Schwerpunkt x=25.
    a, b, mess = _oben(0, 10), _oben(25, 20), _oben(x - 1, 2)
    unten = _flaeche(BRepPrimAPI_MakeBox(gp_Pnt(0., 0., 4.), 50., 12., 8.).Shape(), [0, 0, -1])
    bg = vb.Baugruppe()
    bg.verbinde(1, _oben(10, 5), 7, 2, unten, 70)
    m = bg.neue_messgroesse(1, mess, 1, 2, unten, 70, punkt=[x, 6., 4.])
    # Beide Auflagen beziehen sich auf die feste Anschlussebene Z.
    pmi = [_profil(1, .06, "A-B"), _datum(2, "A"), _datum(3, "B"), _datum(7, "Z"),
           _profil(2, .3, "Z"), _profil(3, .15, "Z")]
    if fall == "doppelt":
        b = a
    elif fall == "versetzt":
        b = _flaeche(BRepPrimAPI_MakeBox(gp_Pnt(25., 0., 1.), 20., 12., 4.).Shape(), [0, 0, 1])
    analyse = bm.Analyse(bg, pmi, lambda t, i: {2: a, 3: b}.get(i) if t == 1 else None)
    e = analyse.berechne(m, mess, unten, proben=1000)
    if fall != "koplanar":
        assert e.hinweise and not bm.bewertung(e, m)[0]
        return
    # x=36.25: eine Parallelverschiebung von A hebt sich auf. Seine Neigung wirkt noch mit.
    # Flaechentraegheitsmoment pro mm Tiefe = 6750 mm^3, fuer A allein 10^3/12 mm^3.
    breite = {1: .06, 2: .1, 3: .1} if x == 25. else {1: .06, 2: 11.25 * (10**3 / 12) / 6750 * .3 / 5, 3: .15}
    assert not e.hinweise
    assert {k.flaeche: k.bereich for k in e.beitraege if k.flaeche is not None} == pytest.approx(breite)
    assert e.wc_max - e.wc_min == pytest.approx(sum(breite.values()))


def test_zwei_getrennte_bezugsfaecher_mit_gleichem_rang(bezugswelle):
    geladen, _, (innen, _) = bezugswelle
    bg, m, f, gegen = _radialmessung(bezugswelle, innen, 98.)
    pmi = [replace(p, bezuege=[BezugsRef("A", 1), BezugsRef("B", 1)])
           if p.typ == "Position" and innen in p.flaechen else p for p in geladen.pmi]
    analyse = bm.Analyse(bg, pmi, lambda t, i: geladen.modell.flaechen[i] if t == 1 else None)
    e = analyse.berechne(m, f, gegen)
    assert any("Rangfolge" in h for h in e.hinweise) and not bm.bewertung(e, m)[0]
    assert analyse.als_kette3d(m, f, gegen).hinweise == e.hinweise
