import csv
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from programm.kern import zeichnungsabgleich as za
from programm.kern.zeichnungsansicht import Blattgeometrie, Blattkreis, modellkreise, muster_am_ziel, zuordnen
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from programm.kern.pmi import Pmi


_BOHRUNGEN = ((8, 7, 2), (29, 9, 2), (13, 29, 3), (40, 25, 4))


def _teil(zusatz=(), bohrungen=_BOHRUNGEN):
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern.laden import _alle_flaechen
    form = BRepPrimAPI_MakeBox(52, 37, 9).Shape()
    for x, y, r in (*bohrungen, *zusatz):
        bohrer = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, 11).Shape()
        form = BRepAlgoAPI_Cut(form, bohrer).Shape()
    return SimpleNamespace(form=form, flaechen=_alle_flaechen(form))


def _blatt(pfad, verzweigt=False, text="Ø4.1", fremdkreis=False, gabel=None, bohrungen=_BOHRUNGEN):
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    with QtGui.QPainter(pdf) as maler:
        for x, y, r in bohrungen:
            maler.drawEllipse(QtCore.QPointF(100+3*x, 200-3*y), 3*r, 3*r)
        # Gleicher Druckwert an der falschen Flaeche. Der zweigliedrige Pfeil zeigt auf die erste Bohrung.
        if fremdkreis:
            maler.drawEllipse(QtCore.QPointF(169, 144), 6, 6)
        maler.setFont(QtGui.QFont("Helvetica", 14))
        maler.drawText(20, 160, text)
        rand = QtGui.QFontMetricsF(maler.font(), maler.device()).tightBoundingRect(text).translated(20, 160)
        anfang = QtCore.QPointF(rand.right()+.4, rand.center().y())
        knick = QtCore.QPointF(78, anfang.y())
        ziel = QtCore.QPointF(118, 179)
        maler.drawLine(anfang, knick)
        if gabel in ("quer", "kreuzung"):
            # Zwei Pfeile an einem einzigen durchgehenden PDF-Strich.
            links, rechts = QtCore.QPointF(124, 179), QtCore.QPointF(187, 173)
            richtung = (rechts-links)/np.hypot(rechts.x()-links.x(), rechts.y()-links.y())
            z1, z2 = links+6*richtung, rechts-6*richtung
            mitte = (z1+z2)/2
            ende = mitte if gabel == "quer" else mitte+(mitte-knick)*.12
            maler.drawLine(knick, ende)
            maler.drawLine(z1, z2)
            pfeile = [(mitte, z1), (mitte, z2)]
        else:
            maler.drawLine(knick, ziel)
            pfeile = [(knick, ziel)]
        if verzweigt:
            abzweig = (knick + ziel)/2 if verzweigt == "innen" else knick
            maler.drawLine(abzweig, QtCore.QPointF(82, 198))
        if gabel and gabel not in ("quer", "kreuzung"):
            von = knick if gabel == "knick" else (knick+ziel)/2
            nach = QtCore.QPointF(181, 173)
            if gabel == "fremdkreis":
                nach = QtCore.QPointF(163, 144)
            elif gabel == "gleiches_ziel":
                nach = QtCore.QPointF(124, 173)
            maler.drawLine(von, nach)
            if gabel != "offen":
                pfeile.append((von, nach))
            if gabel == "drei":
                dritter = QtCore.QPointF(169, 150)
                ast = (von+nach)/2
                maler.drawLine(ast, dritter)
                pfeile.append((ast, dritter))
            elif gabel == "schleife":
                ecke = QtCore.QPointF(90, 191)
                maler.drawLine(knick, ecke)
                maler.drawLine(ecke, von)
        maler.setPen(QtCore.Qt.PenStyle.NoPen)
        maler.setBrush(QtCore.Qt.GlobalColor.black)
        for von, nach in pfeile:
            v = np.array([nach.x()-von.x(), nach.y()-von.y()])
            v /= np.linalg.norm(v)
            basis = np.array([nach.x(), nach.y()]) - 6*v
            n = np.array([-v[1], v[0]])
            maler.drawPolygon(QtGui.QPolygonF([nach, QtCore.QPointF(*(basis+n)), QtCore.QPointF(*(basis-n))]))


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
    erg = lade_alles(str(pfad.with_suffix(".stp")))
    modell = erg.modell
    with pdf.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 1)
        geo = Blattgeometrie(blatt)
        treffer = zuordnen(geo.im_bereich((.17, .09, .395, .36)), modellkreise(modell))
        # Gleiche Flaechen nach raeumlicher Drehung des gesamten STEP-Modells finden.
        geneigt = SimpleNamespace(flaechen=_neige(modell.flaechen))
        gedreht = zuordnen(geo.im_bereich((.17, .09, .395, .36)), modellkreise(geneigt))
        assert len(gedreht) == 14 and gedreht == treffer
        for x, y, achse in ((604.4, 151.1, (63.5, 63.1952)), (592.2, 370., (60.325, 6.35))):
            radien = set()
            for ring in treffer:
                if np.hypot(ring.x-x, ring.y-y) < .15:
                    for i in ring.flaechen:
                        zylinder = BRepAdaptor_Surface(modell.flaechen[i]).Cylinder()
                        assert zylinder.Location().Coord()[:2] == pytest.approx(achse)
                        radien.add(round(zylinder.Radius(), 6))
            assert {3.175, 4.7625} <= radien
        angaben = blatt.fundstellen()
        m, = [a for a in angaben if a.text == "2X⌀.370-.380"]
        anker = geo.hinweisziel(m.box, treffer, musterzeile=True)
        ringe = muster_am_ziel(anker, 2, geo.im_bereich((.17, .09, .395, .36)), treffer)
        kandidat, = [p for p in erg.pmi if p.typ == "Size_Diameter" and za.muster_deckt(2, ringe, p)]
        assert len(ringe) == 2 and kandidat.step_id == 38471
        assert kandidat.grenzen() == pytest.approx((9.398, 9.652))
        assert za.lese_angabe(m.text, 25.4).grenzen() == pytest.approx((9.652, 9.398))
        rahmen = [a for a in angaben if a.text.startswith("⌖")]
        zugeordnet = [(a, k) for a in rahmen if (k := geo.hinweisziel(a.box, treffer, blatt.durchmesseranfang))]
        assert len(zugeordnet) == 1
        a, ziel = zugeordnet[0]
        assert a.text == "⌖ | ⌀.005Ⓜ | A | B | C"
        gleich = [p for p in erg.pmi if p.typ == "Position" and p.material == "M" and p.wert == pytest.approx(.127)]
        assert len(gleich) > 1
        p, = [p for p in gleich if p.flaechen & ziel.flaechen]
        assert p.bezug_text() == "A|B|C" and p.flaechen == set(ziel.flaechen)
        for i in p.flaechen:
            zylinder = BRepAdaptor_Surface(modell.flaechen[i]).Cylinder()
            assert zylinder.Location().Coord()[:2] == pytest.approx((63.5, 63.1952))
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


