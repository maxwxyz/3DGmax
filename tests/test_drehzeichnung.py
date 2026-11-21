import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern.drehzeichnung import drehkontur, drehmasse


def _konturbild():
    bild = np.full((84,149,3),255,np.uint8)
    for x1,x2,r in ((8,48,28),(48,96,16),(96,136,28)):
        bild[41-r:43-r,x1:x2+2] = 0
        bild[41+r:43+r,x1:x2+2] = 0
        bild[41-r:43+r,x1:x1+2] = 0
        bild[41-r:43+r,x2:x2+2] = 0
    bild[41:43,2:146:3] = 0
    return bild


def test_drehkontur_erkennt_nur_vollstaendige_symmetrische_stufen():
    bild = _konturbild()
    box = (0,0,1,1)
    for daten, hoch in ((bild,False),(bild.transpose(1,0,2),True)):
        sitze = drehkontur(daten,box,hoch)
        assert [s.laenge for s in sitze] == pytest.approx([40,48,40])
        assert [s.durchmesser for s in sitze] == pytest.approx([56,32,56])
    for stoerung in ("nut","bohrung","halbkante","offen","fase","asymmetrisch"):
        falsch = bild.copy()
        if stoerung == "nut":
            falsch[20:26,16:31] = 0
        elif stoerung == "bohrung":
            falsch[37:39,8:136] = 0
            falsch[45:47,8:136] = 0
        elif stoerung == "halbkante":
            falsch[42:55,48:50] = 255
        elif stoerung == "offen":
            falsch[11:16,20:28] = 255
        elif stoerung == "fase":
            falsch[13:19,8:14] = 255
            for dx in range(6):
                falsch[18-dx:20-dx,8+dx] = 0
        else:
            falsch[25:27,50:96] = 255
            falsch[21:23,50:96] = 0
        assert not drehkontur(falsch,box), stoerung
    assert not drehkontur(bild,(.09,0,1,1))


def _wellenblatt(pfad):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(300,180),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0,0,0,0))
    with QtGui.QPainter(pdf) as p:
        kontur = [(0,10),(12,10),(12,6),(30,6),(30,10),(38,10),(38,-10),(30,-10),(30,-6),(12,-6),(12,-10),(0,-10)]
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(30+4*x,75-4*r) for x,r in kontur]))
        for x in (12,30):
            p.drawLine(30+4*x,51,30+4*x,99)
        assert pdf.newPage()
        p.drawText(32,151,"12 ±0.1")
        p.drawText(152,151,"Ø20 ±0.05")


