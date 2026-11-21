"""Abbruch, Auftragswechsel und Fensterende zwischen nativer Rechnung und Qt-Zustellung."""

from threading import Event
import time

import pytest
from PySide6 import QtCore
from shiboken6 import isValid

from programm.ui.lader import Lader
from programm.ui.panels import VorschauLader
from programm.ui.vergleich_ui import VergleichsLader
from programm.ui.verzahnung_ui import VerzahnungLader


def zustellen(app):
    app.processEvents()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("alter_vergleich", [False, True])
def test_ersetzter_auftrag_hat_keinen_zugriff_auf_fenster(
        app, fenster, monkeypatch, keine_modalen_dialoge, alter_vergleich):
    alt = VergleichsLader if alter_vergleich else Lader
    neu = Lader if alter_vergleich else VergleichsLader
    freigabe = Event()
    uebernommen = []

    def schon_fertig(lader):
        lader.stand.emit("Alter Stand")
        lader.fehler.emit("Alter Fehler")
        lader.fertig.emit("Altes Ergebnis")

    def noch_aktiv(lader):
        freigabe.wait(5)
        lader.fertig.emit("Neues Ergebnis")

    monkeypatch.setattr(alt, "run", schon_fertig)
    monkeypatch.setattr(neu, "run", noch_aktiv)
    monkeypatch.setattr(fenster, "zeige_ergebnis", uebernommen.append)
    monkeypatch.setattr(fenster, "zeige_vergleich", uebernommen.append)
    monkeypatch.setattr(fenster, "_projekt_messungen", lambda *_: uebernommen.append("Altes Projekt"))
    start = lambda **kw: fenster.starte_vergleich({}, **kw)
    laden = lambda **kw: fenster.lade("neu.stp", **kw)
    zuerst, zuletzt = (start, laden) if alter_vergleich else (laden, start)
    zuerst(projekt={"typ": "modell"}, danach=lambda: uebernommen.append("Altes Beispiel"))
    erster = fenster._lader
    assert erster.wait(5000)  # Fertig, alle UI-Signale sind noch in der Warteschlange.
    zuletzt(danach=lambda: uebernommen.append("Neues Beispiel"))
    zweiter = fenster._lader
    try:
        status = fenster.statusBar().currentMessage()
        zustellen(app)
        assert fenster._lader is zweiter and fenster.statusBar().currentMessage() == status
        assert not isValid(erster)
        assert not uebernommen and not keine_modalen_dialoge
        assert not fenster.fortschritt.isHidden()
    finally:
        freigabe.set()
        assert zweiter.wait(5000)
    zustellen(app)
    assert uebernommen == ["Neues Ergebnis", "Neues Beispiel"]
    assert fenster._lader is None and fenster.fortschritt.isHidden() and not isValid(zweiter)


def test_schliessen_mit_zwei_laufenden_auftraegen(app, fenster, monkeypatch, keine_modalen_dialoge):
    freigabe = Event()
    uebernommen = []

    def native_phase(lader):
        freigabe.wait(5)
        lader.stand.emit("Verspaeteter Stand")
        lader.fertig.emit("Verspaetetes Ergebnis")
        lader.fehler.emit("Verspaeteter Fehler")

    monkeypatch.setattr(Lader, "run", native_phase)
    monkeypatch.setattr(VergleichsLader, "run", native_phase)
    monkeypatch.setattr(fenster, "zeige_ergebnis", uebernommen.append)
    monkeypatch.setattr(fenster, "zeige_vergleich", uebernommen.append)
    fenster.lade("alt.step")
    erster = fenster._lader
    fenster.starte_vergleich({})
    zweiter = fenster._lader
    try:
        assert fenster.close()
        assert erster.abgebrochen and zweiter.abgebrochen
        assert erster.isRunning() and zweiter.isRunning()
        assert erster.parent() is app and zweiter.parent() is app
    finally:
        freigabe.set()
        assert erster.wait(5000) and zweiter.wait(5000)
    zustellen(app)
    assert fenster.statusBar().currentMessage() != "Verspaeteter Stand"
    assert not uebernommen and not keine_modalen_dialoge
    assert not isValid(erster) and not isValid(zweiter)


def test_modell_schliessen_verwirft_ausstehendes_ergebnis(app, fenster, monkeypatch):
    uebernommen = []
    monkeypatch.setattr(Lader, "run", lambda l: l.fertig.emit("Altes Ergebnis"))
    monkeypatch.setattr(fenster, "zeige_ergebnis", uebernommen.append)
    fenster.lade("alt.step")
    assert fenster._lader.wait(5000)
    fenster.schliesse_modell()
    zustellen(app)
    assert not uebernommen and fenster.erg is None


def test_aktueller_ladefehler_wird_angezeigt(app, fenster, monkeypatch, keine_modalen_dialoge):
    monkeypatch.setattr(VergleichsLader, "run", lambda l: l.fehler.emit("Datei fehlt"))
    fenster.starte_vergleich({}, warten=True)
    zustellen(app)
    assert keine_modalen_dialoge == ["Datei fehlt"]
    assert fenster._lader is None and fenster.fortschritt.isHidden()


