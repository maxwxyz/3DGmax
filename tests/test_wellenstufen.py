import numpy as np
import pytest
from PySide6 import QtCore,QtGui,QtWidgets


def _stufenblatt(pfad,profil,rechts,hoch,winkel=None,gesamt=False):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(300,180),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0,0,0,0))
    def sx(tiefe):
        return 30+4*(30-tiefe if rechts else tiefe)
    with QtGui.QPainter(pdf) as p:
        p.save()
        if hoch:
            p.setTransform(QtGui.QTransform(0,1,1,0,0,0))
        aussen = [(0,10),(12,10),(12,6),(30,6),(30,-6),(12,-6),(12,-10),(0,-10)]
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(30+4*x,75-4*r) for x,r in aussen]))
        p.drawLine(78,51,78,99)
        if winkel != 90:
            p.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black,1,QtCore.Qt.PenStyle.DashLine))
        start = 0
        for i,(dm,tiefe) in enumerate(profil):
            ende = tiefe or 30
            spitz = winkel and i == len(profil)-1
            if spitz:
                hoehe = dm/(2*np.tan(np.deg2rad(winkel)/2))
                if gesamt:
                    ende -= hoehe
            for sign in (-1,1):
                y = 75+sign*2*dm
                p.drawLine(QtCore.QPointF(sx(start),y),QtCore.QPointF(sx(ende),y))
                if spitz:
                    p.drawLine(QtCore.QPointF(sx(ende),y),QtCore.QPointF(sx(ende+hoehe),75))
                if i+1 < len(profil):
                    p.drawLine(sx(tiefe),y,sx(tiefe),75+sign*2*profil[i+1][0])
            start = tiefe
        if tiefe and not winkel:
            p.drawLine(sx(tiefe),75-2*dm,sx(tiefe),75+2*dm)
        p.restore()
        assert pdf.newPage()
        for dm in [20,*([12] if rechts else []),*(d for d,_ in profil)]:
            p.drawEllipse(QtCore.QPointF(60,62),1.4*dm,1.4*dm)
        for i,(dm,tiefe) in enumerate(profil):
            y = 48+36*i
            p.drawText(105,y,f"Ø{dm} H{7+i}"+(" THRU" if tiefe is None else ""))
            if tiefe:
                p.drawText(208,y,f"{tiefe} ±0.1")
        if winkel:
            p.drawText(105,151,f"{winkel}° ±1°")


