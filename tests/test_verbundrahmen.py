"""Zusammengesetzte Toleranzen mit getrennten semantischen Rahmenzeilen."""

from pathlib import Path

import pytest

from tests.conftest import pfad


@pytest.mark.parametrize("variante", ["umbenannt", "getrennt", "umgekehrt", "anderes_ziel"])
def test_verbundrahmen_vergleich_der_beiden_step_dateien(ftc07, tmp_path, variante):
    from programm.kern.laden import lade_step
    from programm.kern.pmi_step import lies_toleranzen
    from programm.kern.vergleich_pmi import GEAENDERT, vergleiche_pmi

    quelle = Path(pfad("nist_ftc_07_asme1_ap242-e2.stp"))
    data = quelle.read_text(encoding="utf-8")
    original = "#14486=GEOMETRIC_TOLERANCE_RELATIONSHIP('composite','',#14472,#14483);"
    assert data.count(original) == 1
    if variante == "umbenannt":
        import re
        data = re.sub(r"#144(72|83)\b", r"#900\1", data)
    elif variante == "getrennt":
        data = data.replace(original, "")
    elif variante == "umgekehrt":
        data = data.replace(original, original.replace("#14472,#14483", "#14483,#14472"))
    else:
        data = data.replace(original, original.replace("#14483", "#14623"))
    ziel = tmp_path/"Rahmen.stp"
    ziel.write_text(data, encoding="utf-8")
    alt = lies_toleranzen(ftc07)
    neu = lies_toleranzen(lade_step(str(ziel)))
    for gruppe in (alt, neu):
        for nr, p in enumerate(gruppe, 1):
            p.nummer = nr
    oben, unten = [p for p in alt if p.step_id in (14472, 14483)]
    assert oben.folgetoleranzen == [unten.step_id] and not unten.folgetoleranzen
    assert (oben.wert, unten.wert) == pytest.approx((1.524, .381))
    assert (oben.bezug_text(), unten.bezug_text()) == ("A|B|C", "A")
    aenderungen = [a for a in vergleiche_pmi(alt, neu) if a.status == GEAENDERT]
    erwartet = {"umbenannt": set(), "getrennt": {14472}, "umgekehrt": {14472, 14483}, "anderes_ziel": {14472}}
    assert {a.alt.step_id for a in aenderungen} == erwartet[variante]
    assert all([k for k, _, _ in a.felder] == ["folgetoleranzen"] for a in aenderungen)
    if variante == "getrennt":
        assert aenderungen[0].felder[0][1:] == (f"PMI {unten.nummer}", "–")


def test_verbund_beim_hinzuladen_und_in_der_pmi_liste(ftc07, fenster):
    from programm.kern.pmi_step import lies_toleranzen
    from programm.kern.zusammenfuegen import _pmi_umrechnen

    pmis = [p for p in lies_toleranzen(ftc07) if p.step_id in (14472, 14483)]
    for nr, p in enumerate(pmis, 1):
        p.nummer = nr
    _pmi_umrechnen(pmis, 40, 100000, 10, None)
    assert pmis[0].folgetoleranzen == [pmis[1].step_id] == [114483]
    fenster.pmi.zeige(pmis)
    t = fenster.pmi.tabelle
    spalte = fenster.pmi.SPALTEN.index("Wert")
    assert "Nachgeordnete Toleranz im Verbundrahmen: 12" in t.item(0, spalte).toolTip()
    assert "Übergeordnete Toleranz im Verbundrahmen: 11" in t.item(1, spalte).toolTip()


def test_zwei_gleiche_verbundrahmen_in_anderer_dateireihenfolge():
    from programm.kern.pmi import Pmi
    from programm.kern.vergleich_pmi import GLEICH, vergleiche_pmi

    def rahmen(oben, unten):
        return (Pmi("toleranz", "Position", wert=.2, step_id=oben, folgetoleranzen=[unten]),
                Pmi("toleranz", "Position", wert=.05, step_id=unten))
    a, b = rahmen(1, 2), rahmen(3, 4)
    c, d = rahmen(9, 8), rahmen(7, 6)
    vergleich = vergleiche_pmi([*a, *b], [c[0], d[1], d[0], c[1]])
    assert len(vergleich) == 4 and all(p.status == GLEICH for p in vergleich)


def test_punkt_hinweislinie_braucht_belegten_punkt_und_unverzweigten_schaft():
    import numpy as np
    from programm.kern.pmi_hinweislinie import punkt_hinweislinie

    y, x = np.mgrid[:150, :170]
    d = np.hypot(x-20, y-125)
    schaft = (abs(x-(20+(125-y)*.45)) <= .55) & (y >= 45) & (y <= 125)
    schaft |= (y == 45) & (x >= 56) & (x <= 76)
    symbol = (79, 10, 115, 81)
    voll = schaft | (d <= 7)
    assert punkt_hinweislinie(voll, symbol, 2)
    assert not punkt_hinweislinie(schaft | ((d <= 7) & (d >= 5.5)), symbol, 2)
    ast = (y == 95) & (x >= 33) & (x <= 54)
    assert not punkt_hinweislinie(voll | ast, symbol, 2)


@pytest.mark.parametrize("gefuellt", [False, True])
def test_unlesbare_materialbedingung_wird_keine_zusaetzliche_null(ftc07, tmp_path, gefuellt):
    from dataclasses import replace
    from types import SimpleNamespace
    from programm.kern.laden import lade_step
    from programm.kern.pmi_verbundschrift import lies_verbund
    from programm.kern.praesentation import lies_grafik
    from tests.test_grafische_step_reparatur import _als_fuellung

    g = lies_grafik(ftc07.datei)[14735]
    assert lies_verbund(g) == ("⌖ ⌀.06Ⓜ E B C", "⌖ ⌀.02Ⓜ E B C")
    # Zug 16 ist der untere Ring, Zug 17 das eingeschriebene M.
    m = g.linien[17]
    for innen in ([], [m[[0, 1, 3, 4]]]):
        defekt = replace(g, linien=[*g.linien[:17], *innen, *g.linien[18:]])
        if gefuellt:
            datei = _als_fuellung(pfad("nist_ftc_07_asme1_ap242-e2.stp"), SimpleNamespace(grafik={14735: defekt}),
                                  tmp_path/"Defekter Ring.stp", [(14735, 14732, 14743)])
            defekt = lies_grafik(lade_step(datei).datei)[14735]
            assert defekt.dreiecke and not defekt.linien
        assert not lies_verbund(defekt)
