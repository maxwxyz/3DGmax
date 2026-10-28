"""Verzahnung aus der Geometrie (PLAN §8.27) an selbst erzeugten Evolventenraedern mit bekannten Sollwerten."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "werkzeuge"))


@pytest.mark.parametrize("z, mn, b, beta, x, innen", [
    (23, 2.0, 20.0, 0.0, 0.0, False),
    (23, 2.0, 20.0, 15.0, 0.2, False),
    (31, 1.25, 10.0, -20.0, -0.1, False),
    (40, 1.5, 12.0, 0.0, 0.0, True),
    (12, 4.0, 30.0, 0.0, 0.3, False),
])
def test_stirnrad_erkennen(z, mn, b, beta, x, innen):
    import zahnrad
    from programm.kern import verzahnung as vz
    v = vz.erkenne(zahnrad.zahnrad(z, mn, b, 20.0, beta, x, innen), "Rad")
    assert v is not None and v.z == z and v.innen == innen and v.alpha_n == 20.0
    assert abs(v.mn - mn) < 1e-3 * mn and abs(v.b - b) < 0.01 and abs(v.x - x) < 0.02
    assert abs(v.beta - abs(beta)) < 0.02 and v.hand == ("" if not beta else "rechts" if beta > 0 else "links")
    d = z * mn / math.cos(math.radians(beta))
    assert abs(v.d - d) < 0.05 and not v.hinweise
    at = math.atan(math.tan(math.radians(20.0)) / math.cos(math.radians(beta)))
    assert abs(v.db - d * math.cos(at)) < 0.03
    ha = mn * (1.0 + x) if not innen else -mn * (1.0 - x)
    assert abs(v.da - (d + 2 * ha)) < 0.02
    if not innen:  # Zahnweite nach ISO 21771 mit den Sollwerten
        wk = mn * math.cos(math.radians(20)) * ((v.k - 0.5) * math.pi + z * (math.tan(at) - at)) + \
            2 * x * mn * math.sin(math.radians(20))
        assert abs(v.wk - wk) < 0.03


def test_kein_zahnrad_und_export(tmp_path):
    import json
    import zahnrad
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from programm.kern import verzahnung as vz
    assert vz.erkenne(BRepPrimAPI_MakeBox(10, 20, 30).Shape()) is None
    assert vz.erkenne(BRepPrimAPI_MakeCylinder(10, 5).Shape()) is None
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.gp import gp_Pnt, gp_Vec
    poly = BRepBuilderAPI_MakePolygon()
    for i in range(6):  # Sechskant: periodisch, aber keine Verzahnung
        poly.Add(gp_Pnt(10 * math.cos(i * math.pi / 3), 10 * math.sin(i * math.pi / 3), 0))
    poly.Close()
    assert vz.erkenne(BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(), gp_Vec(0, 0, 8)).Shape()) is None
    v = vz.erkenne(zahnrad.zahnrad(17, 3.0, 15.0), "z17")
    csv = vz.als_csv([v])
    assert "z17" in csv and "17" in csv.splitlines()[2]
    d = json.loads(json.dumps(v.als_dict()))
    assert d["z"] == 17 and abs(d["mn"] - 3.0) < 0.01
