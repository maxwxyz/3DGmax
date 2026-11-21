"""Koplanare Flaechen aus einem Einzelrahmen auf dem Blatt gegen STEP-Geometrie pruefen."""

import csv
from dataclasses import replace
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from PySide6.QtWidgets import QFileDialog

from programm.kern import zeichnungsabgleich as za
from programm.kern.blattverbund import Verbundindex
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from programm.ui.lader import lade_alles
from tests.conftest import pfad

NIST = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files"
CTC02 = "nist_ctc_02_asme1_ap242-e2.stp.gz"
TEXT = "⌓ | 0.1\n4 COPLANAR\nSURFACES"


def _zeichnung(ziel, *, schraeg=True, zeilen=("4 COPLANAR", "SURFACES"), steghoehe=20, bezug=False):
    pdf = PdfWriter()
    seite = pdf.add_blank_page(620, 400)
    font = DictionaryObject({NameObject(k): NameObject(v) for k,v in
                             [("/Type","/Font"), ("/Subtype","/Type1"), ("/BaseFont","/Helvetica")]})
    seite[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
        NameObject("/F1"): pdf._add_object(font)})})
    matrix = ".866 -.5 0 1" if schraeg else "1 0 0 1"
    inhalt = [f"q {matrix} 125 160 cm 0.4 w", f"0 0 {75 if bezug else 57} 20 re S",
              f"30 0 m 30 {steghoehe} l S", "5 5 m 5 10.5 9.5 15 15 15 c 20.5 15 25 10.5 25 5 c h S"]
    def zeile(x, y, wort):
        inhalt.append(f"BT /F1 13.5 Tf 1 0 0 1 {x} {y} Tm ({wort}) Tj ET")
    zeile(34, 5, "0.1")
    if bezug:
        inhalt.append("57 0 m 57 20 l S")
        zeile(61, 5, "A")
    for i, wort in enumerate(zeilen, 1):
        zeile(1, -18*i, wort)
    stream = DecodedStreamObject()
    stream.set_data("\n".join([*inhalt, "Q"]).encode("ascii"))
    seite[NameObject("/Contents")] = pdf._add_object(stream)
    pdf.write(ziel)


@pytest.mark.parametrize("schraeg,zeilen,steghoehe,erwartet", [
    (True, ("4 COPLANAR", "SURFACES"), 20, TEXT),
    (False, ("2 COPLANAR", "SURFACES"), 20, TEXT.replace("4 ", "2 ")),
    (True, ("4 COPLANAR", "SURFACE"), 20, None),
    (True, ("4 COPLANAR", "SURFACES"), 13, None),
    (True, ("4 C0PLANAR", "SURFACES"), 20, None),
    (True, ("4 COPLANAR", "SURFACES", "EXCEPT RIB"), 20, None),
])
def test_einzelrahmen_mit_vollstaendigem_hinweis(tmp_path, schraeg, zeilen, steghoehe, erwartet):
    ziel = tmp_path/"Blatt.pdf"
    _zeichnung(ziel, schraeg=schraeg, zeilen=zeilen, steghoehe=steghoehe)
    with pdfium.PdfDocument(ziel) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        try:
            funde = blatt.fundstellen()
            gelesen = [a.text for a in funde if a.rahmenbox and za.lese_angabe(a.text, 1)]
            assert gelesen == ([erwartet] if erwartet else [])
            if erwartet:
                assert all(a.text != "0.1" for a in funde)
        finally:
            blatt.schliesse()


def test_bezugsfach_bleibt_bei_gedrehtem_profil_erhalten(tmp_path):
    ziel = tmp_path/"MitBezug.pdf"
    _zeichnung(ziel, bezug=True)
    with pdfium.PdfDocument(ziel) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        try:
            fund, = blatt.fundstellen()
            assert fund.text == TEXT.replace("0.1", "0.1 | A")
            assert za.lese_angabe(fund.text, 1).bezug_text() == "A"
        finally:
            blatt.schliesse()


