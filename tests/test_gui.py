"""Oberflaeche ohne Bildschirm (offscreen): Laden, Auswahl, Filter, Ansichten, Hilfe, Uebersetzung."""

import os
import tempfile
import sys

import pytest
from PySide6 import QtCore, QtWidgets

from programm.ui import ansicht3d
from programm.ui.hilfe import MARKE, anleitung_html, menue_befehle
from tests.conftest import WURZEL, pfad


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
    # ohne aktiven Schnitt bzw. Vergleich bewusst ausgegraut
    schnitt = {"schnitt_umkehren", "schnitt_merken", "schnitt_kette", "schnitt_loeschen", "schnitt_kontur"}
    aus = schnitt | set(f.VERGLEICH_AKTIONEN)
    assert all(a.isEnabled() for n, a in f.aktionen.items() if n not in aus)
    assert not any(f.aktionen[n].isEnabled() for n in schnitt)
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
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[idx]])
    f._flaeche_gewaehlt(idx)
    gewaehlt = {f.pmi.pmi[i.row()].nummer for i in f.pmi.tabelle.selectedIndexes()}
    assert bezug_b.nummer in gewaehlt


def test_mehrfachauswahl_bleibt_hervorgehoben(fenster_ctc01):
    """Strg/⌘-Klick auf eine zweite Flaeche: beide bleiben hervorgehoben, PMI beider Flaechen gewaehlt."""
    f = fenster_ctc01
    bezug_a = next(p for p in f.erg.pmi if p.art == "bezug" and p.name == "A")
    bezug_b = next(p for p in f.erg.pmi if p.art == "bezug" and p.name == "B")
    ia, ib = next(iter(bezug_a.flaechen)), next(iter(bezug_b.flaechen))
    fa, fb = f.erg.modell.flaechen[ia], f.erg.modell.flaechen[ib]
    f.ansicht.setze_auswahl([fa])  # wie Klick auf A
    f._flaeche_gewaehlt(ia)
    f.ansicht.setze_auswahl([fa, fb])  # wie Strg/⌘-Klick auf B
    f._flaeche_gewaehlt(ib)
    assert {ia, ib} <= f.ansicht.hervor
    gewaehlt = [f.pmi.pmi[i.row()] for i in f.pmi.tabelle.selectedIndexes()]
    assert {bezug_a.nummer, bezug_b.nummer} <= {p.nummer for p in gewaehlt}
    f.ansicht.setze_auswahl([fb])  # nochmal Strg/⌘-Klick auf A: abgewaehlt
    f._flaeche_gewaehlt(ia)
    gewaehlt = [f.pmi.pmi[i.row()] for i in f.pmi.tabelle.selectedIndexes()]
    assert ib in f.ansicht.hervor and gewaehlt and all(ib in p.flaechen for p in gewaehlt)


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
    # Bilder der Anleitungen liegen vor (packaging/doc_screenshots.py erzeugt sie)
    import re
    for name in ("Anleitung.html", "Manual.html"):
        with open(os.path.join(WURZEL, "programm", name), encoding="utf-8") as d:
            bilder = re.findall(r'<img src="([^"]+)"', d.read())
        assert len(bilder) >= 12, name
        for b in bilder:
            assert os.path.isfile(os.path.join(WURZEL, "programm", b)), b
    from programm.ui.hilfe import anleitung_datei
    with open(anleitung_datei(fenster), encoding="utf-8") as d:
        datei = d.read()
    assert "<base href=" in datei and MARKE not in datei


def test_uebersetzung_vollstaendig():
    sys.path.insert(0, os.path.join(WURZEL, "werkzeuge"))
    import tr_texte
    assert tr_texte.fehlende() == []


def test_selbsttest():
    from programm.app import selbsttest
    assert selbsttest() == 0


def test_datei_aus_dem_finder(app):
    """macOS-Doppelklick: QFileOpenEvent vor dem Fenster wird gemerkt, danach direkt geladen."""
    from PySide6 import QtGui
    from programm.app import datei_oeffner
    o = datei_oeffner(app)
    try:
        app.sendEvent(app, QtGui.QFileOpenEvent("a.stp"))
        geladen = []
        fenster = type("F", (), {"lade": lambda self, p: geladen.append(p)})()
        assert [os.path.basename(p) for p in o.bereit(fenster)] == ["a.stp"]
        app.sendEvent(app, QtGui.QFileOpenEvent("b.stp"))
        assert [os.path.basename(p) for p in geladen] == ["b.stp"]
    finally:
        app.removeEventFilter(o)


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
    sp = p.SPALTEN
    assert sp.index("Art") < sp.index("Merkmal") < sp.index("Name") < sp.index("Wert") < sp.index("Ansichten")
    p.suche.setText("MBD_E")  # Suche nach Ansicht
    assert 0 < len(p.sichtbare()) <= 3
    p.suche.setText("")
    # Toleranz D | E-F-G -> Bezuege D, E, F, G waehlen
    tol = next(q for q in p.pmi if q.bezug_text() == "D|E-F-G")
    assert p.waehle_bezuege([tol]) == 4
    a = next(q for q in p.pmi if q.art == "bezug" and q.name == "A")
    assert p.waehle_mit_bezug([a]) > 10
    # Ansichten der Reihe nach durchklicken (auch ohne PMI), am Ende wieder vorn
    n = len(f.erg.ansichten)
    for erwartet in list(range(1, n + 1)) + [1]:
        f.ansichten.gehe(+1)
        assert f.ansichten.liste.currentRow() == erwartet
    f.ansichten.gehe(-1)
    assert f.ansichten.liste.currentRow() == n
    # Pfeiltaste rechts in der Liste = naechste Ansicht
    from PySide6 import QtCore, QtGui
    ev = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Right, QtCore.Qt.KeyboardModifier.NoModifier)
    app.sendEvent(f.ansichten.liste, ev)
    assert f.ansichten.liste.currentRow() == 1
    # erneuter Klick auf dieselbe Ansicht meldet sie wieder (Kamera zuruecksetzen)
    gemeldet = []
    f.ansichten.gewaehlt.connect(gemeldet.append)
    f.ansichten.liste.itemClicked.emit(f.ansichten.liste.item(1))
    assert gemeldet and gemeldet[0] is f.erg.ansichten[0]
    f.close()


def test_pmi_iso_gps_spalten_und_ausblenden(fenster_ctc01):
    from programm.kern.pmi import MASS, Pmi
    from programm.ui.panels import spalten_menue  # noqa: F401
    f = fenster_ctc01
    p, t = f.pmi, f.pmi.tabelle
    kopf = t.horizontalHeader()
    sp = p.SPALTEN
    assert not kopf.isSectionHidden(sp.index("Merkmal")) and kopf.isSectionHidden(sp.index("Höchstmaß"))
    # Merkmal fuer Toleranzen (z. B. Flaechenform/Position) und Masse (Durchmesser)
    merkmale = {t.item(z, sp.index("Merkmal")).text() for z in range(t.rowCount())}
    assert {"Position", "Durchmesser"} <= merkmale
    # Grenzmasse aus Abmassen
    m = Pmi(MASS, "Size_Diameter", nennwert=10.0, oben=0.1, unten=-0.05)
    assert m.grenzen() == (10.1, 9.95) and abs(m.masstoleranz() - 0.15) < 1e-12
    g = Pmi(MASS, "Size_Diameter", nennwert=10.0, oben=10.2, unten=9.9, grenzmass=True)
    o, u = g.abmasse()
    assert abs(o - 0.2) < 1e-12 and abs(u + 0.1) < 1e-12 and g.grenzen() == (10.2, 9.9)
    werte = p._werte(m, [])
    assert werte["Höchstmaß"] == "10.1" and werte["Oberes Abmaß"] == "+0.1" and werte["Unteres Abmaß"] == "-0.05"
    # gemerkt: ausgeblendete Spalte bleibt ausgeblendet
    kopf.setSectionHidden(sp.index("Ansichten"), True)
    kopf.sectionMoved.emit(0, 0, 0)  # Zustand speichern wie nach Aenderung
    from programm.ui.hauptfenster import Hauptfenster
    h = Hauptfenster()
    assert h.pmi.tabelle.horizontalHeader().isSectionHidden(sp.index("Ansichten"))
    h.close()


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
    assert text.splitlines()[0].startswith("Nr;Art;Merkmal;Typ;Name;Wert") and "MBD_0" in text and "#" in text
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


def test_spalten_verschiebbar_und_gemerkt(app, tmp_path, monkeypatch):
    monkeypatch.setenv("DG_EINSTELLUNGEN", str(tmp_path / "e.ini"))
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    kopf = f.pmi.tabelle.horizontalHeader()
    assert kopf.sectionsMovable()
    kopf.moveSection(kopf.visualIndex(3), 0)  # "Wert" nach vorne
    f.close()
    g = Hauptfenster()
    assert g.pmi.tabelle.horizontalHeader().visualIndex(3) == 0
    g.close()


def test_schnellmessung_statusleiste_und_eigenschaften(fenster_ctc01):
    from programm.kern.messen import art_von
    f = fenster_ctc01
    zyl = [x for x in f.erg.modell.flaechen if art_von(x) == "Zylinder"]
    f.ansicht.setze_auswahl([zyl[0]])
    assert "mm²" in f.schnell.text() and "Zylinder" in f.schnell.text()
    f.pmi.tabelle.selectRow(12)  # Toleranz: PMI-Info ersetzt die 3D-Auswahl
    assert "13:" in f.schnell.text() and "Zylinder" not in f.schnell.text()
    f.ein.setValue("schnellinfo_aus", ["pmi"])
    f._schnell_zeigen()
    assert f.schnell.text() == ""
    f.ein.setValue("schnellinfo_aus", [])
    d = f.zeige_eigenschaften(nur_anlegen=True)
    assert "kg" in d.masse.text() and "800.000 × 450.000 × 150.000" in d.als_text()


def test_fenster_und_spalten_beim_beenden_gemerkt(app, tmp_path, monkeypatch):
    monkeypatch.setenv("DG_EINSTELLUNGEN", str(tmp_path / "e.ini"))
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    kopf = f.pmi.tabelle.horizontalHeader()
    kopf.blockSignals(True)  # nur beim Beenden speichern
    kopf.moveSection(kopf.visualIndex(4), 0)
    kopf.blockSignals(False)
    f.dock_baum.hide()
    f.close()
    g = Hauptfenster()
    assert g.pmi.tabelle.horizontalHeader().visualIndex(4) == 0
    assert not g.dock_baum.isVisibleTo(g)
    g.close()


def test_baumsuche_ausblenden_pmi_filter_bezugssystem(fenster_ctc01):
    from PySide6 import QtCore
    f = fenster_ctc01
    b = f.baum
    b.suche.setText("SOLID")
    wurzel = b.baum.topLevelItem(0)
    assert not wurzel.isHidden()
    namen = []

    def sammle(it):
        if not it.isHidden():
            namen.append(it.text(0))
        for i in range(it.childCount()):
            sammle(it.child(i))
    sammle(wurzel)
    assert "SOLID" in namen and not any("COMPOUND" in n for n in namen)
    b.suche.setText("")
    # Auswahl ausblenden: Haken im Baum folgt
    solid = next(k for k in f.erg.baum.blaetter() if not k.hilfsgeometrie)
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[0]])
    f._teil_befehl("ausblenden")
    assert solid.nummer in f.ansicht.versteckt and f.ansicht.auswahl3d == []
    f.baum.alle_zeigen()
    assert solid.nummer not in f.ansicht.versteckt
    # PMI-Filter steuert die 3D-Anzeige
    f.pmi.art.setCurrentIndex(f.pmi.art.findData("toleranz"))
    tol = {p.step_id for p in f.erg.pmi if p.art == "toleranz" and p.step_id}
    assert f.ansicht.pmi_ids_sichtbar == tol
    f.pmi.art.setCurrentIndex(0)
    assert f.ansicht.pmi_ids_sichtbar is None
    # Bezugssystem einer Toleranz A|B|C
    t = next(p for p in f.erg.pmi if p.bezug_text() == "A|B|C")
    f.pmi.waehle(lambda p: p is t)
    drf = f.ansicht.bezugssystem
    assert [(n, s) for n, s, _ in drf] == [("A", 1), ("B", 2), ("C", 3)] and all(fl for _, _, fl in drf)
    f.pmi.waehle(lambda p: False)
    assert f.ansicht.bezugssystem == []
    assert QtCore  # noqa: B018


