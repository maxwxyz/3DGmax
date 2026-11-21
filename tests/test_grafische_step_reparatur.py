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


def _ohne_semantik(quelle, datei, *, validierung=True):
    quelle = Path(quelle)
    ursprung = lade_alles(str(quelle))
    d = ursprung.modell.datei
    # Alle semantischen Merkmale und ihre Bezugs-/Darstellungslinks entfernen.
    # Die transitive Rueckwaertssuche entfernt auch jede Entitaet, die dadurch ins Leere zeigen wuerde.
    typen = (*pmi_step.MASS_TYPEN, *pmi_step.TOL_ARTEN, "GEOMETRIC_TOLERANCE", "DATUM",
             "DATUM_FEATURE", "DATUM_TARGET", "DRAUGHTING_MODEL_ITEM_ASSOCIATION", p21.DMIA_PH)
    entfernen = {e.id for e in d.of_types_by_id(typen)}
    if not validierung:
        entfernen.update(e.id for e in d.of_type("DESCRIPTIVE_REPRESENTATION_ITEM")
                         if e.args()[0] == "equivalent unicode string")
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
    datei.write_text(";\n".join(statements) + ";\n", encoding="utf-8")
    rein = lade_alles(str(datei))
    assert not any(p.semantisch for p in rein.pmi) and not rein.modell.datei.of_types_by_id(typen)
    assert set(rein.modell.datei.referrers()) <= rein.modell.datei.entities.keys()
    assert rein.grafik.keys() == ursprung.grafik.keys()
    assert len(rein.modell.flaechen) == len(ursprung.modell.flaechen)
    return str(datei), ursprung, rein


@pytest.fixture(scope="module")
def grafische_datei(tmp_path_factory):
    daten = _ohne_semantik(pfad("nist_ctc_01_asme1_ap242-e1.stp"),
                           tmp_path_factory.mktemp("grafische_pmi") / "ctc_01_grafisch.stp")
    rein = daten[2]
    assert len(rein.pmi) == len(rein.grafik) == 23
    return daten


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


def test_abstandspmi_auf_tesselliertem_ap242_mit_pfeil_auf_dem_netz(tmp_path):
    from OCC.Core.BRep import BRep_Tool
    from programm.kern import plausibilitaet
    from programm.kern.ausrichten import tesselliere
    quelle = pfad("nist_ftc_08_asme1_ap242-e1-tg.stp.gz")
    alt = lade_alles(quelle)
    m = alt.modell
    f = m.step_zu_flaeche[7581]
    j = next(i for i in range(len(m.flaechen)) if i != f)
    paar = {f, j}
    assert all(BRep_Tool.Surface(m.flaechen[i]) is None for i in paar)
    p = Pmi("mass", "Location_LinearDistance", nennwert=12., oben=.2, unten=-.2, flaechen=paar,
            quelle="eigen", step_id=-1, nummer=61)
    assert plausibilitaet.geometrie([p], m) == plausibilitaet.geschlossene_ketten([p], m) == []
    ziel = str(tmp_path/"netzabstand.stp")
    bericht = step_schreiben.schreibe(quelle, ziel, [p], m)
    assert bericht.neu == bericht.dargestellt == [61]
    neu = lade_alles(ziel)
    mass, = [p for p in neu.pmi if p.semantisch]
    assert mass.nennwert == 12. and mass.grafisch and len(mass.flaechen) == 2
    grafik, = (g for g in neu.grafik.values() if mass.step_id in g.pmi_ids)
    assert not grafik.erzeugt
    # Der Pfeil liegt auf einem belegten Dreieck (Ebene und baryzentrische Koordinaten).
    spitze = grafik.linien[0][0]
    def auf_dreieck(abc):
        a, b, c = abc
        basis = np.array([b-a, c-a]).T
        uv, _, rang, _ = np.linalg.lstsq(basis, spitze-a, rcond=None)
        return (rang == 2 and np.linalg.norm(a+basis@uv-spitze) < 5e-5
                and uv.min() >= -1e-5 and uv.sum() <= 1+1e-5)
    assert any(auf_dreieck(d) for pkt, tri in tesselliere([neu.modell.flaechen[i] for i in mass.flaechen])
               for d in pkt[tri])


