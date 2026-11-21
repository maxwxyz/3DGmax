"""Kreisziel, Auflage und zugehoerige Rechtwinkligkeit durch Pruefung, Projekt und STEP."""

from dataclasses import replace
import gzip
import re

import numpy as np
import pytest

from programm.kern.pmi_bezugskreis import grafischer_kreis
from programm.kern.pmi_reparieren import vorschlag
from programm.kern.step_schreiben import schreibe
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_profilzonenschrift import _dreiecke
from tests.test_punktbezugsstellen import QUELLE
from tests.test_step_ap242 import _occt


def _netz(g):
    return _gefuellt(replace(g, linien=g.linien[4:])) + _dreiecke(replace(g, linien=g.linien[:4]))


def _strichtext(text, e, g):
    """Neue offene Mittellinien fuer beide Beschriftungshaelften in der Quelldatei."""
    o,x,y,_ = g.ebene
    z = o + 179.5*x - 43.8*y
    phi = np.linspace(0, 2*np.pi, 41)
    schrift = [z + 5*np.cos(phi)[:,None]*x + 7*np.sin(phi)[:,None]*y, [z-6*x-9.1*y,z+6*x+9.1*y]]
    formen = [([(0.45,.5),(.14,.58),(0,.72),(.04,.88),(.23,1),(.68,1),(.89,.9),(.95,.74),
                (.84,.60),(.45,.5),(.14,.42),(0,.28),(.04,.13),(.24,0),(.7,0),(.95,.13),
                (1,.28),(.84,.42),(.45,.5)], 189,-51.8,11),
              ([(.96,1),(.12,1),(.06,.52),(.35,.61),(.68,.58),(.91,.46),(1,.27),(.92,.12),
                (.72,0),(.26,0),(.05,.12),(0,.19)], 202,-51.8,9),
              ([(0,0),(0,1)], 187,-89.9,10), ([(1,1),(0,.48),(1,0)], 187,-89.9,10),
              ([(0,.75),(.7,1),(.7,0)], 202,-89.9,8)]
    for zug, links, unten, breite in formen:
        schrift.append([o+(links+a*breite)*x+(unten+b*15)*y for a,b in zug])
    nr = max(e.modell.datei.entities)+1
    zeilen = []
    gruppe = e.modell.datei.get(e.modell.datei.get(8713).args()[2])
    linien = [f"#{r.id}" for r in gruppe.args()[1][:4]]
    for linie in schrift:
        punkte = []
        for xyz in linie:
            coords = ",".join(f"{w:.12f}" for w in xyz/g.textfaktor)
            zeilen.append(f"#{nr}=CARTESIAN_POINT('',({coords}));")
            punkte.append(f"#{nr}")
            nr += 1
        zeilen.append(f"#{nr}=POLYLINE('',({','.join(punkte)}));")
        linien.append(f"#{nr}")
        nr += 1
    text, n = re.subn(rf"(#{gruppe.id}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;",
                      r"\g<1>(" + ",".join(linien) + "));", text)
    assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(zeilen) + "\n" + text[pos:]


def _k1(e):
    return next(p for p in e.pmi if p.typ == "DatumTarget" and p.name == "K1" and p.semantisch)


def test_kreis_braucht_durchmesser_kennung_hinweis_und_ring():
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[8713]
    f = {e.modell.step_zu_flaeche[1158]}
    netz = [(p*g.textfaktor,t) for p,t in _netz(g)]
    for bild in (replace(g, ebene=None), replace(g, linien=[], ebene=None, dreiecke=netz)):
        k = grafischer_kreis(bild, e.modell, f)
        assert (k.name, k.durchmesser) == ("K1", 85)
        np.testing.assert_allclose(k.mitte, [0,812,-140], atol=1e-6)
        np.testing.assert_allclose(k.normale, [0,1,0], atol=1e-6)
    o, x, y, _ = g.ebene
    z = o + 179.5*x - 43.8*y
    phi = np.linspace(0, 2*np.pi, 41)
    ring = z + 5*np.cos(phi)[:,None]*x + 7*np.sin(phi)[:,None]*y
    quer = np.array([z-6*x-9.1*y, z+6*x+9.1*y])
    strich = replace(g, linien=g.linien[:4]+[ring,quer]+g.linien[7:])
    assert grafischer_kreis(strich, e.modell, f).durchmesser == 85
    for linien in (g.linien[1:], g.linien[:4]+g.linien[7:], g.linien[:-2],
                   [g.linien[0], g.linien[1]+3*g.ebene[2], *g.linien[2:]],
                   [g.linien[0], np.array([g.linien[1][0], [0,812,-140]]), *g.linien[2:]],
                   [*g.linien, g.linien[3]+100*g.ebene[2]]):
        assert grafischer_kreis(replace(g, linien=linien), e.modell, f) is None
    assert grafischer_kreis(g, e.modell, {e.modell.step_zu_flaeche[1124]}) is None
    assert grafischer_kreis(g, e.modell, set()) is None


