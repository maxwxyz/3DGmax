import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern.zeichnungskoerper import plattenmasse, rechteckansicht
from programm.ui.zeichnungskoerper_ui import Plattendialog


def _blatt(pfad, bohrungen=(), innenlinie=False, tiefe=None, taschen=()):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(400, 300), QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0, 0, 0, 0))
    with QtGui.QPainter(pdf) as p:
        p.drawRect(40, 40, 150, 100)
        for x, y, r in bohrungen:
            p.drawEllipse(QtCore.QPointF(40+2.5*x, 140-2.5*y), 2.5*r, 2.5*r)
        for x, y, breite, hoehe, *r in taschen:
            rechteck = QtCore.QRectF(40+2.5*(x-breite/2), 140-2.5*(y+hoehe/2), 2.5*breite, 2.5*hoehe)
            if r:
                p.drawRoundedRect(rechteck, 2.5*r[0], 2.5*r[0])
            else:
                p.drawRect(rechteck)
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
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
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
            for i, werte in enumerate((("20","16","Ø10 ±0.05"), ("48","27.9–28.1","Ø8 H7"))):
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
            for falsch in ("25", "20 H7", "20 ±16", "20°"):
                d.bohrtabelle.item(0,1).setText(falsch)
                assert not d.speichern.isEnabled()
            d.bohrtabelle.item(0,1).setText("20 ±0.1")
            monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 9 and all(p.grafisch and p.semantisch for p in erg.pmi)
            volumen = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, volumen)
            assert volumen.Mass() == pytest.approx(8*(60*40-np.pi*(25+16)))
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                lage = sorted((p for p in quelle if p.typ == "Location_LinearDistance_FromOuterToCenter"),
                              key=lambda p: p.nennwert)
                for p, (wert, achse, xy) in zip(lage, ((16,1,(20,16)), (20,0,(20,16)),
                                                        (28,1,(48,28)), (48,0,(48,28))), strict=True):
                    assert p.nennwert == wert
                    if wert == 20:
                        assert p.grenzen() == pytest.approx((20.1,19.9))
                    if wert == 28:
                        assert p.grenzmass and p.grenzen() == pytest.approx((28.1,27.9))
                    fl = [BRepAdaptor_Surface(erg.modell.flaechen[i]) for i in p.flaechen]
                    ebene, = (f.Plane() for f in fl if f.GetType() == GeomAbs_Plane)
                    zylinder, = (f.Cylinder() for f in fl if f.GetType() == GeomAbs_Cylinder)
                    assert abs(ebene.Axis().Direction().Coord()[achse]) == pytest.approx(1)
                    assert ebene.Location().Coord()[achse] == pytest.approx(0)
                    assert zylinder.Location().Coord()[:2] == pytest.approx(xy)
                zyl = sorted((p for p in quelle if p.typ == "Size_Diameter"), key=lambda p: -p.nennwert)
                assert len(zyl) == 2 and zyl[0].grenzen() == pytest.approx((10.05,9.95))
                for p, (x, y, r) in zip(zyl, ((20,16,5),(48,28,4)), strict=True):
                    f, = p.flaechen
                    z = BRepAdaptor_Surface(erg.modell.flaechen[f]).Cylinder()
                    assert (z.Location().X(), z.Location().Y(), z.Radius()) == pytest.approx((x,y,r))
            datei = erg.modell.datei
            aspekte = {e.args("GEOMETRIC_ITEM_SPECIFIC_USAGE")[2].id: e.args("GEOMETRIC_ITEM_SPECIFIC_USAGE")[4].id
                       for e in datei.of_type("GEOMETRIC_ITEM_SPECIFIC_USAGE")}
            for p in (q for q in erg.pmi if q.typ == "Location_LinearDistance_FromOuterToCenter"):
                ebene, wand = datei.entities[p.step_id].args("DIMENSIONAL_LOCATION")[2:]
                referenzen = [erg.modell.step_zu_flaeche[aspekte[ref.id]] for ref in (ebene, wand)]
                assert [BRepAdaptor_Surface(erg.modell.flaechen[i]).GetType() for i in referenzen] == [
                    GeomAbs_Plane, GeomAbs_Cylinder]
                grafik, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
                linie = grafik.linien[2]
                np.testing.assert_allclose(linie[:,2], [8,8], atol=1e-6)
                assert np.linalg.norm(linie[1]-linie[0]) == pytest.approx(p.nennwert)
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
            assert "14" in d.status.text()
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, v)
            assert v.Mass() == pytest.approx(60*40*8 - np.pi*(9*8+2*16*4))
            assert len(erg.pmi) == 14 and all(p.grafisch and p.semantisch for p in erg.pmi)
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


