"""Minimum-Material-Bedingungen im Toleranzwert und in einzelnen Bezugsfeldern."""

import gzip
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import pmi_strichschrift as schrift
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.kern.pmi_reparieren import vorschlag
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_step_ap242 import _occt


# Semantische Gegenprobe CTC-02 AP242 #59, #60, #67, #185, #184 und #68.
RAHMEN = {
    8678: ("ProfileOfSurface", .8, "", "G|H|JⓁ", {1156}),
    8699: ("ProfileOfSurface", .8, "", "G|HⓁ|J", {1180}),
    8711: ("ProfileOfSurface", .8, "", "G|HⓁ|JⓁ", {1155}),
    8686: ("Position", .15, "L", "G|H", {1116}),
    8687: ("Position", 1., "L", "A|B|C", {1173, 1135}),
    8717: ("Perpendicularity", .1, "L", "G", {1121}),
}


def _pruefe(p, nr, modell):
    typ, wert, material, bezuege, flaechen = RAHMEN[nr]
    assert (p.typ, p.material, p.bezug_text()) == (typ, material, bezuege)
    assert p.wert == pytest.approx(wert)
    assert ("Diameter" in p.modifikatoren) == bool(material)
    assert {modell.flaeche_zu_step[i] for i in p.flaechen} == flaechen


@pytest.mark.parametrize("fuellung", [False, True])
def test_minimummaterial_bis_step(fenster, tmp_path, fuellung):
    quelle = pfad("nist_ctc_02_asme1_ap203.stp.gz")
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if fuellung:
        e = lade_alles(quelle)
        for nr in RAHMEN:
            stil = e.modell.datei.get(nr).args("ANNOTATION_OCCURRENCE")[1][0].id
            text = _mit_fuellsatz(text, _gefuellt(e.grafik[nr]), nr, stil, "fcf")
    eingang = tmp_path / "CTC02.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    e = fenster.erg
    for nr in (8697, 8704, 8683, *RAHMEN):
        p = next(p for p in e.pmi if p.step_id == nr)
        assert not p.semantisch
        fenster._pmi_befehl("semantisch", p)
        dialog = fenster._semantik_dialog
        assert not dialog.fehler()
        if nr in RAHMEN:
            _pruefe(dialog.v, nr, e.modell)
            g = e.grafik[nr]
            assert schrift.lies_schrift(replace(g, ebene=None)) == dialog.v.ocr_text
        dialog._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Pruefung.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Geprueft.step"), melden=False)
    assert ziel
    # A/B/C liegen hier nur als grafische Angaben vor. Ihr Rahmen muss offen bleiben.
    uebersprungen, = fenster._step_bericht.uebersprungen
    assert "A, B, C" in uebersprungen[-1]
    neu = lade_alles(ziel)
    assert _occt(eingang)[1:] == _occt(ziel)[1:]
    for nr in RAHMEN:
        a, b = e.grafik[nr], neu.grafik[nr]
        ergebnis = [p for p in neu.pmi if p.semantisch and p.step_id in b.pmi_ids]
        if nr == 8687:
            assert not ergebnis
        else:
            p, = ergebnis
            _pruefe(p, nr, neu.modell)
        ansichten = _ansichten(e.modell.datei, nr)
        assert ansichten and _ansichten(neu.modell.datei, nr) == ansichten
        assert bool(a.linien) != fuellung and bool(a.dreiecke) == fuellung
        for v, w in zip(a.linien, b.linien, strict=True):
            np.testing.assert_array_equal(v, w)
        for (v, t), (w, u) in zip(a.dreiecke, b.dreiecke, strict=True):
            np.testing.assert_array_equal(v, w)
            np.testing.assert_array_equal(t, u)


def _kreis_und_l():
    winkel = np.linspace(0, 2*np.pi, 97)
    kreis = .5 + .49*np.column_stack((np.cos(winkel), np.sin(winkel)))
    return kreis, np.array([(.36, .75), (.36, .25), (.66, .25)])


def test_mittelstriche_in_wert_und_bezugsfeldern():
    e = lade_alles(pfad("nist_ctc_02_asme1_ap203.stp.gz"))
    for nr, felder in {8678: [4], 8699: [3], 8711: [3, 4], 8686: [1], 8687: [1], 8717: [1]}.items():
        g = e.grafik[nr]
        o, x, y, _ = g.ebene
        pfade = schrift._pfade(g, g.ebene)
        zellen = schrift._zellen(pfade)
        linien = list(g.linien)
        for i in felder:
            links, unten, rechts, oben = zellen[i]
            innen = [(j, p) for j, (p, _) in enumerate(pfade)
                     if np.all(p.min(axis=0) > [links+.001, unten+.001])
                     and np.all(p.max(axis=0) < [rechts-.001, oben-.001])]
            # Der Aussenring ist die am weitesten rechts liegende Kontur dieses Feldes.
            _, ring = max(innen, key=lambda jp: jp[1][:, 0].max())
            start, ende = ring.min(axis=0), ring.max(axis=0)
            for j, p in innen:
                if np.all(p.min(axis=0) >= start) and np.all(p.max(axis=0) <= ende):
                    linien[j] = None
            for zug in _kreis_und_l():
                uv = start + zug*(ende-start)
                linien.append(o + uv[:, :1]*x + uv[:, 1:]*y)
        g = replace(g, linien=[p for p in linien if p is not None], ebene=None)
        p = next(p for p in e.pmi if p.step_id == nr)
        _pruefe(vorschlag(p, g, e.modell), nr, e.modell)


def test_strichschrift_verlangt_vollstaendiges_l_im_kreis():
    kreis, l = _kreis_und_l()

    def lesen(ring, innen):
        pfade = [(ring, False)]
        if len(innen):
            pfade.append((innen, False))
        return schrift._lies_zeile(schrift._bildzeichen(schrift._bild(pfade, (0,0,1,1), 72)))

    assert lesen(kreis, l) == "Ⓛ"
    for innen in ([], l[:2], l*[-1, 1]+[1, 0], np.vstack((l, [.66,.40])), np.vstack((l, [.66,.75]))):
        assert lesen(kreis, innen) != "Ⓛ"
    assert lesen(kreis[12:], l) != "Ⓛ"


def test_b_und_c_bleiben_getrennte_bezuege():
    e = lade_alles(pfad("nist_ctc_02_asme1_ap203.stp.gz"))
    g = e.grafik[8707]
    assert schrift.lies_schrift(g) == schrift.lies_schrift(replace(g, ebene=None)) == "⌖ ⌀1.5Ⓜ A B C"
    pfade = schrift._pfade(g, g.ebene)
    links, unten, _, oben = schrift._zellen(pfade)[-1]
    linien = list(g.linien)
    # Den Trenner zwischen B und C kippen, bis er keine verlaessliche Zellachse mehr ist.
    idx, = [i for i, (p, _) in enumerate(pfade) if len(p) == 2 and
            np.allclose(p[:, 0], links) and np.allclose(sorted(p[:, 1]), [unten, oben])]
    linien[idx] = linien[idx].copy()
    linien[idx][1] += .01*(oben-unten)*g.ebene[1]
    for ebene in (g.ebene, None):
        assert not schrift.lies_schrift(replace(g, linien=linien, ebene=ebene))
