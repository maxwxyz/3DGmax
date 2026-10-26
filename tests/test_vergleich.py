"""Vergleich: Ausrichten, Geometrie, PMI, Aenderungsliste, Pruefprotokoll (Varianten von NIST CTC-01)."""

import sys

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
    from PySide6.QtGui import QFontDatabase
    # ohne Bildschirm hat Qt unter Windows keine Schriften -> Text im PDF nicht auslesbar
    mit_schrift = bool(QFontDatabase.families()) and sys.platform != "win32"
    if mit_schrift:
        assert "MBD_A" in pypdf.PdfReader(p).pages[0].extract_text()
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_geo_pmi.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    v = f.exportiere_pdf("vergleich", str(tmp_path / "vergleich.pdf"))
    text = "".join(s.extract_text() for s in pypdf.PdfReader(v).pages)
    assert len(pypdf.PdfReader(v).pages) >= 1 + len(f.vergleich.aenderungen)
    t = f.exportiere_pdf("pmi_aenderungen", str(tmp_path / "pmi.pdf"))
    if mit_schrift:
        assert "ctc01_geo_pmi.stp" in text and "21" in pypdf.PdfReader(t).pages[0].extract_text()


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
    assert pmi_bericht.als_csv(pmi_bericht.tabelle(alt.pmi, alt.ansichten)).startswith("No;Kind;Characteristic;Type;Name;Value")


def test_projekt_container(fenster, tmp_path):
    from programm.kern import messen
    f = fenster
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_pmi.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    f.vergleich.aenderungen[1].pruefstatus = "abgelehnt"
    f.vergleich.aenderungen[1].kommentar = "Wert prüfen"
    f.messen.fuege_hinzu(messen.punkt_abstand(*[__import__("OCC.Core.gp", fromlist=["gp_Pnt"]).gp_Pnt(0, 0, z)
                                                for z in (0, 5)]))
    ziel = f.speichere_projekt(str(tmp_path / "test"))
    assert ziel.endswith(".3dgmax")
    f.beende_vergleich()
    f.messen.loesche_alle()
    f.lade(ziel, warten=True)
    assert f.vergleich is not None and len(f.vergleich.aenderungen) == 3
    a = f.vergleich.aenderungen[1]
    assert a.pruefstatus == "abgelehnt" and a.kommentar == "Wert prüfen"
    assert len(f.messen.messungen) == 1 and abs(f.messen.messungen[0].wert - 5) < 1e-9


def test_ordnervergleich(fenster, tmp_path):
    import shutil
    from programm.kern import ordnervergleich as ov
    a, b = tmp_path / "alt", tmp_path / "neu"
    a.mkdir()
    b.mkdir()
    shutil.copy(pfad("nist_ctc_01_asme1_ap242-e1.stp"), a / "teil_rev_a.stp")
    shutil.copy(pfad("varianten/ctc01_pmi.stp"), b / "teil_rev_b.stp")
    shutil.copy(pfad("nist_ctc_01_asme1_ap242-e1.stp"), a / "gleich.stp")
    shutil.copy(pfad("nist_ctc_01_asme1_ap242-e1.stp"), b / "gleich.stp")
    shutil.copy(pfad("nist_ctc_01_asme1_ap242-e1.stp"), a / "weg.stp")
    shutil.copy(pfad("nist_ctc_01_asme1_ap242-e1.stp"), b / "dazu.stp")
    assert ov.schluessel("teil_rev_a.stp") == ov.schluessel("Teil Rev B.STP") == "teil"
    d = fenster.zeige_ordnervergleich()
    d.alt[1].setText(str(a))
    d.neu[1].setText(str(b))
    d.starte(warten=True)
    status = {p.schluessel: p.status for p in d.liste}
    assert status == {"teil": "geaendert", "gleich": "gleich", "weg": "nur_alt", "dazu": "nur_neu"}
    zeile = next(i for i, p in enumerate(d.liste) if p.schluessel == "teil")
    d.tabelle.cellDoubleClicked.emit(zeile, 0)
    assert fenster.vergleich is not None and len(fenster.vergleich.aenderungen) == 3
    d.close()


