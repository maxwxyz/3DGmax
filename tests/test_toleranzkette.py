"""Toleranzkette: Verteilungen je Glied und Anwendbarkeit des statistischen Ergebnisses (ohne Qt)."""

import math

import numpy as np
import pytest

from programm.kern import toleranzkette as tk


@pytest.mark.parametrize("art", ["normal", "dreieck", "trapez", "gleich"])
def test_sigma_passt_zur_stichprobe(art):
    g = tk.Glied("x", 10.0, 10.1, 9.9, verteilung=art, form=0.4)
    werte = g.ziehe(np.random.default_rng(3), 400_000)
    assert abs(werte.std() - g.sigma()) < 0.01 * g.sigma() and abs(werte.mean() - 10.0) < 1e-3
    if art != "normal":  # begrenzte Verteilungen bleiben im Toleranzfeld
        assert werte.min() >= 9.9 - 1e-12 and werte.max() <= 10.1 + 1e-12


def test_trapez_grenzfaelle_und_faktoren():
    t = 0.2
    dreieck = tk.Glied("d", 0, t / 2, -t / 2, verteilung="dreieck").sigma()
    gleich = tk.Glied("g", 0, t / 2, -t / 2, verteilung="gleich").sigma()
    assert math.isclose(tk.Glied("a", 0, t / 2, -t / 2, verteilung="trapez", form=0.0).sigma(), dreieck)
    assert math.isclose(tk.Glied("b", 0, t / 2, -t / 2, verteilung="trapez", form=1.0).sigma(), gleich)
    # Verteilungsfaktoren c = 3 sigma / (T/2) nach Scholz: Dreieck 1,225, gleich 1,732
    assert abs(3 * dreieck / (t / 2) - 1.2247) < 1e-3 and abs(3 * gleich / (t / 2) - 1.7321) < 1e-3


def test_anwendbarkeit_nach_wirksamen_beitragsleistern():
    vier = [tk.Glied(str(i), 10, 10.1, 9.9) for i in range(4)]
    e = tk.berechne(vier)
    assert abs(e.n_eff - 4) < 1e-9 and e.statistisch and "statistisch" in tk.anwendbar_text(e)
    # ein dominierendes Glied und drei kleine: zaehlt kaum mehr als eines
    dominiert = [tk.Glied("gross", 10, 10.5, 9.5)] + [tk.Glied(str(i), 10, 10.01, 9.99) for i in range(3)]
    e = tk.berechne(dominiert)
    assert 1 <= e.n_eff < 1.1 and not e.statistisch and "arithmetisch" in tk.anwendbar_text(e)
    assert tk.berechne([]).n_eff == 0
    csv = tk.als_csv(dominiert, e)
    assert "arithmetisch" in csv and "Wirksame Beitragsleister" in csv


def test_monte_carlo_mit_gemischten_verteilungen():
    glieder = [tk.Glied("a", 20, 20.1, 19.9, verteilung="gleich"), tk.Glied("b", 5, 5.05, 4.95, -1, verteilung="dreieck"),
               tk.Glied("c", 8, 8.06, 7.94, verteilung="trapez", form=0.5), tk.Glied("d", 2, 2.03, 1.97)]
    e = tk.berechne(glieder)
    assert abs(e.nenn - 25) < 1e-9 and abs(e.mc_std - e.rss / 3) < 0.02 * e.rss / 3
    assert e.wc_min < e.mc_min < e.mc_max < e.wc_max and abs(sum(e.anteile) - 1) < 1e-9


def test_alte_projekte_ohne_form():
    g = tk.Glied(**{"name": "x", "nenn": 1.0, "hoechst": 1.1, "mindest": 0.9, "verteilung": "gleich"})
    assert g.form == 0.5