def test_kamera_aktionen_vorhanden(fenster_ctc01):
    f = fenster_ctc01
    for n in ("kamera_zurueck", "kamera_vor", "perspektive"):
        assert f.aktionen[n].isEnabled()
    f.aktionen["perspektive"].trigger()
    assert f.ansicht.perspektive and str(f.ein.value("perspektive")).lower() in ("true", "1")
    f.aktionen["perspektive"].trigger()
    assert not f.ansicht.perspektive


def test_norm_menue_und_ballone(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    assert "ASME" in f.pmi.hinweis.text() and f.aktionen["norm_auto"].isChecked()
    f.setze_norm("iso")
    assert "ISO GPS" in f.pmi.hinweis.text() and all(p.norm == "iso" for p in f.erg.pmi)
    f.setze_norm("auto")
    assert all(p.norm == "asme" for p in f.erg.pmi)
    f.aktionen["ballone"].setChecked(True)
    f.zeige_ballone_aktuell()
    assert len(f.ansicht.ballone) >= 10
    spalte = f.pmi.SPALTEN.index("Ballon")
    assert not f.pmi.tabelle.horizontalHeader().isSectionHidden(spalte)
    assert f.pmi.tabelle.item(0, spalte).text() in ("", "1")
    f.pmi.art.setCurrentIndex(f.pmi.art.findData("toleranz"))  # Filter: nur Ballone der Toleranzen
    n_tol = len(f.ansicht.ballone)
    assert 0 < n_tol < len(f.pmi.merkmale)
    f.pmi.art.setCurrentIndex(0)
    f.aktionen["ballone"].setChecked(False)
    f.zeige_ballone_aktuell()
    assert f.ansicht.ballone == []
    csv_pfad = f.exportiere_merkmale(str(tmp_path / "m.csv"))
    assert open(csv_pfad, encoding="utf-8-sig").read().startswith("Ballon;")
    pdf = f.exportiere_pdf("merkmale", str(tmp_path / "m.pdf"))
    assert pdf and (tmp_path / "m.pdf").stat().st_size > 1000


def test_explosion_stueckliste_analyse(fenster, tmp_path):
    from tests.conftest import pfad
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f.aktionen["explosion"].setChecked(True)
    f._explosion_umschalten()
    assert f.ansicht.explosion > 0 and f.explosion_regler_aktion.isVisible() is not None
    f.aktionen["explosion"].setChecked(False)
    f._explosion_umschalten()
    assert f.ansicht.explosion == 0
    s = f.zeige_stueckliste(nur_anlegen=True)
    assert s.tabelle.rowCount() == 4
    assert s.speichere(str(tmp_path / "bom.csv")) and (tmp_path / "bom.csv").stat().st_size > 50
    gemeldet = []
    s.isolieren.connect(gemeldet.append)
    s.tabelle.cellDoubleClicked.emit(2, 0)
    assert gemeldet and len(gemeldet[0]) in (1, 4)
    f.starte_analyse("entformung", {"richtung": "+z", "mindest": 1.0, "klein": 1, "gross": 50}, warten=True)
    assert f.ansicht.abweichung is not None and "Entformung" in f.ansicht.abweichung[3].titel
    f.analyse_aus()
    assert f.ansicht.abweichung is None


def test_netz_laden_schnellmessung_eigenschaften(fenster):
    from tests.conftest import pfad
    f = fenster
    f.lade(pfad("formate/baugruppe.stl"), warten=True)
    assert f.erg is not None and len(f.erg.modell.flaechen) == 1 and f.erg.pmi == []
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[0]])
    assert "Netz" in f.schnell.text() and "Dreiecke" in f.schnell.text()
    d = f.zeige_eigenschaften(nur_anlegen=True)
    assert "120.000 × 105.000 × 37.000" in d.als_text()
    f.lade(pfad("formate/baugruppe.igs"), warten=True)
    assert len(f.erg.modell.flaechen) > 20


def test_gezielte_pmi_suche(fenster_ctc01):
    p = fenster_ctc01.pmi
    p.suche.setText("bezug:c")
    assert p.sichtbare() and all(any("C" in b.name for b in q.bezuege) or q.name == "C" for q in p.sichtbare())
    p.suche.setText("typ:position")
    assert {q.typ for q in p.sichtbare()} == {"Position"}
    p.suche.setText("wert:0.75")
    assert p.sichtbare() and all(0.75 in (q.wert, q.nennwert, q.oben, abs(q.unten or 0)) for q in p.sichtbare())
    p.suche.setText("art:bezug bezug:a")
    assert [q.name for q in p.sichtbare()] == ["A"]
    p.suche.setText("Durchmesser")  # freier Text findet auch das Merkmal
    assert p.sichtbare() and all(q.typ == "Size_Diameter" for q in p.sichtbare())
    p.suche.setText("")


def test_eigene_ansicht_messprotokoll_projekt(fenster_ctc01, tmp_path):
    from programm.kern.messen import Messung
    f = fenster_ctc01
    n0 = len(f.erg.ansichten)
    f.pmi.art.setCurrentIndex(f.pmi.art.findData("toleranz"))
    a = f.merke_ansicht("Toleranzen oben")
    assert a.eigen and len(f.erg.ansichten) == n0 + 1 and a.pmi_nummern
    assert all(p.art == "toleranz" for p in f.erg.pmi if p.nummer in a.pmi_nummern)
    f.pmi.art.setCurrentIndex(0)
    f.messen.fuege_hinzu(Messung("abstand", 12.5, "mm", [(0, 0, 0), (12.5, 0, 0)], "Punkt – Punkt"))
    pdf = f.exportiere_pdf("messungen", str(tmp_path / "m.pdf"))
    assert pdf and (tmp_path / "m.pdf").stat().st_size > 1000
    projekt = f.speichere_projekt(str(tmp_path / "p.3dgmax"))
    f.ansichten.entfernen.emit(a)
    assert len(f.erg.ansichten) == n0
    f.oeffne_projekt(projekt, warten=True)
    namen = [x.name for x in f.erg.ansichten]
    assert "Toleranzen oben" in namen and f.messen.messungen


def test_zeichnung_export(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    for endung in ("pdf", "svg", "dxf"):
        pfad = f.exportiere_zeichnung("blatt", str(tmp_path / f"z.{endung}"))
        assert pfad and (tmp_path / f"z.{endung}").stat().st_size > 1000
    assert f.exportiere_zeichnung("aktuell", str(tmp_path / "a.svg"))


def test_zeichnung_mit_pmi(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    assert f.aktionen["zeichnung_pmi"].isChecked()
    svg = f.exportiere_zeichnung("aktuell", str(tmp_path / "a.svg"))
    text = open(svg, encoding="utf-8").read()
    assert "#1d4ed8" in text  # PMI-Linien der aktuellen Ansicht
    pdf = f.exportiere_zeichnung("ansichten", str(tmp_path / "v.pdf"))
    assert pdf and (tmp_path / "v.pdf").stat().st_size > 1000
    f.aktionen["zeichnung_pmi"].setChecked(False)
    svg = f.exportiere_zeichnung("aktuell", str(tmp_path / "b.svg"))
    assert "#1d4ed8" not in open(svg, encoding="utf-8").read()


def test_vorschaubilder_ansichten(fenster_ctc01):
    f = fenster_ctc01
    f._vorschau.wait(20000)
    from PySide6 import QtWidgets
    QtWidgets.QApplication.processEvents()
    it = f.ansichten.liste.item(1)
    assert it is not None and not it.icon().isNull()


def test_schnittbox_aktion(fenster_ctc01):
    f = fenster_ctc01
    f.aktionen["schnittbox"].setChecked(True)
    f._schnittbox()
    assert not f.aktionen["schnittbox"].isChecked()  # ohne Auswahl nicht moeglich
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[3]])
    f.aktionen["schnittbox"].setChecked(True)
    f._schnittbox()
    assert f.ansicht.box is not None
    f.aktionen["schnittbox"].setChecked(False)
    f._schnittbox()
    assert f.ansicht.box is None


def test_kommentare_anlegen_projekt_export(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    assert f.neuer_kommentar("ohne Auswahl") is None
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[5]])
    k = f.neuer_kommentar("Fase prüfen", "frage")
    assert k.nummer == 1 and k.flaechen == [5] and f.ansicht.kommentar_marken
    f.ansicht.setze_auswahl([])
    f.pmi.waehle(lambda p: p.nummer == 3)
    k2 = f.neuer_kommentar("Toleranz zu eng?", "vorschlag")
    assert k2.nummer == 2 and k2.pmi == [3]
    f.kommentare.tabelle.selectRow(0)
    f.kommentare._erledigt()
    assert f.kommentare.kommentare[0].status == "erledigt"
    assert open(f.exportiere_kommentare(str(tmp_path / "k.csv")), encoding="utf-8-sig").read().count("\n") == 3
    assert f.exportiere_pdf("kommentare", str(tmp_path / "k.pdf"))
    projekt = f.speichere_projekt(str(tmp_path / "p.3dgmax"))
    f.kommentare.setze([])
    f.oeffne_projekt(projekt, warten=True)
    assert [k.text for k in f.kommentare.kommentare] == ["Fase prüfen", "Toleranz zu eng?"]


def test_toleranzzone_anzeigen(fenster_ctc01):
    f = fenster_ctc01
    f.aktionen["toleranzzone"].setChecked(True)
    f.pmi.waehle(lambda p: p.typ == "Flatness")
    assert f.ansicht.zone_formen
    f.pmi.waehle(lambda p: False)
    assert f.ansicht.zone_formen == []
    # ohne PMI-Auswahl: Zonen der PMI an den gewaehlten Flaechen
    p = next(p for p in f.erg.pmi if p.typ == "Flatness")
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in p.flaechen])
    assert f.ansicht.zone_formen and set(f.ansicht.zone_rollen) == {"zone"}
    f.ansicht.setze_auswahl([])
    f.aktionen["toleranzzone"].setChecked(False)
    # alle Zonen des Modells, mit Allgemeintoleranzen (Dialog ohne Bildschirm: Wert direkt setzen)
    from PySide6 import QtWidgets
    from programm.kern import toleranzzone as tz
    from programm.kern.toleranzzone import Allgemein
    from programm.ui.allgemein_ui import AllgemeinDialog
    d = AllgemeinDialog(None, Allgemein("m", "K"))
    assert d.wert() == Allgemein("m", "K")
    f.aktionen["toleranzzonen_alle"].setChecked(True)
    f._zone_aktualisieren([])
    anzahl = len(f.ansicht.zone_formen)
    assert anzahl > 10 and "zone" in f.ansicht.zone_rollen and "allgemein" not in f.ansicht.zone_rollen
    f._allgemein = Allgemein("m", "K")
    f.aktionen["allgemein_zeigen"].setChecked(True)
    f._allgemein_umschalten()
    assert "allgemein" in f.ansicht.zone_rollen and len(f.ansicht.zone_formen) > anzahl
    assert "ISO 2768-mK" in f.statusBar().currentMessage()
    f.waehle_allgemeintoleranzen()  # Dialog abgebrochen: Auswahl bleibt
    assert f._allgemein == Allgemein("m", "K")
    f.aktionen["allgemein_zeigen"].setChecked(False)  # ausschalten, Klassen bleiben gemerkt
    f._allgemein_umschalten()
    assert "allgemein" not in f.ansicht.zone_rollen and f._allgemein == Allgemein("m", "K")
    f.aktionen["toleranzzonen_alle"].setChecked(False)
    # an der Auswahl: Flaeche ohne PMI zeigt nur mit eingeschalteten Allgemeintoleranzen eine Zone
    belegt = {i for p in f.erg.pmi if p.art in ("mass", "toleranz") for i in p.flaechen}
    frei = next(i for i in range(len(f.erg.modell.flaechen)) if i not in belegt and
                tz.allgemein_zone(f.erg.modell, f.erg.pmi, Allgemein("m", "K"), nur={i}) is not None)
    f.aktionen["toleranzzone"].setChecked(True)
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[frei]])
    assert f.ansicht.zone_formen == []
    f.aktionen["allgemein_zeigen"].setChecked(True)
    f._allgemein_umschalten()
    assert set(f.ansicht.zone_rollen) == {"allgemein"} and len(f.ansicht.zone_formen) == 2
    f.aktionen["allgemein_zeigen"].setChecked(False)
    f._allgemein_umschalten()
    f.ansicht.setze_auswahl([])
    f.aktionen["toleranzzone"].setChecked(False)
    f._zone_aktualisieren([])
    assert f.ansicht.zone_formen == [] and isinstance(d, QtWidgets.QDialog)
    # Kontextmenue im 3D-Fenster bietet die Zonen an
    from PySide6 import QtCore
    gesehen = []

    def schliessen():
        menue = QtWidgets.QApplication.activePopupWidget()
        gesehen.extend(menue.actions())
        menue.close()
    QtCore.QTimer.singleShot(50, schliessen)
    f._kontextmenue_3d(QtCore.QPoint(10, 10))
    assert {f.aktionen[n] for n in ("toleranzzone", "toleranzzonen_alle", "allgemein_zeigen",
                                 "allgemeintoleranzen")} <= set(gesehen)


