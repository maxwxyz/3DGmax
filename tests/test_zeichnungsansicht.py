import csv
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern import zeichnungsabgleich as za
from programm.kern.zeichnungsansicht import Blattgeometrie, Blattkreis, modellkreise, zuordnen
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from programm.kern.pmi import Pmi


def _teil():
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern.laden import _alle_flaechen
    form = BRepPrimAPI_MakeBox(52, 37, 9).Shape()
    for x, y, r in ((8, 7, 2), (29, 9, 2), (13, 29, 3), (40, 25, 4)):
        bohrer = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, 11).Shape()
        form = BRepAlgoAPI_Cut(form, bohrer).Shape()
    return SimpleNamespace(flaechen=_alle_flaechen(form))


def _blatt(pfad, verzweigt=False):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    with QtGui.QPainter(pdf) as maler:
        for x, y, r in ((8, 7, 2), (29, 9, 2), (13, 29, 3), (40, 25, 4)):
            maler.drawEllipse(QtCore.QPointF(100+3*x, 200-3*y), 3*r, 3*r)
        # Gleicher Druckwert an der falschen Flaeche. Der zweigliedrige Pfeil zeigt auf die erste Bohrung.
        text = "Ø4.1"
        maler.setFont(QtGui.QFont("Helvetica", 14))
        maler.drawText(20, 160, text)
        rand = QtGui.QFontMetricsF(maler.font(), maler.device()).tightBoundingRect(text).translated(20, 160)
        anfang = QtCore.QPointF(rand.right()+.4, rand.center().y())
        knick = QtCore.QPointF(78, anfang.y())
        ziel = QtCore.QPointF(118, 179)
        maler.drawLine(anfang, knick)
        maler.drawLine(knick, ziel)
        if verzweigt:
            abzweig = (knick + ziel)/2 if verzweigt == "innen" else knick
            maler.drawLine(abzweig, QtCore.QPointF(82, 198))
        v = np.array([ziel.x()-knick.x(), ziel.y()-knick.y()])
        v /= np.linalg.norm(v)
        basis = np.array([ziel.x(), ziel.y()]) - 6*v
        n = np.array([-v[1], v[0]])
        maler.setPen(QtCore.Qt.PenStyle.NoPen)
        maler.setBrush(QtCore.Qt.GlobalColor.black)
        maler.drawPolygon(QtGui.QPolygonF([ziel, QtCore.QPointF(*(basis+n)), QtCore.QPointF(*(basis-n))]))


@pytest.mark.parametrize(("verzweigt", "drehung"), [(False, 0), (True, 0), ("innen", 0), (False, 90)])
def test_hinweisziel_zugeordnet_bei_geaendertem_mass(app, tmp_path, monkeypatch, verzweigt, drehung):
    import pypdfium2 as pdf
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    teil = _teil()
    achsen, = modellkreise(teil)
    assert len(achsen) == 4
    erste = next(k for k in achsen if (k.x, k.y) == (8, 7))
    zweite = next(k for k in achsen if (k.x, k.y) == (29, 9))
    gut = Pmi("mass", "Size_Diameter", nennwert=4., flaechen=set(erste.flaechen), nummer=1)
    falsch = replace(gut, nennwert=4.1, flaechen=set(zweite.flaechen), nummer=2)
    pfad = tmp_path / "Bohrbild.pdf"
    _blatt(pfad, verzweigt)
    with pdf.PdfDocument(pfad) as doc:
        if drehung:
            doc[0].set_rotation(drehung)
        d = Zeichnungsabgleich(doc, [falsch, gut], lambda _: None, (str(pfad), "Teil.stp"), einzelteil=teil)
        try:
            d.einheit.setCurrentIndex(1)
            a = next(a for a in d.seiten[0] if a.text == "Ø4.1")
            d.waehle(a)
            if not verzweigt:
                d.bestaetigen.click()
                assert a.modell is falsch and za.befund(a, 1.) == "gleich"
            d.registrieren.click()
            box = (.74, .14, .88, .45) if drehung else (.14, .12, .45, .26)
            d.ansicht.bereich.emit(box)
            assert d.auftrag.wait(10000)
            app.processEvents()
            assert len(d.kreise[0]) == 4
            if verzweigt:
                assert d.zielvorschlaege[a] is None and d.zuordnung.currentData() is None
                kreis = next(k for k in d.kreise[0] if k.flaechen == erste.flaechen)
                d.text.setPlainText("Ø4.10")
                d.ansicht.kreis_gewaehlt.emit(kreis)
                assert d.text.toPlainText() == "Ø4.10"
            else:
                assert d.zielvorschlaege[a].flaechen == erste.flaechen
            assert d.zuordnung.currentData() == d.modellindex[id(gut)]
            assert za.befund(a, 1.) == "offen" and a.modell is not gut
            d.bestaetigen.click()
            assert a.modell is gut and za.befund(a, 1.) == "geaendert"
            datei = tmp_path / "Pruefung.csv"
            monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(datei), "CSV"))
            d._export()
            with datei.open(encoding="utf-8-sig") as f:
                zeile = next(z for z in csv.DictReader(f, delimiter=";") if z["Angabe"].startswith("Ø4.1"))
            ziel = zeile["Hinweisziel (x/Breite, y/Höhe, Radius/Breite)"]
            assert tuple(map(float, ziel.split())) == pytest.approx(a.blattziel, abs=1e-6)
        finally:
            d.blatt.schliesse()
            d.close()


