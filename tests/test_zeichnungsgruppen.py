"""Gruppenpruefung ueber Blattgrenzen und Vergleich mit expliziten STEP-Partnern."""

import csv
from dataclasses import replace

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern import zeichnungsabgleich as za
from tests.test_simultane_toleranzen import _kopie

_DIALOG_EXEC = QtWidgets.QDialog.exec


def test_bestaetigte_gruppe_braucht_eindeutige_zuordnung_und_bezugsbasis():
    text = "⌓ | .070 | A | B | C"
    muster = za.lese_angabe(text, 25.4)
    modelle = [replace(muster, step_id=n, simultan_mit=ids) for n, ids in [(1, [2]), (2, [1, 3]), (3, [2])]]
    a, b, c = zeilen = [za.Blattangabe(i, (0, 0, .3, .1), text+"\nSIM REQT 1", modell=m)
                        for i, m in enumerate(modelle)]
    def pruefung():
        return [za.befund(z, 25.4, za.gruppenbefunde(zeilen, modelle, 25.4).get(z)) for z in zeilen]

    za.setze_blattgruppe([a, b], True)
    assert pruefung() == ["offen"] * 3  # Auch c traegt die eindeutige gedruckte Kennung.
    za.setze_blattgruppe(zeilen, False)
    assert pruefung() == ["offen"] * 3
    za.setze_blattgruppe(zeilen, True)
    assert pruefung() == ["gleich"] * 3
    c.modell = b.modell
    assert pruefung() == ["offen"] * 3
    c.modell = None
    assert pruefung() == ["offen"] * 3
    c.nur_zeichnung = True
    assert pruefung() == ["geaendert", "geaendert", "zeichnung"]
    c.nur_zeichnung, c.modell = False, modelle[2]
    c.zielkonflikt = True
    assert pruefung() == ["offen"] * 3
    c.zielkonflikt = False
    c.modell.simultan_offen = [999]
    assert pruefung() == ["offen"] * 3
    c.modell.simultan_offen = []
    c.text = text+"\nSIM REQT 2"
    assert pruefung() == ["offen"] * 3
    za.setze_blattgruppe([b, a], True)
    assert pruefung() == ["geaendert", "geaendert", "offen"]
    assert c.simultan is None
    za.loese_blattgruppen([a])
    assert a.simultan is None and b.simultan is None


def test_nur_bestaetigte_gruppe_vergleicht_geltung_und_wert_getrennt():
    p = za.lese_angabe("⌓ | .03", 1.)
    m = replace(p, step_id=1)
    a = za.Blattangabe(0, (0, 0, .5, .1), "⌓ | .03", modell=m)
    za.setze_blattgruppe([a], True)
    def befund():
        return za.befund(a, 1., za.gruppenbefunde([a], [m], 1.)[a])
    assert befund() == "gleich"
    a.text += "\nSIM REQT 1"
    assert befund() == "offen"
    a.text = "⌓ | .04\nSIM REQT 1"
    assert befund() == "geaendert"
    a.text = "⌓ | .03"
    m.simultan_mit = [123]
    assert befund() == "offen"
    m.simultan_mit = []
    m.beschreibung = "SIM REQT EXTRA"
    assert befund() == "offen"


