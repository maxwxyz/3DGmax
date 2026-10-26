"""Oberflaeche ohne Bildschirm (offscreen): Laden, Auswahl, Filter, Ansichten, Hilfe, Uebersetzung."""

import os
import sys

from programm.ui import ansicht3d
from programm.ui.hilfe import MARKE, anleitung_html, menue_befehle
from tests.conftest import WURZEL


def test_platzhalter_ohne_grafik(fenster):
    assert isinstance(fenster.ansicht, ansicht3d.PlatzhalterAnsicht)


def test_ohne_modell_keine_toten_knoepfe(fenster):
    for name, a in fenster.aktionen.items():
        if a.property("braucht_modell"):
            assert not a.isEnabled(), name
    assert fenster.aktionen["oeffnen"].isEnabled()
    assert not fenster.schnitt_regler.isEnabled()


def test_laden_fuellt_alles(fenster_ctc01):
    f = fenster_ctc01
    assert f.erg is not None
    assert f.pmi.tabelle.rowCount() == 23  # 21 PMI + 2 Hinweise (Text.1, Text.2)
    assert f.ansichten.liste.count() == 2  # "keine Ansicht" + MBD_0
    assert f.baum.baum.topLevelItemCount() == 1
    # "Schnittseite umkehren" ist ohne aktiven Schnitt bewusst ausgegraut
    assert all(a.isEnabled() for n, a in f.aktionen.items() if n not in ("schnitt_umkehren", "vergleich_beenden"))
    assert not f.aktionen["schnitt_umkehren"].isEnabled()
    assert os.path.basename(f.zuletzt()[0]) == "nist_ctc_01_asme1_ap242-e1.stp"


def test_pmi_hebt_flaechen_hervor(fenster_ctc01):
    f = fenster_ctc01
    n = f.pmi.waehle(lambda p: p.nummer == 13)  # Position 0.75 | A | B | C
    assert n == 1
    p = f.erg.pmi[12]
    assert f.ansicht.hervor == p.flaechen and p.flaechen
    assert p.step_id in f.ansicht.pmi_ids_hervor


def test_flaeche_waehlt_pmi(fenster_ctc01):
    f = fenster_ctc01
    bezug_b = next(p for p in f.erg.pmi if p.art == "bezug" and p.name == "B")
    idx = next(iter(bezug_b.flaechen))
    f._flaeche_gewaehlt(idx)
    gewaehlt = {f.pmi.pmi[i.row()].nummer for i in f.pmi.tabelle.selectedIndexes()}
    assert bezug_b.nummer in gewaehlt


def test_filter_und_suche(fenster_ctc01):
    f = fenster_ctc01
    f.pmi.art.setCurrentIndex(2)  # Toleranzen
    assert len(f.pmi.sichtbare()) == 6
    f.pmi.art.setCurrentIndex(0)
    f.pmi.suche.setText("0.75")
    assert {p.typ for p in f.pmi.sichtbare()} == {"Position"}
    f.pmi.suche.setText("")
    assert len(f.pmi.sichtbare()) == 23


def test_gespeicherte_ansicht_filtert(app, tmp_path, monkeypatch):
    monkeypatch.setenv("DG_EINSTELLUNGEN", str(tmp_path / "e.ini"))
    from programm.ui.hauptfenster import Hauptfenster
    from tests.conftest import pfad
    f = Hauptfenster()
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    zeile = next(i for i, a in enumerate(f.erg.ansichten, 1) if a.name == "MBD_B")
    f.ansichten.liste.setCurrentRow(zeile)
    a = f.erg.ansichten[zeile - 1]
    assert len(f.pmi.sichtbare()) == len(a.pmi_nummern) > 0
    assert f.ansicht.pmi_ids_sichtbar == a.pmi_ids
    assert f.ansicht.letzte_ansicht == "MBD_B"
    f.ansichten.liste.setCurrentRow(0)
    assert f.ansicht.pmi_ids_sichtbar is None
    f.close()