def test_toleranzkette_fenster(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    k = f.zeige_toleranzkette(nur_anlegen=True)
    f.pmi.waehle(lambda p: p.art == "mass" and p.nennwert is not None)
    f._kette_uebernehmen(+1)
    assert len(k.glieder) >= 5 and k.e.wc_max > k.e.wc_min
    k.tabelle.selectRow(0)
    k._drehen()
    assert k.glieder[0].richtung == -1
    assert k.speichere(str(tmp_path / "kette.csv"))
    assert not any("°" in g.name for g in k.glieder)  # Winkelmasse gehoeren nicht in die Laengenkette
    rss = k.e.rss
    k.cp.setValue(1.33)
    assert abs(k.e.rss - rss / 1.33) < 1e-6
    k.leeren()
    assert k.glieder == [] and k.tabelle.rowCount() == 0


def test_pmi_anlegen_berater_projekt(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    n0 = len(f.erg.pmi)
    loch = next(p for p in f.erg.pmi if p.typ == "Size_Diameter" and p.flaechen)
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in sorted(loch.flaechen)])
    neue = f.pmi_anlegen(uebernehmen=["Size_Diameter", "Position"])
    assert [p.typ for p in neue] == ["Size_Diameter", "Position"] and len(f.erg.pmi) == n0 + 2
    d = neue[0]
    assert d.passung in ("H7", "h7") and d.grenzen()[0] is not None and d.quelle == "eigen"
    assert neue[1].material == "M" and neue[1].bezuege
    assert any(g.erzeugt and d.step_id in g.pmi_ids for g in f.erg.grafik.values())
    projekt = f.speichere_projekt(str(tmp_path / "p.3dgmax"))
    f.oeffne_projekt(projekt, warten=True)
    eigene = [p for p in f.erg.pmi if p.quelle == "eigen"]
    assert [p.typ for p in eigene] == ["Size_Diameter", "Position"]


def test_pmi_bearbeiten_und_loeschen(fenster_ctc01, tmp_path):
    f = fenster_ctc01
    m = next(p for p in f.erg.pmi if p.typ == "Size_Diameter" and p.nennwert)
    alt = m.wert_text()
    f.bearbeite_pmi(m, {"nennwert": m.nennwert, "oben": 0.3, "unten": -0.1, "passung": ""})
    assert m.bearbeitet and m.original and m.wert_text() != alt and "+0.3" in m.wert_text()
    projekt = f.speichere_projekt(str(tmp_path / "p.3dgmax"))
    f.oeffne_projekt(projekt, warten=True)
    m2 = next(p for p in f.erg.pmi if p.step_id == m.step_id)
    assert m2.oben == 0.3 and m2.bearbeitet
    # in eine Kopie der STEP-Datei schreiben: geschrieben oder begruendet uebersprungen, Datei lesbar
    from programm.ui.lader import lade_alles
    ziel = f.speichere_step_pmi(str(tmp_path / "neu.stp"), melden=False)
    b = f._step_bericht
    assert ziel and {x for x in b.geschrieben + [u[:2] for u in b.uebersprungen] if x[0] == m2.nummer}
    if (m2.nummer, "oben") in b.geschrieben:
        assert next(p for p in lade_alles(ziel).pmi if p.step_id == m.step_id).oben == 0.3
    loch = next(p for p in f.erg.pmi if p.typ == "Size_Diameter" and p.flaechen)
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in sorted(loch.flaechen)])
    neue = f.pmi_anlegen(uebernehmen=["Position"])
    n = len(f.erg.pmi)
    f.loesche_eigene_pmi(neue)
    assert len(f.erg.pmi) == n - 1 and not any(neue[0].step_id in g.pmi_ids for g in f.erg.grafik.values())


def test_mehrere_schnittebenen_und_kontur(fenster_ctc01, tmp_path):
    """Zwei Schnittebenen festhalten, als Kette schalten, Schnittkontur als SVG und DXF ausgeben."""
    f = fenster_ctc01
    f.aktionen["schnitt_x"].trigger()
    f.aktionen["schnitt_merken"].trigger()
    f.aktionen["schnitt_y"].trigger()
    assert len(f.ansicht.schnitt_ebenen) == 1 and len(f.ansicht.alle_schnitt_ebenen()) == 2
    assert f.aktionen["schnitt_kette"].isEnabled()
    f.aktionen["schnitt_kette"].trigger()
    assert f.ansicht.schnitt_kette
    svg = f.exportiere_schnittkontur(str(tmp_path / "s.svg"))
    dxf = f.exportiere_schnittkontur(str(tmp_path / "s.dxf"))
    assert svg and "<polyline" in open(svg, encoding="utf-8").read()
    assert "LINE" in open(dxf).read()
    # Schnittansichten mit Schraffur (eine je Ebene)
    dxf = f.exportiere_zeichnung("schnitt", str(tmp_path / "a.dxf"))
    text = open(dxf).read()
    assert "SCHRAFFUR" in text.split("ENTITIES")[1] and "SICHTBAR" in text.split("ENTITIES")[1]
    assert f.exportiere_zeichnung("schnitt", str(tmp_path / "a.pdf"))
    f.blattformat_aktionen["A3"].trigger()  # auf ein Normblatt mit Schriftfeld und Massstab
    try:
        svg = open(f.exportiere_zeichnung("blatt", str(tmp_path / "b.svg")), encoding="utf-8").read()
        assert 'width="420.0mm"' in svg and "A3" in svg and f._letzter_massstab <= 1
        assert os.path.getsize(f.exportiere_zeichnung("blatt", str(tmp_path / "b.pdf"))) > 1000
    finally:
        f.blattformat_aktionen[""].trigger()
    f.aktionen["schnitt_aus"].trigger()
    assert f.ansicht.schnitt_ebenen == [] and f.ansicht.alle_schnitt_ebenen() == []


def test_schnittkontur_kern(ctc01):
    import numpy as np
    from programm.kern import schnitt
    y0 = schnitt.Ebene(np.zeros(3), np.array([0, 1.0, 0]))
    linien = schnitt.kontur(ctc01.form, y0)
    assert linien and all(np.allclose(l[0], l[-1]) for l in linien)  # geschlossene Konturen
    lo = np.vstack(schnitt.in_ebene(linien, y0)).min(axis=0)
    hi = np.vstack(schnitt.in_ebene(linien, y0)).max(axis=0)
    assert abs((hi[0] - lo[0]) - 800) < 0.5 and abs((hi[1] - lo[1]) - 100) < 0.5  # Plattenbreite, Hoehe


def test_schnittansicht_schraffur():
    """Platte mit Bohrung: Schraffur in der Schnittflaeche, die Bohrung bleibt frei; Rest hinter der Ebene."""
    import numpy as np
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern import schnitt, zeichnung
    form = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(40, 30, 10).Shape(),
                           BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 15, -1), gp_Dir(0, 0, 1)), 5, 12).Shape()).Shape()
    a = schnitt.schnittansicht(form, schnitt.Ebene(np.array([20.0, 15, 5]), np.array([0.0, -1, 0]), "A–A"))
    linien = a.linien[zeichnung.SCHRAFFUR]
    x = np.vstack(linien)[:, 0]
    assert len(linien) > 10 and abs(x.min()) < 1e-6 and abs(x.max() - 40) < 1e-6
    assert not any(min(l[:, 0]) < 24.9 and max(l[:, 0]) > 15.1 for l in linien)  # Bohrung frei
    lo, hi = a.grenzen()
    assert np.allclose(hi - lo, [40, 10], atol=1e-6)
    assert 'stroke-width="0.13"' in zeichnung.als_svg([a])
    # Schraffur ohne Kontur: nichts
    assert schnitt.schraffur([], 1.0) == []


def test_zeichnung_auf_blatt():
    import numpy as np
    from programm.kern import zeichnung
    a = zeichnung.Ansicht2D("x")
    a.linien[zeichnung.SICHTBAR] = [np.array([[0.0, 0.0], [800.0, 0.0], [800.0, 100.0]])]
    a.texte = [(np.array([10.0, 10.0]), 0.0, 5.0, "T")]
    out, m = zeichnung.auf_blatt([a], "A3", titel="Platte")
    assert m == 0.2 and zeichnung.massstab_text(m) == "1:5" and zeichnung.massstab_text(2.0) == "2:1"
    lo, hi = zeichnung.rahmen(out)
    assert np.allclose(lo, 0) and np.allclose(hi, [420, 297])  # SVG genau das Blatt
    b = out[1]
    p = b.linien[zeichnung.SICHTBAR][0] + np.asarray(b.versatz)
    assert np.allclose(np.ptp(p, axis=0), [160, 20]) and 25 <= p[:, 0].min() and p[:, 0].max() <= 405
    assert b.texte[0][2] == 1.0 and a.texte[0][2] == 5.0  # skaliert, Original unveraendert
    svg = zeichnung.als_svg(out, "Platte")
    assert 'width="420.0mm"' in svg and "1:5   A3" in svg and 'fill="#000"' in svg
    out, m = zeichnung.auf_blatt([a], "A4", massstab=0.1)
    assert m == 0.1


