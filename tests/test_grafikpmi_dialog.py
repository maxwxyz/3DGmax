"""Modellweite Reparatur prueft jeden Originalcallout und behaelt seine Ansichten bei."""

from dataclasses import replace

from programm.kern.pmi import BezugsRef, Pmi
from programm.ui.semantik_ui import SemantikDialog, kandidaten
from tests.conftest import pfad
from tests.test_step_schreiben import nur_grafisch_ctc01


def test_stapel_uebernehmen_ueberspringen_beenden_und_reparatur_zuruecknehmen(fenster, tmp_path):
    f = fenster
    f.lade(nur_grafisch_ctc01(tmp_path / "graphisch.stp"), warten=True)
    alt = f.erg.pmi.copy()
    p, text1, text2 = kandidaten(f.erg)
    g = f.erg.grafik[p.step_id]
    a = next(a for a in f.erg.ansichten if p.step_id in a.pmi_ids)
    assert f.aktionen["pmi_semantisieren"].isEnabled()
    f.aktionen["grafik"].setChecked(False)
    f.aktionen["pmi_semantisieren"].trigger()
    d = f._semantik_dialog
    assert f.ansicht.grafik_an
    assert d.v.callout == 611 and "1 von 3" in d.windowTitle()
    d.felder["wert"].setText("0,1")
    d._pruefen()
    neu = next(q for q in f.erg.pmi if q.callout == p.step_id)
    assert neu.nummer == p.nummer and neu.step_id in a.pmi_ids and p.nummer in a.pmi_nummern
    assert neu.step_id in g.pmi_ids and f._semantik_dialog.v.callout == text1.step_id
    f._semantik_dialog.done(2)
    assert f._semantik_dialog.v.callout == text2.step_id
    f._semantik_dialog.reject()
    assert f._semantik_dialog is None and kandidaten(f.erg) == [text1, text2]
    assert not f.ansicht.grafik_an
    a_eigen = replace(a, eigen=True, name="Reparatur", pmi_ids={neu.step_id}, pmi_nummern=[neu.nummer])
    f.erg.ansichten.append(a_eigen)
    projekt = f.speichere_projekt(str(tmp_path / "reparatur.3dgmax"))
    f.loesche_eigene_pmi([neu])
    assert f.erg.pmi == alt and f.erg.grafik[p.step_id] is g
    assert neu.step_id not in g.pmi_ids and p.step_id in a.pmi_ids and neu.step_id not in a.pmi_ids
    assert p in kandidaten(f.erg)
    f.oeffne_projekt(projekt, warten=True)
    a_eigen = next(v for v in f.erg.ansichten if v.name == "Reparatur")
    neu = next(q for q in f.erg.pmi if q.callout == p.step_id)
    assert a_eigen.pmi_ids == {neu.step_id}
    f.loesche_eigene_pmi([neu])
    assert a_eigen.pmi_ids == {p.step_id} and a_eigen.pmi_nummern == [p.nummer]
    assert any(q.step_id == p.step_id for q in kandidaten(f.erg))


def test_stapel_modellwechsel_und_fremde_callouts(fenster, tmp_path):
    from programm.kern.zusammenfuegen import ID_VERSATZ
    f = fenster
    f.lade(nur_grafisch_ctc01(tmp_path / "alt.stp"), warten=True)
    p, _, text = kandidaten(f.erg)
    fremd = replace(text, step_id=text.step_id + ID_VERSATZ)
    f.erg.grafik[fremd.step_id] = replace(f.erg.grafik[text.step_id], callout_id=fremd.step_id)
    f.erg.pmi.append(fremd)
    assert kandidaten(f.erg, [fremd, replace(p)]) == []
    f._pmi_befehl("semantisch", [p, text])
    assert "1 von 2" in f._semantik_dialog.windowTitle()
    f._semantik_dialog.done(2)
    assert f._semantik_dialog.v.callout == text.step_id
    f.lade(pfad("baugruppe.stp"), warten=True)
    assert f._semantik_dialog is None and not f.aktionen["pmi_semantisieren"].isEnabled()
    assert not any(q.callout for q in f.erg.pmi)


def test_dialog_prueft_eingaben_und_bewahrt_bezugsmodifikatoren(app):
    p = Pmi("toleranz", "Position", wert=.1, flaechen={3}, bezuege=[
        BezugsRef("A-B", element_modifikatoren={"A": ["MaximumMaterialRequirement"]})])
    d = SemantikDialog(p, set, lambda f: None)
    assert not d.fehler() and d.pmi().bezuege == p.bezuege
    for text in ("NaN", "inf", "-0.01", ""):
        d.felder["wert"].setText(text)
        assert d.fehler()
    d.felder["wert"].setText("0,02")
    d.felder["bezuege"].setText("A B C D")
    assert d.fehler()
    d.felder["bezuege"].setText("A B C")
    assert not d.fehler()
    d.close()
    d = SemantikDialog(replace(p, typ=""), set, lambda f: None)
    assert d.typ.currentIndex() == -1 and d.fehler()
    d.close()


def test_dialog_prueft_projektionsursprung_hoehe_und_versatz(app):
    p = Pmi("toleranz", "Position", wert=.1, flaechen={4}, zone="Projected", zonen_wert=12.)
    d = SemantikDialog(p, lambda: {7}, lambda f: None)
    assert d.fehler()
    d._projektionsende_waehlen()
    assert not d.fehler()
    d.felder["zonen_wert"].setText("0")
    assert d.fehler()
    d.felder["zonen_wert"].setText("12,5")
    d.felder["projektionsversatz"].setText("1,25")
    neu = d.pmi()
    assert not d.fehler() and (neu.zonen_wert, neu.projektionsversatz, neu.projektionsflaechen) == (12.5, 1.25, [7])
    d.close()


def test_maximum_und_kugelzone_bleiben_eindeutig(app):
    p = Pmi("toleranz", "Position", wert=.1, material="M", maximum_toleranz=.4, flaechen={1},
            modifikatoren=["SphericalDiameter", "Free_State"])
    d = SemantikDialog(p, set, lambda f: None)
    form = d.felder["zonenform"]
    assert form.currentData() == "SphericalDiameter" and not d.fehler()
    assert d.pmi().maximum_toleranz == .4 and set(d.pmi().modifikatoren) == set(p.modifikatoren)
    d.felder["wert"].setText(".4")
    assert d.fehler()
    d.felder["wert"].setText(".1")
    d.felder["material"].setCurrentIndex(0)
    assert d.fehler()
    d.felder["maximum_toleranz"].clear()
    form.setCurrentIndex(form.findData("Diameter"))
    assert not d.fehler() and d.pmi().modifikatoren == ["Free_State", "Diameter"]
    d.close()


def test_geometrienennmass_folgt_flaechen_und_massart(app):
    p = Pmi("mass", "Size_Diameter", flaechen={1}, nennwert=10.)
    p.nennwert_aus_geometrie = True
    werte = {("Size_Diameter", 2): 24., ("Size_Radius", 2): 12.}
    d = SemantikDialog(p, lambda: {2}, lambda f: None,
                       geometriewert=lambda typ, ind: werte.get((typ, next(iter(ind)))))
    d._auswahl_uebernehmen()
    assert d.pmi().nennwert == 24.
    d.typ.setCurrentIndex(d.typ.findData("Size_Radius"))
    assert d.pmi().nennwert == 12.
    d.typ.setCurrentIndex(d.typ.findData("Size_Angular"))
    assert d.fehler() and d.pmi().nennwert is None
    d.close()