def _radiusgrafik(voll):
    # Jeder Streifenzug verwendet lokale Koordinaten in der vorhandenen Annotationsebene.
    import json
    from PySide6 import QtCore, QtGui

    if voll:
        bild = QtGui.QImage(160,90,QtGui.QImage.Format.Format_Grayscale8)
        bild.fill(0)
        with QtGui.QPainter(bild) as maler:
            font = QtGui.QFont("Helvetica")
            font.setPixelSize(64)
            maler.setFont(font)
            maler.setPen(QtCore.Qt.GlobalColor.white)
            maler.drawText(5,68,"R2")
        maske = np.frombuffer(bild.constBits(),np.uint8).reshape(90,160) > 127
        zuege = []
        for y, zeile in enumerate(maske):
            kanten = np.flatnonzero(np.diff(np.r_[False,zeile,False]))
            for l,r in kanten.reshape(-1,2):
                zuege.append([(l,-y),(l,-y-1),(r,-y-1),(r,-y)])
    else:
        zuege = [[(0,0),(0,8),(3.9,8),(5.8,7),(6.1,5.3),(4.2,4),(0,4)],
                 [(3,4),(6.1,0)], [(9,6),(10,7.4),(11.1,8),(13.3,8),(15,7),(15,5.3),(9,0),(15.2,0)]]
    punkte, indizes = [], []
    for zug in zuege:
        indizes.append(list(range(len(punkte)+1,len(punkte)+1+len(zug))))
        punkte.extend([[float(x),float(y),0.] for x,y in zug])
    def liste(daten):
        return json.dumps(daten,separators=(",",":")).translate(str.maketrans("[]","()"))
    coords = f"#90001=COORDINATES_LIST('',{len(punkte)},{liste(punkte)});"
    if voll:
        element = f"COMPLEX_TRIANGULATED_SURFACE_SET('',#90001,{len(punkte)},((0.,0.,1.)),(),(),{liste(indizes)})"
    else:
        element = f"TESSELLATED_CURVE_SET('',#90001,{liste(indizes)})"
    return f"{coords}\n#90002={element};\n"


@pytest.mark.parametrize("voll", [False,True], ids=["striche","nur_dreiecke"])
def test_anonymes_radiusmass_mit_originalgrafik_als_step(grafische_datei, fenster, tmp_path, voll):
    datei, referenz, _ = grafische_datei
    text = Path(datei).read_text(encoding="utf-8")
    alt = "TESSELLATED_GEOMETRIC_SET((#461,#348,#462,#349))"
    assert text.count(alt) == 1
    text = text.replace(alt,"TESSELLATED_GEOMETRIC_SET((#90002))").replace("'Flatness.1'","''")
    ende = text.rindex("ENDSEC;")
    quelle = tmp_path / "Grafisches Radiusmass.stp"
    quelle.write_text(text[:ende]+_radiusgrafik(voll)+text[ende:],encoding="utf-8")
    fenster.lade(str(quelle),warten=True)
    vorher = fenster.erg
    g = vorher.grafik[611]
    assert not g.platzhalter and bool(g.dreiecke) == voll and bool(g.linien) != voll
    original = next(p for p in vorher.pmi if p.step_id == 611)
    assert not original.semantisch and original.nennwert is None
    fenster._pmi_befehl("semantisch",original)
    dialog = fenster._semantik_dialog
    assert (dialog.v.ocr_text,dialog.v.typ,dialog.v.nennwert) == ("R2","Size_Radius",2.)
    wand = next(p.flaechen for p in referenz.pmi if p.typ == "Size_Diameter" and p.flaechen)
    fenster.ansicht.setze_auswahl([vorher.modell.flaechen[i] for i in wand])
    dialog._auswahl_uebernehmen()
    assert not dialog.fehler()
    dialog._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Radius und Grafik.stp"),melden=False)
    nachher = lade_alles(ziel)
    neu, = [p for p in nachher.pmi if p.semantisch]
    assert (neu.typ,neu.nennwert,neu.flaechen) == ("Size_Radius",2.,wand)
    assert nachher.grafik[611].pmi_ids == {neu.step_id}
    assert all(nachher.modell.datei.get(i) == e for i,e in vorher.modell.datei.entities.items())


