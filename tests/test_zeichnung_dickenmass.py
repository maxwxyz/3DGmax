"""Wiederholtes lineares Zeichnungsmass, Auflagenzahl und gepruefter CSV-Befund."""
from dataclasses import replace

import pypdfium2 as pdfium
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from programm.kern import zeichnungsabgleich as za
from programm.kern.blattverbund import Verbundindex
from programm.kern.zeichnung_dickenmass import projizierte_linearmasse
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_dickenschrift import QUELLE, ZIELE


def _massblatt(pfad, text, ohne, zusatz, gedreht, *, gegenpfeil=False):
    pdf = PdfWriter()
    seite = pdf.add_blank_page(600,450)
    font = DictionaryObject({NameObject(k): NameObject(v) for k,v in [
        ("/Type","/Font"), ("/Subtype","/Type1"), ("/BaseFont","/Helvetica"), ("/Encoding","/WinAnsiEncoding")]})
    seite[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"):pdf._add_object(font)})})
    # Schraeg projizierte Schreib- und Massachsen, zwei parallele Hilfslinien.
    linien = {"oben":"-100 20 m 14 20 l S", "unten":"-100 -20 m 14 -20 l S",
              "pfeil":"0 20 m -2.6 30 l 2.6 30 l h f", "schaft":"0 30 m 0 45 l S",
              "ende":"0 -20 m 0 -40 l S",
              "kreis":"6 -20 m 6 -16.686 3.314 -14 0 -14 c -3.314 -14 -6 -16.686 -6 -20 c "
                      "-6 -23.314 -3.314 -26 0 -26 c 3.314 -26 6 -23.314 6 -20 c h S"}
    if gegenpfeil:
        linien["kreis"] = "0 -20 m -2.6 -30 l 2.6 -30 l h f"
        linien["ende"] = "0 -30 m 0 -45 l S"
    matrix = ".8 -.4 .65 .7" if not gedreht else "-.8 .4 -.65 -.7"
    start = -24 if gegenpfeil else -44
    inhalt = [f"q {matrix} 300 225 cm .4 w", *(s for k,s in linien.items() if k != ohne),
              rf"BT /F1 18 Tf 1 0 0 1 {start} -6 Tm ({text}) Tj ET", zusatz, "Q"]
    stream = DecodedStreamObject()
    stream.set_data("\n".join(inhalt).encode("ascii"))
    seite[NameObject("/Contents")] = pdf._add_object(stream)
    pdf.write(pfad)


@pytest.mark.parametrize("text,ohne,zusatz,gedreht", [
    (r"4X .82 \261.06", "", "", False), (r"3X .82 \261.02", "", "", True),
    (r"4X .82 \261.06", "oben", "", False), (r"4X .82 \261.06", "unten", "", False),
    (r"4X .82 \261.06", "kreis", "", False), (r"4X .82 \261.06", "pfeil", "", False),
    (r"4X .82 \261.06", "schaft", "", False), (r"4X .82 \261.06", "ende", "", False),
    (r"4X .82 \261.06", "", "-20 12 4 2 re f", False), (r"0X .82 \261.06", "", "", False)])
def test_projektionsachsen_und_vollstaendiger_text(tmp_path,text,ohne,zusatz,gedreht):
    pdf = tmp_path/"Auflagen.pdf"
    _massblatt(pdf, text, ohne, zusatz, gedreht)
    with pdfium.PdfDocument(pdf) as doc:
        blatt = Zeichnungsblatt(doc,0)
        try:
            zeilen = list(projizierte_linearmasse(blatt))
        finally:
            blatt.schliesse()
    if ohne or zusatz or text.startswith("0"):
        assert not zeilen
    else:
        a, = zeilen
        assert a.text == text.replace(" ","").replace(r"\261","±")
        assert len(a.zeilenecken) == 4 and a.modell is None


def test_stueckzahl_und_geometrie_getrennt_vom_masswert():
    e = lade_alles(pfad(QUELLE))
    m = za.Pmi("mass","Size_Thickness",nennwert=20.828,oben=1.524,unten=-1.524,
               flaechen={e.modell.step_zu_flaeche[n] for n in ZIELE})
    index = Verbundindex([m], e.modell)
    a = za.Blattangabe(0,(.1,.1,.2,.2),"4X .82 ±.06",modell=m)
    assert za.befund(a,25.4,verbundindex=index) == "gleich"
    assert za.befund(a,None,verbundindex=index) == za.befund(a,25.4) == "offen"
    for text in ("3× .82 ±.06", "4X .82 ±.02", "4X .83 ±.06"):
        assert za.befund(replace(a,text=text),25.4,verbundindex=index) == "geaendert"
    teilweise = replace(m,flaechen=m.flaechen-{e.modell.step_zu_flaeche[557]})
    assert za.befund(replace(a,modell=teilweise),25.4,verbundindex=index) == "geaendert"
    einzeln = replace(m, flaechen={e.modell.step_zu_flaeche[n] for n in (481,557)})
    assert za.befund(replace(a,modell=einzeln),25.4,verbundindex=index) == "geaendert"
    unbekannt = replace(m,flaechen=set())
    assert za.befund(replace(a,modell=unbekannt),25.4,verbundindex=index) == "offen"
    assert za.lese_angabe("4X .82 ±.06 in",None).grenzen() == pytest.approx(m.grenzen())
    assert za.lese_angabe("0x.82±.06", 25.4) is None
    assert za.lese_angabe("4x2x1",1.) is None


@pytest.mark.parametrize("wort,ohne,zusatz,gedreht,soll", [
    ("(.750)", "", "", False, "(.750)"), ("(.250)", "", "", True, "(.250)"),
    (".750", "", "", False, ".750"), ("0.25", "", "", True, "0.25"),
    ("(66)", "", "", False, ""), ("(.750)", "kreis", "", False, ""),
    ("(.750)", "ende", "", False, ""), ("(.750)", "unten", "", False, ""),
    ("(.750)", "", "-10 12 4 2 re f", False, ""),
    ("(.750)", "", "26 12 4 2 re f", False, ""),
    (r"\(.750", "", "", False, ""), (r".750\)", "", "", True, ""),
])
def test_linearmass_mit_gegenpfeil(tmp_path, wort, ohne, zusatz, gedreht, soll):
    datei = tmp_path/"Gegenpfeile.pdf"
    _massblatt(datei,wort,ohne,zusatz,gedreht,gegenpfeil=True)
    with pdfium.PdfDocument(datei) as doc:
        blatt = Zeichnungsblatt(doc,0)
        try:
            funde = list(projizierte_linearmasse(blatt))
        finally:
            blatt.schliesse()
    assert [a.text for a in funde] == ([soll] if soll else [])
    if soll:
        a, = funde
        assert len(a.hilfslinien) == 2 and len(a.zeilenecken) == 4
        p = za.lese_angabe(a.text,25.4)
        assert ("Hilfsmass" in p.modifikatoren) == soll.startswith("(")
