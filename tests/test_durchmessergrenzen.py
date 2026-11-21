"""Gezeichnete Durchmessergrenzen unter einem allgemeinen STEP-Massnamen."""

import gzip
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from programm.kern import pmi_reparieren as rep
from programm.kern.pmi import MASS
from programm.kern.pmi_lesen import lies_pmi_xcaf
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_hilfsmassschrift import _fuellgrafik, _mit_fuellsatz


@pytest.mark.parametrize("fuellung,wahl", [(False,"grenzen"), (True,"grenzen"), (True,"grafik"), (True,"datei")])
def test_grenzwahl_am_zylinder_bis_step(fuellung, wahl, fenster, tmp_path):
    quelle = pfad("nist_ctc_01_asme1_ap203.stp.gz")
    if fuellung:
        with gzip.open(quelle, "rt", encoding="ascii") as f:
            text = f.read()
        g = lade_alles(quelle).grafik[3413]
        # Innenkonturen des Durchmesserzeichens, der Vier und der Acht aussparen.
        kanten = [(4,), (5,), (6, 7, 8), (9,), (10, 11), (12,), (15, 13, 14),
                  (16,), (17,), (18,), (19,), (20,)]
        text = _mit_fuellsatz(text, _fuellgrafik(g, kanten), 3413, 3437, g.name)
        text, n = re.subn(r"#3226\s*=\s*ANNOTATION_PLANE\([^;]+;", "", text)
        assert n == 1
        if wahl != "grenzen":
            eigenschaft = r"""#90100=CHARACTERIZED_ITEM_WITHIN_REPRESENTATION('','',#3413,#3222);
#90101=PROPERTY_DEFINITION('pmi validation property','',#90100);
#90102=PROPERTY_DEFINITION_REPRESENTATION(#90101,#90103);
#90103=REPRESENTATION('',(#90104),#17160);
#90104=DESCRIPTIVE_REPRESENTATION_ITEM('equivalent unicode string','DIM\\w\X2\2300\X0\34.7-35.3');
"""
            pos = text.rindex("ENDSEC;")
            text = text[:pos] + eigenschaft + text[pos:]
        quelle = str(tmp_path / "Grenzen aus Dreiecken.step")
        Path(quelle).write_text(text.replace("#3226,", "#3413,"), encoding="ascii")
    fenster.lade(quelle, warten=True)
    vorher = fenster.erg
    g = vorher.grafik[3413]
    original = next(p for p in vorher.pmi if p.step_id == 3413)
    assert not original.semantisch and g.name == "linear dimension" and not g.platzhalter
    assert bool(g.linien) != fuellung and bool(g.dreiecke) == fuellung
    assert (g.ebene is None) == fuellung
    ansichten = {a.step_id for a in vorher.ansichten if 3413 in a.pmi_ids}
    flaeche = vorher.modell.step_zu_flaeche[611]
    assert rep.geometrie_nennmass("Size_Diameter", {flaeche}, vorher.modell) == pytest.approx(35.)
    fenster._pmi_befehl("semantisch", original)
    d = fenster._semantik_dialog
    if wahl == "grenzen":
        assert d.v.ocr_text == "⌀34.8-35.2" and not d.v.validierungstexte
        assert set(d.massknoepfe) == {"grenzen"}
    else:
        assert [(key, wort) for key, wort, _ in d.v.masswahl] == [
            ("grafik", "⌀34.8-35.2"), ("datei", "⌀34.7-35.3")]
        assert set(d.massknoepfe) == {"grafik", "datei"}
    assert d.flaechen == {flaeche} and d.v.typ == "Size_Diameter"
    assert not d.v.nennwert_aus_geometrie and not d.felder["nennwert"].text() and d.fehler()
    d.massknoepfe[wahl].click()
    assert not d.fehler()
    d._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Durchmesser mit Grenzen.step"), melden=False)
    neu = lade_alles(ziel)
    sem, = [p for p in neu.pmi if p.semantisch]
    nativ, = [p for p in lies_pmi_xcaf(neu.modell) if p.typ == "Size_Diameter"]
    for p in (sem, nativ):
        assert p.typ == "Size_Diameter" and p.grenzmass and p.nennwert == pytest.approx(35.)
        assert p.grenzen() == pytest.approx((35.3, 34.7) if wahl == "datei" else (35.2, 34.8))
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {611}
    g2 = neu.grafik[3413]
    assert sem.step_id in g2.pmi_ids and "AP242" in neu.modell.datei.schema
    assert ansichten and {a.step_id for a in neu.ansichten if sem.step_id in a.pmi_ids} == ansichten
    for a, b in zip(g.linien, g2.linien, strict=True):
        np.testing.assert_array_equal(a, b)
    for (a, t), (b, u) in zip(g.dreiecke, g2.dreiecke, strict=True):
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(t, u)


def test_konkreter_typ_bleibt_bei_unvereinbaren_grenzen_offen(app):
    e = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    g = e.grafik[3413]
    original = next(p for p in e.pmi if p.step_id == 3413)
    for p in (replace(original, name="distance"), replace(original, name="Radius.1"),
              replace(original, art=MASS, typ="Location_LinearDistance")):
        v = rep.vorschlag(p, g, e.modell)
        assert not v.masswahl and not v.grenzmass and v.typ != "Size_Diameter"