def test_vollwelle_aus_dateimenue_mit_gleichen_sitzen_und_eigenen_masszielen(fenster,tmp_path,monkeypatch):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.zeichnungsabgleich import befund
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Welle.pdf", tmp_path/"Welle.stp"
    _wellenblatt(pdf)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getOpenFileName",lambda *args:(str(pdf),"PDF"))
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(ziel),"STEP"))
    aktion = fenster.aktionen["drehzeichnung"]
    assert aktion.isEnabled()
    aktion.trigger()
    d = fenster.findChild(Drehteildialog)
    try:
        assert d.isVisible() and not d.speichern.isEnabled()
        d.einheit.setCurrentIndex(1)
        d.ansicht.bereich.emit((.05,.10,.7,.70))
        assert len(d.sitze) == 3
        d.seite.setValue(2)
        d.tabelle.setCurrentCell(0,0)
        for i, box in ((2,(.06,.71,.41,.90)),(3,(.47,.71,.93,.90))):
            d.auswahl.setCurrentIndex(i)
            d.ansicht.bereich.emit(box)
        assert d.tabelle.item(0,0).text() == "12 ±0.1"
        assert d.tabelle.item(0,1).text() == "Ø20 ±0.05"
        d.seite.setValue(1)
        assert d.massmarken[0,1].seite == 1
        for i, werte in enumerate((("18","Ø12 h6"),("8 ±0.02","Ø20 ±0.2")),1):
            d.ansicht.gewaehlt.emit(d.sitze[i])
            assert d.tabelle.currentRow() == i
            for j,text in enumerate(werte):
                d.tabelle.item(i,j).setText(text)
        assert d.speichern.isEnabled()
        for j,falsch in ((0,"17"),(1,"12"),(1,"Ø12 ±8")):
            item = d.tabelle.item(1,j)
            alt = item.text()
            item.setText(falsch)
            assert not d.speichern.isEnabled()
            item.setText(alt)
        d.speichern.click()
        erg = lade_alles(str(ziel))
        assert len(erg.pmi) == 6 and all(p.grafisch and p.semantisch for p in erg.pmi)
        prop = GProp_GProps()
        brepgprop.VolumeProperties(erg.modell.form,prop)
        assert prop.Mass() == pytest.approx(np.pi*(100*20+36*18))
        for p in erg.pmi:
            grafik, = (g for g in erg.grafik.values() if p.step_id in g.pmi_ids)
            if p.typ == "Size_Diameter":
                x,y,z = grafik.linien[0][0]
                assert {20.:10.,12.:6.}[p.nennwert] == pytest.approx(np.hypot(y,z),abs=1e-5)
                x1,x2 = {None:(12,30), .05:(0,12), .2:(30,38)}[p.oben]
                assert x1 < x < x2
            else:
                assert sorted(grafik.linien[2][:,0]) == pytest.approx({12:[0,12],18:[12,30],8:[30,38]}[p.nennwert])
        for quelle in (erg.pmi,lies_pmi_xcaf(erg.modell)):
            kreise = []
            for p in quelle:
                fl = [BRepAdaptor_Surface(erg.modell.flaechen[i]) for i in p.flaechen]
                if p.typ == "Size_Diameter":
                    wand, = fl
                    assert 2*wand.Cylinder().Radius() == pytest.approx(p.nennwert)
                    if p.nennwert == 12:
                        assert p.passung == "h6"
                    x1,x2 = sorted(wand.Value(0,v).X() for v in (wand.FirstVParameter(),wand.LastVParameter()))
                    kreise.append((x1,x2,p.oben))
                else:
                    assert p.typ == "Location_LinearDistance"
                    paar = sorted(f.Plane().Location().X() for f in fl)
                    assert paar == pytest.approx({12:[0,12],18:[12,30],8:[30,38]}[p.nennwert])
            assert sorted(kreise) == [(0,12,.05),(12,30,None),(30,38,.2)]
            angabe = d.massmarken[0,1]
            sitz1, sitz3 = sorted((p for p in quelle if p.nennwert == 20),key=lambda p:p.oben)
            angabe.modell = sitz1
            assert befund(angabe,1.) == "gleich"
            angabe.modell = sitz3
            assert befund(angabe,1.) == "geaendert"
        d.auswahl.setCurrentIndex(0)
        d.ansicht.bereich.emit((.1,.72,.6,.9))
        assert not d.speichern.isEnabled() and not d.sitze
    finally:
        d.close()


def test_drehmasse_einheiten_und_gemeinsamer_massstab():
    kontur = drehkontur(_konturbild(),(0,0,1,1))
    werte = [("0.5 in","Ø0.7 in"),("0.6 in","Ø0.4 in"),("0.5 in","Ø0.7 in")]
    assert drehmasse(kontur,werte,None)[0][0].nennwert == pytest.approx(12.7)
    for falsch in ([("0.5","Ø0.7"), *werte[1:]], [werte[0], ("0.5 in","Ø0.4 in"),werte[2]]):
        with pytest.raises(ValueError):
            drehmasse(kontur,falsch,None)


