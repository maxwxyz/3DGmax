import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern.zeichnungskoerper import plattenmasse, rechteckansicht
from programm.ui.zeichnungskoerper_ui import Plattendialog


def _blatt(pfad):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(400, 300), QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0, 0, 0, 0))
    with QtGui.QPainter(pdf) as p:
        p.drawRect(40, 40, 150, 100)
        p.drawRect(40, 185, 120, 16)
        for x, text in ((30, "60 ±0.1"), (140, "40"), (230, "8")):
            p.drawText(x, 250, text)


def test_platte_aus_pdf_mit_bemassung_aus_dateimenue(fenster, tmp_path, monkeypatch):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.zeichnungsabgleich import Blattangabe, befund
    from programm.ui.lader import lade_alles
    pfad = tmp_path / "Platte.pdf"
    ziel = tmp_path / "Platte.stp"
    _blatt(pfad)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args: (str(pfad), "PDF"))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    assert fenster.aktionen["zeichnungskoerper"].isEnabled()
    fenster.aktionen["zeichnungskoerper"].trigger()
    d = fenster.findChild(Plattendialog)
    try:
        assert d.isVisible() and not d.speichern.isEnabled()
        d.einheit.setCurrentIndex(1)

        def einrahmen(i, box):
            d.auswahl.setCurrentIndex(i)
            d.ansicht.bereich.emit(tuple(np.array(box)/[400, 300, 400, 300]))

        einrahmen(0, (34, 34, 196, 146))
        einrahmen(1, (34, 179, 166, 207))
        einrahmen(2, (24, 225, 125, 255))
        einrahmen(3, (133, 225, 200, 255))
        assert "Dicke" in d.status.text() and not d.speichern.isEnabled()
        einrahmen(4, (220, 225, 260, 255))
        assert [w.text() for w in d.texte] == ["60 ±0.1", "40", "8"]
        assert d.speichern.isEnabled()
        d.texte[2].setText("12")
        assert not d.speichern.isEnabled() and "Vorderansicht" in d.status.text()
        d.texte[2].setText("8")
        einrahmen(1, (0,0,4,4))
        assert not d.speichern.isEnabled()
        d.vorne_entfernen.click()
        assert d.speichern.isEnabled()
        einrahmen(1, (34, 179, 166, 207))
        d.speichern.click()
        erg = lade_alles(str(ziel))
        assert erg.modell.datei.schema.startswith("AP242")
        assert len(erg.modell.flaechen) == 6 and len(erg.pmi) == 3
        volumen = GProp_GProps()
        brepgprop.VolumeProperties(erg.modell.form, volumen)
        assert volumen.Mass() == pytest.approx(60*40*8)
        for p in erg.pmi:
            assert p.grafisch and p.semantisch and len(p.flaechen) == 2
            ebenen = [BRepAdaptor_Surface(erg.modell.flaechen[i]).Plane() for i in p.flaechen]
            assert ebenen[0].Distance(ebenen[1]) == pytest.approx(p.nennwert)
        assert sorted(p.nennwert for p in erg.pmi) == [8.,40.,60.]
        assert next(p for p in erg.pmi if p.nennwert == 60).grenzen() == pytest.approx((60.1,59.9))
        xcaf = sorted(lies_pmi_xcaf(erg.modell), key=lambda p: p.nennwert, reverse=True)
        assert len(xcaf) == 3
        for feld, p in zip(d.texte, xcaf, strict=True):
            angabe = Blattangabe(0, (0,0,1,1), feld.text(), modell=p)
            assert len(p.flaechen) == 2 and befund(angabe, 1.) == "gleich"
        assert "gespeichert" in d.status.text()
    finally:
        d.close()


def test_platte_offene_kontur_loch_und_unbekannte_masse():
    bild = np.full((100,160,3), 255, np.uint8)
    bild[10:90,10] = bild[10:90,149] = 0
    bild[10,10:150] = bild[89,10:150] = 0
    assert rechteckansicht(bild, (0,0,1,1)) == (139,79)
    assert rechteckansicht(bild, (.2,0,1,1)) is None
    bild[10,10] = 255
    assert rechteckansicht(bild, (0,0,1,1)) is None
    bild[10,10] = bild[89,149] = 0
    bild[11,60] = 0
    assert rechteckansicht(bild, (0,0,1,1)) is None
    bild[11,60] = 255
    bild[50:54,60:64] = 0
    assert rechteckansicht(bild, (0,0,1,1)) is None
    for masse, einheit in ((["60","40",""],1.), (["60","40","-2"],1.), (["60","40","Ø8"],1.),
                          (["60","40","8"],None), (["60","30","8"],1.), (["60","40","(8)"],1.)):
        with pytest.raises(ValueError):
            plattenmasse(masse, einheit, (600,400))
    assert [p.nennwert for p in plattenmasse(["3 in","2 in",".5 in"], None, (600,400))] == pytest.approx([76.2,50.8,12.7])


def test_unvollstaendiger_pmi_export_erhaelt_fruehere_datei(tmp_path, monkeypatch):
    from programm.kern import step_schreiben
    from programm.kern.zeichnungskoerper import schreibe_platte
    ziel = tmp_path / "Modell.stp"
    ziel.write_bytes(b"frueherer Stand")
    monkeypatch.setattr(step_schreiben, "schreibe", lambda *args: step_schreiben.Bericht(neu=[1, 2, 3]))
    with pytest.raises(ValueError, match="STEP-PMI"):
        schreibe_platte(ziel, plattenmasse(["60", "40", "8"], 1., (600,400)))
    assert ziel.read_bytes() == b"frueherer Stand" and list(tmp_path.iterdir()) == [ziel]


def test_grenzmasse_aus_zollzeichnung_auch_in_xcaf(tmp_path):
    from programm.kern.laden import lade_step
    from programm.kern.pmi_lesen import lies_pmi, lies_pmi_xcaf
    from programm.kern.zeichnungskoerper import schreibe_platte
    masse = plattenmasse(["1.50–1.52 in", "1 in", ".125 ±.002 in"], None, (604,400))
    ziel = tmp_path / "Inch.stp"
    schreibe_platte(ziel, masse)
    modell = lade_step(str(ziel))
    for lesen in (lies_pmi, lies_pmi_xcaf):
        breite, _, dicke = sorted(lesen(modell), key=lambda p: p.nennwert, reverse=True)
        assert breite.nennwert == pytest.approx(38.354) and breite.grenzmass
        assert breite.grenzen() == pytest.approx((38.608,38.1))
        assert (dicke.nennwert, dicke.oben, dicke.unten) == pytest.approx((3.175,.0508,-.0508))
