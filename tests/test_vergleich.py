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
    # Spalten der Aenderungstabelle: Merkmal, alt, neu, Delta, Tendenz der Toleranzbreite
    werte = sorted(vergleich.spalten(a) for a in v.aenderungen)
    assert werte == [("Toleranzwert", "0.2", "0.1", "-0.1", "enger"), ("Toleranzwert", "0.75", "0.5", "-0.25", "enger"),
                     ("unteres Abmaß/Mindestmaß", "-0.2", "-0.3", "-0.1", "weiter")]
    from programm.kern import pmi_bericht
    csv = pmi_bericht.vergleich_csv(v)
    assert "Tendenz" in csv and "enger" in csv


def test_nur_geometrie_geaendert(alt):
    from programm.kern import vergleich
    v = vergleich.vergleiche(alt, _variante("ctc01_geo"))
    arten = sorted((a.kategorie, a.status) for a in v.aenderungen)
    assert arten == [("geometrie", "geaendert"), ("pmi", "geometrie")]
    geo = next(a for a in v.aenderungen if a.kategorie == "geometrie")
    assert len(geo.flaechen_neu) == 2 and "0.500" in geo.beschreibung
    assert vergleich.spalten(geo)[0] == "größte Abweichung" and vergleich.spalten(geo)[3] == "0.500 mm"


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
    assert kopf.startswith("No;Category;Status;Title;Description;Characteristic;Old value;New value;Δ;Tendency;Old;New")
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
    # Status je Instanz: von vier gleichen Schrauben ist eine entfernt (gemeinsame Flaechen allein zeigen das nicht)
    alt = f.vergleich.alt.modell
    entfernt = {alt.flaechen_index(x) for x in f.vergleich.geo.entfernt_a}
    schraube = next(k for k in f.vergleich.alt.baum.blaetter() if k.name.startswith("Schraube"))
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    ex, flaechen = TopExp_Explorer(schraube.form, TopAbs_FACE), set()
    while ex.More():
        flaechen.add(alt.flaechen_index(ex.Current()))
        ex.Next()
    assert entfernt & flaechen
    assert not {i for i, st in f.vergleich.geo.status_a.items() if st == "entfernt"} & flaechen
    assert len(f.ansicht.vergleich_instanzen) == len(f.vergleich.geo.instanzen_b) > len(f.vergleich.geo.status_b)
    f.beende_vergleich()
    assert f.ansicht.vergleich_instanzen == {}


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


def _platte_mit_l_tasche(trsf):
    """Platte mit einer L-foermigen (nicht spiegelsymmetrischen) Tasche, Tasche mit 'trsf' gelegt."""
    from types import SimpleNamespace
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt
    from programm.kern.laden import StepModell, _alle_flaechen
    platte = BRepPrimAPI_MakeBox(gp_Pnt(-60, -60, 0), 120.0, 120.0, 20.0).Shape()
    l_form = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 10), 30.0, 8.0, 11.0).Shape(),
                              BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 10), 8.0, 18.0, 11.0).Shape()).Shape()
    l_form = BRepBuilderAPI_Transform(l_form, trsf, True).Shape()
    form = BRepAlgoAPI_Cut(platte, l_form).Shape()
    m = StepModell("x.stp", None, None, form, _alle_flaechen(form))
    m._baue_index()
    return SimpleNamespace(modell=m, pmi=[], pfad="x.stp")