def test_wortlaut_und_geometrie_unabhaengig():
    erg = lade_alles(pfad(CTC02))
    m = next(p for p in erg.pmi if p.step_id == 53)
    index = Verbundindex(erg.pmi, erg.modell)
    a = za.Blattangabe(2, (0,0,1,1), TEXT, modell=m)
    q = za.lese_angabe(TEXT, 1)
    assert q.beschreibung == "4 COPLANAR SURFACES" and not m.beschreibung
    assert za.befund(a, 1., verbundindex=index) == "gleich"
    assert za.befund(a, 1.) == za.befund(a, None, verbundindex=index) == "offen"
    assert za.koplanarbefund(q, m, index).ist == 4
    idx = next(iter(m.flaechen))
    for anders in (replace(m, flaechen=m.flaechen-{idx}), replace(m, wert=.2),
                   replace(m, beschreibung="2 COPLANAR SURFACES")):
        assert za.befund(replace(a, modell=anders), 1, verbundindex=index) == "geaendert"
    for ziel, grund in ((2514, "ebenen"), (2516, "gekruemmt")):
        andere = m.flaechen-{min(m.flaechen)} | {erg.modell.step_zu_flaeche[ziel]}
        versetzt = replace(m, flaechen=andere, beschreibung=q.beschreibung)
        k = za.koplanarbefund(q, versetzt, index)
        assert (k.ist, k.grund) == (4, grund)
        assert za.befund(replace(a, modell=versetzt), 1., verbundindex=index) == "geaendert"
    m2 = replace(m, beschreibung=q.beschreibung)
    assert za.befund(replace(a, modell=m2, text="⌓ | 0.1"), 1., verbundindex=index) == "geaendert"
    assert za.befund(replace(a, modell=replace(m2,flaechen=set())), 1., verbundindex=index) == "offen"
    assert za.befund(replace(a, zielkonflikt=True), 1., verbundindex=index) == "offen"
    for text in (TEXT+"\nEXCEPT RIB", TEXT.replace("4 COPLANAR", "04 COPLANAR"),
                 TEXT.replace("⌓", "⏥"), TEXT.replace("4 COPLANAR", "4 COPLANAR\n4 COPLANAR")):
        assert za.lese_angabe(text, 1.) is None


@pytest.mark.parametrize("modell,zeichnung,blattnr,nr,faktor,anzahl,text", [
    (pfad(CTC02), "nist_ctc_02_asme1_rc.pdf", 3, 53, 1., 4, TEXT),
    (str(NIST/"nist_ctc_03_asme1_ap242-e2.stp"), "nist_ctc_03_asme1_rc.pdf", 1, 35, 25.4, 2,
     "⌓ | .01\n2 COPLANAR\nSURFACES"),
])
def test_nist_zeichnung_gegen_step_und_csv(fenster, tmp_path, monkeypatch, modell, zeichnung, blattnr, nr, faktor, anzahl, text):
    datei = NIST/"PDF"/zeichnung
    if not datei.exists() or not Path(modell).is_file():
        pytest.skip("Lokales NIST-Referenzpaar fehlt")
    ziel = tmp_path/"Pruefung.csv"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(datei), "PDF"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(ziel), "CSV"))
    fenster.lade(modell, warten=True)
    fenster.aktionen["zeichnungsabgleich"].trigger()
    d = fenster.zeichnungsabgleich
    try:
        d.seite.setValue(blattnr)
        d.einheit.setCurrentIndex(d.einheit.findData(faktor))
        angabe, = [a for a in d.seiten[blattnr-1] if "COPLANAR" in a.text]
        assert angabe.text == text and len(angabe.zeilenecken) == 4
        d.waehle(angabe)
        m = next(m for m in d.modell if m.step_id == nr)
        d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(m)]))
        d.bestaetigen.click()
        assert d._befund(angabe) == "gleich" and len(m.flaechen) == anzahl
        assert "Getrennte Flächen in derselben Ebene" in d.detail.text()
        d._export()
        with ziel.open(encoding="utf-8-sig") as f:
            daten = list(csv.DictReader(f, delimiter=";"))
        assert all(None not in z and None not in z.values() for z in daten)
        zeile, = [z for z in daten if z["Angabe"] == text]
        assert zeile["Befund"] == "Werte gleich" and zeile["Quell-ID der Modell-PMI"] == str(nr)
        assert f"Zeichnung {anzahl} · Modellflächen {anzahl}" in zeile["Prüfung der koplanaren Flächen"]
    finally:
        d.close()
