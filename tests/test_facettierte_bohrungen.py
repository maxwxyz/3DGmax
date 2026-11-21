"""Facettierte Bohrungsraender und getrennte Teilbereiche derselben Schraegansicht."""
import csv
import gzip

import numpy as np
import pytest
from PySide6 import QtCore, QtTest, QtWidgets
from pypdfium2 import PdfDocument

from programm.kern.zeichnungsansicht import Blattgeometrie
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from tests.conftest import pfad
from tests.test_bogenringe import _pdf
from tests.test_zeichnung_koplanar import NIST


def test_strichbreite_kontrast_und_regelmaessiges_polygon(tmp_path):
    pdf = tmp_path/"Facetten.pdf"
    inhalt = []
    for i, art in enumerate(("sichtbar", "regelmaessig", "duenn", "abgedeckt", "gefuellt")):
        phi = np.linspace(0,2*np.pi,21)
        if art != "regelmaessig":
            phi += .055*np.sin(5*phi)
        x = 35+60*i
        punkte = np.column_stack((x+22*np.cos(phi), 100+13*np.sin(phi)))
        if art == "sichtbar":
            inhalt.append(f".82 g {x-26} 82 52 36 re f")
        inhalt.append(".05 w" if art == "duenn" else ".85 w")
        inhalt.append(" ".join(f"{u:.5f} {v:.5f} "+("m" if j == 0 else "l")
                               for j,(u,v) in enumerate(punkte))+(" h B" if art == "gefuellt" else " h S"))
        if art == "abgedeckt":
            inhalt.append(f".67 g {x+17} 88 14 24 re f")
    _pdf(pdf,inhalt)
    with PdfDocument(pdf) as doc:
        blatt = Zeichnungsblatt(doc,0)
        try:
            g = Blattgeometrie(blatt,mit_ellipsen=True)
            k, = g.kreise
            assert (k.x*320/g.groesse[0], k.r*320/g.groesse[0], k.kurz/k.r) == pytest.approx((35,22,13/22),abs=.01)
        finally:
            blatt.schliesse()


def _ziehen(ansicht, box, *, sammeln=False):
    w,h = ansicht.sceneRect().width(),ansicht.sceneRect().height()
    l,t,r,b = box
    a = ansicht.mapFromScene(QtCore.QPointF(l*w,t*h))
    z = ansicht.mapFromScene(QtCore.QPointF(r*w,b*h))
    taste = QtCore.Qt.KeyboardModifier.ShiftModifier if sammeln else QtCore.Qt.KeyboardModifier.NoModifier
    QtTest.QTest.mousePress(ansicht.viewport(),QtCore.Qt.MouseButton.LeftButton,taste,a)
    QtTest.QTest.mouseMove(ansicht.viewport(),z)
    QtTest.QTest.mouseRelease(ansicht.viewport(),QtCore.Qt.MouseButton.LeftButton,taste,z)


def test_teilbereiche_lassen_fremden_kreis_in_der_luecke_frei(app, tmp_path):
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    from tests.test_zeichnungsansicht import _blatt, _teil
    pdf = tmp_path/"Teilbereiche.pdf"
    _blatt(pdf,fremdkreis=True)
    with PdfDocument(pdf) as doc:
        d = Zeichnungsabgleich(doc,[],lambda _:None,(str(pdf),"Teil.stp"),einzelteil=_teil())
        try:
            d.show()
            app.processEvents()
            g = Blattgeometrie(d.blatt)
            ks = sorted(g.kreise,key=lambda k:k.y)
            assert len(ks) == 5
            def box(kreise):
                l,t = np.min([(k.x-k.r,k.y-k.r) for k in kreise],axis=0)-4
                r,b = np.max([(k.x+k.r,k.y+k.r) for k in kreise],axis=0)+4
                return (l,t,r,b)/np.tile(g.groesse,2)
            d.registrieren.click()
            _ziehen(d.ansicht,box(ks[:2]),sammeln=True)
            _ziehen(d.ansicht,box(ks[-2:]))
            assert d.auftrag.wait(10000)
            app.processEvents()
            assert len(d.kreise[0]) == 4 and ks[2] not in d.sichtkreise[0]
        finally:
            d.blatt.schliesse()
            d.close()


