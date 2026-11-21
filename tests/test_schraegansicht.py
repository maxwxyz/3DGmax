import csv
from dataclasses import replace
import math

import numpy as np
import pytest
from PySide6 import QtCore,QtGui,QtWidgets,QtTest

from programm.kern import zeichnungsabgleich as za
from programm.kern.blattring import Blattkreis,ellipse
from programm.kern.zeichnungsansicht import modellkreise,zuordnen
from programm.kern.pmi import Pmi


def _blatt(pfad, gruppe, tiefen, spiegel):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(320,220),QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF())
    q = .55
    with QtGui.QPainter(pdf) as p:
        for k,z in zip(gruppe,tiefen,strict=True):
            weg = QtGui.QTransform().translate(100,78).rotate(32).scale(3,3).translate(0,math.sqrt(1-q*q)*z).scale(1,q).rotate(-20).scale(1,spiegel)
            p.setTransform(weg)
            p.drawEllipse(QtCore.QPointF(k.x,k.y),k.r,k.r)
            if k is gruppe[0]:
                ort = weg.map(QtCore.QPointF(k.x,k.y))
                winkel = math.radians(32)
                ziel = ort-QtCore.QPointF(math.cos(winkel),math.sin(winkel))*3*k.r
        p.resetTransform()
        p.setFont(QtGui.QFont("Helvetica",10))
        text = "Ø4.1"
        p.drawText(13,60,text)
        rand = QtGui.QFontMetricsF(p.font(),p.device()).tightBoundingRect(text).translated(13,60)
        start = QtCore.QPointF(rand.right()+.3,rand.center().y())
        knick = QtCore.QPointF(57,start.y())
        p.drawLine(start,knick)
        p.drawLine(knick,ziel)
        richtung = (ziel-knick)/math.hypot((ziel-knick).x(),(ziel-knick).y())
        basis = ziel-3.6*richtung
        quer = QtCore.QPointF(-richtung.y(),richtung.x())*.65
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtCore.Qt.GlobalColor.black)
        p.drawPolygon(QtGui.QPolygonF([ziel,basis+quer,basis-quer]))
    return ort,ziel


@pytest.mark.parametrize("z,spiegel",[((0,0,0,0),1),((0,9,9,0),-1)])
def test_schraege_bohrungen_mit_hinweispfeil_und_csv(app,tmp_path,monkeypatch,z,spiegel):
    from pypdfium2 import PdfDocument
    from test_zeichnungsansicht import _teil
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    teil = _teil()
    gruppe, = modellkreise(teil)
    gruppe.sort(key=lambda k:k.x)
    a = gruppe[0]
    assert a.r == 2 and {z for z,_ in a.raender} == {0.,9.}
    richtig = Pmi("mass","Size_Diameter",nennwert=4.,flaechen=set(a.flaechen),nummer=1)
    falsch = replace(richtig,nennwert=4.1,flaechen=set(gruppe[2].flaechen),nummer=2)
    pdf = tmp_path/"Schraeg.pdf"
    _blatt(pdf,gruppe,z,spiegel)
    with PdfDocument(pdf) as doc:
        dlg = Zeichnungsabgleich(doc,[richtig,falsch],lambda _:None,(str(pdf),"Teil.stp"),einzelteil=teil)
        try:
            dlg.einheit.setCurrentIndex(1)
            eintrag = next(a for a in dlg.seiten[0] if a.text == "Ø4.1")
            dlg.waehle(eintrag)
            dlg.registrieren.click()
            dlg.ansicht.bereich.emit((.16,.06,.95,.98))
            assert dlg.auftrag.wait(10000)
            app.processEvents()
            assert len(dlg.kreise[0]) == 4,dlg.status.text()
            k = dlg.zielvorschlaege[eintrag]
            assert k and k.flaechen == a.flaechen
            assert k.kurz/k.r == pytest.approx(.55,abs=.001)
            assert k.winkel == pytest.approx(32,abs=.05)
            item = next(item for ring,item in dlg.ansicht.kreismarken if ring == k)
            assert item.rotation() == k.winkel and item.rect().height() == pytest.approx(2*k.kurz)
            dlg.show()
            app.processEvents()
            konturpunkt = item.mapToScene(QtCore.QPointF(0,k.kurz))
            klick = QtTest.QSignalSpy(dlg.ansicht.kreis_gewaehlt)
            QtTest.QTest.mouseClick(dlg.ansicht.viewport(),QtCore.Qt.MouseButton.LeftButton,
                                        pos=dlg.ansicht.mapFromScene(konturpunkt))
            assert klick.count() == 1 and klick.at(0)[0] == k
            assert dlg.zuordnung.currentData() == dlg.modellindex[id(richtig)]
            dlg.bestaetigen.click()
            assert eintrag.modell is richtig and za.befund(eintrag,1.) == "geaendert"
            datei = tmp_path/"pruefung.csv"
            monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(datei),"CSV"))
            dlg._export()
            with datei.open(encoding="utf-8-sig") as f:
                zeile = next(z for z in csv.DictReader(f,delimiter=";") if z["Angabe"] == "Ø4.1")
            werte = tuple(map(float,(zeile["Hinweisziel (x/Breite, y/Höhe, Radius/Breite)"]+" "+zeile["Hinweisellipse (kleine Halbachse/Breite, Drehwinkel in Grad)"]).split()))
            assert werte == pytest.approx(eintrag.blattziel,abs=1e-6)
        finally:
            dlg.blatt.schliesse()
            dlg.close()


