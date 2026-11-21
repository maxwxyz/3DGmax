import csv
from pathlib import Path

import pytest
from PySide6 import QtCore,QtGui,QtWidgets


def _blatt(pfad, winkel, umgekehrt, zusatz=False, offen=False, schrift=""):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(1900,1230),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF())
    bild = QtGui.QImage(str(Path(__file__).parent/"daten/nist_d2mi_904_4x_durchmesser.png"))
    with QtGui.QPainter(pdf) as p:
        p.translate(870,600)
        p.rotate(winkel)
        # Alle Bohrungen treffen die Modelllage unter einer unabhaengigen Blattdrehung.
        for x,y,r in ((8,7,2),(29,9,2),(13,29,3),(40,25,4)):
            p.drawEllipse(QtCore.QPointF(5*x-275,5*y+60),5*r,5*r)
        p.save()
        if umgekehrt:
            p.translate(154,0)
            p.rotate(180)
        if schrift:
            font = QtGui.QFont("Helvetica")
            font.setPixelSize(20)
            pfad = QtGui.QPainterPath()
            pfad.addText(5,7,font,schrift)
            p.fillPath(pfad,QtCore.Qt.GlobalColor.black)
        else:
            p.drawImage(QtCore.QRectF(5,-8,144,16),bild)
        if zusatz:
            p.drawRect(155,-4,6,8)
            p.drawLine(155,-4,161,4)
        p.restore()
        p.drawLine(-72,0,0,0)
        tip = QtCore.QPointF(-225,95)
        knie = QtCore.QPointF(-72,0)
        p.drawLine(knie,tip)
        if offen:
            p.drawLine(knie,QtCore.QPointF(-77,-33))
        richtung = (knie-tip)
        richtung /= (richtung.x()**2+richtung.y()**2)**.5
        quer = QtCore.QPointF(-richtung.y(),richtung.x())*2
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtCore.Qt.GlobalColor.black)
        p.drawPolygon(QtGui.QPolygonF([tip,tip+richtung*10+quer,tip+richtung*10-quer]))


@pytest.mark.parametrize("winkel,umgekehrt,drehung,zusatz,offen",[
    (28,False,0,False,False),(-38,True,90,False,False),(147,False,270,False,False),
    (28,False,0,True,False),(147,False,0,False,True)])
def test_entdeckt_vollstaendige_geneigte_masszeile_am_genauen_hinweisende(app,tmp_path,monkeypatch,winkel,umgekehrt,drehung,zusatz,offen):
    from pypdfium2 import PdfDocument
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    from programm.kern.zeichnungsansicht import modellkreise
    from test_zeichnungsansicht import _teil
    datei = tmp_path/"Geneigtes Mass.pdf"
    _blatt(datei,winkel,umgekehrt,zusatz,offen)
    teil = _teil()
    achsen, = modellkreise(teil)
    erwartet = next(k.flaechen for k in achsen if k.mitte == (8,7))
    with PdfDocument(datei) as doc:
        doc[0].set_rotation(drehung)
        d = Zeichnungsabgleich(doc,[],lambda _:None,(str(datei),""),einzelteil=teil)
        try:
            def abgleichen():
                d.registrieren.click()
                d.ansicht.bereich.emit((0,0,1,1))
                assert d.auftrag.wait(10000)
                app.processEvents()
            assert not d.seiten[0]
            abgleichen()
            assert len(d.kreise[0]) == 4
            if zusatz or offen:
                assert not d.seiten[0]
                return
            a, = d.seiten[0]
            assert a.text == "4X⌀.215-.225" and len(a.hinweisenden) == 1
            assert d.zielvorschlaege[a].flaechen == erwartet
            d.waehle(a)
            _,rahmen = next(m for m in d.ansicht.marken if m[0] is a)
            assert len(rahmen.polygon()) == len(a.zeilenecken) == 4
            vorschau = d.ausschnitt.pixmap()
            assert vorschau.width() > 4*vorschau.height() and vorschau.height() > 20
            csvziel = tmp_path/"Pruefung.csv"
            monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(csvziel),"CSV"))
            d._export()
            with csvziel.open(encoding="utf-8-sig") as f:
                zeile = next(csv.DictReader(f,delimiter=";"))
            for titel,gruppe in (("Ecken der Maßzeile in Leserichtung (x/Breite, y/Höhe)",a.zeilenecken),
                                 ("Textseitige Hinweisenden (x/Breite, y/Höhe)",a.hinweisenden)):
                for feld,xy in zip(zeile[titel].split(" | "),gruppe,strict=True):
                    assert tuple(map(float,feld.split())) == pytest.approx(xy,abs=1e-6)
            abgleichen()
            assert d.seiten[0] == [a] and d.zielvorschlaege[a].flaechen == erwartet
            d.entfernen.click()
            abgleichen()
            assert not d.seiten[0]
        finally:
            d.blatt.schliesse()
            d.close()


@pytest.mark.parametrize("text,befund", [("2X R2","gleich"),("2X CR2","geaendert"),("2X B2",None)])
def test_gefuelltes_radiusmass_am_bohrbild(app, tmp_path, text, befund):
    from pypdfium2 import PdfDocument
    from programm.kern import zeichnungsabgleich as za
    from programm.kern.pmi import Pmi
    from programm.kern.zeichnungsansicht import modellkreise
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    from test_zeichnungsansicht import _teil

    datei = tmp_path / "Radien.pdf"
    _blatt(datei,27,False,schrift=text)
    teil = _teil()
    kreise, = modellkreise(teil)
    waende = set().union(*(k.flaechen for k in kreise if k.r == 2))
    radius = Pmi("mass","Size_Radius",nennwert=2.,flaechen=waende,nummer=1)
    durchmesser = Pmi("mass","Size_Diameter",nennwert=2.,flaechen=waende,nummer=2)
    with PdfDocument(datei) as doc:
        d = Zeichnungsabgleich(doc,[durchmesser,radius],lambda _:None,(str(datei),""),einzelteil=teil)
        try:
            d.einheit.setCurrentIndex(1)
            d.registrieren.click()
            d.ansicht.bereich.emit((0,0,1,1))
            assert d.auftrag.wait(10000)
            app.processEvents()
            if befund is None:
                assert not d.seiten[0]
                return
            a, = d.seiten[0]
            assert a.text == text.replace(" ","")
            d.waehle(a)
            assert d.zuordnung.currentData() == d.modellindex[id(radius)]
            d.bestaetigen.click()
            assert a.modell is radius and len(a.musterziele) == 2
            assert za.befund(a,1.) == befund
        finally:
            d.blatt.schliesse()
            d.close()