def _hohlwellenblatt(pfad, spur):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(300,180),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0,0,0,0))
    with QtGui.QPainter(pdf) as p:
        kontur = [(0,10),(12,10),(12,6),(30,6),(30,-6),(12,-6),(12,-10),(0,-10)]
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(30+4*x,75-4*r) for x,r in kontur]))
        p.drawLine(78,51,78,99)
        if spur:
            p.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black,1,QtCore.Qt.PenStyle.DashLine))
            for y in (59,91):
                p.drawLine(30,y,30+4*spur,y)
            p.setPen(QtCore.Qt.GlobalColor.black)
        assert pdf.newPage()
        for radius in (10,25):
            p.drawEllipse(QtCore.QPointF(70,65),radius,radius)
        p.drawText(145,148,"Ø8 H7 THRU ALL")


@pytest.mark.parametrize("spur",[30,0])
def test_hohlwelle_aus_zwei_ansichten_und_step_rundlauf(app,tmp_path,monkeypatch,spur):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.vergleich_geo import _nachbarn
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Hohl.pdf", tmp_path/"Hohl.stp"
    _hohlwellenblatt(pdf,spur)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Drehteildialog(doc,pdf)
        try:
            d.einheit.setCurrentIndex(1)
            d.ansicht.bereich.emit((.05,.1,.6,.7))
            assert len(d.sitze) == 2
            for i,(laenge,dm) in enumerate((("12","Ø20"),("18","Ø12 h6"))):
                d.tabelle.item(i,0).setText(laenge)
                d.tabelle.item(i,1).setText(dm)
            assert (d.spur is not None) == bool(spur)
            assert d.speichern.isEnabled() == (not spur)
            d.bohrtext.setText("Ø8 H7")
            assert d.speichern.isEnabled() == bool(spur)
            d.seite.setValue(2)
            d.auswahl.setCurrentIndex(4)
            d.ansicht.bereich.emit((.13,.18,.35,.55))
            assert d.stirn and d.stirn[0]/d.stirn[-1] == pytest.approx(.4,abs=.001)
            assert d.speichern.isEnabled() == bool(spur)
            for falsch in ("Ø11 THRU","Ø8 ±4 THRU","Ø8 U8 THRU","Ø4 THRU","2X Ø8 THRU"):
                d.bohrtext.setText(falsch)
                assert not d.speichern.isEnabled()
            d.auswahl.setCurrentIndex(5)
            d.ansicht.bereich.emit((.45,.7,.98,.87))
            assert d.bohrtext.text() == "Ø8 H7 THRU ALL" and d.speichern.isEnabled()
            assert "Hohlwelle" in d.status.text()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            prop = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form,prop)
            assert prop.Mass() == pytest.approx(np.pi*(100*12+36*18-16*30))
            assert len(erg.pmi) == 5 and all(p.semantisch and p.grafisch for p in erg.pmi)
            for quelle in (erg.pmi,lies_pmi_xcaf(erg.modell)):
                bore, = (p for p in quelle if p.nennwert == 8)
                assert bore.passung == "H7"
                f, = bore.flaechen
                s = BRepAdaptor_Surface(erg.modell.flaechen[f])
                assert s.Cylinder().Radius() == pytest.approx(4)
                nachbarn = _nachbarn(erg.modell.flaechen,erg.modell.flaechen_index)[f]
                assert sorted(BRepAdaptor_Surface(erg.modell.flaechen[k]).Plane().Location().X()
                              for k in nachbarn) == pytest.approx([0,30])
            bore, = (p for p in erg.pmi if p.nennwert == 8)
            g, = (g for g in erg.grafik.values() if bore.step_id in g.pmi_ids)
            x,y,z = g.linien[0][0]
            assert 0 < x < 30 and np.hypot(y,z) == pytest.approx(4,abs=1e-5)
            d.auswahl.setCurrentIndex(4)
            d.ansicht.bereich.emit((.2,.31,.27,.43))
            assert not d.speichern.isEnabled()
            d.stirn_entfernen.click()
            assert d.speichern.isEnabled() == bool(spur)
        finally:
            d.blatt.schliesse()
            d.close()


