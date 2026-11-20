"""Reales CTC-01 mit unveraenderten grafischen PMI, aber ohne semantische Mass-, Toleranz- oder Bezugsdaten."""

from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from programm.kern import p21, pmi_step, step_schreiben
from programm.kern.pmi import Pmi
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_step_schreiben import _occt_darstellungen


@pytest.fixture(scope="module")
def grafische_datei(tmp_path_factory):
    quelle = Path(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    ursprung = lade_alles(str(quelle))
    d = ursprung.modell.datei
    # Alle semantischen Merkmale und ihre Bezugs-/Darstellungslinks entfernen.
    # Die transitive Rueckwaertssuche entfernt auch jede Entitaet, die dadurch ins Leere zeigen wuerde.
    typen = (*pmi_step.MASS_TYPEN, *pmi_step.TOL_ARTEN, "GEOMETRIC_TOLERANCE", "DATUM",
             "DATUM_FEATURE", "DATUM_TARGET", "DRAUGHTING_MODEL_ITEM_ASSOCIATION", p21.DMIA_PH)
    entfernen = {e.id for e in d.of_types_by_id(typen)}
    offen = list(entfernen)
    rueck = d.referrers()
    while offen:
        for n in rueck.get(offen.pop(), []):
            if n not in entfernen:
                entfernen.add(n)
                offen.append(n)
    statements = []
    for s in p21._statements(quelle.read_text(encoding="utf-8")):
        if not s.startswith("#") or int(s[1:s.index("=")]) not in entfernen:
            statements.append(s)
    datei = tmp_path_factory.mktemp("grafische_pmi") / "ctc_01_grafisch.stp"
    datei.write_text(";\n".join(statements) + ";\n", encoding="utf-8")
    rein = lade_alles(str(datei))
    assert len(rein.pmi) == len(rein.grafik) == 23
    assert not any(p.semantisch for p in rein.pmi) and not rein.modell.datei.of_types_by_id(typen)
    assert set(rein.modell.datei.referrers()) <= rein.modell.datei.entities.keys()
    assert rein.grafik.keys() == ursprung.grafik.keys()
    assert len(rein.modell.flaechen) == len(ursprung.modell.flaechen)
    return str(datei), ursprung, rein


def _pruefen(d, ref, f):
    # Der Pruefer liefert die Sollangaben des unveraenderten NIST-Referenzmodells.
    d.art.setCurrentIndex(d.art.findData(ref.art))
    d.typ.setCurrentIndex(d.typ.findData(ref.typ))
    assert d.typ.currentData() == ref.typ
    f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in sorted(ref.flaechen)])
    d._auswahl_uebernehmen()
    assert d.flaechen == ref.flaechen
    if ref.art == "bezug":
        d.felder["name"].setText(ref.name)
    elif ref.art == "mass":
        d.felder["nennwert"].setText(str(ref.nennwert))
        d.felder["grenzmass"].setChecked(ref.grenzmass)
        for name, w in (("oben", ref.oben), ("unten", ref.unten)):
            d.felder[name].setText("" if w is None else str(w))
    else:
        d.felder["wert"].setText(str(ref.wert))
        d.felder["bezuege"].setText(" ".join(b.name for b in ref.bezuege))
    assert not d.fehler()
    d._pruefen()