def test_gedrehte_und_gespiegelte_tasche():
    import numpy as np
    from OCC.Core.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from programm.kern import vergleich
    from programm.kern.ausrichten import Ausrichtung
    gleich = Ausrichtung(np.eye(4), "gleich", 0.0, 1.0)
    alt = _platte_mit_l_tasche(gp_Trsf())
    dreh = gp_Trsf()
    dreh.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), np.radians(30))
    schieb = gp_Trsf()
    schieb.SetTranslation(gp_Vec(-25, -30, 0))
    neu = _platte_mit_l_tasche(schieb.Multiplied(dreh))
    v = vergleich.vergleiche(alt, neu, 0.01, 2.0, gleich)
    lage = [a for a in v.aenderungen if a.status == vergleich.VERSCHOBEN]
    assert len(lage) == 1 and "gedreht um +30.00°" in lage[0].beschreibung, [a.beschreibung for a in v.aenderungen]
    spiegel = gp_Trsf()
    spiegel.SetMirror(gp_Ax2(gp_Pnt(-5, 0, 0), gp_Dir(1, 0, 0)))  # Spiegelung an x = -5
    neu = _platte_mit_l_tasche(spiegel)
    v = vergleich.vergleiche(alt, neu, 0.01, 2.0, gleich)
    lage = [a for a in v.aenderungen if a.status == vergleich.VERSCHOBEN]
    assert len(lage) == 1 and lage[0].titel == "Geometrie gespiegelt", [a.titel for a in v.aenderungen]
    assert "(+1.000, +0.000, +0.000) bei -5.000" in lage[0].beschreibung


def test_vergleich_je_instanz():
    """Zwei Instanzen desselben Teils: nur die zweite ist verschoben -> wird erkannt (Flaechen je Instanz)."""
    from types import SimpleNamespace
    import numpy as np
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from programm.kern import vergleich_geo
    from programm.kern.ausrichten import Ausrichtung
    from programm.kern.laden import StepModell, _alle_flaechen
    teil = BRepPrimAPI_MakeBox(20.0, 10.0, 5.0).Shape()

    def modell(x2):
        comp = TopoDS_Compound()
        bb = BRep_Builder()
        bb.MakeCompound(comp)
        for x in (0.0, x2):
            t = gp_Trsf()
            t.SetTranslation(gp_Vec(x, 0, 0))
            bb.Add(comp, teil.Located(TopLoc_Location(t)))
        m = StepModell("x.stp", None, None, comp, _alle_flaechen(comp))
        m._baue_index()
        return m
    alt, neu = modell(50.0), modell(53.0)
    assert len(alt.flaechen) == 6  # Instanzen teilen sich die Flaechen
    geo = vergleich_geo.vergleiche(alt, neu, Ausrichtung(np.eye(4), "gleich", 0.0, 1.0), 0.01, 4000, 5.0)
    assert any(s != vergleich_geo.GLEICH for s in geo.status_b.values())
    # Status je Instanz: die erste Instanz ist gleich, nur die verschobene zweite ist geaendert
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    st = {0: set(), 1: set()}
    ex = TopExp_Explorer(neu.form, TopAbs_FACE)
    while ex.More():
        f = ex.Current()
        ex.Next()
        x = f.Location().Transformation().TranslationPart().X()
        st[int(x > 1)].add(geo.instanzen_b[vergleich_geo.instanz_schluessel(neu.flaechen_index(f), f)])
    assert st[0] == {vergleich_geo.GLEICH} and vergleich_geo.GLEICH not in st[1]
    assert geo.entfernt_a is not None and len(geo.entfernt_a) <= 6
    geo = vergleich_geo.vergleiche(alt, modell(50.0), Ausrichtung(np.eye(4), "gleich", 0.0, 1.0), 0.01, 4000, 5.0)
    assert all(s == vergleich_geo.GLEICH for s in geo.status_b.values())
    # Aenderungsliste je Instanz: nur die zweite Instanz betroffen -> ein Eintrag mit ihrem Blatt
    from programm.kern import vergleich as kv
    from programm.kern.baum import Knoten

    def mit_baum(m):
        from OCC.Core.TopoDS import TopoDS_Iterator
        blaetter = []
        it = TopoDS_Iterator(m.form)
        n = 0
        while it.More():
            n += 1
            blaetter.append(Knoten(f"Teil.{n}", it.Value().Moved(m.form.Location()), nummer=n))
            it.Next()
        return SimpleNamespace(modell=m, baum=Knoten("Wurzel", m.form, blaetter, True))
    neu_b = mit_baum(neu)
    geo = vergleich_geo.vergleiche(alt, neu, Ausrichtung(np.eye(4), "gleich", 0.0, 1.0), 0.01, 4000, 5.0)
    nachbarn = vergleich_geo._nachbarn(neu.flaechen, neu.flaechen_index)
    liste = kv._je_instanz(kv._geo_aenderungen(geo, nachbarn, nachbarn), neu_b, geo)
    geaendert = [a for a in liste if a.status == vergleich_geo.GEAENDERT]
    assert geaendert and all(a.knoten == 2 and a.titel.endswith("Teil.2") for a in geaendert)
    # beide Instanzen gleich geaendert (Teil selbst verschoben): ein Eintrag "an allen 2 Instanzen"
    alle = mit_baum(modell(50.0))
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(0, 0, 0.5))
    alle.modell.form.Location(TopLoc_Location(t))
    alle.modell._baue_index()
    geo = vergleich_geo.vergleiche(alt, alle.modell, Ausrichtung(np.eye(4), "gleich", 0.0, 1.0), 0.01, 4000, 5.0)
    liste = kv._je_instanz(kv._geo_aenderungen(geo, nachbarn, nachbarn), mit_baum(alle.modell), geo)
    assert vergleich_geo.GLEICH not in geo.instanzen_b.values()
    assert any("2" in a.beschreibung and not a.knoten for a in liste if a.status == vergleich_geo.GEAENDERT)


