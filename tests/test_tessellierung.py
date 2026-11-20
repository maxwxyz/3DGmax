import numpy as np
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
from OCC.Core.Poly import Poly_Triangulation
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods
from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from programm.kern.ausrichten import tesselliere


def test_geteiltes_netz_in_instanzlage(monkeypatch):
    form = BRepPrimAPI_MakeSphere(5.).Shape()
    face = topods.Face(TopExp_Explorer(form, TopAbs_FACE).Current())
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 1)), .78)
    t.SetTranslationPart(gp_Vec(10, -7, 3))
    gedreht = topods.Face(face.Moved(TopLoc_Location(t)).Reversed())
    flaechen = [gedreht, face, face]
    aufrufe = []
    auslesen = Poly_Triangulation.MapNodeArray

    def zaehle(tri):
        aufrufe.append(1)
        return auslesen(tri)

    monkeypatch.setattr(Poly_Triangulation, "MapNodeArray", zaehle)
    netze = tesselliere(flaechen)
    assert len(aufrufe) == 1
    for f, (punkte, dreiecke) in zip(flaechen, netze, strict=True):
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        erwartet = [tri.Node(i).Transformed(loc.Transformation()).Coord() for i in range(1, tri.NbNodes() + 1)]
        np.testing.assert_allclose(punkte, erwartet, rtol=0, atol=1e-13)
        indizes = [tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]
        np.testing.assert_array_equal(dreiecke, np.array(indizes) - 1)
    for punkte, dreiecke in netze[1:]:
        assert not np.shares_memory(dreiecke, netze[0][1])
    assert not np.shares_memory(netze[1][0], netze[2][0])