def test_grafisches_gesamtmodell_stapel_und_step_rundlauf(grafische_datei, fenster, tmp_path, app):
    datei, referenz, vorher = grafische_datei
    je_id = {p.step_id: p for p in referenz.pmi}
    soll = {}
    for nr, g in referenz.grafik.items():
        p, = (je_id[i] for i in g.pmi_ids if i in je_id)
        if p.art in ("toleranz", "bezug") or p.art == "mass" and p.nennwert is not None:
            soll[nr] = p
    assert Counter(p.art for p in soll.values()) == {"toleranz": 6, "bezug": 3, "mass": 8}
    f = fenster
    f.lade(datei, warten=True)
    f.aktionen["pmi_semantisieren"].trigger()
    besucht = set()
    for _ in vorher.grafik:
        app.processEvents()
        d = f._semantik_dialog
        nr = d.v.callout
        assert nr not in besucht
        besucht.add(nr)
        if nr in soll:
            _pruefen(d, soll[nr], f)
        else:
            d.done(2)  # Freitexte und Hilfsmasse ohne eigenstaendigen Nennwert
    assert besucht == set(vorher.grafik)
    assert {p.callout for p in f.erg.pmi if p.quelle == "eigen"} == set(soll)
    ziel = f.speichere_step_pmi(str(tmp_path / "mit_semantik.stp"), melden=False)
    bericht = f._step_bericht
    assert len(bericht.neu) == 17 and bericht.neu == bericht.repariert
    assert not bericht.uebersprungen and not bericht.dargestellt

    nachher = lade_alles(ziel)
    # Jede originale Entitaet ist unveraendert: Geometrie, Linien-/Dreiecksgrafik, Kamera, Modell und Sichtbarkeit.
    assert all(nachher.modell.datei.entities[i] == e for i, e in vorher.modell.datei.entities.items())
    assert nachher.grafik.keys() == vorher.grafik.keys()
    assert len(nachher.pmi) == 23 and sum(p.semantisch for p in nachher.pmi) == 17
    je_id = {p.step_id: p for p in nachher.pmi}
    for nr, g in nachher.grafik.items():
        sichtbar, = g.pmi_ids.intersection(je_id)
        neu = je_id[sichtbar]
        assert not g.erzeugt and g.fertig and not g.leer()
        if nr not in soll:
            assert neu.step_id == nr and not neu.semantisch
            continue
        s = soll[nr]
        assert neu.semantisch and neu.grafisch and (neu.art, neu.typ, neu.flaechen) == (s.art, s.typ, s.flaechen)
        assert neu.bezuege == s.bezuege
        if s.art == "bezug":
            assert neu.name == s.name
        elif s.art == "mass":
            assert neu.nennwert == pytest.approx(s.nennwert) and neu.grenzen() == pytest.approx(s.grenzen())
            assert neu.grenzmass == s.grenzmass
        else:
            assert neu.wert == pytest.approx(s.wert)
        for alt, neu_linie in zip(vorher.grafik[nr].linien, g.linien, strict=True):
            np.testing.assert_array_equal(neu_linie, alt)
    ansicht, = nachher.ansichten
    assert ansicht.name == vorher.ansichten[0].name
    assert set(ansicht.pmi_nummern) == {p.nummer for p in nachher.pmi}
    # Unabhaengiger XCAF-Import: nur freie Callouts und echte Masse in den Dimensionsdarstellungen.
    dimensionen, bezuege = _occt_darstellungen(ziel)
    assert set(dimensionen) == {g.name for n, g in vorher.grafik.items() if n not in soll or soll[n].art == "mass"}
    assert set(bezuege) == {vorher.grafik[n].name for n, p in soll.items() if p.art == "bezug"}


def test_ungueltige_callout_bindung_schreibt_keine_verwaiste_semantik(grafische_datei, tmp_path):
    datei, _, vorher = grafische_datei
    # Ein Bezug mit einer Produkt-ID als Callout darf keinen scheinbar verfuegbaren Bezug zuruecklassen.
    f = vorher.modell.step_zu_flaeche[861]
    produkt, *_ = vorher.modell.datei.of_type("PRODUCT")
    bezug = Pmi("bezug", typ="Datum", name="A", quelle="eigen", nummer=24, step_id=-1, flaechen={f},
                callout=produkt.id)
    ziel = str(tmp_path / "ungueltiger_verweis.stp")
    bericht = step_schreiben.schreibe(datei, ziel, [bezug], vorher.modell)
    assert [nr for nr, _, _ in bericht.uebersprungen] == [24] and not bericht.neu and not bericht.repariert
    gelesen = lade_alles(ziel)
    assert gelesen.modell.datei.entities == vorher.modell.datei.entities
    assert not any(p.semantisch for p in gelesen.pmi)