def test_verzahnung_im_fenster(fenster, tmp_path):
    sys.path.insert(0, os.path.join(WURZEL, "werkzeuge"))
    import json
    import zahnrad
    f = fenster
    pfad_rad = zahnrad.speichere(zahnrad.zahnrad(19, 2.5, 12.0, x=0.1), str(tmp_path / "rad.stp"), "Rad z19")
    f.lade(pfad_rad, warten=True)
    f.erkenne_verzahnung(warten=True)
    d = f._verzahnung
    assert len(d.liste) == 1 and d.liste[0].z == 19 and abs(d.liste[0].mn - 2.5) < 0.005
    assert d.tabelle.columnCount() == 2 and d.tabelle.item(1, 0).text() == "19"
    j = json.load(open(d.speichere("json", str(tmp_path / "v.json")), encoding="utf-8"))
    assert j["zahnraeder"][0]["hand"] == "" and abs(j["zahnraeder"][0]["x"] - 0.1) < 0.02
    assert "19" in open(d.speichere("csv", str(tmp_path / "v.csv")), encoding="utf-8-sig").read()
    d.close()
    # Radpaar: zweite Tabelle und Paare im JSON
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    from programm.kern import verzahnung as vz
    from programm.ui.verzahnung_ui import VerzahnungFenster
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(46.0, 0, 0))
    raeder = [vz.erkenne(zahnrad.zahnrad(19, 2.5, 12.0), "A"),
              vz.erkenne(zahnrad.zahnrad(18, 2.5, 12.0).Moved(TopLoc_Location(t)), "B")]
    d = VerzahnungFenster(raeder, str(tmp_path / "x"), f)
    assert len(d.paare) == 1 and d.paar_tabelle.columnCount() == 1
    assert json.load(open(d.speichere("json", str(tmp_path / "p.json")), encoding="utf-8"))["paare"][0]["a"] == "A"
    d.close()


def test_fokusmodus(fenster_ctc01):
    """Fokus: Bauteile durchscheinend, solange etwas gewaehlt ist; Auswahl (Flaechen, Teile) bleibt deckend."""
    f = fenster_ctc01
    assert not f.ansicht.fokus_aktiv()
    f.aktionen["fokus"].setChecked(True)
    f._fokus_umschalten()
    assert f.ansicht.fokus and not f.ansicht.fokus_aktiv()  # nichts gewaehlt: nichts durchscheinend
    f.pmi.waehle(lambda p: p.typ == "Flatness")
    assert f.ansicht.fokus_aktiv() and f.ansicht.hervor
    f.pmi.waehle(lambda p: False)
    f.baum.baum.topLevelItem(0).child(0).setSelected(True)
    assert f.ansicht.fokus_teile and f.ansicht.fokus_aktiv()
    f.baum.baum.clearSelection()
    f.aktionen["fokus"].setChecked(False)
    f._fokus_umschalten()
    assert not f.ansicht.fokus_aktiv()


def test_pdf_spalten_wie_pmi_liste(fenster_ctc01):
    """Die PMI-Tabelle im PDF uebernimmt die sichtbaren Spalten und ihre Reihenfolge aus der Liste."""
    from programm.ui.berichte import pmi_tabelle
    f = fenster_ctc01
    kopf = f.pmi.tabelle.horizontalHeader()
    spalten = list(f.pmi.SPALTEN)
    kopf.setSectionHidden(spalten.index("Toleranzwert"), False)
    kopf.setSectionHidden(spalten.index("Name"), True)
    kopf.moveSection(kopf.visualIndex(spalten.index("Wert")), 0)
    titel, zeilen = pmi_tabelle(f, f.erg.pmi[:3])
    namen = f.pmi.sichtbare_spalten()
    assert namen[0] == "Wert" and "Toleranzwert" in namen and "Name" not in namen
    assert len(titel) == len(namen) and abs(sum(w for _, w in titel) - 1.0) < 1e-9
    assert zeilen[0][0] == f.erg.pmi[0].wert_text()


def test_vorschaubilder_klein(fenster):
    f = fenster
    assert f.ansichten.vorschau == "klein" and f.ansichten.liste.iconSize().width() <= 48
    f.ansichten.setze_vorschaugroesse("gross")
    assert f.ansichten.liste.iconSize().width() == 96
    f.ansichten.setze_vorschaugroesse("aus")
    assert f.ansichten.liste.iconSize().width() == 0
    f.ansichten.setze_vorschaugroesse("klein")


def test_scanpruefung_im_fenster(fenster_ctc01):
    """Scan (Netz mit Rauschen, verschoben, Ebenheit verletzt) gegen die PMI: Ergebnisliste, Farbkarte ueber CAD."""
    from programm.kern import scanpruefung as sp
    from tests.conftest import pfad
    f = fenster_ctc01
    f.pruefe_scan(pfad("varianten/ctc01_scan_fehler.ply"), warten=True)
    assert f.ansicht.abweichung is not None and f.ansicht.abweichung_ueberlagert
    nach_typ = {e.pmi.typ: e.status for e in f.scan.ergebnisse}
    assert nach_typ["Flatness"] == sp.NOK and nach_typ["Perpendicularity"] == sp.OK
    zeile = next(i for i, e in enumerate(f.scan.ergebnisse) if e.pmi.typ == "Flatness")
    f.scan.tabelle.selectRow(zeile)
    assert [p.typ for p in f.pmi.gewaehlte()] == ["Flatness"]
    assert "Flatness" not in f.scan.als_csv() and ";" in f.scan.als_csv()
    f.scan_aus()
    assert f.ansicht.abweichung is None and not f.dock_scan.isVisible()


def test_reiter_schliessen_und_abbrechen(fenster_ctc01):
    """X auf dem Reiter schliesst die Leiste; Abbrechen beendet eine Analyse und blendet den Laufbalken aus."""
    import time
    from PySide6 import QtCore, QtWidgets
    from programm.kern import analyse as an
    f = fenster_ctc01
    app = QtWidgets.QApplication.instance()
    f.dock_messen.show()
    for _ in range(5):
        app.processEvents()
    leisten = [l for l in f.findChildren(QtWidgets.QTabBar, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly)
               if l.isVisible()]
    leiste = next(l for l in leisten if f.dock_messen.windowTitle() in [l.tabText(i) for i in range(l.count())])
    assert leiste.tabsClosable()
    leiste.tabCloseRequested.emit([leiste.tabText(i) for i in range(leiste.count())].index(f.dock_messen.windowTitle()))
    assert not f.dock_messen.isVisible() and f.dock_pmi.isVisible()

    f.starte_analyse(an.ENTFORMUNG, {"mindest": 1.0, "richtung": "+z"})
    assert f.fortschritt.isVisibleTo(f) and f.abbrechen.isVisibleTo(f) and not f.analyse.start.isEnabled()
    f.abbrechen.click()
    t0 = time.time()
    while f._analyse_lader.isRunning() and time.time() - t0 < 30:
        app.processEvents()
    app.processEvents()
    assert not f.fortschritt.isVisibleTo(f) and f.analyse.start.isEnabled() and f.ansicht.abweichung is None




def _beispiele(f, namen):
    from programm.kern import beispiele
    for b in beispiele.BEISPIELE:
        if b.name not in namen:
            continue
        assert beispiele.dateien(b) is not None, b.name
        assert f.oeffne_beispiel(b.name, warten=True), b.name
        assert f.erg is not None and getattr(f, "_nach_laden", None) is None, b.name
        if b.name == "pmi":
            assert f._ansicht_pmi_ids
        elif b.name == "zonen":
            assert "allgemein" in f.ansicht.zone_rollen and "zone" in f.ansicht.zone_rollen
        elif b.name == "schnittansicht":
            assert f.ansicht.ansicht_schnitt
        elif b.name in ("vergleich_pmi", "vergleich_geo", "baugruppe"):
            assert f.vergleich is not None and f.vergleich.aenderungen
        elif b.name == "scan":
            assert getattr(f, "_scan", None) is not None
        elif b.name == "kette":
            assert f._kette.glieder and abs(f._kette.cp.value() - 1.33) < 1e-9
        elif b.name == "kollision":
            assert f.ansicht.kollision is not None and f.ansicht.kollision[1] is not None
        elif b.name == "zusammenbau":
            assert len(f.baugruppe.verbindungen) == 2 and f.zusammenbau.wiggle_an.isChecked()
            f.zusammenbau_zuruecksetzen()
            f.zusammenbau.wiggle_an.setChecked(False)
    f.beende_vergleich()
    f.kollision_aus()
    f.scan_aus()
    f.aktionen["toleranzzonen_alle"].setChecked(False)
    f.aktionen["allgemein_zeigen"].setChecked(False)


@pytest.mark.langsam
def test_beispiele_modell(fenster):
    """Datei > Beispiele (ein Modell): Dateien gefunden, Schritte nach dem Laden ausgefuehrt."""
    from programm.kern import beispiele
    assert {b.name for b in beispiele.BEISPIELE} == {"pmi", "pruefen", "zonen", "schnittansicht", "kette", "scan",
                                                      "vergleich_pmi", "vergleich_geo", "baugruppe", "kollision",
                                                      "zusammenbau", "variation", "kette_getriebe"}
    _beispiele(fenster, ("pmi", "pruefen", "zonen", "schnittansicht", "kette", "kollision", "zusammenbau"))


def test_baugruppenvariation_im_fenster(fenster, tmp_path):
    """Beispiel Baugruppenvariation: Messgroessen mit Ergebnis und Beitragenden, Soll per Tabelle, PDF, Projekt."""
    f = fenster
    _beispiele(f, ("variation",))
    z = f.zusammenbau
    assert len(f.baugruppe.verbindungen) == 5 and len(f.baugruppe.masse) == 2
    assert z.reiter.currentIndex() == 1 and z.masse.rowCount() == 2 and z.gewaehlte_messgroesse() == 2
    assert "…" in z.masse.item(0, 3).text() and z.beitraege.rowCount() == 5
    assert z.masse.item(1, 6).text().endswith("%") and z.masse.item(1, 7).text()
    z.masse.item(0, 5).setText("≥ 4,1")  # Soll per Doppelklick: fast alles ausserhalb
    m = f.baugruppe.masse[0]
    assert m.soll_min == 4.1 and m.soll_max is None and float(z.masse.item(0, 6).text().rstrip("%")) > 90
    pdf = f.exportiere_messgroessen_pdf(str(tmp_path / "m.pdf"))
    assert pdf and os.path.getsize(pdf) > 1000
    # Messgroesse aus der Auswahl: Zylinder geht nicht, gleiche Ebene am selben Teil auch nicht
    knoten = {k.nummer: k for k in f.erg.baum.blaetter()}
    from programm.kern.verbindung import flaeche_im_teil
    deckel = next(k.nummer for k in knoten.values() if k.name == "Deckel")
    fl = flaeche_im_teil(knoten[deckel].form, 15, f.erg.modell)
    f.ansicht.setze_auswahl([fl, fl], [deckel, deckel])
    assert f.messgroesse_auswahl() is None
    projekt = f.speichere_projekt(str(tmp_path / "p.3dgmax"))
    f.oeffne_projekt(projekt, warten=True)
    assert [x.soll_min for x in f.baugruppe.masse] == [4.1, -0.05] and f.zusammenbau.masse.rowCount() == 2
    z.gewaehlte_messgroesse() and z._mass_entfernen()
    assert len(f.baugruppe.masse) == 1


def test_zusammenbau_321_im_fenster(fenster):
    """3-2-1 aus sechs Ebenen: Deckel an drei Ebenen der Grundplatte, danach bestimmt; falsche Auswahl gemeldet."""
    import numpy as np
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import verbindung as vb
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    knoten = {k.name: k for k in f.erg.baum.blaetter()}

    def ebene(name, n, groesste):
        """Ebene des Teils mit Normale n, die am weitesten (groesste) bzw. wenigsten in Richtung n liegt."""
        kandidaten, ex = [], TopExp_Explorer(knoten[name].form, TopAbs_FACE)
        while ex.More():
            m = vb.merkmal(ex.Current())
            if m and m[0] == "ebene" and np.allclose(m[2], n, atol=1e-6):
                kandidaten.append((float(m[1] @ np.asarray(n)), ex.Current()))
            ex.Next()
        return max(kandidaten, key=lambda x: x[0] if groesste else -x[0])[1]
    deckel, platte = knoten["Deckel"].nummer, knoten["Grundplatte"].nummer
    auswahl, teile = [], []
    for n in ((0, 0, -1), (-1, 0, 0), (0, -1, 0)):
        gegen = tuple(-x for x in n)
        auswahl += [ebene("Deckel", n, False), ebene("Grundplatte", gegen, True)]
        teile += [deckel, platte]
    f.ansicht.setze_auswahl(auswahl[:4], teile[:4])
    assert f.verbinde_321() is None
    f.ansicht.setze_auswahl(auswahl, teile)
    out = f.verbinde_321()
    assert out and len(out) == 3 and not f.baugruppe.verletzt() and len(f.baugruppe.freiheitsgrade(deckel)) == 0
    assert f.zusammenbau.verbindungen.rowCount() >= 3


