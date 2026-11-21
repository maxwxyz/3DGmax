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


def _fuellgrafik(g, konturen=((4,), (5,), (8, 6, 7), (9,), (10,), (11,)), striche=range(4)):
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
    for i in striche:
        a, b = g.linien[i]
        quer = np.cross(g.ebene[3], b-a) * (.07 / np.linalg.norm(b-a))
        netze.append((np.array([a-quer, b-quer, b+quer, a+quer]), [[0, 1, 2], [0, 2, 3]]))
    for index, *loecher in konturen:
        fl = BRepBuilderAPI_MakeFace(draht(g.linien[index]), True)
        for loch in loecher:
            fl.Add(draht(g.linien[loch]))
        form = fl.Face()
        BRepMesh_IncrementalMesh(form, .01)
        netze.extend(_netz_und_umriss(form)[1])
    return netze


def _als_dreiecke(text, g, klammer=True, toleriert=False):
    netze = _fuellgrafik(g)
    if not klammer:
        netze = netze[:-2]
    if toleriert:
        from programm.kern.pmi_darstellung import text_glyphen
        o, x, y, _ = g.ebene
        _, zusatz = text_glyphen("±1", o+66*x-46*y, x, y, 13.5, "Helvetica")
        netze.extend(zusatz)
    return _mit_fuellsatz(text, netze, 3418, 3447, "")


def _mit_fuellsatz(text, netze, callout, stil, name):
    datei = p21.lese_text(text)
    if not datei.schema.startswith(step_ap242.AP242):
        text = step_ap242.aus_ap203(text, datei)
    punktliste = max(90001, max(datei.entities)+1)
    netz, gruppe, vorkommen = range(punktliste+1, punktliste+4)
    punkte, dreiecke = [], []
    for p, t in netze:
        dreiecke.extend(np.asarray(t) + len(punkte) + 1)
        punkte.extend(p)
    coords = ",".join("(" + ",".join(f"{x:.10f}" for x in v) + ")" for v in punkte)
    fans = ",".join("(%d,%d,%d)" % tuple(v) for v in dreiecke)
    neu = (f"#{punktliste}=COORDINATES_LIST('',{len(punkte)},({coords}));\n"
           f"#{netz}=COMPLEX_TRIANGULATED_SURFACE_SET('',#{punktliste},{len(punkte)},((0.,0.,1.)),(),(),({fans}));\n"
           f"#{gruppe}=TESSELLATED_GEOMETRIC_SET('',(#{netz}));\n"
           f"#{vorkommen}=TESSELLATED_ANNOTATION_OCCURRENCE('',(#{stil}),#{gruppe});\n")
    text, n = re.subn(rf"#{callout}\s*=[^;]+;", f"#{callout}=DRAUGHTING_CALLOUT('{name}',(#{vorkommen}));", text)
    assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + neu + text[pos:]


def _als_striche(text, g, toleriert):
    """Eigenstaendig gezeichnete Acht und Fuenf auf der Ebene der Masshilfslinien."""
    o, x, y, _ = g.ebene
    acht = [(2,4), (0,5.2), (0,7), (1.8,8), (4.2,8), (6,7), (6,5.2), (4,4),
            (2,4), (0,3), (0,1), (2,0), (4,0), (6,1), (6,3), (4,4)]
    fuenf = [(15,8), (10,8), (9,4), (12,4), (14,3), (15,2), (14,1), (13,0), (10,0), (9,1)]
    zuege = [acht, fuenf]
    if toleriert:
        zuege.extend(([(19,5), (25,5)], [(22,2.5), (22,7.5)], [(19,0), (25,0)],
                      [(28,6), (31,8), (31,0)]))
    elemente = []
    for i, zug in enumerate(zuege):
        ids = []
        for j, (u, v) in enumerate(zug):
            nummer = 90010 + 20*i + j
            punkt = o + (49+u)*x + (-46+v)*y
            coords = ",".join(f"{a:.10f}" for a in punkt)
            elemente.append(f"#{nummer}=CARTESIAN_POINT('',({coords}));")
            ids.append(f"#{nummer}")
        elemente.append(f"#{90000+i}=POLYLINE('',({','.join(ids)}));")
    refs = ",".join(f"#{90000+i}" for i in range(len(zuege)))
    text, n = re.subn(r"#3916,\s*#3917,\s*#3918,\s*#3919,\s*#3920,\s*#3921\)", refs + ")", text)
    assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(elemente) + "\n" + text[pos:]