def test_pmi_name_wird_verglichen():
    from programm.kern.pmi import TOLERANZ, Pmi
    from programm.kern.vergleich_pmi import vergleiche_pmi
    a = Pmi(TOLERANZ, typ="Flatness", name="Flatness.1", wert=0.1, flaechen={1}, nummer=1)
    b = Pmi(TOLERANZ, typ="Flatness", name="Ebenheit Dichtfläche", wert=0.1, flaechen={1}, nummer=1)
    r = vergleiche_pmi([a], [b])
    assert r[0].status == "geaendert" and r[0].felder == [("name", "Flatness.1", "Ebenheit Dichtfläche")]


def test_manuell_ausrichten(fenster):
    """Punktpaare: neuer Stand um 20 mm in x verschoben -> drei Paare -> Ausrichtung findet die Verschiebung."""
    import numpy as np
    f = fenster
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_pmi.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    panel = f.starte_manuell_ausrichten()
    assert f.ansicht.ausricht_alt is not None
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.gp import gp_Pnt
    panel.fang.setChecked(False)
    for p in ([0, 0, 0], [50, 0, 0], [0, 30, 10]):
        neu = (p[0] + 20.0, p[1], p[2])  # Anzeigekoordinaten des neuen Stands (aktuell Einheitsmatrix)
        panel.punkt("neu", BRepBuilderAPI_MakeVertex(gp_Pnt(*neu)).Vertex(), neu)
        panel.punkt("alt", BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex(), tuple(p))
    assert panel.los.isEnabled()
    a = panel.berechne()
    assert np.allclose(a.matrix[:3, 3], [-20, 0, 0], atol=1e-6)
    f._neu_ausrichten(a, warten=True)
    assert f.vergleich.ausrichtung.methode == "punkte"
    panel.close()
    assert f.ansicht.ausricht_alt is None
    f.aktionen["umdrehen"].trigger()
    assert getattr(f.ansicht, "umgedreht", False)


def test_ausrichten_nach_ebenen_und_achsen():
    """Drei Ebenen (3-2-1) bzw. Ebene + zwei Achsen legen die Lage fest; zwei Ebenen nicht."""
    import numpy as np
    from programm.kern import ausrichten as au
    from scipy.spatial.transform import Rotation
    r = Rotation.from_rotvec([0.3, -0.2, 0.9]).as_matrix()
    t = np.array([12.0, -4.0, 7.0])

    def b_von(o, d):  # Element im neuen Stand (B) aus dem alten (A): B = R^-1 (A - t)
        return (r.T @ (o - t), None if d is None else r.T @ d)

    ebenen = [(np.array([0, 0, 0.0]), np.array([0, 0, 1.0])), (np.array([0, 0, 0.0]), np.array([1, 0, 0.0])),
              (np.array([0, 0, 0.0]), np.array([0, 1, 0.0]))]
    paare = [(au.EBENE, b_von(o, d), (o, d)) for o, d in ebenen]
    a = au.richte_nach_elementen(paare)
    assert np.allclose(a.matrix[:3, :3], r, atol=1e-6) and np.allclose(a.matrix[:3, 3], t, atol=1e-6)
    achsen = [(np.array([10, 0, 0.0]), np.array([0, 0, 1.0])), (np.array([0, 20, 0.0]), np.array([0, 0, 1.0]))]
    paare2 = [paare[0]] + [(au.ACHSE, b_von(o, d), (o, d)) for o, d in achsen]
    a2 = au.richte_nach_elementen(paare2)
    assert np.allclose(a2.matrix[:3, 3], t, atol=1e-5)
    with pytest.raises(ValueError):
        au.richte_nach_elementen(paare[:2])