def test_werkstoffe_stichworte_und_step():
    from programm.kern import p21, werkstoffe as ws
    from tests.conftest import pfad
    assert ws.bibliotheksname("S235JR") == "Stahl" and ws.bibliotheksname("EN AW-6082 T6") == "Aluminium"
    assert ws.bibliotheksname("1.4301") == "Nichtrostender Stahl" and ws.bibliotheksname("CuZn39Pb3") == "Messing"
    assert ws.bibliotheksname("C75S Federstahl") == "Stahl" and ws.bibliotheksname("Holz") is None
    stoffe = ws.werkstoffe_aus_step(p21.lese(pfad("getriebe.stp")))
    assert stoffe == {"Welle": "42CrMo4", "Zahnrad": "16MnCr5", "Distanzhülse": "EN AW-6082", "Wälzlager": "100Cr6",
                      "Sicherungsring": "C75S Federstahl"}  # Umlaute: OCCT schreibt UTF-8
    assert abs(ws.laengenaenderung(23.0, 100.0, 120.0) - 0.23) < 1e-12


def test_getriebe_kette_temperatur_stellglied_datei(tmp_path):
    import copy
    from programm.kern import kette_datei
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    assert k.modell.endswith("getriebe.stp") and len(k.glieder) == 6
    assert [g.richtung for g in k.glieder] == [-1, -1, -1, 1, 1, -1]  # aus dem Schlussmass erzeugt
    e = tk.berechne(k.glieder, anforderung=k.anforderung)
    assert abs(e.nenn - 0.4) < 1e-9 and abs(e.wc_min) < 1e-9 and abs(e.wc_max - 1.1) < 1e-9  # Lehrbuch: 0 ... 1,1
    heiss = tk.berechne(tk.thermisch(k.glieder, k.alpha(), 100.0))
    # Stahl wirkt ueber 106,5 + 1,3 - 51 - 12 - 1,2 = 43,6 mm, die Alu-Huelse (43,2 mm) dagegen: Spiel kleiner
    erwartet = (11.5 * 43.6 - 23.0 * 43.2) * 1e-6 * 80
    assert abs((heiss.nenn - e.nenn) - erwartet) < 1e-6
    kuehl = tk.berechne(tk.thermisch(k.glieder, k.alpha(), 100.0, {"Welle": 60.0}))  # Welle kuehler
    assert kuehl.nenn < heiss.nenn
    g = copy.deepcopy(k.glieder)
    g[-1].stellglied = True
    lo, hi = tk.stellbereich(g, (0.05, 1.1))
    assert lo <= hi and abs(hi - lo - (1.05 - (1.1 - 0.06))) < 1e-9
    feder = tk.bereich_glied("Feder", 8.0, 6.0, -1, True)
    assert feder.mindest == 6.0 and feder.hoechst == 8.0 and feder.verteilung == "gleich" and feder.quelle == "bereich"
    ziel = kette_datei.speichere(str(tmp_path / "x"), kette_datei.KettenDatei(g, 1.33, (0.05, 1.1), (-20.0, 100.0),
                                                                               k.werkstoffe, k.modell))
    k2 = kette_datei.lade(ziel)
    assert ziel.endswith(".3dgkette") and k2.cp == 1.33 and k2.temperaturen == (-20.0, 100.0)
    assert k2.glieder[-1].stellglied and k2.glieder[0].flaechen == k.glieder[0].flaechen and k2.alpha() == k.alpha()


def test_richtungen_aus_schlussmass_mit_falschen_vorzeichen():
    from programm.kern import kette_datei
    from programm.kern.laden import lade_modell
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    m = lade_modell(pfad("getriebe.stp"))
    durcheinander = [k.glieder[i] for i in (3, 0, 5, 1, 4, 2)]
    for g in durcheinander:
        g.richtung = 1
    lager, ring = k.glieder[0].flaechen[0], k.glieder[-1].flaechen[0]
    # Flaechen des Schlussmasses: rechte Lagerflaeche und linke Ringflaeche (je die naeher am Spalt)
    from programm.kern.toleranzkette import _ebene_oder_achse
    x = lambda i: float(_ebene_oder_achse(m.flaechen[i])[1][0])  # noqa: E731
    lager = max(k.glieder[0].flaechen, key=x)
    ring = min(k.glieder[-1].flaechen, key=x)
    reihe, hinweise = tk.richtungen_aus_schlussmass(durcheinander, m, lager, ring)
    assert not hinweise and [g.name[:2] for g in reihe] == ["M3", "M2", "M1", "M4", "M5", "M6"]
    assert [g.richtung for g in reihe] == [-1, -1, -1, 1, 1, -1]
    assert abs(tk.berechne(reihe).nenn - 0.4) < 1e-9
