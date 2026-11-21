import csv
import math

import numpy as np
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from pypdfium2 import PdfDocument
from PySide6.QtWidgets import QFileDialog

from programm.kern.zeichnungsabgleich import befund
from programm.kern.zeichnungsansicht import Blattgeometrie, modellkreise
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from programm.kern.pmi import Pmi
from programm.ui.zeichnungsabgleich_ui import Zeichnungsabgleich
from test_zeichnungsansicht import _teil, _BOHRUNGEN


def _pdf(pfad, inhalt):
    w = PdfWriter()
    seite = w.add_blank_page(320, 200)
    font = DictionaryObject({NameObject(k): NameObject(v) for k,v in (
        ("/Type","/Font"), ("/Subtype","/Type1"), ("/BaseFont","/Helvetica"), ("/Encoding","/WinAnsiEncoding"))})
    seite["/Resources"][NameObject("/Font")] = DictionaryObject({NameObject("/F1"): w._add_object(font)})
    s = DecodedStreamObject()
    s.set_data("\n".join(inhalt).encode("ascii"))
    seite[NameObject("/Contents")] = w._add_object(s)
    w.write(pfad)


def _bogen(anfang, ende):
    # Kubische Viertelkreise auch in umgekehrter Pfadrichtung schreiben.
    t = np.linspace(anfang, ende, abs(ende-anfang)+1) * (math.pi/2)
    punkt = np.column_stack((np.cos(t), np.sin(t)))
    tangente = np.column_stack((-np.sin(t), np.cos(t))) * (4/3 * math.tan((t[1]-t[0])/4))
    def xy(p):
        return f"{p[0]:.8f} {p[1]:.8f}"
    teile = [xy(punkt[0])+" m"]
    for i in range(len(t)-1):
        teile.append(f"{xy(punkt[i]+tangente[i])} {xy(punkt[i+1]-tangente[i+1])} {xy(punkt[i+1])} c")
    return " ".join(teile) + " S"


@pytest.mark.parametrize(("neigung", "drehung"), [(1., 0), (.55, 90)])
def test_geteilte_bohrungsraender_bis_zum_csv(app, tmp_path, monkeypatch, neigung, drehung):
    teil = _teil()
    reihe, = modellkreise(teil)
    wand = next(k.flaechen for k in reihe if (k.x,k.y) == (8,7))
    andere = next(k.flaechen for k in reihe if (k.x,k.y) == (29,9))
    richtig = Pmi("mass", "Size_Diameter", nennwert=4., flaechen=set(wand), nummer=1)
    falsch = Pmi("mass", "Size_Diameter", nennwert=4.1, flaechen=set(andere), nummer=2)
    inhalt = []
    for i,(x,y,r) in enumerate(_BOHRUNGEN):
        # Der PDF-Drucker setzt die Boegen je Bohrung in einer lokalen Koordinatentransformation.
        inhalt.append(f"q {3*r} 0 0 {3*r*neigung} {80+3*x} {70+3*y*neigung} cm .03 w")
        for a,b in ([(2,4),(2,0)] if i%2 else [(2,1),(3,4),(0,1),(3,2)]):
            inhalt.append(_bogen(a,b))
        inhalt.append("Q")
    y = 70 + 21*neigung
    inhalt += [f"BT /F1 10 Tf 12 {y-3.5} Td <D8342E31> Tj ET",
               f".4 w 33 {y} m 98 {y} l S", f"98 {y} m 93 {y+1} l 93 {y-1} l h f"]
    pfad = tmp_path/"Geteilte Bohrungen.pdf"
    _pdf(pfad, inhalt)
    with PdfDocument(pfad) as doc:
        doc[0].set_rotation(drehung)
        dialog = Zeichnungsabgleich(doc, [falsch, richtig], lambda _: None, (str(pfad), ""), einzelteil=teil)
        try:
            dialog.einheit.setCurrentIndex(1)
            angabe = next(a for a in dialog.seiten[0] if a.text == "Ø4.1")
            dialog.waehle(angabe)
            dialog.registrieren.click()
            dialog.ansicht.bereich.emit((0.,0.,1.,1.))
            assert dialog.auftrag.wait(10000)
            app.processEvents()
            assert len(dialog.kreise[0]) == 4
            ziel = dialog.zielvorschlaege[angabe]
            assert ziel and ziel.flaechen == wand
            if neigung < 1:
                assert ziel.kurz/ziel.r == pytest.approx(neigung, abs=.002)
            dialog.bestaetigen.click()
            assert angabe.modell is richtig and befund(angabe, 1.) == "geaendert"
            csvpfad = tmp_path/"Ergebnis.csv"
            monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(csvpfad), "CSV"))
            dialog._export()
            with csvpfad.open(encoding="utf-8-sig") as f:
                row = next(r for r in csv.DictReader(f, delimiter=";") if r["Angabe"] == "Ø4.1")
            assert row["Hinweisziel (x/Breite, y/Höhe, Radius/Breite)"]
            assert bool(row["Hinweisellipse (kleine Halbachse/Breite, Drehwinkel in Grad)"]) == (neigung < 1)
        finally:
            dialog.blatt.schliesse()
            dialog.close()


