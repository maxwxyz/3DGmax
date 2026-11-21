"""Grosser STEP-Import: gleiche Referenzen und editierbare Geometrie, Abbruch mit lebendem Reader."""

from concurrent.futures import ThreadPoolExecutor
import pytest

from programm.kern import laden, p21, step_import
from tests.conftest import pfad


def test_rohgeometrie_index_und_paralleler_zugriff():
    text = """DATA;
    #3=CARTESIAN_POINT('text; /* #19 */ und ''#20''',(1,-2,3.));
    #4=LINE('',#3,#3); #7=EDGE_LOOP('',(#4,#4,#3)); #12=(A(#3) B(#7));
    ENDSEC;"""
    d = p21.lese_text(text, geometrie_spaeter=True)
    assert list(d.referrers().items()) == [(3, [4, 4, 7, 12]), (4, [7, 7]), (7, [12])]
    assert [e.id for e in d.of_types_by_id(["LINE", "A", "B"])] == [4, 12]
    with ThreadPoolExecutor(4) as pool:
        listen = list(pool.map(lambda _: d.get(4).args(), range(20)))
    assert all(werte is listen[0] for werte in listen)
    assert d.entities == p21.lese_text(text).entities
    d = p21.lese_text(text, geometrie_spaeter=True)
    d.get(4).args()[1].id = 8
    d.get(7).parts = {"EDGE_LOOP": ["", [p21.Ref(4)]]}
    assert d.referrers() == {8: [4], 3: [4, 12], 4: [7], 7: [12]}
    with pytest.raises(InterruptedError):
        p21.lese_text(text, geometrie_spaeter=True, abbruch=lambda: True)


def test_step_transfer_abbrechen_und_neu_laden(monkeypatch):
    monkeypatch.setattr(laden, "STEP_PARALLEL_AB", 0)
    if step_import.bibliothek() is None:
        pytest.skip("Native STEP-Bibliothek im Quellbaum nicht gebaut")
    quelle = pfad("nist_ftc_10_asme1_ap242-e2.stp")
    fortschritt = []
    def abbrechen(text):
        if "%" in text:
            prozent = int(text.split("…")[-1].strip(" %"))
            fortschritt.append(prozent)
            if prozent > 0:
                raise InterruptedError("abgebrochen")
    with pytest.raises(InterruptedError):
        laden.lade_step(quelle, abbrechen)
    assert any(p > 0 for p in fortschritt)
    modell = laden.lade_step(quelle)
    assert modell.flaeche_zu_step and len(modell.flaechen) > 243
    i, quelle = next(iter(modell.flaeche_zu_step.items()))
    assert modell.form_von_step(quelle).IsPartner(modell.flaechen[i])


def test_step_import_ohne_native_bibliothek(monkeypatch):
    monkeypatch.setattr(step_import, "bibliothek", lambda: None)
    modell = laden.lade_step(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    assert len(modell.flaechen) == 117
    assert modell.datei.get(21).is_a("GEOMETRIC_TOLERANCE")