def test_lesbarer_step_text_und_modifikatoren_am_originalcallout(grafische_datei, tmp_path):
    from programm.kern.pmi_reparieren import vorschlag
    datei, _, _ = grafische_datei
    text = Path(datei).read_text(encoding="utf-8")
    alt = "#611=DRAUGHTING_CALLOUT('Flatness.1',(#519))"
    assert alt in text
    neu = """#90001=CARTESIAN_POINT('',(4.,8.,2.));
#90002=AXIS2_PLACEMENT_3D('',#90001,$,$);
#90003=PLANAR_EXTENT('',14.,2.);
#90004=DRAUGHTING_PRE_DEFINED_TEXT_FONT('ISO 3098-1 font A');
#90005=TEXT_LITERAL_WITH_EXTENT('','⌖ S⌀0.25Ⓕ',#90002,'baseline left',.RIGHT.,#90004,#90003);
#90006=ANNOTATION_TEXT_OCCURRENCE('',(#3461),#90005);
#611=DRAUGHTING_CALLOUT('Position',(#519,#90006))"""
    quelle = tmp_path / "textliteral.stp"
    quelle.write_text(text.replace(alt, neu), encoding="utf-8")
    erg = lade_alles(str(quelle))
    g = erg.grafik[611]
    assert g.linien and len(g.platzhalter) == 1
    ph = g.platzhalter[0]
    assert (ph.breite, ph.hoehe) == (14, 2)
    np.testing.assert_array_equal(ph.ursprung, (4., 8., 2.))
    p = vorschlag(next(p for p in erg.pmi if p.step_id == 611), g, erg.modell)
    assert p.typ == "Position" and p.wert == .25 and p.flaechen
    assert set(p.modifikatoren) == {"Free_State", "SphericalDiameter"}
    p.quelle, p.step_id, p.nummer = "eigen", -1, 24
    ziel = tmp_path / "textliteral_repariert.stp"
    assert step_schreiben.schreibe(str(quelle), str(ziel), [p], erg.modell).repariert == [24]
    gelesen = lade_alles(str(ziel))
    semantik, = [p for p in gelesen.pmi if p.semantisch]
    assert semantik.wert == .25 and set(semantik.modifikatoren) == set(p.modifikatoren)
    assert gelesen.grafik[611].pmi_ids == {semantik.step_id}
    assert gelesen.grafik[611].platzhalter[0].text == ph.text


def test_bereits_semantischer_callout_wird_nicht_erneut_belegt(grafische_datei, tmp_path):
    datei, _, vorher = grafische_datei
    f = vorher.modell.step_zu_flaeche[861]
    reparatur = Pmi("toleranz", typ="Flatness", wert=.2, quelle="eigen", nummer=24, step_id=-1,
                    flaechen={f}, callout=611)
    einmal = str(tmp_path / "einmal.stp")
    assert step_schreiben.schreibe(datei, einmal, [reparatur], vorher.modell).repariert == [24]
    geladen = lade_alles(einmal)
    nochmal = str(tmp_path / "nochmal.stp")
    bericht = step_schreiben.schreibe(einmal, nochmal, [reparatur], geladen.modell)
    assert [nr for nr, _, _ in bericht.uebersprungen] == [24] and not bericht.neu and not bericht.repariert
    assert lade_alles(nochmal).modell.datei.entities == geladen.modell.datei.entities


def test_gepacktes_grafikmodell_als_step_mit_semantik(grafische_datei, fenster, tmp_path):
    from zipfile import ZipFile
    datei, _, _ = grafische_datei
    quelle = tmp_path / "modell.stpz"
    with ZipFile(quelle, "w") as archiv:
        archiv.write(datei, "modell.stp")
    fenster.lade(str(quelle), warten=True)
    p = next(p for p in fenster.erg.pmi if p.step_id == 611)
    fenster._pmi_befehl("semantisch", p)
    d = fenster._semantik_dialog
    d.felder["wert"].setText("0,25")
    assert not d.fehler()
    d._pruefen()
    ziel = str(tmp_path / "mit_semantik.stp")
    assert fenster.speichere_step_pmi(ziel, melden=False) == ziel
    gelesen = lade_alles(ziel)
    semantik, = (p for p in gelesen.pmi if p.semantisch)
    assert semantik.wert == .25 and gelesen.grafik[611].pmi_ids == {semantik.step_id}


