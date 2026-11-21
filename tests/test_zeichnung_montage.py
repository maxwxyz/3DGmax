"""Getrennte Pruefung von Positionsrahmen und Bohrungsmass im projizierten PDF."""
import csv
import gzip
from dataclasses import replace

import pypdfium2 as pdfium
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from PySide6.QtWidgets import QFileDialog

from programm.kern import zeichnungsabgleich as za
from programm.kern.zeichnungsblatt import Zeichnungsblatt
from tests.test_zeichnung_koplanar import NIST

KOPF = "⌖ | ⌀.05Ⓜ | D | B | C"
HINWEIS = "SWITCH MOUNTING LOCATIONS"
TEXT = KOPF+"\nSWITCH MOUNTING\nLOCATIONS"


def _blatt(ziel, *, menge="4", ring=r"\330", zeilen=("SWITCH MOUNTING", "LOCATIONS"),
           schraeg=True, steghoehe=20, hinweis=True, rahmenwert=".12", massbeginn=1):
    pdf = PdfWriter()
    seite = pdf.add_blank_page(560,320)
    font = DictionaryObject({NameObject(k): NameObject(v) for k,v in [
        ("/Type","/Font"), ("/Subtype","/Type1"), ("/BaseFont","/Helvetica"), ("/Encoding","/WinAnsiEncoding")]})
    seite[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"):pdf._add_object(font)})})
    matrix = ".866 -.5 0 1" if schraeg else "1 0 0 1"
    daten = [f"q {matrix} 125 200 cm .4 w", "0 0 100 20 re S",
             "30 0 m 30 20 l S", "63 0 m 63 20 l S", f"82 0 m 82 {steghoehe} l S",
             "10 10 m 10 12.8 12.2 15 15 15 c 17.8 15 20 12.8 20 10 c "
             "20 7.2 17.8 5 15 5 c 12.2 5 10 7.2 10 10 c h S",
             "7 10 m 23 10 l S 15 2 m 15 18 l S"]
    def text(x,y,wort):
        daten.append(f"BT /F1 13.5 Tf 1 0 0 1 {x} {y} Tm ({wort}) Tj ET")
    text(34,5,rahmenwert)
    text(68,5,"B")
    text(87,5,"C")
    for i,wort in enumerate(zeilen):
        text(1,-18*(i+1),wort)
    mass = (menge+"X " if menge is not None else "")+ring+r".625 \261.005"
    text(massbeginn,24,mass)
    if hinweis == "links":
        daten.append("-3 29 m -15 29 l -30 40 l S")
    elif hinweis:
        x = massbeginn + (99 if menge is not None else 78)
        daten.append(f"{x} 29 m {x+9} 29 l {x+30} 43 l S")
    stream = DecodedStreamObject()
    stream.set_data("\n".join([*daten, "Q"]).encode("ascii"))
    seite[NameObject("/Contents")] = pdf._add_object(stream)
    pdf.write(ziel)


def _funde(pfad):
    with pdfium.PdfDocument(pfad) as doc:
        blatt = Zeichnungsblatt(doc, 0)
        try:
            return blatt.fundstellen()
        finally:
            blatt.schliesse()


@pytest.mark.parametrize("optionen,rahmen,mass", [
    ({}, True, True), ({"menge":"3"}, True, True), ({"hinweis":"links"}, True, True),
    ({"schraeg":False}, True, True), ({"menge":"0"}, True, False),
    ({"ring":"O"}, True, False), ({"ring":"8"}, True, False),
    ({"hinweis":False}, True, False), ({"rahmenwert":"XX"}, False, True),
    ({"zeilen":("SWITCH M0UNTING","LOCATIONS")}, False, True),
    ({"zeilen":("SWITCH MOUNTING","LOCATION")}, False, True),
    ({"zeilen":("SWITCH MOUNTING","LOCATIONS","EXCEPT SLOT")}, False, True),
    ({"steghoehe":13}, False, True),
])
def test_projizierte_masszeile_eigenstaendig(tmp_path, optionen, rahmen, mass):
    pdf = tmp_path/"Rahmen.pdf"
    _blatt(pdf, **optionen)
    funde = _funde(pdf)
    position = [a for a in funde if a.rahmenbox and a.text.startswith("⌖") and za.lese_angabe(a.text,1)]
    masse = [a for a in funde if za.musteranzahl(a.text) and a.hinweisenden]
    assert len(position) == int(rahmen)
    assert len(masse) == int(mass)
    if rahmen:
        p = za.lese_angabe(position[0].text,1)
        assert (p.wert,p.beschreibung,p.bezug_text()) == (.12,HINWEIS,"B|C")
    if mass:
        assert sum(bool(za.musteranzahl(a.text)) for a in funde) == 1
        d, = masse
        assert d.text == optionen.get("menge","4")+"X⌀.625±.005"
        assert d.hinweisenden and len(d.zeilenecken) == 4


@pytest.mark.parametrize("kennung,blatt,wort,einheit,ids", [
    ("ctc_02", 1, "2X⌀52±0.15", 1., {404}),
    ("ftc_09", 1, "2X⌀.234±.008", 25.4, {8504,8539,8595}),
    ("ftc_09", 4, "2X⌀.156±.008", 25.4, {9157,9367,9482}),
    ("ftc_10", 5, "4X⌀7±0.25", 1., {20713}),
])
def test_weitere_muster_mit_hinweisziel(kennung, blatt, wort, einheit, ids):
    from programm.kern.zeichnungsansicht import Blattgeometrie
    from programm.ui.lader import lade_alles
    pdf = next((NIST/"PDF").glob(f"nist_{kennung}_asme1_r*.pdf"), None)
    modell = next(NIST.glob(f"nist_{kennung}_asme1_ap242-e*.stp"), None)
    if pdf is None or modell is None:
        pytest.skip("Lokales NIST-Referenzpaar fehlt")
    with pdfium.PdfDocument(pdf) as doc:
        b = Zeichnungsblatt(doc, blatt-1)
        try:
            a, = [v for v in b.fundstellen() if v.text == wort]
            geo = Blattgeometrie(b, mit_ellipsen=True)
            assert len(geo._starts(a.box, None, True, a.hinweisenden)) == 1
        finally:
            b.schliesse()
    e = lade_alles(str(modell))
    mass = za.lese_angabe(wort,einheit)
    assert {p.step_id for p in e.pmi if p.semantisch and not za.unterschiede(mass,p)} == ids
    assert a.modell is None


def test_einzelmasse_und_muster_am_richtigen_blattort():
    from programm.kern.zeichnungsansicht import Blattgeometrie
    from programm.ui.lader import lade_alles
    pdf = NIST/"PDF/nist_ctc_03_asme1_rc.pdf"
    modell = NIST/"nist_ctc_03_asme1_ap242-e2.stp"
    if not pdf.is_file() or not modell.is_file():
        pytest.skip("Lokales NIST-Referenzpaar fehlt")
    # Die zwei rechts uebereinander liegenden Einzelbohrungen tragen denselben Wert.
    erwartet = [
        ("2X⌀.438±.005",{263,264,266}), ("⌀2.00±.01",{267}),
        ("4X⌀.625±.005",{265}), ("⌀.438±.005",{263,264,266}),
        ("⌀1.065±.003",{271}), ("⌀.438±.005",{263,264,266}), ("⌀1.500±.005",{268})]
    with pdfium.PdfDocument(pdf) as doc:
        b = Zeichnungsblatt(doc,0)
        try:
            zeilen = sorted((a for a in b.fundstellen() if a.hinweisenden),key=lambda a:a.box[1])
            geo = Blattgeometrie(b,mit_ellipsen=True)
            starts = [geo._starts(a.box,None,True,a.hinweisenden) for a in zeilen]
            assert all(len(st) == 1 for st in starts) and len({st[0] for st in starts}) == len(erwartet)
        finally:
            b.schliesse()
    e = lade_alles(str(modell))
    for a,(text,ids) in zip(zeilen,erwartet,strict=True):
        assert a.text == text and a.modell is None and a.blattziel is None
        p = za.lese_angabe(a.text,25.4)
        assert {q.step_id for q in e.pmi if q.semantisch and not za.unterschiede(p,q)} == ids


def test_gedruckter_wert_hat_weniger_dezimalstellen_als_step():
    from programm.ui.lader import lade_alles
    pdf = NIST/"PDF/nist_ftc_06_asme1_rd.pdf"
    modell = NIST/"nist_ftc_06_asme1_ap242-e2.stp"
    if not pdf.is_file() or not modell.is_file():
        pytest.skip("Lokales NIST-Referenzpaar fehlt")
    a, = [a for a in _funde(pdf) if a.text == "2X⌀.562±.008"]
    p = za.lese_angabe(a.text,25.4)
    ref = next(p for p in lade_alles(str(modell)).pmi if p.step_id == 271)
    assert len(a.hinweisenden) == 1 and p.oben == pytest.approx(ref.oben)
    assert ref.nennwert-p.nennwert == pytest.approx(.0005*25.4)
    assert za.wertunterschiede(p, ref) == ["nennwert", "maximum", "minimum"]


@pytest.mark.parametrize("optionen,erkannt", [
    ({}, True), ({"schraeg":False}, True), ({"massbeginn":26}, True),
    ({"massbeginn":65}, False), ({"ring":"8"}, False), ({"ring":"O"}, False),
    ({"hinweis":False}, False), ({"rahmenwert":"XX"}, True),
])
def test_einzelmass_ohne_stueckzahl(tmp_path, optionen, erkannt):
    pdf = tmp_path/"Einzelmass.pdf"
    _blatt(pdf, menge=None, **optionen)
    funde = _funde(pdf)
    zeilen = [a for a in funde if a.hinweisenden and a.text.startswith("⌀")]
    assert len(zeilen) == int(erkannt)
    if erkannt:
        assert zeilen[0].text == "⌀.625±.005"
        assert sum(za.lese_angabe(a.text,1).typ == "Size_Diameter"
                   for a in funde if za.lese_angabe(a.text,1)) == 1


def test_abweichender_pdf_text_am_selben_ort():
    from programm.kern.zeichnungsblatt import _mass_eintragen
    grafik = za.Blattangabe(0,(.30,.10,.40,.14),"⌀2.00±.01",hinweisenden=((.42,.12),))
    for text in ("Ø2.00±.01", "Ø2.00±.02", "2XØ2.00±.01"):
        pdf = replace(grafik, box=(.301,.101,.401,.141),text=text,hinweisenden=())
        andere = replace(pdf, box=(.45,.10,.55,.14))
        funde = {a.box:a for a in (pdf,andere)}
        _mass_eintragen(funde,grafik,1000,1000)
        assert len(funde) == 2 and funde[andere.box].text == text
        if text == "Ø2.00±.01":
            assert funde[grafik.box] is grafik
        else:
            assert funde[pdf.box].text == "?"


def test_felder_einzeln_und_ohne_zeichnungseinheit():
    angabe = za.Blattangabe(0,(0,0,1,1),TEXT)
    p = za.lese_angabe(TEXT,25.4)
    assert p.typ == "Position" and p.wert == pytest.approx(1.27)
    assert "Diameter" in p.modifikatoren and p.material == "M" and p.bezug_text() == "D|B|C"
    assert za.befund(replace(angabe,modell=p),None) == "offen"
    for anders, feld in ((replace(p,beschreibung=""),"beschreibung"), (replace(p,wert=.05),"wert"),
                         (replace(p,material=""),"material"), (replace(p,modifikatoren=[]),"modifikatoren"),
                         (replace(p,bezuege=[replace(b,stelle=i) for i,b in enumerate(reversed(p.bezuege),1)]),"bezuege")):
        assert za.wertunterschiede(p,anders) == [feld]
        assert za.befund(replace(angabe,modell=anders),25.4) == "geaendert"
    assert za.befund(replace(angabe,modell=p),25.4) == "gleich"
    assert za.lese_angabe(TEXT.replace("⌖","⌓"),25.4) is None


@pytest.mark.parametrize("reparieren", [False, True], ids=["referenz", "grafischer_export"])
def test_zeichnungsbefund_bis_csv(fenster, tmp_path, monkeypatch, reparieren):
    pdf = NIST/"PDF/nist_ctc_03_asme1_rc.pdf"
    modell = NIST/"nist_ctc_03_asme1_ap242-e2.stp"
    if not pdf.is_file() or not reparieren and not modell.is_file():
        pytest.skip("Lokales NIST-Referenzpaar fehlt")
    if reparieren:
        from tests.conftest import pfad
        quelle = tmp_path/"Grafik.step"
        with gzip.open(pfad("nist_ctc_03_asme1_ap203.stp.gz"), "rb") as f:
            quelle.write_bytes(f.read())
        fenster.lade(str(quelle), warten=True)
        for nr in (3643, 3632, 3624, 3627, 3638, 3629, 3634):
            p = next(p for p in fenster.erg.pmi if p.step_id == nr)
            fenster._pmi_befehl("semantisch", p)
            dialog = fenster._semantik_dialog
            assert not dialog.fehler()
            dialog._pruefen()
        modell = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.step"), melden=False)
        assert modell and not fenster._step_bericht.uebersprungen
    ziel = tmp_path/"Montage.csv"
    monkeypatch.setattr(QFileDialog,"getOpenFileName",lambda *a:(str(pdf),"PDF"))
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *a:(str(ziel),"CSV"))
    fenster.lade(str(modell),warten=True)
    fenster.aktionen["zeichnungsabgleich"].trigger()
    d = fenster.zeichnungsabgleich
    try:
        d.einheit.setCurrentIndex(d.einheit.findData(25.4))
        position, = [a for a in d.seiten[0] if a.text == TEXT]
        mass, = [a for a in d.seiten[0] if za.musteranzahl(a.text) == 4]
        groesse = za.lese_angabe(mass.text,25.4)
        def ziel_pmi(kennung, callout):
            ids = fenster.erg.grafik[callout].pmi_ids if reparieren else {kennung}
            return next(m for m in d.modell if m.semantisch and m.step_id in ids)
        assert not za.unterschiede(groesse,ziel_pmi(265,3638))
        assert len(position.zeilenecken) == len(mass.zeilenecken) == 4 and len(mass.hinweisenden) == 1
        d.waehle(position)
        m = ziel_pmi(41,3627)
        d.zuordnung.setCurrentIndex(d.zuordnung.findData(d.modellindex[id(m)]))
        d.bestaetigen.click()
        assert d._befund(position) == ("gleich" if reparieren else "geaendert")
        if not reparieren:
            assert HINWEIS in d.detail.text()
        doppelt = [a for a in d.seiten[0] if a.text == "⌀.438±.005"]
        assert len(doppelt) == 2 and doppelt[0].hinweisenden != doppelt[1].hinweisenden
        for a in doppelt:
            d.waehle(a)
            assert d.zuordnung.currentData() is None and a.modell is None
        bohrung, = [a for a in d.seiten[0] if a.text == "⌀2.00±.01"]
        d.waehle(bohrung)
        durchmesser = ziel_pmi(267,3629)
        assert d.zuordnung.currentData() == d.modellindex[id(durchmesser)]
        assert bohrung.modell is None
        d.bestaetigen.click()
        assert bohrung.modell is durchmesser and d._befund(bohrung) == "gleich"
        dicke, = [a for a in d.seiten[0] if a.text == "4X.82±.06"]
        d.waehle(dicke)
        auflagen = ziel_pmi(270,3634)
        assert len(dicke.zeilenecken) == 4 and dicke.modell is None
        assert d.zuordnung.currentData() == d.modellindex[id(auflagen)]
        assert "Auflagen im Modell 4" in d.detail.text()
        d.bestaetigen.click()
        assert d._befund(dicke) == "gleich"
        d._export()
        with ziel.open(encoding="utf-8-sig") as f:
            daten = list(csv.DictReader(f,delimiter=";"))
        assert all(None not in z and None not in z.values() for z in daten)
        dick, = [z for z in daten if z["Angabe"] == dicke.text]
        assert dick["Quell-ID der Modell-PMI"] == str(auflagen.step_id)
        assert dick["Befund"] == "Werte gleich" and "Auflagen im Modell 4" in dick["Prüfung der koplanaren Flächen"]
        z, = [z for z in daten if z["Angabe"] == TEXT]
        assert z["Quell-ID der Modell-PMI"] == str(m.step_id)
        assert z["Befund"] == ("Werte gleich" if reparieren else "Abweichend")
        if reparieren:
            assert HINWEIS in z["Modellwert"] and "überein" in z["Vergleich der angegebenen Werte"]
        else:
            assert HINWEIS in z["Vergleich der angegebenen Werte"] and "Im Modell: –" in z["Vergleich der angegebenen Werte"]
        assert any(z["Angabe"] == mass.text and z["Befund"] == "Zu prüfen" for z in daten)
        bore, = [z for z in daten if z["Angabe"] == bohrung.text]
        assert bore["Befund"] == "Werte gleich" and bore["Quell-ID der Modell-PMI"] == str(durchmesser.step_id)
        assert sum(z["Angabe"] == doppelt[0].text and z["Befund"] == "Zu prüfen" for z in daten) == 2
    finally:
        d.close()
