"""Unbeschriftete STEP-Winkelangaben aus Originalgrafik und Dreiecksflaechen pruefen."""

import json
from pathlib import Path

import numpy as np
import pytest

from programm.kern.pmi_lesen import lies_pmi_xcaf
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_grafische_step_reparatur import _als_fuellung, _ohne_semantik, _ohne_zeichenebene


def _strichwinkel():
    sechs = [(6, 8), (3, 8), (1, 6), (0, 4), (0, 1), (1, 0), (4, 0), (6, 1),
             (6, 3), (5, 4), (2, 4), (0, 3)]
    null = [(11, 8), (13, 8), (15, 7), (15, 1), (13, 0), (11, 0), (9, 1), (9, 7), (11, 8)]
    winkel = np.linspace(0, 2*np.pi, 9)
    grad = np.column_stack((17 + np.cos(winkel), 7 + np.sin(winkel)))
    return [np.column_stack((linie, np.zeros(len(linie)))) for linie in (sechs, null, grad)]


def test_offenes_gradzeichen_bleibt_ungeklaert(app):
    from programm.kern.pmi_strichschrift import lies_schrift
    from programm.kern.praesentation import Grafik
    from scipy.spatial.transform import Rotation
    drehung = Rotation.from_rotvec([.49, -.26, .65]).as_matrix()
    linien = [l @ drehung.T + [37., 14., 23.] for l in _strichwinkel()]
    assert lies_schrift(Grafik(0, linien=linien)) == "60°"
    linien[-1] = linien[-1][:-3]
    assert lies_schrift(Grafik(0, linien=linien)) == ""


@pytest.mark.parametrize("art", ["original", "dreiecke", "striche"])
def test_winkel_ohne_ebene_mit_beiden_massflaechen(art, tmp_path, fenster):
    gefuellt = art == "dreiecke"
    datei, ref, rein = _ohne_semantik(pfad("nist_ctc_01_asme1_ap242-e1.stp"),
                                      tmp_path / "Grafik.stp", validierung=False)
    if gefuellt:
        datei = _als_fuellung(datei, rein, tmp_path / "Gefuellt.stp", [(618, 473, 572)])
    text = Path(datei).read_text()
    if gefuellt:
        # Der erste Kurvensatz enthaelt jetzt alle urspruenglichen Linien als Dreiecke.
        text = text.replace("((#473,#359,#474,#360))", "((#473,#359,#360))")
    # Vorhandene Z-Verschiebung direkt an die Punkte schreiben.
    for nr in ([417, 419] if gefuellt else [416, 417, 418, 419]):
        start = text.index(f"#{nr}=COORDINATES_LIST(")
        ende = text.index(";", start)
        text = text[:start] + text[start:ende].replace(",0.)", ",-50.)") + text[ende:]
    text = _ohne_zeichenebene(text.replace("#572,#618,", "#618,"), 618, 572)
    text = text.replace("REPOSITIONED_TESSELLATED_ITEM(#4195)", "").replace("'Angular Size.1'", "''")
    if art == "striche":
        linien = [l + [75., -215., -50.] for l in _strichwinkel()]
        punkte = np.vstack(linien)
        def liste(a):
            return json.dumps(a).translate(str.maketrans("[]", "()"))
        grenzen = np.r_[0, np.cumsum([len(l) for l in linien])]
        zuege = [list(range(a+1, b+1)) for a, b in zip(grenzen.tolist(), grenzen[1:].tolist())]
        pos = text.rindex("ENDSEC;")
        text = (text[:pos] + f"#90000=COORDINATES_LIST('',{len(punkte)},{liste(punkte.tolist())});\n"
                + f"#90001=TESSELLATED_CURVE_SET('',#90000,{liste(zuege)});\n" + text[pos:])
        text = text.replace("((#473,#359,#474,#360))", "((#473,#90001))")
    quelle = tmp_path / "Winkel ohne Schreibebene.stp"
    quelle.write_text(text)
    fenster.lade(str(quelle), warten=True)
    vorher = fenster.erg
    g = vorher.grafik[618]
    assert g.ebene is None and not g.platzhalter and g.pmi_ids == {618} and not g.name
    assert bool(g.dreiecke) == (art != "striche") and bool(g.linien) != gefuellt
    assert all(np.allclose(p[:, 2], -50) for p, _ in g.dreiecke)
    original = next(p for p in vorher.pmi if p.step_id == 618)
    assert not original.semantisch
    ansichten = {a.step_id for a in vorher.ansichten if 618 in a.pmi_ids}
    fenster._pmi_befehl("semantisch", original)
    dialog = fenster._semantik_dialog
    assert not dialog.v.validierungstexte and not dialog.v.nennwert_aus_geometrie
    erwartet = ("60°", 60., None, None) if art == "striche" else ("60°±0.5°", 60., .5, -.5)
    assert (dialog.v.ocr_text, dialog.v.nennwert, dialog.v.oben, dialog.v.unten) == erwartet
    soll, = [p for p in ref.pmi if p.step_id in ref.grafik[618].pmi_ids]
    assert soll.typ == "Location_Angular" and len(soll.flaechen) == 2
    dialog.typ.setCurrentIndex(dialog.typ.findData(soll.typ))
    fenster.ansicht.setze_auswahl([vorher.modell.flaechen[i] for i in soll.flaechen])
    dialog._auswahl_uebernehmen()
    assert not dialog.fehler()
    dialog._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Winkel mit PMI.stp"), melden=False)
    neu = lade_alles(ziel)
    assert all(neu.modell.datei.get(i) == e for i, e in vorher.modell.datei.entities.items())
    sem, = [p for p in neu.pmi if p.semantisch and p.step_id in neu.grafik[618].pmi_ids]
    assert ansichten and {a.step_id for a in neu.ansichten if sem.step_id in a.pmi_ids} == ansichten
    nativ, = [p for p in lies_pmi_xcaf(neu.modell) if p.typ == soll.typ]
    for p in (sem, nativ):
        assert p.typ == soll.typ and p.flaechen == soll.flaechen
        assert p.nennwert == pytest.approx(60.)
        if art == "striche":
            assert p.oben is None and p.unten is None
        else:
            assert (p.oben, p.unten) == pytest.approx((.5, -.5))