def test_ap203_originale_radialbemaszung_als_gepruefter_durchmesser(fenster, tmp_path):
    fenster.lade(pfad("nist_ctc_01_asme1_ap203.stp.gz"), warten=True)
    quelle = fenster.erg
    assert len(quelle.pmi) == 21 and all(not p.semantisch for p in quelle.pmi)
    assert len(quelle.ansichten[0].pmi_nummern) == 21
    p = next(p for p in quelle.pmi if p.step_id == 3410)
    fenster._pmi_befehl("semantisch", p)
    d = fenster._semantik_dialog
    assert d.flaechen == {quelle.modell.step_zu_flaeche[605]}
    d.typ.setCurrentIndex(d.typ.findData("Size_Diameter"))
    d.felder["nennwert"].setText("20")
    assert not d.fehler()
    d._pruefen()
    ziel = str(tmp_path / "radial_ap242.stp")
    assert fenster.speichere_step_pmi(ziel, melden=False) == ziel
    assert fenster._step_bericht.ap242_kopie
    neu = lade_alles(ziel)
    assert "AP242" in neu.modell.datei.schema
    assert len(neu.ansichten[0].pmi_nummern) == len(neu.pmi) == 21
    assert neu.grafik.keys() == quelle.grafik.keys()
    sem, = (p for p in neu.pmi if p.semantisch)
    assert sem.typ == "Size_Diameter" and sem.nennwert == 20
    assert sem.flaechen == {neu.modell.step_zu_flaeche[605]}
    assert sem.step_id in neu.grafik[3410].pmi_ids and sem.nummer in neu.ansichten[0].pmi_nummern


