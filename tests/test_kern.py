"""Kernfunktionen an NIST-Modellen: Laden, Flaechenzuordnung, PMI, Ansichten."""

from programm.kern import p21
from programm.kern.ansichten import lies_ansichten
from programm.kern.pmi import BEZUG, MASS, TOLERANZ
from programm.kern.pmi_lesen import lies_pmi, lies_pmi_xcaf
from tests.conftest import pfad


def _art(liste, art):
    return [p for p in liste if p.art == art]


def test_p21_liest_komplexe_entitaeten():
    d = p21.lese(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    assert d.schema.startswith("AP242")
    e = d.entities[21]
    assert e.is_a("GEOMETRIC_TOLERANCE") and e.is_a("POSITION_TOLERANCE")
    assert e.args("GEOMETRIC_TOLERANCE")[0] == "Position.1"


def test_p21_dekodiert_sonderzeichen():
    assert p21._dekodiere("\\X2\\00E4\\X0\\") == "ä"
    assert p21._dekodiere("a\\X\\E4b") == "aäb"


def test_alle_flaechen_zugeordnet(ctc01, ftc10):
    for m in (ctc01, ftc10):
        assert len(m.flaechen) == len(m.datei.of_type("ADVANCED_FACE"))
        assert len(m.step_zu_flaeche) == len(m.flaechen)


def test_ctc01_masse(ctc01):
    masse = _art(lies_pmi(ctc01), MASS)
    texte = [p.wert_text() for p in masse]
    assert len(masse) == 12
    assert "⌀35 0/-0.2" in texte
    assert "⌀20 +0.05/-0.1" in texte
    assert "60° ±0.5" in texte
    assert "⌀34.8–35.2" in texte
    assert all(p.flaechen for p in masse)


def test_ctc01_toleranzen_und_bezuege(ctc01):
    liste = lies_pmi(ctc01)
    tol = {p.wert_text() for p in _art(liste, TOLERANZ)}
    assert "⌖ | 0.75 | A | B | C" in tol
    assert "⏥ | 0.2" in tol
    bez = {p.name: p for p in _art(liste, BEZUG)}
    assert set(bez) == {"A", "B", "C"}
    # B und C haengen in der Datei an SET_REPRESENTATION_ITEM (fehlt in OCCT)
    assert len(bez["B"].flaechen) == 2 and len(bez["C"].flaechen) == 2


def test_ftc10_modifikatoren(ftc10):
    tol = [p.wert_text() for p in _art(lies_pmi(ftc10), TOLERANZ)]
    assert len(tol) == 40
    assert "⌖ | ⌀1Ⓜ | A | B | C" in tol
    assert "⌖ | ⌀0.8 Ⓟ3.2 | D | E | B" in tol
    assert "⌖ | ⌀0.8 | D | E-F-G" in tol
    masse = [p.wert_text() for p in _art(lies_pmi(ftc10), MASS)]
    assert "⌀3.5 G6" in masse


def test_ftc07_zoll_grenzmass(ftc07):
    """Datei in Zoll; Mindestmass 0.012 in (OCCT liest hier faelschlich den Nennwert)."""
    radien = [p for p in _art(lies_pmi(ftc07), MASS) if p.typ == "Size_Radius" and p.grenzmass]
    assert any(abs(p.unten - 0.3048) < 1e-6 and abs(p.oben - 0.5588) < 1e-6 for p in radien)


def test_eigene_masse_umfassen_occt(ctc01, ftc10):
    """Jedes von OCCT gelesene Mass mit Wert ist auch im eigenen Leser."""
    for m in (ctc01, ftc10):
        eigen = {(round(p.nennwert, 4)) for p in _art(lies_pmi(m), MASS) if p.nennwert is not None}
        for p in lies_pmi_xcaf(m):
            if p.art == MASS and p.nennwert is not None and p.typ != "CommonLabel":
                assert round(p.nennwert, 4) in eigen


def test_ansichten(ftc10):
    pmi = lies_pmi(ftc10)
    ans = lies_ansichten(ftc10, pmi)
    assert len(ans) == 18
    mit_pmi = [a for a in ans if a.pmi_nummern]
    assert len(mit_pmi) >= 5
    for a in ans:
        assert abs(sum(c * c for c in a.richtung) - 1) < 1e-6
