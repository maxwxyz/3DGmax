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


def test_feinere_analyse_in_zwei_lagen_bei_grober_anzeige(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from programm.kern import ausrichten, vergleich_geo

    form = BRepPrimAPI_MakeSphere(12.).Shape()
    f = topods.Face(TopExp_Explorer(form, TopAbs_FACE).Current())
    BRepMesh_IncrementalMesh(form, 2., False, 1.2, False)
    original = BRep_Tool.Triangulation(f, TopLoc_Location())
    assert original.Deflection() > 1.
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(15, 6, 9))
    f2 = topods.Face(f.Moved(TopLoc_Location(t)).Reversed())
    modell = SimpleNamespace(flaechen=[f], flaechen_index=lambda _: 0)
    aufrufe = []

    def meshen(*args):
        aufrufe.append(args[1])
        return BRepMesh_IncrementalMesh(*args)

    monkeypatch.setattr(ausrichten, "BRepMesh_IncrementalMesh", meshen)
    with ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(tesselliere, [f, f2], .01, modell=modell) for _ in range(2)]
        paare = [job.result() for job in jobs]
    assert aufrufe == [.01]
    for (p, tri), (q, ix) in paare:
        assert len(tri) > original.NbTriangles()
        assert 12 - np.linalg.norm(p[tri].mean(axis=1), axis=1).min() <= .01
        np.testing.assert_allclose(q, p + [15, 6, 9])
        np.testing.assert_array_equal(ix, tri)
    # Die Vorstufe des echten Geometrievergleichs verwendet dasselbe feinere Netz.
    seite = vergleich_geo.bereite_vor(modell, anzahl=50, feinheit=.05)
    assert aufrufe == [.01] and len(seite.netze[0][1]) == len(paare[0][0][1])
    assert BRep_Tool.Triangulation(f, TopLoc_Location()) == original


def test_kreisscheibenrand_trotz_ebenheit_und_unveraendertes_importnetz():
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.TopoDS import TopoDS_Face

    form = BRepPrimAPI_MakeCylinder(12., 3.).Shape()
    BRepMesh_IncrementalMesh(form, 2., False, 1.2, False)
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while BRepAdaptor_Surface(f := topods.Face(ex.Current())).GetType() != GeomAbs_Plane:
        ex.Next()
    alt = BRep_Tool.Triangulation(f, TopLoc_Location())
    assert alt.Deflection() < 1e-8
    (punkte, _), = tesselliere([f], .01)
    assert len(punkte) > 4 * alt.NbNodes()
    netz = TopoDS_Face()
    BRep_Builder().MakeFace(netz, alt)
    (roh, ix), = tesselliere([netz], .001)
    assert len(roh) == alt.NbNodes() and len(ix) == alt.NbTriangles()
    assert BRep_Tool.Triangulation(netz, TopLoc_Location()) == alt


def test_abtastung_mit_leeren_und_entarteten_flaechen():
    from programm.kern.ausrichten import abtasten

    p = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    tri = np.array([[0, 1, 2]])
    leer = (p, tri[:0])
    entartet = (p, np.zeros((65536, 3), dtype=int))
    netze = [leer, (p, tri), entartet, leer, (p * 2 + [0, 0, 1], tri)]
    punkte, flaechen = abtasten(iter(netze), 100)
    # Die zweite echte Flaeche hat den vierfachen Inhalt. Beide liegen auf verschiedenen Ebenen.
    rng = np.random.default_rng(1)
    wahl = rng.choice(2, size=100, p=[.2, .8])
    np.testing.assert_array_equal(flaechen, np.where(wahl, 4, 1))
    np.testing.assert_allclose(punkte[:, 2], wahl, atol=2e-16)
    s, r = np.sqrt(rng.random(100)), rng.random(100)
    np.testing.assert_allclose(punkte[:, 0], s * (1 - r) * (1 + wahl))
    np.testing.assert_allclose(punkte[:, 1], s * r * (1 + wahl))
    assert abtasten([leer, entartet])[0].shape == (0, 3)


def test_gemischte_pmi_hinweisflaechen_in_instanzlage():
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.TopoDS import TopoDS_Face
    from OCC.Core.gp import gp_Pln
    from programm.kern import pmi_erzeugen, plausibilitaet
    from programm.kern.laden import _poly

    ebene = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0,0,0), gp_Dir(0,0,1)), -10.,10.,-10.,10.).Face()
    netz = TopoDS_Face()
    BRep_Builder().MakeFace(netz, _poly([[0,0,0],[4,0,0],[0,4,0]], [[0,1,2]]))
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(10,0,4))
    netz = topods.Face(netz.Moved(TopLoc_Location(t)))
    flaechen = [ebene, netz]
    assert plausibilitaet.ebene_zur_achse(flaechen) is None
    assert plausibilitaet.ebene_zur_achse(flaechen[::-1]) is None
    cache = {}
    for ziel, erwartet in (([11,1,5],[11,1,4]), ([11,5,5],[10,4,4]), ([2,1,-1],[2,1,0])):
        np.testing.assert_allclose(pmi_erzeugen._naechster_punkt(flaechen, np.array(ziel), cache), erwartet)
    assert len(cache) == 1
