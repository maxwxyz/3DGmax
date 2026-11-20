"""Grafische MBD-Angaben als gepruefte Startwerte fuer die Semantik-Reparatur."""

from types import SimpleNamespace

import numpy as np
import pytest

from programm.kern import pmi_ableiten as lesen, pmi_reparieren as rep
from programm.kern.pmi import HINWEIS, Pmi
from programm.kern.praesentation import Grafik


@pytest.mark.parametrize("text,nenn,grenzen", [
    (["⌀", "35", "0", "−0,2"], 35., (0., -.2)),
    (["6X ⌀20 +0.1/0"], 20., (.1, 0.)),
    (["⌀ .438IN ± .005IN"], 11.1252, (.127, -.127)),
    ([".25 ± .010"], 6.35, (.254, -.254)),
    (["60.00° ± .50°"], 60., (.5, -.5)),
    (["Ø 35,20", "34,80"], 35., (35.2, 34.8)),
])
def test_graphische_masse(text, nenn, grenzen):
    faktor = 25.4 if text[0].startswith((".25", "60")) else 1.
    f = lesen.aus_text(text, faktor)
    assert f["nennwert"] == pytest.approx(nenn)
    assert (f["oben"], f["unten"]) == pytest.approx(grenzen)


def test_passung_und_kugelradius():
    f = lesen.aus_text(["2X Ø20 H7"])
    assert (f["nennwert"], f["passung"]) == (20., "H7")
    assert lesen.aus_text(["(SR.500IN)"]) == dict(art="mass", typ="Size_SphericalRadius",
                                                    nennwert=12.7, modifikatoren=["Hilfsmass"])


def test_gemeinsamer_bezug_und_projektion():
    f = lesen.aus_text(["⌖ | Ø 0,05 Ⓜ Ⓟ 6 | A | HⓂ-JⓁ"])
    assert (f["wert"], f["material"], f["zone"], f["zonen_wert"]) == (.05, "M", "Projected", 6.)
    a, hj = f["bezuege"]
    assert a.name == "A" and hj.stelle == 2 and hj.text() == "HⓂ-JⓁ"
    assert hj.modifikatoren == [] and hj.element_modifikatoren == {
        "H": ["MaximumMaterialRequirement"], "J": ["LeastMaterialRequirement"]}
    assert lesen.bezugsreferenz("(H-J)Ⓜ", 1).modifikatoren == ["MaximumMaterialRequirement"]


@pytest.mark.parametrize("angabe", ["ISO 2768-mK", "NOTE 12", "M6 x 1", "10 x 20", "1.2.3", "35 30", "Ø-5",
                                    "2X R5 TYP SEE NOTE 4"])
def test_ziffern_in_notizen_sind_keine_masse(angabe):
    assert lesen.aus_text([angabe]) is None


@pytest.mark.parametrize("angabe", ["⌖ ⌀.015 Ⓕ Z ⌀.020 A", "⏥ .005/0.25X0.25", "⌖ ⌀ .1 ⓂⓁ A",
                                    "⌖ ⌀ .1 Ⓜ MAX .1 A"])
def test_mehrdeutiger_rahmen_bleibt_ohne_zahlenwert(angabe):
    f = lesen.aus_text([angabe])
    assert f["art"] == "toleranz" and "wert" not in f


def test_rahmen_mit_kugeldurchmesser():
    p = Pmi(**lesen.aus_text(["⌖ S⌀ .1 Ⓜ MAX .25 A"]))
    assert p.maximum_toleranz == .25 and "S⌀0.1" in p._rahmen_text() and p.zonen_text() == "S⌀"


def test_qif_pmi_zoll_unabhaengig_von_der_geometrie(tmp_path):
    from programm.kern import qif, qif_grafik
    pfad = tmp_path / "texte.qif"
    pfad.write_text("""<QIFDocument xmlns="http://qifstandards.org/xsd/qif3"><FileUnits><PrimaryUnits>
    <LinearUnit><UnitName>mm</UnitName><UnitConversion><Factor>0.001</Factor></UnitConversion></LinearUnit>
    <PMILinearUnit><UnitName>inch</UnitName><UnitConversion><Factor>0.0254</Factor></UnitConversion></PMILinearUnit>
    </PrimaryUnits></FileUnits><PMIDisplaySet><PMIDisplay><Plane><Origin>0 0 0</Origin></Plane><Texts>
    <Text><XY>0 1</XY><Data>{DIAMETER}.438{PLUS_MINUS}.005</Data></Text></Texts>
    </PMIDisplay></PMIDisplaySet></QIFDocument>""")
    dok = qif.QifDokument(str(pfad))
    g, = qif_grafik.grafik(dok).values()
    assert dok.faktor == 1 and g.textfaktor == 25.4
    v = lesen.ableiten(g)
    assert v["nennwert"] == pytest.approx(11.1252) and v["oben"] == .127
    p = Pmi(HINWEIS, "Note", step_id=g.callout_id, semantisch=False)
    assert rep.reparierbar(p, {g.callout_id: g})


def test_eindeutige_geometrie_als_nennmass_und_cache():
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from programm.kern.laden import _alle_flaechen
    form = BRepPrimAPI_MakeCylinder(7., 20.).Shape()
    modell = SimpleNamespace(form=form, flaechen=_alle_flaechen(form))
    p = Pmi(HINWEIS, "Note", "Diameter.7", step_id=3, semantisch=False)
    g = Grafik(3, p.name, [np.array([[14., 0, 12], [7., 0, 12]])])
    v = rep.vorschlag(p, g, modell)
    assert v.typ == "Size_Diameter" and v.nennwert == 14. and v.nennwert_aus_geometrie and len(v.flaechen) == 1
    index = modell._reparatur_index
    assert rep.flaechen_vorschlag(g, modell) == v.flaechen and modell._reparatur_index is index
    # Eine Kante zwischen Deckel und Mantel ist fuer eine automatische Zuordnung mehrdeutig.
    g.linien = [np.array([[14., 0, 20], [7., 0, 20]])]
    assert not rep.flaechen_vorschlag(g, modell)


def test_pfeilspitze_auf_prc_netzflaeche():
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Face
    from programm.kern.laden import _poly
    f = TopoDS_Face()
    BRep_Builder().MakeFace(f, _poly([(0, 0, 0), (10, 0, 0), (0, 10, 0)], [(0, 1, 2)]))
    modell = SimpleNamespace(form=f, flaechen=[f])
    g = Grafik(-700, "Linear Dimension", [np.array([[2., 3., 4.], [2., 3., 0.]])])
    assert rep.flaechen_vorschlag(g, modell) == {0}
    assert rep.geometrie_nennmass("Size_Diameter", {0}, modell) is None


def test_typ_aus_cad_callout_bei_gezeichnetem_symbol():
    g = Grafik(17, "Flatness.2")
    g.platzhalter = [SimpleNamespace(text=".020")]
    assert lesen.ableiten(g)["typ"] == "Flatness" and lesen.ableiten(g)["wert"] == .020
    g.name = "Diameter.7"
    assert lesen.ableiten(g)["typ"] == "Size_Diameter"
    g.name = "fcf"
    assert lesen.ableiten(g) == {"art": "toleranz", "typ": ""}
    g.name = "radial dimension"
    assert lesen.ableiten(g) == {"art": "mass", "typ": "", "nennwert": .020}
    assert rep.vorschlag(Pmi(HINWEIS, "Note", g.name), g, SimpleNamespace(flaechen=[])).typ == ""
