"""Explosion nach Baugruppenebenen."""

from programm.kern.baum import Knoten
from programm.kern.explosion import versaetze


def _blatt(nr):
    return Knoten(f"T{nr}", None, nummer=nr)


def test_flach_wie_radial():
    baum = Knoten("M", None, [_blatt(1), _blatt(2)], baugruppe=True)
    w = versaetze(baum, {1: (-1, 0, 0), 2: (1, 0, 0)}, 1.0, faktor=1.0)
    assert w[1] == (-1, 0, 0) and w[2] == (1, 0, 0)
    assert versaetze(baum, {1: (0, 0, 0)}, 0.0) == {}


def test_ebenen_gestaffelt():
    # Unterbaugruppe U (Teile 2, 3 bei x = 10 +- 1) und Einzelteil 1 bei x = -10
    u = Knoten("U", None, [_blatt(2), _blatt(3)], baugruppe=True, nummer=4)
    baum = Knoten("M", None, [_blatt(1), u], baugruppe=True)
    mitten = {1: (-10, 0, 0), 2: (9, 0, 0), 3: (11, 0, 0)}
    halb = versaetze(baum, mitten, 0.5, faktor=1.0)
    # erste Haelfte: U bewegt sich als Einheit, die Teile darin bleiben zusammen
    assert halb[1] == (-10, 0, 0) and halb[2] == halb[3] == (10, 0, 0)
    voll = versaetze(baum, mitten, 1.0, faktor=1.0)
    assert voll[2] == (9, 0, 0) and voll[3] == (11, 0, 0)