@pytest.mark.parametrize(("geschlossen", "abzweig", "einzeln"),
                         [(True, False, False), (True, False, True), (False, False, True), (True, True, False)])
def test_pfeil_aus_getrennten_strichen_braucht_geschlossene_kontur(app, tmp_path, geschlossen, abzweig, einzeln):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    import pypdfium2 as pdf
    w = PdfWriter()
    seite = w.add_blank_page(400, 200)
    # Der Kreis rechts wird links vom Pfeil getroffen. Die Schraffur beruehrt den Hinweisstrich.
    linien = ["0.45 w", "90 100 m 240 100 l S",
              "232 101.3 m 232 98.7 l S 232 98.7 m 240 100 l S" if einzeln else "232 101.3 m 232 98.7 l 240 100 l S", "232 100.1 m 236 100.1 l S"]
    if geschlossen:
        linien.append("240 100 m 232 101.3 l S")
    if abzweig:
        linien.append("235 100 m 235 102 l S")
    phi = np.linspace(0., 2*np.pi, 65)
    for i, t in enumerate(phi):
        linien.append(f"{250+10*np.cos(t):.4f} {100+10*np.sin(t):.4f} " + ("m" if i == 0 else "l"))
    linien.append("h S")
    strom = DecodedStreamObject()
    strom.set_data("\n".join(linien).encode("ascii"))
    seite[NameObject("/Contents")] = w._add_object(strom)
    pfad = tmp_path / "Kontur.pdf"
    w.write(pfad)
    with pdf.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        g = Blattgeometrie(blatt)
        kreis, = g.kreise
        ring = replace(kreis, flaechen=frozenset([42]))
        ziel = g.hinweisziel((50/400, .45, 90/400, .55), [ring])
        assert ziel == (ring if geschlossen and not abzweig else None)
        blatt.schliesse()


