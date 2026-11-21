import numpy as np
import pytest
from PySide6 import QtCore,QtGui,QtWidgets


def _blatt(pfad, blind, hoch, aussen):
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
