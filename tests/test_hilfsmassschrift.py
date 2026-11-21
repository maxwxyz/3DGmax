"""Geklammertes NIST-Hilfsmass ohne Zeichenebene aus Kurven und gefuellten Glyphen."""

import gzip
import re
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import p21, pmi_reparieren, pmi_strichschrift, step_ap242
from programm.kern.pmi_lesen import lies_pmi_xcaf
from programm.ui.lader import lade_alles
from tests.conftest import pfad


def _fuellgrafik(g):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.gp import gp_Pnt
    from programm.kern.pmi_darstellung import _netz_und_umriss

    def draht(linie):
        polygon = BRepBuilderAPI_MakePolygon()
        for punkt in linie[:-1]:
            polygon.Add(gp_Pnt(*punkt))
        polygon.Close()
        return polygon.Wire()

    netze = []
    for linie in g.linien[:4]:
        a, b = linie
        quer = np.cross(g.ebene[3], b-a) * (.07 / np.linalg.norm(b-a))
        netze.append((np.array([a-quer, b-quer, b+quer, a+quer]), [[0, 1, 2], [0, 2, 3]]))
    # Zwei Dreieckspfeile und vier Buchstaben. Die Acht braucht beide Innenkonturen.
    for index in (4, 5, 8, 9, 10, 11):
        fl = BRepBuilderAPI_MakeFace(draht(g.linien[index]), True)
        if index == 8:
            for loch in g.linien[6:8]:
                fl.Add(draht(loch))
        form = fl.Face()
        BRepMesh_IncrementalMesh(form, .01)
        netze.extend(_netz_und_umriss(form)[1])
    return netze


def _als_dreiecke(text, g):
    text = step_ap242.aus_ap203(text, p21.lese_text(text))
    punkte, dreiecke = [], []
    for p, t in _fuellgrafik(g):
        dreiecke.extend(np.asarray(t) + len(punkte) + 1)
        punkte.extend(p)
    coords = ",".join("(" + ",".join(f"{x:.10f}" for x in v) + ")" for v in punkte)
    fans = ",".join("(%d,%d,%d)" % tuple(v) for v in dreiecke)
    neu = (f"#90001=COORDINATES_LIST('',{len(punkte)},({coords}));\n"
           f"#90002=COMPLEX_TRIANGULATED_SURFACE_SET('',#90001,{len(punkte)},((0.,0.,1.)),(),(),({fans}));\n"
           "#90003=TESSELLATED_GEOMETRIC_SET('',(#90002));\n"
           "#90004=TESSELLATED_ANNOTATION_OCCURRENCE('',(#3447),#90003);\n")
    text, n = re.subn(r"#3418\s*=[^;]+;", "#3418=DRAUGHTING_CALLOUT('',(#90004));", text)
    assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + neu + text[pos:]


@pytest.mark.parametrize("fuellung", [False, True], ids=["ap203_kurven", "ap242_fuellung"])
def test_hilfsmass_aus_grafik_mit_beiden_zielflaechen(fuellung, fenster, tmp_path):
    quelle = pfad("nist_ctc_01_asme1_ap203.stp.gz")
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if fuellung:
        text = _als_dreiecke(text, lade_alles(quelle).grafik[3418])
    text, n = re.subn(r"#3231\s*=\s*ANNOTATION_PLANE\([^;]+;", "", text)
    assert n == 1
    eingang = tmp_path / "Hilfsmass ohne Ebene.stp"
    eingang.write_text(text.replace("#3231,", "#3418,"), encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    vorher = fenster.erg
    g = vorher.grafik[3418]
    assert g.ebene is None and not g.platzhalter and g.textfaktor == 1.
    assert bool(g.linien) != fuellung and bool(g.dreiecke) == fuellung
    if fuellung:
        assert not g.name
    original = next(p for p in vorher.pmi if p.step_id == 3418)
    assert not original.semantisch and original.nennwert is None
    ansichten = {a.step_id for a in vorher.ansichten if 3418 in a.pmi_ids}
    fenster._pmi_befehl("semantisch", original)
    d = fenster._semantik_dialog
    assert not d.v.validierungstexte and not d.v.nennwert_aus_geometrie
    assert (d.v.ocr_text, d.v.typ, d.v.nennwert, d.v.modifikatoren) == (
        "(85)", "Location_LinearDistance", 85., ["Hilfsmass"])
    ziel = {vorher.modell.step_zu_flaeche[i] for i in (568, 572)}
    assert d.flaechen == ziel and not d.fehler()
    d._pruefen()
    ausgang = fenster.speichere_step_pmi(str(tmp_path / "Hilfsmass mit Originalgrafik.stp"), melden=False)
    neu = lade_alles(ausgang)
    sem, = [p for p in neu.pmi if p.semantisch]
    assert sem.modifikatoren == ["Hilfsmass"]
    nativ, = [p for p in lies_pmi_xcaf(neu.modell) if p.typ == "Location_LinearDistance"]
    for p in (sem, nativ):
        assert p.typ == "Location_LinearDistance" and p.nennwert == pytest.approx(85.)
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {568, 572}
        assert p.unten is None and p.oben is None
    g2 = neu.grafik[3418]
    assert sem.step_id in g2.pmi_ids and ansichten == {a.step_id for a in neu.ansichten if sem.step_id in a.pmi_ids}
    assert ansichten and "AP242" in neu.modell.datei.schema
    for l, n in zip(g.linien, g2.linien, strict=True):
        np.testing.assert_array_equal(l, n)
    for (p, t), (q, u) in zip(g.dreiecke, g2.dreiecke, strict=True):
        np.testing.assert_array_equal(p, q)
        np.testing.assert_array_equal(t, u)


def test_klammerzahl_ohne_massbeleg_und_mit_zolleinheit(app):
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    g = replace(erg.grafik[3418], ebene=None, textfaktor=25.4)
    assert pmi_reparieren.schriftvorschlag(g, None) == ("(85)", {})
    ziel = {erg.modell.step_zu_flaeche[i] for i in (568, 572)}
    assert pmi_reparieren.schriftvorschlag(g, None, erg.modell, ziel) == ("(85)", {})
    _, felder = pmi_reparieren.schriftvorschlag(g, ("mass", "Location_LinearDistance"))
    assert felder["nennwert"] == pytest.approx(2159.) and felder["modifikatoren"] == ["Hilfsmass"]
    assert not pmi_strichschrift.lies_schrift(replace(g, textfaktor=None))
    assert not pmi_strichschrift.lies_schrift(replace(g, linien=g.linien[:-1]))


def test_drehbare_klammerzahl_braucht_eine_schreibrichtung(app):
    from programm.kern.pmi_darstellung import text_glyphen
    from programm.kern.praesentation import Grafik
    o = np.zeros(3)
    x, y, z = np.eye(3)
    _, dreiecke = text_glyphen("(66)", o, x, y, 10., "Helvetica")
    g = Grafik(0, ebene=(o, x, y, z), dreiecke=dreiecke)
    assert pmi_strichschrift.lies_schrift(g) == "(66)"
    assert not pmi_strichschrift.lies_schrift(replace(g, ebene=None))