@pytest.mark.parametrize("rechts,hoch,profil",[
    (False,False,[(10,6),(6,None)]),
    (True,True,[(10,6),(6,14)]),
    (False,True,[(14,4),(10,9),(6,14)]),
    (True,False,[(10,18),(6,None)]),
])
def test_wellenstufen_vom_pdf_mit_gemeinsamem_tiefenbezug(app,tmp_path,monkeypatch,rechts,hoch,profil):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.axialbohrung import Stufenbohrspur
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.vergleich_geo import _nachbarn
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    pdf, ziel = tmp_path/"Schnitt.pdf", tmp_path/"Stufen.step"
    _stufenblatt(pdf,profil,rechts,hoch)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Drehteildialog(doc,pdf)
        try:
            d.einheit.setCurrentIndex(1)
            d.auswahl.setCurrentIndex(int(hoch))
            d.ansicht.bereich.emit((.05,.05,.5,.94) if hoch else (.05,.1,.6,.7))
            assert isinstance(d.spur,Stufenbohrspur) and d.spur.von_rechts == rechts
            for i,werte in enumerate((("12 ±0.03","Ø20"),("18","Ø12 h6"))):
                for j,wert in enumerate(werte):
                    d.tabelle.item(i,j).setText(wert)
            assert not d.bohrstufen.isHidden() and d.bohrstufen.rowCount() == len(profil)
            d.seite.setValue(2)
            d.auswahl.setCurrentIndex(4)
            d.ansicht.bereich.emit((.075,.12,.32,.56))
            assert len(d.stirn) == len(profil)+1+int(rechts)
            for i,(_,tiefe) in enumerate(profil):
                d.bohrstufen.setCurrentCell(i,0)
                assert not d.speichern.isEnabled()
                y = 48+i*36
                for index,x1,x2 in ((5,100,199),(6,204,299)):
                    if index == 6 and tiefe is None:
                        assert not d.auswahl.model().item(6).isEnabled()
                        continue
                    d.auswahl.setCurrentIndex(index)
                    d.ansicht.bereich.emit((x1/300,(y-20)/180,x2/300,(y+6)/180))
            assert d.speichern.isEnabled(), d.status.text()
            item = d.bohrstufen.item(0,1)
            original = item.text()
            item.setText("1")
            assert not d.speichern.isEnabled()
            item.setText(original)
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 4+len(profil)+sum(t is not None for _,t in profil)
            assert all(p.grafisch and p.semantisch for p in erg.pmi)
            nachbarn = _nachbarn(erg.modell.flaechen,erg.modell.flaechen_index)
            def pos(t):
                return 30-t if rechts else t
            def ebene(k):
                return BRepAdaptor_Surface(erg.modell.flaechen[k]).Plane().Location().X()
            for quelle in (erg.pmi,lies_pmi_xcaf(erg.modell)):
                start, volumen = 0, 100*12+36*18
                for i,(dm,tiefe) in enumerate(profil):
                    ende = tiefe or 30
                    volumen -= (dm/2)**2*(ende-start)
                    p, = (p for p in quelle if p.passung == f"H{7+i}")
                    wand, = p.flaechen
                    assert p.nennwert == dm
                    assert sorted(ebene(k) for k in nachbarn[wand]) == pytest.approx(sorted([pos(start),pos(ende)]))
                    if not i:
                        eintritt, = (k for k in nachbarn[wand] if abs(ebene(k)-pos(0)) < 1e-6)
                    if tiefe:
                        boden, = (k for k in nachbarn[wand] if abs(ebene(k)-pos(ende)) < 1e-6)
                        mass, = (p for p in quelle if p.typ == "Location_LinearDistance" and p.nennwert == tiefe and p.oben == .1)
                        assert mass.flaechen == {eintritt,boden} and mass.unten == pytest.approx(-.1)
                        if quelle is erg.pmi:
                            g, = (g for g in erg.grafik.values() if mass.step_id in g.pmi_ids)
                            assert sorted(g.linien[2][:,0]) == pytest.approx(sorted([pos(0),pos(ende)]))
                    start = ende
            prop = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form,prop)
            assert prop.Mass() == pytest.approx(np.pi*volumen)
            d.auswahl.setCurrentIndex(0)
            d.ansicht.bereich.emit((.05,.01,.25,.07))
            assert d.bohrstufen.rowCount() == 0 and not d.speichern.isEnabled()
        finally:
            d.blatt.schliesse()
            d.close()


def _schnittbild():
    bild = np.full((91,140,3),255,np.uint8)
    mitte = 45
    for sign in (-1,1):
        for x1,x2,r in ((8,68,30),(68,128,24),(8,68,16),(68,105,8)):
            bild[mitte+sign*r,x1:x2+1] = 0
        for x,r1,r2 in ((8,16,30),(68,24,30),(68,8,16)):
            y1,y2 = sorted((mitte+sign*r1,mitte+sign*r2))
            bild[y1:y2+1,x] = 0
    bild[21:70,128] = 0
    bild[37:54,105] = 0
    return bild