@pytest.mark.parametrize("schrift,klammer", [("kontur", True), ("fuellung", True),
                                            ("kontur", False), ("fuellung", False), ("strich", False),
                                            ("toleriert", False), ("strich_toleriert", False)])
def test_hilfsmass_aus_grafik_mit_beiden_zielflaechen(schrift, klammer, fenster, tmp_path):
    quelle = pfad("nist_ctc_01_asme1_ap203.stp.gz")
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    toleriert = schrift.endswith("toleriert")
    fuellung = schrift in ("fuellung", "toleriert")
    if schrift.startswith("strich"):
        text = _als_striche(text, lade_alles(quelle).grafik[3418], toleriert)
    elif fuellung:
        text = _als_dreiecke(text, lade_alles(quelle).grafik[3418], klammer, toleriert)
    elif not klammer:
        text, n = re.subn(r",\s*#3920,\s*#3921\)", ")", text)
        assert n == 1
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
    solltext = "(85)" if klammer else ("85±1" if toleriert else "85")
    assert (d.v.ocr_text, d.v.typ, d.v.nennwert, d.v.modifikatoren) == (
        solltext, "Location_LinearDistance", 85., ["Hilfsmass"] if klammer else [])
    ziel = {vorher.modell.step_zu_flaeche[i] for i in (568, 572)}
    assert d.flaechen == ziel and not d.fehler()
    d._pruefen()
    ausgang = fenster.speichere_step_pmi(str(tmp_path / "Hilfsmass mit Originalgrafik.stp"), melden=False)
    neu = lade_alles(ausgang)
    sem, = [p for p in neu.pmi if p.semantisch]
    assert sem.modifikatoren == (["Hilfsmass"] if klammer else [])
    nativ, = [p for p in lies_pmi_xcaf(neu.modell) if p.typ == "Location_LinearDistance"]
    for p in (sem, nativ):
        assert p.typ == "Location_LinearDistance" and p.nennwert == pytest.approx(85.)
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {568, 572}
        assert (p.unten, p.oben) == ((-1., 1.) if toleriert else (None, None))
    g2 = neu.grafik[3418]
    assert sem.step_id in g2.pmi_ids and ansichten == {a.step_id for a in neu.ansichten if sem.step_id in a.pmi_ids}
    assert ansichten and "AP242" in neu.modell.datei.schema
    for l, n in zip(g.linien, g2.linien, strict=True):
        np.testing.assert_array_equal(l, n)
    for (p, t), (q, u) in zip(g.dreiecke, g2.dreiecke, strict=True):
        np.testing.assert_array_equal(p, q)
        np.testing.assert_array_equal(t, u)


def test_nennmass_braucht_masslinien_und_passende_flaechen(app):
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    original = erg.grafik[3418]
    g = replace(original, name="", ebene=None, linien=original.linien[:10])
    ziel = {erg.modell.step_zu_flaeche[i] for i in (568, 572)}
    lies = pmi_reparieren.schriftvorschlag
    assert lies(g, None, erg.modell, set()) == ("", {})
    assert lies(replace(g, textfaktor=25.4), None, erg.modell, ziel) == ("85", {})
    assert lies(replace(g, linien=g.linien[6:]), None, erg.modell, ziel) == ("", {})
    assert lies(replace(g, linien=g.linien[1:]), None, erg.modell, ziel) == ("", {})


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


def test_66_zwischen_masslinien_bleibt_ohne_richtung_mehrdeutig(app):
    from programm.kern.pmi_darstellung import text_glyphen
    g = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz")).grafik[3418]
    o, x, y, _ = g.ebene
    _, ziffern = text_glyphen("66", o+50*x-46*y, x, y, 13.5, "Helvetica")
    g = replace(g, linien=[], dreiecke=_fuellgrafik(g)[:6]+ziffern)
    assert pmi_strichschrift.lies_schrift(g, linearmass=True) == "66"
    assert not pmi_strichschrift.lies_schrift(replace(g, ebene=None), linearmass=True)
