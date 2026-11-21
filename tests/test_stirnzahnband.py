"""Neun verrundete Stirnzaehne, zentrale Bohrung und rueckseitiger Absatz."""

import numpy as np
import pytest


def _ringe(z=9, flach=False, glatt=False, bund=0.):
    phi = np.arange(z*24) * 2*np.pi / (z*24)
    muster = (1 + np.tanh(1.8*np.cos(z*phi))/np.tanh(1.8)) / 2
    aussen = 16.1 + 3.9*muster

    def ring(r, h):
        return np.column_stack([r*np.cos(phi), r*np.sin(phi), np.broadcast_to(h, phi.shape)])

    ringe = [ring(6.7, -2), ring(6.7, 0), ring(9, 0)]
    for t in (.08, .25, .5, .8, 1.):
        r = 9 + t*(aussen-9)
        h = 0 if flach else .43*(r-9)
        amplitude = 2.8 if flach else 2.8 + 3.2*(r-9)/11
        ringe.append(ring(r, (h + amplitude*(0 if glatt else muster))*min(1., t/.25)))
    ringe.extend((ring(aussen, -2+.025*(aussen-16)**2), ring(14.8, -3.2), ring(13, -4.25),
                  ring(7.2, -4.7), ring(7.2, -2)))
    for reihe in ringe[2:8]:
        r = np.linalg.norm(reihe[:, :2], axis=1)
        reihe[:, 2] += bund * np.maximum(0, 1 - (r-9)/3)**2
    return np.array(ringe)


def _stirnradform(bund=0.):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeSolid, BRepBuilderAPI_MakeWire
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.BRepLib import breplib
    from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCC.Core.GeomAPI import GeomAPI_Interpolate
    from OCC.Core.TColgp import TColgp_HArray1OfPnt
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Pnt

    loft = BRepOffsetAPI_ThruSections(False, True)
    loft.CheckCompatibility(False)
    draehte = []
    for ring in _ringe(bund=bund):
        pts = TColgp_HArray1OfPnt(1, len(ring))
        for k, p in enumerate(ring, 1):
            pts.SetValue(k, gp_Pnt(*p))
        kurve = GeomAPI_Interpolate(pts, True, 1e-8)
        kurve.Perform()
        draehte.append(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(kurve.Curve()).Edge()).Wire())
    for draht in [*draehte, draehte[0]]:
        loft.AddWire(draht)
    loft.Build()
    form = BRepBuilderAPI_MakeSolid(topods.Shell(loft.Shape())).Solid()
    assert breplib.OrientClosedSolid(form) and BRepCheck_Analyzer(form).IsValid()
    return form


@pytest.mark.parametrize("z,flach,glatt,bund", [(7, False, False, 0), (9, False, False, 0),
    (11, False, False, 0), (9, True, False, 0), (9, False, True, 0),
    (9, True, False, 4), (9, False, False, 4)])
def test_axiales_zahnrelief(z, flach, glatt, bund):
    from scipy.spatial.transform import Rotation
    from programm.kern import stirnzahnband, verzahnung as vz
    p = _ringe(z, flach, glatt, bund)
    a, b = p, np.roll(p, -1, axis=1)
    c, d = np.roll(b, -1, axis=0), np.roll(a, -1, axis=0)
    t = np.vstack([np.stack(abc, axis=2).reshape(-1, 3, 3) for abc in ((a,b,c), (a,c,d))])
    rot = Rotation.from_rotvec([.7, 2.1, -.3])
    t = rot.apply(t.reshape(-1, 3)).reshape(t.shape) + [27., 11., -48.]
    ergebnisse = vz._aus_netz(t, "Rad", True, True)
    kandidaten = [v for v in ergebnisse if isinstance(v, stirnzahnband.Stirnzahnband)]
    if flach or glatt:
        assert not kandidaten
    else:
        v, = kandidaten
        assert v.z == z and v.relief > 3 and v.radien[1]-v.radien[0] > 4


@pytest.mark.parametrize("bund", [0., 4.])
def test_stirnseitiges_rad_aus_step(fenster, tmp_path, bund):
    from werkzeuge.zahnrad import speichere
    from programm.kern.verzahnung_daten import datenblatt
    from PySide6 import QtWidgets
    pfad = speichere(_stirnradform(bund), str(tmp_path / "Bolzenrad.step"), "Rad")
    fenster.lade(pfad, warten=True)
    k, = fenster.erg.baum.blaetter()
    fenster.baum.baum.setCurrentItem(fenster.baum._knoten[k.nummer])
    fenster.aktionen["verzahnung"].trigger()
    assert fenster._verzahnung_lader.wait(30000)
    QtWidgets.QApplication.processEvents()
    v, = fenster._verzahnung.liste
    assert v.z == 9 and v.art == "kegelrad_stirnseitig"
    assert datenblatt([v], [])["sonderprofile"][0]["anzahl"] == 9
    if bund:
        ziel = fenster.exportiere_baumauswahl(str(tmp_path / "Ausgleichsrad-mit-Bund.step"))
        assert ziel
        fenster.lade(ziel, warten=True)
        fenster.aktionen["verzahnung"].trigger()
        assert fenster._verzahnung_lader.wait(30000)
        QtWidgets.QApplication.processEvents()
        erneut, = fenster._verzahnung.liste
        assert (erneut.art, erneut.z) == (v.art, v.z)
        assert erneut.radien == pytest.approx(v.radien)
