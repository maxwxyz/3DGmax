import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets


def _kegelblatt(pfad, hoch, rechts_gross):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(225,225),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0,0,0,0))
    a,b = (32,56) if rechts_gross else (56,32)
    with QtGui.QPainter(pdf) as p:
        p.save()
        if hoch:
            p.setTransform(QtGui.QTransform(0,1,1,0,0,0))
        p.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black,1))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x,y) for x,y in ((30,100-a),(150,100-b),(150,100+b),(30,100+a))]))
        p.drawLine(20,100,158,100)
        p.restore()
        assert pdf.newPage()
        for y,text in ((40,"30 ±0.2"),(75,f"Ø{a//2} h6"),(110,f"Ø{b//2} h7"),(145,"22.62° ±0.01°")):
            p.drawText(30,y,text)


@pytest.mark.parametrize("hoch,rechts_gross",[(False,False),(True,True)])
def test_kegelstumpf_aus_pdf_mit_zwei_stirnkanten(app,tmp_path,monkeypatch,hoch,rechts_gross):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve,BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import topods
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    pdf,ziel = tmp_path/"welle.pdf",tmp_path/"welle.stp"
    _kegelblatt(pdf,hoch,rechts_gross)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Drehteildialog(doc,pdf)
        try:
            d.auswahl.setCurrentIndex(int(hoch))
            d.ansicht.bereich.emit((0,0,.8,.8))
            assert d._kegel()
            assert not d.auswahl.model().item(4).isEnabled()
            d.einheit.setCurrentIndex(1)
            d.seite.setValue(2)
            for i,y in zip((2,3,9,10),(40,75,110,145),strict=True):
                d.auswahl.setCurrentIndex(i)
                d.ansicht.bereich.emit((.08,(y-17)/225,.8,(y+5)/225))
            assert d.speichern.isEnabled(),d.status.text()
            winkel = d.tabelle.item(0,3)
            winkel.setText("45°")
            assert not d.speichern.isEnabled()
            winkel.setText("")
            assert d.speichern.isEnabled()
            winkel.setText("22.62° ±0.01°")
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 4 and all(p.grafisch and p.semantisch for p in erg.pmi)
            for quelle in (erg.pmi,lies_pmi_xcaf(erg.modell)):
                for p in quelle:
                    if p.typ == "Size_Diameter":
                        pos = {"h6":0,"h7":30}[p.passung]
                        assert p.kanten == 1
                        if quelle is erg.pmi:
                            k, = p.teilformen
                            kreis = BRepAdaptor_Curve(topods.Edge(k)).Circle()
                            assert kreis.Location().X() == pytest.approx(pos)
                            assert kreis.Radius()*2 == pytest.approx(p.nennwert)
                            g, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
                            x,y,z = g.linien[0][0]
                            assert x == pytest.approx(pos) and np.hypot(y,z)*2 == pytest.approx(p.nennwert)
                    elif p.typ == "Size_Angular":
                        k, = p.flaechen
                        assert np.rad2deg(abs(BRepAdaptor_Surface(erg.modell.flaechen[k]).Cone().SemiAngle())*2) == pytest.approx(22.619865)
                        assert (p.nennwert,p.oben) == pytest.approx((22.62,.01))
                    else:
                        assert p.nennwert == 30 and sorted(BRepAdaptor_Surface(erg.modell.flaechen[k]).Plane().Location().X() for k in p.flaechen) == pytest.approx([0,30])
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form,v)
            assert v.Mass() == pytest.approx(np.pi*10*(14**2+14*8+8**2))
        finally:
            d.blatt.schliesse()
            d.close()


def test_kegel_braucht_gerade_geschlossene_flanken_und_einen_massstab():
    from programm.kern.drehkegel import kegelkontur,kegelmasse
    from programm.kern.drehzeichnung import drehmasse
    bild = np.full((100,160,3),255,np.uint8)
    for x in range(20,141):
        rad = round(30-(x-20)*.15)
        for y in (48-rad,48+rad):
            bild[y:y+2,x] = 0
    for x,rad in ((20,30),(140,12)):
        bild[48-rad:50+rad,x] = 0
    box = (0,0,1,1)
    profil = kegelkontur(bild,box)
    assert profil is not None
    masse = drehmasse([profil],[("30","Ø15")],1)
    pruefen = lambda ende,winkel: kegelmasse(profil,masse,ende,winkel,1)
    assert pruefen("Ø6","17,06°")[1].nennwert == 17.06
    for ende,winkel in (("Ø5",""),("Ø6 ±9",""),("Ø6","17.09°"),("Ø6","17.1° ±0.01°")):
        with pytest.raises(ValueError):
            pruefen(ende,winkel)
    for fehler in ("flanke","stirn","bohrung","zusatz","gebogen"):
        kopie = bild.copy()
        if fehler == "flanke":
            kopie[:44,60:68] = 255
        elif fehler == "stirn":
            kopie[40:45,20] = 255
        elif fehler == "bohrung":
            kopie[44,20:141] = 0
            kopie[53,20:141] = 0
        elif fehler == "zusatz":
            kopie[25:30,48] = 0
        else:
            for x in range(40,120):
                weg = round(3*np.sin((x-40)*np.pi/80))
                kopie[:48,x] = np.roll(kopie[:48,x],weg,axis=0)
                kopie[50:,x] = np.roll(kopie[50:,x],-weg,axis=0)
        assert kegelkontur(kopie,box) is None,fehler