def test_massmodifikatoren_bleiben_am_einzelnen_mass(grafische_datei, tmp_path):
    datei, _, vorher = grafische_datei
    f = vorher.modell.step_zu_flaeche[861]
    daten = [(607, "Size_Radius", ["Hilfsmass", "ControlledRadius"]),
             (608, "Size_Diameter", ["Theoretisch"]),
             (609, "Size_Diameter", ["StatisticalTolerance", "Envelope"]),
             (610, "Size_Radius", ["ControlledRadius", "StatisticalTolerance"])]
    masse = [Pmi("mass", typ=typ, modifikatoren=mods, nennwert=5.+i, flaechen={f}, quelle="eigen",
                 callout=nr, nummer=24+i, step_id=-1-i) for i, (nr, typ, mods) in enumerate(daten)]
    ziel = str(tmp_path / "masszusatz.stp")
    bericht = step_schreiben.schreibe(datei, ziel, masse, vorher.modell)
    assert bericht.repariert == [p.nummer for p in masse] and not bericht.uebersprungen
    neu = lade_alles(ziel)
    je_id = {p.step_id: p for p in neu.pmi}
    d = neu.modell.datei
    blatt_ids = set()
    for (nr, _, mods), soll in zip(daten, masse, strict=True):
        item, = neu.grafik[nr].pmi_ids
        p = je_id[item]
        assert set(p.modifikatoren) == set(mods) and p.nennwert == pytest.approx(soll.nennwert)
        link, = [d.entities[i] for i in d.referrers()[item] if d.entities[i].is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION")]
        darst = d.get(link.args()[1])
        ids = {ie.id for ie in pmi_step.mass_items(d, darst)}
        assert not blatt_ids.intersection(ids)
        blatt_ids.update(ids)
        gruppen = [d.get(ref) for ref in darst.args()[1] if d.get(ref).is_a("COMPOUND_REPRESENTATION_ITEM")]
        typ2 = set(mods).intersection(pmi_step.MASS_TYP2.values())
        assert len(gruppen) == int(bool(typ2))
        if gruppen:
            name, liste = gruppen[0].args()
            assert (name, liste.typ, len(liste.args[0])) == ("modifiers", "LIST_REPRESENTATION_ITEM", len(typ2))
        p.bearbeitet, p.original, p.nennwert = True, {"nennwert": p.nennwert}, p.nennwert + 1
    erneut = str(tmp_path / "editiert.stp")
    bericht = step_schreiben.schreibe(ziel, erneut, neu.pmi)
    assert len(bericht.geschrieben) == 4 and not bericht.uebersprungen
    gelesen = {p.step_id: p for p in lade_alles(erneut).pmi}
    for p in neu.pmi:
        if p.bearbeitet:
            assert gelesen[p.step_id].nennwert == pytest.approx(p.nennwert)
            assert gelesen[p.step_id].modifikatoren == p.modifikatoren


def test_nist_statistische_massnotiz_als_set():
    erg = lade_alles(pfad("nist_ftc_07_asme1_ap242-e2.stp"))
    mass, = [p for p in erg.pmi if p.step_id == 15607]
    assert mass.nennwert == pytest.approx(22.225) and mass.modifikatoren == ["StatisticalTolerance"]


def test_masswert_in_einfacher_entitaet_mit_direkter_massnotiz(tmp_path):
    text = Path(pfad("nist_ftc_07_asme1_ap242-e2.stp")).read_text(encoding="utf-8")
    a, b = step_schreiben._anweisung(text, 15605)
    text = text[:a] + "#15605=MEASURE_REPRESENTATION_ITEM('nominal value',LENGTH_MEASURE(0.875),#6);" + text[b:]
    text = text.replace("(#15605,#15604)", "(#15603,#15605)")
    quelle = tmp_path / "direkte_notiz.stp"
    quelle.write_text(text, encoding="utf-8")
    p = next(p for p in lade_alles(str(quelle)).pmi if p.step_id == 15607)
    assert p.nennwert == pytest.approx(22.225) and p.modifikatoren == ["StatisticalTolerance"]
    p.bearbeitet, p.original, p.nennwert = True, {"nennwert": p.nennwert}, 25.4
    ziel = str(tmp_path / "direkte_notiz_bearbeitet.stp")
    assert step_schreiben.schreibe(str(quelle), ziel, [p]).geschrieben == [(p.nummer, "nennwert")]
    assert "LENGTH_MEASURE(1.),#6)" in Path(ziel).read_text(encoding="utf-8")
    assert next(p for p in lade_alles(ziel).pmi if p.step_id == 15607).nennwert == pytest.approx(25.4)


def test_mass_mit_widerspruechlichen_zusaetzen_bleibt_grafisch(grafische_datei, tmp_path):
    datei, _, vorher = grafische_datei
    p = Pmi("mass", typ="Size_Radius", nennwert=3., modifikatoren=["Theoretisch", "Hilfsmass"],
            flaechen={vorher.modell.step_zu_flaeche[861]}, quelle="eigen", callout=607, nummer=24, step_id=-1)
    ziel = str(tmp_path / "widerspruch.stp")
    bericht = step_schreiben.schreibe(datei, ziel, [p], vorher.modell)
    assert [n for n, _, _ in bericht.uebersprungen] == [24] and not bericht.neu
    assert lade_alles(ziel).modell.datei.entities == vorher.modell.datei.entities


def test_nist_ftc08_netzflaeche_und_vier_ansichten_beim_rundlauf(tmp_path):
    from programm.kern.pmi_reparieren import vorschlag

    quelle = pfad("nist_ftc_08_asme1_ap242-e1-tg.stp.gz")
    alt = lade_alles(quelle)
    m, nr = alt.modell, 25921
    assert len(alt.pmi) == len(alt.grafik) == 60 and not any(p.semantisch for p in alt.pmi)
    assert len(m.flaechen) == len(m.step_zu_flaeche) == len(m.flaeche_zu_step) == 273
    for eid, idx in m.step_zu_flaeche.items():
        assert m.flaeche_zu_step[idx] == eid and m.form_von_step(eid).IsPartner(m.flaechen[idx])
    p = vorschlag(next(p for p in alt.pmi if p.step_id == nr), alt.grafik[nr], m)
    assert p.typ == "Flatness" and {m.flaeche_zu_step[i] for i in p.flaechen} == {7581}
    assert p.wert == pytest.approx(.762) and p.modifikatoren == ["Free_State"] and not p.material
    p.quelle, p.step_id, p.nummer, p.wert = "eigen", -1, 61, .123
    ziel = str(tmp_path / "ftc08_eine_ebenheit.stp")
    bericht = step_schreiben.schreibe(quelle, ziel, [p], m)
    assert bericht.repariert == [61] and not bericht.uebersprungen
    neu = lade_alles(ziel)
    assert len(neu.pmi) == 60 and neu.grafik.keys() == alt.grafik.keys()
    assert {p.step_id for p in neu.pmi if not p.semantisch} == set(alt.grafik) - {nr}
    g, = (p for p in neu.pmi if p.semantisch)
    assert g.typ == "Flatness" and g.wert == pytest.approx(.123)
    assert {neu.modell.flaeche_zu_step[i] for i in g.flaechen} == {7581} and g.step_id in neu.grafik[nr].pmi_ids
    d = neu.modell.datei
    assert all(d.entities[i] == e for i, e in m.datei.entities.items())
    assert g.modifikatoren == ["Free_State"] and not g.material
    aspekt = d.entities[g.step_id].args("GEOMETRIC_TOLERANCE")[3]
    assert d.get(aspekt).args()[2] == p21.Ref(56)
    gisu, = [e for e in d.of_type("GEOMETRIC_ITEM_SPECIFIC_USAGE") if e.args()[2] == aspekt]
    assert gisu.args()[3:] == [p21.Ref(106), p21.Ref(7581)]

    def sichtbare_grafiken(erg):
        callouts = {p.nummer: next(n for n, grafik in erg.grafik.items() if p.step_id in grafik.pmi_ids)
                    for p in erg.pmi}
        return {a.name: (a.ort, a.richtung, {callouts[n] for n in a.pmi_nummern}) for a in erg.ansichten}

    assert [len(a.pmi_nummern) for a in alt.ansichten] == [15, 17, 6, 22]
    assert sichtbare_grafiken(neu) == sichtbare_grafiken(alt)


def test_netzflaeche_in_zwei_produktformen_ist_nicht_eindeutig(tmp_path):
    import gzip

    quelle = pfad("nist_ftc_08_asme1_ap242-e1-tg.stp.gz")
    with gzip.open(quelle, "rt", encoding="utf-8") as f:
        text = f.read()
    # Derselbe TESSELLATED_SOLID wird nun sowohl von Produkt #56 als auch von #90002 verwendet.
    pos = text.rindex("ENDSEC;")
    datei = tmp_path / "zwei_produkte.stp"
    datei.write_text(text[:pos] + """#90001=PRODUCT_DEFINITION('2','',#46,#36);
#90002=PRODUCT_DEFINITION_SHAPE('','',#90001);
#90003=SHAPE_DEFINITION_REPRESENTATION(#90002,#11451);
""" + text[pos:], encoding="utf-8")
    erg = lade_alles(str(datei))
    idx = erg.modell.step_zu_flaeche[7581]
    p = Pmi("toleranz", "Flatness", wert=.123, flaechen={idx}, quelle="eigen", callout=25921, nummer=61, step_id=-1)
    ziel = str(tmp_path / "mehrdeutig.stp")
    bericht = step_schreiben.schreibe(str(datei), ziel, [p], erg.modell)
    assert [n for n, _, _ in bericht.uebersprungen] == [61] and not bericht.neu
    assert not any(p.semantisch for p in lade_alles(ziel).pmi)


def test_ocr_reine_fuellung_vom_pruefdialog_bis_zur_step_kopie(grafische_datei, fenster, tmp_path):
    datei, referenz, _ = grafische_datei
    text = Path(datei).read_text(encoding="utf-8")
    # Nur die Dreiecke der Ziffern behalten, auch Rahmen, Symbol und Pfeil entfallen.
    alt = "TESSELLATED_GEOMETRIC_SET((#461,#348,#462,#349))"
    assert text.count(alt) == 1
    quelle = tmp_path / "nur_fuellung.stp"
    quelle.write_text(text.replace(alt, "TESSELLATED_GEOMETRIC_SET((#349))"), encoding="utf-8")
    fenster.lade(str(quelle), warten=True)
    vorher = fenster.erg
    g = vorher.grafik[611]
    assert not g.linien and not g.platzhalter and len(g.dreiecke) == 1
    original = next(p for p in vorher.pmi if p.step_id == 611)
    assert not original.semantisch and original.wert is None
    fenster._pmi_befehl("semantisch", original)
    dialog = fenster._semantik_dialog
    assert dialog.v.ocr_text == "0.2" and dialog.v.typ == "Flatness" and dialog.v.wert == .2
    ref = next(p for p in referenz.pmi if p.typ == "Flatness")
    fenster.ansicht.setze_auswahl([vorher.modell.flaechen[i] for i in ref.flaechen])
    dialog._auswahl_uebernehmen()
    assert not dialog.fehler()
    dialog._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path / "fuellung_und_semantik.stp"), melden=False)
    nachher = lade_alles(ziel)
    neu, = [p for p in nachher.pmi if p.semantisch]
    assert (neu.typ, neu.wert, neu.flaechen) == ("Flatness", .2, ref.flaechen)
    assert nachher.grafik[611].pmi_ids == {neu.step_id}
    assert all(nachher.modell.datei.get(i) == e for i, e in vorher.modell.datei.entities.items())