def test_axialspur_erfordert_zwei_koaxiale_waende_und_die_volle_laenge(app,tmp_path):
    from pypdfium2 import PdfDocument
    from programm.kern.drehzeichnung import drehprofil
    from programm.kern.zeichnungsblatt import Zeichnungsblatt
    pdf = tmp_path/"Sackloch.pdf"
    _hohlwellenblatt(pdf,14)
    with PdfDocument(pdf) as doc:
        b = Zeichnungsblatt(doc,0)
        try:
            assert drehprofil(b.bild,(.05,.1,.6,.7)) == ([],None)
        finally:
            b.schliesse()
    bild = _konturbild()
    for y in (34,48):
        bild[y:y+2,8:138] = 0
    sitze,spur = drehprofil(bild.transpose(1,0,2),(0,0,1,1),True)
    assert len(sitze) == 3 and spur == pytest.approx(14)
    for bereich in ((slice(34,36),slice(60,70)), (slice(48,50),slice(9,45))):
        defekt = bild.copy()
        defekt[bereich] = 255
        assert drehprofil(defekt,(0,0,1,1)) == ([],None)


def test_schnittkontur_der_hohlwelle_mit_offenen_stirnflaechen():
    from programm.kern.drehzeichnung import drehprofil
    bild = _konturbild()
    for x in (8,48,96,136):
        bild[35:49,x:x+2] = 255
    for y in (34,48):
        bild[y:y+2,8:138] = 0
    sitze, spur = drehprofil(bild,(0,0,1,1))
    assert [s.laenge for s in sitze] == pytest.approx([40,48,40])
    assert spur == pytest.approx(14)
    bild[36:40,8:10] = 0
    assert drehprofil(bild,(0,0,1,1)) == ([],None)


def test_stirnringe_pruefen_alle_ringe_und_gedruckte_kontur(tmp_path):
    from programm.kern.axialbohrung import stirnringe
    from programm.kern.drehzeichnung import axiales_bohrmass, schreibe_drehteil
    from programm.kern.zeichnungsansicht import Blattkreis
    y,x = np.mgrid[:90,:90]
    abstand = np.hypot(y-45,x-45)
    kreise = [Blattkreis(45,45,r) for r in (12,18,30)]
    bild = np.full((90,90,3),255,np.uint8)
    for k in kreise:
        bild[abs(abstand-k.r) <= 1] = 0
    box = (0,0,1,1)
    ringe = stirnringe(bild,box,kreise)
    assert ringe == (24,36,60)
    kontur = drehkontur(_konturbild(),box)
    masse = drehmasse(kontur,[("10","Ø14"),("12","Ø8"),("10","Ø14")],1.)
    with pytest.raises(ValueError):
        axiales_bohrmass(kontur,masse,None,(24,48,84),"DURCHGANG Ø4 H7",1.)
    assert axiales_bohrmass(kontur,masse,None,(24,84),"DURCHGANG Ø4 H7",1.).passung == "H7"
    assert axiales_bohrmass(kontur[:2],masse[:2],None,(24,48,84),"Ø4 THRU",1.).nennwert == 4
    with pytest.raises(ValueError):
        axiales_bohrmass(kontur,masse,None,(24,58,84),"Ø4 THRU",1.)
    ziel = tmp_path/"vorhanden.stp"
    ziel.write_bytes(b"vorhanden")
    with pytest.raises(ValueError):
        schreibe_drehteil(ziel,masse,masse[1][1])
    assert ziel.read_bytes() == b"vorhanden"
    assert not stirnringe(bild,box,[Blattkreis(48,45,12),*kreise[1:]])
    assert not stirnringe(bild,(.3,0,1,1),kreise)
    for y0,x0 in ((45,58),(55,55)):
        defekt = bild.copy()
        defekt[y0-2:y0+2,x0-2:x0+2] = 255 if y0 == 45 else 0
        assert not stirnringe(defekt,box,kreise)
