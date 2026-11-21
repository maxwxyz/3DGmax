"""Mehrfaches Dickenmass an den vier Auflagen von CTC-03, einschliesslich STEP-Ruecklesen."""
from dataclasses import replace
import gzip
from pathlib import Path

import numpy as np
import pytest

from programm.kern import pmi_strichschrift as schrift
from programm.kern.baugruppe_mass import ebene
from programm.kern.pmi_dickenschrift import dickenmass
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_kreisbezugsstelle import _ersetze_schrift
from tests.test_radialmass_knickpfeil import QUELLE
from tests.test_step_ap242 import _occt

ZIELE = {481,557,558,563,566}
WORT = "4X.82±.06"


def _striche(g):
    """Einlinige Zeichen an den Druckpositionen der Originalkonturen."""
    form = {6:["58 50 05 65"], 8:["00 68","60 08"], 9:["00 60 68 08 00"],
            12:["20 40 61 63 44 24 03 01 20","24 44 65 67 48 28 07 05 24"],
            13:["02 11 20 40 61 63 08 68"], 14:["30 38","04 64"], 15:["04 64"],
            16:["00 60 68 08 00"], 17:["20 40 61 67 48 28 07 01 20"],
            19:["60 30 12 04 07 18 48 67 65 54 24 05"]}
    o,x,y,_ = g.ebene
    pfade = schrift._pfade(g, g.ebene)
    neue = []
    for i, zuege in form.items():
        p = pfade[i][0]
        for zug in zuege:
            uv = np.array([(int(a)/6, 1-int(b)/8) for a,b in zug.split()])
            breite, hoehe = np.ptp(p,axis=0)
            if i == 12:
                breite = .75*hoehe
            pos = (p.max(0)+p.min(0))/2 + (uv-.5)*[breite,hoehe]
            neue.append(o+pos[:, :1]*x+pos[:, 1:]*y)
    return neue


def test_dickenmass_braucht_vollstaendige_grafik_und_ziele():
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[3634]
    ids = {e.modell.step_zu_flaeche[n] for n in ZIELE}
    netz = [(p*g.textfaktor,t) for p,t in _gefuellt(g)]
    for grafik in (replace(g,linien=g.linien[::-1]), replace(g,linien=g.linien[:6]+_striche(g)),
                   replace(g,linien=[],dreiecke=netz)):
        assert dickenmass(replace(grafik, ebene=None), e.modell, ids)[0] == WORT
    assert dickenmass(g, e.modell, ids-{e.modell.step_zu_flaeche[558]}) is None
    for linien in (g.linien[1:], g.linien[:4]+g.linien[5:], g.linien[:8]+g.linien[9:],
                   g.linien+[g.linien[9]+70*g.ebene[2]], [g.linien[0]+g.ebene[2], *g.linien[1:]]):
        assert dickenmass(replace(g,linien=linien), e.modell, ids) is None
    # Nur die gedruckte Stueckzahl bzw. das Abmass aendern.
    pfade = schrift._pfade(g,g.ebene)
    for ziel, quelle, soll in [(6,13,None), (19,13,"4X.82±.02")]:
        p,q = pfade[ziel][0],pfade[quelle][0]
        pos = p.min(0) + (q-q.min(0))*np.ptp(p,0)/np.ptp(q,0)
        o,x,y,_ = g.ebene
        linien = list(g.linien)
        linien[ziel:ziel+2] = [o+pos[:,:1]*x+pos[:,1:]*y]
        fund = dickenmass(replace(g,linien=linien),e.modell,ids)
        assert (fund[0] if fund else None) == soll


@pytest.mark.parametrize("art", ["kontur","strich","fuellung"])
def test_dicke_im_projekt_und_step(art, fenster, tmp_path):
    quelle = pfad(QUELLE)
    e = lade_alles(quelle)
    g = e.grafik[3634]
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if art == "strich":
        text = _ersetze_schrift(text, e, g, 6, _striche(g))
    elif art == "fuellung":
        stil = e.modell.datei.get(3634).args()[1][0].id
        text = _mit_fuellsatz(text, _gefuellt(g), 3634, stil, g.name)
    eingang = tmp_path/"Auflagen.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    alt = fenster.erg
    grafik = alt.grafik[3634]
    fenster._pmi_befehl("semantisch", next(p for p in alt.pmi if p.step_id == 3634))
    d = fenster._semantik_dialog
    assert d.v.ocr_text == WORT and d.v.typ == "Size_Thickness" and not d.fehler()
    entfernte = d.flaechen.pop()
    assert d.fehler()
    d.flaechen.add(entfernte)
    d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path/"Auflagen.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    n = neu.grafik[3634]
    p, = [q for q in neu.pmi if q.semantisch and q.step_id in n.pmi_ids]
    assert p.typ == "Size_Thickness" and p.nennwert == pytest.approx(20.828)
    assert p.grenzen() == pytest.approx((22.352,19.304))
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == ZIELE
    assert _ansichten(alt.modell.datei, 3634) == _ansichten(neu.modell.datei, 3634) != set()
    for a,b in zip(grafik.linien, n.linien, strict=True):
        np.testing.assert_array_equal(a,b)
    for (a,t),(b,u) in zip(grafik.dreiecke, n.dreiecke, strict=True):
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t,u)
    refpfad = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/nist_ctc_03_asme1_ap242-e2.stp"
    if refpfad.is_file():
        ref = lade_alles(str(refpfad))
        r = next(q for q in ref.pmi if q.step_id == 270)
        assert (r.typ,r.nennwert) == (p.typ,pytest.approx(p.nennwert))
        assert r.grenzen() == pytest.approx(p.grenzen())
        def mitten(modell, ids):
            return sorted(tuple(ebene(modell.flaechen[i])[0].round(5)) for i in ids)
        # Die AP242-Auflagen liegen um 0,00254 mm hoeher als im AP203-Modell.
        np.testing.assert_allclose(mitten(ref.modell,r.flaechen), mitten(neu.modell,p.flaechen),
                                   rtol=0, atol=.00255)
    typen, diagnosen, volumen = _occt(ziel)
    assert "DimensionalSize" in typen[p.step_id]
    assert (diagnosen, volumen) == _occt(eingang)[1:]