def test_ocr_kurvengrafik_liest_symbole_und_verwirft_zusatzangabe():
    from programm.kern.pmi_reparieren import vorschlag
    vorher = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    def lies(nr):
        return vorschlag(next(p for p in vorher.pmi if p.step_id == nr), vorher.grafik[nr], vorher.modell)
    assert not vorher.grafik[3420].dreiecke and not vorher.grafik[3420].platzhalter
    mass = lies(3420)
    assert (mass.typ, mass.nennwert, mass.unten, mass.oben) == ("Size_Diameter", 25, -.15, .15)
    assert not mass.nennwert_aus_geometrie
    rahmen = lies(3415)
    assert (rahmen.typ, rahmen.wert, [b.name for b in rahmen.bezuege]) == ("Position", .75, ["A", "B", "C"])
    assert lies(3428).wert == .2
    assert lies(3422).wert is None


def test_einlinige_schrift_auf_schraeger_ebene_und_unbekanntes_zeichen():
    from programm.kern.pmi_strichschrift import lies_schrift
    from programm.kern.praesentation import Grafik
    # Frei gezeichnete Zwei und Sieben, weder Konturen noch Dreiecke. Lage und Massstab sind beliebig.
    x = np.array([0., 1., 0.])
    y = np.array([.6, 0., .8])
    o = np.array([34., 28., -71.])
    def linie(punkte):
        return np.array([o + .7 * (u*x + v*y) for u, v in punkte])
    l = [linie([(0, 6.1), (1.1, 7.2), (2, 8), (4, 8), (6, 7), (6.1, 5), (0, 0), (6, 0)]),
         linie([(9, 8), (15, 8.1), (11, 0)])]
    g = Grafik(19, linien=l, ebene=(o, x, y, np.cross(x, y)))
    assert lies_schrift(g) == "27"
    g.linien.append(linie([(18, 0), (24, 8), (18, 8), (24, 0), (18, 0)]))
    assert lies_schrift(g) == ""


