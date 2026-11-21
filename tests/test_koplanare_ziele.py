"""Anzahl koplanarer Flaechen, Trennfugen und Lage im Modell fuer eine Zeichnungsangabe."""

from types import SimpleNamespace

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt

from programm.kern.koplanare_ziele import pruefe_koplanar, zielanzahl


def _ebene(punkte):
    rand = BRepBuilderAPI_MakePolygon()
    for p in punkte:
        rand.Add(gp_Pnt(*p))
    rand.Close()
    return BRepBuilderAPI_MakeFace(rand.Wire()).Face()


def test_getrennte_dreiecke_trotz_ueberlappender_boxen_und_beruehrender_split():
    f = _ebene([(0,0,0), (2,0,0), (0,2,0)])
    frei = _ebene([(2,2,0), (1,2,0), (2,1,0)])
    geteilt = _ebene([(2,2,0), (0,2,0), (2,0,0)])
    m = SimpleNamespace(flaechen=[f, frei, geteilt])
    assert pruefe_koplanar(2, {0,1}, m).grund == "getrennt"
    assert pruefe_koplanar(2, {0,2}, m).grund == "beruehrung"
    assert pruefe_koplanar(2, {0,2}, m).status == "offen"
    assert pruefe_koplanar(3, {0,1}, m).grund == "anzahl"


def test_ebenen_mit_anderem_ursprung_und_neigung():
    def flaeche(ort, normale):
        ebene = gp_Pln(gp_Pnt(*ort), gp_Dir(*normale))
        return BRepBuilderAPI_MakeFace(ebene, 0, 1, 0, 1).Face()
    m = SimpleNamespace(flaechen=[flaeche((0,0,0), (0,0,1)), flaeche((20,20,0), (0,0,-1)),
                                  flaeche((20,20,.01), (0,0,1)), flaeche((20,20,0), (0,.1,1))])
    assert pruefe_koplanar(2, {0,1}, m).grund == "getrennt"
    for i in (2,3):
        assert pruefe_koplanar(2, {0,i}, m).grund == "ebenen"


def test_nur_eindeutige_anzahl_und_verfuegbare_einzelteilgeometrie(ftc07):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Face
    from programm.kern.pmi_vorschlag import _flaeche_info
    text = "⌓ | .07 | A | B | C\n⌓ | .015 | A\n4 COPLANAR SURFACES\nSIM REQT"
    assert zielanzahl(text) == 4
    assert zielanzahl(text+"\n2 COPLANAR SURFACES") is None
    assert zielanzahl(text.replace("4 COPLANAR", "UP TO 4 COPLANAR")) is None
    assert pruefe_koplanar(4, {3,265,266,267}, ftc07).status == "gleich"
    assert pruefe_koplanar(4, {8}, ftc07).grund == "anzahl"
    assert pruefe_koplanar(4, {3,8,265,266}, ftc07).grund == "ebenen"
    zyl = next(i for i,f in enumerate(ftc07.flaechen) if _flaeche_info(f)[0] == "zylinder")
    assert pruefe_koplanar(2, {3,zyl}, ftc07).grund == "gekruemmt"
    face = TopoDS_Face()
    BRep_Builder().MakeFace(face)
    for ids,m in [({1}, None), (set(), ftc07), ({-1, 3}, ftc07), ({0}, SimpleNamespace(flaechen=[face]))]:
        assert pruefe_koplanar(2, ids, m).status == "offen"


def test_lage_desselben_flaechenprototyps_bleibt_offen():
    from programm.kern.blattverbund import Verbundindex
    from programm.kern.laden import lade_step
    from tests.conftest import pfad
    m = lade_step(pfad("baugruppe.stp"))
    index = Verbundindex([], m)
    assert index.mehrfach_verbaut
    p = SimpleNamespace(flaechen={next(iter(index.mehrfach_verbaut))})
    text = "⌓ | .07 | A\n⌓ | .015 | A\n4 COPLANAR SURFACES"
    assert index.koplanar(text, p, p).grund == "vorkommen"


def test_ebene_aus_polen_und_platzierter_flaeche():
    from OCC.Core.Geom import Geom_BezierSurface
    from OCC.Core.TColgp import TColgp_Array2OfPnt
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Trsf, gp_Vec
    pole = TColgp_Array2OfPnt(1, 3, 1, 3)
    for i in range(1,4):
        for j in range(1,4):
            pole.SetValue(i, j, gp_Pnt(i,j,0))
    face = BRepBuilderAPI_MakeFace(Geom_BezierSurface(pole), 1e-7).Face()
    def verschoben(z):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(10, 0, z))
        return topods.Face(face.Moved(TopLoc_Location(t)))
    m = SimpleNamespace(flaechen=[face, verschoben(0), verschoben(2)])
    assert pruefe_koplanar(2, {0,1}, m).grund == "getrennt"
    assert pruefe_koplanar(2, {0,2}, m).grund == "ebenen"


def test_wortgleiche_unbekannte_geometrische_anforderung_bleibt_offen(ftc07):
    from programm.kern.blattverbund import Verbundindex, pruefe_rahmen
    from programm.kern.pmi_step import lies_toleranzen
    from programm.kern.zeichnungsabgleich import Blattangabe
    pmis = lies_toleranzen(ftc07)
    nach_id = {p.step_id:p for p in pmis}
    a = Blattangabe(2, (0,0,1,1), "⌓ | .070 | A | B | C\n⌓ | .015 | A\n4 COPLANAR SURFACES",
                    verbundrahmen=True, modell=nach_id[14614], unten=nach_id[14623])
    index = Verbundindex(pmis, ftc07)
    for zusatz, status in [("", "gleich"), ("\nEXCEPT CORNERS", "offen")]:
        a.text += zusatz
        a.modell.beschreibung = a.unten.beschreibung = " ".join(a.text.splitlines()[2:])
        r = pruefe_rahmen(a, 25.4, index)
        assert r.koplanar.status == "gleich" and r.wortlaut == "gleich" and r.status == status
