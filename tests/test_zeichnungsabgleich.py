import csv
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern import zeichnungsabgleich as za
from programm.kern.pmi import BezugsRef, Pmi


def _zeichnung(pfad):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    p = QtGui.QPainter(pdf)
    p.setFont(QtGui.QFont("Helvetica", 14))
    p.drawText(90, 80, "Ø25 ±0.15")
    p.drawText(90, 125, "[D]")
    pdf.newPage()
    p.drawText(90, 80, "Ø25 ±0.10")
    p.end()
    return str(pfad)


def test_semantische_felder_einheiten_grenzen_und_offene_zuordnung():
    p = Pmi("toleranz", "Position", wert=.127, material="M", zone="Diameter", bezuege=[BezugsRef("A", 1)])
    a = za.Blattangabe(0, (0, 0, .1, .1), "⌖ | ⌀.005Ⓜ | A")
    assert za.befund(a, 25.4) == "offen"
    a.modell = p
    assert za.befund(a, None) == "offen" and za.befund(a, 25.4) == "gleich"
    a.modell = replace(p, material="L", bezuege=[BezugsRef("B", 1)])
    assert set(za.unterschiede(za.lese_angabe(a.text, 25.4), a.modell)) == {"material", "bezuege"}
    assert za.befund(a, 25.4) == "geaendert"
    a.text = "⌖ | ? | A"
    assert za.befund(a, 25.4) == "offen"
    a.text, a.modell = "⌀25.2\n24.9", Pmi("mass", "Size_Diameter", nennwert=25., oben=.2, unten=-.1)
    assert za.befund(a, 1.) == "gleich"
    a.modell = replace(a.modell, oben=-.1, unten=.2)
    assert za.befund(a, 1.) == "offen"
    assert za.lese_angabe("⌀10 H7", 1.).passung == "H7"
    assert za.lese_angabe("3X ⌀10", 1.) is None
    assert za.lese_angabe("⌖ | ⌀.005 A | B", 25.4) is None
    assert za.lese_angabe("⌖ | Ø.005 in | A", None).wert == pytest.approx(.127)
    assert "bezuege" in za.unterschiede(p, replace(p, bezuege=[BezugsRef("A", 2)]))


def test_pdf_aus_dem_dateimenue_zuordnen_und_exportieren(fenster_ctc01, tmp_path, monkeypatch):
    f = fenster_ctc01
    pfad = _zeichnung(tmp_path / "Zeichnung.pdf")
    out = tmp_path / "Prüfung.csv"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args: (pfad, "PDF"))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(out), "CSV"))

    f.aktionen["zeichnungsabgleich"].trigger()
    d = f.zeichnungsabgleich
    try:
        assert d.isVisible() and not d.isModal()
        d.einheit.setCurrentIndex(1)
        a = next(a for a in d.seiten[0] if "25" in a.text)
        d.waehle(a)
        m = next(m for m in d.modell if m.typ == "Size_Diameter" and m.nennwert == 25)
        assert d.text.toPlainText() == "Ø25 ±0.15"
        d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(m)]))
        d.bestaetigen.click()
        assert a.modell is m and za.befund(a, 1.) == "gleich"
        assert f.ansicht.hervor == m.flaechen and not d.ausschnitt.pixmap().isNull()
        datum = next(a for a in d.seiten[0] if a.text == "[D]")
        d.waehle(datum)
        d.zuordnung.setCurrentIndex(1)
        d.bestaetigen.click()
        d._export()
        assert "Blatt ungeprüft" in out.read_text(encoding="utf-8-sig")
        d.seite.setValue(2)
        detail = next(a for a in d.seiten[1] if "25" in a.text)
        d.waehle(detail)
        assert d.text.toPlainText() == "Ø25 ±0.10"
        d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(m)]))
        d.bestaetigen.click()
        assert detail.modell is m and za.befund(detail, 1.) == "geaendert"
        fehlt = next(p for p in d.modell if p is not m)
        d.waehle(fehlt)
        d.zuordnung.setCurrentIndex(1)
        d.bestaetigen.click()
        d.seite.setValue(1)
        d.waehle(a)
        assert d.text.toPlainText() == "Ø25 ±0.15"
        d._export()
        eigen, = f.fuege_pmi_hinzu([Pmi("mass", "Size_Diameter", nennwert=25, flaechen=set(m.flaechen))])
        assert id(eigen) in d.modellindex
        d.waehle(a)
        d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(eigen)]))
        d.bestaetigen.click()
        f.loesche_eigene_pmi([eigen])
        assert a.modell is None and detail.modell is m and id(eigen) not in d.modellindex
    finally:
        d.close()
    assert f.zeichnungsabgleich is None
    with out.open(encoding="utf-8-sig") as csvdatei:
        zeilen = list(csv.DictReader(csvdatei, delimiter=";"))
    assert {z["Befund"] for z in zeilen} >= {"Werte gleich", "Abweichend", "Nur in Zeichnung", "Nur im Modell"}
    beide = [z for z in zeilen if z["Angabe"].startswith("Ø25")]
    assert [z["Blatt"] for z in beide] == ["1", "2"] and beide[0]["Modell-PMI"] == beide[1]["Modell-PMI"]
    for z in beide:
        l, t, r, b = map(float, z["Blattbereich (links, oben, rechts, unten relativ)"].split())
        assert 0 <= l < r <= 1 and 0 <= t < b <= 1 and z["Flächen"] != "[]"
        assert int(z["Quell-ID der Modell-PMI"]) == m.step_id
        assert z["Zeichnungsdatei"] == pfad and z["Modelldatei"] == str(f.erg.pfad)