@pytest.mark.parametrize("anzahl", [False, True])
def test_anschluss_am_durchmesser_unterscheidet_mengenpraefix(app, tmp_path, anzahl):
    import pypdfium2 as pdf
    bild = QtGui.QImage(str(Path(__file__).parent / "daten/nist_d2mi_904_rahmen.png")).copy(98, 15, 131, 39)
    pfad = tmp_path / "Masszeile.pdf"
    schreiber = QtGui.QPdfWriter(str(pfad))
    schreiber.setResolution(72)
    with QtGui.QPainter(schreiber) as maler:
        if anzahl:
            maler.setFont(QtGui.QFont("Helvetica", 12))
            maler.drawText(40, 62, "2X")
        maler.drawImage(QtCore.QRectF(60 if anzahl else 40, 50, bild.width()/3, bild.height()/3), bild)
    with pdf.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        h, w = blatt.bild.shape[:2]
        y, x = np.nonzero(blatt.bild.min(axis=2) < 190)
        box = ((x.min()-4)/w, (y.min()-4)/h, (x.max()+4)/w, (y.max()+4)/h)
        assert blatt.durchmesseranfang(box) != anzahl
        blatt.schliesse()


@pytest.mark.parametrize(("winkel", "spiegel"), [(27.5, 1), (123.4, -1)])
def test_schraeg_gedruckte_hauptansicht_im_dialog(app, tmp_path, winkel, spiegel):
    import pypdfium2 as pdf
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    teil = _teil()
    gruppe, = modellkreise(teil)
    weg = QtGui.QTransform().translate(250, 300).rotate(winkel).scale(2.7, spiegel*2.7)
    pfad = tmp_path / "Gedrehte Ansicht.pdf"
    pdfwriter = QtGui.QPdfWriter(str(pfad))
    pdfwriter.setResolution(72)
    with QtGui.QPainter(pdfwriter) as maler:
        maler.setTransform(weg)
        for k in gruppe:
            maler.drawEllipse(QtCore.QPointF(k.x, k.y), k.r, k.r)
    with pdf.PdfDocument(pfad) as doc:
        dialog = Zeichnungsabgleich(doc, [], lambda _: None, (str(pfad), ""), einzelteil=teil)
        try:
            dialog.registrieren.click()
            dialog.ansicht.bereich.emit((0., 0., 1., 1.))
            assert dialog.auftrag.wait(10000)
            app.processEvents()
            kreise = dialog.kreise[0]
            assert len(kreise) == 4
            # Zwei Bohrungen sind gleich gross. Unabhaengig die Reihenfolge auf dem Blatt pruefen.
            erwartet = sorted(gruppe, key=lambda k: weg.map(QtCore.QPointF(k.x, k.y)).x())
            assert [k.flaechen for k in sorted(kreise, key=lambda k: k.x)] == [k.flaechen for k in erwartet]
        finally:
            dialog.blatt.schliesse()
            dialog.close()


