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