def test_suche_liest_grafische_schrift_erst_bei_bedarf(fenster, monkeypatch, app):
    import time
    from programm.kern import pmi_strichschrift

    gelesen = []
    lies = pmi_strichschrift.lies_schrift
    def mitzaehlen(g):
        gelesen.append(g.callout_id)
        return lies(g)
    monkeypatch.setattr(pmi_strichschrift, "lies_schrift", mitzaehlen)
    fenster.lade(pfad("nist_ctc_01_asme1_ap203.stp.gz"), warten=True)
    panel = fenster.pmi
    panel.suche.setText("nr:1")
    assert not gelesen and not panel._schrift_timer.isActive()
    panel.suche.setText("⌀25")
    assert panel._schrift_timer.isActive()
    panel.suche.clear()
    assert not panel._schrift_timer.isActive() and not gelesen
    panel.suche.setText("wert:0.75 bezug:c")
    ende = time.monotonic() + 5
    while not panel._schrift_fertig and time.monotonic() < ende:
        app.processEvents()
        time.sleep(.002)
    assert {p.step_id for p in panel.sichtbare()} == {3415, 3424}
    assert len(gelesen) == len(set(gelesen)) == 21
    panel.suche.setText("⌀25±0.15")
    assert [p.step_id for p in panel.sichtbare()] == [3420]
    assert not panel._schrift_timer.isActive()
    assert all(not p.semantisch and p.wert is None for p in fenster.erg.pmi)
    fenster.schliesse_modell()
    assert not panel._schriftwerte and not panel.sichtbare()


