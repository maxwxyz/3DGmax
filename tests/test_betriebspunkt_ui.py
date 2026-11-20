"""Bedienung und Exporte eines Kegelraddifferentials mit zwei moeglichen Traegerachsen."""

import csv
import json

import numpy as np
import pytest
from pypdf import PdfReader
from PySide6 import QtCore

from programm.kern.verzahnung_sonder import Sonderprofil
from programm.ui.verzahnung_ui import VerzahnungFenster


def _kreuz():
    teile = []
    for name, n in (("Ost", [1,0,0]), ("West", [-1,0,0]), ("Oben", [0,0,1]), ("Unten", [0,0,-1])):
        n = np.array(n, float)
        teile.append(Sonderprofil(name, "konisch", 20, 12 * n, n, 4., (13., 17.), (11., 15.), 0.))
    return teile


def _vorgabe(seite, welle, n):
    an, feld = seite.eingaben[welle]
    an.setChecked(True)
    feld.setValue(n)


def test_mehrdeutige_traegerachse_und_betriebsgrenzen(tmp_path, app):
    f = VerzahnungFenster(_kreuz(), str(tmp_path / "Differential"))
    seite = f.betriebspunkt
    assert f.reiter.isTabVisible(f.reiter.indexOf(seite))
    wahl = seite.varianten[0]
    assert wahl.count() == 3 and not seite.ergebnis["saetze"] and seite.daten()["differentialachsen"][0]["auswahl"] is None
    wahl.setCurrentIndex(1)
    a, b, steg = seite.ergebnis["saetze"][0]["wellen"]
    _vorgabe(seite, steg, 120)
    assert seite.ergebnis["wellen"][0]["status"] == "frei"
    _vorgabe(seite, a, -20)
    werte = {w["id"]: w["drehzahl"] for w in seite.ergebnis["wellen"]}
    assert werte[b] == pytest.approx(260)
    item = next(seite.kupplungen.item(i) for i in range(seite.kupplungen.count())
                if set(seite.kupplungen.item(i).data(QtCore.Qt.ItemDataRole.UserRole)) == {a, b})
    item.setCheckState(QtCore.Qt.CheckState.Checked)
    assert all(w["status"] == "widerspruch" and w["drehzahl"] is None for w in seite.ergebnis["wellen"])
    seite.eingaben[a][0].setChecked(False)
    assert all(w["drehzahl"] == pytest.approx(120) for w in seite.ergebnis["wellen"])
    wahl.setCurrentIndex(2)
    assert not seite.ergebnis["kupplungen"] and all(w["vorgabe"] is None for w in seite.ergebnis["wellen"])
    wahl.setCurrentIndex(1)
    assert seite.ergebnis["kupplungen"] and all(w["drehzahl"] == pytest.approx(120) for w in seite.ergebnis["wellen"])
    f.speichere("json", str(tmp_path / "daten.json"))
    export = json.loads((tmp_path / "daten.json").read_text())
    assert export["differentialgruppen"][0]["achswahl"] == 0
    daten = export["betriebspunkt"]
    assert {w["rollen"][0] for w in daten["wellen"]} == {"seitenrad_a", "seitenrad_b", "steg"}
    assert daten["differentialachsen"][0]["auswahl"] == 0 and daten["kupplungen"] == [[min(a,b), max(a,b)]]
    assert daten["wellen"][0]["positive_achse"] == daten["wellen"][1]["positive_achse"]
    f.speichere("csv", str(tmp_path / "daten.csv"))
    with (tmp_path / "daten.csv").open(encoding="utf-8-sig") as datei:
        zeilen = list(csv.reader(datei, delimiter=";"))
    assert ["Betriebspunkt"] in zeilen and any(z and z[0] == "Drehfeste Kopplung" for z in zeilen)
    assert any(len(z) == 5 and z[1:4] == ["120", "120", "bestimmt"] for z in zeilen)
    bericht = PdfReader(f.speichere("pdf", str(tmp_path / "daten.pdf")))
    seiten = [s.extract_text().replace("\t", " ") for s in bericht.pages]
    assert any("Betriebspunkt" in s and "Drehfeste Kopplung" in s and "120" in s for s in seiten)
    f.close()


def test_planetenrollen_bei_unbenannten_bauteilen(app):
    from tests.test_getriebe_betrieb import _planetensatz
    raeder = _planetensatz("A", 18)
    for i, rad in enumerate(raeder):
        rad.teil = f"STL [{i+1}]"
    f = VerzahnungFenster(raeder, "")
    seite = f.betriebspunkt
    a, b, steg = seite.betrieb.saetze[0]["wellen"]
    assert "Sonne" in seite._wellenname(a) and "Hohlrad" in seite._wellenname(b)
    assert "Steg" in seite._wellenname(steg)
    _vorgabe(seite, a, 1200)
    _vorgabe(seite, b, 0)
    werte = {w["id"]: w for w in seite.daten()["wellen"]}
    assert werte[steg]["drehzahl"] == pytest.approx(300) and werte[steg]["rollen"] == ["steg"]
    f.close()


def test_rueckkehrender_stirnradzug_getrennte_wellen(app, tmp_path):
    from tests.test_getriebezug import _rad
    rad = [_rad("Eingang", 16, 0), _rad("Zwischenrad", 32, 24),
           _rad("Zwischenritzel", 12, 24, 12), _rad("Ausgang", 36, 0, 12)]
    f = VerzahnungFenster(rad, "")
    seite = f.betriebspunkt
    assert not seite.wellentrennung.isHidden() and len(seite.eingaben) == 2
    _vorgabe(seite, seite.modell.welle[0], 900)
    seite.wellentrennung.setChecked(True)
    assert len(seite.eingaben) == 4
    assert all(w["vorgabe"] is None for w in seite.daten()["wellen"])
    ein, m1, m2, aus = [seite.modell.welle[i] for i in range(4)]
    _vorgabe(seite, ein, 1200)
    item = next(seite.kupplungen.item(i) for i in range(seite.kupplungen.count())
                if set(seite.kupplungen.item(i).data(QtCore.Qt.ItemDataRole.UserRole)) == {m1, m2})
    item.setCheckState(QtCore.Qt.CheckState.Checked)
    pfad = tmp_path / "wellen.json"
    f.speichere("json", str(pfad))
    export = json.loads(pfad.read_text())["betriebspunkt"]
    werte = {w["id"]: w["drehzahl"] for w in export["wellen"]}
    assert export["getrennte_wellen"] and [werte[i] for i in (ein,m1,m2,aus)] == pytest.approx([1200,-600,-600,200])
    assert len(export["kupplungen"]) == 1
    csvpfad = f.speichere("csv", str(tmp_path / "wellen.csv"))
    with open(csvpfad, encoding="utf-8-sig") as datei:
        assert ["Wellenzuordnung im Betriebspunkt", "Getrennte Wellen mit einzeln gewählten Kopplungen"] in list(
            csv.reader(datei, delimiter=";"))
    pdf = PdfReader(f.speichere("pdf", str(tmp_path / "wellen.pdf")))
    assert any("Getrennte Wellen" in s.extract_text() and "200" in s.extract_text() for s in pdf.pages)
    seite.wellentrennung.setChecked(False)
    assert not seite.daten()["getrennte_wellen"] and not seite.daten()["kupplungen"]
    assert all(w["vorgabe"] is None for w in seite.daten()["wellen"])
    seite.wellentrennung.setChecked(True)
    assert not seite.daten()["kupplungen"] and all(w["vorgabe"] is None for w in seite.daten()["wellen"])
    f.close()