@pytest.mark.parametrize(("mit_bohrung", "durchbrueche"), [(False,0), (True,0), (True,1), (False,2)])
def test_rechtecktaschen_aus_pdf_mit_eindeutigen_wandpaaren(app, tmp_path, monkeypatch, mit_bohrung, durchbrueche):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Taschen.pdf", tmp_path/"Taschen.stp"
    _blatt(pdf, [(30,32,2)] if mit_bohrung else [], tiefe="3 ±0.1", taschen=[(15,16,12,8),(45,16,12,8)])
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60", "40", "8 ±0.1")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            assert len(d.taschen) == 2 and len(d.ringe) == int(mit_bohrung)
            if mit_bohrung:
                for j, text in enumerate(("30","32","4"), 1):
                    d.bohrtabelle.item(0,j).setText(text)
                d.durchgehend.click()
            for i, x in enumerate((15,45)):
                from PySide6.QtTest import QTest
                app.processEvents()
                d.ansicht.einpassen()
                l,t,r,b = d.taschen[i].box
                sz = d.ansicht.sceneRect()
                punkt = d.ansicht.mapFromScene((l+r)*sz.width()/2, (t+b)*sz.height()/2)
                QTest.mouseClick(d.ansicht.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=punkt)
                assert d.innen.currentIndex() == 1 and d.taschentabelle.currentRow() == i
                for j, text in enumerate((str(x), "16", "12 ±0.05", "8"), 1):
                    d.taschentabelle.item(i,j).setText(text)
                d.auswahl.setCurrentIndex(d.auswahl.findData(5))
                d.ansicht.bereich.emit((.52,.86,.8,.96))
                assert d.taschentabelle.item(i,5).text() == "3 ±0.1"
            assert d.speichern.isEnabled()
            if mit_bohrung:
                ring = d.ringe[0].kreis
                punkt = d.ansicht.mapFromScene(ring.x+ring.r, ring.y)
                QTest.mouseClick(d.ansicht.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=punkt)
                assert d.innen.currentIndex() == 0 and d.auswahl.currentIndex() == 5
            for j, falsch in ((1,"42"), (3,"13"), (5,"8"), (5,"3 ±4")):
                item = d.taschentabelle.item(1,j)
                gut = item.text()
                item.setText(falsch)
                assert not d.speichern.isEnabled()
                item.setText(gut)
            for zeile in range(durchbrueche):
                art = d.taschentabelle.cellWidget(zeile, 6)
                d.auswahl.setCurrentIndex(d.auswahl.findData(5))
                d.taschentabelle.setCurrentCell(zeile, 1)
                art.setCurrentIndex(1)
                d.ansicht.bereich.emit((.52,.86,.8,.96))
                assert d.taschentabelle.item(zeile,5).text() == "" and ("tasche",zeile,5) not in d.marken
                assert d.speichern.isEnabled()
                art.setCurrentIndex(0)
                assert not d.speichern.isEnabled()
                art.setCurrentIndex(1)
            d.speichern.click()
            erg = lade_alles(str(ziel))
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, v)
            assert v.Mass() == pytest.approx(60*40*8-12*8*(6+5*durchbrueche)-(32*np.pi if mit_bohrung else 0))
            assert len(erg.pmi) == 13-durchbrueche+3*int(mit_bohrung) and all(p.grafisch and p.semantisch for p in erg.pmi)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                breite = [p for p in quelle if p.nennwert == 12]
                tiefen = [p for p in quelle if p.nennwert == 3]
                hoehen = [p for p in quelle if p.nennwert == 8 and p.oben is None]
                assert len(breite) == len(hoehen) == 2 and len(tiefen) == 2-durchbrueche
                xpaare = []
                for p in breite:
                    assert p.grenzen() == pytest.approx((12.05,11.95))
                    xpaare.append(sorted(BRepAdaptor_Surface(erg.modell.flaechen[f]).Plane().Location().X() for f in p.flaechen))
                np.testing.assert_allclose(sorted(xpaare), [[9,21],[39,51]], atol=1e-6)
                wandmitten = []
                for p in hoehen:
                    xs = []
                    for f in p.flaechen:
                        props = GProp_GProps()
                        brepgprop.SurfaceProperties(erg.modell.flaechen[f], props)
                        xs.append(props.CentreOfMass().X())
                    wandmitten.append(sorted(xs))
                    assert sorted(BRepAdaptor_Surface(erg.modell.flaechen[f]).Plane().Location().Y() for f in p.flaechen) == pytest.approx([12,20])
                np.testing.assert_allclose(sorted(wandmitten), [[15,15],[45,45]], atol=1e-6)
                mitten = []
                for p in tiefen:
                    assert p.grenzen() == pytest.approx((3.1,2.9))
                    ebenen = sorted((BRepAdaptor_Surface(erg.modell.flaechen[f]).Plane().Location().Z(),f) for f in p.flaechen)
                    assert [z for z,_ in ebenen] == pytest.approx([5,8])
                    boden = GProp_GProps()
                    brepgprop.SurfaceProperties(erg.modell.flaechen[ebenen[0][1]], boden)
                    mitten.append(boden.CentreOfMass().Coord())
                np.testing.assert_allclose(sorted(mitten), [(15,16,5),(45,16,5)][durchbrueche:], atol=1e-6)
        finally:
            d.blatt.schliesse()
            d.close()


def test_taschen_kollisionen_und_offene_konturen():
    from programm.kern.plattenbohrung import plattenumriss
    from programm.kern.plattentasche import Taschenkontur, solltaschen
    from programm.kern.zeichnungsabgleich import lese_angabe
    from programm.kern.zeichnungskoerper import Plattenbohrung
    tex = ("30","20","12","8","3")
    umriss = Taschenkontur((0,0,1,1), .5,.5,.2,.2)
    masse = plattenmasse(["60","40","8"],1.,(600,400))
    bohrung = Plattenbohrung(38,20,lese_angabe("Ø4",1.))
    with pytest.raises(ValueError, match="Bohrung"):
        solltaschen([umriss], [tex], masse, (600,400), [bohrung])
    with pytest.raises(ValueError, match="andere Tasche"):
        solltaschen([umriss]*2, [tex]*2, masse, (600,400), [])
    bild = np.full((100,150,3), 255, np.uint8)
    for l,t,r,b in ((5,5,145,95),(30,30,90,60)):
        bild[t:b+1,l] = bild[t:b+1,r] = bild[t,l:r+1] = bild[b,l:r+1] = 0
    assert len(plattenumriss(bild,(0,0,1,1),[])[2]) == 1
    bild[30,40:46] = 255
    assert plattenumriss(bild,(0,0,1,1),[]) is None


