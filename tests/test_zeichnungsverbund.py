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


@pytest.mark.parametrize("aenderung,bindung,felder,wortlaut,status", [
    ("", "gleich", ((), ()), "gleich", "gleich"),
    ("umkehren", "umgekehrt", ((), ()), "gleich", "geaendert"),
    ("trennen", "fehlt", ((), ()), "gleich", "geaendert"),
    ("dritter", "weitere", ((), ()), "gleich", "geaendert"),
    ("zahl", "gleich", ((), ("wert",)), "gleich", "geaendert"),
    ("bezug", "gleich", (("bezuege",), ()), "gleich", "geaendert"),
    ("hinweis", "gleich", ((), ()), "geaendert", "geaendert"),
    ("gruppe", "gleich", ((), ()), "gleich", "offen"),
    ("gesicht", "gleich", ((), ()), "gleich", "geaendert"),
    ("unbekannt", "offen", ((), ()), "gleich", "offen"),
])
def test_pdf_paar_gegen_semantischen_ftc07_verbund(ftc07, aenderung, bindung, felder, wortlaut, status):
    from programm.kern.blattverbund import Verbundindex, pruefe_rahmen
    from programm.kern.pmi_step import lies_toleranzen
    from programm.kern.zeichnungsabgleich import Blattangabe
    pmis = lies_toleranzen(ftc07)
    nach_id = {p.step_id: p for p in pmis}
    oben, unten = nach_id[15076], nach_id[15085]
    a = Blattangabe(2, (.64,.14,.76,.31), "⌓ | .070 | A | B | C\n⌓ | .015 | A", modell=oben,
                    verbundrahmen=True, unten=unten)
    if aenderung == "umkehren":
        oben.folgetoleranzen, unten.folgetoleranzen = [], [oben.step_id]
    elif aenderung == "trennen":
        oben.folgetoleranzen = []
    elif aenderung == "dritter":
        nach_id[14614].folgetoleranzen.append(unten.step_id)
    elif aenderung == "zahl":
        a.text = a.text.replace(".015", ".025")
    elif aenderung == "bezug":
        a.text = a.text.replace("A | B", "B | A")
    elif aenderung == "hinweis":
        a.text += "\n4 COPLANAR SURFACES\nSIM REQT"
    elif aenderung == "gruppe":
        a.text += "\nSIM REQT"
        oben.beschreibung = unten.beschreibung = "SIM REQT"
    elif aenderung == "gesicht":
        unten.flaechen = nach_id[14623].flaechen
    elif aenderung == "unbekannt":
        pmis.append(oben)
    index = Verbundindex(pmis)
    r = pruefe_rahmen(a, 25.4, index)
    assert (r.verknuepfung, r.felder, r.wortlaut, r.status) == (bindung, felder, wortlaut, status)
    assert befund(a, 25.4, verbundindex=index) == status
    assert befund(a, None, verbundindex=index) == "offen"


