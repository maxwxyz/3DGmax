"""Einzelrahmen mit Flaechenanzahl im grafischen NIST CTC-02 und CTC-03."""

from dataclasses import replace
import gzip
from pathlib import Path

import numpy as np
import pytest

from programm.kern.pmi_freier_hinweis import _ansichten
from programm.kern.pmi_koplanarschrift import passende_flaechen, profil_mit_hinweis
from programm.kern.pmi_reparieren import vorschlag
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_kreisbezugsstelle import _ersetze_schrift
from tests.test_punktbezugsstellen import QUELLE
from tests.test_step_ap242 import _occt


def _strichtext(g, zeilen):
    from programm.kern.pmi_rahmenzusatz import _ZUEGE
    o, x, y, _ = g.ebene
    linien = list(g.linien[:14])
    start, oben = (115., 40.) if g.callout_id == 3636 else (150., 58.)
    zuege = {**_ZUEGE, "2": [[(0,3.7), (2,1.7), (5.2,0), (10.4,0), (15,2.2), (15,5.8), (.2,16), (15,16)]],
             "Z": [[(0,0), (15,0), (0,16), (15,16)]]}
    for i, wort in enumerate(zeilen):
        pos = start
        for z in wort:
            if z == " ":
                pos += 7
                continue
            for zug in zuege[z]:
                linien.append(np.array([o+(pos+.70*u)*x+(oben-i*26-.9*v)*y for u, v in zug]))
            pos += 13
    return replace(g, linien=linien)


def test_vollstaendige_beschriftung_und_quellflaechen():
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[8709]
    orig = next(p for p in e.pmi if p.step_id == 8709)
    v = vorschlag(orig, g, e.modell)
    netz = replace(g, linien=[], dreiecke=[(a*g.textfaktor, t) for a,t in _gefuellt(g)])
    for grafik in (g, netz, _strichtext(g, ("4 COPLANAR", "SURFACES"))):
        for achsen in (grafik.ebene, None):
            assert profil_mit_hinweis(replace(grafik, ebene=achsen)) == ("⌓ 0.1", "4 COPLANAR SURFACES")
    for zeilen in (("44 COPLANAR", "SURFACES"), ("4 COPLANAR SURFACES",)):
        assert profil_mit_hinweis(_strichtext(g, zeilen)) == ("⌓ 0.1", " ".join(zeilen))
    assert {e.modell.flaeche_zu_step[i] for i in v.flaechen} == {1127, 1198, 1187, 1132}
    assert passende_flaechen(g, 4, v.flaechen, e.modell)
    assert not passende_flaechen(replace(g, pmi_ids=g.pmi_ids-{274, 275}), 4, v.flaechen, e.modell)
    assert not passende_flaechen(g, 5, v.flaechen, e.modell)
    for falsch in (replace(g, linien=g.linien[:-1]), replace(g, linien=g.linien[:29]),
            replace(g, linien=g.linien[:29]+[a+5*g.ebene[3] for a in g.linien[29:]]),
            replace(g, linien=g.linien[:16]+[a-5*g.ebene[1] for a in g.linien[16:29]]+g.linien[29:]),
            _strichtext(g, ("4 C0PLANAR", "SURFACES")), _strichtext(g, ("4 COPLANAR", "SURFACE"))):
        assert profil_mit_hinweis(falsch) is None


def test_validierung_bestaetigt_oder_widerspricht(monkeypatch):
    from programm.kern import pmi_validierungstext
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[8709]
    orig = next(p for p in e.pmi if p.step_id == 8709)
    for roh, wert in ((r"FCF\w⌓\w0.1", .1), (r"FCF\w⌓\w0.1\xTXT\w4 COPLANAR SURFACES", .1),
                      (r"FCF\w⌓\w0.1\xTXT\w3 COPLANAR SURFACES", None), (r"FCF\w⌓\w0.2", None)):
        monkeypatch.setattr(pmi_validierungstext, "_validierungswerte", lambda *args: {roh})
        q = vorschlag(orig, g, e.modell)
        assert q.wert == wert and q.beschreibung == "4 COPLANAR SURFACES"


