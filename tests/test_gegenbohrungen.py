import numpy as np
import pytest
from PySide6 import QtCore,QtGui,QtWidgets


def _blatt(pfad, blind, hoch, aussen, spitzen=(None,None)):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(320,205),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0,0,0,0))
    links = [(10,6),(6,13)] if blind else [(10,6)]
    rechts = [(aussen,8),(6,10)] if blind else [(aussen,8)]
    with QtGui.QPainter(pdf) as p:
        p.save()
        if hoch:
            p.setTransform(QtGui.QTransform(0,1,1,0,0,0))
        kontur = [(0,10),(12,10),(12,6),(30,6),(30,-6),(12,-6),(12,-10),(0,-10)]
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(30+4*x,75-4*y) for x,y in kontur]))
        p.drawLine(78,51,78,99)
        if not hoch:
            p.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black,1,QtCore.Qt.PenStyle.DashLine))
        for rev,stufen in ((False,links),(True,rechts)):
            start = 0
            def sx(tiefe):
                return 30+4*(30-tiefe if rev else tiefe)
            for i,(dm,tiefe) in enumerate(stufen):
                innen = stufen[i+1][0] if i+1 < len(stufen) else 0 if blind else 6
                for sign in (-1,1):
                    y = 75+sign*2*dm
                    p.drawLine(sx(start),y,sx(tiefe),y)
                    winkel = spitzen[rev] if i == len(stufen)-1 else None
                    if winkel:
                        h = dm/(2*np.tan(np.deg2rad(winkel)/2))
                        p.drawLine(QtCore.QPointF(sx(tiefe),y),QtCore.QPointF(sx(tiefe+h),75))
                    else:
                        p.drawLine(sx(tiefe),y,sx(tiefe),75+sign*2*innen)
                start = tiefe
        if not blind:
            for y in (63,87):
                p.drawLine(54,y,118,y)
        p.restore()
        assert pdf.newPage()
        p.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black,1,QtCore.Qt.PenStyle.SolidLine))
        for x,dms in ((41,(6,10,20)),(112,(6,aussen,12,20))):
            for dm in dms:
                p.drawEllipse(QtCore.QPointF(x,45),dm*1.4,dm*1.4)
        zeilen = [*links,*rechts]+([] if blind else [(6,None)])
        for i,(dm,tiefe) in enumerate(zeilen):
            y = 42+35*i
            p.drawText(154,y,f"Ø{dm} H{7+i}"+(" THRU" if tiefe is None else ""))
            if tiefe:
                p.drawText(238,y,f"{tiefe} ±0.{i+1}")
        for i,winkel in enumerate(spitzen):
            if winkel:
                p.drawText(155+65*i,193,f"{winkel}°")
    return zeilen