def test_freier_drehwinkel_mit_fremdkreis_und_mehrdeutiger_symmetrie():
    gruppe = [Blattkreis(x, y, r, frozenset([i])) for i, (x, y, r) in
              enumerate(((0, 0, 2), (18, 5, 2), (11, 29, 4), (20, 15, 5)))]
    def drehen(k):
        q = (k.x + 1j*k.y)*3*np.exp(.49j) + 260 + 160j
        return Blattkreis(q.real, q.imag, 3*k.r)
    blatt = [Blattkreis(450, 210, 12)] + [drehen(k) for k in gruppe]
    assert [k.flaechen for k in zuordnen(blatt, [gruppe])] == [k.flaechen for k in gruppe]
    gerundet = [replace(k, x=round(k.x*2)/2, y=round(k.y*2)/2, r=round(k.r*2)/2) for k in blatt]
    assert [k.flaechen for k in zuordnen(gerundet, [gruppe])] == [k.flaechen for k in gruppe]
    # Zwei exakt passende Muster im Modell unterscheiden sich um 28 Grad.
    kopie = [replace(drehen(k), flaechen=frozenset([i+4])) for i, k in enumerate(gruppe)]
    assert not zuordnen(blatt, [gruppe+kopie])
    dreieck = [Blattkreis(30*np.cos(t), 30*np.sin(t), 2, frozenset([i]))
               for i, t in enumerate(np.arange(3)*2*np.pi/3)]
    assert not zuordnen([drehen(k) for k in dreieck], [dreieck])


def _neige(flaechen):
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    trafo = gp_Trsf()
    trafo.SetRotation(gp_Ax1(gp_Pnt(13, -29, 9), gp_Dir(1., 2., -1.)), .83)
    lage = TopLoc_Location(trafo)
    return [topods.Face(f.Moved(lage)) for f in flaechen]


def test_geneigte_bohrgruppe_und_zweite_ansichtsrichtung(app):
    teil = _teil()
    original, = modellkreise(teil)
    blatt = [Blattkreis(3*k.x+80, -3*k.y+170, 3*k.r) for k in original]
    geneigt = _neige(teil.flaechen)
    treffer = zuordnen(blatt, modellkreise(SimpleNamespace(flaechen=geneigt)))
    assert [k.flaechen for k in treffer] == [k.flaechen for k in original]
    # Die gleiche Gruppe auf einer anderen Flaeche ist auf dem Blatt nicht unterscheidbar.
    beide = modellkreise(SimpleNamespace(flaechen=[*teil.flaechen, *geneigt]))
    assert len(beide) == 2 and not zuordnen(blatt, beide)


@pytest.mark.parametrize("fremdkreis", [False, True])
def test_mengenmass_im_dialog_mit_vollstaendiger_flaechenzuordnung(app, tmp_path, monkeypatch, fremdkreis):
    import pypdfium2 as pdf
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    teil = _teil()
    gruppe, = modellkreise(teil)
    zielringe = [k for k in gruppe if k.r == 2]
    beide = set.union(*(set(k.flaechen) for k in zielringe))
    gut = Pmi("mass", "Size_Diameter", nennwert=4., flaechen=beide, nummer=1)
    einzeln = replace(gut, flaechen=set(zielringe[0].flaechen), nummer=2)
    extra = replace(gut, flaechen=beide | {999}, nummer=3)
    pfad = tmp_path / "Muster.pdf"
    _blatt(pfad, text="2X Ø4", fremdkreis=fremdkreis)
    with pdf.PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, [einzeln, extra, gut], lambda _: None, (str(pfad), ""), einzelteil=teil)
        try:
            d.einheit.setCurrentIndex(1)
            a = next(a for a in d.seiten[0] if a.text.startswith("2X"))
            d.waehle(a)
            assert d.zuordnung.currentData() is None
            d.registrieren.click()
            d.ansicht.bereich.emit((.12, .11, .46, .3))
            assert d.auftrag.wait(10000)
            app.processEvents()
            anker = d.zielvorschlaege[a]
            assert anker is not None
            if fremdkreis:
                assert d.zuordnung.currentData() is None
                d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(gut)]))
                d.bestaetigen.click()
                assert za.befund(a, 1.) == "offen"
                anderer = next(k for k in d.kreise[0] if k.flaechen <= beide and k != anker)
                d.ansicht.musterkreis_gewaehlt.emit(anderer)
            assert d.zuordnung.currentData() == d.modellindex[id(gut)]
            d.bestaetigen.click()
            assert za.befund(a, 1.) == "gleich" and len(a.musterziele) == 2
            datei = tmp_path / "Bohrbild.csv"
            monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(datei), "CSV"))
            d._export()
            with datei.open(encoding="utf-8-sig") as f:
                zeile = next(z for z in csv.DictReader(f, delimiter=";") if z["Angabe"].startswith("2X"))
            orte = zeile["Bohrbild (x/Breite, y/Höhe, Radius/Breite je Bohrung)"].split(" | ")
            assert len(orte) == 2 and zeile["Befund"] == "Werte gleich"
            for wort, ziel in zip(orte, a.musterziele):
                assert tuple(map(float, wort.split())) == pytest.approx(ziel.ort, abs=1.e-6)
            # Die Pruefung einer anderen Ansicht auf demselben Blatt behaelt den bestaetigten Befund.
            d.registrieren.click()
            d.ansicht.bereich.emit((.8, .8, .95, .95))
            assert d.auftrag.wait(10000)
            app.processEvents()
            assert za.befund(a, 1.) == "gleich" and len(d._muster(a, 2)) == 2
            for falsch in (einzeln, extra):
                d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(falsch)]))
                d.bestaetigen.click()
                assert za.befund(a, 1.) == "offen"
            d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(gut)]))
            d.text.setPlainText("2× Ø4.1")
            d.bestaetigen.click()
            assert za.befund(a, 1.) == "geaendert"
            d.text.setPlainText("3X Ø4")
            d.bestaetigen.click()
            assert za.befund(a, 1.) == "offen"
        finally:
            d.blatt.schliesse()
            d.close()

