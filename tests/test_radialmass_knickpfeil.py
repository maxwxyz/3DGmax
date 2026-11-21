"""Durchmessermass mit langem Knickpfeil an der zentralen Bohrung von CTC-03."""
from dataclasses import replace
import gzip
from pathlib import Path

import numpy as np
import pytest
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder

from programm.kern import pmi_strichschrift as schrift
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_kreisbezugsstelle import _ersetze_schrift
from tests.test_step_ap242 import _occt

QUELLE = "nist_ctc_03_asme1_ap203.stp.gz"
WORT = "⌀2.00±.01"


def _strichschrift(g):
    """Einlinige Ziffern und Zeichen in den Originalpositionen der Konturschrift."""
    phi = np.linspace(0, 2*np.pi, 65)
    ring = .5 + .5*np.column_stack((np.cos(phi), np.sin(phi)))
    null = [[(.33,0),(.66,0),(1,.13),(1,.87),(.66,1),(.33,1),(0,.87),(0,.13),(.33,0)]]
    punkt = [[(0,0),(1,0),(1,1),(0,1),(0,0)]]
    zeichen = {
        3: [[(0,.75),(.16,.88),(.33,1),(.67,1),(1,.88),(1,.63),(0,0),(1,0)]],
        4: punkt, 5: null, 7: null,
        9: [[(.5,0),(.5,1)],[(0,.5),(1,.5)]], 10: [[(0,.5),(1,.5)]],
        11: punkt, 12: null, 14: [[(0,.75),(.76,1),(.76,0)]],
        15: [ring*[.98,.72]+[.01,.14],[(.12,0),(.9,1)]]}
    o, x, y, _ = g.ebene
    pfade = schrift._pfade(g, g.ebene)
    linien = []
    for i, zuege in zeichen.items():
        kontur = pfade[i][0]
        for zug in zuege:
            uv = kontur.min(0) + np.array(zug)*np.ptp(kontur, axis=0)
            linien.append(o + uv[:, :1]*x + uv[:, 1:]*y)
    return linien


def test_radialmass_schrift_und_zusatzzeichen():
    g = lade_alles(pfad(QUELLE)).grafik[3629]
    for grafik in (g, replace(g, linien=g.linien[:3]+_strichschrift(g)),
                   replace(g, linien=[], dreiecke=[(a*g.textfaktor,t) for a,t in _gefuellt(g)])):
        for ebene in (g.ebene, None):
            assert schrift.lies_schrift(replace(grafik, ebene=ebene)) == WORT
    # Ein Zusatz oberhalb des Werts und eine beschaedigte Spitze sind keine neue Lesart.
    for linien in (g.linien+[g.linien[3]+18*g.ebene[2]], g.linien[:2]+g.linien[3:]):
        assert not schrift.lies_schrift(replace(g, linien=linien))
    # Ein anderes gedrucktes Abmass am selben Zylinder muss die Lesung aendern.
    pfade = schrift._pfade(g, g.ebene)
    dx, dy = pfade[14][0].min(0) - pfade[3][0].min(0)
    linien = list(g.linien)
    linien[14] = linien[3] + dx*g.ebene[1] + dy*g.ebene[2]
    assert schrift.lies_schrift(replace(g, linien=linien)) == "⌀2.00±.02"


def _pruefe_zylinder(modell, flaechen):
    umfang = 0.
    for i in flaechen:
        a = BRepAdaptor_Surface(modell.flaechen[i])
        assert a.GetType() == GeomAbs_Cylinder
        c = a.Cylinder()
        assert c.Radius() == pytest.approx(25.4)
        assert c.Location().Coord()[:2] == pytest.approx((-151.9174,356.9208))
        assert c.Axis().Direction().Coord() == pytest.approx((0,0,1))
        assert [a.Value(0,v).Z() for v in (a.FirstVParameter(),a.LastVParameter())] == pytest.approx((76.2,78.10754))
        umfang += a.LastUParameter()-a.FirstUParameter()
    assert umfang == pytest.approx(2*np.pi)


@pytest.mark.parametrize("art", ["kontur","strich","fuellung"])
def test_gepruefter_bohrungsdurchmesser_im_step(art, fenster, tmp_path):
    quelle = pfad(QUELLE)
    e = lade_alles(quelle)
    g = e.grafik[3629]
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if art == "strich":
        text = _ersetze_schrift(text, e, g, 3, _strichschrift(g))
    elif art == "fuellung":
        stil = e.modell.datei.get(3629).args()[1][0].id
        text = _mit_fuellsatz(text, _gefuellt(g), 3629, stil, g.name)
    eingang = tmp_path/"Bohrung.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    alt = fenster.erg
    grafik = alt.grafik[3629]
    assert bool(grafik.dreiecke) == (art == "fuellung") and bool(grafik.linien) == (art != "fuellung")
    fenster._pmi_befehl("semantisch", next(p for p in alt.pmi if p.step_id == 3629))
    d = fenster._semantik_dialog
    assert not d.fehler() and d.v.ocr_text == WORT
    d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path/"Bohrung.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    n = neu.grafik[3629]
    p, = [p for p in neu.pmi if p.semantisch and p.step_id in n.pmi_ids]
    assert p.typ == "Size_Diameter" and p.nennwert == pytest.approx(50.8)
    assert p.grenzen() == pytest.approx((51.054,50.546))
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {544}
    _pruefe_zylinder(neu.modell, p.flaechen)
    referenz = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/nist_ctc_03_asme1_ap242-e2.stp"
    if referenz.is_file():
        ref = lade_alles(str(referenz))
        r = next(q for q in ref.pmi if q.step_id == 267)
        assert p.typ == r.typ and p.grenzen() == pytest.approx(r.grenzen())
        _pruefe_zylinder(ref.modell, r.flaechen)
    assert _ansichten(alt.modell.datei, 3629) == _ansichten(neu.modell.datei, 3629) != set()
    for a,b in zip(grafik.linien, n.linien, strict=True):
        np.testing.assert_array_equal(a,b)
    for (a,t),(b,u) in zip(grafik.dreiecke, n.dreiecke, strict=True):
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t,u)
    typen, diagnosen, volumen = _occt(ziel)
    assert "DimensionalSize" in typen[p.step_id]
    assert (diagnosen, volumen) == _occt(eingang)[1:]