@pytest.mark.langsam
def test_beispiele_vergleich_und_scan(fenster):
    _beispiele(fenster, ("vergleich_pmi", "vergleich_geo", "baugruppe", "scan"))


def test_toleranzkette_aus_3d_auswahl(fenster):
    """Flaechen in Klickreihenfolge -> Glieder; Zeile waehlen hebt ihre Flaechen hervor; Verteilung je Glied."""
    f = fenster
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    k = f.zeige_toleranzkette(nur_anlegen=True)
    k.lage.setChecked(False)
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in (181, 187, 183, 185)])
    assert f._kette_aus_auswahl() == 3
    assert [g.quelle for g in k.glieder] == ["pmi", "ohne", "pmi"]  # FTC-10 nennt keine Allgemeintoleranz
    assert "ohne Toleranz" in f.statusBar().currentMessage() or "without tolerance" in f.statusBar().currentMessage()
    k.leeren()
    from programm.kern.toleranzzone import Allgemein
    f._allgemein = Allgemein("m", "")
    f._kette_aus_auswahl()
    assert [g.quelle for g in k.glieder] == ["pmi", "allgemein", "pmi"]
    k.lage.setChecked(True)
    k.tabelle.selectRow(0)
    assert f.ansicht.hervor == {181, 187}
    k.tabelle.cellWidget(1, 7).setCurrentIndex(k.tabelle.cellWidget(1, 7).findData("gleich"))
    assert k.glieder[1].verteilung == "gleich" and k.e.anteile[1] > k.e.anteile[0]
    k.leeren()


def test_kollisionen_im_fenster(fenster, tmp_path):
    """Leiste Kollisionen: pruefen, Befund waehlen zeigt ihn, Status/CSV, Abbrechen ueber die Statuszeile."""
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f.zeige_kollision_leiste()
    werte = f.kollision.werte()
    assert werte["umfang"] == "alle" and not f.kollision.hoechst.isEnabled()
    f.starte_kollision(werte, warten=True)
    assert len(f.kollision.befunde) == 5 and f.kollision.zaehler()["kollision"] == 4  # 4 x Schraube/Deckel + Kontakt
    f.kollision.tabelle.selectRow(0)
    teile, form, punkte = f.ansicht.kollision
    assert len(teile) == 2 and form is not None
    f.kollision.tabelle.cellWidget(0, 7).setCurrentIndex(1)
    assert f.kollision.befunde[0].status == "akzeptiert"
    assert f.kollision.speichere_csv(str(tmp_path / "k.csv"))
    # gewaehlte Teile gegen den Rest, mit Band
    f.baum.baum.clearSelection()
    platte = next(it for it in f.baum.baum.findItems("Grundplatte", __import__("PySide6").QtCore.Qt.MatchFlag.MatchRecursive))
    platte.setSelected(True)
    f.starte_kollision({**werte, "umfang": "gegen", "hoechst": 4.0, "kontakte": False}, warten=True)
    assert [b.art for b in f.kollision.befunde] == ["zu_weit"]
    f.kollision_aus()
    assert f.ansicht.kollision is None and not f.kollision.befunde


@pytest.mark.langsam
def test_toleranzkette_lage_pdf_projekt(fenster, tmp_path):
    """Lagetoleranzen der Endflaechen als Glieder, PDF-Bericht, Kette im Projekt gespeichert und wieder geladen."""
    f = fenster
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    k = f.zeige_toleranzkette(nur_anlegen=True)
    k.leeren()
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in (181, 187, 183, 185)])
    f._kette_aus_auswahl()
    lage = [g for g in k.glieder if g.quelle == "lage"]
    assert [g.pmi_nummer for g in lage] == [34, 36] and abs(lage[0].toleranz - 1.0) < 1e-9
    k.cp.setValue(1.33)
    assert os.path.getsize(f.exportiere_kette_pdf(str(tmp_path / "kette.pdf"))) > 1000
    k.geprueft.setChecked(True)
    k.pruef_kommentar.setText("abgestimmt")
    projekt = f.speichere_projekt(str(tmp_path / "k.3dgmax"))
    k.leeren()
    assert not k.geprueft.isChecked()
    f.oeffne_projekt(projekt, warten=True)
    k = f._kette
    assert len(k.glieder) == 5 and abs(k.cp.value() - 1.33) < 1e-9 and k.glieder[0].flaechen == (181, 187)
    assert k.geprueft.isChecked() and k.freigabe["kommentar"] == "abgestimmt"  # Freigabe auch im Projekt
    k.leeren()


def test_zusammenbau_im_fenster(fenster, tmp_path):
    """Leiste Zusammenbau: zwei Flaechen fangen, Freiheitsgrade, Wiggle, Projekt, Kollision mit Teillagen."""
    import numpy as np
    from programm.kern.verbindung import flaeche_im_teil
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f.zeige_zusammenbau()
    knoten = {k.nummer: k for k in f.erg.baum.blaetter()}
    fl = lambda t, i: flaeche_im_teil(knoten[t].form, i, f.erg.modell)  # noqa: E731
    f.ansicht.setze_auswahl([fl(4, 18)], [4])
    assert f.verbinde_auswahl() is None  # nur eine Flaeche
    f.ansicht.setze_auswahl([fl(4, 18), fl(3, 15)], [4, 3])
    assert f.verbinde_auswahl().art == "eben"
    f.ansicht.setze_auswahl([fl(4, 19), fl(2, 6)], [4, 2])
    f.verbinde_auswahl()
    assert f.zusammenbau.verbindungen.rowCount() == 2 and np.allclose(f.ansicht.teil_lagen[4][:3, 3], [0, 0, 1])
    zeile = f.zusammenbau._teil_nummern.index(4)
    assert f.zusammenbau.teile.item(zeile, 1).text() == "1"
    assert f.zusammenbau.teile.item(f.zusammenbau._teil_nummern.index(2), 1).text() == "–"  # Grundplatte fest
    f.zusammenbau.teile.selectRow(zeile)
    f.zusammenbau.wiggle_an.setChecked(True)
    for _ in range(5):
        f._wiggle_schritt()
    assert not np.allclose(f.ansicht.teil_lagen[4], f.baugruppe.lage(4))  # bewegt sich
    f.zusammenbau.wiggle_an.setChecked(False)
    assert np.allclose(f.ansicht.teil_lagen[4], f.baugruppe.lage(4))
    # Spielraum: Geometrie 6.6/6 -> 0.3 (kein PMI, keine Allgemeintoleranz in der Datei), Doppelklick aendert
    assert abs(f.baugruppe.verbindungen[1].toleranz - 0.3) < 1e-9
    assert f.zusammenbau.teile.item(zeile, 2).text().startswith("±")
    f.zusammenbau.verbindungen.item(0, 6).setText("0.05")
    assert f.baugruppe.verbindungen[0].toleranz == 0.05 and f.baugruppe.verbindungen[0].quelle in ("manuell", "manual")
    f.zusammenbau.wiggle_art.setCurrentIndex(1)  # innerhalb der Toleranzen
    f.zusammenbau.wiggle_an.setChecked(True)
    assert f._wiggle_zustand is not None and f._wiggle_zustand[3] is not None
    for _ in range(10):
        f._wiggle_schritt()
    weg = np.abs(f.ansicht.teil_lagen[4][:3, 3] - f.baugruppe.lage(4)[:3, 3]).max()
    assert 0 < weg < 0.35 * f.zusammenbau.faktor.value() + 1e-6
    f.zusammenbau.wiggle_an.setChecked(False)
    f.zusammenbau.wiggle_art.setCurrentIndex(0)
    projekt = f.speichere_projekt(str(tmp_path / "z.3dgmax"))
    f.zusammenbau_zuruecksetzen()
    assert not f.baugruppe.verbindungen and f.ansicht.teil_lagen == {}
    f.oeffne_projekt(projekt, warten=True)
    assert len(f.baugruppe.verbindungen) == 2 and np.allclose(f.baugruppe.lage(4)[:3, 3], [0, 0, 1])
    f.zusammenbau_zuruecksetzen()


def test_reiter_menue_blendet_leisten_ein(fenster_ctc01):
    """Rechtsklick auf die Reiterleiste: ausgeblendete Leiste einblenden, sie landet in dieser Reitergruppe."""
    from PySide6 import QtCore, QtWidgets
    f = fenster_ctc01
    app = QtWidgets.QApplication.instance()
    f.dock_messen.show()
    for _ in range(5):
        app.processEvents()
    leiste = next(l for l in f.findChildren(QtWidgets.QTabBar, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly)
                  if l.isVisible() and l.count() > 1)
    assert leiste.contextMenuPolicy() == QtCore.Qt.ContextMenuPolicy.CustomContextMenu
    f.dock_kommentare.hide()
    m = f._tab_menue(leiste, QtCore.QPoint(5, 5), ausfuehren=False)
    a = next(a for a in m.actions() if a.text() == f.dock_kommentare.windowTitle())
    assert not a.isChecked()
    a.setChecked(True)
    for _ in range(5):
        app.processEvents()
    assert f.dock_kommentare.isVisible() and f.dock_kommentare in f.tabifiedDockWidgets(f.dock_pmi)
    f.dock_kommentare.hide()
    f.dock_messen.hide()


@pytest.mark.langsam
def test_scanpruefung_punktwolke_bezug_bericht(fenster_ctc01, tmp_path):
    """Punktwolke (XYZ) pruefen, am Bezugssystem A|B|C neu auswerten, Pruefbericht als PDF."""
    from programm.kern.laden import lies_ply
    f = fenster_ctc01
    pts, _ = lies_ply(pfad("varianten/ctc01_scan_fehler.ply"))
    datei = tmp_path / "scan.xyz"
    datei.write_text("\n".join(f"{x:.5f} {y:.5f} {z:.5f}" for x, y, z in pts[::5]), encoding="utf-8")
    f.pruefe_scan(str(datei), warten=True)
    assert f._scan["punktwolke"] and f.ansicht.abweichung is not None
    assert f.scan.ausrichtung.count() >= 2 and tuple(f.scan.ausrichtung.itemData(1)) == ("A", "B", "C")
    nach_typ = {e.pmi.typ: e.status for e in f.scan.ergebnisse}
    assert nach_typ["Flatness"] == "nok"
    f.scan.ausrichtung.setCurrentIndex(1)
    f.pruefe_scan(f._scan["pfad"], warten=True, bezug=f.scan.gewaehlter_bezug())
    assert f._scan["bezug"] == ("A", "B", "C") and "3-2-1" in f.scan.kopf.text()
    assert f.scan.gewaehlter_bezug() == ("A", "B", "C")
    pdf = f.exportiere_scan_pdf(str(tmp_path / "bericht.pdf"), bilder=False)
    assert os.path.getsize(pdf) > 1000
    f.scan_aus()