def test_zuordnung_beider_step_zeilen_auf_originalblatt(fenster, tmp_path, monkeypatch):
    import csv
    from PySide6.QtWidgets import QFileDialog
    from tests.conftest import pfad
    quelle = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/PDF/nist_ftc_07_asme1_rd.pdf"
    if not quelle.is_file():
        pytest.skip("Lokale NIST-Referenzzeichnung fehlt")
    fenster.lade(pfad("nist_ftc_07_asme1_ap242-e2.stp"), warten=True)
    ausgabe = tmp_path/"Paare.csv"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(quelle), "PDF"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(ausgabe), "CSV"))
    fenster.aktionen["zeichnungsabgleich"].trigger()
    d = fenster.zeichnungsabgleich
    try:
        d.seite.setValue(3)
        d.einheit.setCurrentIndex(2)
        links, rechts = [a for a in d.seiten[2] if a.verbundrahmen]
        pmis = {p.step_id:p for p in d.modell}
        for a, oben, unten in [(links,15076,15085), (rechts,14614,14623)]:
            d.waehle(a)
            assert d.untere_zeile.isVisible()
            for combo, nr in ((d.zuordnung,oben), (d.untere_zeile,unten)):
                combo.setCurrentIndex(combo.findData(d.modellindex[id(pmis[nr])]))
            d.bestaetigen.click()
            assert [p.step_id for p in a.zugeordnete_pmi()] == [oben, unten]
            assert "Obere Zeile: Werte gleich · Untere Zeile: Werte gleich" in d.detail.text()
            assert "Obere Zeile verweist auf die untere" in d.detail.text()
            assert "Toleranzbeschreibungen: Abweichend" in d.detail.text()
            if a is rechts:
                assert "Text am Formelement #13858 · Eigenschaft #16453 · Darstellung #16454 · Grafik #16461 · Übereinstimmung" in d.detail.text()
                assert "Modellflächen 4 · Getrennte Flächen in derselben Ebene" in d.detail.text()
            else:
                assert "Text am Formelement" not in d.detail.text()
                assert "Koplanare Flächen" not in d.detail.text()
        d._export()
        with ausgabe.open(encoding="utf-8-sig") as f:
            zeilen = list(csv.DictReader(f, delimiter=";"))
        paare = [z for z in zeilen if z["STEP-ID der unteren Rahmenzeile"]]
        assert [(z["Quell-ID der Modell-PMI"], z["STEP-ID der unteren Rahmenzeile"]) for z in paare] == [
            ("15076","15085"), ("14614","14623")]
        assert all(z["Befund"] == "Abweichend" and z["Modellwert der unteren Rahmenzeile"] for z in paare)
        assert all(z["Quell-ID der Modell-PMI"] not in ("14623","15085") for z in zeilen)
        assert "Zeichnung 4 · Modellflächen 4" in paare[1]["Prüfung des Verbundrahmens"]
        assert "4 COPLANAR SURFACES\nSIM REQT" in paare[1]["Prüfung des Verbundrahmens"]
        d.waehle(rechts)
        for combo, nr in ((d.zuordnung,15076), (d.untere_zeile,15085)):
            combo.setCurrentIndex(combo.findData(d.modellindex[id(pmis[nr])]))
        assert "Zeichnung 4 · Modellflächen 1 · Flächenanzahl weicht ab" in d.detail.text()
        assert "Obere Zeile: Werte gleich · Untere Zeile: Werte gleich" in d.detail.text()
        d.setze_modell([p for p in d.modell if p.step_id != 14623])
        assert rechts.unten is None and d._befund(rechts) == "offen"
    finally:
        d.close()


@pytest.mark.parametrize("verweis,erwartet", [("", "fehlt"), ("#15085,#15076", "umgekehrt"),
                                             ("#15076,#14623", "fehlt")])
def test_gleiche_werte_mit_veraenderter_step_beziehung(tmp_path, verweis, erwartet):
    from programm.kern.blattverbund import Verbundindex, pruefe_rahmen
    from programm.kern.laden import lade_step
    from programm.kern.pmi_step import lies_toleranzen
    from programm.kern.zeichnungsabgleich import Blattangabe
    from tests.conftest import pfad
    quelle = Path(pfad("nist_ftc_07_asme1_ap242-e2.stp")).read_text()
    original = "#15086=GEOMETRIC_TOLERANCE_RELATIONSHIP('composite','',#15076,#15085);"
    assert quelle.count(original) == 1
    datei = tmp_path/"Geaenderter Verbund.stp"
    datei.write_text(quelle.replace(original, original.replace("#15076,#15085", verweis) if verweis else ""))
    pmis = lies_toleranzen(lade_step(str(datei)))
    nach_id = {p.step_id:p for p in pmis}
    a = Blattangabe(2, (.64,.14,.76,.31), "⌓ | .070 | A | B | C\n⌓ | .015 | A",
                    verbundrahmen=True, modell=nach_id[15076], unten=nach_id[15085])
    r = pruefe_rahmen(a, 25.4, Verbundindex(pmis))
    assert r.felder == ((), ()) and r.verknuepfung == erwartet and r.status == "geaendert"