def test_abweichungskarte_vorzeichen_und_strahl():
    from programm.kern import abweichung
    from programm.kern.laden import lade_step
    from tests.conftest import pfad
    a = lade_step(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    b = lade_step(pfad("varianten/ctc01_geo.stp"))
    selbst = abweichung.berechne(a, a)
    assert abs(selbst.alle()).max() < 0.005  # nur Netzrest an gekruemmten Flaechen
    k = abweichung.berechne(a, b)
    lo, hi = k.bereich()
    assert abs(lo + 0.5) < 0.01 and hi < 0.01  # Bohrung im neuen Stand: Untermass -0.5
    assert abweichung.standard_grenze(k, 0.01) == 0.5
    g = abweichung.stufen(0.01, 0.5)
    assert g[0] == -0.5 and g[-1] == 0.5 and 0.01 in g and -0.01 in g
    # Strahl von oben auf die Platte trifft das Netz mit Abweichung ~0
    pts, _, _ = k.gesamt()
    mitte = pts.mean(axis=0)
    treffer = k.am_strahl((mitte[0], mitte[1], pts[:, 2].max() + 100), (0, 0, -1))
    assert treffer is not None and abs(treffer[1]) < 0.01
    assert abweichung.farbe(0.0, 0.01, 0.5) != abweichung.farbe(0.4, 0.01, 0.5) != abweichung.farbe(-0.4, 0.01, 0.5)


def test_farbkarte_im_vergleich(fenster):
    from tests.conftest import pfad
    f = fenster
    f.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_geo.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    f.aenderungen.karte_an.blockSignals(True)
    f.aenderungen.karte_an.setChecked(True)
    f.aenderungen.karte_an.blockSignals(False)
    f.zeige_farbkarte(True, warten=True)
    assert getattr(f.vergleich, "karte", None) is not None
    assert f.ansicht.abweichung is not None and f.ansicht.abweichung[2] == 0.5
    f.zeige_farbkarte(False)
    assert f.ansicht.abweichung is None
    f.beende_vergleich()


def test_materialvergleich_bohrung_aufgeweitet():
    import math
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern import vergleich_volumen as vv

    def platte(r):
        box = BRepPrimAPI_MakeBox(100.0, 60.0, 20.0).Shape()
        loch = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(50, 30, -1), gp_Dir(0, 0, 1)), r, 22.0).Shape()
        return BRepAlgoAPI_Cut(box, loch).Shape()
    m = vv.berechne(platte(10.0), platte(10.5))
    soll = math.pi * (10.5 ** 2 - 10.0 ** 2) * 20
    assert abs(m.vol_weg - soll) < 1e-3 * soll and m.vol_dazu < 1e-6 and m.teile_weg == 1
    m = vv.berechne(platte(10.5), platte(10.0))
    assert abs(m.vol_dazu - soll) < 1e-3 * soll and m.vol_weg < 1e-6
    selbst = vv.berechne(platte(10.0), platte(10.0))
    assert selbst.dazu is None and selbst.weg is None


def test_materialvergleich_im_fenster(fenster):
    from tests.conftest import pfad
    f = fenster
    f.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    f.starte_vergleich({"alt": pfad("nist_ctc_01_asme1_ap242-e1.stp"), "neu": pfad("varianten/ctc01_pmi.stp"),
                        "toleranz": 0.01, "suchweite": 2.0}, warten=True)
    f.aenderungen.material_an.blockSignals(True)
    f.aenderungen.material_an.setChecked(True)
    f.aenderungen.material_an.blockSignals(False)
    f.zeige_material(True, warten=True)
    assert getattr(f.vergleich, "material", None) is not None
    f.zeige_material(False)
    assert f.ansicht.material is None
    f.beende_vergleich()


def test_verschobene_bohrung_erkannt():
    from types import SimpleNamespace
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.kern import vergleich
    from programm.kern.ausrichten import Ausrichtung
    from programm.kern.laden import StepModell, _alle_flaechen
    import numpy as np

    def modell(x):
        box = BRepPrimAPI_MakeBox(100.0, 60.0, 20.0).Shape()
        form = BRepAlgoAPI_Cut(box, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 30, -1), gp_Dir(0, 0, 1)), 5.0,
                                                               22.0).Shape()).Shape()
        m = StepModell("x.stp", None, None, form, _alle_flaechen(form))
        m._baue_index()
        return SimpleNamespace(modell=m, pmi=[], pfad="x.stp")
    alt, neu = modell(30.0), modell(42.0)
    v = vergleich.vergleiche(alt, neu, 0.01, 2.0, Ausrichtung(np.eye(4), "gleich", 0.0, 1.0))
    versch = [a for a in v.aenderungen if a.status == vergleich.VERSCHOBEN]
    assert len(versch) == 1 and "+12.000" in versch[0].beschreibung
    assert not any(a.status in ("neu", "entfernt") for a in v.aenderungen if a.kategorie == "geometrie")


