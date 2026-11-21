"""Stirnradpaare aus Zielvorgaben bis zum gespeicherten Entwurf und STEP pruefen."""

import json
from math import inf, nan

import pytest
from PySide6 import QtCore, QtWidgets

from programm.kern.stirnradgeometrie import radpaarvorschlaege
from programm.ui.maschinenelemente_ui import AuslegungFenster
from programm.ui.stirnradziel_ui import StirnradzielDialog

_DIALOG_EXEC = QtWidgets.QDialog.exec


@pytest.mark.parametrize("i,z1,z2", [(2.5, 20, 50), (.4, 50, 20), (1., 35, 35)])
def test_exakter_achsabstand_und_uebersetzungsrichtung(i, z1, z2):
    paare = radpaarvorschlaege(i, 52.5, 0, 1.5, 20)
    p = paare[0]
    assert (p.i, p.z1, p.z2) == (i, z1, z2)
    assert all(p.a == 52.5 and p.epsilon >= 1 for p in paare)
    if i != 1:
        assert p.epsilon == pytest.approx(1.655756, abs=1e-6)


def test_fenster_grenzen_reihenfolge_und_geometrie():
    paare = radpaarvorschlaege(2.46, 52.9, .6, 1.5, 20)
    assert len(paare) == 12
    assert (paare[0].z1, paare[0].z2) == (20, 50)
    assert {p.a for p in paare} == {52.5, 53.25}
    fehler = [(abs(p.i-2.46), abs(p.a-52.9)) for p in paare]
    assert fehler == sorted(fehler)
    assert radpaarvorschlaege(2.5, 52.51, .01, 1.5, 20)[0].a == 52.5
    assert not radpaarvorschlaege(2.5, 52.51, .009, 1.5, 20)
    assert not radpaarvorschlaege(1, 8, 0, 1, 20)
    for werte in ((nan, 50, 0, 1, 20), (1, inf, 0, 1, 20), (1, 50, -1, 1, 20),
                  (1, 50, 1, 0, 20), (1, 50, 0, 1, 90), (1, 1000000, 100000, 1, 20)):
        with pytest.raises(ValueError):
            radpaarvorschlaege(*werte)


def test_vorschlag_pruefen_uebernehmen_speichern_und_exportieren(app, tmp_path, monkeypatch):
    from tests.test_stirnradgeometrie import _pruefe_datei
    monkeypatch.setattr(StirnradzielDialog, "exec", _DIALOG_EXEC)
    messung = dict(z1=18, z2=36, alpha=20., m=1.5, b1=8., b2=10.)
    f = AuslegungFenster(messwerte=messung, quelle="Messung")
    f.show()
    f.felder["t"].setText("12")
    d = StirnradzielDialog(f, dict(i=2.5, a=52.5, da=0, alpha=20., m=1.5))
    assert d.uebernehmen.isEnabled()
    d.felder["a"].setText("52,51")
    assert not d.uebernehmen.isEnabled() and d.tabelle.rowCount() == 0
    d._berechnen()
    assert not d.uebernehmen.isEnabled() and d.status.text()
    d.reject()
    urspruenglich = f.daten.copy()
    QtCore.QTimer.singleShot(0, lambda: app.activeModalWidget().reject())
    f.vorschlagen.click()
    assert f.daten == urspruenglich

    def waehlen():
        dialog = app.activeModalWidget()
        dialog.felder["i"].setText("0,4")
        dialog.felder["a"].setText("52,5")
        dialog._berechnen()
        dialog.uebernehmen.click()

    QtCore.QTimer.singleShot(0, waehlen)
    f.vorschlagen.click()
    assert f.daten["eingaben"] == dict(z1=50, z2=20, m=1.5, alpha=20, t=12.)
    assert f.daten["ergebnisse"]["ft"] == 320. and f.daten["ergebnisse"]["i"] == .4
    assert f.daten["auslegungsziel"] == dict(a=52.5, da=0, i=.4)
    assert f.messwerte == messung and f.daten["geometrie"] == dict(b1=8., b2=10.)
    pfad = tmp_path / "Entwurf.json"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a: (str(pfad), ""))
    f._speichern()
    assert json.loads(pfad.read_text()) == f.daten
    f.felder["z1"].setText("40")
    assert "+0.1" in f.ergebnis.text() and "-7.5" in f.ergebnis.text()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a: (str(pfad), ""))
    f._oeffnen()
    assert f.daten == json.loads(pfad.read_text())

    ziel = tmp_path / "Schnellgang.step"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a: (str(ziel), ""))
    f.step.click()
    assert f.paarauftrag.wait(60000)
    app.processEvents()
    _pruefe_datei(ziel, 50, 20, 1.5, 20, 8, 10)
    f.close()


def test_leerer_entwurf_zweite_variante_ohne_drehmoment(fenster, app, monkeypatch):
    from PySide6.QtTest import QSignalSpy
    monkeypatch.setattr(StirnradzielDialog, "exec", _DIALOG_EXEC)
    fenster.aktionen["maschinenelement"].trigger()
    f, = fenster.findChildren(AuslegungFenster)
    for k, v in (("b1", "8"), ("b2", "10")):
        f.breitenfelder[k].setText(v)

    def andere_variante():
        dialog = app.activeModalWidget()
        for k, v in dict(i="2,46", a="52,9", da="0,6", m="1,5").items():
            dialog.felder[k].setText(v)
        spy = QSignalSpy(dialog.tabelle.itemSelectionChanged)
        if spy.wait(3000):
            dialog.tabelle.selectRow(1)
            dialog.uebernehmen.click()
        else:
            dialog.reject()

    QtCore.QTimer.singleShot(0, andere_variante)
    f.vorschlagen.click()
    assert (f.felder["z1"].text(), f.felder["z2"].text()) == ("21", "50")
    assert f.step.isEnabled() and not f.speichern.isEnabled()
    assert f.stirnradziel == dict(i=2.46, a=52.9, da=.6)