def test_stufenbohrungen_mit_absatz_und_kern_tiefe_ab_oberseite(app, tmp_path, monkeypatch):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles

    pdf, ziel = tmp_path/"Stufen.pdf", tmp_path/"Stufen.stp"
    _blatt(pdf, [(16,20,6),(16,20,2),(16,20,4),(42,20,2),(42,20,4)], tiefe="2 ±0.1")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60","40","8")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            assert [r.kern for r in d.ringe] == [None,0,0,None,3]
            assert not d.durchgehend.isEnabled()
            tabelle = d.bohrtabelle
            for i, (x, dm, ende, tiefe) in enumerate(((16,4,1,None), (None,8,1,"5"), (None,12,1,"2 ±0.1"),
                                                       (42,4,2,"6"), (None,8,1,"2 ±0.2"))):
                if x is not None:
                    tabelle.item(i,1).setText(str(x))
                    tabelle.item(i,2).setText("20")
                else:
                    assert not tabelle.item(i,1).flags() & QtCore.Qt.ItemFlag.ItemIsEditable
                tabelle.item(i,3).setText(str(dm))
                tabelle.cellWidget(i,4).setCurrentIndex(ende)
                if tiefe:
                    tabelle.item(i,5).setText(tiefe)
            assert d.speichern.isEnabled()
            tabelle.item(1,5).setText("2.2 ±0.2")
            assert not d.speichern.isEnabled()
            tabelle.item(1,5).setText("5")
            tabelle.item(1,3).setText("8 ±4")
            assert not d.speichern.isEnabled()
            tabelle.item(1,3).setText("8")
            tabelle.cellWidget(2,4).setCurrentIndex(0)
            assert not d.speichern.isEnabled()
            tabelle.cellWidget(2,4).setCurrentIndex(1)
            d.ansicht.kreis_gewaehlt.emit(d.ringe[2].kreis)
            d.auswahl.setCurrentIndex(8)
            d.ansicht.bereich.emit((.52,.86,.8,.96))
            assert tabelle.item(2,5).text() == "2 ±0.1" and d.speichern.isEnabled()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 16 and all(p.grafisch and p.semantisch for p in erg.pmi)
            props = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, props)
            assert props.Mass() == pytest.approx(60*40*8-np.pi*(4*8+12*5+20*2+4*6+12*2))
            for merkmale in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                zylinder = []
                tiefen = []
                for p in merkmale:
                    if p.typ == "Size_Diameter":
                        f, = p.flaechen
                        s = BRepAdaptor_Surface(erg.modell.flaechen[f])
                        x = s.Cylinder().Location().X()
                        zs = [s.Value(0,v).Z() for v in (s.FirstVParameter(),s.LastVParameter())]
                        zylinder.append((x,p.nennwert,*sorted(zs)))
                    if p.typ == "Location_LinearDistance" and p.nennwert in (2,5,6):
                        fl = sorted((BRepAdaptor_Surface(erg.modell.flaechen[f]).Plane().Location().Z(), f)
                                    for f in p.flaechen)
                        assert [z for z, _ in fl] == pytest.approx([8-p.nennwert,8])
                        brepgprop.SurfaceProperties(erg.modell.flaechen[fl[0][1]], props)
                        tiefen.append((props.CentreOfMass().X(), p.nennwert, p.oben or 0.))
                np.testing.assert_allclose(sorted(zylinder), [(16,4,0,3),(16,8,3,6),(16,12,6,8),
                                                             (42,4,2,6),(42,8,6,8)], atol=1e-6)
                np.testing.assert_allclose(sorted(tiefen, key=lambda v:(round(v[0]),v[1])),
                                           [(16,2,.1),(16,5,0),(42,2,.2),(42,6,0)], atol=1e-6)
        finally:
            d.blatt.schliesse()
            d.close()


def test_nahe_ringradien_und_exzentrische_ringe(app):
    from programm.kern.plattenbohrung import plattenumriss, sollbohrungen
    from programm.kern.zeichnungsansicht import Blattkreis
    yy, xx = np.indices((300,400))
    bild = np.full((300,400,3), 255, np.uint8)
    bild[20:281,20] = bild[20:281,380] = bild[20,20:381] = bild[280,20:381] = 0
    for versatz in (0, 1):
        maske = bild.copy()
        kreise = [Blattkreis(200,150,60), Blattkreis(200+versatz,150,65)]
        for k in kreise:
            maske[np.abs(np.hypot(xx-k.x, yy-k.y)-k.r) <= 1] = 0
        umfang, ringe, _ = plattenumriss(maske, (0,0,1,1), kreise)
        assert [r.kern for r in ringe] == [None, None if versatz else 0]
        masse = plattenmasse(["360","260","8"], 1., umfang)
        werte = [("180","130","120"), (str(180+versatz),"130","130")]
        if versatz:
            with pytest.raises(ValueError, match="andere Bohrung"):
                sollbohrungen(ringe, werte, masse, umfang, tiefen=[None,"3"])
        else:
            assert len(sollbohrungen(ringe, werte, masse, umfang, tiefen=[None,"3"])) == 2


