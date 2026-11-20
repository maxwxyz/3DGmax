"""Analytische Fussboegen und Kopf-Fasen an einem evolventischen Referenzrad."""

import math

import numpy as np
import pytest

from programm.kern import verzahnung as vz
from programm.kern import verzahnung_daten as vd


def _rad(asymmetrisch=False, parabelfuss=False):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.GC import GC_MakeArcOfCircle
    from OCC.Core.Geom import Geom_BezierCurve
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.gp import gp_Pnt, gp_Vec
    z, modul = 40, 2.0
    r = z * modul / 2
    rb, rf, ra = r * math.cos(math.radians(20)), r - 1.25 * modul, r + modul
    r0, rfase = rf + 0.65, ra - 0.32
    teilung = 2 * math.pi / z

    def inv(radius):
        a = math.acos(rb / radius)
        return math.tan(a) - a

    def halb(radius, fase=True):
        winkel = teilung / 4 + inv(r) - inv(radius)
        return winkel - (0.22 / ra if fase and radius == ra else 0)

    def punkt(rad, winkel):
        return gp_Pnt(rad * math.cos(winkel), rad * math.sin(winkel), 0)

    draht = BRepBuilderAPI_MakeWire()
    for i in range(z):
        c = i * teilung
        radien = [*np.linspace(r0, rfase, 14), ra]
        links = [punkt(rad, c - halb(rad)) for rad in radien]
        rechts = [punkt(rad, c + halb(rad, not (asymmetrisch and i == 0))) for rad in radien]
        for p, q in zip(links, links[1:]):
            draht.Add(BRepBuilderAPI_MakeEdge(p, q).Edge())
        kopf = GC_MakeArcOfCircle(links[-1], punkt(ra, c), rechts[-1]).Value()
        draht.Add(BRepBuilderAPI_MakeEdge(kopf).Edge())
        for p, q in zip(rechts[:0:-1], rechts[-2::-1]):
            draht.Add(BRepBuilderAPI_MakeEdge(p, q).Edge())
        naechster = punkt(r0, c + teilung - halb(r0))
        if parabelfuss:
            pole = TColgp_Array1OfPnt(1, 3)
            pole.SetValue(1, rechts[0])
            pole.SetValue(2, punkt(2 * rf - r0 * math.cos(teilung / 2 - halb(r0)), c + teilung / 2))
            pole.SetValue(3, naechster)
            fuss = Geom_BezierCurve(pole)
        else:
            mitte = punkt(rf + (0.1 if asymmetrisch and i == 0 else 0), c + teilung / 2)
            fuss = GC_MakeArcOfCircle(rechts[0], mitte, naechster).Value()
        draht.Add(BRepBuilderAPI_MakeEdge(fuss).Edge())
    # Sollradius aus Sehnenlaenge und Pfeilhoehe.
    winkel = teilung / 2 - halb(r0)
    pfeil = r0 * math.cos(winkel) - rf
    sehne = 2 * r0 * math.sin(winkel)
    rho = sehne ** 2 / (8 * pfeil) + pfeil / 2
    form = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(draht.Wire()).Face(), gp_Vec(0, 0, 8)).Shape()
    return form, rho, ra - rfase


@pytest.mark.parametrize("asymmetrisch", [False, True])
def test_fussradius_und_kopffase(asymmetrisch):
    f, rho, fase = _rad(asymmetrisch)
    v = vz.erkenne(f, "Rad")
    assert v is not None and v.z == 40
    if asymmetrisch:
        assert v.fussradius is None and v.kopffase is None
    else:
        assert v.fussradius == pytest.approx(rho, abs=1e-6)
        assert v.kopffase == pytest.approx(fase, abs=1e-6)
        daten = vd.datenblatt([v], [])["zahnraeder"][0]["mikrogeometrie"]
        assert daten["fussrundungsradius"] == v.fussradius and daten["kopffase_radial"] == v.kopffase
        assert daten["kopfruecknahme"] is None


def test_ruecknahme_ohne_nachweisbare_fase():
    from werkzeuge import zahnrad
    v = vz.erkenne(zahnrad.zahnrad(23, 2.0, 9.0, ruecknahme=(0.02, 0.6)))
    assert v.kopffase is None and v.fussradius is None
    assert vd.profil(v).ca == pytest.approx(0.02, abs=0.003)


def test_parabelfuss_liefert_keinen_kreisradius():
    form, _, fase = _rad(parabelfuss=True)
    v = vz.erkenne(form, "Parabelfuß")
    assert v.fussradius is None and v.kopffase == pytest.approx(fase, abs=1e-6)