def test_ftc07_validierungstext_aus_grafischer_datei_bis_step_export(fenster, tmp_path):
    from PySide6.QtWidgets import QLabel
    from programm.kern.pmi_validierungstext import validierungsvorschlag
    datei, referenz, rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path / "grafisch.stp")
    fenster.lade(datei, warten=True)
    nr_typ = {13706:"Datum", 13747:"Datum", 13788:"Datum", 14558:"Position",
              15715:"Size_Diameter", 15899:"Size_Diameter"}
    for nr, typ in nr_typ.items():
        quelle = next(p for p in fenster.erg.pmi if p.step_id == nr)
        soll, = [p for p in referenz.pmi if p.step_id in referenz.grafik[nr].pmi_ids and p.typ == typ]
        assert not quelle.semantisch and not fenster.erg.grafik[nr].platzhalter
        fenster._pmi_befehl("semantisch", quelle)
        d = fenster._semantik_dialog
        assert not d.v.ocr_text and d.v.validierungstexte and d.v.typ == typ
        assert any("STEP-Validierungseigenschaft" in label.text() for label in d.findChildren(QLabel))
        if typ == "Datum":
            assert d.v.name == soll.name
        elif typ == "Position":
            assert d.v.rahmensymbolquelle == "grafik"
            assert any("ersten gezeichneten Fach" in label.text() for label in d.findChildren(QLabel))
            g = rein.grafik[nr]
            assert validierungsvorschlag(rein.modell.datei, g, None)[1]["typ"] == "Position"
            assert not validierungsvorschlag(rein.modell.datei, g, ("toleranz","Flatness"))[1]
            assert d.v.wert == pytest.approx(1.016) and d.v.material == "M"
            assert d.v.bezug_text() == "A|B|C"
        elif nr == 15715:
            assert d.v.nur_grafik_text == "4X ⌀.173 +.005\n-.001"
            assert (d.v.nennwert,d.v.oben,d.v.unten) == pytest.approx((4.3942,.127,-.0254))
        else:
            assert d.v.nur_grafik_text == "4X ⌀.438±.010" and d.v.nennwert == pytest.approx(11.1252)
            assert soll.nennwert == pytest.approx(.4375*25.4)
        fenster.ansicht.setze_auswahl([fenster.erg.modell.flaechen[i] for i in soll.flaechen])
        d._auswahl_uebernehmen()
        assert not d.fehler()
        d._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Grafik mit Semantik.stp"), melden=False)
    assert len(fenster._step_bericht.repariert) == len(nr_typ) and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == e for i,e in rein.modell.datei.entities.items())
    assert sum(p.semantisch for p in neu.pmi) == len(nr_typ)
    for nr,typ in nr_typ.items():
        p, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[nr].pmi_ids]
        soll, = [p for p in referenz.pmi if p.step_id in referenz.grafik[nr].pmi_ids and p.typ == typ]
        assert p.typ == typ and p.flaechen == soll.flaechen
        if typ == "Position":
            assert p.material == "M" and p.wert == pytest.approx(1.016) and p.bezug_text() == "A|B|C"
        elif typ == "Datum":
            assert p.name == soll.name
        else:
            assert p.nennwert == pytest.approx((.438 if nr == 15899 else .173)*25.4)
            assert (p.oben, p.unten) == pytest.approx((.254,-.254) if nr == 15899 else (.127,-.0254))


@pytest.mark.parametrize("validierung,quelle",[(False,"grafik"),(True,"datei"),(True,"grafik")])
def test_breite_strichschrift_mit_gepruefter_masslesart_bis_step(fenster,tmp_path,validierung,quelle):
    datei,referenz,rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Strichgrafik.stp",
                                        validierung=validierung)
    fenster.lade(datei, warten=True)
    def oeffnen(nr):
        original = next(p for p in fenster.erg.pmi if p.step_id == nr)
        g = fenster.erg.grafik[nr]
        assert not original.semantisch and g.linien and not g.dreiecke and not g.platzhalter
        fenster._pmi_befehl("semantisch",original)
        d = fenster._semantik_dialog
        soll, = [p for p in referenz.pmi if p.art == "mass" and p.step_id in referenz.grafik[nr].pmi_ids]
        fenster.ansicht.setze_auswahl([fenster.erg.modell.flaechen[i] for i in soll.flaechen])
        d._auswahl_uebernehmen()
        return d
    d = oeffnen(15405)
    if validierung:
        assert set(d.massknoepfe) == {"grafik","datei"} and d.fehler()
        assert not d.felder["nennwert"].text() and not d.felder["unten"].text()
        assert [wahl[1] for wahl in d.v.masswahl] == ["4X⌀.250 +.003\n-.001", "4X ⌀.250 +.003\n-.000"]
        d.massknoepfe[quelle].click()
    else:
        assert not d.v.validierungstexte and not d.massknoepfe and d.v.ocr_text == "4X⌀.250 +.003\n-.001"
    assert not d.fehler()
    d._pruefen()
    d = oeffnen(16200)
    assert not d.felder["nennwert"].text() and d.fehler() and set(d.massknoepfe) == {"grenzen"}
    assert d.v.nur_grafik_text == "R.022-.012"
    d.massknoepfe["grenzen"].click()
    assert d.felder["grenzmass"].isChecked() and not d.fehler()
    d._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.stp"),melden=False)
    assert len(fenster._step_bericht.repariert) == 2 and not fenster._step_bericht.uebersprungen
    kopie = lade_alles(ziel)
    assert all(kopie.modell.datei.get(i) == ent for i,ent in rein.modell.datei.entities.items())
    for nr in (15405,16200):
        neu, = [p for p in kopie.pmi if p.semantisch and p.step_id in kopie.grafik[nr].pmi_ids]
        soll, = [p for p in referenz.pmi if p.art == "mass" and p.step_id in referenz.grafik[nr].pmi_ids]
        assert neu.flaechen == soll.flaechen
        if nr == 15405:
            assert neu.typ == "Size_Diameter" and neu.nennwert == pytest.approx(6.35)
            assert (neu.oben,neu.unten) == pytest.approx((.0762, -.0254 if quelle == "grafik" else 0))
        else:
            assert neu.typ == "Size_Radius" and neu.grenzmass and neu.nennwert == pytest.approx(.4318)
            assert neu.grenzen() == pytest.approx((.5588,.3048))