def test_befehlssuche_und_startseite(fenster):
    """Strg/⌘+K findet Befehle auch ueber den englischen Text, Enter fuehrt aus; Startseite mit Aufgaben."""
    from PySide6 import QtWidgets
    from programm.kern import beispiele
    from programm.ui import befehle_ui as bu
    f = fenster
    assert len(f.start.beispiele_menue.actions()) == len(beispiele.BEISPIELE)
    alle = bu.befehle(f.menuBar())
    assert len(alle) > 100 and all(b.text for b in alle)
    assert bu.treffer(alle, "schnitt ausw")[0].aktion is f.aktionen["schnitt_auswahl"]
    assert f.aktionen["schnitt_auswahl"] in {b.aktion for b in bu.treffer(alle, "section selection")}  # englisch
    assert not bu.treffer(alle, "gibtsnicht")
    d = f.zeige_befehlssuche()
    d.eingabe.setText("Perspektive")
    assert d.treffer[0].aktion is f.aktionen["perspektive"] and not d.ausfuehren()  # ohne Modell gesperrt
    f.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    d = f.zeige_befehlssuche()
    d.eingabe.setText("perspek")
    vorher = f.aktionen["perspektive"].isChecked()
    assert d.ausfuehren()
    QtWidgets.QApplication.processEvents()
    assert f.aktionen["perspektive"].isChecked() != vorher and not d.isVisible()


def test_alle_zonen_nur_sichtbare_teile(fenster):
    """Alle Toleranz-/Allgemeintoleranzzonen: ausgeblendete Teile zeigen keine Zonen, Einblenden holt sie zurueck."""
    from programm.kern.toleranzzone import Allgemein
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f._allgemein = Allgemein("m", "")
    f.aktionen["toleranzzonen_alle"].setChecked(True)
    f.aktionen["allgemein_zeigen"].setChecked(True)
    f._allgemein_umschalten()
    alle = len(f.ansicht.zone_formen)
    platte = next(k.nummer for k in f.erg.baum.blaetter() if k.name == "Grundplatte")
    deckel = next(k.nummer for k in f.erg.baum.blaetter() if k.name == "Deckel")
    f.ansicht.knoten_sichtbar({platte}, False)
    weniger = len(f.ansicht.zone_formen)
    assert 0 < weniger < alle  # nur noch die Schrauben
    f.ansicht.isoliere({deckel})  # Deckel hat keine Flaeche ohne Angabe mit Allgemeintoleranz-Zone
    assert len(f.ansicht.zone_formen) == 0
    f.ansicht.isoliere(None)
    assert len(f.ansicht.zone_formen) == alle


def test_toleranzkette_planspiel_und_anwendbar(fenster, tmp_path):
    """Planspiel: Toleranz in der Tabelle aendern, Ist und Planspiel nebeneinander, Verwerfen/Uebernehmen;
    Doppelklick auf die Richtung; das anwendbare Verfahren fett."""
    from programm.kern import toleranzkette as tk
    from programm.ui.toleranzkette_ui import SP_RICHTUNG, SP_TOL
    f = fenster
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    k = f.zeige_toleranzkette(nur_anlegen=True)
    k.ergaenze([tk.Glied("a", 20, 20.1, 19.9), tk.Glied("b", 5, 5.05, 4.95, -1)])
    koepfe, zeilen = k.ergebnis_zeilen()
    assert [fett for _, fett in zeilen[:2]] == [True, False] and zeilen[0][0][0].startswith("✓")  # 2 Glieder
    assert k.ergebnisse.item(0, 0).font().bold() and not k.ergebnisse.item(1, 0).font().bold()
    k._doppelklick(1, SP_RICHTUNG)
    assert k.glieder[1].richtung == 1 and k.tabelle.item(1, SP_RICHTUNG).text() == "+"
    k.ergaenze([tk.Glied(str(i), 3, 3.1, 2.9) for i in range(3)])  # n_eff = 4,4
    assert k.e.statistisch and k.ergebnisse.item(1, 0).font().bold()  # jetzt statistisch fett
    breite = k.e.wc_max - k.e.wc_min
    k.starte_planspiel()
    assert k.im_planspiel and k.plan_leiste.isVisibleTo(k) and k.ergebnisse.horizontalHeaderItem(2).text()
    k.tabelle.item(0, SP_TOL).setText("0,1")  # Toleranz des ersten Glieds halbieren
    assert abs(k.glieder[0].toleranz - 0.1) < 1e-12 and abs(k._ist[0].toleranz - 0.2) < 1e-12
    assert k.e.wc_max - k.e.wc_min < breite and abs(k.e_ist.wc_max - k.e_ist.wc_min - breite) < 1e-12
    assert k.ergebnis_zeilen()[1][0][0][3].startswith("-")  # Δ Breite negativ
    from PySide6 import QtWidgets
    QtWidgets.QApplication.processEvents()
    assert k.tabelle.item(0, SP_TOL).font().bold() and "0.2" in k.tabelle.item(0, SP_TOL).toolTip()
    pdf = f.exportiere_kette_pdf(str(tmp_path / "plan.pdf"))
    assert pdf and os.path.getsize(pdf) > 1000
    k.beende_planspiel(False)
    assert not k.im_planspiel and abs(k.glieder[0].toleranz - 0.2) < 1e-12
    k.starte_planspiel()
    k.tabelle.item(0, SP_TOL).setText("0,1")
    k.beende_planspiel(True)
    assert abs(k.glieder[0].toleranz - 0.1) < 1e-12 and k.e_ist is None


def test_toleranzkette_szenarien(fenster, tmp_path):
    f = fenster
    assert f.oeffne_beispiel("kette_getriebe", warten=True)
    k = f._kette
    assert not k.vergleichen.isEnabled() and k.merke_szenario("x") is None  # nur im Planspiel
    k.starte_planspiel()
    g = k.glieder[1]
    g.hoechst, g.mindest = g.mitte + 0.05, g.mitte - 0.05
    assert k.merke_szenario("Hülse genauer") == "Hülse genauer"
    k.glieder[0].hoechst += 0.2
    assert k.merke_szenario("Zahnrad gröber")
    koepfe, zeilen = k.szenario_zeilen()
    assert [z[0] for z in zeilen][1:] == ["Hülse genauer", "Zahnrad gröber"] and len(koepfe) == 7
    breite = [float(z[4].replace(",", ".")) for z in zeilen]
    assert breite[1] < breite[0] and abs(breite[2] - breite[1] - 0.2) < 1e-9  # Szenario 2 baut auf 1 auf
    d = k.zeige_szenarien()
    d.close()
    ziel = k.speichere_kette(str(tmp_path / "s"))  # im Planspiel: das Ist wird gespeichert
    k.beende_planspiel(False)
    k.leeren()
    f.oeffne_kette(ziel, warten=True)
    assert list(k.szenarien) == ["Hülse genauer", "Zahnrad gröber"] and k.szenario.count() == 3
    ist = k.glieder[1].toleranz
    k.lade_szenario("Hülse genauer")
    assert k.im_planspiel and abs(k.glieder[1].toleranz - 0.1) < 1e-9 and abs(k._ist[1].toleranz - ist) < 1e-12


def test_toleranzkette_korrelation(fenster):
    f = fenster
    assert f.oeffne_beispiel("kette_getriebe", warten=True)
    k = f._kette
    vorher = k.e.rss
    k.setze_korrelation([3, 4], "Welle", 1.0)  # Bund bis Nut und Nutbreite: eine Aufspannung
    assert k.glieder[3].gruppe == "Welle" and "Welle ρ 1" in k.tabelle.item(3, 0).text()
    assert k.e.rss != vorher
    k.setze_korrelation([3, 4], "Welle", 0.0)
    assert not k.glieder[3].gruppe and abs(k.e.rss - vorher) < 1e-12


def test_toleranzkette_messwerte(fenster):
    from programm.ui.toleranzkette_ui import MesswerteDialog
    f = fenster
    assert f.oeffne_beispiel("kette_getriebe", warten=True)
    k = f._kette
    g = k.glieder[1]
    mitte = k.e.mitte
    k._setze(g, "verteilung", "messwerte")
    d = MesswerteDialog(g, k)
    d.text.setPlainText("43,21\n43,19\n43,22\n43,20")
    assert "n = 4" in d.info.text() and len(d.werte()) == 4
    assert k.messwerte_eingeben(g, d.werte()) and g.gemessen
    k._fuelle()
    knopf = k.tabelle.cellWidget(1, 8)
    assert "n = 4" in knopf.text() and not k.tabelle.cellWidget(1, 9).isEnabled()
    assert abs(k.e.mitte - mitte - g.wirk_versatz * g.richtung) < 1e-9


def test_toleranzkette_getriebe_beispiel(fenster, tmp_path):
    """Beispiel: Kette mit Modell laden, Temperaturen und Werkstoffe, Bauteiltemperatur, Stellglied, Laengenbereich,
    Speichern und wieder Oeffnen, Richtungen aus dem Schlussmass, Kette ablaufen."""
    from programm.kern import toleranzkette as tk
    from programm.ui.toleranzkette_ui import WerkstoffDialog
    f = fenster
    assert f.oeffne_beispiel("kette_getriebe", warten=True)
    k = f._kette
    assert f.erg is not None and f.erg.pfad.endswith("getriebe.stp") and len(k.glieder) == 6
    assert k.waerme.isChecked() and [t for t, _ in k.e_temp] == [-20.0, 100.0]
    assert k.werkstoffe["Distanzhülse"]["alpha"] == 23.0 and {g.teil for g in k.glieder} >= {"Welle", "Zahnrad"}
    texte = [k.ergebnisse.item(z, 0).text() for z in range(k.ergebnisse.rowCount())]
    assert any("100 °C" in t for t in texte) and k.e_temp[1][1].nenn < k.e.nenn
    d = WerkstoffDialog(k, k)
    assert d.tabelle.rowCount() == 5
    k.setze_teiltemperatur("Welle", "t2", 60.0)
    assert k.e_temp[1][1].nenn < tk.berechne(tk.thermisch(k.glieder, k._alpha(), 100.0)).nenn
    assert any("Bauteiltemperaturen" in k.ergebnisse.item(z, 0).text() for z in range(k.ergebnisse.rowCount()))
    k.setze_stellglied(5, True)
    assert "Stellglied" in k.ergebnis.text() and "[" in k.tabelle.item(5, 0).text()
    k.ergaenze_bereich("Wellfeder", 2.0, 3.0, -1)
    assert k.glieder[-1].quelle == "bereich" and k.glieder[-1].verteilung == "gleich"
    ziel = k.speichere_kette(str(tmp_path / "meine"))
    k.leeren()
    assert not k.glieder
    f.oeffne_kette(ziel, warten=True)
    assert len(k.glieder) == 7 and k.glieder[5].stellglied and k.werkstoffe["Welle"]["t2"] == 60.0
    # Richtungen aus dem Schlussmass: Vorzeichen durcheinander, dann aus der 3D-Auswahl setzen
    for g in k.glieder:
        g.richtung = 1
    from programm.kern.toleranzkette import _ebene_oder_achse
    x = lambda i: float(_ebene_oder_achse(f.erg.modell.flaechen[i])[1][0])  # noqa: E731
    lager = max(k.glieder[0].flaechen, key=x)
    ring = min(k.glieder[5].flaechen, key=x)
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[lager], f.erg.modell.flaechen[ring]])
    hinweise = f._kette_schluss()
    assert [g.richtung for g in k.glieder[:6]] == [-1, -1, -1, 1, 1, -1] and abs(k.e.nenn - (0.4 + 2.5)) < 1e-6  # Feder (+1, nicht auf dem Weg)
    assert any("Wellfeder" in h for h in hinweise)  # Feder hat keine Flaechen: nicht auf dem Weg
    k.ablauf.setChecked(True)
    assert "Glied 1 von 7" in k.ergebnis.text().replace("&nbsp;", " ")
    k._ablauf_schritt()
    assert k.tabelle.currentRow() == 1
    k.ablauf.setChecked(False)
    # ein Klick: ganze Kette als Pfeile im 3D (Bereich orange, Schlussmass blau), im Planspiel Ist grau
    k.bild3d.setChecked(True)
    linien = f.ansicht.hilfslinien
    assert sum(1 for li in linien if li[2]) == 8 and any(li[3] == tk.FARBEN["bereich"] for li in linien)
    assert any(li[2].startswith("Schlussmaß") and li[3] == tk.FARBEN["schluss"] for li in linien)
    k.starte_planspiel()
    k._setze(k.glieder[1], "hoechst", k.glieder[1].hoechst + 0.1)
    assert any(li[3] == tk.FARBEN["ist"] for li in f.ansicht.hilfslinien)
    k.beende_planspiel(False)
    k.bild3d.setChecked(False)
    assert f.ansicht.hilfslinien == []
    # Histogramm rechts neben der Ergebnistabelle; Anforderungsgrenze ziehen, Anteil an der Mausposition
    k.anforderung.setChecked(True)
    k.histogramm.grenze_gezogen.emit(1, 0.8)
    assert k.oben.value() == 0.8 and k.anforderung_werte()[1] == 0.8
    assert k.teiler.count() == 2
    # Histogramm folgt der Ergebnistabelle: anwendbares Verfahren (hier Worst Case), Zeile waehlt, "alle" ueberlagert
    assert k.histogramm.art == ("rss" if k.e.statistisch else "wc") and k.histogramm.anteil_unter(0.4) is None
    k._verfahren_gewaehlt(2, 0)
    assert k.histogramm.art == "mc" and 0.0 < k.histogramm.anteil_unter(k.e.nenn) < 1.0
    k._verfahren_gewaehlt(2, 0)
    assert k.histogramm.art == ("rss" if k.e.statistisch else "wc")
    k.alle_ueberlagern.setChecked(True)
    assert k.histogramm.art == "alle"
    # Erklaerungen: Verfahren in der Ergebnistabelle, Spalten der Gliedertabelle; Streuungsbild je Glied
    from PySide6 import QtCore
    from programm.ui.toleranzkette_ui import SP_STREUUNG
    assert "Worst Case" in k.ergebnisse.item(0, 0).toolTip() and "RSS" in k.ergebnisse.item(1, 0).toolTip()
    assert k.tabelle.horizontalHeaderItem(SP_STREUUNG).toolTip() and k.tabelle.item(0, 5).toolTip()
    hoehen, lo, hi, mindest, hoechst = k.tabelle.item(0, SP_STREUUNG).data(QtCore.Qt.ItemDataRole.UserRole)
    assert max(hoehen) == 1.0 and lo < mindest < hoechst < hi
    # Fertigungsverfahren je Glied und kostenoptimale Verteilung im Planspiel
    from programm.ui.toleranzkette_ui import SP_FERTIGUNG
    feld = k.tabelle.cellWidget(1, SP_FERTIGUNG)
    feld.setCurrentIndex(feld.findData("druckguss"))
    assert k.glieder[1].verfahren == "druckguss"
    assert k.verteile(1.0, "kosten", False) and k.im_planspiel and "Fertigungskosten" in k.ergebnis.text()
    k.beende_planspiel(False)
    # Ampel und manuelle Freigabe (Datei und Bericht)
    assert k.bewertung()[0] in ("gruen", "gelb", "rot") and "●" in k.ampel.text()
    k.geprueft.setChecked(True)
    k.pruef_kommentar.setText("Funktion im Versuch nachgewiesen")
    assert k.freigabe["geprueft"] and k.freigabe["datum"] and k.als_datei().freigabe["kommentar"]
    ziel = f.exportiere_kette_pdf(str(tmp_path / "kette.pdf"))
    from pypdf import PdfReader
    text = "".join(s.extract_text() for s in PdfReader(ziel).pages)
    assert "Manuell freigegeben" in text and "Bewertung" in text