def test_kegelsenkungen_aus_pdf_mit_eintrittskreis_und_winkel(app, tmp_path, monkeypatch):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import topods
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles

    pdf, ziel = tmp_path/"Senkung.pdf", tmp_path/"Senkung.stp"
    _blatt(pdf, [(16,20,2),(16,20,6),(42,20,2),(42,20,4),(42,20,6)], tiefe="90° ±1°")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, wert in zip(d.texte, ("60","40","8")):
                feld.setText(wert)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            t = d.bohrtabelle
            for i, (x, dm, art, wert) in enumerate(((16,"4",1,None),(None,"12 ±0.1",3,"90° ±1°"),
                                                    (42,"4",2,"7"),(None,"8",2,"4"),(None,"12 ±0.2",3,"120° ±2°"))):
                if x:
                    t.item(i,1).setText(str(x))
                    t.item(i,2).setText("20")
                t.item(i,3).setText(dm)
                auswahl = t.cellWidget(i,4)
                auswahl.setCurrentIndex(auswahl.findData(art))
                if wert:
                    t.item(i,5).setText(wert)
            assert t.cellWidget(3,4).findData(3) == -1 and d.speichern.isEnabled()
            for falsch in ("", "90", "90 mm", "180°", "1°", "90° ±91°"):
                t.item(1,5).setText(falsch)
                assert not d.speichern.isEnabled()
            d.ansicht.kreis_gewaehlt.emit(d.ringe[1].kreis)
            d.auswahl.setCurrentIndex(8)
            d.ansicht.bereich.emit((.52,.86,.8,.96))
            assert "".join(t.item(1,5).text().split()) == "90°±1°" and d.speichern.isEnabled()
            art = t.cellWidget(1,4)
            art.setCurrentIndex(art.findData(2))
            assert t.item(1,5).text() == "" and not d.speichern.isEnabled()
            art.setCurrentIndex(art.findData(3))
            t.item(1,5).setText("90° ±1°")
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 16 and all(p.grafisch and p.semantisch for p in erg.pmi)
            props = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, props)
            def ringkegel(r, R, alpha):
                h = (R-r)/np.tan(np.deg2rad(alpha/2))
                return np.pi*h*(R*R+R*r-2*r*r)/3
            material = 60*40*8-np.pi*(4*8+4*7+12*4)-ringkegel(2,6,90)-ringkegel(4,6,120)
            assert props.Mass() == pytest.approx(material)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                winkel = sorted((p for p in quelle if p.typ == "Size_Angular"), key=lambda p:p.nennwert)
                for p, (x,w,tol) in zip(winkel, ((16,90,1),(42,120,2)), strict=True):
                    f, = p.flaechen
                    kegel = BRepAdaptor_Surface(erg.modell.flaechen[f]).Cone()
                    assert p.grenzen() == pytest.approx((w+tol,w-tol))
                    assert np.rad2deg(2*abs(kegel.SemiAngle())) == pytest.approx(w)
                    assert kegel.Location().X() == pytest.approx(x)
                rand = sorted((p for p in quelle if p.typ == "Size_Diameter" and p.nennwert == 12), key=lambda p:p.oben)
                assert len(rand) == 2 and all(p.kanten == 1 for p in rand)
            for p, x in zip(sorted((p for p in erg.pmi if p.kanten), key=lambda p:p.oben), (16,42), strict=True):
                form, = p.teilformen
                kreis = BRepAdaptor_Curve(topods.Edge(form)).Circle()
                assert kreis.Location().Coord() == pytest.approx((x,20,8))
                assert kreis.Radius() == pytest.approx(6)
                g, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
                spitze = g.linien[0][0]
                assert spitze[2] == pytest.approx(8)
                assert np.hypot(spitze[0]-x,spitze[1]-20) == pytest.approx(6)
        finally:
            d.blatt.schliesse()
            d.close()


@pytest.mark.parametrize("gesamt", [False, True])
def test_bohrspitzen_mit_zylinder_oder_gesamttiefe(app, tmp_path, monkeypatch, gesamt):
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopAbs import TopAbs_VERTEX
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import topods
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Bohrspitzen.pdf", tmp_path/"Bohrspitzen.stp"
    _blatt(pdf, [(16,20,2),(42,20,2),(42,20,4)], tiefe="118° ±1°")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, wert in zip(d.texte, ("60","40","8 ±0.1")):
                feld.setText(wert)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            t = d.bohrtabelle
            assert t.isColumnHidden(6)
            for i, x in enumerate((16,42)):
                t.item(i,1).setText(str(x))
                t.item(i,2).setText("20")
                t.item(i,3).setText("Ø4 ±0.1")
                art = t.cellWidget(i,4)
                art.setCurrentIndex(art.findData(5 if gesamt and i == 1 else 4))
                t.item(i,5).setText("5 ±0.1")
                assert not t.isColumnHidden(6)
                t.item(i,6).setText("118° ±1°" if i == 0 else "90° ±2°")
            t.item(2,3).setText("8")
            art = t.cellWidget(2,4)
            art.setCurrentIndex(art.findData(3))
            t.item(2,5).setText("120°")
            assert d.speichern.isEnabled()
            if gesamt:
                for tiefe in ("1.8", "3 ±0.1", "8 ±0.1"):
                    t.item(1,5).setText(tiefe)
                    assert not d.speichern.isEnabled()
                t.item(1,5).setText("5 ±0.1")
            for winkel in ("118", "0°", "5°", "180°"):
                t.item(0,6).setText(winkel)
                assert not d.speichern.isEnabled()
            d.ansicht.kreis_gewaehlt.emit(d.ringe[0].kreis)
            d.auswahl.setCurrentIndex(9)
            d.ansicht.bereich.emit((.52,.86,.8,.96))
            assert d.speichern.isEnabled()
            t.item(0,5).setText("6.6 ±0.2")
            assert not d.speichern.isEnabled()
            t.item(0,5).setText("5 ±0.1")
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 15 and all(p.grafisch and p.semantisch for p in erg.pmi)
            props = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, props)
            spitzen = sum(4*2/np.tan(np.deg2rad(w/2))/3 for w in (118,90))
            sitz = (16+8-8)*2/np.tan(np.deg2rad(60))/3
            assert props.Mass() == pytest.approx(60*40*8-np.pi*(2*4*5-8*gesamt+spitzen+sitz))
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                tiefen = [p for p in quelle if p.nennwert == 5]
                assert len(tiefen) == 2
                for p in tiefen:
                    deckel, = p.flaechen
                    assert BRepAdaptor_Surface(erg.modell.flaechen[deckel]).Plane().Location().Z() == pytest.approx(8)
                    assert p.kanten == 1 and p.grenzen() == pytest.approx((5.1,4.9))
                winkel = sorted((q for q in quelle if q.typ == "Size_Angular" and q.nennwert < 119),
                                key=lambda q:q.nennwert)
                for p, (soll,tol) in zip(winkel, ((90,2),(118,1)), strict=True):
                    assert p.grenzen() == pytest.approx((soll+tol,soll-tol))
                    f, = p.flaechen
                    s = BRepAdaptor_Surface(erg.modell.flaechen[f])
                    alpha = round(p.nennwert)
                    assert alpha in (90,118) and np.rad2deg(abs(s.Cone().SemiAngle())*2) == pytest.approx(alpha)
                    zs = sorted(s.Value(0,v).Z() for v in (s.FirstVParameter(),s.LastVParameter()))
                    ende = 5 if gesamt and alpha == 90 else 3
                    assert zs == pytest.approx([ende-2/np.tan(np.deg2rad(alpha/2)),ende])
            xwerte = []
            for p in (q for q in erg.pmi if q.nennwert == 5):
                form, = p.teilformen
                if form.ShapeType() == TopAbs_VERTEX:
                    assert gesamt
                    punkt = BRep_Tool.Pnt(topods.Vertex(form)).Coord()
                    assert punkt == pytest.approx((42,20,3))
                    g, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
                    np.testing.assert_allclose(g.linien[0][0], punkt, atol=1e-6)
                    xwerte.append(punkt[0])
                    continue
                kreis = BRepAdaptor_Curve(topods.Edge(form)).Circle()
                x,y,z = kreis.Location().Coord()
                assert (y,z,kreis.Radius()) == pytest.approx((20,3,2))
                xwerte.append(x)
            assert sorted(xwerte) == pytest.approx([16,42])
        finally:
            d.blatt.schliesse()
            d.close()