@pytest.mark.langsam
def test_scan_gegen_toleranzen():
    """Erzeugte Scans (werkzeuge/testmodelle.py): sauberer Scan i. O., Scan mit Welligkeit verletzt die Ebenheit."""
    from programm.kern import ausrichten, scanpruefung as sp
    from programm.kern.laden import lade_modell
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    cad = lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    for name, flach in (("ctc01_scan", sp.OK), ("ctc01_scan_fehler", sp.NOK)):
        scan = lade_modell(pfad(f"varianten/{name}.ply"))
        grob = ausrichten.richte_aus(cad.modell.flaechen, scan.flaechen, 0.05)
        assert grob.methode == "bestpassung"
        m = sp.feinausrichten(cad.modell, sp.scan_punkte(scan, None), grob.matrix)
        z = sp.zuordnen(cad.modell, sp.scan_punkte(scan, m), nur=sp.pmi_flaechen(cad.pmi))
        erg = {e.pmi.nummer: e for e in sp.bewerte(cad.pmi, cad.modell, z)}
        ebenheit = next(e for e in erg.values() if e.pmi.typ == "Flatness")
        assert ebenheit.status == flach
        # Masse am Durchmesser: Istmass im Rauschen (5 um) um das Nennmass
        for e in erg.values():
            if e.pmi.typ == "Size_Diameter" and e.ist is not None:
                assert abs(e.ist - abs(e.pmi.nennwert)) < 0.01, (name, e.pmi.wert_text(), e.ist)
        assert not any(e.status == sp.NOK for e in erg.values() if e.pmi.typ != "Flatness"), name


def test_neue_varianten_vergleich():
    """Gleiche Geometrie mit anderen PMI; minimal verschobene Bohrung mit gleichen PMI."""
    import numpy as np
    from programm.kern import vergleich_geo, vergleich_pmi
    from programm.kern.ausrichten import Ausrichtung
    from programm.ui.lader import lade_alles
    a = lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    b = _variante("ctc01_pmi_andere")
    geo = vergleich_geo.vergleiche(a.modell, b.modell, Ausrichtung(np.eye(4), "gleich", 0, 1), 0.01, 4000, 2.0)
    assert all(s == vergleich_geo.GLEICH for s in geo.status_b.values())
    liste = vergleich_pmi.vergleiche_pmi(a.pmi, b.pmi, geo.zuordnung, zuordnung_ab=geo.zuordnung_ab)
    geaendert = [x for x in liste if x.status != vergleich_pmi.GLEICH]
    assert len(geaendert) >= 3
    assert any(x.alt is not None and x.alt.typ == "Flatness" and x.status == vergleich_pmi.ENTFALLEN for x in liste)
    assert any(x.neu is not None and x.neu.typ == "Straightness" and x.status == vergleich_pmi.NEU for x in liste)
    c = _variante("ctc01_geo_klein")
    geo = vergleich_geo.vergleiche(a.modell, c.modell, Ausrichtung(np.eye(4), "gleich", 0, 1), 0.01, 4000, 2.0)
    anders = [i for i, s in geo.status_b.items() if s != vergleich_geo.GLEICH]
    assert 1 <= len(anders) <= 6  # nur die Bohrung (und ihre Randflaechen)
    assert len(c.pmi) == len(a.pmi)


