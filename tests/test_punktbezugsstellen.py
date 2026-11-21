"""Punktbezugsstellen aus CTC-02 mit der unabhaengigen semantischen Kontrollzeichnung vergleichen."""

import gzip
from dataclasses import replace

import numpy as np
import pytest

from programm.kern.pmi_bezugspunkt import grafischer_punkt
from programm.kern.pmi_reparieren import vorschlag
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_profilzonenschrift import _dreiecke
from tests.test_step_ap242 import _occt

STELLEN = {8672: "A1", 8706: "A2", 8693: "A3", 8677: "B1", 8674: "B2", 8710: "B3", 8716: "B4", 8679: "C1"}
QUELLE = "nist_ctc_02_asme1_ap203.stp.gz"


def _netz(g):
    schrift = _gefuellt(replace(g, linien=g.linien[4:-2]))
    return schrift + _dreiecke(replace(g, linien=g.linien[:4] + g.linien[-2:]))


def _referenz():
    erg = lade_alles(pfad("nist_ctc_02_asme1_ap242-e2.stp.gz"))
    d = erg.modell.datei
    orte = {}
    for p in erg.pmi:
        if p.typ != "DatumTarget" or p.modifikatoren != ["point"]:
            continue
        eig, = [a for i in d.referrers()[p.step_id] if (a := d.get(i)).typ == "PROPERTY_DEFINITION" and not a.args()[0]]
        rel, = [d.get(r) for r in d.referrers()[eig.id] if d.get(r).typ == "SHAPE_DEFINITION_REPRESENTATION"]
        ax, = d.get(rel.args()[1]).args()[1]
        orte[p.name] = d.get(d.get(ax).args()[1]).args()[1]
    return orte


def test_zielkreuz_braucht_kontakt_und_kennung():
    erg = lade_alles(pfad(QUELLE))
    orte = _referenz()
    for nr, name in STELLEN.items():
        g = erg.grafik[nr]
        for bild in (g, replace(g, ebene=None), replace(g, linien=[], ebene=None,
                dreiecke=[(v*g.textfaktor, t) for v, t in _netz(g)])):
            wort, ort = grafischer_punkt(bild)
            assert wort == name and np.linalg.norm(ort - orte[name]) < .05
    a = erg.grafik[8672]
    _, x, y, _ = a.ebene
    mitte = a.linien[2].mean(axis=0)
    striche = [[(0,0), (.5,1), (1,0)], [(.2,.4), (.8,.4)], [(1.4,.77), (1.68,1), (1.68,0)]]
    linien = [np.array([mitte + (u-.84)*12*x + (v-1.55)*15*y for u,v in zug]) for zug in striche]
    assert grafischer_punkt(replace(a, linien=a.linien[:4]+linien+a.linien[-2:]))[0] == "A1"
    b = erg.grafik[8674]
    p = next(p for p in erg.pmi if p.step_id == 8674)
    for falsch in (replace(b, linien=b.linien[:-1]), replace(b, linien=b.linien[:4]+b.linien[-2:]),
                   replace(b, linien=[b.linien[0] + b.ebene[3], *b.linien[1:]]), erg.grafik[8713]):
        v = vorschlag(p, falsch, erg.modell)
        assert v.bezugspunkt is None and not v.name and v.typ == "DatumTarget"