def test_struktur_ein_ausblenden(fenster_ctc01):
    f = fenster_ctc01
    wurzel = f.baum.baum.topLevelItem(0)
    from PySide6.QtCore import Qt
    wurzel.setCheckState(0, Qt.CheckState.Unchecked)
    assert f.ansicht.versteckt
    f.baum.alle_zeigen()
    assert not f.ansicht.versteckt


def test_schnitt_und_darstellung(fenster_ctc01):
    f = fenster_ctc01
    f.aktionen["schnitt_z"].trigger()
    assert f.ansicht.schnitt_zustand[0] == "z" and f.schnitt_regler.isEnabled()
    f.aktionen["schnitt_aus"].trigger()
    assert f.ansicht.schnitt_zustand is None and not f.schnitt_regler.isEnabled()
    f.aktionen["darstellung_draht"].trigger()
    assert f.ansicht.modus == "draht"


def test_anleitung_enthaelt_alle_menuebefehle(fenster):
    for name in ("Anleitung.html", "Manual.html"):
        with open(os.path.join(WURZEL, "programm", name), encoding="utf-8") as d:
            assert MARKE in d.read(), name
    text = anleitung_html(fenster)
    befehle = menue_befehle(fenster)
    assert len(befehle) > 30
    for _pfad, befehl, _k, _t in befehle:
        assert befehl in text


def test_uebersetzung_vollstaendig():
    sys.path.insert(0, os.path.join(WURZEL, "werkzeuge"))
    import tr_texte
    assert tr_texte.fehlende() == []


def test_selbsttest():
    from programm.app import selbsttest
    assert selbsttest() == 0


def test_einstellungen_standard_catia_und_umschalten(fenster):
    from programm.ui.einstellungen import EinstellungenDialog
    assert fenster.ansicht.navigation == "catia"
    d = EinstellungenDialog(fenster.ein, fenster)
    assert d.werte()["navigation"] == "catia"
    w = d.werte()
    w["navigation"] = "klassisch"
    fenster.wende_einstellungen_an(w)
    assert fenster.ansicht.navigation == "klassisch"
    assert fenster.ein.value("navigation") == "klassisch"


def test_version_im_titel_und_autor(fenster_ctc01):
    from programm.ui.hilfe import ueber_html
    from programm.version import VERSION
    assert VERSION in fenster_ctc01.windowTitle()
    assert "nist_ctc_01" in fenster_ctc01.windowTitle()
    assert "Max Wilfinger" in ueber_html()


def test_pmi_farbe_kontrast_oder_datei(fenster_ctc01):
    f = fenster_ctc01
    g = next(iter(f.erg.grafik.values()))
    assert g.farbe is not None  # Farbe aus der Datei gelesen
    assert f.ansicht.pmi_kontrast  # Standard: an das Schema angepasst
    assert f.ansicht.pmi_farbe(g) == f.thema["pmi"]
    f.wende_einstellungen_an({"navigation": "catia", "thema": f.ein.value("thema", "auto"),
                              "sprache": f.ein.value("sprache", "auto"), "pmi_kontrast": False})
    assert f.ansicht.pmi_farbe(g) == g.farbe
    assert f.ein.value("pmi_kontrast", type=bool) is False


def test_pmi_liste_name_ansichten_bezuege(app, tmp_path, monkeypatch):
    monkeypatch.setenv("DG_EINSTELLUNGEN", str(tmp_path / "e.ini"))
    from programm.ui.hauptfenster import Hauptfenster
    from tests.conftest import pfad
    f = Hauptfenster()
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    p = f.pmi
    assert p.SPALTEN.index("Name") == 4 and p.SPALTEN.index("Ansichten") == 5
    p.suche.setText("MBD_E")  # Suche nach Ansicht
    assert 0 < len(p.sichtbare()) <= 3
    p.suche.setText("")
    # Toleranz D | E-F-G -> Bezuege D, E, F, G waehlen
    tol = next(q for q in p.pmi if q.bezug_text() == "D|E-F-G")
    assert p.waehle_bezuege([tol]) == 4
    a = next(q for q in p.pmi if q.art == "bezug" and q.name == "A")
    assert p.waehle_mit_bezug([a]) > 10
    # Ansichten durchklicken
    f.ansichten.gehe(+1)
    assert f.ansichten.liste.currentRow() == 1
    f.ansichten.gehe(-1)
    assert f.ansichten.liste.currentRow() == len(f.erg.ansichten) or f.ansichten.liste.currentRow() >= 1
    f.close()