@pytest.mark.parametrize("blind,hoch,aussen",[(False,False,10),(True,False,10),(False,True,8),(True,True,8)])
def test_gegenbohrungen_aus_beiden_enden_mit_eigenen_passungen(app,tmp_path,monkeypatch,blind,hoch,aussen):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.axialbohrung import Gegenbohrungen
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.vergleich_geo import _nachbarn
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    pdf,ziel = tmp_path/"Welle.pdf",tmp_path/"Welle.stp"
    zeilen = _blatt(pdf,blind,hoch,aussen)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *args:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Drehteildialog(doc,pdf)
        try:
            d.einheit.setCurrentIndex(1)
            d.auswahl.setCurrentIndex(int(hoch))
            d.ansicht.bereich.emit((.03,.04,.48,.85) if hoch else (.04,.09,.55,.64))
            assert isinstance(d.spur,Gegenbohrungen)
            assert (d.spur.kern is None) == blind
            assert d.bohrstufen.rowCount() == len(zeilen)
            for i,werte in enumerate((("12","Ø20"),("18","Ø12 h6"))):
                for j,w in enumerate(werte):
                    d.tabelle.item(i,j).setText(w)
            d.seite.setValue(2)
            box1,box2 = (.02,.05,.24,.39),(.25,.05,.46,.39)
            for index,box in ((4,box1),(8,box2)):
                d.auswahl.setCurrentIndex(index)
                d.ansicht.bereich.emit(box)
            assert len(d.stirn) == 3 and len(d.stirn2) == 4
            for i,(_,tiefe) in enumerate(zeilen):
                d.bohrstufen.setCurrentCell(i,0)
                y = 42+35*i
                for index,l,r in ((5,145,231),(6,233,319)):
                    if index == 6 and tiefe is None:
                        assert not d.auswahl.model().item(6).isEnabled()
                        continue
                    d.auswahl.setCurrentIndex(index)
                    d.ansicht.bereich.emit((l/320,(y-19)/205,r/320,(y+5)/205))
            assert d.speichern.isEnabled(), d.status.text()
            d.auswahl.setCurrentIndex(8)
            d.ansicht.bereich.emit(box1)
            assert not d.speichern.isEnabled()
            d.stirn_entfernen.click()
            assert d.stirn2 is None and len(d.stirn) == 3 and d.speichern.isEnabled()
            d.speichern.click()
            erg = lade_alles(str(ziel))
            assert len(erg.pmi) == 4+len(zeilen)+sum(t is not None for _,t in zeilen)
            assert all(p.grafisch and p.semantisch for p in erg.pmi)
            nb = _nachbarn(erg.modell.flaechen,erg.modell.flaechen_index)
            def x(f):
                return BRepAdaptor_Surface(erg.modell.flaechen[f]).Plane().Location().X()
            abschnitte = [(0,6,0),(6,13,0),(22,30,30),(20,22,30)] if blind else [(0,6,0),(22,30,30),(6,22,None)]
            for quelle in (erg.pmi,lies_pmi_xcaf(erg.modell)):
                for i,((a,b,bezug),(dm,tiefe)) in enumerate(zip(abschnitte,zeilen,strict=True)):
                    p, = (p for p in quelle if p.passung == f"H{7+i}")
                    wand, = p.flaechen
                    assert p.nennwert == dm and sorted(x(f) for f in nb[wand]) == pytest.approx([a,b])
                    if tiefe:
                        m, = (p for p in quelle if p.typ == "Location_LinearDistance" and p.oben == (i+1)/10)
                        assert m.nennwert == tiefe
                        soll = sorted((bezug,b if bezug == 0 else a))
                        assert sorted(x(f) for f in m.flaechen) == pytest.approx(soll)
                        if quelle is erg.pmi:
                            g, = (g for g in erg.grafik.values() if m.step_id in g.pmi_ids)
                            assert sorted(g.linien[2][:,0]) == pytest.approx(soll)
            v = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form,v)
            assert v.Mass() == pytest.approx(np.pi*(100*12+36*18-sum((b-a)*(dm/2)**2 for (a,b,_),(dm,_) in zip(abschnitte,zeilen))))
        finally:
            d.blatt.schliesse()
            d.close()


@pytest.mark.parametrize("durchgang",[False,True])
def test_gegenbohrungen_grenzen_muessen_die_mitte_und_beide_schultern_erhalten(tmp_path,durchgang):
    from programm.kern.axialbohrung import Gegenbohrungen
    from programm.kern.drehzeichnung import Sitzkontur,drehmasse,schreibe_drehteil
    from programm.kern.zeichnungsabgleich import lese_angabe
    kontur = [Sitzkontur((),48,80),Sitzkontur((),72,48)]
    masse = drehmasse(kontur,[("12 ±0.2","Ø20"),("18 ±0.3","Ø12")],1.)
    def mass(text):
        return lese_angabe(text,1.)
    ziel = tmp_path/"vorhanden.step"
    ziel.write_bytes(b"bestand")
    kern = mass("Ø6 ±0.2") if durchgang else None
    for links,rechts,dm in (("14 ±1","14 ±0.5","Ø10"),("15","15","Ø10"),
                            ("6","8","Ø6.5 ±0.5" if durchgang else "Ø12 ±0.1")):
        gegen = Gegenbohrungen(((mass("Ø10"),mass(links)),),((mass(dm),mass(rechts)),),kern)
        with pytest.raises(ValueError):
            schreibe_drehteil(ziel,masse,gegen=gegen)
        assert ziel.read_bytes() == b"bestand"