def test_alle_zwoelf_breiten_masszeilen_ohne_dateitext(ftc07):
    from programm.kern.praesentation import lies_grafik
    from programm.kern.pmi_strichschrift import lies_schrift

    grafik = lies_grafik(ftc07.datei)
    erwartet = {
        15146: "⌀.250 +.003\n-.000", 15254: "⌀.250 +.003\n-.000",
        15360: "2X⌀.250 +.003\n-.000", 15405: "4X⌀.250 +.003\n-.001",
        15623: "3X⌀.875±.020", 15669: "3X⌀.875±.010",
        15715: "4X⌀.173 +.005\n-.001", 15761: "2X⌀.594 +.012\n-.002",
        15807: "4X⌀.281 +.006\n-.001", 15899: "4X⌀.438±.010",
        16020: "2X⌀.594 +.012\n-.002", 16200: "R.022-.012",
    }
    assert set(erwartet) == {nr for nr, g in grafik.items() if g.name.startswith("Linear Size.")}
    for nr, wort in erwartet.items():
        assert lies_schrift(grafik[nr]) == wort


def test_abgesetztes_zeichen_bleibt_ohne_passenden_radialpfeil_offen(ftc07):
    from dataclasses import replace
    from programm.kern.pmi_strichschrift import lies_schrift
    from programm.kern.praesentation import lies_grafik

    g = lies_grafik(ftc07.datei)[15146]
    bogen = g.linien[18]
    # Die ersten 18 Zuege sind Text, danach folgen Bogen, Schaft und die Pfeilspitze.
    assert not lies_schrift(replace(g, linien=g.linien[:20]))
    gerade = np.linspace(bogen[0], bogen[-1], len(bogen))
    verschoben = bogen + 1.5*g.ebene[1]
    am_text = bogen - bogen.mean(axis=0) + g.linien[0][0] - 3*g.ebene[1]
    for zeichen in (gerade, verschoben, am_text):
        linien = [*g.linien[:18], zeichen, *g.linien[19:]]
        assert not lies_schrift(replace(g, linien=linien))
    assert not lies_schrift(replace(g, linien=[*g.linien, am_text]))


def _als_fuellung(datei, rein, ziel, callouts, ohne_ebene=False):
    import json

    def liste(daten):
        return json.dumps(daten, separators=(",", ":")).translate(str.maketrans("[]", "()"))

    text = Path(datei).read_text(encoding="utf-8")
    for nr, kurve, ebene in callouts:
        g = rein.grafik[nr]
        punkte, faecher = [], []
        normale = g.ebene[3]
        for linie in g.linien:
            for a, b in zip(linie, linie[1:]):
                v = b-a
                laenge = np.linalg.norm(v)
                if laenge < 1e-9:
                    continue
                v *= .07 / laenge
                quer = np.cross(normale, v)
                # Der Streifen hat eine Flaeche; keine seiner Kanten wird als Linie gespeichert.
                q = np.array([a-.1*v-quer, b+.1*v-quer, b+.1*v+quer, a-.1*v+quer])
                faecher.append(list(range(len(punkte)+1, len(punkte)+5)))
                punkte.extend(np.round(q / g.textfaktor, 9).tolist())
        koord = 90000 + nr
        start = text.index(f"#{kurve}=TESSELLATED_CURVE_SET(")
        ende = text.index(";", start)+1
        text = (text[:start] + f"#{koord}=COORDINATES_LIST('',{len(punkte)},{liste(punkte)});\n"
                + f"#{kurve}=COMPLEX_TRIANGULATED_SURFACE_SET('',#{koord},{len(punkte)},"
                + f"({liste(normale.tolist())}),(),(),{liste(faecher)});" + text[ende:])
        if ohne_ebene:
            start = text.index(f"#{ebene}=ANNOTATION_PLANE(")
            text = text[:start] + text[text.index(";", start)+1:]
            text = text.replace(f"#{ebene},", "")
    ziel.write_text(text, encoding="utf-8")
    return str(ziel)


