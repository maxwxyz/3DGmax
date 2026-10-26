"""Vergleich: Ausrichten, Geometrie, PMI, Aenderungsliste, Pruefprotokoll (Varianten von NIST CTC-01)."""

import numpy as np
import pytest

from tests.conftest import pfad


@pytest.fixture(scope="module")
def alt():
    from programm.ui.lader import lade_alles
    return lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))


def _variante(name):
    from programm.ui.lader import lade_alles
    return lade_alles(pfad(f"varianten/{name}.stp"))


def test_selbstvergleich_ohne_aenderung(alt):
    from programm.kern import vergleich
    v = vergleich.vergleiche(alt, alt)
    assert v.ausrichtung.methode == "gleich"
    assert vergleich.ist_gleich(v)
    assert float(v.geo.abw_b.max()) < v.toleranz  # Netzwerte klar unter der Toleranz werden nicht nachgerechnet


def test_nur_pmi_geaendert(alt):
    from programm.kern import vergleich
    v = vergleich.vergleiche(alt, _variante("ctc01_pmi"))
    texte = sorted(a.beschreibung for a in v.aenderungen)
    assert all(a.kategorie == "pmi" and a.status == "geaendert" for a in v.aenderungen)
    assert texte == ["Toleranzwert: 0.2 → 0.1", "Toleranzwert: 0.75 → 0.5", "unteres Abmaß/Mindestmaß: -0.2 → -0.3"]


def test_nur_geometrie_geaendert(alt):
    from programm.kern import vergleich
    v = vergleich.vergleiche(alt, _variante("ctc01_geo"))
    arten = sorted((a.kategorie, a.status) for a in v.aenderungen)
    assert arten == [("geometrie", "geaendert"), ("pmi", "geometrie")]
    geo = next(a for a in v.aenderungen if a.kategorie == "geometrie")
    assert len(geo.flaechen_neu) == 2 and "0.500" in geo.beschreibung


def test_geometrie_und_pmi_geaendert(alt):
    from programm.kern import vergleich
    v = vergleich.vergleiche(alt, _variante("ctc01_geo_pmi"))
    pmi = [a for a in v.aenderungen if a.kategorie == "pmi"]
    assert len(pmi) == 2 and all("Nennwert: 20 → 21" in a.beschreibung for a in pmi)


def test_bestpassung_findet_drehung(alt):
    """Neuer Stand gedreht und verschoben: Bestpassung findet die Lage wieder."""
    from programm.kern import ausrichten
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCC.Core.TopoDS import topods
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 1.1)
    t2 = gp_Trsf()
    t2.SetTranslation(gp_Vec(40, -15, 7))
    t2.Multiply(t)
    gedreht = [topods.Face(BRepBuilderAPI_Transform(f, t2, True).Shape()) for f in alt.modell.flaechen]
    a = ausrichten.richte_aus(alt.modell.flaechen, gedreht)
    assert a.methode == "bestpassung" and a.anteil > 0.95
    p = np.array([[10.0, 20.0, 30.0]])
    zurueck = a.wende_an(np.array([[gp_Pnt(10, 20, 30).Transformed(t2).Coord(i) for i in (1, 2, 3)]]))
    assert np.allclose(zurueck, p, atol=0.01)


def test_drei_punkte():
    from programm.kern import ausrichten
    a = [[0, 0, 0], [10, 0, 0], [0, 5, 0]]
    b = [[1, 2, 3], [1, 12, 3], [-4, 2, 3]]  # um 90° gedreht und verschoben
    r = ausrichten.richte_nach_punkten(b, a)
    assert r.mittel < 1e-9
    with pytest.raises(ValueError):
        ausrichten.richte_nach_punkten(b[:2], a[:2])