@pytest.mark.parametrize("gefuellt", [False, True])
def test_bezugsstellen_projekt_und_step(fenster, tmp_path, gefuellt):
    with gzip.open(pfad(QUELLE), "rt", encoding="ascii") as f:
        text = f.read()
    if gefuellt:
        erg = lade_alles(pfad(QUELLE))
        profil = erg.grafik[8712]
        stil = erg.modell.datei.get(8712).args()[1][0].id
        text = _mit_fuellsatz(text, _gefuellt(profil), 8712, stil, profil.name)
        for nr in STELLEN:
            g = erg.grafik[nr]
            stil = erg.modell.datei.get(nr).args()[1][0].id
            text = _mit_fuellsatz(text, _netz(g), nr, stil, g.name)
    eingang = tmp_path / "Modell.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    e = fenster.erg
    quelle = {p.step_id: p for p in e.pmi}
    referenz = _referenz()
    zielwerte = {}
    for nr in (8688, 8694, 8714, 8712, *sorted(STELLEN, key=lambda n: n == 8674)):
        fenster._pmi_befehl("semantisch", quelle[nr])
        d = fenster._semantik_dialog
        assert not d.fehler(), (nr, d.fehler())
        if nr in STELLEN:
            assert d.typ.currentData() == "DatumTarget" and d.pmi().name == STELLEN[nr]
            assert np.linalg.norm(np.asarray(d.pmi().bezugspunkt) - referenz[STELLEN[nr]]) < .05
            zielwerte[nr] = (d.pmi().bezugspunkt, {e.modell.flaeche_zu_step[i] for i in d.flaechen})
            if nr == 8674:
                teil = fenster.speichere_step_pmi(str(tmp_path / "Teil.step"), melden=False)
                assert teil and len(fenster._step_bericht.uebersprungen) == 4
                assert all("B2" in grund for _, _, grund in fenster._step_bericht.uebersprungen)
        d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Modell.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(str(ziel))
    typen, diagnosen, volumen = _occt(ziel)
    assert (diagnosen, volumen) == _occt(eingang)[1:]
    for nr, (xyz, f) in zielwerte.items():
        g, alt = neu.grafik[nr], e.grafik[nr]
        p, = [p for p in neu.pmi if p.semantisch and p.step_id in g.pmi_ids and p.typ == "DatumTarget"]
        assert p.name == STELLEN[nr] and p.modifikatoren == ["point"]
        assert "PlacedDatumTargetFeature" in typen[p.step_id]
        np.testing.assert_allclose(p.bezugspunkt, xyz, atol=1e-7)
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == f
        for a,b in zip(alt.linien,g.linien,strict=True):
            np.testing.assert_array_equal(a,b)
        for (a,t),(b,u) in zip(alt.dreiecke,g.dreiecke,strict=True):
            np.testing.assert_array_equal(a,b)
            np.testing.assert_array_equal(t,u)
    for nr in (8688, 8694, 8714):
        p, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[nr].pmi_ids]
        assert p.bezug_text() == "A|B|C" and p.wert == 2.5
    profil, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[8712].pmi_ids]
    assert (profil.typ, profil.wert, profil.bezug_text()) == ("ProfileOfLine", .25, "A|B|C")
    assert "GeoTolAndGeoTolWthDatRef" in typen[profil.step_id]
    assert {neu.modell.flaeche_zu_step[i] for i in profil.flaechen} == {e.modell.flaeche_zu_step[i]
            for i in vorschlag(quelle[8712], e.grafik[8712], e.modell).flaechen}
    if not gefuellt:
        from programm.kern.step_schreiben import schreibe
        offen = lade_alles(teil)
        qs = [replace(vorschlag(p, offen.grafik[p.step_id], offen.modell), quelle="eigen", nummer=p.nummer)
              for p in offen.pmi if p.step_id in (8674, 8688, 8694, 8714) and not p.semantisch]
        assert len(qs) == 4
        ohne_b2 = [q for q in qs if q.typ != "DatumTarget"]
        kopie = tmp_path / "Ergaenzt.step"
        bericht = schreibe(teil, kopie, ohne_b2, offen.modell)
        assert len(bericht.uebersprungen) == 3 and all("B2" in m for _,_,m in bericht.uebersprungen)
        bericht = schreibe(teil, kopie, qs, offen.modell)
        assert len(bericht.neu) == 4 and not bericht.uebersprungen


def test_kontakt_in_zoll_und_falsche_uebernahmen(tmp_path):
    from programm.kern.step_schreiben import schreibe
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
    eingang, ziel = tmp_path / "Zoll.step", tmp_path / "Punkt.step"
    eingang.write_text(text, encoding="ascii")
    erg = lade_alles(str(eingang))
    g = erg.grafik[8672]
    roh = next(p for p in erg.pmi if p.step_id == 8672)
    a1 = replace(vorschlag(roh, g, erg.modell), quelle="eigen", nummer=100)
    assert a1.name == "A1" and g.textfaktor == 25.4
    for falsch in (replace(a1, name="A2"), replace(a1, bezugspunkt=[0,0,0]),
                   replace(a1, flaechen={erg.modell.step_zu_flaeche[1129]})):
        bericht = schreibe(eingang, ziel, [falsch], erg.modell)
        assert len(bericht.uebersprungen) == 1 and not bericht.neu
    bericht = schreibe(eingang, ziel, [a1, a1], erg.modell)
    assert len(bericht.uebersprungen) == len(bericht.neu) == 1
    neu = lade_alles(str(ziel))
    q, = [p for p in neu.pmi if p.typ == "DatumTarget" and p.semantisch]
    np.testing.assert_allclose(q.bezugspunkt, a1.bezugspunkt)
    np.testing.assert_allclose(np.asarray(q.bezugspunkt)/25.4, _referenz()["A1"], atol=.05)
