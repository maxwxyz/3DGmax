"""Nummerierte Geltungshinweise aus Originalglyphen von FTC-07."""

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from programm.kern.pmi_verbundschrift import lies_verbund
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_grafische_step_reparatur import _als_fuellung, _ohne_semantik


def _anhaengen(grafik, text):
    g = grafik[15098]
    zuege = {"1": (g, 10, 12), "0": (g, 1, 2), "5": (g, 12, 13), "7": (g, 2, 3),
             "2": (grafik[15623], 6, 7), "3": (grafik[15623], 13, 15), "4": (grafik[15761], 3, 4),
             "6": (grafik[15807], 8, 9), "8": (grafik[15623], 1, 2), "9": (grafik[15761], 2, 3),
             "I": (g, 17, 20), "Q": (g, 25, 26), "O": (grafik[15050], 31, 32)}
    links, linien = 180.8, list(g.linien)
    for z in text:
        quelle, start, ende = zuege[z]
        xy = [(l-quelle.ebene[0]) @ np.asarray(quelle.ebene[1:3]).T for l in quelle.linien[start:ende]]
        punkte = np.vstack(xy)
        skala = 7 / np.ptp(punkte[:, 1])
        for zug in xy:
            x, y = ((zug-punkte.min(axis=0))*skala).T
            linien.append(g.ebene[0] + (x+links)[:, None]*g.ebene[1] + (y+133.59)[:, None]*g.ebene[2])
        links += np.ptp(punkte[:, 0])*skala+1.42
    return replace(g, linien=linien)


def _strichdatei(quelle, g, ziel):
    def liste(daten):
        return json.dumps(daten, separators=(",", ":")).translate(str.maketrans("[]", "()"))
    punkte, indizes = [], []
    for l in g.linien:
        indizes.append(list(range(len(punkte)+1, len(punkte)+1+len(l))))
        punkte.extend(np.round(l/g.textfaktor, 9).tolist())
    text = Path(quelle).read_text(encoding="utf-8")
    start = text.index("#15095=TESSELLATED_CURVE_SET(")
    text = (text[:start] + f"#91234=COORDINATES_LIST('',{len(punkte)},{liste(punkte)});\n"
            + f"#15095=TESSELLATED_CURVE_SET('',#91234,{liste(indizes)})" + text[text.index(";", start):])
    ziel.write_text(text, encoding="utf-8")
    return str(ziel)


