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
    from programm.kern.toleranzzone import Allgemein
    from programm.ui.allgemein_ui import AllgemeinDialog
    d = AllgemeinDialog(None, Allgemein("m", "K"))
    assert d.wert() == Allgemein("m", "K")
    f.aktionen["toleranzzonen_alle"].setChecked(True)
    f._zone_aktualisieren([])
    anzahl = len(f.ansicht.zone_formen)
    assert anzahl > 10 and "zone" in f.ansicht.zone_rollen and "allgemein" not in f.ansicht.zone_rollen
    f._allgemein = Allgemein("m", "K")
    f._zone_aktualisieren([])
    assert "allgemein" in f.ansicht.zone_rollen and len(f.ansicht.zone_formen) > anzahl
    assert "ISO 2768-mK" in f.statusBar().currentMessage()
    f.waehle_allgemeintoleranzen()  # Dialog abgebrochen: Auswahl bleibt
    assert f._allgemein == Allgemein("m", "K")
    f.aktionen["toleranzzonen_alle"].setChecked(False)
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
    assert {f.aktionen[n] for n in ("toleranzzone", "toleranzzonen_alle", "allgemeintoleranzen")} <= set(gesehen)


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