def test_gerundete_taschen_aus_pdf_mit_radius_und_flaechenbezug(app, tmp_path, monkeypatch):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Rundung.pdf", tmp_path/"Rundung.stp"
    _blatt(pdf, [(30,32,2)], tiefe="4× R3 ±0.1", taschen=[(15,16,16,10,3),(45,16,16,10,3)])
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.show()
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60","40","8")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            assert len(d.taschen) == 2 and len(d.ringe) == 1
            for j, wert in enumerate(("30","32","4"), 1):
                d.bohrtabelle.item(0,j).setText(wert)
            d.durchgehend.click()
            t = d.taschentabelle
            assert not t.isColumnHidden(7)
            for i, x in enumerate((15,45)):
                for j, wert in enumerate((str(x),"16","16","10"), 1):
                    t.item(i,j).setText(wert)
                t.setCurrentCell(i,1)
                if i == 0:
                    t.item(i,5).setText("4")
                    d.auswahl.setCurrentIndex(d.auswahl.findData(7))
                    d.ansicht.bereich.emit((.52,.86,.8,.96))
                    assert t.item(i,7).text() == "4× R3 ±0.1"
                else:
                    t.cellWidget(i,6).setCurrentIndex(1)
                    for falsch in ("","Ø3","2× R3","R1","R3 ±2"):
                        t.item(i,7).setText(falsch)
                        assert not d.speichern.isEnabled()
                    t.item(i,7).setText("R3 ±0.2")
            assert d.speichern.isEnabled()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, v)
            assert v.Mass() == pytest.approx(60*40*8-(16*10-(4-np.pi)*9)*12-32*np.pi)
            assert len(erg.pmi) == 17 and all(p.grafisch and p.semantisch for p in erg.pmi)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                radien = sorted((p for p in quelle if p.typ == "Size_Radius"), key=lambda p:p.oben)
                for p, (x,z,tol) in zip(radien, ((15,4,.1),(45,0,.2)), strict=True):
                    assert p.grenzen() == pytest.approx((3+tol,3-tol))
                    ecken = []
                    for f in p.flaechen:
                        s = BRepAdaptor_Surface(erg.modell.flaechen[f])
                        ort = s.Cylinder().Location()
                        assert s.Cylinder().Radius() == pytest.approx(3)
                        assert sorted(s.Value(0,v).Z() for v in (s.FirstVParameter(),s.LastVParameter())) == pytest.approx([z,8])
                        ecken.append((round(ort.X(),6),round(ort.Y(),6)))
                    assert sorted(ecken) == [(x-5,14),(x-5,18),(x+5,14),(x+5,18)]
                breiten = [p for p in quelle if p.nennwert == 16 and p.typ == "Location_LinearDistance"]
                assert sorted(sorted(round(BRepAdaptor_Surface(erg.modell.flaechen[i]).Plane().Location().X(),6)
                                     for i in p.flaechen) for p in breiten) == [[7,23],[37,53]]
                tiefe, = (p for p in quelle if p.nennwert == 4 and p.typ == "Location_LinearDistance")
                boden = min(tiefe.flaechen, key=lambda i:BRepAdaptor_Surface(erg.modell.flaechen[i]).Plane().Location().Z())
                brepgprop.SurfaceProperties(erg.modell.flaechen[boden], v)
                assert v.CentreOfMass().Coord() == pytest.approx((15,16,4))
        finally:
            d.blatt.schliesse()
            d.close()