def test_deutliche_aenderung_geometrie_und_pmi():
    """Beispiel "Vergleich": versetzte Bohrung (verschoben, ihr Mass folgt), gefuellte Bohrung (entfernt), Fase
    (neue Kegel in der Aenderung der Oberseite); PMI: Wert, Bezugsreihenfolge, entfallen, neu - und sonst nichts."""
    from programm.kern import vergleich
    from programm.ui.lader import lade_alles
    a = lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    b = _variante("ctc01_geo_pmi_deutlich")
    v = vergleich.vergleiche(a, b)
    assert v.ausrichtung.methode == "gleich"
    geo = {(x.status, len(x.flaechen_neu), len(x.flaechen_alt)): x for x in v.aenderungen if x.kategorie == "geometrie"}
    versetzt = geo[(vergleich.VERSCHOBEN, 2, 2)]
    assert "dX +15.000  dY +0.000  dZ +0.000" in versetzt.beschreibung
    assert (vergleich.ENTFERNT, 0, 2) in geo  # gefuellte Bohrung
    kegel = {i for i, f in enumerate(b.modell.flaechen) if _flaechentyp(f) == "kegel"}
    fase = [x for x in v.aenderungen if x.kategorie == "geometrie" and x.status == vergleich.GEAENDERT
            and x.flaechen_neu & kegel]
    assert len(fase) == 1 and len(fase[0].flaechen_neu & kegel) == 2  # beide Kegel der Fase
    assert len([x for x in v.aenderungen if x.kategorie == "geometrie"]) == 4  # keine Randartefakte
    pmi = {(x.status, (x.pmi_alt or x.pmi_neu).typ): x for x in v.aenderungen if x.kategorie == "pmi"}
    assert pmi[("geaendert", "Position")].pmi_alt is not None
    werte = sorted(vergleich.spalten(x)[:3] for x in v.aenderungen if x.kategorie == "pmi" and x.status == "geaendert")
    assert werte == [("Bezüge", "A|B|C", "A|C|B"), ("Toleranzwert", "0.75", "0.5")]
    assert ("entfallen", "Perpendicularity") in pmi and ("neu", "Position") in pmi
    mass = pmi[(vergleich.VERSCHOBEN, "Size_Diameter")]  # Mass der versetzten Bohrung folgt ihr
    assert mass.pmi_neu.nennwert == 25.0 and mass.flaechen_neu == versetzt.flaechen_neu
    assert pmi[("neu", "Position")].flaechen_neu == versetzt.flaechen_neu
    assert {x.status for x in v.aenderungen if x.kategorie == "pmi"} == {"geaendert", "entfallen", "neu",
                                                                       vergleich.VERSCHOBEN, "geometrie"}


def _flaechentyp(f) -> str:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone
    return "kegel" if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cone else ""