@pytest.mark.parametrize("art", ["striche", "fuellung", "fuellung_ohne_ebene"])
def test_grafische_kennung_in_beiden_semantischen_zeilen_und_originalgrafik(fenster, tmp_path, art):
    quelle, referenz, rein = _ohne_semantik(pfad("nist_ftc_07_asme1_ap242-e2.stp"), tmp_path/"Grafik.stp",
                                            validierung=art == "fuellung_ohne_ebene")
    rein.grafik[15098] = _anhaengen(rein.grafik, "10")
    ziel = tmp_path/"Gruppe 10 grafisch.stp"
    if art == "striche":
        quelle = _strichdatei(quelle, rein.grafik[15098], ziel)
    else:
        quelle = _als_fuellung(quelle, rein, ziel, [(15098, 15095, 15106)], ohne_ebene=art == "fuellung_ohne_ebene")
    f = fenster
    f.lade(quelle, warten=True)
    g = f.erg.grafik[15098]
    assert not any(p.semantisch for p in f.erg.pmi)
    assert bool(g.linien) == (art == "striche") and bool(g.dreiecke) == (art != "striche")
    assert (g.ebene is None) == (art == "fuellung_ohne_ebene")
    assert lies_verbund(g) == ("⌓ .070 A B C", "⌓ .015 A", "SIM REQT 10")
    for nr in (13706, 13747, 13788, 13887, 15098):
        p = next(p for p in f.erg.pmi if p.step_id == nr)
        f._pmi_befehl("semantisch", p)
        for soll in (p for p in referenz.pmi if p.step_id in referenz.grafik[nr].pmi_ids
                     and p.art == ("bezug" if nr != 15098 else "toleranz")):
            d = f._semantik_dialog
            if nr == 15098:
                assert d.v.beschreibung == "SIM REQT 10" and d.v.wert == pytest.approx(soll.wert)
                if art == "fuellung_ohne_ebene":
                    assert d.v.kurzer_geltungshinweis == "SIM REQT"
            f.ansicht.setze_auswahl([f.erg.modell.flaechen[i] for i in soll.flaechen])
            d._auswahl_uebernehmen()
            assert not d.fehler()
            d._pruefen()
    ausgabe = f.speichere_step_pmi(str(tmp_path/"Gruppe 10 semantisch.stp"), melden=False)
    neu = lade_alles(ausgabe)
    assert all(neu.modell.datei.get(i) == e for i,e in f.erg.modell.datei.entities.items())
    toleranzen = [p for p in neu.pmi if p.art == "toleranz" and p.step_id in neu.grafik[15098].pmi_ids]
    oben, unten = toleranzen
    assert oben.folgetoleranzen == [unten.step_id]
    assert oben.bezug_text() == "A|B|C" and unten.bezug_text() == "A"
    assert [p.wert for p in toleranzen] == pytest.approx([1.778, .381])
    original = [p for p in referenz.pmi if p.step_id in referenz.grafik[15098].pmi_ids and p.art == "toleranz"]
    assert [p.flaechen for p in toleranzen] == [p.flaechen for p in original]
    assert [v.name for v in neu.ansichten if {oben.step_id, unten.step_id} <= v.pmi_ids] == ["MBD_D"]
    for p in toleranzen:
        assert p.beschreibung == "SIM REQT 10" and not p.simultan_mit
        assert neu.modell.datei.get(p.step_id).args("GEOMETRIC_TOLERANCE")[1] == p.beschreibung
    assert lies_verbund(neu.grafik[15098]) == lies_verbund(g)
    if art == "fuellung_ohne_ebene":
        from OCC.Core.STEPControl import STEPControl_Reader
        from OCC.Core.StepDimTol import StepDimTol_GeometricTolerance
        leser = STEPControl_Reader()
        assert leser.ReadFile(ausgabe) == 1
        modell = leser.StepModel()
        ids = {p.step_id for p in toleranzen}
        gefunden = {}
        for i in range(1, modell.NbEntities()+1):
            ent = modell.Value(i)
            if (nr := modell.IdentLabel(ent)) in ids:
                gefunden[nr] = StepDimTol_GeometricTolerance.DownCast(ent).Description().ToCString()
        assert gefunden == dict.fromkeys(ids, "SIM REQT 10")


@pytest.mark.parametrize("gefuellt", [False, True])
def test_nummer_braucht_ziffern_und_keinen_aehnlichen_buchstaben(ftc07, tmp_path, gefuellt):
    from types import SimpleNamespace
    from programm.kern import p21
    from programm.kern.praesentation import lies_grafik

    grafik = lies_grafik(ftc07.datei)
    def erkenne(g):
        if gefuellt:
            quelle = _als_fuellung(ftc07.pfad, SimpleNamespace(grafik={15098: g}), tmp_path/"Suffix.stp",
                                   [(15098, 15095, 15106)])
            g = lies_grafik(p21.lese(quelle))[15098]
            assert g.dreiecke and not g.linien
        return lies_verbund(g)
    for text in ("1", "5", "7", "1750", "234", "689"):
        assert erkenne(_anhaengen(grafik, text))[-1] == "SIM REQT "+text
    for text in ("0", "1I", "1Q", "1O"):
        assert not erkenne(_anhaengen(grafik, text))
    eins = _anhaengen(grafik, "1")
    assert not erkenne(replace(eins, linien=eins.linien[:-1]))


def test_andere_gruppennummer_im_validierungstext_bleibt_ein_konflikt(ftc07):
    from programm.kern import pmi_ableiten, pmi_validierungstext
    from programm.kern.praesentation import lies_grafik

    g = lies_grafik(ftc07.datei)[15098]
    zeilen = lies_verbund(g)[:2]
    daten = [pmi_ableiten.aus_text([text], g.textfaktor) for text in zeilen]
    # Neues Dateimodell verwenden, damit die Sitzungsfixture unveraendert bleibt.
    from programm.kern import p21
    datei = p21.lese(ftc07.pfad)
    for ent in datei.of_type("DESCRIPTIVE_REPRESENTATION_ITEM"):
        args = ent.args()
        if args[0] == "equivalent unicode string" and "SIM REQT" in args[1]:
            args[1] = args[1].replace("SIM REQT", "SIM REQT 1")
    assert pmi_validierungstext.verbundtext_abgleich(datei,g,zeilen,daten,"SIM REQT 1") == (True, "")
    assert pmi_validierungstext.verbundtext_abgleich(datei,g,zeilen,daten,"SIM REQT 10") == (False, "")