@pytest.mark.parametrize("darstellung", ["striche", "dreiecke", "dreiecke_ohne_ebene"])
def test_breite_toleranzrahmen_ohne_validierung_mit_projektion_und_material_im_step(fenster,tmp_path,darstellung):
    from programm.kern.pmi_strichschrift import lies_schrift
    datei,ref,rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"),tmp_path/"Rahmen.stp",validierung=False)
    fuellung = darstellung != "striche"
    ohne_ebene = darstellung == "dreiecke_ohne_ebene"
    if fuellung:
        callouts = ((14040, 14037, 14047), (14795, 14792, 14803), (14498, 14495, 14506))
        datei = _als_fuellung(datei, rein, tmp_path/"Rahmen gefuellt.stp", callouts, ohne_ebene)
    fenster.lade(datei,warten=True)
    rein = fenster.erg
    for nr in (14040,14795,14498):
        assert (rein.grafik[nr].ebene is None) == ohne_ebene
        assert bool(rein.grafik[nr].linien) != fuellung and bool(rein.grafik[nr].dreiecke) == fuellung
    nummern = (13706,13747,13788,14040,14795)
    wortlaut = ("[A]","[B]","[C]","⌖ ⌀.020Ⓟ.425 A B","⌖ ⌀.040Ⓜ A B C")
    for nr,wort in zip(nummern,wortlaut,strict=True):
        p = next(p for p in fenster.erg.pmi if p.step_id == nr)
        art = "toleranz" if nr >= 14040 else "bezug"
        soll, = [p for p in ref.pmi if p.art == art and p.step_id in ref.grafik[nr].pmi_ids]
        assert not p.semantisch and not fenster.erg.grafik[nr].platzhalter
        fenster._pmi_befehl("semantisch",p)
        d = fenster._semantik_dialog
        assert not d.v.validierungstexte and d.v.ocr_text == wort
        fenster.ansicht.setze_auswahl([fenster.erg.modell.flaechen[i] for i in soll.flaechen])
        d._auswahl_uebernehmen()
        if nr == 14040:
            assert d.v.zone == "Projected" and d.v.zonen_wert == pytest.approx(10.795)
            assert d.fehler() and not d.projektionsflaechen
            fenster.ansicht.setze_auswahl([fenster.erg.modell.flaechen[i] for i in soll.projektionsflaechen])
            d._projektionsende_waehlen()
        assert not d.fehler()
        d._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Rahmen mit Semantik.stp"),melden=False)
    assert len(fenster._step_bericht.repariert) == 5 and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == ent for i,ent in rein.modell.datei.entities.items())
    for nr in (14040,14795):
        soll, = [p for p in ref.pmi if p.art == "toleranz" and p.step_id in ref.grafik[nr].pmi_ids]
        ist, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[nr].pmi_ids]
        assert ist.typ == "Position" and ist.flaechen == soll.flaechen and ist.wert == pytest.approx(soll.wert)
        assert ist.bezug_text() == soll.bezug_text() and "Diameter" in ist.modifikatoren
        if nr == 14040:
            assert ist.zone == "Projected" and ist.zonen_wert == pytest.approx(10.795)
            assert ist.projektionsflaechen == soll.projektionsflaechen
        else:
            assert ist.material == "M"
    # Zusatzzeichen, mehrzeilige Rahmen und Bereichsangaben nicht auf eine einfache Toleranz kuerzen.
    for nr in (14405,14498,14269):
        assert lies_schrift(rein.grafik[nr]) == ""
    if ohne_ebene:
        from dataclasses import replace
        from scipy.spatial.transform import Rotation

        g = rein.grafik[14040]
        punkte, netz = g.dreiecke[0]
        drehung = Rotation.from_rotvec([.26, -.24, .77]).as_matrix()
        # Jedes Dreieck hat eigene Punktindizes, auch an einer gemeinsamen Kante.
        frei = punkte[netz].reshape(-1, 3) @ drehung.T + [31., 42., 56.]
        einzeln = np.arange(len(frei)).reshape(-1, 3)
        gedreht = replace(g, dreiecke=[(frei, einzeln)])
        assert lies_schrift(gedreht) == wortlaut[3]
        frei[0] += [10., 37., -43.]
        assert lies_schrift(gedreht) == ""