def test_gleiche_werte_an_zwei_flaechen_bleiben_offen(app, tmp_path):
    import pypdfium2 as pdf
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    pfad = _zeichnung(tmp_path / "Detail.pdf")
    p = Pmi("mass", "Size_Diameter", nennwert=25., oben=.15, unten=-.15, nummer=1, flaechen={1})
    with pdf.PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, [p, replace(p, nummer=2, flaechen={2})], lambda _: None, (pfad, ""))
        d.einheit.setCurrentIndex(1)
        a = next(a for a in d.seiten[0] if a.text == "Ø25 ±0.15")
        d.waehle(a)
        assert d.zuordnung.currentData() is None
        d.bestaetigen.click()
        assert za.befund(a, 1.) == "offen"
        d.ansicht.bereich.emit(a.box)
        assert d.aktiv is not a and d.aktiv.text == a.text
        d.entfernen.click()
        assert a in d.seiten[0] and len(d.seiten[0]) == 2
        d.blatt.schliesse()
        d.close()


@pytest.mark.parametrize("winkel", [0, 90, 180, 270])
def test_gescannter_toleranzrahmen_ohne_textschicht(app, tmp_path, winkel):
    # Unveraenderter Rasterausschnitt aus NIST D2MI 827-9999-904 Rev C, Blatt 2.
    import pypdfium2 as pdf
    from programm.kern.zeichnungsblatt import Zeichnungsblatt
    bild = QtGui.QImage(str(Path(__file__).parent / "daten/nist_d2mi_904_rahmen.png"))
    ziel = tmp_path / "Scan.pdf"
    schreiber = QtGui.QPdfWriter(str(ziel))
    schreiber.setResolution(72)
    schreiber.setPageSize(QtGui.QPageSize(QtCore.QSizeF(1224, 792), QtGui.QPageSize.Unit.Point))
    with QtGui.QPainter(schreiber) as maler:
        maler.translate(350, 200)
        maler.rotate(winkel)
        maler.drawImage(QtCore.QRectF(0, 0, bild.width()/4, bild.height()/4), bild)
    with pdf.PdfDocument(ziel) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        assert not blatt.textbereiche
        angabe, = blatt.fundstellen()
        l, t, r, b = angabe.box
        assert ((r-l)*blatt.breite > (b-t)*blatt.hoehe) == (winkel in (0, 180))
        p = za.lese_angabe(angabe.text, 25.4)
        assert p.typ == "Position" and p.wert == pytest.approx(.127) and p.material == "L"
        assert p.bezug_text() == "A|B|C"
        blatt.schliesse()