def test_offene_mehrdeutige_und_nur_teilweise_sichtbare_raender(app, tmp_path):
    phi = np.linspace(0, math.tau, 13)
    ecken = [f"{math.cos(t):.7f} {math.sin(t):.7f}" for t in phi]
    rest = np.linspace(0, math.tau-.06, 65)
    fast_kreis = " l ".join(f"{math.cos(t):.7f} {math.sin(t):.7f}" for t in rest[1:])
    faelle = [
        [_bogen(0,2), _bogen(4,2)],
        [_bogen(0,2), _bogen(2,3)],
        [_bogen(0,2), _bogen(4,2), "1 0 m 2 .3 2 1 2 2 c S"],
        [_bogen(0,2), "q 1 1 4 4 re W n", _bogen(2,4), "Q"],
        [_bogen(0,2), _bogen(2,0)],
        [_bogen(0,2), "[.1 .2] 0 d", _bogen(2,4)],
        [_bogen(0,2), _bogen(2,4), "1 g .13 .80 .10 .40 re f"],
        [ecken[0]+" m "+" l ".join(ecken[1:7])+" l S", ecken[6]+" m "+" l ".join(ecken[7:])+" l S"],
        ["1 0 m " + fast_kreis + " l S"],
        [_bogen(0,4), "1 g .13 .80 .10 .40 re f"],
        ["[.1 .2] 0 d", _bogen(0,4)],
    ]
    inhalt = []
    for i, fall in enumerate(faelle):
        inhalt.extend([f"q 9 0 0 9 {15+28*i} 100 cm .04 w", *fall, "Q"])
    pfad = tmp_path/"Kontrollen.pdf"
    _pdf(pfad, inhalt)
    with PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        try:
            geo = Blattgeometrie(blatt, mit_ellipsen=True)
            k, = geo.kreise
            assert k.x/geo.groesse[0]*320 == pytest.approx(15, abs=.1)
        finally:
            blatt.schliesse()


@pytest.mark.parametrize("luecke", [False, True])
def test_platte_aus_geteilten_bohrungsraendern_mit_step_pmi(app, tmp_path, monkeypatch, luecke):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.pmi_lesen import lies_pmi_xcaf
    from programm.ui.lader import lade_alles
    from programm.ui.zeichnungskoerper_ui import Plattendialog

    pfad, ziel = tmp_path/"Bohrplatte.pdf", tmp_path/"Bohrplatte.stp"
    inhalt = [".4 w 40 40 150 100 re S"]
    for x,y,r in ((20,16,5), (48,28,4)):
        inhalt.append(f"q {2.5*r} 0 0 {2.5*r} {40+2.5*x} {40+2.5*y} cm .03 w")
        inhalt.extend((_bogen(0,2), _bogen(2,3 if luecke and x == 48 else 4), "Q"))
    _pdf(pfad, inhalt)
    with PdfDocument(pfad) as doc:
        d = Plattendialog(doc, pfad)
        try:
            d.einheit.setCurrentIndex(1)
            for feld, text in zip(d.texte, ("60","40","8"), strict=True):
                feld.setText(text)
            d.ansicht.bereich.emit((.10,.27,.62,.84))
            if luecke:
                assert not d.ringe and not d.speichern.isEnabled()
                return
            assert len(d.ringe) == 2
            for i,ring in enumerate(d.ringe):
                werte = ("20","16","Ø10 ±0.05") if ring.kreis.x < d.geometrie.groesse[0]/2 else ("48","28","Ø8 H7")
                for spalte, wert in enumerate(werte,1):
                    d.bohrtabelle.item(i,spalte).setText(wert)
            d.durchgehend.setChecked(True)
            assert d.speichern.isEnabled()
            monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(ziel), "STEP"))
            d.speichern.click()
            erg = lade_alles(str(ziel))
            volumen = GProp_GProps()
            brepgprop.VolumeProperties(erg.modell.form, volumen)
            assert volumen.Mass() == pytest.approx(8*(60*40-math.pi*(25+16)))
            assert len(erg.pmi) == 9 and all(p.grafisch and p.semantisch for p in erg.pmi)
            for quelle in (erg.pmi, lies_pmi_xcaf(erg.modell)):
                gross, klein = sorted((p for p in quelle if p.typ == "Size_Diameter"), key=lambda p: -p.nennwert)
                assert gross.grenzen() == pytest.approx((10.05, 9.95)) and klein.passung == "H7"
                for mass, erwartet in ((gross,(20,16,5)),(klein,(48,28,4))):
                    nr, = mass.flaechen
                    z = BRepAdaptor_Surface(erg.modell.flaechen[nr]).Cylinder()
                    assert (z.Location().X(), z.Location().Y(), z.Radius()) == pytest.approx(erwartet)
        finally:
            d.blatt.schliesse()
            d.close()