def test_breite_rahmen_mit_weiteren_merkmalen(ftc07):
    from programm.kern.pmi_strichschrift import lies_schrift
    from programm.kern.praesentation import lies_grafik

    grafik = lies_grafik(ftc07.datei)
    erwartet = {13999: "⟂ ⌀.015Ⓟ.425 A", 14302: "∥ .03 A", 14335: "⌓ .06 A B C"}
    for nr, wort in erwartet.items():
        assert lies_schrift(grafik[nr]) == wort


@pytest.mark.parametrize("fuellung", [False, True], ids=["striche", "dreiecke"])
def test_breite_masse_mit_zielbogen_mengen_und_abmassen_im_step(fenster, tmp_path, fuellung):
    from programm.kern.pmi_strichschrift import lies_schrift

    datei, referenz, rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Masse.stp",
                                           validierung=False)
    callouts = ((15669, 15666, None), (15807, 15804, None), (15146, 15143, None))
    quelle = _als_fuellung(datei, rein, tmp_path/"Masse gefuellt.stp", callouts) if fuellung else datei
    fenster.lade(quelle, warten=True)
    vorher = fenster.erg
    werte = {15669: ("3X⌀.875±.010", .875, .010, -.010), 15807: ("4X⌀.281 +.006\n-.001", .281, .006, -.001),
             15146: ("⌀.250 +.003\n-.000", .250, .003, 0.)}
    for nr, angabe in werte.items():
        original = next(p for p in vorher.pmi if p.step_id == nr)
        g = vorher.grafik[nr]
        assert bool(g.dreiecke) == fuellung and bool(g.linien) != fuellung
        assert not g.platzhalter and not original.semantisch
        fenster._pmi_befehl("semantisch", original)
        dialog = fenster._semantik_dialog
        assert not dialog.v.validierungstexte and dialog.v.ocr_text == angabe[0]
        soll, = [p for p in referenz.pmi if p.art == "mass" and p.step_id in referenz.grafik[nr].pmi_ids]
        fenster.ansicht.setze_auswahl([vorher.modell.flaechen[i] for i in soll.flaechen])
        dialog._auswahl_uebernehmen()
        assert not dialog.fehler()
        dialog._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Masse mit Semantik.stp"), melden=False)
    assert len(fenster._step_bericht.repariert) == 3 and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == ent for i, ent in vorher.modell.datei.entities.items())
    for nr, (text, nenn, oben, unten) in werte.items():
        assert lies_schrift(neu.grafik[nr]) == text
        ist, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[nr].pmi_ids]
        soll, = [p for p in referenz.pmi if p.art == "mass" and p.step_id in referenz.grafik[nr].pmi_ids]
        assert ist.typ == "Size_Diameter" and ist.flaechen == soll.flaechen
        assert (ist.nennwert, ist.oben, ist.unten) == pytest.approx(np.array([nenn, oben, unten])*25.4)


