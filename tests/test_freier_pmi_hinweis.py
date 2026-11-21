"""Freistehende Schrift auf FTC-07 in beiden Toleranzzeilen pruefen und als STEP lesen."""

from dataclasses import replace

import pytest

from programm.kern import p21
from programm.kern.pmi_freier_hinweis import freier_hinweis
from programm.kern.pmi_verbundschrift import lies_verbund_mit_lage
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_grafische_step_reparatur import _als_fuellung, _ohne_semantik


@pytest.mark.parametrize("rahmen_id,note,ansicht,werte,text", [
    (14636, 16461, "MBD_C", [1.778, .381], "4 COPLANAR SURFACES SIM REQT"),
    (14143, 16374, "MBD_B", [1.016, .254], "4 COPLANAR SURFACES"),
])
@pytest.mark.parametrize("art", ["striche", "fuellung"])
def test_freier_hinweis_grafisch_pruefen_und_exportieren(fenster, tmp_path, art, rahmen_id, note, ansicht, werte, text):
    q, ref, rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Grafik.stp", validierung=False)
    if art == "fuellung":
        q = _als_fuellung(q, rein, tmp_path/"Rahmen.stp", [(rahmen_id, rahmen_id-3, rahmen_id+8)], ohne_ebene=True)
        q = _als_fuellung(q, rein, tmp_path/"Hinweis.stp", [(note, note-3, note+8)], ohne_ebene=True)
    f = fenster
    f.lade(q, warten=True)
    quelle = f.erg
    assert not any(p.semantisch for p in quelle.pmi)
    assert all(quelle.modell.datei.get(i) is None for i in (note-8, note+9, note+12))
    assert bool(quelle.grafik[note].linien) == (art == "striche")
    assert bool(quelle.grafik[note].dreiecke) == (art == "fuellung")
    for nr in (13706, 13747, 13788, 13887, rahmen_id):
        p = next(p for p in quelle.pmi if p.step_id == nr)
        f._pmi_befehl("semantisch", p)
        for i, soll in enumerate(p for p in ref.pmi if p.step_id in ref.grafik[nr].pmi_ids
                                 and p.art == ("toleranz" if nr == rahmen_id else "bezug")):
            d = f._semantik_dialog
            if nr == rahmen_id and i == 0:
                assert d.v.freier_hinweis == (note, text)
                assert not d.hinweiswahl.isChecked() and not d.pmi().beschreibung
                d.hinweiswahl.setChecked(True)
            if nr == rahmen_id and i == 1:
                assert d.hinweiswahl is None and d.pmi().beschreibung == text
            f.ansicht.setze_auswahl([quelle.modell.flaechen[j] for j in soll.flaechen])
            d._auswahl_uebernehmen()
            assert not d.fehler()
            d._pruefen()
    ziel = f.speichere_step_pmi(str(tmp_path/"Mit Hinweis.stp"), melden=False)
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == e for i, e in quelle.modell.datei.entities.items())
    paar = [p for p in neu.pmi if p.art == "toleranz" and p.step_id in neu.grafik[rahmen_id].pmi_ids]
    assert len(paar) == 2 and paar[0].folgetoleranzen == [paar[1].step_id]
    assert [p.bezug_text() for p in paar] == ["A|B|C", "A"]
    assert [p.wert for p in paar] == pytest.approx(werte)
    for p in paar:
        assert p.beschreibung == text and not p.simultan_mit
        assert p.flaechen == next(t.flaechen for t in ref.pmi if t.art == "toleranz" and t.step_id in ref.grafik[rahmen_id].pmi_ids)
        assert [v.name for v in neu.ansichten if p.step_id in v.pmi_ids] == [ansicht]
    rahmen = neu.grafik[rahmen_id]
    assert (rahmen.ebene is None) == (art == "fuellung")
    assert freier_hinweis(neu.modell.datei, rahmen, neu.grafik, lies_verbund_mit_lage(rahmen)[1]) == (note, text)
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.StepDimTol import StepDimTol_GeometricTolerance
    leser = STEPControl_Reader()
    assert leser.ReadFile(ziel) == 1
    m = leser.StepModel()
    ids = {p.step_id for p in paar}
    gelesen = {m.IdentLabel(e): StepDimTol_GeometricTolerance.DownCast(e).Description().ToCString()
               for i in range(1, m.NbEntities()+1) if m.IdentLabel(e := m.Value(i)) in ids}
    assert gelesen == dict.fromkeys(ids, text)


def test_freier_hinweis_bei_mehrdeutigkeit_oder_widerspruch():
    ftc07 = lade_alles(pfad("nist_ftc_07_asme1_ap242-e2.stp"))
    g = ftc07.grafik
    rahmen, note = g[14636], g[16461]
    datei = ftc07.modell.datei
    _, lage = lies_verbund_mit_lage(rahmen)
    def mit(nr, ersatz):
        return freier_hinweis(datei, rahmen, {**g, nr: ersatz}, lage)
    for verschiebung in (20*rahmen.ebene[1], rahmen.ebene[3]):
        assert mit(16461, replace(note, linien=[p+verschiebung for p in note.linien])) is None
    assert mit(16461, replace(note, linien=note.linien[1:])) is None
    assert mit(16461, replace(note, kontext=99)) is None
    # Ein zweiter Hinweis oder ein zweiter Rahmen an derselben Stelle verhindert die Zuordnung.
    for kopie in (note, rahmen):
        assert mit(13887, replace(kopie, callout_id=13887)) is None
    def geaendert(nr, teile):
        neu = replace(datei, entities={**datei.entities, nr: p21.Entity(nr, teile)})
        return freier_hinweis(neu, rahmen, g, lage)
    a = datei.get(16480).args()
    assert geaendert(16480, {"DRAUGHTING_MODEL_ITEM_ASSOCIATION": [*a[:2], p21.Ref(13681), *a[3:]]}) is None
    a = datei.get(16451).args()
    assert geaendert(16451, {"DESCRIPTIVE_REPRESENTATION_ITEM": [a[0], "3 COPLANAR SURFACES"]}) is None
    a = datei.get(16473).args()
    assert geaendert(16473, {"DESCRIPTIVE_REPRESENTATION_ITEM": [a[0], a[1].replace("4 ", "3 ")]}) is None
    teile = datei.get(16658).parts.copy()
    name, items, kontext = teile["REPRESENTATION"]
    teile["REPRESENTATION"] = [name, [r for r in items if r != p21.Ref(16461)], kontext]
    assert geaendert(16658, teile) is None