def test_rundkontur_verlangt_vier_gleiche_boegen_und_geschlossenen_druckrand():
    from programm.kern.rundkontur import druckrand, passende_rundung, rundrechteck

    def pfad(radien, stuetzstellen=9):
        ecken = []
        for i, r in enumerate(radien):
            x = r if i in (0,3) else 60-r
            y = r if i in (0,1) else 40-r
            winkel = np.linspace(np.pi*(1+i/2), np.pi*(1.5+i/2), stuetzstellen)
            ecken.extend(np.column_stack((x+r*np.cos(winkel), y+r*np.sin(winkel))))
        return np.array([*ecken, ecken[0]])

    p = pfad([8]*4)
    q = rundrechteck(p)
    assert q == pytest.approx([0,0,60,40,8])
    assert rundrechteck(p[:-1]) is None
    assert rundrechteck(pfad([8,8,5,8])) is None
    assert rundrechteck(pfad([8]*4, 2)) is None
    assert rundrechteck(pfad([20]*4)) == pytest.approx([0,0,60,40,20])
    assert rundrechteck(pfad([19.9]*4)) is None
    winkel = np.linspace(0, 2*np.pi, 73)
    assert rundrechteck(np.column_stack((30*np.cos(winkel),20*np.sin(winkel)))) is None
    versatz = np.array([-1,-1,1,1,1])
    assert druckrand([(q-versatz,1),(q+versatz,-1)], False) == pytest.approx(q)
    assert druckrand([(q-versatz,1),(q+versatz,1)], False) is None
    assert druckrand([(q-versatz,1),(q+versatz,1)], True) == pytest.approx(q)
    y, x = np.mgrid[:41,:61]
    dx, dy = abs(x-30)-22, abs(y-20)-12
    d = np.hypot(dx.clip(0), dy.clip(0))+np.minimum(np.maximum(dx,dy),0)-8
    ring = abs(d) <= 1
    assert passende_rundung(ring,0,0,[q]) == pytest.approx(q)
    assert passende_rundung(d <= 1,0,0,[q]) is None
    ring[:5,30] = False
    assert passende_rundung(ring,0,0,[q]) is None


def test_bohrung_neben_gerundeter_taschenecke():
    from programm.kern.plattentasche import Taschenkontur, eckradiusmass, solltaschen
    from programm.kern.zeichnungsabgleich import lese_angabe
    from programm.kern.zeichnungskoerper import Plattenbohrung
    masse = [lese_angabe(s,1.) for s in ("60","40","8")]
    kontur = Taschenkontur((), .5, .5, 20/60, 16/40, 5/60)
    zeile = ("30","20","20","16","4","4X R5")
    assert eckradiusmass("3X R5",1.) is None
    durchmesser = lese_angabe("Ø2",1.)
    assert solltaschen([kontur],[zeile],masse,(600,400),[Plattenbohrung(20,12,durchmesser)])
    with pytest.raises(ValueError, match="Bohrung"):
        solltaschen([kontur],[zeile],masse,(600,400),[Plattenbohrung(21,13,durchmesser)])


def test_langloch_quer_und_hoch_mit_gesamtmass_im_step(app, tmp_path, monkeypatch):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.plausibilitaet import langlochenden
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Langloch.pdf", tmp_path/"Langloch.stp"
    _blatt(pdf, tiefe="16 ±0.1", taschen=[(15,16,16,6,3),(44,20,6,16,3)])
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60","40","8")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            assert [q.langloch for q in d.taschen] == [True,True]
            assert d.taschentabelle.isColumnHidden(7)
            for i, daten in enumerate((("15","16","16","6 ±0.04","4"),("44","20","6 ±0.03","16 ±0.2"))):
                for j, text in enumerate(daten, 1):
                    d.taschentabelle.item(i,j).setText(text)
            d.taschentabelle.cellWidget(1,6).setCurrentIndex(1)
            d.taschentabelle.setCurrentCell(0,3)
            d.auswahl.setCurrentIndex(d.auswahl.findData(3))
            d.ansicht.bereich.emit((.52,.86,.8,.96))
            assert d.taschentabelle.item(0,3).text() == "16 ±0.1"
            assert d.speichern.isEnabled()
            d.taschentabelle.item(0,3).setText("16 ±10")
            assert not d.speichern.isEnabled()
            assert "Grenzmaß" in d.status.text()
            d.taschentabelle.item(0,3).setText("16 ±0.1")
            d.speichern.click()
            erg = lade_alles(str(ziel))
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, v)
            assert v.Mass() == pytest.approx(60*40*8-(10*6+9*np.pi)*12)
            assert len(erg.pmi) == 12 and all(p.grafisch and p.semantisch for p in erg.pmi)
            from dataclasses import replace
            from programm.kern.plausibilitaet import geometrie
            for p in (p for p in erg.pmi if p.typ == "Location_LinearDistance_FromOuterToOuter"):
                assert not geometrie([p], erg.modell)
                assert geometrie([replace(p,nennwert=10)], erg.modell)
                g, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
                achse = 0 if p.oben == pytest.approx(.1) else 1
                linie = g.linien[2]
                assert sorted(linie[:,achse]) == pytest.approx([7,23] if achse == 0 else [12,28])
                np.testing.assert_allclose(linie[:,2], [8,8], atol=1e-6)
                assert np.linalg.norm(linie[1]-linie[0]) == pytest.approx(16)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                laengen = sorted((p for p in quelle if p.typ == "Location_LinearDistance_FromOuterToOuter"), key=lambda p:p.oben)
                for p, tol, punkte in zip(laengen,(.1,.2),([(7,16,8),(23,16,8)],[(44,12,8),(44,28,8)]),strict=True):
                    assert p.grenzen() == pytest.approx((16+tol,16-tol))
                    waende = [erg.modell.flaechen[j] for j in p.flaechen]
                    assert len(waende) == 2
                    for f in waende:
                        s = BRepAdaptor_Surface(f)
                        assert s.Cylinder().Radius() == pytest.approx(3)
                        assert s.LastUParameter()-s.FirstUParameter() == pytest.approx(np.pi)
                    a,b,_ = langlochenden(waende)
                    assert sorted([tuple(a.round(6)),tuple(b.round(6))]) == punkte
                breiten = sorted((p for p in quelle if p.nennwert == 6),key=lambda p:p.oben)
                for p, achse, lagen in zip(breiten,(0,1),([41,47],[13,19]),strict=True):
                    assert sorted(BRepAdaptor_Surface(erg.modell.flaechen[j]).Plane().Location().Coord()[achse]
                                  for j in p.flaechen) == pytest.approx(lagen)
                tiefe, = (p for p in quelle if p.nennwert == 4)
                assert sorted(BRepAdaptor_Surface(erg.modell.flaechen[j]).Plane().Location().Z()
                              for j in tiefe.flaechen) == pytest.approx([4,8])
        finally:
            d.blatt.schliesse()
            d.close()


