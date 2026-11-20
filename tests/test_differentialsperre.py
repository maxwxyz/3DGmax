"""Explizite Sperrmodelle, passive Momentenhuelle und Exporte am symmetrischen Differential."""

import csv
import json

import pytest
from pypdf import PdfReader

from programm.kern.differentialsperre import Sperrvorgabe
from programm.kern.getriebe_betrieb import Betriebsmodell
from programm.ui.verzahnung_ui import VerzahnungFenster
from tests.test_betriebspunkt_ui import _kreuz, _vorgabe
from tests.test_schraegraddifferential import schraegraeder  # noqa: F401 - STL-Modell als Fixture


def _betrieb():
    modell = Betriebsmodell(_kreuz(), [])
    b = modell.betrieb({0: 0})
    return b, b.saetze[0]["wellen"]


def test_formschlusssperre_und_ideales_offenes_differential():
    b, (a, rechts, steg) = _betrieb()
    offen = b.auswerten({steg: 300}, [], sperren={steg: Sperrvorgabe("offen", 400)})
    assert offen["differentialsperren"][0]["seitenmomente_a_b"] == [[200, 200], [200, 200]]
    assert all(w["drehzahl"] is None for w in offen["wellen"] if w["id"] != steg)
    lock = {steg: Sperrvorgabe("gesperrt", 400)}
    zu = b.auswerten({a: -300}, [], sperren=lock)
    assert all(w["drehzahl"] == -300 for w in zu["wellen"])
    assert zu["differentialsperren"][0]["status"] == "lastabhaengig"
    konflikt = b.auswerten({a: 200, rechts: 201}, [], sperren=lock)
    assert all(w["status"] == "widerspruch" for w in konflikt["wellen"])
    assert konflikt["differentialsperren"][0]["status"] == "drehzahlwiderspruch"


@pytest.mark.parametrize("tbr,moment,grenzen", [(1, 400, [200,200]), (3, 400, [100,300]),
                                               (2, 0, [0,0]), (2, None, None)])
def test_tbr_begrenzt_momente_und_erlaubt_unterschiedliche_drehzahlen(tbr, moment, grenzen):
    b, (a, rechts, steg) = _betrieb()
    konfig = {steg: Sperrvorgabe("tbr", moment, tbr)}
    ergebnis = b.auswerten({steg: 80, a: 60}, [], sperren=konfig)
    assert next(w["drehzahl"] for w in ergebnis["wellen"] if w["id"] == rechts) == 100
    fall, = ergebnis["differentialsperren"]
    if grenzen is None:
        assert fall["seitenmomente_a_b"] is None
    else:
        assert fall["seitenmomente_a_b"] == [[moment / 2, grenzen[1]], [grenzen[0], moment / 2]]
        ruhe = b.auswerten({}, [], sperren=konfig)["differentialsperren"][0]
        assert ruhe["seitenmomente_a_b"] == [grenzen, grenzen]
        rueckwaerts = b.auswerten({steg: -80, a: -100}, [], sperren=konfig)["differentialsperren"][0]
        assert rueckwaerts["seitenmomente_a_b"] == [[grenzen[0], moment / 2], [moment / 2, grenzen[1]]]
    assert fall["quelle"].startswith("https://torsen.com/")
    bei_kopplung = b.auswerten({}, [(a, rechts)], sperren=konfig)["differentialsperren"][0]
    assert bei_kopplung["status"] == "lastabhaengig" and bei_kopplung["seitenmomente_a_b"] is None


def test_eingabebereich_und_ungewaehlte_achse():
    for args in [("tbr", 400, .9), ("tbr", 100, float("nan")), ("offen", -100), ("gesperrt", None, 3)]:
        with pytest.raises(ValueError):
            Sperrvorgabe(*args)
    b = Betriebsmodell(_kreuz(), []).betrieb({})
    with pytest.raises(ValueError):
        b.auswerten({}, [], sperren={3: Sperrvorgabe("gesperrt")})


def test_editor_export_und_wechselseitige_achsvarianten(app, tmp_path):
    f = VerzahnungFenster(_kreuz(), "")
    seite = f.betriebspunkt
    editor = seite.sperren
    assert editor.isHidden()
    achse = seite.varianten[0]
    achse.setCurrentIndex(1)
    assert not editor.isHidden() and editor.modell.currentData() == "offen"
    a, rechts, steg = seite.betrieb.saetze[0]["wellen"]
    _vorgabe(seite, steg, 80)
    _vorgabe(seite, a, 60)
    editor.modell.setCurrentIndex(editor.modell.findData("gesperrt"))
    assert seite.ergebnis["wellen"][0]["status"] == "widerspruch"
    editor.modell.setCurrentIndex(editor.modell.findData("tbr"))
    editor.nutze_moment.setChecked(True)
    editor.moment.setValue(400)
    editor.tbr.setValue(3)
    assert "A 200 bis 300 Nm, B 100 bis 200 Nm" in editor.text.text()
    achse.setCurrentIndex(2)
    assert editor.modell.currentData() == "offen" and not editor.nutze_moment.isChecked()
    achse.setCurrentIndex(1)
    assert editor.modell.currentData() == "tbr" and editor.moment.value() == 400
    f.speichere("json", str(tmp_path / "sperre.json"))
    fall, = json.loads((tmp_path / "sperre.json").read_text())["betriebspunkt"]["differentialsperren"]
    assert fall["modell"] == "tbr" and fall["tbr"] == 3 and fall["seitenmomente_a_b"] == [[200,300], [100,200]]
    with open(f.speichere("csv", str(tmp_path / "sperre.csv")), encoding="utf-8-sig") as datei:
        assert ["Seitenmomente", "A 200 bis 300 Nm, B 100 bis 200 Nm, zusammen 400 Nm"] in list(csv.reader(datei, delimiter=";"))
    seiten = [s.extract_text() for s in PdfReader(f.speichere("pdf", str(tmp_path / "sperre.pdf"))).pages]
    assert any("Teilgesperrt" in s and "200 bis 300 Nm" in s and "ohne Vorspannung" in s for s in seiten)
    f.close()


