"""Messen: Rechnungen gegen NIST-Masse und das Werkzeug in der Oberflaeche."""

import itertools

import pytest

from programm.kern import messen
from programm.kern.pmi import MASS
from programm.kern.pmi_lesen import lies_pmi


def _flaechen(m, p):
    return [m.flaechen[i] for i in sorted(p.flaechen)]


def test_durchmesser_wie_nist(ctc01):
    for p in lies_pmi(ctc01):
        if p.art == MASS and p.typ == "Size_Diameter" and p.nennwert:
            r = messen.radius(_flaechen(ctc01, p)[0])
            assert abs(2 * r.wert - p.nennwert) < 1e-6
            assert r.zusatz.startswith("Ø")


def test_winkel_wie_nist(ctc01):
    p = next(p for p in lies_pmi(ctc01) if p.typ == "Location_Angular")
    w = messen.winkel(*_flaechen(ctc01, p)[:2])
    assert min(abs(w.wert - 60), abs(180 - w.wert - 60)) < 1e-6


def test_abstand_und_csv(ctc01):
    fl = ctc01.flaechen
    m = messen.abstand(fl[0], fl[1])
    assert m.wert >= 0 and len(m.punkte) == 2
    m.nummer = 1
    text = messen.als_csv([m])
    assert text.splitlines()[0].startswith("Nr;Art;Wert")
    assert "abstand" in text


def test_fang_endpunkt():
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCC.Core.gp import gp_Pnt
    kante = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(10, 0, 0)).Edge()
    art, p = messen.fange(kante, gp_Pnt(9.6, 0, 0), 1.0)
    assert art == "Endpunkt" and abs(p.X() - 10) < 1e-9
    art, p = messen.fange(kante, gp_Pnt(5.2, 0, 0), 1.0)
    assert art == "Mitte"
    art, _ = messen.fange(kante, gp_Pnt(3, 0, 0), 1.0)
    assert art.startswith("auf ")


def test_wandstaerke_quader():
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    box = BRepPrimAPI_MakeBox(10, 20, 7).Shape()
    ex = TopExp_Explorer(box, TopAbs_FACE)
    werte = set()
    while ex.More():
        f = ex.Current()
        werte.add(round(messen.wandstaerke(box, f, messen._mittelpunkt(f)).wert, 6))
        ex.Next()
    assert werte == {10.0, 20.0, 7.0}


def test_nicht_messbar():
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    f = TopExp_Explorer(BRepPrimAPI_MakeBox(1, 1, 1).Shape(), TopAbs_FACE).Current()
    with pytest.raises(ValueError):
        messen.radius(f)


def test_messwerkzeug_in_oberflaeche(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    f.aktionen["messen"].trigger()
    assert f.messen.modus == "abstand" and f.ansicht.messmodus
    fl = f.erg.modell.flaechen
    a, b = messen._mittelpunkt(fl[0]), messen._mittelpunkt(fl[5])
    f.messen.fang.setChecked(False)
    f.messen.element(fl[0], (a.X(), a.Y(), a.Z()))
    assert not f.messen.messungen
    f.messen.element(fl[5], (b.X(), b.Y(), b.Z()))
    assert len(f.messen.messungen) == 1 and f.ansicht.messungen
    # Radius an einem Zylinder (Durchmesser 35)
    zyl = next(p for p in f.erg.pmi if p.typ == "Size_Diameter" and p.nennwert == 35)
    fz = fl[sorted(zyl.flaechen)[0]]
    f.messen.setze_modus("radius")
    c = messen._mittelpunkt(fz)
    f.messen.element(fz, (c.X(), c.Y(), c.Z()))
    assert abs(f.messen.messungen[-1].wert - 17.5) < 1e-6
    # Wandstaerke braucht den Koerper aus dem Baum
    f.messen.setze_modus("wandstaerke")
    f.messen.element(fl[0], (a.X(), a.Y(), a.Z()))
    assert f.messen.messungen[-1].art == "wandstaerke" and f.messen.messungen[-1].wert > 0
    ziel = tmp_path / "m.csv"
    assert f.messen.speichere_csv(str(ziel)) and ziel.read_text(encoding="utf-8-sig").count("\n") == 4
    f.aktionen["messen_ende"].trigger()
    assert f.messen.modus is None and not f.ansicht.messmodus
    f.messen.loesche_alle()
    assert not f.ansicht.messungen