def test_3d_auswahl_zoom_normal_und_schnitt(fenster_ctc01):
    f = fenster_ctc01
    fl = f.erg.modell.flaechen
    f.ansicht.setze_auswahl([fl[3], fl[7]])
    f.aktionen["zoom_auswahl"].trigger()
    assert f.ansicht.letzter_zoom[0] == {3, 7}
    f.aktionen["normal_auswahl"].trigger()
    assert f.ansicht.letzte_ausrichtung[0] == {3, 7}
    assert not f.schnitt_regler_aktion.isVisible()
    f.aktionen["schnitt_z"].trigger()
    assert f.schnitt_regler_aktion.isVisible()
    f.aktionen["schnitt_aus"].trigger()
    assert not f.schnitt_regler_aktion.isVisible()
    f.ansicht.setze_auswahl([])
    f.aktionen["schnitt_auswahl"].trigger()  # ohne Auswahl: Hinweis, kein Schnitt
    assert f.ansicht.schnitt_zustand is None


def test_eigene_farben(fenster_ctc01):
    f = fenster_ctc01
    g = next(iter(f.erg.grafik.values()))
    f.wende_einstellungen_an({"navigation": "catia", "thema": f.ein.value("thema", "auto"),
                              "sprache": f.ein.value("sprache", "auto"), "pmi_kontrast": True,
                              "pmi_eigen": True, "pmi_eigene_farbe": "#ff0000",
                              "hg_eigen": True, "hg_oben": "#000000", "hg_unten": "#ffffff"})
    assert f.ansicht.pmi_farbe(g) == (1.0, 0.0, 0.0)
    assert f.ansicht.hintergrund == ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    from programm.ui.einstellungen import EinstellungenDialog
    d = EinstellungenDialog(f.ein, f)
    assert d.werte()["pmi_eigen"] and d.werte()["hg_eigen"]


def test_pmi_export_und_pruefung(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    ziel = tmp_path / "pmi.csv"
    assert f.exportiere_pmi(str(ziel))
    text = ziel.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].startswith("Nr;Art;Typ;Name;Wert") and "MBD_0" in text and "#" in text
    assert len(text.splitlines()) == 1 + len(f.erg.pmi)
    fenster = f.pruefe_pmi()
    assert fenster.tabelle.rowCount() > 0
    fenster.tabelle.cellDoubleClicked.emit(0, 0)
    assert f.pmi.gewaehlte()
    fenster.close()


def test_pmi_pruefung_regeln():
    from programm.kern.pmi import BEZUG, TOLERANZ, BezugsRef, Pmi
    from programm.kern.pmi_bericht import pruefe
    pmi = [Pmi(BEZUG, typ="Datum", name="A", flaechen={1}, nummer=1),
           Pmi(BEZUG, typ="Datum", name="B", flaechen={2}, nummer=2),
           Pmi(TOLERANZ, typ="Perpendicularity", wert=0.1, flaechen={3}, nummer=3),
           Pmi(TOLERANZ, typ="Flatness", wert=0.1, flaechen={4}, nummer=4, bezuege=[BezugsRef("A")]),
           Pmi(TOLERANZ, typ="Position", wert=0.2, flaechen={5}, nummer=5, bezuege=[BezugsRef("C")])]
    texte = {b.text for b in pruefe(pmi)}
    assert "Bezug B wird von keiner Toleranz verwendet" in texte
    assert any("nicht definierte Bezüge: C" in t for t in texte)
    assert any("Richtungs-/Lauftoleranz ohne Bezug" in t for t in texte)
    assert any("Formtoleranz mit Bezug" in t for t in texte)