def test_ocr_gestapelte_abmasse_und_grenzmasse_im_step(grafische_datei, tmp_path):
    from programm.kern.pmi_reparieren import vorschlag

    datei, referenz, vorher = grafische_datei
    erwartet = {607: (35., 0., -.2, False), 608: (35., .2, 0., False),
                609: (20., .05, -.10, False), 614: (35., 35.2, 34.8, True)}
    bestaetigt = []
    for nr, soll in erwartet.items():
        original = next(p for p in vorher.pmi if p.step_id == nr)
        v = vorschlag(original, vorher.grafik[nr], vorher.modell)
        assert v.typ == "Size_Diameter" and "\n" in v.ocr_text and not v.nennwert_aus_geometrie
        assert (v.nennwert, v.oben, v.unten, v.grenzmass) == soll
        # Der Pruefer waehlt die Bezugsflaeche. Alle Masswerte stammen ausschliesslich aus der Schrift.
        ref = next(p for p in referenz.pmi if p.step_id in referenz.grafik[nr].pmi_ids)
        v.flaechen = set(ref.flaechen)
        v.quelle, v.step_id, v.nummer = "eigen", -nr, nr
        bestaetigt.append(v)
    ziel = str(tmp_path / "gestapelt.stp")
    bericht = step_schreiben.schreibe(datei, ziel, bestaetigt, vorher.modell)
    assert set(bericht.repariert) == set(erwartet)
    neu = lade_alles(ziel)
    for nr, soll in erwartet.items():
        sem, = [p for p in neu.pmi if p.step_id in neu.grafik[nr].pmi_ids]
        assert sem.semantisch and (sem.nennwert, sem.oben, sem.unten, sem.grenzmass) == soll
    assert all(neu.modell.datei.get(i) == e for i, e in vorher.modell.datei.entities.items())


def test_ocr_winkel_hilfsmass_und_buchstabe_ohne_bezugsrahmen():
    from programm.kern.pmi_reparieren import vorschlag
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    def lies(nr):
        return vorschlag(next(p for p in erg.pmi if p.step_id == nr), erg.grafik[nr], erg.modell)
    p = lies(3421)
    assert p.typ in ("Size_Angular", "Location_Angular") and (p.nennwert, p.oben, p.unten) == (60, .5, -.5)
    assert "Hilfsmass" in lies(3418).modifikatoren and lies(3418).nennwert == 85
    assert not lies(3412).ocr_text  # Der Buchstabe B ist hier nur eine Notiz.


def test_laufende_schrifterkennung_nach_modellwechsel(fenster, monkeypatch, app):
    import threading
    import time
    from programm.kern import pmi_strichschrift

    gestartet, freigabe = threading.Event(), threading.Event()
    def warte(g):
        gestartet.set()
        freigabe.wait(4)
        return "⌀123"
    monkeypatch.setattr(pmi_strichschrift, "lies_schrift", warte)
    fenster.lade(pfad("nist_ctc_01_asme1_ap203.stp.gz"), warten=True)
    panel = fenster.pmi
    panel.suche.setText("123")
    ende = time.monotonic() + 3
    while not gestartet.is_set() and time.monotonic() < ende:
        app.processEvents()
        time.sleep(.002)
    try:
        assert gestartet.is_set()
        arbeit = panel._schriftarbeit
        fenster.schliesse_modell()
        assert arbeit.abgebrochen and panel._schriftarbeit is None
    finally:
        freigabe.set()
    assert arbeit.wait(3000)
    app.processEvents()
    assert not panel._schriftwerte and not panel.sichtbare()


def test_suche_nach_originaltext_einer_freitextnotiz(app):
    from programm.kern.pmi_lesen import ergaenze_hinweise
    from programm.kern.praesentation import Grafik, Platzhalter
    from programm.ui.panels import PmiPanel
    o, x, y = np.zeros(3), np.array([1., 0., 0.]), np.array([0., 1., 0.])
    g = Grafik(41, "Text.1", platzhalter=[Platzhalter(o, x, y, 20., 2., "Scharfe Kanten entgraten")])
    p, = ergaenze_hinweise([], {41: g})
    panel = PmiPanel()
    panel.zeige([p])
    panel.suche.setText("Entgraten")
    assert panel.sichtbare() == [p] and p.name == "Text.1" and not p.semantisch


def test_unbekannter_modifikator_im_wertfach_wird_kein_bezug():
    from dataclasses import replace
    from programm.kern.pmi_strichschrift import lies_schrift
    erg = lade_alles(pfad("nist_ftc_08_asme1_ap242-e1-tg.stp.gz"))
    g = erg.grafik[25921]
    # Letzten Buchstaben F durch ein L ersetzen; der Kreis und alle anderen Striche stammen aus der Datei.
    o, x, y, _ = g.ebene
    zeichen = (g.linien[-1] - o) @ np.column_stack((x, y))
    (l, b), (r, t) = zeichen.min(0), zeichen.max(0)
    l_kontur = np.array([o + u*x + v*y for u, v in [(l, t), (l, b), (r, b)]])
    assert not lies_schrift(replace(g, linien=[*g.linien[:-1], l_kontur]))