def test_baugruppenvergleich(fenster):
    from programm.kern import vergleich_baugruppe as vb
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    a, b = lade_alles(pfad("baugruppe.stp")), lade_alles(pfad("baugruppe_b.stp"))
    erg = {(x.status, x.name) for x in vb.vergleiche(a.baum, b.baum)}
    assert erg == {(vb.GEAENDERT, "Deckel"), (vb.VERSCHOBEN, "Winkel"), (vb.ENTFERNT, "Schraube M6x25"),
                   (vb.NEU, "Stift 4x15")}
    assert vb.vergleiche(a.baum, a.baum) == []
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f.starte_vergleich({"alt": pfad("baugruppe.stp"), "neu": pfad("baugruppe_b.stp"), "toleranz": 0.01,
                        "suchweite": 2.0}, warten=True)
    bg = [x for x in f.vergleich.aenderungen if x.kategorie == "baugruppe"]
    assert len(bg) == 4 and any("dX +10.000" in x.beschreibung for x in bg)
    f.aenderungen.filter.setCurrentIndex(f.aenderungen.filter.findData("baugruppe"))
    sichtbar = [z for z in range(f.aenderungen.tabelle.rowCount()) if not f.aenderungen.tabelle.isRowHidden(z)]
    assert len(sichtbar) == 4
    f.beende_vergleich()


def test_pmi_darstellung_verschoben():
    import copy
    from types import SimpleNamespace
    import numpy as np
    from programm.kern import vergleich, vergleich_pmi
    from programm.kern.ausrichten import Ausrichtung
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    e = lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    neu_grafik = copy.deepcopy(e.grafik)
    ziel = next(g for g in neu_grafik.values() if g.linien and g.pmi_ids and not g.erzeugt)
    ziel.linien = [l + np.array([5.0, 0, 0]) for l in ziel.linien]  # Beschriftung 5 mm verschoben
    ziel.dreiecke = [(p + np.array([5.0, 0, 0]), t) for p, t in ziel.dreiecke]
    alt = SimpleNamespace(grafik=e.grafik)
    neu = SimpleNamespace(grafik=neu_grafik)
    liste = vergleich_pmi.vergleiche_pmi(e.pmi, e.pmi)
    gefunden = vergleich._grafik_aenderungen(liste, alt, neu, Ausrichtung(np.eye(4), "gleich", 0, 1), 0.01)
    assert gefunden and all(a.status == vergleich.GRAFIK for a in gefunden)
    assert any("dX +5.00" in a.beschreibung for a in gefunden)
    assert vergleich._grafik_aenderungen(liste, alt, alt, Ausrichtung(np.eye(4), "gleich", 0, 1), 0.01) == []


def test_vergleich_netz_gegen_cad(fenster):
    """Scan-/Netzvergleich: STL des Modells gegen das CAD-Modell (Ausrichtung, Farbkarte ohne Absturz)."""
    from tests.conftest import pfad
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    f.starte_vergleich({"alt": pfad("baugruppe.stp"), "neu": pfad("formate/baugruppe.stl"), "toleranz": 0.05,
                        "suchweite": 2.0}, warten=True)
    v = f.vergleich
    assert v is not None and v.ausrichtung.methode == "gleich"
    f.aenderungen.karte_an.blockSignals(True)
    f.aenderungen.karte_an.setChecked(True)
    f.aenderungen.karte_an.blockSignals(False)
    f.zeige_farbkarte(True, warten=True)
    lo, hi = v.karte.bereich()
    assert abs(lo) < 0.5 and abs(hi) < 0.5  # Netz liegt (bis auf Sehnenfehler/Exemplare) auf dem CAD
    f.beende_vergleich()


def test_hinweise_ueber_text_verglichen():
    from programm.kern import vergleich_pmi as vp
    from programm.kern.pmi import HINWEIS, Pmi
    alt = [Pmi(HINWEIS, "Note", "Text.1", nur_grafik_text="ALL FILLETS R2", semantisch=False),
           Pmi(HINWEIS, "Note", "Text.2", nur_grafik_text="BREAK SHARP EDGES 0.5", semantisch=False)]
    neu = [Pmi(HINWEIS, "Note", "Text.9", nur_grafik_text="BREAK SHARP EDGES 0.5", semantisch=False),
           Pmi(HINWEIS, "Note", "Text.1", nur_grafik_text="ALL FILLETS R3", semantisch=False)]
    erg = {(x.status, (x.alt or x.neu).nur_grafik_text) for x in vp.vergleiche_pmi(alt, neu)}
    assert (vp.GEAENDERT, "ALL FILLETS R2") in erg  # gleicher Name, Text geaendert
    stat = {x.status for x in vp.vergleiche_pmi(alt, neu) if (x.alt and "BREAK" in x.alt.nur_grafik_text)}
    assert stat <= {vp.GLEICH, vp.GEAENDERT} and vp.NEU not in stat  # gleicher Text -> zugeordnet
