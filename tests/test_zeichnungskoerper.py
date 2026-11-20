import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern.zeichnungskoerper import plattenmasse, rechteckansicht
from programm.ui.zeichnungskoerper_ui import Plattendialog


def _blatt(pfad, bohrungen=(), innenlinie=False, tiefe=None):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(400, 300), QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0, 0, 0, 0))
    with QtGui.QPainter(pdf) as p:
        p.drawRect(40, 40, 150, 100)
        for x, y, r in bohrungen:
            p.drawEllipse(QtCore.QPointF(40+2.5*x, 140-2.5*y), 2.5*r, 2.5*r)
        if innenlinie:
            p.drawLine(123, 80, 134, 88)
        p.drawRect(40, 185, 120, 16)
        if bohrungen:
            p.drawText(60, 280, "Ø10 ±0.05")
        if tiefe:
            p.drawText(220, 280, tiefe)
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



@pytest.mark.parametrize("innenlinie", [False, True])
def test_bohrungen_im_plattendialog_mit_ap242_wandbezug(app, tmp_path, monkeypatch, innenlinie):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    pfad, ziel = (tmp_path / name for name in ("Bohrbild.pdf", "Bohrplatte.stp"))
    _blatt(pfad, ((20,16,5),(48,28,4)), innenlinie)
    with PdfDocument(pfad) as doc:
        d = Plattendialog(doc, pfad)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60","40","8")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            if innenlinie:
                assert not d.speichern.isEnabled() and not d.ringe
                return
            assert d.bohrfeld.isVisible() and not d.speichern.isEnabled()
            assert d.bohrtabelle.rowCount() == len(d.ansicht.kreismarken) == 2
            d.ansicht.kreis_gewaehlt.emit(d.ringe[1].kreis)
            assert d.bohrtabelle.currentRow() == 1
            for i, werte in enumerate((("20","16","Ø10 ±0.05"), ("48","28","Ø8 H7"))):
                for j, text in enumerate(werte, 1):
                    d.bohrtabelle.item(i,j).setText(text)
            d.bohrtabelle.setCurrentCell(0, 3)
            d.auswahl.setCurrentIndex(7)
            d.ansicht.bereich.emit((.12,.86,.38,.96))
            assert d.bohrtabelle.item(0,3).text() == "Ø10 ±0.05"
            d.einheit.setCurrentIndex(2)
            d.ansicht.bereich.emit((.12,.86,.38,.96))
            assert d.bohrtabelle.item(0,3).text().endswith(" in")
            d.einheit.setCurrentIndex(1)
            d.ansicht.bereich.emit((.12,.86,.38,.96))
            d.auswahl.setCurrentIndex(0)
            assert not d.speichern.isEnabled()
            d.durchgehend.setChecked(True)
            assert d.speichern.isEnabled()
            for falsch in ("25", "20 ±0.1", "20°"):
                d.bohrtabelle.item(0,1).setText(falsch)
                assert not d.speichern.isEnabled()
            d.bohrtabelle.item(0,1).setText("20")
            monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 5 and all(p.grafisch and p.semantisch for p in erg.pmi)
            volumen = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, volumen)
            assert volumen.Mass() == pytest.approx(8*(60*40-np.pi*(25+16)))
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                zyl = sorted((p for p in quelle if p.typ == "Size_Diameter"), key=lambda p: -p.nennwert)
                assert len(zyl) == 2 and zyl[0].grenzen() == pytest.approx((10.05,9.95))
                for p, (x, y, r) in zip(zyl, ((20,16,5),(48,28,4)), strict=True):
                    f, = p.flaechen
                    z = BRepAdaptor_Surface(erg.modell.flaechen[f]).Cylinder()
                    assert (z.Location().X(), z.Location().Y(), z.Radius()) == pytest.approx((x,y,r))
            assert any(p.passung == "H7" for p in erg.pmi)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            assert not d.durchgehend.isChecked() and not d.speichern.isEnabled()
        finally:
            d.blatt.schliesse()
            d.close()


def test_mengenangabe_und_falsches_bohrziel_bleiben_offen():
    from programm.kern.plattenbohrung import Plattenring, sollbohrungen
    from programm.kern.zeichnungsansicht import Blattkreis
    ring = Plattenring(Blattkreis(200, 240, 50), 1/3, .4, 1/12)
    masse = plattenmasse(["60","40","8"], 1., (600,400))
    for zeile in (("20", "16", "2X Ø10"), ("4", "16", "Ø10"), ("20", "16", "R5"),
                  ("20", "16", "Ø20"), ("20", "16", "Ø10 ±11")):
        with pytest.raises(ValueError):
            sollbohrungen([ring], [zeile], masse, (600,400))
    with pytest.raises(ValueError, match="andere Bohrung"):
        sollbohrungen([ring, ring], [("20","16","Ø10"), ("20","16","Ø10")], masse, (600,400))


def test_sackloch_gemischte_platte_mit_getrennten_tiefenzielen(app, tmp_path, monkeypatch):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path / "Grundriss.pdf", tmp_path / "Flachboden.stp"
    _blatt(pdf, ((12, 12, 3), (32, 20, 4), (48, 28, 4)), tiefe="4 ±0.1")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60", "40", "8 ±0.1")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            assert len(d.ringe) == 3
            for i, werte in enumerate((("12","12","6"), ("32","20","8"), ("48","28","8"))):
                for j, wert in enumerate(werte, 1):
                    d.bohrtabelle.item(i,j).setText(wert)
            d.durchgehend.click()
            assert d.speichern.isEnabled()
            for i in (1,2):
                d.bohrtabelle.cellWidget(i,4).setCurrentIndex(2)
                assert not d.speichern.isEnabled() and not d.durchgehend.isChecked()
                d.bohrtabelle.setCurrentCell(i,5)
                d.auswahl.setCurrentIndex(8)
                d.ansicht.bereich.emit((.52,.86,.80,.96))
                assert d.bohrtabelle.item(i,5).text() == "4 ±0.1"
            for fehler in ("0", "4 ±5", "7.8 ±0.2", "Ø4", "(4)", "4 H7"):
                d.bohrtabelle.item(2,5).setText(fehler)
                assert not d.speichern.isEnabled()
            d.bohrtabelle.item(2,5).setText("↧4 ±0.2")
            assert d.speichern.isEnabled()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert "8" in d.status.text()
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, v)
            assert v.Mass() == pytest.approx(60*40*8 - np.pi*(9*8+2*16*4))
            assert len(erg.pmi) == 8 and all(p.grafisch and p.semantisch for p in erg.pmi)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                tiefen = sorted((p for p in quelle if p.nennwert == 4), key=lambda p: p.oben)
                assert len(tiefen) == 2
                for p, (x,y,tol) in zip(tiefen, ((32,20,.1),(48,28,.2)), strict=True):
                    assert p.typ == "Location_LinearDistance" and p.grenzen() == pytest.approx((4+tol,4-tol))
                    ebenen = sorted((BRepAdaptor_Surface(erg.modell.flaechen[i]).Plane().Location().Z(), i)
                                    for i in p.flaechen)
                    assert [z for z, _ in ebenen] == pytest.approx([4,8])
                    boden = GProp_GProps()
                    brepgprop.SurfaceProperties(erg.modell.flaechen[ebenen[0][1]], boden)
                    assert boden.CentreOfMass().Coord() == pytest.approx((x,y,4))
            d.bohrtabelle.cellWidget(2,4).setCurrentIndex(1)
            assert d.bohrtabelle.item(2,5).text() == "" and (2,8) not in d.marken
        finally:
            d.blatt.schliesse()
            d.close()