def test_einzel_pmi_aus_ap242_pro_bohrung_pruefen_und_exportieren(app, tmp_path, monkeypatch):
    import pypdfium2 as pdf
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from programm.kern.step_schreiben import schreibe
    from programm.ui.lader import lade_alles
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich

    quelle, ziel = (str(tmp_path / name) for name in ("Bohrungen.stp", "Einzelmasse.stp"))
    writer = STEPControl_Writer()
    schema = Interface_Static.CVal("write.step.schema")
    try:
        assert Interface_Static.SetCVal("write.step.schema", "AP242DIS")
        assert writer.Transfer(_teil().form, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(quelle) == IFSelect_RetDone
    finally:
        Interface_Static.SetCVal("write.step.schema", schema)
    teil = lade_alles(quelle).modell
    gruppe, = modellkreise(teil)
    ringe = sorted((k for k in gruppe if k.r == 2), key=lambda k: k.x)
    masse = [Pmi("mass", "Size_Diameter", nennwert=4.+i*.1, flaechen=set(k.flaechen),
                 quelle="eigen", nummer=901+i, step_id=-901-i) for i,k in enumerate(ringe)]
    assert schreibe(quelle, ziel, masse, teil).neu == [901, 902]
    erg = lade_alles(ziel)
    assert len(erg.pmi) == 2 and erg.modell.datei.schema.startswith("AP242")
    pfad = tmp_path / "Bohrbild.pdf"
    _blatt(pfad, text="2X Ø4")
    markiert = []
    with pdf.PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, erg.pmi, markiert.append, (str(pfad), ziel), einzelteil=erg.modell)
        try:
            d.einheit.setCurrentIndex(1)
            a = next(a for a in d.seiten[0] if a.text.startswith("2X"))
            d.waehle(a)
            d.registrieren.click()
            d.ansicht.bereich.emit((.12, .11, .46, .3))
            assert d.auftrag.wait(10000)
            app.processEvents()
            assert d.zuordnung.currentData() == -2 and not d.einzel.isHidden()
            for i,z in enumerate(d.einzel.ziele):
                d.einzel.bohrung.setCurrentIndex(i)
                assert markiert[-1] is z.modell and z.modell.flaechen <= z.flaechen
            d.bestaetigen.click()
            assert a.modell is None and za.befund(a, 1.) == "geaendert"
            assert {m.step_id for m in a.zugeordnete_pmi()} == {m.step_id for m in erg.pmi}
            datei = tmp_path / "Einzel.csv"
            monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(datei), "CSV"))
            d._export()
            with datei.open(encoding="utf-8-sig") as f:
                zeilen = list(csv.DictReader(f, delimiter=";"))
            assert len(zeilen) == 2
            for i,(zeile,z) in enumerate(zip(zeilen,a.musterziele), 1):
                assert zeile["Bohrung im Muster"] == f"{i}/2" and zeile["Gesamtbefund des Bohrbilds"] == "Abweichend"
                assert int(zeile["Quell-ID der Modell-PMI"]) == z.modell.step_id
                assert zeile["Befund"] == ("Abweichend" if z.modell.nennwert > 4 else "Werte gleich")
                assert tuple(map(float,zeile["Bohrbild (x/Breite, y/Höhe, Radius/Breite je Bohrung)"].split())) == pytest.approx(z.ort, abs=1.e-6)

            d.registrieren.click()
            d.ansicht.bereich.emit((.8, .8, .95, .95))
            assert d.auftrag.wait(10000)
            app.processEvents()
            assert za.befund(a, 1.) == "geaendert"
            bleibt = next(m for m in erg.pmi if m.nennwert == 4)
            d.setze_modell([bleibt])
            assert za.befund(a, 1.) == "offen"
            offen = next(i for i,z in enumerate(d.einzel.ziele) if z.modell is None)
            d.einzel.bohrung.setCurrentIndex(offen)
            assert d.einzel.mass.count() == 2
            d.einzel.mass.setCurrentIndex(1)
            d.bestaetigen.click()
            assert a.musterziele[offen].nur_zeichnung and za.befund(a, 1.) == "geaendert"
            d.setze_modell(erg.pmi)
            assert not a.musterziele[offen].nur_zeichnung and za.befund(a, 1.) == "offen"
            # Eine zweite PMI auf derselben Bohrung darf der Zahlenwert nicht aufloesen.
            richtig = next(m for m in erg.pmi if m is not bleibt)
            doppelt = replace(richtig, nennwert=4., nummer=77, step_id=-77)
            d.setze_modell([*erg.pmi, doppelt])
            d.einzel.bohrung.setCurrentIndex(offen)
            assert d.einzel.mass.count() == 4 and d.einzel.mass.currentIndex() == 0
            d.einzel.mass.setCurrentIndex(d.einzel.mass.findText(f"#77  {doppelt.wert_text()}"))
            d.bestaetigen.click()
            assert za.befund(a, 1.) == "gleich" and a.musterziele[offen].modell is doppelt
        finally:
            d.blatt.schliesse()
            d.close()

