"""Lokale Ebenheit auf einer rechteckigen Einheitsflaeche aus NIST CTC-03."""

import gzip
import re
from pathlib import Path
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import pmi_ableiten, pmi_strichschrift, scanpruefung, zeichnungsabgleich
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.kern.vergleich_pmi import vergleiche_pmi
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_step_ap242 import _occt


def _strichwert(text, e):
    """Den Wert .005/.25X.20 mit eigenen Mittellinien in dasselbe Rahmenfach schreiben."""
    g = e.grafik[3623]
    o, x, y, _ = g.ebene
    pfade = pmi_strichschrift._pfade(g, g.ebene)
    gruppe = e.modell.datei.get(e.modell.datei.get(3623).args()[2])
    refs = [str(n) for n in gruppe.args()[1][:7]]
    neu = []
    nr = max(e.modell.datei.entities) + 1
    zuege = {
        ".": [[(0,0),(1,0),(1,1),(0,1),(0,0)]],
        "0": [[(.27,1),(.71,1),(1,.83),(1,.18),(.72,0),(.26,0),(0,.18),(0,.81),(.27,1)]],
        "2": [[(0,.76),(.17,.93),(.39,1),(.74,1),(1,.84),(1,.65),(0,0),(1,0)]],
        "5": [[(1,1),(.15,1),(0,.52),(.53,.52),(.84,.42),(1,.24),(.76,0),(.22,0),(0,.15)]],
        "/": [[(0,0),(1,1)]], "X": [[(0,0),(1,1)],[(0,1),(1,0)]]}
    for i, z in zip((7,8,10,12,13,14,15,16,17,18,19,20), ".005/.25X.20", strict=True):
        kontur = pfade[i][0]
        for zug in zuege[z]:
            ids = []
            for u, v in kontur.min(axis=0) + np.asarray(zug)*np.ptp(kontur, axis=0):
                coords = ",".join(f"{a:.11f}" for a in (o+u*x+v*y)/g.textfaktor)
                neu.append(f"#{nr}=CARTESIAN_POINT('',({coords}));")
                ids.append(f"#{nr}")
                nr += 1
            neu.append(f"#{nr}=POLYLINE('',({','.join(ids)}));")
            refs.append(f"#{nr}")
            nr += 1
    refs.extend(str(n) for n in gruppe.args()[1][21:])
    text, n = re.subn(rf"(#{gruppe.id}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;",
                      r"\g<1>(" + ",".join(refs) + "));", text)
    assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(neu) + "\n" + text[pos:]


def _rechteck_pmi(e):
    return next(p for p in e.pmi if p.einheitslaenge is not None)


@pytest.mark.parametrize("schrift", ["kontur", "strich", "fuellung"])
def test_rechteckige_einheitsflaeche_bis_step(fenster, tmp_path, schrift):
    quelle = pfad("nist_ctc_03_asme1_ap203.stp.gz")
    e = lade_alles(quelle)
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    if schrift == "strich":
        text = _strichwert(text, e)
    if schrift == "fuellung":
        g = e.grafik[3623]
        linien = list(g.linien)
        # Die zweite Fuenf gegen die beiden Originalkonturen einer Null tauschen.
        x = g.ebene[1]
        dx = (linien[20] @ x).min() - (linien[8] @ x).min()
        linien[20:21] = [linie + dx*x for linie in linien[8:10]]
        nets = _gefuellt(replace(g, linien=linien))
        stil = e.modell.datei.get(3623).args("ANNOTATION_OCCURRENCE")[1][0].id
        text = _mit_fuellsatz(text, nets, 3623, stil, "fcf")
        text, n = re.subn(r"#3390=ANNOTATION_PLANE\([^;]+;", "", text)
        assert n == 1 and text.count("#3390,") == 1
        text = text.replace("#3390,", "")
    datei = tmp_path / "Grafik.step"
    datei.write_text(text, encoding="ascii")
    fenster.lade(str(datei), warten=True)
    erg = fenster.erg
    g = erg.grafik[3623]
    assert bool(g.dreiecke) == (schrift == "fuellung")
    assert (g.ebene is None) == (schrift == "fuellung")
    fenster._pmi_befehl("semantisch", next(p for p in erg.pmi if p.step_id == 3623))
    dialog = fenster._semantik_dialog
    breite = 6.35 if schrift == "kontur" else 5.08
    assert dialog.v.typ == "Flatness" and not dialog.fehler()
    assert (dialog.v.wert, dialog.v.einheitslaenge, dialog.v.einheitsbreite) == pytest.approx((.127, 6.35, breite))
    feld = dialog.felder["einheitsbreite"]
    feld.setText("0")
    assert dialog.fehler()
    feld.setText(str(breite))
    assert {erg.modell.flaeche_zu_step[i] for i in dialog.flaechen} == {479}
    dialog._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Einheitsflaeche.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    assert _rechteck_pmi(fenster.erg).einheitsbreite == pytest.approx(breite)
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Semantik.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    p = _rechteck_pmi(neu)
    assert p.semantisch and p.step_id in neu.grafik[3623].pmi_ids
    ansichten = _ansichten(erg.modell.datei, 3623)
    assert ansichten and _ansichten(neu.modell.datei, 3623) == ansichten
    assert (p.wert, p.einheitslaenge, p.einheitsbreite) == pytest.approx((.127, 6.35, breite))
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {479}
    typ = neu.modell.datei.get(p.step_id)
    assert typ.is_a("FLATNESS_TOLERANCE") and typ.args("GEOMETRIC_TOLERANCE_WITH_DEFINED_AREA_UNIT")[0].name == "RECTANGULAR"
    for a, b in zip(g.linien, neu.grafik[3623].linien, strict=True):
        np.testing.assert_array_equal(a, b)
    for (a, ia), (b, ib) in zip(g.dreiecke, neu.grafik[3623].dreiecke, strict=True):
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(ia, ib)
    typen, diagnosen, volumen = _occt(ziel)
    _, alt, ursprung = _occt(datei)
    assert volumen == pytest.approx(ursprung)
    # OCCT 8 liest dieselbe Komplexinstanz in NIST CTC-03 #37 als UndefinedEntity.
    if typen[p.step_id] == "StepData_UndefinedEntity":
        link, = [e for e in neu.modell.datei.of_type("DRAUGHTING_MODEL_ITEM_ASSOCIATION")
                 if e.args()[2].id == p.step_id]
        fehler = (link.id, "Parameter n0.3 (item_identified_representation_usage.definition) : Entity has illegal type")
        diagnosen.remove(fehler)
    assert diagnosen == alt
    assert p.einheitsrechteck_text() in p.wert_text()
    # Entgegengesetzte Abweichungen ueber die ganze Flaeche belegen keine lokale Ueberschreitung.
    idx, = p.flaechen
    scan = scanpruefung.Zuordnung(np.zeros((8, 3)), np.linspace(-.2, .2, 8), np.full(8, idx))
    lokal, global_ = scanpruefung.bewerte([p, replace(p, einheitslaenge=None, einheitsbreite=None)], neu.modell, scan)
    assert lokal.status == scanpruefung.OFFEN and global_.status == scanpruefung.NOK
    aenderung, = vergleiche_pmi([p], [replace(p, einheitsbreite=p.einheitsbreite+1.)])
    assert [k for k, _, _ in aenderung.felder] == ["einheitsbreite"]
    zeichnung = zeichnungsabgleich.lese_angabe("⏥ | .005 / .25 X .25", 25.4)
    assert zeichnungsabgleich.unterschiede(zeichnung, p) == ([] if schrift == "kontur" else ["einheitsbreite"])