def test_langloch_achsabstand_als_abgeleitetes_ziel_und_masslinie(app,tmp_path,monkeypatch):
    from dataclasses import replace
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.plausibilitaet import geometrie
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.vergleich_pmi import vergleiche_pmi
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Achsen.pdf", tmp_path/"Achsen.stp"
    _blatt(pdf,tiefe="10 ±0.1",taschen=[(15,16,16,6,3),(44,20,6,16,3)])
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc, pdf)
        try:
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60","40","8")):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            t = d.taschentabelle
            assert not t.isColumnHidden(8)
            for i, daten in enumerate((("15","16","","6 ±0.04","4"), ("44","20","6 ±0.03","16 ±0.2"))):
                for j, text in enumerate(daten,1):
                    t.item(i,j).setText(text)
            t.cellWidget(1,6).setCurrentIndex(1)
            assert not d.speichern.isEnabled()
            t.setCurrentCell(0,8)
            d.auswahl.setCurrentIndex(d.auswahl.findData(8))
            d.ansicht.bereich.emit((.52,.86,.8,.96))
            assert t.item(0,8).text() == "10 ±0.1" and d.speichern.isEnabled()
            for ungueltig in ("10 ±10","R10","12","10 H7"):
                t.item(1,8).setText(ungueltig)
                assert not d.speichern.isEnabled()
            t.item(1,8).setText("9.98–10.08")
            assert d.speichern.isEnabled()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            vol = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, vol)
            assert vol.Mass() == pytest.approx(60*40*8-(10*6+9*np.pi)*12)
            assert len(erg.pmi) == 13 and all(p.semantisch and p.grafisch for p in erg.pmi)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                gesamt, = (p for p in quelle if p.typ == "Location_LinearDistance_FromOuterToOuter")
                assert gesamt.grenzen() == pytest.approx((16.2,15.8))
                achsen = sorted((p for p in quelle if p.typ == "Location_LinearDistance"
                                 and 9.98 <= p.nennwert <= 10.08),key=lambda p:p.grenzmass)
                for p, grenzen, orte in zip(achsen, ((10.1,9.9),(10.08,9.98)),
                                            ([(10,16),(20,16)],[(44,15),(44,25)]),strict=True):
                    assert p.typ == "Location_LinearDistance" and p.grenzen() == pytest.approx(grenzen)
                    assert sorted(tuple(np.round(BRepAdaptor_Surface(erg.modell.flaechen[f]).Cylinder().Location().Coord()[:2],6))
                                  for f in p.flaechen) == orte
            datei = erg.modell.datei
            for p in (p for p in erg.pmi if p.nennwert == 10):
                assert p.mittenabstand and p.merkmal() == "Abstand zwischen Symmetriezentren"
                assert not geometrie([p], erg.modell)
                assert geometrie([replace(p,nennwert=16)], erg.modell)
                aenderung, = vergleiche_pmi([p],[replace(p,mittenabstand=False)])
                assert aenderung.status == "geaendert"
                refs = datei.entities[p.step_id].args("DIMENSIONAL_LOCATION")[2:]
                assert all(datei.get(ref).is_a("CENTRE_OF_SYMMETRY") for ref in refs)
                g, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
                linie = g.linien[2]
                assert np.linalg.norm(linie[1]-linie[0]) == pytest.approx(10.)
                achse = int(p.grenzmass)
                assert sorted(linie[:,achse]) == pytest.approx([15,25] if achse else [10,20])
                np.testing.assert_allclose(linie[:,2], [8,8], atol=1e-6)
        finally:
            d.blatt.schliesse()
            d.close()


def test_langloch_grenzmasse_schneiden_sich_nur_bei_gemeinsam_erreichbaren_werten():
    from programm.kern.plattentasche import _langlochmasse
    from programm.kern.zeichnungsabgleich import lese_angabe
    with pytest.raises(ValueError, match="unvereinbar"):
        _langlochmasse("16 +0.5/+0.3", lese_angabe("6 ±0.03",1.), "10 ±0.1")
    gesamt, kurz, achse = _langlochmasse("15.94–16.02", lese_angabe("5.98–6.12",1.), "10")
    assert gesamt.nennwert == pytest.approx(kurz.nennwert+achse.nennwert)
    assert gesamt.unten <= gesamt.nennwert <= gesamt.oben
    assert kurz.unten <= kurz.nennwert <= kurz.oben
    with pytest.raises(ValueError, match="widersprechen"):
        _langlochmasse("16", lese_angabe("6",1.), "9.8–9.95")


