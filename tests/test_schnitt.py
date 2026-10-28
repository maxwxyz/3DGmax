"""Schnittkontur fuer die Anzeige (aus der Triangulierung) gegen die exakte Kontur (kern.schnitt)."""

import numpy as np

from programm.kern import schnitt


def _platte_mit_bohrung():
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(100, 60, 20).Shape(), BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(50, 30, -1), gp_Dir(0, 0, 1)), 10, 22).Shape()).Shape()


def test_anzeigekontur_wie_exakt():
    """Schnitt durch die Bohrungsachse: zwei Rechtecke (links und rechts der Bohrung), geschlossen, gleiche Lage."""
    form = _platte_mit_bohrung()
    e = schnitt.Ebene(np.array([0.0, 30.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    schnell, exakt = schnitt.kontur_anzeige(form, e), schnitt.kontur(form, e)
    assert len(schnell) == len(exakt) == 2
    for zug in schnell:
        assert np.allclose(zug[:, 1], 30.0) and np.linalg.norm(zug[0] - zug[-1]) < 1e-6  # in der Ebene, geschlossen
    umfang = lambda zuege: sum(float(np.linalg.norm(np.diff(z, axis=0), axis=1).sum()) for z in zuege)  # noqa: E731
    assert abs(umfang(schnell) - umfang(exakt)) < 1e-3 * umfang(exakt)
    # Ebene ausserhalb: nichts
    assert schnitt.kontur_anzeige(form, schnitt.Ebene(np.array([0.0, 99.0, 0.0]), np.array([0.0, 1.0, 0.0]))) == []


def test_verketten_schnell_linear():
    """Viele Stuecke eines Kreises werden zu einem geschlossenen Zug verbunden (ohne quadratischen Aufwand)."""
    w = np.linspace(0, 2 * np.pi, 5001)
    p = np.c_[np.cos(w), np.sin(w), np.zeros_like(w)]
    seg = np.stack([p[:-1], p[1:]], axis=1)[np.random.default_rng(1).permutation(5000)]
    zuege = schnitt._verketten_schnell(seg, 1e-9)
    assert len(zuege) == 1 and len(zuege[0]) == 5001