@pytest.mark.parametrize("reparieren",[False,True],ids=["referenz","grafischer_export"])
def test_getrennte_bohrungen_ueber_pfeil_und_flaeche_bis_csv(fenster, app, tmp_path, monkeypatch, reparieren):
    pdf = NIST/"PDF/nist_ctc_03_asme1_rc.pdf"
    modell = NIST/"nist_ctc_03_asme1_ap242-e2.stp"
    if not pdf.is_file() or not reparieren and not modell.is_file():
        pytest.skip("Lokales NIST-Referenzpaar fehlt")
    if reparieren:
        eingang = tmp_path/"Bohrungen.step"
        with gzip.open(pfad("nist_ctc_03_asme1_ap203.stp.gz"),"rb") as f:
            eingang.write_bytes(f.read())
        fenster.lade(str(eingang),warten=True)
        for nr in (3638,3640,3641,3649):
            fenster._pmi_befehl("semantisch",next(p for p in fenster.erg.pmi if p.step_id==nr))
            dialog = fenster._semantik_dialog
            assert not dialog.fehler()
            dialog._pruefen()
        modell = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.step"),melden=False)
        assert modell and not fenster._step_bericht.uebersprungen
    ziel = tmp_path/"Bohrungen.csv"
    monkeypatch.setattr(QtWidgets.QFileDialog,"getOpenFileName",lambda *a:(str(pdf),"PDF"))
    monkeypatch.setattr(QtWidgets.QFileDialog,"getSaveFileName",lambda *a:(str(ziel),"CSV"))
    fenster.lade(str(modell),warten=True)
    fenster.aktionen["zeichnungsabgleich"].trigger()
    d = fenster.zeichnungsabgleich
    try:
        d.show()
        app.processEvents()
        d.einheit.setCurrentIndex(d.einheit.findData(25.4))
        links = (.35,.145,.493,.594)
        rechts = (.726,.42,.757,.716)
        d.registrieren.click()
        _ziehen(d.ansicht,links,sammeln=True)
        assert len(d.ansicht.bohrbildbereiche) == 1 and d.auftrag is None
        d.registrieren.click()
        assert d.ansicht.bohrbildbereiche is None
        d.registrieren.click()
        _ziehen(d.ansicht,links,sammeln=True)
        _ziehen(d.ansicht,links,sammeln=True)
        _ziehen(d.ansicht,rechts)
        assert d.auftrag.wait(20000)
        app.processEvents()
        assert len(d.bereiche[0]) == 2 and len(d.kreise[0]) == 7
        g = d.blattgeometrie
        assert len(g.im_bereich((.34,.44,.63,.7))) == 6
        einzeln = sorted((a for a in d.seiten[0] if a.text=="⌀.438±.005"),key=lambda a:a.box[1])
        muster, = [a for a in d.seiten[0] if a.text=="4X⌀.625±.005"]
        for a,nr,quelle in zip([*einzeln,muster],(264,263,265),(3641,3649,3638),strict=True):
            ids = fenster.erg.grafik[quelle].pmi_ids if reparieren else {nr}
            p, = [p for p in d.modell if p.semantisch and p.step_id in ids and p.art=="mass"]
            d.waehle(a)
            k = d.zielvorschlaege[a]
            assert k and k.kurz and k.flaechen and k.flaechen <= p.flaechen
            assert d.zuordnung.currentData() == d.modellindex[id(p)]
            d.bestaetigen.click()
            assert a.modell is p and a.blattziel == k.blattort(*g.groesse)
            assert d._befund(a) == "gleich"
        assert einzeln[0].modell.flaechen.isdisjoint(einzeln[1].modell.flaechen)
        assert len(muster.musterziele) == 4
        paar, = [a for a in d.seiten[0] if a.text == "2X⌀.438±.005"]
        assert d.zielvorschlaege[paar] and len(d._muster(paar,2)) == 1
        assert d._befund(paar) == "offen"
        d._export()
        with ziel.open(encoding="utf-8-sig") as f:
            csvzeilen = list(csv.DictReader(f,delimiter=";"))
        for a in einzeln:
            row, = [z for z in csvzeilen if z["Angabe"]==a.text and z["Quell-ID der Modell-PMI"]==str(a.modell.step_id)]
            assert row["Befund"] == "Werte gleich"
            assert tuple(map(float,row["Hinweisziel (x/Breite, y/Höhe, Radius/Breite)"].split())) == pytest.approx(a.blattziel[:3],abs=1e-6)
    finally:
        d.close()