@pytest.mark.parametrize("hoch,winkel", [(True,(90,118)),(False,(118,90)),(True,(None,90)),(True,(118,None))])
def test_gegenueberliegende_bohrspitzen_aus_pdf_mit_semantischen_zielen(app,tmp_path,monkeypatch,hoch,winkel):
    from pypdfium2 import PdfDocument
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone,GeomAbs_Plane
    from programm.kern.axialbohrung import Gegenbohrungen
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.kern.vergleich_geo import _nachbarn
    from programm.ui.drehzeichnung_ui import Drehteildialog
    from programm.ui.lader import lade_alles
    pdf,ziel = tmp_path/"Spitzen.pdf",tmp_path/"Spitzen.stp"
    stufen = _blatt(pdf,True,hoch,8,winkel)
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(ziel),"STEP"))
    with PdfDocument(pdf) as doc:
        d = Drehteildialog(doc,pdf)
        try:
            d.einheit.setCurrentIndex(1)
            d.auswahl.setCurrentIndex(int(hoch))
            d.ansicht.bereich.emit((.03,.04,.48,.85) if hoch else (.04,.09,.55,.64))
            assert isinstance(d.spur,Gegenbohrungen)
            assert tuple(map(bool,d.spur.spitzen)) == tuple(map(bool,winkel))
            for i,(l,dm) in enumerate(((12,20),(18,12))):
                d.tabelle.item(i,0).setText(str(l))
                d.tabelle.item(i,1).setText(f"Ø{dm}")
            d.seite.setValue(2)
            for i,(dm,tiefe) in enumerate(stufen):
                d.bohrstufen.setCurrentCell(i,0)
                spitz = i in (1,3) and winkel[i//2]
                assert d.auswahl.model().item(7).isEnabled() == bool(spitz)
                d.bohrstufen.item(i,0).setText(f"Ø{dm} H{7+i}")
                if spitz:
                    d.auswahl.setCurrentIndex(7)
                    x = 155+65*(i//2)
                    d.ansicht.bereich.emit(((x-4)/320,176/205,(x+52)/320,200/205))
                    assert str(spitz) in d.bohrstufen.item(i,2).text()
                    # Links Wandende, rechts Scheitel; beide Eingaben bleiben voneinander unabhaengig.
                    d.bohrstufen.cellWidget(i,3).setCurrentIndex(1+int(i==3))
                    if i==3:
                        tiefe += dm/(2*np.tan(np.deg2rad(spitz)/2))
                d.bohrstufen.item(i,1).setText(f"{tiefe:.5f} ±0.{i+1}")
            assert d.speichern.isEnabled(), d.status.text()
            for zeile in (1,3):
                bezug = d.bohrstufen.cellWidget(zeile,3)
                if bezug is not None:
                    art = bezug.currentIndex()
                    bezug.setCurrentIndex(3-art)
                    assert not d.speichern.isEnabled()
                    bezug.setCurrentIndex(art)
            assert d.speichern.isEnabled(), d.status.text()
            d.speichern.click()
        finally:
            d.blatt.schliesse()
            d.close()
    erg = lade_alles(str(ziel))
    fl = [BRepAdaptor_Surface(f) for f in erg.modell.flaechen]
    nachbarn = _nachbarn(erg.modell.flaechen,erg.modell.flaechen_index)
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    eigenschaften = GProp_GProps()
    brepgprop.VolumeProperties(erg.modell.form,eigenschaften)
    spitzenvolumen = sum(9/np.tan(np.deg2rad(w)/2) for w in winkel if w)
    soll = np.pi*(12*100+18*36 - 6*25 - 7*9 - 8*16 - 2*9 - spitzenvolumen)
    assert eigenschaften.Mass() == pytest.approx(soll)
    assert len(erg.pmi) == 12+sum(bool(w) for w in winkel)
    assert all(p.semantisch and p.grafisch for p in erg.pmi)
    for pmis in (erg.pmi,lies_pmi_xcaf(erg.modell)):
        for rechts,w in enumerate(winkel):
            if not w:
                continue
            wand, = next(p for p in pmis if p.passung == ("H10" if rechts else "H8")).flaechen
            kegel, = (f for f in nachbarn[wand] if fl[f].GetType()==GeomAbs_Cone)
            assert 2*np.rad2deg(abs(fl[kegel].Cone().SemiAngle())) == pytest.approx(w)
            assert next(p for p in pmis if p.typ=="Size_Angular" and p.flaechen=={kegel}).nennwert == pytest.approx(w)
            tiefe, = (p for p in pmis if p.typ=="Location_LinearDistance" and p.oben == (.4 if rechts else .2))
            eintritt, = (f for f in tiefe.flaechen if fl[f].GetType()==GeomAbs_Plane)
            assert fl[eintritt].Plane().Location().X() == pytest.approx(30 if rechts else 0)
            assert tiefe.nennwert == pytest.approx(10+3/np.tan(np.deg2rad(w)/2) if rechts else 13)
            assert tiefe.flaechen == {eintritt} and tiefe.kanten == 1
            if pmis is erg.pmi:
                from OCC.Core.BRep import BRep_Tool
                from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
                from OCC.Core.TopoDS import topods
                ziel, = tiefe.teilformen
                if rechts:
                    punkt = BRep_Tool.Pnt(topods.Vertex(ziel))
                    ort = 30-tiefe.nennwert
                else:
                    kreis = BRepAdaptor_Curve(topods.Edge(ziel)).Circle()
                    punkt, ort = kreis.Location(), 13
                    assert kreis.Radius() == pytest.approx(3)
                assert punkt.Coord() == pytest.approx((ort,0,0),abs=1e-6)
                grafik, = (g for g in erg.grafik.values() if tiefe.step_id in g.pmi_ids)
                x,y,z = grafik.linien[0][0]
                assert (x,np.hypot(y,z)) == pytest.approx((ort,0 if rechts else 3),abs=1e-5)


@pytest.mark.parametrize("dm,alpha,tiefe,rechts", [
    ("Ø6", "90°", "13", "14"),        # 13 + 3 + 14 = 30
    ("Ø6 ±0.4", "90°", "13", "13.9"),
    ("Ø6", "90° ±5°", "13", "13.9"),
    ("Ø6", "90°", "12.9 ±0.2", "14"),
])
def test_beide_spitzen_lassen_bei_grenzmass_material_zwischen_den_scheiteln(tmp_path,dm,alpha,tiefe,rechts):
    from programm.kern.axialbohrung import Gegenbohrungen
    from programm.kern.drehzeichnung import Bohrspitze,Sitzkontur,drehmasse,schreibe_drehteil
    from programm.kern.plattenbohrung import kegelwinkelmass
    from programm.kern.zeichnungsabgleich import lese_angabe
    masse = drehmasse([Sitzkontur((),120,80)],[("30","Ø20")],1.)
    spitzen = (Bohrspitze(kegelwinkelmass(alpha),False),Bohrspitze(kegelwinkelmass("118°"),True))
    def stufe(d,t):
        return ((lese_angabe(d,1.),lese_angabe(t,1.)),)
    gegen = Gegenbohrungen(stufe(dm,tiefe),stufe("Ø4",rechts),spitzen=spitzen)
    ziel = tmp_path/"Vorhanden.stp"
    ziel.write_bytes(b"vorhanden")
    with pytest.raises(ValueError,match="Materialsteg"):
        schreibe_drehteil(ziel,masse,gegen=gegen)
    assert ziel.read_bytes() == b"vorhanden"


def test_zwei_einfache_bohrspitzen_und_fehlende_flanke():
    from programm.kern.axialbohrung import Gegenbohrungen
    from programm.kern.drehzeichnung import drehprofil
    skala = 4
    spur = QtGui.QImage(320*skala,205*skala,QtGui.QImage.Format.Format_RGB888)
    spur.fill(QtCore.Qt.GlobalColor.white)
    with QtGui.QPainter(spur) as p:
        p.scale(skala,skala)
        kontur = [(0,10),(12,10),(12,6),(30,6),(30,-6),(12,-6),(12,-10),(0,-10)]
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(30+4*x,75-4*y) for x,y in kontur]))
        p.drawLine(78,51,78,99)
        for x,ende,scheitel,r in ((30,66,78,12),(150,118,110,8)):
            for s in (-1,1):
                y = 75+s*r
                p.drawLine(x,y,ende,y)
                p.drawLine(ende,y,scheitel,75)
    bild = np.frombuffer(spur.constBits(),np.uint8).reshape(205*skala,320*skala,3).copy()
    kontur,bohrung = drehprofil(bild,(.04,.09,.55,.64))
    assert len(kontur)==2 and isinstance(bohrung,Gegenbohrungen)
    assert bohrung.spitzen == pytest.approx((12*skala,8*skala),abs=1.)
    bild[67*skala:75*skala,110*skala:118*skala] = 255
    assert drehprofil(bild,(.04,.09,.55,.64)) == ([],None)
