"""Toleranzzonen: Linienprofil je Schnitt, ACS, CZ/SZ, Toleranzen an Kanten, Gewinde (Konstruktionsgeometrie) und
fuer das ganze Teil."""

from types import SimpleNamespace

import pytest

from programm.kern import toleranzzone as tz
from programm.kern.pmi import TOLERANZ, BezugsRef, Pmi
from tests.conftest import pfad


def _flaechen(form):
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    out, ex = [], TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        out.append(topods.Face(ex.Current()))
        ex.Next()
    return out


@pytest.fixture(scope="module")
def platte():
    """Platte 100 x 60 x 20 mit Bohrung Ø20 (durch) - Flaechen und Form als Modell-Ersatz."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(100, 60, 20).Shape(),
                           BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(50, 30, -1), gp_Dir(0, 0, 1)), 10, 22).Shape()).Shape()
    return SimpleNamespace(form=form, flaechen=_flaechen(form))


def _index(modell, art, **bed):
    from programm.kern.funktion import _geometrie
    for i, f in enumerate(modell.flaechen):
        g = _geometrie(f)
        if g and g["art"] == art and all(abs(float(v(g))) < 1e-6 for v in bed.values()):
            return i
    raise AssertionError(art)


def test_linienprofil_je_schnitt_und_laengs(platte):
    bohrung = _index(platte, "zylinder", d=lambda g: g["groesse"] - 20)
    p = Pmi(TOLERANZ, "ProfileOfLine", wert=0.1, flaechen={bohrung}, bezuege=[BezugsRef("A")])
    z = tz.zone(p, platte)
    assert z.art == "linien" and len(z.formen) >= 3 and "drei Schnitten" in z.hinweise[0]
    q = Pmi(TOLERANZ, "Straightness", wert=0.05, flaechen={bohrung}, modifikatoren=["Line_Element"])
    zl = tz.zone(q, platte)
    assert zl.art == "linien" and "Längsschnitten" in zl.hinweise[0]


def test_acs_und_gemeinsame_zone(platte):
    bohrung = _index(platte, "zylinder", d=lambda g: g["groesse"] - 20)
    p = Pmi(TOLERANZ, "Position", wert=0.2, flaechen={bohrung}, modifikatoren=["Diameter", "Any_Cross_Section"],
            bezuege=[BezugsRef("A")])
    z = tz.zone(p, platte)
    assert z.art == "querschnitt" and len(z.formen) == 3 and "ACS" in z.hinweise[0]
    # zwei Flaechen in einer Ebene: Deckflaeche geteilt ist hier nicht vorhanden - Ober- und Unterseite sind nicht
    # koplanar, daher keine CZ-Zone, sondern getrennte Flaechenzonen
    oben = _index(platte, "ebene", z=lambda g: g["punkt"][2] - 20 if abs(g["richtung"][2]) > 0.9 else 1)
    unten = _index(platte, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1)
    getrennt = tz.zone(Pmi(TOLERANZ, "Flatness", wert=0.05, flaechen={oben, unten}, modifikatoren=["Common_Zone"]),
                       platte)
    assert getrennt.art == "flaechen" and len(getrennt.formen) == 4
    assert any("theoretisch genau" in h for h in getrennt.hinweise)  # CZ an versetzten Flaechen: gemeinsam ausgerichtet


def test_gemeinsame_zone_koplanar():
    """CZ: zwei getrennte Flaechen in einer Ebene bekommen ein gemeinsames Ebenenpaar."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt
    form = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 20, 20, 10).Shape(),
                            BRepPrimAPI_MakeBox(gp_Pnt(40, 0, 0), 20, 20, 10).Shape()).Shape()
    m = SimpleNamespace(form=form, flaechen=_flaechen(form))
    from programm.kern.funktion import _geometrie
    oben = {i for i, f in enumerate(m.flaechen) if (g := _geometrie(f)) and g["art"] == "ebene"
            and g["richtung"][2] > 0.9 and abs(g["punkt"][2] - 10) < 1e-6}
    assert len(oben) == 2
    z = tz.zone(Pmi(TOLERANZ, "Flatness", wert=0.05, flaechen=oben, modifikatoren=["Common_Zone"]), m)
    assert len(z.formen) == 2 and any("CZ" in h for h in z.hinweise)
    sz = tz.zone(Pmi(TOLERANZ, "Flatness", wert=0.05, flaechen=oben, modifikatoren=["Separate_Requirement"]), m)
    assert len(sz.formen) == 4 and any("SZ" in h for h in sz.hinweise)


def test_kante_und_punkt():
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex
    from OCC.Core.gp import gp_Pnt
    p = Pmi(TOLERANZ, "Straightness", wert=0.1)
    p.teilformen = [BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(50, 0, 0)).Edge(),
                    BRepBuilderAPI_MakeVertex(gp_Pnt(0, 10, 0)).Vertex()]
    z = tz.zone(p, SimpleNamespace(form=None, flaechen=[]))
    assert z.art == "teilform" and len(z.formen) == 2


def test_gewinde_und_ganzes_teil_nist():
    """FTC-10: Position Ø0,8 Ⓟ3,2 an Gewinden (Konstruktionsgeometrie) und Flaechenprofil fuer das ganze Teil."""
    from programm.kern.laden import lade_modell
    from programm.kern.pmi_lesen import lies_pmi
    m = lade_modell(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    pmi = lies_pmi(m)
    gewinde = [p for p in pmi if p.typ == "Position" and not p.flaechen]
    assert len(gewinde) == 3
    for p in gewinde:
        z = tz.zone(p, m, alle_pmi=pmi)
        assert z.rollen == ["zone", "bonus", "zone", "bonus"]  # je Gewinde Achszone und projizierte Zone
    ganz = next(p for p in pmi if getattr(p, "ganzes_teil", False))
    z = tz.zone(ganz, m, alle_pmi=pmi)
    assert len(z.formen) > 100 and any("ganze Teil" in h for h in z.hinweise)
