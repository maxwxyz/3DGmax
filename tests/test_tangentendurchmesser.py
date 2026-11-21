"""Geklammertes Durchmessermass an zwei Tangenten der CTC-03-Bohrung."""
from dataclasses import replace
import gzip
from pathlib import Path

import numpy as np
import pytest
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface

from programm.kern import pmi_strichschrift as schrift
from programm.kern.pmi_durchmesserschrift import tangentendurchmesser
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.kern.pmi_lesen import lies_pmi_xcaf
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_kreisbezugsstelle import _ersetze_schrift
from tests.test_radialmass_knickpfeil import QUELLE
from tests.test_step_ap242 import _occt


def _striche(g):
    y = np.linspace(0, 1, 25)
    bogen = np.column_stack((1-np.sin(np.pi*y), y))
    zeichen = (bogen, [(0,.75),(.76,1),(.76,0)], [(0,0),(1,0),(1,1),(0,1),(0,0)],
               [(1,1),(.16,1),(0,.5),(.5,.5),(.84,.37),(1,.25),(.84,.12),(.66,0),(.16,0),(0,.12)],
               (1-bogen)*[1,-1]+[0,1])
    linien = []
    o,x,y,_ = g.ebene
    for zug, (p, _) in zip(zeichen, schrift._pfade(g, g.ebene)[6:], strict=True):
        uv = p.min(0) + np.asarray(zug)*np.ptp(p, axis=0)
        linien.append(o+uv[:, :1]*x+uv[:, 1:]*y)
    return linien


def test_tangenten_brauchen_gleichen_rand_pfeile_und_passende_schrift():
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[3625]
    wand = {e.modell.step_zu_flaeche[545]}
    fuellung = replace(g, linien=[], dreiecke=[(p*g.textfaktor,t) for p,t in _gefuellt(g)])
    for q in (fuellung, replace(g,linien=g.linien[:6]+_striche(g)), replace(g,linien=g.linien[::-1])):
        assert tangentendurchmesser(replace(q,ebene=None,name=""), e.modell, wand)[0] == "(1.5)"
    for linien in (g.linien[1:], g.linien[:3]+g.linien[4:], g.linien[:5]+g.linien[6:], g.linien[:-1],
                   [g.linien[0]+g.ebene[1], *g.linien[1:]],
                   [p + g.ebene[3] for p in g.linien], g.linien+[g.linien[7]+12*g.ebene[2]]):
        assert tangentendurchmesser(replace(g,linien=linien),e.modell,wand) is None
    assert tangentendurchmesser(replace(g,linien=g.linien[:6]+[p-150*g.ebene[1] for p in g.linien[6:]]),
                                e.modell, wand) is None
    assert tangentendurchmesser(replace(g,textfaktor=1.), e.modell, wand) is None
    assert tangentendurchmesser(g, e.modell, {e.modell.step_zu_flaeche[481]}) is None


def test_zusaetzliche_kanten_muessen_zum_beruehrten_kreis_gehoeren(tmp_path):
    with gzip.open(pfad(QUELLE), "rt", encoding="ascii") as f:
        quelle = f.read()
    ziel = tmp_path/"Andere Kante.step"
    # Derselbe Zylinder, aber eine der drei Kantenverknuepfungen zeigt zum anderen Ende.
    original = "GEOMETRIC_ITEM_SPECIFIC_USAGE('','PMI',#160,#154,#2053)"
    assert quelle.count(original) == 1
    ziel.write_text(quelle.replace(original, original.replace("#2053", "#2079")), encoding="ascii")
    e = lade_alles(str(ziel))
    assert tangentendurchmesser(e.grafik[3625], e.modell, {e.modell.step_zu_flaeche[545]}) is None


@pytest.mark.parametrize("schriftart", ["kontur","strich","fuellung"])
def test_durchmesser_und_hilfsmass_am_selben_zylinder(fenster, tmp_path, schriftart):
    quelle = pfad(QUELLE)
    e = lade_alles(quelle)
    g = e.grafik[3625]
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if schriftart == "strich":
        text = _ersetze_schrift(text, e, g, 6, _striche(g))
    if schriftart == "fuellung":
        stil = e.modell.datei.get(3625).args()[1][0].id
        text = _mit_fuellsatz(text, _gefuellt(g), 3625, stil, g.name)
    eingang = tmp_path/"Bohrung.step"
    eingang.write_text(text,encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    alt = fenster.erg
    original = alt.grafik[3625]
    for cid in (3625,3642):
        fenster._pmi_befehl("semantisch", next(p for p in alt.pmi if p.step_id == cid))
        d = fenster._semantik_dialog
        assert d.v.typ == "Size_Diameter" and not d.fehler()
        if cid == 3625:
            assert d.v.ocr_text == "(1.5)" and d.v.modifikatoren == ["Hilfsmass"]
            d.flaechen.add(alt.modell.step_zu_flaeche[481])
            assert d.fehler()
            d.flaechen.remove(alt.modell.step_zu_flaeche[481])
        d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path/"Bohrung.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    n = neu.grafik[3625]
    for cid in (3625,3642):
        sem, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[cid].pmi_ids]
        assert sem.typ == "Size_Diameter" and sem.nennwert == pytest.approx(38.1)
        assert {neu.modell.flaeche_zu_step[i] for i in sem.flaechen} == {545}
        if cid == 3625:
            assert sem.modifikatoren == ["Hilfsmass"] and (sem.oben, sem.unten) == (None,None)
        else:
            assert not sem.modifikatoren and (sem.oben, sem.unten) == pytest.approx((.127,-.127))
    nativ = [q for q in lies_pmi_xcaf(neu.modell) if q.typ == "Size_Diameter"
             and q.nennwert == pytest.approx(38.1)]
    assert len(nativ) == 2
    assert _ansichten(alt.modell.datei,3625) == _ansichten(neu.modell.datei,3625) != set()
    for a,b in zip(original.linien, n.linien, strict=True):
        np.testing.assert_array_equal(a,b)
    for (a,t),(b,u) in zip(original.dreiecke, n.dreiecke, strict=True):
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t,u)
    assert _occt(ziel)[1:] == _occt(eingang)[1:]
    refpfad = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/nist_ctc_03_asme1_ap242-e2.stp"
    if refpfad.is_file():
        ref = lade_alles(str(refpfad))
        p = next(p for p in ref.pmi if p.step_id == 269)
        assert p.typ == "Size_Diameter" and len(p.flaechen) == 2
        for i in p.flaechen:
            assert BRepAdaptor_Surface(ref.modell.flaechen[i]).Cylinder().Radius() == pytest.approx(19.05)