@pytest.mark.parametrize("gabel", ["knick", "schaft", "quer", "kreuzung", "drei", "offen", "gleiches_ziel", "fremdkreis", "schleife"])
def test_gegabelte_hinweislinie_im_zeichnungsabgleich(app, tmp_path, gabel):
    import pypdfium2 as pdf
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    anzahl = 3 if gabel == "drei" else 2
    teil = _teil(((23, 56/3, 2),) if anzahl == 3 else ())
    gruppe, = modellkreise(teil)
    gruppe = [k for k in gruppe if k.r == 2]
    masse = [Pmi("mass", "Size_Diameter", nennwert=4., flaechen=set(k.flaechen), nummer=i)
             for i, k in enumerate(gruppe, 1)]
    pfad = tmp_path / "Pfeilzweige.pdf"
    _blatt(pfad, text=f"{anzahl}X Ø4", fremdkreis=True, gabel=gabel)
    with pdf.PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, masse, lambda _: None, (str(pfad), ""), einzelteil=teil)
        try:
            d.einheit.setCurrentIndex(1)
            a = next(a for a in d.seiten[0] if a.text.startswith(f"{anzahl}X"))
            d.waehle(a)
            d.registrieren.click()
            d.ansicht.bereich.emit((.12, .11, .46, .3))
            assert d.auftrag.wait(10000)
            app.processEvents()
            assert len(d.sichtkreise[0]) == 5 and len(d.kreise[0]) == 2+anzahl
            if gabel in ("knick", "schaft", "quer", "drei"):
                assert d.zuordnung.currentData() == -2
                assert {k.flaechen for k in d._muster(a, anzahl)} == {k.flaechen for k in gruppe}
                d.bestaetigen.click()
                assert za.befund(a, 1.) == "gleich"
                assert not d.blattgeometrie.hinweisgruppe(a.box, d.kreise[0], anzahl+1)
            else:
                assert d.zielvorschlaege[a] is None and not d._muster(a, anzahl)
                assert za.befund(a, 1.) == "offen"
        finally:
            d.blatt.schliesse()
            d.close()