def test_programmende_wartet_auf_native_rechnung(app, fenster, monkeypatch):
    kontrolliert = Event()

    def native_phase(lader):
        frist = time.monotonic() + 5
        while not lader.abgebrochen and time.monotonic() < frist:
            time.sleep(0.005)
        kontrolliert.set()

    monkeypatch.setattr(Lader, "run", native_phase)
    fenster.lade("gross.stp")
    lader = fenster._lader
    app.aboutToQuit.emit()
    assert lader.abgebrochen and kontrolliert.is_set() and lader.isFinished()
    fenster.lade_abbrechen()
    zustellen(app)
    assert not isValid(lader)


def test_vorschau_gleiche_blickrichtung_mit_eigenen_pmi(app, monkeypatch):
    from types import SimpleNamespace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from programm.kern import zeichnung
    from programm.kern.ansichten import Ansicht

    ansichten = [Ansicht("A", 1), Ansicht("B", 2, oben=(1, 0, 0)), Ansicht("C", 3)]
    grafik = SimpleNamespace(linien=[[(0, 0, 0), (2, 1, 0)]], dreiecke=[], platzhalter=[])
    form = BRepPrimAPI_MakeBox(10, 9, 8).Shape()
    lader = VorschauLader(form, ansichten, [[], [], [grafik]], {})
    echt = zeichnung.projiziere
    aufrufe = []

    def zaehle(form, richtung, oben, **kwargs):
        aufrufe.append((richtung, oben))
        return echt(form, richtung, oben, **kwargs)

    monkeypatch.setattr(zeichnung, "projiziere", zaehle)
    bilder = {}
    lader.fertig.connect(lambda i, svg: bilder.update({i: svg}))
    lader.run()
    assert len(aufrufe) == 2 and set(bilder) == {0, 1, 2}
    for i, a in enumerate(ansichten):
        z = echt(form, a.richtung, a.oben, a.name, verdeckt=False, abweichung=0.5, schnell=True)
        zeichnung.pmi_hinzu(z, lader.grafik_je_ansicht[i], {}, a.richtung, a.oben)
        assert bilder[i] == zeichnung.als_svg([z], a.name)
    bilder.clear()
    aufrufe.clear()
    lader.fertig.connect(lambda *_: setattr(lader, "abgebrochen", True))
    lader.run()
    assert set(bilder) == {0} and len(aufrufe) == 1


def test_fenster_schliessen_waehrend_ansichtenprojektion(app, fenster, monkeypatch):
    from tests.conftest import pfad

    freigabe = Event()
    bilder = []

    def projiziere(lader):
        freigabe.wait(5)
        lader.fertig.emit(0, "Alte Vorschau")

    monkeypatch.setattr(VorschauLader, "run", projiziere)
    monkeypatch.setattr(fenster.ansichten, "setze_vorschau", lambda *_: bilder.append(1))
    fenster.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    lader = fenster._vorschau
    try:
        assert fenster.close()
        assert lader.abgebrochen and lader.isRunning()
    finally:
        freigabe.set()
        assert lader.wait(5000)
    zustellen(app)
    assert not bilder and fenster._vorschau is None and not isValid(lader)


@pytest.mark.parametrize("wechsel", ["erneut", "laden", "zeigen"])
def test_verzahnungsanalyse_verwirft_ausstehende_signale(
        app, fenster_ctc01, monkeypatch, keine_modalen_dialoge, wechsel):
    from dataclasses import replace

    f = fenster_ctc01
    fortschritt = []
    monkeypatch.setattr(f, "_prozent", fortschritt.append)

    def verspaetet(lader):
        lader.stand.emit(34)
        lader.fehler.emit("Alter Fehler")
        lader.fertig.emit([])

    monkeypatch.setattr(VerzahnungLader, "run", verspaetet)
    alt = f.erkenne_verzahnung()
    assert alt.wait(5000)
    if wechsel == "erneut":
        monkeypatch.setattr(VerzahnungLader, "run", lambda l: l.stand.emit(75))
        neu = f.erkenne_verzahnung(alle_sichtbaren=True)
        assert neu.wait(5000)
    elif wechsel == "laden":
        f.lade(f.erg.pfad, warten=True)
    else:
        f.zeige_ergebnis(replace(f.erg))
    zustellen(app)
    assert fortschritt == ([75] if wechsel == "erneut" else [])
    assert not keine_modalen_dialoge and getattr(f, "_verzahnung", None) is None
    assert f._verzahnung_lader is None and not f._aufgaben
    assert not isValid(alt)


def test_fenster_waehrend_getriebeanalyse_loeschen(app, tmp_path, monkeypatch, keine_modalen_dialoge):
    from programm.ui.hauptfenster import Hauptfenster
    from tests.conftest import pfad

    freigabe = Event()

    def analysiere(lader):
        freigabe.wait(5)
        lader.stand.emit(100)
        lader.fehler.emit("Verworfener Fehler")
        lader.fertig.emit([])

    monkeypatch.setattr(VerzahnungLader, "run", analysiere)
    monkeypatch.setenv("DG_EINSTELLUNGEN", str(tmp_path / "einstellungen.ini"))
    f = Hauptfenster()
    f.show()
    f.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    arbeit = f.erkenne_verzahnung(alle_sichtbaren=True)
    try:
        f.close()
        assert arbeit.abgebrochen and arbeit.isRunning() and arbeit.parent() is app
        f.deleteLater()
        zustellen(app)
        assert not isValid(f) and arbeit.isRunning()
    finally:
        freigabe.set()
        assert arbeit.wait(5000)
    zustellen(app)
    assert not keine_modalen_dialoge and not isValid(arbeit)