def test_offene_pfade_unterschiedliche_projektionen_und_mehrdeutige_tiefen():
    phi = np.linspace(0,2*np.pi,65)
    punkte = np.column_stack((20*np.cos(phi),8*np.sin(phi)))
    assert ellipse(punkte).kurz == pytest.approx(8)
    assert ellipse(punkte[:-6]) is None
    assert ellipse(np.concatenate((punkte,punkte[::-1]))) is None
    assert ellipse(np.column_stack((phi,phi))) is None
    kreise = [Blattkreis(x,y,r,raender=((2,frozenset({n})),))
              for n,(x,y,r) in enumerate(((1,7,4),(13,3,2),(5,19,3),(25,26,2)))]
    blatt = [Blattkreis(k.x*4,k.y*2,k.r*4,kurz=k.r*2) for k in kreise]
    assert [k.flaechen for k in zuordnen(blatt,[kreise])] == [frozenset({i}) for i in range(4)]
    anders = [replace(k,raender=((7,frozenset({n+4})),)) for n,k in enumerate(kreise)]
    assert not zuordnen(blatt,[kreise,anders],mit_gruppen=True)
    assert not zuordnen([*blatt[:-1],replace(blatt[-1],winkel=30)],[kreise])
    assert not zuordnen([*blatt[:-1],replace(blatt[-1],kurz=0)],[kreise])
    assert not zuordnen([*blatt[:-1],replace(blatt[-1],y=blatt[-1].y+9)],[kreise])


def test_schraegansicht_unterscheidet_koaxiale_oeffnungen_und_prueft_symmetrie():
    ringe = [Blattkreis(x,y,r,raender=((3.,frozenset({i})),))
             for i,(x,y,r) in enumerate(((2,4,2),(17,8,2),(7,19,4),(24,22,3)))]
    ringe[0] = replace(ringe[0],raender=(*ringe[0].raender,(13.,frozenset({9}))))
    blatt = [Blattkreis(k.x*3,3*(.6*k.y+.8*(13 if i == 0 else 3)),k.r*3,kurz=k.r*1.8)
             for i,k in enumerate(ringe)]
    assert [k.flaechen for k in zuordnen(blatt,[ringe])] == [frozenset({i}) for i in (9,1,2,3)]
    # Bei deckungsgleichen Alternativen an nur einer Bohrung bleiben die anderen drei bestimmt.
    ringe[0] = replace(ringe[0],raender=(*ringe[0].raender,(13.01,frozenset({10}))))
    assert [k.flaechen for k in zuordnen(blatt,[ringe])] == [frozenset({i}) for i in (1,2,3)]
    quadrat = [Blattkreis(x,y,2,raender=((0.,frozenset({i})),))
               for i,(x,y) in enumerate(((0,0),(20,0),(0,20),(20,20)))]
    blatt = [Blattkreis(k.x+25,.55*k.y+50,2,kurz=1.1) for k in quadrat]
    assert not zuordnen(blatt,[quadrat])
    muster = zuordnen(blatt,[quadrat],mit_gruppen=True)
    assert len(muster) == 4 and all(len(k.tauschgruppe) == 4 and not k.flaechen for k in muster)


def test_d2mi_904_schraegansicht_mit_acht_ellipsen(app):
    from pathlib import Path
    from pypdfium2 import PdfDocument
    from programm.kern.zeichnungsansicht import Blattgeometrie,muster_am_ziel
    from programm.kern.zeichnungsblatt import Zeichnungsblatt
    from programm.ui.lader import lade_alles
    pfad = Path(__file__).parents[1]/"daten/nist_d2mi/NIST-D2MI-Models/827-9999-904 rev c.pdf"
    if not pfad.exists():
        pytest.skip("Lokales NIST-D2MI-Referenzpaket fehlt")
    erg = lade_alles(str(pfad.with_suffix(".stp")))
    with PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc,0)
        try:
            geo = Blattgeometrie(blatt,mit_ellipsen=True)
            ringe = geo.im_bereich((.43,.50,.69,.67))
            treffer = zuordnen(ringe,modellkreise(erg.modell),mit_gruppen=True)
            assert len(treffer) == len(ringe) == 8
            assert all(k.kurz/k.r == pytest.approx(.376,abs=.002) for k in treffer)
            muster = muster_am_ziel(max(treffer,key=lambda k:k.r),4,ringe,treffer)
            assert len(muster) == 4 and all(k.tauschgruppe and not k.flaechen for k in muster)
            mass, = [p for p in erg.pmi if za.muster_deckt(4,muster,p)]
            assert mass.step_id == 103256 and mass.grenzen() == pytest.approx((5.461,5.715))
        finally:
            blatt.schliesse()


def test_beide_sichtbaren_raender_zaehlen_als_eine_bohrung():
    from programm.kern.zeichnungsansicht import muster_am_ziel
    modell,blatt = [],[]
    for n,(x,y) in enumerate(((1,2),(20,6),(9,23),(31,28))):
        wand = frozenset({n})
        modell.append(Blattkreis(x,y,2,raender=((0,wand),(7,wand))))
        for z in (0,7):
            blatt.append(Blattkreis(4*x,4*(.8*y+.6*z),8,kurz=6.4))
    treffer = zuordnen(blatt,[modell],mit_gruppen=True)
    assert [k.flaechen for k in treffer] == [frozenset({j//2}) for j in range(8)]
    muster = muster_am_ziel(treffer[0],4,blatt,treffer)
    assert treffer[0] in muster and len({k.flaechen for k in muster}) == len(muster) == 4
    pmi = Pmi("mass","Size_Diameter",nennwert=4,flaechen=set(range(4)))
    assert za.muster_deckt(4,muster,pmi)
    assert not za.muster_deckt(8,treffer,pmi)