@pytest.mark.parametrize("zusatz", [False, True])
def test_freie_grafische_masszeile_beim_zuordnen_des_bohrbilds(app, tmp_path, zusatz):
    from pypdfium2 import PdfDocument
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    pfad = tmp_path / "Freie Zeile.pdf"
    pdf = QtGui.QPdfWriter(str(pfad))
    pdf.setResolution(72)
    pdf.setPageSize(QtGui.QPageSize(QtCore.QSizeF(1900, 1230), QtGui.QPageSize.Unit.Point))
    pdf.setPageMargins(QtCore.QMarginsF(0, 0, 0, 0))
    bild = QtGui.QImage(str(Path(__file__).parent / "daten/nist_d2mi_904_4x_durchmesser.png"))
    with QtGui.QPainter(pdf) as maler:
        for x,y,r in ((8,7,2), (29,9,2), (13,29,3), (40,25,4)):
            maler.drawEllipse(QtCore.QPointF(300+5*x, 500+5*y), 5*r, 5*r)
        maler.drawImage(QtCore.QRectF(684, 312, 144, 16), bild)
        if zusatz:
            maler.drawRect(835, 317, 5, 6)
            maler.drawLine(835, 317, 840, 323)
        tip = np.array([350., 535.])
        knie = np.array([550., 320.])
        maler.drawLine(QtCore.QPointF(679, 320), QtCore.QPointF(*knie))
        maler.drawLine(QtCore.QPointF(*knie), QtCore.QPointF(*tip))
        v = (knie-tip)/np.linalg.norm(knie-tip)
        n = np.array([-v[1], v[0]])
        maler.setPen(QtCore.Qt.PenStyle.NoPen)
        maler.setBrush(QtCore.Qt.GlobalColor.black)
        maler.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*tip), QtCore.QPointF(*(tip+10*v+2*n)),
                                           QtCore.QPointF(*(tip+10*v-2*n))]))
    with PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, [], lambda _: None, (str(pfad), ""), einzelteil=_teil())
        try:
            assert not d.blatt.textbereiche and not d.seiten[0]
            def registrieren():
                d.registrieren.click()
                d.ansicht.bereich.emit((.14,.38,.29,.56))
                assert d.auftrag.wait(10000)
                app.processEvents()
            registrieren()
            assert len(d.kreise[0]) == 4
            if zusatz:
                assert not d.seiten[0]
                return
            a, = d.seiten[0]
            assert a.text == "4X⌀.215-.225" and d.zielvorschlaege[a] is not None
            d.waehle(a)
            registrieren()
            assert d.seiten[0] == [a]
            d.entfernen.click()
            registrieren()
            assert not d.seiten[0]
        finally:
            d.blatt.schliesse()
            d.close()


def test_symmetrisches_bohrbild_nur_mit_vollstaendiger_flaechenmenge():
    ringe = [Blattkreis(x, y, 3, frozenset([i])) for i, (x, y) in enumerate(((0,0),(0,20),(35,0),(35,20)))]
    gruppe = zuordnen(ringe, [ringe], mit_gruppen=True)
    assert len(gruppe) == 4 and all(not k.flaechen and len(k.tauschgruppe) == 4 for k in gruppe)
    mass = Pmi("mass", "Size_Diameter", nennwert=6, flaechen=set(range(4)))
    assert za.muster_deckt(4, gruppe, mass)
    assert not za.muster_deckt(3, gruppe[:3], mass)
    assert not za.muster_deckt(4, [*gruppe[:3], gruppe[0]], mass)
    assert not za.muster_deckt(4, gruppe, replace(mass, typ="Size_Radius"))
    for flaechen in ({0,1,2}, {0,1,2,3,4}):
        assert not za.muster_deckt(4, gruppe, replace(mass, flaechen=flaechen))
    andere = [replace(k, flaechen=frozenset([i+10])) for i,k in enumerate(ringe)]
    assert not zuordnen(ringe, [ringe, andere], mit_gruppen=True)