def test_zonen_je_instanz_und_zusammenbaulage(fenster):
    """Zonen an jeder Instanz eines mehrfach verbauten Teils; sie folgen der Lage aus dem Zusammenbau."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from programm.kern.toleranzzone import Allgemein
    from programm.kern.verbindung import flaeche_im_teil
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f._allgemein = Allgemein("m", "")
    f.aktionen["toleranzzonen_alle"].setChecked(True)
    f.aktionen["allgemein_zeigen"].setChecked(True)
    f._allgemein_umschalten()
    assert len(f.ansicht.zone_formen) == 8 + 4 * 4  # Platte 8, jede der vier Schrauben 4
    schrauben = [k.nummer for k in f.erg.baum.blaetter() if k.name.startswith("Schraube")]
    f.ansicht.knoten_sichtbar({schrauben[1]}, False)
    assert len(f.ansicht.zone_formen) == 8 + 3 * 4
    f.ansicht.knoten_sichtbar({schrauben[1]}, True)

    def hoehe():
        b = Bnd_Box()
        for form in f.ansicht.zone_formen:
            brepbndlib.Add(form, b)
        return b.Get()[5]
    vorher = hoehe()
    knoten = {k.nummer: k for k in f.erg.baum.blaetter()}
    deckel = next(k.nummer for k in knoten.values() if k.name == "Deckel")
    s = schrauben[0]
    f.ansicht.setze_auswahl([flaeche_im_teil(knoten[s].form, 18, f.erg.modell),
                             flaeche_im_teil(knoten[deckel].form, 15, f.erg.modell)], [s, deckel])
    f.verbinde_auswahl()  # Kopf auf den Deckel: Schraube 1 mm hoeher
    assert abs(hoehe() - vorher - 1.0) < 1e-6


def test_zusammenbau_umkehren_tauschen_knopf(fenster):
    f = fenster
    assert f.oeffne_beispiel("zusammenbau", warten=True)  # nicht _beispiele: das setzt den Zusammenbau zurueck
    z = f.zusammenbau
    z.verbindungen.selectRow(1)  # koaxial
    z.umkehr_knopf.click()
    assert [v.nummer for v in f.baugruppe.verletzt()] == [1]  # Kopfauflage nach dem Umkehren nicht mehr erfuellt
    z.verbindungen.selectRow(0)
    teil = f.baugruppe.verbindungen[0].teil
    z.tausch_knopf.click()
    assert f.baugruppe.verbindungen[0].gegen_teil == teil
    assert z.wiggle_an.text().startswith("⏸")  # das Beispiel laesst den Wiggle laufen
    z.wiggle_an.setChecked(False)
    assert z.wiggle_an.text().startswith("▶")


def test_groesse_der_oberflaeche(fenster, monkeypatch):
    from programm import app
    from programm.ui import groesse
    f = fenster
    assert f.aktionen["skala_100"].isChecked()
    f.aktionen["skala_130"].trigger()
    assert groesse.skalierung(f.ein) == 1.3 and groesse.gespeicherte_skalierung() == 1.3
    monkeypatch.delenv("QT_SCALE_FACTOR", raising=False)
    app.groesse_einstellen()
    assert os.environ.get("QT_SCALE_FACTOR") == "1.30"
    monkeypatch.delenv("QT_SCALE_FACTOR")


def test_toleranzkette_stufe4_verfahren_verteilen(fenster):
    from programm.kern import toleranzkette as tk
    from programm.ui.toleranzkette_ui import SP_FAKTOR
    f = fenster
    k = f.zeige_toleranzkette(nur_anlegen=True)
    k.ergaenze([tk.Glied(str(i), 10, 10.05, 9.95) for i in range(5)] + [tk.Glied("Lager", 12, 12.05, 11.95)])
    rss = k.e.rss
    k.methode.setCurrentIndex(k.methode.findData("bender"))
    zeile = [k.ergebnisse.item(1, s).text() for s in range(4)]
    assert "Bender" in zeile[0] and k.ergebnisse.item(1, 0).font().bold()
    assert abs(float(zeile[3]) - 2 * 1.5 * rss) < 1e-3
    k.methode.setCurrentIndex(k.methode.findData("verschiebung"))
    assert rss < k.e.verschiebung < (k.e.wc_max - k.e.wc_min) / 2
    k.methode.setCurrentIndex(0)
    k.tabelle.cellWidget(0, SP_FAKTOR).setValue(2.0)
    assert abs((k.e.wc_max - k.e.wc_min) - (0.1 * 7)) < 1e-9  # 5 Glieder, eines mit Faktor 2, plus Lager
    k.glieder[-1].fest = True
    assert k.verteile(0.4, "varianz", True) and k.im_planspiel
    assert abs(k.glieder[-1].toleranz - 0.1) < 1e-12 and abs(2 * k.e.rss - 0.4) < 1e-9
    assert abs(k._ist[0].toleranz - 0.1) < 1e-12  # Ist unveraendert
    k.beende_planspiel(False)
    assert abs(k.glieder[0].toleranz - 0.1) < 1e-12


def test_zusammenbau_teil_frei_bewegen(fenster):
    f = fenster
    assert f.oeffne_beispiel("zusammenbau", warten=True)
    z = f.zusammenbau
    z.wiggle_an.setChecked(False)
    schraube = next(n for n in z._teil_nummern if not f.baugruppe.fest(n))
    z.teile.selectRow(z._teil_nummern.index(schraube))
    assert z.bewegen_box.isVisibleTo(z) and len(z._frei_felder) == 1 and z._frei_felder[0].suffix() == " °"
    vorher = f.baugruppe.lage(schraube).copy()
    z._frei_felder[0].setValue(45.0)
    assert not f.baugruppe.verletzt() and f.ansicht.teil_lagen[schraube] is not None
    z._frei_zuruecksetzen()
    import numpy as np
    assert np.allclose(f.baugruppe.lage(schraube), vorher)


def test_zusammenbau_3d_griff(fenster):
    """Teil im Zusammenbau gewaehlt: 3D-Griff mit nur der offenen Drehung; Ziehen dreht das Teil um seine Achse."""
    import numpy as np
    from programm.kern import verbindung as vb
    f = fenster
    assert f.oeffne_beispiel("zusammenbau", warten=True)
    z = f.zusammenbau
    z.wiggle_an.setChecked(False)
    f.dock_zusammenbau.show()
    schraube = next(n for n in z._teil_nummern if not f.baugruppe.fest(n))
    z.teile.selectRow(z._teil_nummern.index(schraube))
    r = f.ansicht.manipulator
    assert r is not None and sum(r["drehen"]) == 1 and not any(r["verschieben"])
    achse = r["achsen"][int(np.argmax(r["drehen"]))]
    vorher = f.baugruppe.lage(schraube).copy()
    m = vb.bewegung(np.r_[achse, -np.cross(achse, r["punkt"])], 30.0)  # 30 Grad um die Griffachse
    f.ansicht.manipulator_bewegt.emit(m)
    assert not f.baugruppe.verletzt() and not np.allclose(f.baugruppe.lage(schraube), vorher)
    f.ansicht.manipulator_fertig.emit()
    assert np.allclose(f._frei[2], f.baugruppe.lage(schraube))
    z.teile.clearSelection()
    f._frei_anzeigen()
    assert f.ansicht.manipulator is None


def test_kollision_tiefe_kurven_pdf_projekt(fenster, tmp_path):
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f.zeige_kollision_leiste()
    f.starte_kollision(f.kollision.werte(), warten=True)
    k = next(b for b in f.kollision.befunde if b.art == "kollision")
    # Der Deckel hat keine Bohrungen: der Schaft (Ø 6) geht durch die 4 mm des Deckels -> Tiefe 4 mm
    assert abs(k.tiefe - 4.0) < 1e-6 and k.kurven is not None and f.kollision.tabelle.item(0, 6).text()
    f.kollision.tabelle.selectRow(0)
    assert f.ansicht.kollision[1] is not None
    f.kollision.tabelle.cellWidget(0, 7).setCurrentIndex(1)  # akzeptiert
    f.kollision.befunde[0].kommentar = "Senkung fehlt"
    pdf = f.exportiere_kollision_pdf(str(tmp_path / "k.pdf"))
    assert pdf and os.path.getsize(pdf) > 1000
    projekt = f.speichere_projekt(str(tmp_path / "p.3dgmax"))
    f.kollision_aus()
    f.oeffne_projekt(projekt, warten=True)
    assert f.kollision.befunde and f.kollision.befunde[0].status == "akzeptiert"
    assert f.kollision.befunde[0].kommentar == "Senkung fehlt"


def test_neues_fenster_und_gekoppelte_kameras(fenster):
    from programm.ui import hauptfenster as hf
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    g = f.neues_fenster()
    try:
        assert g is not f and g in hf.FENSTER and f in hf.FENSTER
        g.lade(pfad("baugruppe_b.stp"), warten=True)
        g.aktionen["kameras_koppeln"].trigger()
        assert f.aktionen["kameras_koppeln"].isChecked() and hf._fenster_uhr().isActive()
        hf.kameras_abgleichen()
        k = ((3.0, 2.0, 1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 40.0)
        g.ansicht.setze_kamera_daten(k)
        hf.kameras_abgleichen()
        assert f.ansicht.kamera_daten() == k
        g.aktionen["kameras_koppeln"].trigger()
        assert not hf._fenster_uhr().isActive()
    finally:
        g.close()
    assert g not in hf.FENSTER and f in hf.FENSTER and f.erg is not None


def test_kollision_in_grenzlagen(fenster):
    f = fenster
    assert f.oeffne_beispiel("variation", warten=True)
    f.zeige_kollision_leiste()
    werte = {**f.kollision.werte(), "mindest": 0.2, "kontakte": False}
    f.starte_kollision(werte, warten=True)
    nenn = [(b.art, b.grenzlage) for b in f.kollision.befunde]
    assert all(g == "" for _, g in nenn)
    f.starte_kollision({**werte, "grenzlagen": True}, warten=True)
    extra = [b for b in f.kollision.befunde if b.grenzlage]
    # direkt verbundene Paare (Deckel/Grundplatte, Schraube/Grundplatte, Schraube/Deckel) legt die Verbindung fest:
    # in den Grenzlagen nicht gemeldet (sonst Artefakte des symmetrischen Spiels)
    gepaart = {frozenset((v.teil, v.gegen_teil)) for v in f.baugruppe.verbindungen}
    assert all(frozenset((b.a.nummer, b.b.nummer)) not in gepaart for b in extra)
    from programm.kern import kollision as ko
    teile = [ko.Teil(k.nummer, k.name, k.form) for k in f.erg.baum.blaetter() if not k.hilfsgeometrie]
    roh = ko.pruefe_grenzlagen(teile, f._grenzlagen(), None, ko.Einstellung(0.01, 0.2, 0.0, False))
    assert any(frozenset((b.a.nummer, b.b.nummer)) in gepaart for b in roh)  # ohne Filter: Artefakte da
    assert len(f.kollision.befunde) == len(nenn) + len(extra)


def test_kollision_bewegungsbereich(fenster):
    """Schraube im Zusammenbau: Drehung um ihre Achse ist frei (rotationssymmetrisch), der Bereich +-180 Grad."""
    f = fenster
    assert f.oeffne_beispiel("zusammenbau", warten=True)
    f.zeige_kollision_leiste()
    f.kollision.bereich.setChecked(True)
    assert f.kollision.bereich_grad.isEnabled()
    f.kollision.bereich_grad.setValue(90.0)
    f.starte_kollision(f.kollision.werte(), warten=True)
    assert len(f.freie_bereiche) == 1
    name, art, unten, oben, einheit = f.freie_bereiche[0]
    assert (unten, oben, einheit) == (-90.0, 90.0, "°") and name in f.kollision.kopf.text()
    assert not any(b.bewegung for b in f.kollision.befunde)


@pytest.mark.langsam
def test_scan_von_hand_ausrichten(fenster):
    """Scan von Hand: Panel mit Scan als waehlbarer Form; drei Punktpaare (Scan = Modell verschoben) ergeben die
    Startlage, die Pruefung laeuft neu mit Feinausrichtung."""
    import numpy as np
    from programm.kern import ausrichten
    f = fenster
    assert f.oeffne_beispiel("scan", warten=True)
    d = f._scan
    p = f.scan_von_hand()
    assert p is not None and f.ansicht.ausricht_alt is not None
    # Punktpaare: Modellpunkte und dieselben Punkte im Scan (Scan -> Modell ist d["matrix"])
    inv = np.linalg.inv(d["matrix"])
    for q in ((0, 0, 0), (100, 0, 0), (0, 60, 0), (0, 0, 20)):
        q = np.array(q, float)
        p.paare.append(("punkt", (q, None), (inv[:3, :3] @ q + inv[:3, 3], None)))
    a = ausrichten.richte_nach_elementen(p.paare)
    f._scan_hand_fertig(a, warten=True)
    assert f._scan["ausrichtung"].methode == "punkte"
    assert np.allclose(f._scan["matrix"], d["matrix"], atol=0.05)  # gleiche Lage wie die Bestpassung
    p.close()


def test_qt_eigene_texte_deutsch(fenster):
    """Standardknoepfe der Qt-Dialoge auf Deutsch, wenn die Oberflaeche Deutsch ist."""
    from PySide6 import QtWidgets
    from programm import i18n
    app = QtWidgets.QApplication.instance()
    alt = i18n.SPRACHE
    try:
        i18n.SPRACHE = "de"
        assert i18n.qt_uebersetzung(app)
        kasten = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        assert kasten.buttons()[0].text().replace("&", "") == "Schließen"
        i18n.SPRACHE = "en"
        assert not i18n.qt_uebersetzung(app)
    finally:
        i18n.SPRACHE = alt
        for u in i18n._QT_UEBERSETZER:
            app.removeTranslator(u)
        i18n._QT_UEBERSETZER.clear()


def test_tooltips_vollstaendig(fenster):
    """Jedes nicht selbsterklaerende Bedienelement hat einen Tooltip (werkzeuge/tooltips.py)."""
    sys.path.insert(0, os.path.join(WURZEL, "werkzeuge"))
    import tooltips
    funde = {name: tooltips.ohne_tooltip(w) for name, w in [("Hauptfenster", fenster)] + list(tooltips.dialoge(fenster))}
    assert not {n: f for n, f in funde.items() if f}


def test_funktion_zur_tolerierung(fenster):
    """Rollen im Fenster vergeben: Bezugssystem vorschlagen und die Tolerierung als eigene PMI uebernehmen."""
    from programm.kern import funktion as fu
    f = fenster
    f.lade(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    w = f.zeige_funktion()
    m = f.erg.modell
    geo = {i: g for i in range(len(m.flaechen)) if (g := fu._geometrie(m.flaechen[i])) is not None}
    auflage = max((i for i in geo if geo[i]["art"] == "ebene"), key=lambda i: geo[i]["inhalt"])
    n = geo[auflage]["richtung"]
    bohrung = max((i for i in geo if geo[i]["art"] == "zylinder" and geo[i]["bohrung"]
                   and fu._parallel(geo[i]["richtung"], n)), key=lambda i: geo[i]["groesse"])
    f.ansicht.setze_auswahl([m.flaechen[auflage]])
    assert w.setze_rolle(w.auswahl(), "auflage") == 1
    w.setze_rolle([bohrung], "zentrierung")
    s = w.zeige_bezuege()
    assert [b.buchstabe for b in s.bezuege][:2] == ["A", "B"] and "<b>A</b>" in w.bezug_text.text()
    vorher = len(f.erg.pmi)
    neue = f._funktion_anlegen(w.vorschlaege(), fragen=False)
    assert neue and len(f.erg.pmi) == vorher + len(neue)
    assert any(p.typ == "Size_Diameter" and p.passung == "H7" for p in neue)
    projekt = f.speichere_projekt(os.path.join(tempfile.mkdtemp(), "f.3dgmax"))
    w.rollen = {}
    f.oeffne_projekt(projekt, warten=True)
    assert f._funktion.rollen == {auflage: "auflage", bohrung: "zentrierung"}  # Rollen im Projekt


def test_toleranzkette_von_hand_ohne_modell(fenster):
    """Ohne Modell: Glieder mit ＋ anlegen, Werte in die Zellen tippen, mit － entfernen; das Ergebnis rechnet."""
    from programm.ui.toleranzkette_ui import SP_HOCH, SP_MIN, SP_NENN
    f = fenster
    assert f.erg is None
    k = f.zeige_toleranzkette()
    k.leeren()
    k.neu_glied.click()
    k.neu_glied.click()
    k.neues_glied("Deckel", 5.0, 0.05, -0.05, -1)
    assert len(k.glieder) == 3 and k.glieder[0].quelle == "eigen"
    k.tabelle.item(0, 0).setText("Gehäuse")
    k.tabelle.item(0, SP_NENN).setText("50")
    k.tabelle.item(0, SP_HOCH).setText("50,2")
    k.tabelle.item(1, SP_MIN).setText("9.8")
    QtWidgets.QApplication.processEvents()
    g = k.glieder[0]
    assert g.name == "Gehäuse" and (g.nenn, g.hoechst, g.mindest) == (50.0, 50.2, 49.9)
    assert k.glieder[1].mindest == 9.8 and abs(k.e.nenn - (50 + 10 - 5)) < 1e-9
    assert k.tabelle.item(0, 0).flags() & QtCore.Qt.ItemFlag.ItemIsEditable
    k.tabelle.selectRow(1)
    k.weg.click()
    assert [x.name for x in k.glieder] == ["Gehäuse", "Deckel"] and abs(k.e.nenn - 45.0) < 1e-9
    k.bild3d.setChecked(True)  # Kettenbild auch ohne Modell (schematisch)
    assert any(li[2].startswith("Schlussmaß") for li in f.ansicht.hilfslinien)
    k.bild3d.setChecked(False)


def test_kette2d_fenster(fenster):
    """2D-Kette von Hand: Vorlage, Segment anhaengen, Wert per Drehfeld, Schlussgroesse waehlen, uebernehmen."""
    f = fenster
    w = f.zeige_kette2d()
    w.lade_vorlage("winkel")
    assert len(w.kette.segmente) == 2 and "50.0000 mm" in w.ergebnis.text()
    w.tabelle.cellWidget(1, 1).setValue(30.0)  # zweiter Schenkel 30 -> Abstand Wurzel(1800)
    assert abs(w.ergebnisse()["nenn"] - 1800 ** 0.5) < 1e-9
    w.schluss.setCurrentIndex(w.schluss.findData("x"))
    assert abs(w.ergebnisse()["nenn"] + 30) < 1e-9
    w.neues_segment()
    assert w.tabelle.rowCount() == 3
    w.in_kette.click()
    k = f._kette
    assert len(k.glieder) >= 3 and any(g.faktor != 1.0 for g in k.glieder) and k.glieder[-1].toleranz == 0


def test_kette3d_fenster(fenster):
    """3D-Kette von Hand: Vorlage, Editor-Feld aendern, Schlussgroesse waehlen, im 3D zeigen, uebernehmen."""
    f = fenster
    w = f.zeige_kette3d()
    w.lade_vorlage("turm")
    assert w.liste.count() == 2 and "20.0000 mm" in w.ergebnis.text()
    w.liste.setCurrentRow(1)
    w.editor.cellWidget(0, 0).setValue(120.0)  # Armlaenge
    w.schluss.setCurrentIndex(w.schluss.findData("x"))
    assert abs(w.ergebnisse()["nenn"] - 120) < 1e-9  # Verschiebung im Rahmen davor, Drehung wirkt danach
    w.schluss.setCurrentIndex(w.schluss.findData("y"))
    assert abs(w.ergebnisse()["nenn"]) < 1e-9
    w.im_modell.setChecked(True)
    assert any(li[2] == "Funktionspunkt" for li in f.ansicht.hilfslinien)
    w.im_modell.setChecked(False)
    w.neues_glied()
    assert w.liste.count() == 3
    w.schluss.setCurrentIndex(w.schluss.findData("z"))  # Hoehe: Kippung des Sockels wirkt mit Hebel 120
    w.in_kette.click()
    assert any(g.faktor != 1.0 for g in f._kette.glieder)