def test_stl_schraegverzahnung_mit_nutzerdefinierter_sperre(schraegraeder, app):
    f = VerzahnungFenster(schraegraeder, "")
    seite = f.betriebspunkt
    editor = seite.sperren
    assert not seite.varianten and not editor.isHidden()
    a, b, steg = seite.betrieb.saetze[0]["wellen"]
    _vorgabe(seite, steg, 350.)
    editor.modell.setCurrentIndex(editor.modell.findData("gesperrt"))
    assert all(w["drehzahl"] == 350 for w in seite.ergebnis["wellen"])
    editor.modell.setCurrentIndex(editor.modell.findData("tbr"))
    editor.nutze_moment.setChecked(True)
    editor.moment.setValue(500.)
    editor.tbr.setValue(4.)
    fall, = seite.ergebnis["differentialsperren"]
    assert fall["wellen_a_b_steg"] == [a, b, steg] and fall["seitenmomente_a_b"] == [[100,400], [100,400]]
    assert all(w["status"] == "frei" for w in seite.ergebnis["wellen"] if w["id"] != steg)
    f.close()


@pytest.mark.parametrize("mk,mc,gesamt", [(40, 200, [60,140]), (200, 100, [0,100]),
                                          (0, 200, [100,100]), (40, 0, [0,0])])
def test_lamellenkupplung_rechnet_kapazitaet_je_seite(mk, mc, gesamt):
    b, (a, rechts, steg) = _betrieb()
    konfig = {steg: Sperrvorgabe("lamelle", mc, kupplungsmoment_max=mk)}
    def berechne(drehzahlen):
        return b.auswerten(drehzahlen, [], sperren=konfig)["differentialsperren"][0]
    assert berechne({})["seitenmomente_a_b"] == [gesamt, gesamt]
    assert berechne({steg: 80, a: 60})["seitenmomente_a_b"] == [[mc/2, gesamt[1]], [gesamt[0], mc/2]]
    assert berechne({steg: -80, a: -100})["seitenmomente_a_b"] == [[gesamt[0], mc/2], [mc/2, gesamt[1]]]
    assert berechne({a: 90, rechts: 90})["seitenmomente_a_b"] == [gesamt, gesamt]
    assert berechne({})["kupplungsmoment_max"] == mk


def test_lamellenkapazitaet_wird_nicht_automatisch_angenommen():
    b, (_, _, steg) = _betrieb()
    fall, = b.auswerten({}, [], sperren={steg: Sperrvorgabe("lamelle", 200)})["differentialsperren"]
    assert fall["status"] == "kupplungsmoment_fehlt" and fall["seitenmomente_a_b"] is None
    for art, mk in [("offen", 4), ("lamelle", -1), ("lamelle", float("inf"))]:
        with pytest.raises(ValueError):
            Sperrvorgabe(art, 200, kupplungsmoment_max=mk)


def test_lamellenmodell_ueber_ui_csv_json_pdf(app, tmp_path):
    f = VerzahnungFenster(_kreuz(), "")
    seite = f.betriebspunkt
    seite.varianten[0].setCurrentIndex(1)
    editor = seite.sperren
    editor.modell.setCurrentIndex(editor.modell.findData("lamelle"))
    editor.nutze_moment.setChecked(True)
    editor.moment.setValue(200)
    assert "Maximales Kupplungsmoment" in editor.text.text()
    editor.lamelle.setValue(40)
    a, _, steg = seite.betrieb.saetze[0]["wellen"]
    _vorgabe(seite, steg, 80)
    _vorgabe(seite, a, 60)
    assert "A 100 bis 140 Nm, B 60 bis 100 Nm" in editor.text.text()
    f.speichere("json", str(tmp_path / "lamelle.json"))
    fall, = json.loads((tmp_path / "lamelle.json").read_text())["betriebspunkt"]["differentialsperren"]
    assert (fall["modell"], fall["kupplungsmoment_max"], fall["tbr"]) == ("lamelle", 40, None)
    assert "ohne_vorspannung" not in fall["bedingungen"] and "kupplung_zwischen_seitenraedern" in fall["bedingungen"]
    with open(f.speichere("csv", str(tmp_path / "lamelle.csv")), encoding="utf-8-sig") as datei:
        assert ["Maximales Kupplungsmoment A–B", "40 Nm"] in list(csv.reader(datei, delimiter=";"))
    seiten = [s.extract_text() for s in PdfReader(f.speichere("pdf", str(tmp_path / "lamelle.pdf"))).pages]
    assert any("Lamellenkupplung" in s and "100 bis 140 Nm" in s and "40 Nm" in s for s in seiten)
    f.close()