def test_d2mi_904_grafische_pmi_im_modell_und_auf_blatt_zwei(app):
    import pypdfium2 as pdf
    from programm.kern.zeichnungsblatt import Zeichnungsblatt
    from programm.ui.lader import lade_alles
    pfad = Path(__file__).parents[1] / "daten/nist_d2mi/NIST-D2MI-Models/827-9999-904 rev c.pdf"
    if not pfad.exists():
        pytest.skip("Lokales NIST-D2MI-Referenzpaket fehlt")
    modell = [p for p in lade_alles(str(pfad.with_suffix(".stp"))).pmi if p.semantisch]
    with pdf.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 1)
        angaben = {a.text: a for a in blatt.fundstellen()}
        blatt.schliesse()
    for text, typ, wert in [("2.016", "Location_LinearDistance", 51.2064),
                            ("⌖ | ⌀.005Ⓛ | A | B | C", "Position", .127), ("⏥ | .005", "Flatness", .127)]:
        a = angaben[text]
        p = za.lese_angabe(text, 25.4, a.grundmass)
        assert p.typ == typ and (p.nennwert or p.wert) == pytest.approx(wert)
        gleich = [m for m in za.kandidaten(p, modell) if not za.unterschiede(p, m)]
        assert gleich and gleich[0].flaechen and a.modell is None
    assert len([m for m in modell if m.typ == "Position" and m.material == "M"]) > 1


def test_gemeinsame_rahmenwand_haelt_mehrzeilige_angaben_offen():
    from programm.kern.zeichnungsblatt import _mehrzeilig
    oben = [(30, 10, 43, 24), (44, 10, 75, 24), (76, 10, 90, 24)]
    unten = [(30, 25, 43, 38), (44, 25, 81, 38)]
    daneben = [(95, 25, 108, 38), (109, 25, 134, 38)]
    assert _mehrzeilig([oben, unten, daneben], lambda z: "⌖") == {0, 1}
    assert not _mehrzeilig([oben, daneben], lambda z: "⌖")
    assert not _mehrzeilig([oben, unten], lambda z: "⏥" if z == oben[0] else "⟂")
    assert za.lese_angabe("⌖ | ⌀.1 | A | …", 1.) is None


@pytest.mark.parametrize("winkel", [25, 55, 135, 224])
def test_frei_markierte_schraege_rasterbemassung(app, tmp_path, winkel):
    import numpy as np
    import pypdfium2 as pdf
    from programm.kern.zeichnungsblatt import Zeichnungsblatt
    # Der Ausschnitt enthaelt allein die Ziffern und den Dezimalpunkt der NIST-Vorlage.
    bild = QtGui.QImage(str(Path(__file__).parent / "daten/nist_d2mi_904_rahmen.png")).copy(135, 18, 95, 35)
    pfad = tmp_path / "Geneigte Beschriftung.pdf"
    schreiber = QtGui.QPdfWriter(str(pfad))
    schreiber.setResolution(72)
    with QtGui.QPainter(schreiber) as maler:
        maler.translate(200, 100)
        maler.rotate(winkel)
        maler.drawImage(QtCore.QRectF(0, 0, bild.width()/3, bild.height()/3), bild)
    with pdf.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        h, w = blatt.bild.shape[:2]
        y, x = np.nonzero(blatt.bild.min(axis=2) < 190)
        box = ((x.min()-5)/w, (y.min()-5)/h, (x.max()+5)/w, (y.max()+5)/h)
        text = blatt.lies(box)
        assert text == ".005"
        p = za.lese_angabe(text, 25.4)
        assert p.nennwert == pytest.approx(.127)
        blatt.schliesse()


def test_hinweislinie_und_zwei_beschriftungen_bleiben_offen(app):
    import numpy as np
    from scipy import ndimage
    from programm.kern.zeichnungsblatt import _geneigte_angabe
    bild = QtGui.QImage(str(Path(__file__).parent / "daten/nist_d2mi_904_rahmen.png"))
    bild = bild.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    pixel = np.frombuffer(bild.constBits(), np.uint8).reshape(bild.height(), bild.bytesPerLine())
    zahl = pixel[18:53, 135:230] < 185
    zwei_zeilen = np.vstack([zahl, np.zeros_like(zahl), zahl])
    linie = np.pad(np.ones((1, 200), bool), ((10, 10), (5, 5)))
    for maske in (linie, zwei_zeilen):
        assert not _geneigte_angabe(ndimage.rotate(maske, 33, order=0))
