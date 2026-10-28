"""Von der Funktion zur Tolerierung: Rollen je Flaeche -> Bezugssystem 3-2-1 -> PMI-Vorschlaege (kern.funktion)."""

from types import SimpleNamespace

import pytest

from programm.kern import funktion as fu
from programm.kern.pmi import BEZUG, MASS, TOLERANZ


@pytest.fixture(scope="module")
def teil():
    """Platte 100 x 60 x 20 mit Zentrierbohrung Ø20 (Mitte) und Stiftloch Ø6 (versetzt), beide durch."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepPrimAPI_MakeBox(100, 60, 20).Shape()
    for x, y, r in ((50, 30, 10), (85, 30, 3)):
        form = BRepAlgoAPI_Cut(form, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, 22)
                               .Shape()).Shape()
    flaechen, ex = [], TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        flaechen.append(topods.Face(ex.Current()))
        ex.Next()
    return SimpleNamespace(flaechen=flaechen)


def _finde(teil, art, **bed):
    for i, f in enumerate(teil.flaechen):
        g = fu._geometrie(f)
        if g and g["art"] == art and all(abs(float(bed[k](g)) ) < 1e-6 for k in bed):
            return i
    raise AssertionError(art)


def test_bezugssystem_und_tolerierung(teil):
    unten = _finde(teil, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1,
                   n=lambda g: g["richtung"][2] + 1)
    oben = _finde(teil, "ebene", z=lambda g: g["punkt"][2] - 20 if abs(g["richtung"][2]) > 0.9 else 1)
    links = _finde(teil, "ebene", x=lambda g: g["punkt"][0] if abs(g["richtung"][0]) > 0.9 else 1)
    bohrung = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 20)
    stift = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 6)
    rollen = {unten: "auflage", bohrung: "zentrierung", stift: "verdrehsicherung", oben: "dichtung", links: "frei"}
    s = fu.bezugssystem(teil, rollen)
    assert [(b.buchstabe, b.flaeche, b.element) for b in s.bezuege] == \
        [("A", unten, "ebene"), ("B", bohrung, "achse"), ("C", stift, "achse")] and s.offen == 0
    v = fu.tolerierung(teil, rollen, s)
    typen = {(p.pmi.art, p.pmi.typ, tuple(sorted(p.pmi.flaechen))) for p in v}
    assert (BEZUG, "Datum", (unten,)) in typen and (TOLERANZ, "Flatness", (unten,)) in typen
    passung = {p.pmi.passung for p in v if p.pmi.art == MASS}
    assert passung == {"H7"}  # beide Bohrungen: Bohrungsbasis H7
    stift_pos = next(p.pmi for p in v if p.pmi.typ == "Position" and stift in p.pmi.flaechen)
    assert stift_pos.material == "M" and [b.name for b in stift_pos.bezuege] == ["A", "B"]
    senkrecht = next(p.pmi for p in v if p.pmi.typ == "Perpendicularity" and bohrung in p.pmi.flaechen)
    assert [b.name for b in senkrecht.bezuege] == ["A"] and 0 < senkrecht.wert < 0.1
    assert not any(links in p.pmi.flaechen for p in v)  # Freiflaeche: Allgemeintoleranz
    nur_achse = fu.bezugssystem(teil, {bohrung: "zentrierung"})
    assert nur_achse.bezuege[0].freiheitsgrade == 4 and nur_achse.offen == 2 and nur_achse.hinweise


def test_element_aus_halbschalen_und_eigene_werte():
    """Bohrung aus zwei Halbschalen = ein Element (Inhalt beider, PMI an beiden Flaechen); von Hand gesetzte
    Toleranz und Passung ersetzen die Startwerte."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(60, 40, 20).Shape(), BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(30, 20, -1), gp_Dir(0, 0, 1)), 10, 22).Shape()).Shape()
    teilen = ShapeUpgrade_ShapeDivideClosed(form)
    teilen.SetNbSplitPoints(1)
    teilen.Perform()
    flaechen, ex = [], TopExp_Explorer(teilen.Result(), TopAbs_FACE)
    while ex.More():
        flaechen.append(topods.Face(ex.Current()))
        ex.Next()
    t = SimpleNamespace(flaechen=flaechen)
    halbe = [i for i, f in enumerate(flaechen) if (g := fu._geometrie(f)) and g["art"] == "zylinder"]
    unten = _finde(t, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1,
                   n=lambda g: g["richtung"][2] + 1)
    oben = _finde(t, "ebene", z=lambda g: g["punkt"][2] - 20 if abs(g["richtung"][2]) > 0.9 else 1)
    assert len(halbe) == 2 and fu.ein_element(t, halbe) and not fu.ein_element(t, [halbe[0], unten])
    assert not fu.ein_element(t, [unten, oben])  # parallel, aber nicht in einer Ebene
    gruppen = {halbe[0]: tuple(halbe)}
    g1, g2 = fu._geometrie(flaechen[halbe[0]]), fu._geo(t, halbe[0], gruppen)
    assert abs(g2["inhalt"] - 2 * g1["inhalt"]) < 1e-6 and g2["groesse"] == 20
    rollen = {unten: "auflage", halbe[0]: "zentrierung"}
    s = fu.bezugssystem(t, rollen, gruppen)
    assert [b.flaeche for b in s.bezuege] == [unten, halbe[0]]
    v = fu.tolerierung(t, rollen, s, gruppen)
    assert {p.flaechen == set(halbe) for p in (x.pmi for x in v) if halbe[0] in p.flaechen} == {True}
    start = fu.startwerte(t, halbe[0], "zentrierung", gruppen)
    assert start["passung"] == "H7" and start["lage"] > 0
    v = fu.tolerierung(t, rollen, s, gruppen, {halbe[0]: {"toleranz": 0.05, "passung": "H8"}})
    eigene = [x.pmi for x in v if halbe[0] in x.pmi.flaechen]
    assert {p.wert for p in eigene if p.art == TOLERANZ} == {0.05}
    assert [p.passung for p in eigene if p.art == MASS] == ["H8"]
    assert all(x.pmi.wert != 0.05 for x in v if unten in x.pmi.flaechen and x.pmi.art == TOLERANZ)
