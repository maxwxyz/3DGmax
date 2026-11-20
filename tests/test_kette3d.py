"""3D-Toleranzkette als Folge von Lagen: Geometrie, Empfindlichkeiten (Hebelwirkung von Kippungen), Linearisierung."""

import math

import numpy as np

from programm.kern import kette3d as k3
from programm.kern import toleranzkette as tk


def _turm(schluss="x"):
    """Sockel 20 hoch, darauf um rz 90° gedreht ein Arm 100 lang in X; Kippung des Sockels um Y ±0,1°."""
    return k3.Kette3D([k3.glied("Sockel", z=(20, 0.05, -0.05), ry=(0, 0.1, -0.1)),
                       k3.glied("Arm", x=(100, 0.1, -0.1), rz=90)], punkt=(0, 0, 0), schluss=schluss)


def test_lage_und_hebelwirkung():
    k = _turm()
    p, _ = k3.funktionspunkt(k)
    assert np.allclose(p, [100, 0, 20])  # Arm entlang X des (ungedrehten) Sockels
    e = k3.empfindlichkeiten(k)
    # Kippung des Sockels um Y (an seinem oberen Ende): das Armende entlang X bewegt sich in X nur zweiter Ordnung
    assert abs(e[(0, "ry")]) < 1e-6
    assert abs(e[(1, "x")] - 1.0) < 1e-6 and abs(e[(0, "z")]) < 1e-9
    kz = _turm("z")
    assert abs(k3.empfindlichkeiten(kz)[(0, "ry")] + 100 * math.pi / 180) < 1e-6  # Armende sinkt bei +ry


def test_linearisiert_und_nichtlinear():
    k = _turm("z")
    e = tk.berechne(k3.als_glieder(k), proben=20_000)
    assert abs(e.nenn - 20) < 1e-6
    halb = 0.05 + 100 * math.pi / 180 * 0.1
    assert abs((e.wc_max - e.wc_min) / 2 - halb) < 1e-4
    mc = k3.monte_carlo(k, 4000)
    assert abs(np.std(mc) - e.rss / 3) / (e.rss / 3) < 0.1
    assert k3.von_dict(k3.als_dict(k)) == k
    w = k3.Kette3D(k.glieder, richtung=(0, 0, 1), schluss="winkel", ziel=(0, 0, 1))
    assert abs(k3.schlussgroesse(w)) < 1e-9 and abs(k3.schlussgroesse(w, {(0, "ry"): 0.1}) - 0.1) < 1e-6


def test_abstand_null_nicht_linearisierbar():
    """Abstand am Nennwert 0: Empfindlichkeiten 0 (Betrag nicht differenzierbar), Monte Carlo zeigt die Streuung."""
    k = k3.Kette3D([k3.glied("Platte", x=(40, 0.1, -0.1), y=(0, 0.1, -0.1))], schluss="abstand", ziel=(40, 0, 0))
    assert all(abs(d) < 1e-6 for d in k3.empfindlichkeiten(k).values())
    assert np.quantile(k3.monte_carlo(k, 2000), 0.99) > 0.05


def test_wiggle_bilder_und_anzeige():
    """Wiggle der 3D-Kette (kern.kette3d_anzeige): Worst Case pendelt zwischen den nichtlinearen Ecken, Glied fuer
    Glied bewegt je Glied nur seine Komponenten; Ueberhoehung nur in der Anzeige; Teile folgen ihrem Glied."""
    from programm.kern import kette3d_anzeige as ka
    k = _turm("z")
    lo, hi = ka.bereich(k)
    e = tk.berechne(k3.als_glieder(k), proben=2000)
    assert abs(lo - e.wc_min) < 1e-3 and abs(hi - e.wc_max) < 1e-3
    b = ka.bilder(k, "wc")
    werte = [x.wert for x in b]
    assert len(b) == ka.SCHRITTE and min(werte) >= lo - 1e-9 and max(werte) <= hi + 1e-9
    assert abs(max(werte) - hi) < 1e-9 and abs(min(werte) - lo) < 1e-9  # Sinus erreicht beide Grenzen
    je_glied = ka.bilder(k, "glieder")
    assert {x.glied for x in je_glied} == {0, 1} and all({i for i, _ in x.werte} == {x.glied} for x in je_glied)
    assert ka.faktor(k) > 1 and ka.groesse(k) > 100
    k.glieder[0].teil = 7
    w = ka.anzeige_werte(k, b[ka.SCHRITTE // 4].werte, 10.0)
    assert abs(abs(w[(0, "ry")]) - 10 * 0.1) < 1e-9  # um den Faktor ueberhoeht
    m = ka.teil_bewegungen(k, w)
    assert set(m) == {7} and not np.allclose(m[7], np.eye(4))
    assert np.allclose(ka.teil_bewegungen(k, ka.anzeige_werte(k, {}))[7], np.eye(4))  # Nennlage: keine Bewegung
    assert k3.von_dict(k3.als_dict(k)).glieder[0].teil == 7
    texte = [t for *_, t, _f, _b in ka.linien(k) if t]
    assert {"X", "Y", "Z", "Sockel", "Arm"} <= set(texte) and any(t.startswith("Funktionspunkt") for t in texte)
    assert ka.grund(k) == "" and ka.grund(k3.Kette3D([k3.glied("A", x=5)])) != ""


def test_ausrichtung_zu_modellachsen():
    """Glied aus dem Zusammenbau an ein gedrehtes Kettenende: ein Ausrichtungsglied fuehrt zum Teilpunkt und
    zurueck zu den Modellachsen."""
    k = _turm("z")
    ziel = np.array([30.0, 40.0, 50.0])
    g = k3.ausrichtung(k, ziel, "Ausrichtung")
    assert g is not None
    k.glieder.append(g)
    r, t = k3.ende_welt(k)
    assert np.allclose(r, np.eye(3), atol=1e-9) and np.allclose(t, ziel)
    assert k3.ausrichtung(k, ziel + 1, "x") is None  # Ende schon achsparallel