def test_symmetrisches_mengenmass_im_zeichnungsabgleich(app, tmp_path, monkeypatch):
    from pypdfium2 import PdfDocument
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    bohrungen = ((8,7,2), (38,7,2), (12,29,2), (34,29,2))
    teil = _teil(bohrungen=bohrungen)
    achse, = modellkreise(teil)
    alle = Pmi("mass", "Size_Diameter", nennwert=4., nummer=1, step_id=100,
               flaechen=set().union(*(k.flaechen for k in achse)))
    einzeln = replace(alle, nummer=2, step_id=101, flaechen=set(achse[0].flaechen))
    pfad = tmp_path / "Symmetrie.pdf"
    _blatt(pfad, text="4X Ø4", bohrungen=bohrungen)
    with PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, [einzeln, alle], lambda _: None, (str(pfad), ""), einzelteil=teil)
        try:
            d.einheit.setCurrentIndex(1)
            a = next(a for a in d.seiten[0] if a.text.startswith("4X"))
            d.waehle(a)
            for wiederholung in range(2):
                d.registrieren.click()
                d.ansicht.bereich.emit((.12, .11, .46, .30))
                assert d.auftrag.wait(10000)
                app.processEvents()
                assert d.zuordnung.currentData() == d.modellindex[id(alle)]
                assert d.zuordnung.findData(-2) < 0
                assert len(d.ansicht.kreismarken) == 4
                assert all(item.pen().style() == QtCore.Qt.PenStyle.DashLine for _,item in d.ansicht.kreismarken)
                if wiederholung:
                    assert za.befund(a, 1.) == "gleich"
                d.bestaetigen.click()
                assert len(a.musterziele) == 4 and all(not z.flaechen for z in a.musterziele)
                assert a.modell is alle and za.befund(a, 1.) == "gleich"
            d.text.setPlainText("4X Ø4.2")
            d.bestaetigen.click()
            assert za.befund(a, 1.) == "geaendert"
            datei = tmp_path / "Befund.csv"
            monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(datei), "CSV"))
            d._export()
            with datei.open(encoding="utf-8-sig") as f:
                zeile = next(z for z in csv.DictReader(f, delimiter=";") if z["Angabe"].startswith("4X"))
            assert zeile["Nur als Gruppe zugeordnet"] == "1" and zeile["Quell-ID der Modell-PMI"] == "100"
            assert len(zeile["Bohrbild (x/Breite, y/Höhe, Radius/Breite je Bohrung)"].split(" | ")) == 4
        finally:
            d.blatt.schliesse()
            d.close()


def test_d2mi_904_symmetrisches_vierfachmass(app):
    from pypdfium2 import PdfDocument
    from programm.ui.lader import lade_alles
    from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
    pfad = Path(__file__).parents[1] / "daten/nist_d2mi/NIST-D2MI-Models/827-9999-904 rev c.pdf"
    if not pfad.exists():
        pytest.skip("Lokales NIST-D2MI-Referenzpaket fehlt")
    erg = lade_alles(str(pfad.with_suffix(".stp")))
    with PdfDocument(pfad) as doc:
        d = Zeichnungsabgleich(doc, erg.pmi, lambda _: None, (str(pfad), erg.pfad), einzelteil=erg.modell)
        try:
            d.seite.setValue(3)
            d.einheit.setCurrentIndex(2)
            d.registrieren.click()
            d.ansicht.bereich.emit((.32, .33, .55, .57))
            assert d.auftrag.wait(10000)
            app.processEvents()
            a = next(a for a in d.seiten[2] if a.text == "4X⌀.215-.225")
            d.waehle(a)
            d.bestaetigen.click()
            assert a.modell.step_id == 103256 and len(a.modell.flaechen) == 8
            assert len(a.musterziele) == 4 and all(not z.flaechen for z in a.musterziele)
            assert a.modell.grenzen() == pytest.approx((5.461, 5.715))
            assert not a.zielkonflikt and za.befund(a, 25.4) == "offen"
        finally:
            d.blatt.schliesse()
            d.close()