@pytest.mark.parametrize("schrift", ["kontur", "fuellung", "strich"])
def test_k1_und_rechtwinkligkeit_bis_step(fenster, tmp_path, schrift):
    with gzip.open(pfad(QUELLE), "rt", encoding="ascii") as f:
        text = f.read()
    if schrift != "kontur":
        e = lade_alles(pfad(QUELLE))
        g = e.grafik[8713]
        text = (_strichtext(text, e, g) if schrift == "strich" else
                _mit_fuellsatz(text, _netz(g), 8713, e.modell.datei.get(8713).args()[1][0].id, g.name))
    eingang = tmp_path / "Quelle.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    e = fenster.erg
    for nr in (8680, 8713):
        p = next(p for p in e.pmi if p.step_id == nr)
        fenster._pmi_befehl("semantisch", p)
        d = fenster._semantik_dialog
        assert not d.fehler()
        if nr == 8713:
            assert d.pmi().wert_text() == "[K1] ⌀85"
            assert d.felder["kreismass"].text() == "⌀85"
            assert d.felder["kreisachse"].isVisible()
            d.flaechen = {e.modell.step_zu_flaeche[1124]}
            assert d.fehler()
            d.flaechen = {e.modell.step_zu_flaeche[1158]}
        d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Kreis.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Kreis.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    k = _k1(neu)
    soll = _k1(lade_alles(pfad("nist_ctc_02_asme1_ap242-e2.stp.gz")))
    assert k.modifikatoren == soll.modifikatoren == ["circle"]
    assert k.bezugsdurchmesser == soll.bezugsdurchmesser == 85.0
    np.testing.assert_allclose(k.bezugspunkt, soll.bezugspunkt, atol=1e-7)
    np.testing.assert_allclose(k.bezugsnormale, soll.bezugsnormale)
    assert {neu.modell.flaeche_zu_step[i] for i in k.flaechen} == {1158}
    assert k.step_id in neu.grafik[8713].pmi_ids
    rahmen, = [q for q in neu.pmi if q.semantisch and q.step_id in neu.grafik[8680].pmi_ids]
    assert (rahmen.typ, rahmen.wert, rahmen.bezug_text()) == ("Perpendicularity", .25, "K")
    typen, diagnosen, volumen = _occt(ziel)
    assert (diagnosen, volumen) == _occt(eingang)[1:]
    assert "PlacedDatumTargetFeature" in typen[k.step_id]
    g, alt = neu.grafik[8713], e.grafik[8713]
    for a,b in zip(g.linien,alt.linien,strict=True):
        np.testing.assert_array_equal(a,b)
    for (a,b),(c,d) in zip(g.dreiecke,alt.dreiecke,strict=True):
        np.testing.assert_array_equal(a,c)
        np.testing.assert_array_equal(b,d)
    if schrift == "kontur":
        e = lade_alles(str(eingang))
        p = next(v for v in e.pmi if v.step_id == 8713)
        eigen = replace(vorschlag(p, alt, e.modell), quelle="eigen", nummer=100)
        for falsch in (replace(eigen, bezugsdurchmesser=75), replace(eigen, bezugsnormale=[0,-1,0]),
                       replace(eigen, bezugspunkt=[0,812,0]), replace(eigen, modifikatoren=["point"])):
            b = schreibe(eingang, tmp_path / "Abgewiesen.step", [falsch], e.modell)
            assert len(b.uebersprungen) == 1 and not b.neu


def test_zoll_kreis_und_ausgerichteter_revisionsvergleich(tmp_path):
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    from programm.kern.vergleich_pmi import vergleiche_pmi
    with gzip.open(pfad(QUELLE), "rt", encoding="ascii") as f:
        text = f.read()
    kontext = "GLOBAL_UNIT_ASSIGNED_CONTEXT((#46157,#46153,#46152))"
    assert text.count(kontext) == 1
    text = text.replace(kontext, kontext.replace("#46157", "#90002"))
    ende = text.rindex("ENDSEC;")
    text = text[:ende] + """#90000=DIMENSIONAL_EXPONENTS(1.,0.,0.,0.,0.,0.,0.);
#90001=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(25.4),#46157);
#90002=(CONVERSION_BASED_UNIT('INCH',#90001)LENGTH_UNIT()NAMED_UNIT(#90000));
""" + text[ende:]
    eingang, ziel = tmp_path / "Zoll.step", tmp_path / "Ergebnis.step"
    eingang.write_text(text, encoding="ascii")
    e = lade_alles(str(eingang))
    p = next(v for v in e.pmi if v.step_id == 8713)
    k = replace(vorschlag(p,e.grafik[8713],e.modell), quelle="eigen", nummer=80)
    assert k.bezugsdurchmesser == 85*25.4
    assert not schreibe(eingang, ziel, [k], e.modell).uebersprungen
    a = _k1(lade_alles(str(ziel)))
    assert a.bezugsdurchmesser == 85*25.4
    np.testing.assert_allclose(a.bezugspunkt, np.array([0,812,-140])*25.4, atol=1e-6)
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), .73)
    t.SetTranslationPart(gp_Vec(35,-40,75))
    b = replace(a, bezugspunkt=gp_Pnt(*a.bezugspunkt).Transformed(t).Coord(),
                bezugsnormale=gp_Dir(*a.bezugsnormale).Transformed(t).Coord())
    lage = TopLoc_Location(t.Inverted())
    assert vergleiche_pmi([a], [b], lage=lage)[0].status == "gleich"
    q = replace(b, bezugsdurchmesser=90*25.4, bezugspunkt=[0,0,0], bezugsnormale=[0,0,1])
    diff, = vergleiche_pmi([a], [q], lage=lage)
    assert {feld for feld, _, _ in diff.felder} == {"bezugsdurchmesser", "bezugspunkt", "bezugsnormale"}