@pytest.mark.parametrize("form", ["eckig", "rund", "langloch"])
def test_taschenmittelpunkte_als_semantische_und_gezeichnete_lagemasse(app,tmp_path,monkeypatch,form):
    from dataclasses import replace
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from pypdfium2 import PdfDocument
    from programm.kern.plausibilitaet import ebene_zur_mittenebene, geometrie
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.vergleich_pmi import vergleiche_pmi
    from programm.ui.lader import lade_alles
    b,h = (16,6) if form == "langloch" else (12,8)
    r = (3,) if form != "eckig" else ()
    pdf,ziel = tmp_path/"Koordinaten.pdf",tmp_path/"Koordinaten.stp"
    _blatt(pdf,tiefe="15 ±0.2",taschen=[(x,16,b,h,*r) for x in (15,45)])
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Plattendialog(doc,pdf)
        try:
            d.einheit.setCurrentIndex(1)
            for feld,text in zip(d.texte,("60","40","8"),strict=True):
                feld.setText(text)
            d.ansicht.bereich.emit((.08,.1,.51,.52))
            t = d.taschentabelle
            assert t.rowCount() == 2
            for i,x in enumerate((15,45)):
                for j,text in enumerate((f"{x} ±0.2","15.9–16.1",str(b),str(h),"3"),1):
                    t.item(i,j).setText(text)
                if form == "rund":
                    t.item(i,7).setText("R3")
            t.cellWidget(1,6).setCurrentIndex(1)
            t.setCurrentCell(0,1)
            t.item(0,1).setText("")
            d.auswahl.setCurrentIndex(d.auswahl.findData(1))
            d.ansicht.bereich.emit((.52,.86,.80,.96))
            assert t.item(0,1).text() == "15 ±0.2"
            assert d.speichern.isEnabled(),d.status.text()
            d.speichern.click()
        finally:
            d.blatt.schliesse()
            d.close()
    erg = lade_alles(str(ziel))
    model = erg.modell
    mittel = [p for p in erg.pmi if p.mittenbezug is not None]
    assert len(mittel) == 4
    xcaf = [p for p in lies_pmi_xcaf(model) if p.typ == "Location_LinearDistance_FromOuterToCenter"]
    assert len(xcaf) == 4
    for p in mittel:
        assert p.grafisch and p.semantisch and p.merkmal() == "Abstand zur Mittelebene"
        assert len(p.flaechen) == 3 and p.mittenbezug in p.flaechen
        vergleich, = (m for m in xcaf if m.flaechen == p.flaechen)
        achse = int(p.grenzmass)
        tol = .1 if achse else .2
        for m in (p,vergleich):
            assert m.nennwert == p.nennwert and m.grenzen() == pytest.approx((p.nennwert+tol,p.nennwert-tol))
        ref = BRepAdaptor_Surface(model.flaechen[p.mittenbezug]).Plane()
        assert abs(ref.Axis().Direction().Coord()[achse]) == pytest.approx(1.)
        assert ref.Location().Coord()[achse] == pytest.approx(0)
        a,b,_ = ebene_zur_mittenebene(p,model)
        assert (a[achse],b[achse]) == pytest.approx((0,p.nennwert))
        assert b[0] == pytest.approx(15) or b[0] == pytest.approx(45)
        assert (b[1],b[2]) == pytest.approx((16,8))
        assert not geometrie([p],model) and geometrie([replace(p,nennwert=p.nennwert+1)],model)
        g, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
        linie = g.linien[2]
        assert list(linie[:,achse]) == pytest.approx([0,p.nennwert])
        assert list(linie[:,2]) == pytest.approx([8,8])
        lage = model.datei.get(p.step_id)
        ursprung,zielref = lage.args("DIMENSIONAL_LOCATION")[2:]
        assert model.datei.get(ursprung).is_a("SHAPE_ASPECT")
        assert model.datei.get(zielref).is_a("CENTRE_OF_SYMMETRY")
        anders = replace(p,mittenbezug=next(iter(p.flaechen-{p.mittenbezug})))
        assert vergleiche_pmi([p],[anders])[0].status == "geaendert"


def test_taschenlage_grenzen_an_rand_bohrung_und_zweiter_tasche():
    from programm.kern.plattentasche import Taschenkontur,solltaschen
    from programm.kern.zeichnungskoerper import Plattenbohrung,koordinatenmasse
    from programm.kern.zeichnungsabgleich import lese_angabe
    masse = plattenmasse(["60","40","8"],1.,(600,400))
    a = Taschenkontur((),.25,.4,.2,.2)
    b = Taschenkontur((),.5,.4,.2,.2)
    t1,t2 = ("15 ±2","16","12","8","3"),("30 ±1","16","12","8","3")
    def taschen(konturen,zeilen,bohrungen=()):
        return solltaschen(konturen,zeilen,masse,(600,400),bohrungen)
    with pytest.raises(ValueError,match="Plattenrand"):
        taschen([a],[("15 ±9",*t1[1:])])
    with pytest.raises(ValueError,match="andere Tasche"):
        taschen([a,b],[t1,t2])
    assert len(taschen([a,b],[t1,("30 ±0.9",*t2[1:])])) == 2
    kern = Plattenbohrung(28,16,lese_angabe("Ø2",1.),lagemasse=koordinatenmasse("28 ±2","16"))
    senkung = Plattenbohrung(28,16,lese_angabe("Ø6",1.),kern=0)
    assert taschen([a],[t1],[kern])
    with pytest.raises(ValueError,match="Bohrung"):
        taschen([a],[t1],[kern,senkung])
