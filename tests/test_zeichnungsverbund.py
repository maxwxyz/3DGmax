"""Geneigte zweizeilige PDF-Rahmen mit gemeinsamem Merkmal und zugehoerigem Geltungshinweis."""

from pathlib import Path

import pypdfium2 as pdfium
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from programm.kern.schriftstreifen import zeilenvorschau
from programm.kern.zeichnungsabgleich import befund
from programm.kern.zeichnungsblatt import Zeichnungsblatt


def _zeichnung(pfad, *, trennwand=False, hinweis="SIM REQT 2", doppelt=False):
    pdf = PdfWriter()
    seite = pdf.add_blank_page(600, 400)
    schrift = DictionaryObject({NameObject(k): NameObject(v) for k,v in
                                [("/Type","/Font"), ("/Subtype","/Type1"), ("/BaseFont","/Helvetica")]})
    seite[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): pdf._add_object(schrift)})})
    inhalt = ["q .86 .5 0 1 160 145 cm .7 w",
              "0 0 29 48 re S", "29 24 43 24 re S", "29 0 43 24 re S",
              "72 24 22 24 re S", "94 24 22 24 re S", "72 0 22 24 re S",
              "5 20 m 5 33 24 33 24 20 c h S"]
    if trennwand:
        inhalt.append("0 24 m 29 24 l S")
    def zeile(x, y, text):
        inhalt.append(f"BT /F1 14 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET")
    for x, y, text in [(34,31,".070"), (34,7,".015"), (77,31,"A"), (99,31,"B"), (77,7,"A")]:
        zeile(x, y, text)
    zeile(0, -15, hinweis)
    if doppelt:
        zeile(8, -15, "SIM REQT 3")
    inhalt.append("Q")
    daten = DecodedStreamObject()
    daten.set_data("\n".join(inhalt).encode("ascii"))
    seite[NameObject("/Contents")] = pdf._add_object(daten)
    pdf.write(pfad)


@pytest.mark.parametrize("trennwand,hinweis,doppelt,erwartet", [
    (False, "SIM REQT 2", False, True), (True, "SIM REQT 2", False, False),
    (False, "SIM REQT EXTRA", False, False), (False, "SIM REQT 2", True, False),
])
def test_schraeges_pdf_mit_gemeinsamem_symbol(tmp_path, trennwand, hinweis, doppelt, erwartet):
    pfad = tmp_path/"Schraeg.pdf"
    _zeichnung(pfad, trennwand=trennwand, hinweis=hinweis, doppelt=doppelt)
    with pdfium.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        try:
            funde = [a for a in blatt.fundstellen() if a.zeilenecken]
            assert len(funde) == int(erwartet)
            if erwartet:
                assert funde[0].text == "⌓ | .070 | A | B\n⌓ | .015 | A\nSIM REQT 2"
                assert befund(funde[0], 25.4) == "offen"
        finally:
            blatt.schliesse()


def test_beide_verbundrahmen_auf_ftc07_blatt_drei():
    pfad = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/PDF/nist_ftc_07_asme1_rd.pdf"
    if not pfad.is_file():
        pytest.skip("Lokale NIST-Referenzzeichnung fehlt")
    with pdfium.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 2)
        try:
            alle = blatt.fundstellen()
            funde = [a for a in alle if "SIM REQT" in a.text]
            assert [a.text.splitlines() for a in funde] == [
                ["⌓ | .070 | A | B | C", "⌓ | .015 | A", "SIM REQT"],
                ["⌓ | .070 | A | B | C", "⌓ | .015 | A", "4 COPLANAR SURFACES", "SIM REQT"]]
            assert all(a.text != ".015" for a in alle)
            assert funde[0].box[2] < funde[1].box[0]
            for a in funde:
                assert a.simultan is None and befund(a, 25.4) == "offen"
                bild = zeilenvorschau(blatt, a.zeilenecken, 520, 140)
                try:
                    from programm.kern.zeichnungsblatt import _zellen
                    zellen = _zellen(bild.to_numpy().min(axis=2) < 220)
                    assert sum(1 for l,t,r,b in zellen if b-t >= 15 and r-l >= 10) >= 5
                finally:
                    bild.close()
        finally:
            blatt.schliesse()


def test_verbund_im_dateimenue_und_in_der_pruefliste(fenster_ctc01, tmp_path, monkeypatch):
    import csv
    from PySide6.QtWidgets import QFileDialog
    pfad = tmp_path/"Verbund.pdf"
    ausgabe = tmp_path/"Vergleich.csv"
    _zeichnung(pfad)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(pfad), "PDF"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(ausgabe), "CSV"))
    fenster_ctc01.aktionen["zeichnungsabgleich"].trigger()
    dialog = fenster_ctc01.zeichnungsabgleich
    try:
        angabe, = [a for a in dialog.seiten[0] if a.zeilenecken]
        dialog.waehle(angabe)
        assert dialog.text.toPlainText() == angabe.text
        assert dialog.ausschnitt.pixmap().height() > 62
        dialog._export()
        with ausgabe.open(encoding="utf-8-sig") as f:
            zeile, = [z for z in csv.DictReader(f, delimiter=";") if z["Angabe"] == angabe.text]
        assert zeile["Befund"] == dialog._befunde()["offen"]
        assert len(zeile["Ecken der Maßzeile in Leserichtung (x/Breite, y/Höhe)"].split(" | ")) == 4
        assert not zeile["Befund der Toleranzgruppe"]
    finally:
        dialog.close()
