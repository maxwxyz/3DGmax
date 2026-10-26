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
    assert f.pmi.tabelle.rowCount() == 21
    assert f.ansichten.liste.count() == 2  # "keine Ansicht" + MBD_0
    assert f.baum.baum.topLevelItemCount() == 1
    # "Schnittseite umkehren" ist ohne aktiven Schnitt bewusst ausgegraut
    assert all(a.isEnabled() for n, a in f.aktionen.items() if n != "schnitt_umkehren")
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
    assert len(f.pmi.sichtbare()) == 21


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
