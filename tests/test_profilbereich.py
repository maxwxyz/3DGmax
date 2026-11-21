"""Profilrahmen mit zwei gezeichneten Endmarken und expliziten B-Rep-Kanten."""

import gzip
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import pmi_reparieren, pmi_zwischenbereich as bereich
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_hilfsmassschrift import _fuellgrafik, _mit_fuellsatz


def _fuellsatz(text, grafiken):
    g = grafiken[3422]
    gruppen = ((2,), (4, 5), (7,), (8,), (9,), (10,), (12, 13), (15, 16, 17),
               (19,), (23, 24), (25,), (26, 27, 28))
    netze = _fuellgrafik(g, gruppen, striche=(0, 1, 3, 6, 11, 14, 18, 20, 21, 22))
    text = _mit_fuellsatz(text, netze, 3422, 3455, "fcf")
    for nr, stil in ((3425, 3461), (3412, 3435)):
        note = grafiken[nr]
        netze = _fuellgrafik(note, ((2,), tuple(range(3, len(note.linien)))), striche=(0, 1))
        text = _mit_fuellsatz(text, netze, nr, stil, "note")
    return text


@pytest.mark.parametrize("gefuellt", [False, True])
def test_profilbereich_mit_originalgrafiken(gefuellt, fenster, tmp_path):
    quelle = pfad("nist_ctc_01_asme1_ap203.stp.gz")
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if gefuellt:
        text = _fuellsatz(text, lade_alles(quelle).grafik)
    eingang = tmp_path / "Profilbereich.stp"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    erg = fenster.erg
    from programm.kern.pmi_freier_hinweis import _ansichten
    from tests.test_step_ap242 import _occt
    for nr, name in ((3417, "A"), (3427, "B"), (3414, "C"), (3422, "")):
        original = next(p for p in erg.pmi if p.step_id == nr)
        fenster._pmi_befehl("semantisch", original)
        d = fenster._semantik_dialog
        if name:
            assert d.v.art == "bezug" and d.v.name == name
        else:
            assert bool(erg.grafik[nr].dreiecke) == gefuellt
            assert bool(erg.grafik[nr].linien) != gefuellt
            assert d.v.bereichsgrenzen == [["A", 2023], ["B", 2025]]
            assert d.v.grenzgrafiken == [3425, 3412]
            assert [b.text() for b in d.v.bezuege] == ["A", "B", "C"]
            ziel = d.flaechen
            d.flaechen = {erg.modell.step_zu_flaeche[553]}
            assert d.fehler()
            d.flaechen = ziel
        assert not d.fehler()
        d._pruefen()
    ausgang = fenster.speichere_step_pmi(str(tmp_path / "Profilbereich mit Originalgrafik.stp"), melden=False)
    neu = lade_alles(ausgang)
    typen, fehler, _ = _occt(ausgang)
    assert fehler == _occt(eingang)[1] and "StepRepr_BetweenShapeAspect" in typen.values()
    p, = [p for p in neu.pmi if p.semantisch and p.art == "toleranz"]
    assert (p.typ, p.wert, p.bereichsgrenzen) == ("ProfileOfSurface", 1.25, [["A", 2023], ["B", 2025]])
    assert [b.text() for b in p.bezuege] == ["A", "B", "C"]
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {553, 554}
    assert "A ↔ B" in p.wert_text() and p.step_id in neu.grafik[3422].pmi_ids
    for nr in (3422, 3425, 3412):
        vorher, nachher = erg.grafik[nr], neu.grafik[nr]
        assert bool(vorher.dreiecke) == gefuellt and bool(vorher.linien) != gefuellt
        for l, n in zip(vorher.linien, nachher.linien, strict=True):
            np.testing.assert_array_equal(l, n)
        for (p1, t1), (p2, t2) in zip(vorher.dreiecke, nachher.dreiecke, strict=True):
            np.testing.assert_array_equal(p1, p2)
            np.testing.assert_array_equal(t1, t2)
        ansichten = _ansichten(erg.modell.datei, nr)
        assert ansichten and _ansichten(neu.modell.datei, nr) == ansichten


def test_fehlende_oder_verschobene_grenzmarke(app):
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    original = next(p for p in erg.pmi if p.step_id == 3422)
    g = erg.grafik[3422]
    grafiken = dict(erg.grafik)
    note = grafiken.pop(3425)
    for ersatz in (None, replace(note, linien=[l+np.array([7., 8., 9.]) for l in note.linien])):
        if ersatz is not None:
            grafiken[3425] = ersatz
        v = pmi_reparieren.vorschlag(original, g, erg.modell)
        bereich.ergaenze(v, g, erg.modell, grafiken)
        assert not v.bereichsgrenzen and v.wert is None
    for fl, k in (([553, 554], [2023, 2024]), ([553, 554], [2023, 2023]), ([553, 554, 611], [2023, 2025])):
        assert not bereich.begrenzter_verband(erg.modell.datei, fl, k)

    ohne_pfeil = replace(g, linien=[l for i, l in enumerate(g.linien) if i != 25])
    assert bereich._bereichstext(ohne_pfeil) is None
    extra = replace(g, linien=[*g.linien, g.linien[25]+80*g.ebene[2]])
    assert bereich._bereichstext(extra) is None