def test_gleiche_kennungen_in_getrennt_geprueften_ansichten():
    text = "⌓ | .03\nSIM REQT 2"
    p = za.lese_angabe("⌓ | .03", 1.)
    modelle = [replace(p, step_id=n, simultan_mit=[partner]) for n, partner in [(1,2), (2,1), (3,4), (4,3)]]
    zeilen = [za.Blattangabe(i // 2, (0, i/10, .4, i/10+.1), text, modell=m) for i,m in enumerate(modelle)]
    za.setze_blattgruppe(zeilen[:2], True)
    assert za.gruppenbefunde(zeilen, modelle, 1.)[zeilen[0]].grund == "kennung"
    za.setze_blattgruppe(zeilen[2:], True)
    assert all(b.status == "gleich" for b in za.gruppenbefunde(zeilen, modelle, 1.).values())
    offen = replace(p, step_id=-1)
    zeilen[1].modell = offen
    befund = za.gruppenbefunde(zeilen, [*modelle, offen], 1.)[zeilen[0]]
    assert befund.grund == "zuordnung" and befund.blatt_ids == {1}


@pytest.mark.parametrize("kennung,partner,befund,soll", [
    ("1", [], "gleich", "#14614, #15076"),
    ("", [], "gleich", "#14614, #15076"),
    ("1", [(14614, 14472)], "geaendert", "#14472, #14614, #15076"),
])
def test_zwei_pdf_blaetter_gegen_ftc07_step(fenster, tmp_path, monkeypatch, kennung, partner, befund, soll):
    quelle = _kopie(tmp_path/"Gruppe.stp", [(14614, 15076), *partner])
    fenster.lade(quelle, warten=True)
    pfad = tmp_path/"Gruppe.pdf"
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    maler = QtGui.QPainter(pdf)
    maler.setFont(QtGui.QFont("Helvetica", 14))
    for seite in range(2):
        if seite:
            pdf.newPage()
        maler.drawText(90, 80, "⌓ | .070 | A | B | C")
        maler.drawText(90, 102, ("SIM REQT " + kennung).strip())
    maler.end()
    ausgabe = tmp_path/"Abgleich.csv"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args: (str(pfad), "PDF"))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ausgabe), "CSV"))
    fenster.aktionen["zeichnungsabgleich"].trigger()
    d = fenster.zeichnungsabgleich
    def gruppendialog():
        markiert = []
        def bestaetigen():
            dialog = QtWidgets.QApplication.activeModalWidget()
            liste = dialog.findChild(QtWidgets.QListWidget)
            for i in range(liste.count()):
                item = liste.item(i)
                markiert.append(item.checkState() == QtCore.Qt.CheckState.Checked)
                item.setCheckState(QtCore.Qt.CheckState.Checked)
            dialog.findChild(QtWidgets.QDialogButtonBox).button(QtWidgets.QDialogButtonBox.StandardButton.Ok).click()
        QtCore.QTimer.singleShot(0, bestaetigen)
        with monkeypatch.context() as mp:
            mp.setattr(QtWidgets.QDialog, "exec", _DIALOG_EXEC)
            d.gruppenknopf.click()
        return markiert

    try:
        d.einheit.setCurrentIndex(2)
        zeilen = []
        for nr, sid in enumerate([14614, 15076]):
            d.seite.setValue(nr+1)
            a, = [z for z in d.seiten[nr] if "|" in z.text]
            assert za.gruppenkennung(a.text) == kennung
            zeilen.append(a)
            d.waehle(a)
            m = next(m for m in d.modell if m.step_id == sid)
            d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(m)]))
            d.bestaetigen.click()
            assert d._befund(a) == "offen"
            assert d.aktiv is a and d.gruppenknopf.isEnabled()
            assert gruppendialog() == ([True] if nr == 0 else [bool(kennung), True])
        assert all(d._befund(a) == befund for a in zeilen)
        assert "#14614, #15076" in d.detail.text()
        d._export()
        with ausgabe.open(encoding="utf-8-sig") as f:
            treffer = [z for z in csv.DictReader(f, delimiter=";") if z["Befund der Toleranzgruppe"]]
        assert [z["Blatt"] for z in treffer] == ["1", "2"]
        for z in treffer:
            assert z["Befund"] == d._befunde()[befund]
            assert z["Befund der Toleranzgruppe"] == d._gruppentext(d.gruppen[a])
            assert z["Quell-IDs der Modellgruppe"] == soll
            assert z["Der Blattgruppe zugeordnete Quell-IDs"] == "#14614, #15076"
            assert " | 2: " in z["Toleranzgruppe auf der Zeichnung (Blatt und Bereich)"]
        d.text.setPlainText("⌓ | .060 | A | B | C")
        d.bestaetigen.click()
        assert all(a.simultan is None for a in zeilen)
    finally:
        d.close()