@pytest.mark.langsam
def test_scanpruefung_stufe2(tmp_path):
    """Winkel- und Laengenmasse, Ausrichtung am Bezugssystem A|B|C, Punktwolke ohne Dreiecke."""
    import numpy as np
    from programm.kern import ausrichten, punktwolke, scanpruefung as sp
    from programm.kern.laden import lade_modell, lies_ply
    from programm.ui.lader import lade_alles
    cad = lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    assert sp.bezugssysteme(cad.pmi)[0] == ("A", "B", "C")
    assert sp.bezug_flaechen(cad.pmi, "A") == {97} and len(sp.bezug_flaechen(cad.pmi, "B")) == 2
    scan = lade_modell(pfad("varianten/ctc01_scan.ply"))
    roh = sp.scan_punkte(scan, None)
    grob = ausrichten.richte_aus(cad.modell.flaechen, scan.flaechen, 0.05)
    best = sp.feinausrichten(cad.modell, roh, grob.matrix)
    m = sp.richte_nach_bezug(cad.modell, roh, best, [sp.bezug_flaechen(cad.pmi, b) for b in "ABC"])
    nur = sp.pmi_flaechen(cad.pmi)
    z = sp.zuordnen(cad.modell, sp.scan_punkte(scan, m), nur=nur)
    a = np.isin(z.flaeche, [97]) & (np.abs(z.abstand) < 0.5)
    assert abs(float(z.abstand[a].mean())) < 0.002  # Primaerbezug liegt im Mittel auf
    assert np.abs(m[:3, 3] - best[:3, 3]).max() < 0.01  # sauberer Scan: Bezug und Bestpassung fast gleich
    # kleine Winkelflaechen (15, 17) haben nur 4-8 Scanknoten: Winkel mit der Bestpassung pruefen
    zb = sp.zuordnen(cad.modell, sp.scan_punkte(scan, best), nur=nur)
    winkel = next(e for e in sp.bewerte(cad.pmi, cad.modell, zb) if e.pmi.typ == "Location_Angular")
    assert winkel.status == sp.OK and abs(winkel.ist - 60.0) < 0.05
    # Laengenmasse (FTC-10, Punkte aus dem CAD-Netz: Istmass = Nennmass, auch bei Mustern)
    ftc = lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    p = np.vstack([q for q, _ in ausrichten.tesselliere(ftc.modell.flaechen, 0.2) if len(q)])
    erg = {e.pmi.nummer: e for e in sp.bewerte(ftc.pmi, ftc.modell,
                                               sp.zuordnen(ftc.modell, p, nur={i for n in (6, 8, 15, 16) for q in ftc.pmi
                                                                              if q.nummer == n for i in q.flaechen}))}
    for nr, soll in ((6, 15.0), (8, 10.0), (15, 2.0)):
        assert erg[nr].status == sp.OK and abs(erg[nr].ist - soll) < 1e-3, nr
    assert erg[16].status == sp.OFFEN  # nur eine Flaeche verknuepft
    # Punktwolke als Text (Semikolon, Dezimalkomma, Kopfzeile) und PLY nur mit Punkten
    pts, _ = lies_ply(pfad("varianten/ctc01_scan.ply"))
    datei = tmp_path / "wolke.csv"
    zeilen = ["x;y;z"] + [f"{x:.5f};{y:.5f};{w:.5f}".replace(".", ",") for x, y, w in pts[::10]]
    datei.write_text("\n".join(zeilen), encoding="utf-8")
    assert punktwolke.ist_punktwolke(str(datei)) and not punktwolke.ist_punktwolke(pfad("varianten/ctc01_scan.ply"))
    wolke = punktwolke.lies_punkte(str(datei))
    assert len(wolke) == len(pts[::10]) and np.allclose(wolke[0], pts[0], atol=1e-4)
    g = ausrichten.richte_aus(cad.modell.flaechen, None, 0.05, punkte_b=wolke)
    assert g.methode == "bestpassung" and g.anteil > 0.8