def test_stufen_im_offenen_schnitt_und_unvollstaendige_kanten():
    from programm.kern.axialbohrung import Stufenbohrspur
    from programm.kern.drehzeichnung import drehprofil
    bild = _schnittbild()
    box = (0,0,1,1)
    sitze,spur = drehprofil(bild,box)
    assert len(sitze) == 2 and spur == Stufenbohrspur(((32,60),(16,97)),False)
    for fehler in ("unterer Absatz fehlt","Boden fehlt","Wand unterbrochen","schiefer Absatz","zweite Öffnung"):
        defekt = bild.copy()
        if fehler == "unterer Absatz fehlt":
            defekt[55:60,68] = 255
        elif fehler == "Boden fehlt":
            defekt[38:53,105] = 255
        elif fehler == "Wand unterbrochen":
            defekt[37,75:84] = 255
        elif fehler == "schiefer Absatz":
            defekt[30:37,68] = 255
            for y in range(30,37):
                defekt[y,68+(y-30)//2] = 0
        else:
            defekt[40:50,128] = 255
        assert drehprofil(defekt,box) == ([],None), fehler


def test_stufengrenzen_schuetzen_absatz_und_vorhandene_datei(tmp_path):
    from programm.kern.drehzeichnung import schreibe_drehteil
    from programm.kern.zeichnungsabgleich import lese_angabe
    def mass(text):
        return lese_angabe(text,1.)
    masse = [(mass("12"),mass("Ø20")),(mass("18"),mass("Ø12"))]
    ziel = tmp_path/"Ergebnis.stp"
    ziel.write_bytes(b"bestehende Datei")
    for d1,t1,d2,t2 in (("Ø10 ±2","6","Ø8","14"),("Ø10","6 ±2","Ø8","9 ±1"),
                         ("Ø14","11 ±1","Ø6","14"),("Ø10","6","Ø6","29 ±1")):
        with pytest.raises(ValueError):
            schreibe_drehteil(ziel,masse,mass(d2),mass(t2),False,[(mass(d1),mass(t1))])
        assert ziel.read_bytes() == b"bestehende Datei"


def test_gemeinsamer_massstab_und_stirnansicht_bis_zur_kernbohrung():
    from programm.kern.axialbohrung import Stufenbohrspur
    from programm.kern.drehzeichnung import Sitzkontur,drehmasse,stufenmasse
    kontur = [Sitzkontur((),60,100),Sitzkontur((),90,60)]
    masse = drehmasse(kontur,[("12","Ø20"),("18","Ø12")],1.)
    spur = Stufenbohrspur(((50,30),(30,None)),True)
    werte = [("Ø10 H7","6"),("Ø6 H8 THRU","")]
    ringe = (12,20,24,40)
    assert len(stufenmasse(kontur,masse,spur,ringe,werte,1.)) == 2
    for stirn,zeilen in (((),werte),((12,20,40),werte),((20,24,40),werte),
                         (ringe,[("Ø10 THRU","6"),werte[1]]),
                         (ringe,[werte[0],("Ø6","24")]),(ringe,[("Ø10","7"),werte[1]])):
        with pytest.raises(ValueError):
            stufenmasse(kontur,masse,spur,stirn,zeilen,1.)


@pytest.mark.parametrize("rechts,hoch,winkel,gesamt,gestuft",[
    (False,False,118,False,True),(True,True,118,True,True),
    (False,True,90,True,False),(True,False,90,False,False)])
def test_gezeichnete_bohrspitze_mit_kreis_oder_punkt_als_tiefenziel(app,tmp_path,monkeypatch,rechts,hoch,winkel,gesamt,gestuft):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve,BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import topods
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    profil = ([(10,6)] if gestuft else [])+[(6,14)]
    pdf,ziel = tmp_path/"Spitze.pdf",tmp_path/"Spitze.stp"
    _stufenblatt(pdf,profil,rechts,hoch,winkel,gesamt)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Drehteildialog(doc,pdf)
        try:
            d.einheit.setCurrentIndex(1)
            d.auswahl.setCurrentIndex(int(hoch))
            d.ansicht.bereich.emit((.05,.05,.5,.94) if hoch else (.05,.1,.6,.7))
            assert d.spur and d.spur.spitzenhoehe > 0 and d.spur.von_rechts == rechts
            assert not d.spitzenzeile.isHidden()
            for i,(laenge,dm) in enumerate((("12","Ø20"),("18","Ø12"))):
                d.tabelle.item(i,0).setText(laenge)
                d.tabelle.item(i,1).setText(dm)
            for i,(dm,tiefe) in enumerate(profil):
                d.bohrstufen.item(i,0).setText(f"Ø{dm} H7")
                d.bohrstufen.item(i,1).setText(f"{tiefe} ±0.1")
            d.seite.setValue(2)
            d.auswahl.setCurrentIndex(7)
            d.ansicht.bereich.emit((.32,.7,.75,.87))
            assert d.winkeltext.text() == f"{winkel}° ±1°" and not d.speichern.isEnabled()
            d.tiefenbezug.setCurrentIndex(1 if gesamt else 2)
            assert not d.speichern.isEnabled()
            d.tiefenbezug.setCurrentIndex(2 if gesamt else 1)
            for falsch in ("","90","130°","118° ±80°"):
                d.winkeltext.setText(falsch)
                assert not d.speichern.isEnabled()
            d.winkeltext.setText(f"{winkel}° ±1°")
            assert d.speichern.isEnabled(),d.status.text()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 5+2*len(profil) and all(p.semantisch and p.grafisch for p in erg.pmi)
            for quelle in (erg.pmi,lies_pmi_xcaf(erg.modell)):
                tiefe, = (p for p in quelle if p.nennwert == 14)
                ebene, = tiefe.flaechen
                assert BRepAdaptor_Surface(erg.modell.flaechen[ebene]).Plane().Location().X() == pytest.approx(30 if rechts else 0)
                assert tiefe.kanten == 1 and tiefe.grenzen() == pytest.approx((14.1,13.9))
                alpha, = (p for p in quelle if p.typ == "Size_Angular")
                f, = alpha.flaechen
                assert alpha.grenzen() == pytest.approx((winkel+1,winkel-1))
                assert np.rad2deg(abs(BRepAdaptor_Surface(erg.modell.flaechen[f]).Cone().SemiAngle())*2) == pytest.approx(winkel)
            tiefe, = (p for p in erg.pmi if p.nennwert == 14)
            target, = tiefe.teilformen
            if gesamt:
                punkt = BRep_Tool.Pnt(topods.Vertex(target))
            else:
                kreis = BRepAdaptor_Curve(topods.Edge(target)).Circle()
                assert kreis.Radius() == pytest.approx(3)
                punkt = kreis.Location()
            assert punkt.Coord() == pytest.approx((16 if rechts else 14,0,0))
            g, = (g for g in erg.grafik.values() if tiefe.step_id in g.pmi_ids)
            x,y,z = g.linien[0][0]
            assert (x,np.hypot(y,z)) == pytest.approx((punkt.X(),0 if gesamt else 3),abs=1e-5)
            h = 3/np.tan(np.deg2rad(winkel)/2)
            zyl = 14-h if gesamt else 14
            soll = 100*12+36*18-9*zyl-3*h-(6*(25-9) if gestuft else 0)
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form,v)
            assert v.Mass() == pytest.approx(np.pi*soll)
        finally:
            d.blatt.schliesse()
            d.close()