def test_symmetrisch_kollinear_und_konzentrisch_bleiben_offen():
    teile = [Blattkreis(x, y, 3, frozenset([i])) for i,(x,y) in enumerate(((0,0),(0,20),(35,0),(35,20)))]
    assert not zuordnen(teile, [teile])
    for punkte in [[(5*i, 0, 2) for i in range(4)], [(0, 0, i+1) for i in range(4)]]:
        gruppe = [Blattkreis(*p, frozenset([i])) for i,p in enumerate(punkte)]
        assert not zuordnen(gruppe, [gruppe])


def test_d2mi_904_einzelbohrung_in_hauptansicht(app):
    import pypdfium2 as pdf
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from programm.ui.lader import lade_alles
    pfad = Path(__file__).parents[1] / "daten/nist_d2mi/NIST-D2MI-Models/827-9999-904 rev c.pdf"
    if not pfad.exists():
        pytest.skip("Lokales NIST-D2MI-Referenzpaket fehlt")
    modell = lade_alles(str(pfad.with_suffix(".stp"))).modell
    with pdf.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 1)
        geo = Blattgeometrie(blatt)
        treffer = zuordnen(geo.im_bereich((.17, .09, .395, .36)), modellkreise(modell))
        blatt.schliesse()
    k, = [k for k in treffer if np.linalg.norm([k.x-384.35, k.y-296.65]) < .1]
    assert len(k.flaechen) == 2
    for i in k.flaechen:
        z = BRepAdaptor_Surface(modell.flaechen[i]).Cylinder()
        assert z.Radius() == pytest.approx(2.38125)
        assert z.Location().Coord()[:2] == pytest.approx((6.35, 25.4))


def test_gleicher_kreis_auf_getrennten_sackloechern_hat_keine_eindeutige_tiefe():
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern.laden import _alle_flaechen
    form = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
    for z in (-1, 15):
        bohrer = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(5, 5, z), gp_Dir(0, 0, 1)), 2, 7).Shape()
        form = BRepAlgoAPI_Cut(form, bohrer).Shape()
    gruppe, = modellkreise(SimpleNamespace(flaechen=_alle_flaechen(form)))
    kreis, = gruppe
    assert not kreis.flaechen and (kreis.x, kreis.y, kreis.r) == (5, 5, 2)


def test_wechsel_des_blatts_verwirft_laufende_zuordnung(app, tmp_path, monkeypatch):
    import threading
    import pypdfium2 as pdf
    from programm.ui import zeichnungsabgleich_ui as ui
    bereit, weiter = threading.Event(), threading.Event()

    def langsam(modell, pruefe):
        bereit.set()
        weiter.wait(5)
        pruefe()
        return []

    monkeypatch.setattr(ui.ansichtsabgleich, "modellkreise", langsam)
    pfad = tmp_path / "Zwei Blaetter.pdf"
    pdfwriter = QtGui.QPdfWriter(str(pfad))
    with QtGui.QPainter(pdfwriter) as maler:
        maler.drawText(50, 50, "1")
        pdfwriter.newPage()
        maler.drawText(50, 50, "2")
    with pdf.PdfDocument(pfad) as doc:
        d = ui.Zeichnungsabgleich(doc, [], lambda _: None, (str(pfad), ""), einzelteil=_teil())
        d.registrieren.click()
        d.ansicht.bereich.emit((0., 0., 1., 1.))
        arbeit = d.auftrag
        try:
            assert bereit.wait(5)
            d.seite.setValue(2)
            assert arbeit.abgebrochen and d.auftrag is None
            weiter.set()
            assert arbeit.wait(5000)
            app.processEvents()
            assert not d.kreise and d.blatt.nummer == 1
        finally:
            weiter.set()
            d.blatt.schliesse()
            d.close()