def test_vergleichsmodi(fenster):
    """Alt, Neu, Ueberlagern, Nebeneinander mit gekoppelter Kamera, Blinken mit Leertaste; Baum folgt dem Modus."""
    f = fenster
    f.starte_vergleich({"alt": pfad("baugruppe.stp"), "neu": pfad("baugruppe_b.stp"), "toleranz": 0.01,
                        "suchweite": 2.0}, warten=True)
    v = f.vergleich
    assert f.modus_leiste.isVisibleTo(f) and f.ansicht_alt is None  # zweite Ansicht erst bei Bedarf
    f.setze_vergleichsmodus("nebeneinander")
    alt = f.ansicht_alt
    assert alt is not None and alt.isVisibleTo(f) and f.ansicht.isVisibleTo(f) and alt.szene.modell is v.alt.modell
    assert alt.vergleich_status == v.geo.status_a
    # Kamera: die zuletzt bewegte Ansicht gibt die Lage vor
    f._kameras_koppeln()
    k = ((1.0, 2.0, 3.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 50.0)
    f.ansicht.setze_kamera_daten(k)
    f._kameras_koppeln()
    assert alt.kamera_daten() == k
    k2 = ((5.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 20.0)
    alt.setze_kamera_daten(k2)
    f._kameras_koppeln()
    assert f.ansicht.kamera_daten() == k2
    f.setze_vergleichsmodus("alt")
    assert alt.isVisibleTo(f) and not f.ansicht.isVisibleTo(f)
    assert f._baum_ansicht() is alt and f.baum_alt.isVisibleTo(f)  # beide Strukturen, auch im Modus Alt
    f._alt_neu_wechseln()  # Leertaste: Alt -> Neu
    assert f._vergleichsmodus == "neu" and f.ansicht.isVisibleTo(f) and not alt.isVisibleTo(f)
    f.modus_leiste.hervor.setChecked(False)
    assert f.ansicht.vergleich_status == {}  # ohne Hervorhebung neutral
    f.modus_leiste.hervor.setChecked(True)
    f.setze_vergleichsmodus("ueberlagern")
    assert f.ansicht.ueberlagerung is v.alt.modell.form
    f.setze_vergleichsmodus("blinken")
    assert f._blink.isActive() and f.modus_leiste.blink.isVisibleTo(f)
    sichtbar = alt.isVisibleTo(f)
    f._blink_schritt()
    assert alt.isVisibleTo(f) != sichtbar and f.ansicht.isVisibleTo(f) == sichtbar
    f._alt_neu_wechseln()  # Leertaste im Blinken: anhalten und von Hand wechseln
    assert not f._blink.isActive() and f.modus_leiste.pause_knopf.text().startswith("▶")
    f.setze_vergleichsmodus("vergleich")
    assert f.ansicht.ueberlagerung is None and not alt.isVisibleTo(f) and not f._kopplung.isActive()
    f.setze_vergleichsmodus("nebeneinander")  # beide Strukturen untereinander, die alte mit Status
    assert f.baum_alt.isVisibleTo(f) and f.baum_alt.baum.topLevelItem(0) is not None
    texte = []
    def gehe(it):
        texte.append(it.text(0))
        for i in range(it.childCount()):
            gehe(it.child(i))
    gehe(f.baum_alt.baum.topLevelItem(0))
    assert any(t.startswith("● ") and "Schraube" in t for t in texte)  # entfallene Schraube markiert
    schraube = next(k for k in f.vergleich.alt.baum.blaetter() if "Schraube" in k.name)
    f.baum_alt.sichtbar_geaendert.emit({schraube.nummer}, False)
    assert schraube.nummer in f.ansicht_alt.versteckt and schraube.nummer not in f.ansicht.versteckt
    f.setze_vergleichsmodus("neu")
    assert f.baum_alt.isVisibleTo(f)  # im Vergleich bleiben beide Strukturen sichtbar
    f.beende_vergleich()
    assert not f.modus_leiste.isVisibleTo(f) and f.dock_baum.windowTitle() in ("Struktur", "Structure")
    assert not f.baum_alt.isVisibleTo(f)


def test_aenderung_einer_instanz_zeigen(fenster):
    """Aenderung nur an einer Instanz: Ausschnitt auf diese Instanz, im Baum markiert."""
    import copy
    f = fenster
    f.starte_vergleich({"alt": pfad("baugruppe.stp"), "neu": pfad("baugruppe_b.stp"), "toleranz": 0.01,
                        "suchweite": 2.0}, warten=True)
    deckel = next(k for k in f.vergleich.neu.baum.blaetter() if k.name == "Deckel")
    a = copy.copy(next(x for x in f.vergleich.aenderungen if x.kategorie == "geometrie"))
    a.knoten = deckel.nummer
    f._aenderung_gewaehlt(a)
    assert f.ansicht.letzter_zoom[1] == 1
    from PySide6 import QtCore
    assert f.baum.baum.currentItem().data(0, QtCore.Qt.ItemDataRole.UserRole) is deckel


def test_baum_mit_teilestatus(fenster):
    """Vergleich der Testbaugruppe: Deckel geaendert, Stift neu; im Modus Alt die entfallene Schraube entfernt."""
    from programm.kern.vergleich_geo import teil_status
    f = fenster
    f.starte_vergleich({"alt": pfad("baugruppe.stp"), "neu": pfad("baugruppe_b.stp"), "toleranz": 0.01,
                        "suchweite": 2.0}, warten=True)
    v = f.vergleich
    neu = teil_status(v.neu.baum, v.neu.modell, v.geo.status_b, v.geo.instanzen_b)
    namen = {k.nummer: k.name for k in v.neu.baum.blaetter()}
    nach_name = {namen[n]: s for n, s in neu.items()}
    assert nach_name["Deckel"] == "geaendert"  # geometrisch; der neue Stift teilt eine Ebene mit dem alten Deckel
    status = f._teil_status(v, False)  # mit Baugruppenvergleich: Stift neu
    assert {namen[n]: s for n, s in status.items()}["Stift 4x15"] == "neu"
    assert "entfernt" in f._teil_status(v, True).values()

    def texte(it):
        yield it.text(0), it.toolTip(0)
        for i in range(it.childCount()):
            yield from texte(it.child(i))
    eintraege = list(texte(f.baum.baum.topLevelItem(0)))
    assert any(t.startswith("● Stift") and tip in ("neu", "new") for t, tip in eintraege)
    assert eintraege[0][0].endswith("•")  # Wurzel: enthaelt Aenderungen
    f.setze_vergleichsmodus("alt")  # der alte Stand steht immer in der zweiten Struktur darunter
    eintraege = list(texte(f.baum_alt.baum.topLevelItem(0)))
    assert any(tip in ("entfernt", "removed") for _, tip in eintraege)
    f.beende_vergleich()
    assert not any(t.startswith("●") for t, _ in texte(f.baum.baum.topLevelItem(0)))


def test_scan_rundheit_und_rundlauf_je_querschnitt():
    """Kegelig gemessener Zapfen (Radius aendert sich 0,05 mm ueber die Laenge, je Schnitt rund): Rundheit 0,02 ist
    je Querschnitt erfuellt (flaechig waere die Spannweite 0,05); eine Unrundheit 0,03 in einem Schnitt nicht."""
    from types import SimpleNamespace
    import numpy as np
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import scanpruefung as sp, toleranzzone as tz
    from programm.kern.pmi import TOLERANZ, Pmi
    ex = TopExp_Explorer(BRepPrimAPI_MakeCylinder(10.0, 30.0).Shape(), TopAbs_FACE)
    flaechen = []
    while ex.More():
        flaechen.append(ex.Current())
        ex.Next()
    mantel = next(i for i, f in enumerate(flaechen) if tz._achsen([f]))
    modell = SimpleNamespace(flaechen=flaechen, flaechen_index=lambda f: next(
        (i for i, g in enumerate(flaechen) if g.IsSame(f)), None))
    rng = np.random.default_rng(2)
    w, h = rng.uniform(0, 2 * np.pi, 6000), rng.uniform(0.5, 29.5, 6000)
    d = 0.05 * h / 30  # kegelig, je Schnitt rund
    punkte = np.column_stack([(10 + d) * np.cos(w), (10 + d) * np.sin(w), h])
    z = sp.Zuordnung(punkte, d, np.full(len(d), mantel))
    rund = Pmi(TOLERANZ, "CircularityOrRoundness", wert=0.02, flaechen={mantel})
    e = sp.bewerte([rund], modell, z)[0]
    assert e.status == sp.OK and e.ist < 0.01 and "Querschnitt" in e.text
    eben = Pmi(TOLERANZ, "Cylindricity", wert=0.02, flaechen={mantel})
    assert sp.bewerte([eben], modell, z)[0].status == sp.NOK  # Zylinderform sieht die Kegeligkeit
    unrund = d + np.where(h > 25, 0.015 * np.cos(2 * w), 0.0)  # Oval im letzten Schnitt: Spannweite 0,03
    z2 = sp.Zuordnung(punkte, unrund, z.flaeche)
    e = sp.bewerte([rund], modell, z2)[0]
    assert e.status == sp.NOK and e.ist > 0.025 and "2" in e.text
    lauf = Pmi(TOLERANZ, "CircularRunout", wert=0.02, flaechen={mantel})
    assert sp.bewerte([lauf], modell, z)[0].status == sp.OK  # je Schnitt konstanter Abstand


def test_scan_linienprofil_je_schnitt():
    """Linienprofil ohne Bezug je Schnitt: Kegeligkeit 0,05 ueber die Laenge stoert je Querschnitt nicht (Spannweite
    je Schnitt klein); mit LE (Laengsschnitte) zaehlt sie dagegen - eine Mantellinie ist dann schraeg."""
    from types import SimpleNamespace
    import numpy as np
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import scanpruefung as sp, toleranzzone as tz
    from programm.kern.pmi import TOLERANZ, Pmi
    ex = TopExp_Explorer(BRepPrimAPI_MakeCylinder(10.0, 30.0).Shape(), TopAbs_FACE)
    flaechen = []
    while ex.More():
        flaechen.append(ex.Current())
        ex.Next()
    mantel = next(i for i, f in enumerate(flaechen) if tz._achsen([f]))
    modell = SimpleNamespace(flaechen=flaechen)
    rng = np.random.default_rng(3)
    w, h = rng.uniform(0, 2 * np.pi, 8000), rng.uniform(0.5, 29.5, 8000)
    d = 0.05 * h / 30
    punkte = np.column_stack([(10 + d) * np.cos(w), (10 + d) * np.sin(w), h])
    z = sp.Zuordnung(punkte, d, np.full(len(d), mantel))
    quer = Pmi(TOLERANZ, "ProfileOfLine", wert=0.02, flaechen={mantel})
    e = sp.bewerte([quer], modell, z)[0]
    assert e.status == sp.OK and "Schnitte" in e.text
    laengs = Pmi(TOLERANZ, "ProfileOfLine", wert=0.02, flaechen={mantel}, modifikatoren=["Line_Element"])
    e = sp.bewerte([laengs], modell, z)[0]
    assert e.status == sp.NOK and "Längsschnitte" in e.text and e.ist > 0.04


def test_bezug_als_anlage_iso5459():
    """Bezugsebene aus einer welligen Oberseite mit einer Erhebung: Gauss-Ausgleich legt die Ebene in die Mitte, die
    Anlage nach ISO 5459 an die hoechsten Punkte (alle Punkte im Material, groesster Abstand minimal)."""
    from types import SimpleNamespace
    import numpy as np
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import scanpruefung as sp, verbindung as vb
    ex = TopExp_Explorer(BRepPrimAPI_MakeBox(40.0, 30.0, 10.0).Shape(), TopAbs_FACE)
    flaechen = []
    while ex.More():
        flaechen.append(ex.Current())
        ex.Next()
    oben = next(i for i, f in enumerate(flaechen) if (m := vb.merkmal(f)) and m[2][2] > 0.99)
    modell = SimpleNamespace(flaechen=flaechen)
    rng = np.random.default_rng(4)
    x, y = rng.uniform(1, 39, 3000), rng.uniform(1, 29, 3000)
    z = 10 + 0.01 * np.sin(x / 3) * np.cos(y / 4)
    z[np.hypot(x - 30, y - 20) < 2] += 0.03  # Erhebung
    punkte = np.column_stack([x, y, z])
    gauss = sp.richte_nach_bezug(modell, punkte, np.eye(4), [{oben}])
    anlage = sp.richte_nach_bezug(modell, punkte, np.eye(4), [{oben}], anlage=True)
    hoehe = lambda m: (punkte @ m[:3, :3].T + m[:3, 3])[:, 2] - 10  # noqa: E731
    assert abs(float(hoehe(gauss).mean())) < 2e-3
    h = hoehe(anlage)
    assert h.max() < 1e-4 and h.max() > -1e-4 and h.min() < -0.005  # an die hoechsten Punkte angelegt
