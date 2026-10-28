"""2D-Toleranzkette als Vektorzug: Geometrie, Empfindlichkeiten, Linearisierung und nichtlinearer Monte Carlo."""

import math

import numpy as np

from programm.kern import kette2d as k2
from programm.kern import toleranzkette as tk


def _winkelkette(schluss="abstand"):
    """Rechter Winkel: 30 nach X, dann 40 nach Y -> Schlussabstand 50 (3-4-5)."""
    return k2.Kette2D([k2.Segment("a", 30, 0.1, -0.1), k2.Segment("b", 40, 0.1, -0.1, 90, 0.5, -0.5)], schluss)


def test_geometrie_und_empfindlichkeit():
    k = _winkelkette()
    assert np.allclose(k2.punkte(k)[-1], [30, 40]) and abs(k2.schlussgroesse(k) - 50) < 1e-9
    e = k2.empfindlichkeiten(k)
    assert abs(e[(0, "laenge")] - 0.6) < 1e-6 and abs(e[(1, "laenge")] - 0.8) < 1e-6  # cos/sin des Schlussvektors
    # Winkel b (Grad): dS/dθ = -30·40/50 · π/180 (Abstand nimmt ab, wenn b nach innen dreht)
    assert abs(e[(1, "winkel")] - (-24 * math.pi / 180)) < 1e-5
    assert abs(k2.schlussgroesse(_winkelkette("x")) + 30) < 1e-9 and abs(k2.schlussgroesse(_winkelkette("winkel")) - 90) < 1e-9


def test_linearisiert_wie_nichtlinear():
    k = _winkelkette()
    glieder = k2.als_glieder(k)
    e = tk.berechne(glieder, cp=1.0, proben=50_000)
    assert abs(e.nenn - 50) < 1e-6  # Linearisierungsrest bringt den Nennwert
    wc = 0.6 * 0.1 + 0.8 * 0.1 + 24 * math.pi / 180 * 0.5
    assert abs((e.wc_max - e.wc_min) / 2 - wc) < 1e-4
    mc = k2.monte_carlo(k, 50_000)
    assert abs(np.std(mc) - (e.rss / 3)) / (e.rss / 3) < 0.05  # kleine Toleranzen: linear ≈ nichtlinear
    assert k2.von_dict(k2.als_dict(k)) == k
