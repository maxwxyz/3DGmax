"""Blockuebertragung von Punkten und Dreiecken fuer gefuellte PMI, Farbkarte und Netzdateien."""

import numpy as np
import pytest
from programm.kern.laden import _poly


def test_dreiecksnetz_behaelt_praezision_indexfolge_und_orientierung():
    xyz = np.arange(36, dtype='float64').reshape(6, 6)[:, ::2] / 7.
    tris = np.array([[0, 3, 5], [2, 1, 0]], dtype='uint16')[:, ::-1]
    netz = _poly(xyz, tris)
    assert netz.NbNodes() == len(xyz) and netz.NbTriangles() == len(tris)
    np.testing.assert_array_equal([netz.Node(i).Coord() for i in range(1, 7)], xyz)
    np.testing.assert_array_equal([netz.Triangle(i).Get() for i in (1, 2)], tris + 1)
    assert _poly(xyz, []).NbTriangles() == 0
    for falsch in ([[0, 1, 6]], [[0, -1, 5]], [[2, 4]], [[0, np.nan, 2]]):
        with pytest.raises(ValueError):
            _poly(xyz, falsch)