@pytest.mark.parametrize("darstellung,validierung", [
    ("striche", False), ("dreiecke", False), ("striche", True), ("dreiecke_ohne_ebene", False),
])
def test_verbundrahmen_grafisch_bis_zum_semantischen_step(fenster, tmp_path, darstellung, validierung):
    fuellung = darstellung != "striche"
    ohne_ebene = darstellung == "dreiecke_ohne_ebene"
    quelle, ref, rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Verbund.stp",
                                       validierung=validierung)
    if fuellung:
        quelle = _als_fuellung(quelle, rein, tmp_path/"Verbund gefuellt.stp", [(14498, 14495, 14506)], ohne_ebene)
    f = fenster
    f.lade(quelle, warten=True)

    ansichten = {a.step_id for a in f.erg.ansichten if 14498 in a.pmi_ids}
    assert ansichten == {16614}
    assert (f.erg.grafik[14498].ebene is None) == ohne_ebene

    def oeffnen(nr):
        p = next(p for p in f.erg.pmi if p.step_id == nr)
        f._pmi_befehl("semantisch", p)
        return f._semantik_dialog

    for nr in (13706, 13747, 13788):
        d = oeffnen(nr)
        soll, = [p for p in ref.pmi if p.art == "bezug" and p.step_id in ref.grafik[nr].pmi_ids]
        f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in soll.flaechen])
        d._auswahl_uebernehmen()
        assert not d.fehler()
        d._pruefen()

    def erste_zeile():
        d = oeffnen(14498)
        assert "1 von 2" in d.windowTitle() and d.v.ocr_text == "⌖ ⌀.060 A B C"
        assert d.v.wert == pytest.approx(1.524) and d.v.bezug_text() == "A|B|C"
        ziel = next(p.flaechen for p in ref.pmi if p.step_id == 14472)
        f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in ziel])
        d._auswahl_uebernehmen()
        assert not d.fehler()
        d._pruefen()
        return f._semantik_dialog

    d = erste_zeile()
    assert "2 von 2" in d.windowTitle()
    d.reject()
    assert not any(p.callout == 14498 for p in f.erg.pmi)
    d = erste_zeile()
    assert d.v.ocr_text == "⌖ ⌀.015 A" and d.v.wert == pytest.approx(.381) and not d.fehler()
    assert d.v.bezug_text() == "A"
    d._pruefen()
    projekt = f.speichere_projekt(str(tmp_path/"Zwei Zeilen"))
    f.lade(projekt, warten=True)
    oben, unten = sorted([p for p in f.erg.pmi if p.callout == 14498], key=lambda p: -p.wert)
    assert oben.folgetoleranzen == [unten.step_id] and not unten.folgetoleranzen
    assert {oben.step_id, unten.step_id} <= f.erg.grafik[14498].pmi_ids
    assert bool(f.erg.grafik[14498].dreiecke) == fuellung
    for a in f.erg.ansichten:
        assert ({oben.step_id, unten.step_id} <= a.pmi_ids) == (a.step_id in ansichten)
        assert ({oben.nummer, unten.nummer} <= set(a.pmi_nummern)) == (a.step_id in ansichten)
    # Ein ungueltiger Bezug in der zweiten Zeile darf keine einzelne erste Zeile hinterlassen.
    from dataclasses import replace
    gespeicherte_bezuege = unten.bezuege
    unten.bezuege = [replace(unten.bezuege[0], name="ZZ")]
    fehler = f.speichere_step_pmi(str(tmp_path/"Ohne Verbund.stp"), melden=False)
    assert {n for n, _, _ in f._step_bericht.uebersprungen} == {oben.nummer, unten.nummer}
    ohne = lade_alles(fehler)
    assert not any(p.art == "toleranz" and p.semantisch for p in ohne.pmi)
    unten.bezuege = gespeicherte_bezuege
    ziel = f.speichere_step_pmi(str(tmp_path/"Gepruefter Verbund.stp"), melden=False)
    assert not f._step_bericht.uebersprungen and len(f._step_bericht.repariert) == 5
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == ent for i, ent in f.erg.modell.datei.entities.items())
    a, b = sorted([p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[14498].pmi_ids],
                  key=lambda p: -p.wert)
    assert {v.step_id for v in neu.ansichten if {a.step_id, b.step_id} <= v.pmi_ids} == ansichten
    assert a.folgetoleranzen == [b.step_id] and not b.folgetoleranzen
    assert a.typ == b.typ == "Position" and a.flaechen == b.flaechen == oben.flaechen
    assert (a.wert, b.wert) == pytest.approx((1.524, .381))
    assert (a.bezug_text(), b.bezug_text()) == ("A|B|C", "A")
    assert all("Diameter" in p.modifikatoren for p in (a, b))
    assert (neu.modell.datei.get(a.step_id).args("GEOMETRIC_TOLERANCE")[3]
            == neu.modell.datei.get(b.step_id).args("GEOMETRIC_TOLERANCE")[3])
    f.loesche_eigene_pmi([unten])
    assert not any(p.callout == 14498 for p in f.erg.pmi)
    assert len([p for p in f.erg.pmi if p.step_id == 14498 and not p.semantisch]) == 1
    assert 14498 in f.erg.grafik and not {oben.step_id, unten.step_id} & f.erg.grafik[14498].pmi_ids
    for a in f.erg.ansichten:
        assert (14498 in a.pmi_ids) == (a.step_id in ansichten)
        assert unten.nummer not in a.pmi_nummern