def test_pruefprotokoll(alt, tmp_path):
    from programm.kern import pruefung, vergleich
    v = vergleich.vergleiche(alt, _variante("ctc01_pmi"))
    v.aenderungen[0].pruefstatus = "geprueft"
    v.aenderungen[1].kommentar = "mit Lieferant abgestimmt"
    d = pruefung.protokoll(v, "M. Muster", "mit Auflagen", "Test", "0.1")
    assert pruefung.ist_unveraendert(d)
    j, t = pruefung.speichere(d, str(tmp_path / "protokoll"))
    assert "Prüfsumme" in open(t, encoding="utf-8").read()
    d["ergebnis"] = "freigegeben"
    assert not pruefung.ist_unveraendert(d)


def test_vergleich_in_oberflaeche(fenster, tmp_path):
    f = fenster
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_geo_pmi.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    assert f.vergleich is not None and f.dock_aenderungen.isVisibleTo(f)
    assert f.aenderungen.tabelle.rowCount() == 3
    assert f.ansicht.vergleich_status is not None
    assert "→" in f.windowTitle()
    # Pruefrundgang: starten, Status setzen springt zur naechsten offenen Aenderung
    f.aenderungen.pruefen_starten()
    erste = f.aenderungen.gewaehlte()
    assert erste.nummer == 1 and f.ansicht.letzter_zoom is not None
    f.aenderungen.kommentar.setText("passt")
    f.aenderungen.setze_status("geprueft")
    assert erste.pruefstatus == "geprueft" and erste.kommentar == "passt"
    assert f.aenderungen.gewaehlte().nummer == 2
    f.aenderungen.setze_status("abgelehnt")
    j, t = f.schliesse_pruefung_ab(str(tmp_path / "p.json"),
                                   {"pruefer": "Test", "ergebnis": "mit Auflagen", "bemerkung": ""})
    import json
    from programm.kern import pruefung
    daten = json.load(open(j, encoding="utf-8"))
    assert pruefung.ist_unveraendert(daten) and daten["aenderungen"][0]["kommentar"] == "passt"
    # Auf Auswahl zoomen mit gewaehlter PMI
    f.dock_aenderungen.hide()
    f.pmi.waehle(lambda p: p.nummer == 1)
    f._zoome_auswahl()
    f.beende_vergleich()
    assert f.vergleich is None and f.ansicht.vergleich_status is None


def test_pdf_berichte(fenster, tmp_path):
    f = fenster
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    p = f.exportiere_pdf("ansichten", str(tmp_path / "ansichten.pdf"))
    import pypdf
    seiten = len(pypdf.PdfReader(p).pages)
    assert seiten >= sum(1 for a in f.erg.ansichten if a.pmi_nummern)
    assert "MBD_A" in pypdf.PdfReader(p).pages[0].extract_text()
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_geo_pmi.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    v = f.exportiere_pdf("vergleich", str(tmp_path / "vergleich.pdf"))
    text = "".join(s.extract_text() for s in pypdf.PdfReader(v).pages)
    assert "ctc01_geo_pmi.stp" in text and len(pypdf.PdfReader(v).pages) >= 1 + len(f.vergleich.aenderungen)
    t = f.exportiere_pdf("pmi_aenderungen", str(tmp_path / "pmi.pdf"))
    assert "21" in pypdf.PdfReader(t).pages[0].extract_text()


def test_exporte_englisch(alt, monkeypatch):
    """Mit englischer Oberflaeche sind Aenderungstexte und CSV-Spalten englisch."""
    from programm import i18n
    monkeypatch.setattr(i18n, "SPRACHE", "en")
    from programm.kern import pmi_bericht, vergleich
    v = vergleich.vergleiche(alt, _variante("ctc01_geo_pmi"))
    text = pmi_bericht.vergleich_csv(v)
    kopf = text.splitlines()[0]
    assert kopf.startswith("No;Category;Status;Title;Description;Old;New")
    assert "nominal: 20 → 21" in text and "PMI changed: Dimension" in text
    assert "face(s), largest deviation" in text
    assert pmi_bericht.als_csv(pmi_bericht.tabelle(alt.pmi, alt.ansichten)).startswith("No;Kind;Type;Name;Value")
