"""E57-Punktwolken (eigener Leser) an freien Testdateien von libE57Format."""

import numpy as np
import pytest

from tests.conftest import pfad


def test_wuerfel_float():
    from programm.kern import e57
    p = e57.lies(pfad("e57/ColouredCubeFloat.e57"))
    assert p.shape == (7680, 3) and np.allclose(p.min(0), -500) and np.allclose(p.max(0), 500)  # 1 m Wuerfel, mm
    # Punkte liegen auf der Oberflaeche: je Punkt mindestens eine Koordinate am Rand
    assert np.all(np.isclose(np.abs(p), 500, atol=1e-3).any(axis=1))


def test_hase_skalierte_ganzzahlen():
    """bunnyInt32: ScaledInteger, bitgepackt ueber mehrere Datenpakete und Seiten (CRC)."""
    from programm.kern import e57, punktwolke
    p = e57.lies(pfad("e57/bunnyInt32.e57"))
    assert len(p) == 30571 and np.allclose(p.min(0), [-94.69, 40.01, -61.87], atol=0.01)
    assert punktwolke.ist_punktwolke(pfad("e57/bunnyInt32.e57"))
    assert np.array_equal(punktwolke.lies_punkte(pfad("e57/bunnyInt32.e57")), p)


def test_keine_e57(tmp_path):
    from programm.kern import e57
    f = tmp_path / "x.e57"
    f.write_bytes(b"kein E57" + bytes(100))
    with pytest.raises(ValueError):
        e57.lies(str(f))