def test_verbundrahmen_widerspruch_und_zusatzgrafik(tmp_path):
    from dataclasses import replace
    from programm.kern import pmi_reparieren
    from programm.kern.pmi_verbundschrift import lies_verbund

    datei, _, _ = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Quelle.stp")
    quelle = Path(datei)
    data = quelle.read_text(encoding="utf-8")
    start = data.index("#14511=DESCRIPTIVE_REPRESENTATION_ITEM")
    ende = data.index(";", start)
    zeile = data[start:ende]
    assert zeile.count(".015") == 1
    quelle.write_text(data[:start]+zeile.replace(".015", ".075")+data[ende:], encoding="utf-8")
    erg = lade_alles(datei)
    g = erg.grafik[14498]
    p = next(p for p in erg.pmi if p.step_id == 14498)
    v = pmi_reparieren.vorschlag(p, g, erg.modell)
    paar = pmi_reparieren.verbundvorschlaege(v, g, erg.modell)
    assert len(paar) == 2 and all(z.wert is None and ".075" in z.validierungstexte[0] for z in paar)
    # Zusatz im freien Feld rechts neben der unteren Zeile.
    extra = g.linien[0] + 68*g.ebene[1] - 13*g.ebene[2]
    assert not lies_verbund(replace(g, linien=[*g.linien, extra]))
    from scipy.spatial.transform import Rotation
    d = Rotation.from_rotvec([.6, -.82, .17]).as_matrix()
    gedreht = replace(g, ebene=None, linien=[p @ d.T + [133., 21., 16.] for p in g.linien])
    assert lies_verbund(gedreht) == ("⌖ ⌀.060 A B C", "⌖ ⌀.015 A")
    gedreht.linien[0][0] += [10., 37., -43.]
    assert not lies_verbund(gedreht)


@pytest.mark.parametrize("fuellung", [False, True], ids=["striche", "dreiecke"])
def test_verbundrahmen_mit_material_und_profilhinweisen(fenster, tmp_path, fuellung):
    from programm.kern.pmi_verbundschrift import lies_verbund

    quelle, ref, rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Profil.stp",
                                       validierung=False)
    if fuellung:
        callouts = [(nr, nr-3, None) for nr in (14143, 14636, 14735, 15050, 15098)]
        quelle = _als_fuellung(quelle, rein, tmp_path/"Profil gefuellt.stp", callouts)
    f = fenster
    f.lade(quelle, warten=True)
    druck = {14143: ("⌓ .04 A B C", "⌓ .01 A"), 14636: ("⌓ .070 A B C", "⌓ .015 A"),
             14735: ("⌖ ⌀.06Ⓜ E B C", "⌖ ⌀.02Ⓜ E B C")}
    for nr in (13706, 13747, 13788, 13887, *druck):
        referenzen = [p for p in ref.pmi if p.step_id in ref.grafik[nr].pmi_ids and
                      p.art == ("toleranz" if nr in druck else "bezug")]
        g = f.erg.grafik[nr]
        p = next(p for p in f.erg.pmi if p.step_id == nr)
        f._pmi_befehl("semantisch", p)
        if nr in druck:
            assert tuple(lies_verbund(g)) == druck[nr] and bool(g.dreiecke) == fuellung
        for i, soll in enumerate(referenzen):
            d = f._semantik_dialog
            if nr in druck:
                assert d.v.ocr_text == druck[nr][i]
            f.ansicht.setze_auswahl([f.erg.modell.flaechen[j] for j in soll.flaechen])
            d._auswahl_uebernehmen()
            assert not d.fehler()
            d._pruefen()
    for nr in (15050, 15098):
        assert not lies_verbund(f.erg.grafik[nr])
    ziel = f.speichere_step_pmi(str(tmp_path/"Profil geprueft.stp"), melden=False)
    assert len(f._step_bericht.repariert) == 10 and not f._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == ent for i, ent in f.erg.modell.datei.entities.items())
    for nr in druck:
        soll = [p for p in ref.pmi if p.art == "toleranz" and p.step_id in ref.grafik[nr].pmi_ids]
        ist = [p for p in neu.pmi if p.art == "toleranz" and p.step_id in neu.grafik[nr].pmi_ids]
        assert len(ist) == 2 and ist[0].folgetoleranzen == [ist[1].step_id]
        for a, b in zip(soll, ist, strict=True):
            assert b.typ == a.typ and b.wert == pytest.approx(a.wert)
            assert b.material == a.material and b.modifikatoren == a.modifikatoren
            assert b.bezug_text() == a.bezug_text() and b.flaechen == a.flaechen
