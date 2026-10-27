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