@pytest.mark.parametrize("angabe", [".005/.25X", ".005/.25X0", ".005/.25X.25 ABC", ".005/.25X.25/.2",
                                   ".01/⌀", ".01/⌀0", ".01/⌀1 A", ".01/⌀1X2", ".01/S⌀1"])
def test_unvollstaendige_einheitsflaeche_liefert_keinen_globalen_wert(angabe):
    assert "wert" not in pmi_ableiten.aus_text(["⏥ " + angabe], 25.4)


def test_unabhaengige_nist_referenz_mit_rechteckiger_einheitsflaeche():
    datei = Path(__file__).resolve().parents[1] / "daten/nist/NIST-PMI-STEP-Files/nist_ctc_03_asme1_ap242-e2.stp"
    if not datei.is_file():
        pytest.skip("Optionales semantisches NIST-Referenzmodell fehlt")
    e = lade_alles(str(datei))
    p = _rechteck_pmi(e)
    assert p.step_id == 37 and p.typ == "Flatness"
    assert (p.wert, p.einheitslaenge, p.einheitsbreite) == pytest.approx((.127, 6.35, 6.35))
    assert {e.modell.flaeche_zu_step[i] for i in p.flaechen} == {1441}


def test_kreisflaeche_aus_ftc07_im_vergleich_und_scan(ftc07):
    from programm.kern import pmi_erzeugen, pmi_step
    p = next(p for p in pmi_step.lies_toleranzen(ftc07) if p.step_id == 14257)
    assert {ftc07.flaeche_zu_step[i] for i in p.flaechen} == {10770}
    assert pmi_erzeugen.felder(p) == ["⏥", "0.254 / ⌀25.4"]
    geaendert = replace(p, einheitsdurchmesser=12.7)
    aenderung, = vergleiche_pmi([p], [geaendert])
    assert [k for k, _, _ in aenderung.felder] == ["einheitsdurchmesser"]
    zeichnung = zeichnungsabgleich.lese_angabe("⏥ | .01 / Ø.5", 25.4)
    assert zeichnungsabgleich.unterschiede(zeichnung, geaendert) == []
    assert zeichnungsabgleich.unterschiede(zeichnung, p) == ["einheitsdurchmesser"]
    idx, = p.flaechen
    scan = scanpruefung.Zuordnung(np.zeros((8, 3)), np.linspace(-.2, .2, 8), np.full(8, idx))
    lokal, global_ = scanpruefung.bewerte([p, replace(p, einheitsdurchmesser=None)], ftc07, scan)
    assert lokal.status == scanpruefung.OFFEN and "⌀25.4" in lokal.text
    assert global_.status == scanpruefung.NOK