@pytest.mark.parametrize("schrift", ["kontur", "strich", "fuellung"])
@pytest.mark.parametrize("modell,nr,zeilen,ziele,ansicht,mm", [
    ("02", 8709, ("4 COPLANAR", "SURFACES"), {1127, 1198, 1187, 1132}, 8309, .1),
    ("03", 3636, ("2 COPLANAR SURFACES",), {492, 502}, 3388, .254),
])
def test_koplanarer_rahmen_projekt_und_step(fenster, tmp_path, schrift, modell, nr, zeilen, ziele, ansicht, mm):
    from programm.kern.step_schreiben import schreibe
    quelle = pfad(f"nist_ctc_{modell}_asme1_ap203.stp.gz")
    anzahl = len(ziele)
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if schrift != "kontur":
        e = lade_alles(quelle)
        g = e.grafik[nr]
        stil = e.modell.datei.get(nr).args()[1][0].id
        if schrift == "strich":
            linien = _strichtext(g, zeilen).linien[14:]
            text = _ersetze_schrift(text, e, g, 14, linien)
        else:
            text = _mit_fuellsatz(text, _gefuellt(g), nr, stil, g.name)
    eingang = tmp_path/"Modell.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    e = fenster.erg
    g = e.grafik[nr]
    fenster._pmi_befehl("semantisch", next(p for p in e.pmi if p.step_id == nr))
    d = fenster._semantik_dialog
    assert not d.fehler() and d.pmi().koplanare_anzahl == anzahl
    flaechen = set(d.flaechen)
    idx = d.flaechen.pop()
    assert d.fehler()
    d.flaechen.add(idx)
    d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path/"Kontrolle.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    q, = [p for p in fenster.erg.pmi if p.quelle == "eigen"]
    assert q.koplanare_anzahl == anzahl
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Kontrolle.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(str(ziel))
    n = neu.grafik[nr]
    p, = [p for p in neu.pmi if p.semantisch and p.step_id in n.pmi_ids]
    assert (p.typ, p.wert, p.bezuege, p.modifikatoren) == ("ProfileOfSurface", pytest.approx(mm), [], [])
    assert p.beschreibung == " ".join(zeilen)
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == ziele
    assert _ansichten(neu.modell.datei, nr) == _ansichten(e.modell.datei, nr) == {ansicht}
    referenz = (Path(pfad("nist_ctc_02_asme1_ap242-e2.stp.gz")) if modell == "02" else
                Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/nist_ctc_03_asme1_ap242-e2.stp")
    if referenz.is_file():
        from programm.kern.messen import _mittelpunkt
        ref = lade_alles(str(referenz))
        r = next(q for q in ref.pmi if q.step_id == (53 if modell == "02" else 35))
        assert (p.typ, p.wert, p.bezuege, p.modifikatoren) == (r.typ, pytest.approx(r.wert), r.bezuege, r.modifikatoren)
        def mitten(modell, flaechen):
            return sorted((_mittelpunkt(modell.flaechen[i]).Coord() for i in flaechen),
                          key=lambda xyz: tuple(np.round(xyz, 5)))
        np.testing.assert_allclose(mitten(neu.modell, p.flaechen), mitten(ref.modell, r.flaechen), atol=.0001, rtol=0)
    for a,b in zip(g.linien,n.linien,strict=True):
        np.testing.assert_array_equal(a,b)
    for (a,t),(b,u) in zip(g.dreiecke,n.dreiecke,strict=True):
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t,u)
    typen, diagnosen, volumen = _occt(ziel)
    assert "SurfaceProfileTolerance" in typen[p.step_id]
    assert (diagnosen, volumen) == _occt(eingang)[1:]
    if schrift == "kontur":
        for defekt in (dict(flaechen=flaechen-{idx}), dict(koplanare_anzahl=3),
                dict(beschreibung="3 COPLANAR SURFACES"), dict(callout=8712)):
            bericht = schreibe(str(eingang), tmp_path/"Unvollstaendig.step", [replace(q, **defekt)], e.modell)
            assert not bericht.neu and len(bericht.uebersprungen) == 1

def test_enge_konturen_und_geteilte_dreieckskanten():
    e = lade_alles(pfad("nist_ctc_03_asme1_ap203.stp.gz"))
    g = e.grafik[3636]
    linien = g.linien
    netz = replace(g, linien=[], dreiecke=[(p*g.textfaktor, t[::-1]) for p,t in reversed(_gefuellt(g))])
    for bild in (g, netz):
        for ebene in (g.ebene, None):
            assert profil_mit_hinweis(replace(bild, ebene=ebene)) == ("⌓ .01", "2 COPLANAR SURFACES")
    for text in ("Z COPLANAR SURFACES", "2 C0PLANAR SURFACES", "2COPLANAR SURFACES"):
        assert profil_mit_hinweis(_strichtext(g, (text,))) is None
    for defekt in (linien[:17]+linien[18:], linien[:14]+linien[15:], linien[:-1], linien+[linien[-1]],
                   linien[:28]+[p-4*g.ebene[1] for p in linien[28:]]):
        assert profil_mit_hinweis(replace(g, linien=defekt)) is None