def test_kegelhuelle_in_schmalerem_sitz_und_tiefengrenzen(tmp_path):
    from programm.kern.drehzeichnung import Bohrspitze,schreibe_drehteil
    from programm.kern.zeichnungsabgleich import lese_angabe
    def mass(text):
        return lese_angabe(text,1.)
    masse = [(mass("12"),mass("Ø20")),(mass("18"),mass("Ø4.2"))]
    ziel = tmp_path/"Welle.step"
    # Ab Position 12 hat die Spitze maximal Radius 2. Nur der Kegel reicht in den schmalen Sitz.
    for gesamt, text in ((True,"14"),(False,"11")):
        spitze = Bohrspitze(mass("90°"),gesamt)
        assert schreibe_drehteil(ziel,masse,mass("Ø6"),mass(text),spitze=spitze) == 7
        # Eine Spitze genau an der aeusseren Schulter laesst noch die volle zweite Sitzlaenge stehen.
        assert schreibe_drehteil(ziel,masse,mass("Ø6"),mass("12" if gesamt else "9"),spitze=spitze) == 7
    vorher = ziel.read_bytes()
    for d,tiefe,winkel,gesamt,vor in (("Ø6","14 ±0.2","90°",True,()),
        ("Ø6","11 ±0.2","90°",False,()), ("Ø6","14","90° ±10°",True,()),
        ("Ø6","11","90° ±10°",False,()), ("Ø6","30","90°",True,()),
        ("Ø6","12","90°",True,[(mass("Ø8"),mass("9 ±0.1"))]),
        ("Ø6","3","90°",True,())):
        with pytest.raises(ValueError):
            schreibe_drehteil(ziel,masse,mass(d),mass(tiefe),False,vor,Bohrspitze(mass(winkel),gesamt))
        assert ziel.read_bytes() == vorher


def test_bohrspitze_verlangt_zwei_gerade_flanken_bis_zum_gemeinsamen_scheitel():
    from programm.kern.drehzeichnung import drehprofil
    bild = np.full((120,180,3),255,np.uint8)
    bild[15,10:161] = bild[105,10:161] = 0
    bild[15:106,10] = bild[15:106,160] = 0
    bild[36,10:101] = bild[84,10:101] = 0
    for s in (-1,1):
        for dr in range(25):
            bild[60+s*dr,124-dr] = 0
    box = (0,0,1,1)
    sitze,spur = drehprofil(bild,box)
    assert len(sitze) == 1 and spur.spitzenhoehe == pytest.approx(24)
    for fehler in ("einseitig","Knick","Doppellinie","Flankenlücke","flacher Restboden"):
        kopie = bild.copy()
        if fehler == "einseitig":
            kopie[41:57,101:124] = 255
        elif fehler == "Knick":
            for dy in range(5,18):
                kopie[60+dy,124-dy] = 255
                kopie[60+dy,124-dy-4] = 0
        elif fehler == "Doppellinie":
            for dy in range(3,19):
                kopie[60+dy,124-dy+7] = 0
        elif fehler == "Flankenlücke":
            kopie[65:71,107:122] = 255
        else:
            kopie[56:65,121:125] = 255
            kopie[56:65,120] = 0
        assert drehprofil(kopie,box) == ([],None), fehler
