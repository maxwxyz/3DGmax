"""Ein benanntes Bezugselement mit mehreren Flaechen im Starrkoerpermodell."""

from dataclasses import replace

import numpy as np
import pytest
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.gp import gp_Pnt

from programm.kern import baugruppe_mass as bm, verbindung as vb
from tests.test_merkmalstreuung import _datum, _flaeche, _oben, _profil


@pytest.mark.parametrize("fall", ["auflagen", "zwei_definitionen", "flaeche_fehlt", "fremde_ebene", "ueberlappung", "ueberlappung_d_e"])
def test_gemeinsame_auflagen_eines_einzelbezugs(fall):
    a, b, mess = _oben(0, 10), _oben(25, 20), _oben(24, 2)
    unten = _flaeche(BRepPrimAPI_MakeBox(gp_Pnt(0., 0., 4.), 50., 12., 8.).Shape(), [0, 0, -1])
    bg = vb.Baugruppe()
    bg.verbinde(1, _oben(10, 5), 7, 2, unten, 70)
    m = bg.neue_messgroesse(1, mess, 1, 2, unten, 70, punkt=[25., 6., 4.])
    m.soll_min, m.soll_max = -5., 5.
    pmi = [_profil(1, .06, "D"), replace(_datum(2, "D"), flaechen={2, 3}), _datum(7, "Z"),
           _profil(2, .3, "Z"), _profil(3, .15, "Z")]
    if fall == "zwei_definitionen":
        pmi[1] = _datum(2, "D")
        pmi.append(_datum(3, "D"))
    if fall == "ueberlappung_d_e":
        pmi[0], pmi[1] = _profil(1, .06, "D-E"), _datum(2, "D")
        pmi.append(_datum(3, "E"))
        b = _oben(3, 12)
    if fall == "ueberlappung":
        b = a
    if fall == "flaeche_fehlt":
        b = None
    if fall == "fremde_ebene":
        b = unten
    formen = {2: a, 3: b}
    analyse = bm.Analyse(bg, pmi, lambda t, i: formen.get(i) if t == 1 else None)
    e = analyse.berechne(m, mess, unten, proben=200)
    assert analyse.als_kette3d(m, mess, unten).hinweise == e.hinweise
    if fall == "auflagen":
        assert not e.hinweise and bm.bewertung(e, m)[0] == "gruen"
        assert {w.flaeche: w.bereich for w in e.beitraege if w.flaeche is not None} == pytest.approx({
            1: .06, 2: .1, 3: .1})
    else:
        assert e.hinweise and not bm.bewertung(e, m)[0]


@pytest.fixture(scope="module")
def ftc_daten():
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    return lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))


@pytest.mark.parametrize("fall", ["nominal", "gedreht", "original", "doppelt", "andere_wand", "einzelrahmen", "ueberlagert", "gegenseite"])
def test_ftc10_geteilte_bezuege_im_projektionsrahmen(ftc_daten, fall):
    ftc = ftc_daten
    formen = ftc.modell.flaechen
    quelle = next(p for p in ftc.pmi if p.step_id == 19580)
    bezuege = [p for p in ftc.pmi if p.art == "bezug" and p.name in ("D", "E", "B")]
    e_datum = next(p for p in bezuege if p.name == "E")
    assert e_datum.flaechen == {242, 243}
    pmi = [quelle, *bezuege]
    if fall == "original":
        pmi = ftc.pmi
    elif fall == "doppelt":
        pmi.remove(e_datum)
        pmi.extend(replace(e_datum, flaechen={i}) for i in (242, 243))
    elif fall == "einzelrahmen":
        pmi.append(_profil(243, .2, "D"))
    elif fall == "andere_wand":
        pmi[pmi.index(e_datum)] = replace(e_datum, flaechen={242, 164})
    def form_fuer(teil, i):
        if fall == "gegenseite" and i == 243:
            from OCC.Core.TopoDS import topods
            return topods.Face(formen[i].Reversed())
        if fall == "ueberlagert" and i == 243:
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Copy
            from OCC.Core.TopoDS import topods
            return topods.Face(BRepBuilderAPI_Copy(formen[242]).Shape())
        return formen[i]
    bg = vb.Baugruppe()
    if fall == "gedreht":
        lage = np.eye(4)
        lage[:3, :3] = [[0., -1., 0.], [0., 0., 1.], [-1., 0., 0.]]
        lage[:3, 3] = [35., -20., 4.]
        bg.lagen[1] = lage
    a = bm.Analyse(bg, pmi, form_fuer, formen.__getitem__)
    for wand in (238, 239):
        m = bm.Messgroesse(1, 1, 87, 1, wand, bm.PUNKT_ACHSE, punkt=[35.9, 28.6, -30.],
                           konstruktions_pmi=19580, soll_min=0., soll_max=8.)
        e = a.berechne(m, formen[87], formen[wand], proben=100)
        k = a.als_kette3d(m, formen[87], formen[wand])
        assert e.hinweise == k.hinweise
        beitrag, = [b for b in e.beitraege if b.flaeche == wand]
        assert beitrag.bereich == pytest.approx(.8)
        if fall in ("nominal", "gedreht"):
            assert not e.hinweise and bm.bewertung(e, m)[0] == "gruen"
            assert (e.wc_min, e.wc_max) == pytest.approx((3.6, 4.4))
            assert e.wc_min < e.mc_min < e.mc_max < e.wc_max
            assert "Bezug D" in beitrag.text
        elif fall == "original":
            assert e.hinweise and not bm.bewertung(e, m)[0]
            assert any("⌓" in h for h in e.hinweise)
            assert all("Bezug D nicht" not in h and "Bezug E nicht" not in h for h in e.hinweise)
        else:
            assert any("Bezug E " in h for h in e.hinweise) and not bm.bewertung(e, m)[0]
