"""Stresstest: alle Aktionen ohne und mit Modell ausloesen (blockierende Dialoge werden ersetzt)."""

from PySide6 import QtWidgets


def _ohne_dialoge(monkeypatch):
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a, **k: None)
    from programm.ui import hilfe
    monkeypatch.setattr(hilfe.Einfuehrung, "exec", lambda self: 0)


def _alle(fenster):
    for name, a in list(fenster.aktionen.items()):
        if name in ("beenden",):
            continue
        if a.isEnabled():
            a.trigger()
            QtWidgets.QApplication.processEvents()
    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QDialog):
            w.close()


def test_alle_aktionen_ohne_modell(fenster, monkeypatch):
    _ohne_dialoge(monkeypatch)
    _alle(fenster)
    assert fenster.erg is None


def test_alle_aktionen_mit_modell(fenster_ctc01, monkeypatch):
    _ohne_dialoge(monkeypatch)
    f = fenster_ctc01
    for name, a in list(f.aktionen.items()):
        if name in ("beenden", "schliessen"):
            continue
        if a.isEnabled():
            a.trigger()
            QtWidgets.QApplication.processEvents()
    for z in range(f.ansichten.liste.count()):
        f.ansichten.liste.setCurrentRow(z)
    for z in range(f.pmi.tabelle.rowCount()):
        f.pmi.tabelle.selectRow(z)
    f.aktionen["schliessen"].trigger()
    assert f.erg is None
    assert not f.aktionen["alles"].isEnabled()


def test_erster_start_zeigt_einfuehrung(fenster, monkeypatch):
    _ohne_dialoge(monkeypatch)
    gezeigt = []
    monkeypatch.setattr(fenster, "zeige_einfuehrung", lambda: gezeigt.append(1))
    fenster.erster_start()
    fenster.erster_start()
    assert gezeigt == [1]
