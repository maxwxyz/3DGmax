"""PMI-Farben je Farbschema: lesbar (Kontrast >= 4,5:1) auf beiden Farben des Hintergrundverlaufs, auch so, wie OCCT
den Verlauf gammakorrigiert zeigt; erzeugte und Datei-PMI unterscheidbar; eigene Farbe mit Warnung."""

import colorsys

import pytest

from programm.ui import thema

PMI_FARBEN = ("pmi", "pmi_erzeugt", "pmi_vorschau", "pmi_hervor")


@pytest.mark.parametrize("name", sorted(thema.THEMEN))
def test_pmi_farben_lesbar_auf_dem_hintergrund(name):
    t = thema.THEMEN[name]
    hg = thema.hintergrund_3d(t)
    assert len(hg) == 4  # oben, unten, je wie angegeben und gammakorrigiert
    for schluessel in PMI_FARBEN:
        for h in hg:
            assert thema.kontrast(t[schluessel], h) >= thema.MIN_KONTRAST, (name, schluessel, h)
        assert thema.lesbar(t[schluessel], hg) == tuple(t[schluessel])  # nichts nachzubessern


@pytest.mark.parametrize("name", sorted(thema.THEMEN))
def test_erzeugt_und_datei_unterscheidbar(name):
    t = thema.THEMEN[name]
    farbton = {k: colorsys.rgb_to_hsv(*t[k])[0] * 360 for k in PMI_FARBEN}
    for a in PMI_FARBEN:
        for b in PMI_FARBEN:
            if a < b:
                d = abs(farbton[a] - farbton[b])
                assert min(d, 360 - d) >= 25, (name, a, b)


def test_dunkles_schema_wirklich_dunkel():
    """OCCT zeigt den Verlauf gammakorrigiert: auch so bleibt der Hintergrund dunkel (frueher mittelgrau)."""
    for farbe in thema.hintergrund_3d(thema.THEMEN["dunkel"]):
        assert thema.leuchtdichte(farbe) < 0.06


def test_lesbar_und_schrift_auf():
    grau = ((0.65, 0.65, 0.65), (0.55, 0.55, 0.55))
    neu = thema.lesbar((0.5, 0.28, 0.72), grau)
    assert thema.kleinster_kontrast(neu, grau) >= thema.MIN_KONTRAST and neu != (0.0, 0.0, 0.0)
    unerreichbar = ((0.3, 0.3, 0.3), (0.75, 0.75, 0.75))
    assert thema.lesbar((0.5, 0.28, 0.72), unerreichbar) == (0.0, 0.0, 0.0)  # bestmoeglich
    assert thema.kontrast((1, 1, 1), (0, 0, 0)) == pytest.approx(21.0)
    assert thema.schrift_auf((0.84, 0.62, 1.0)) == (0.0, 0.0, 0.0)
    assert thema.schrift_auf((0.38, 0.14, 0.58)) == (1.0, 1.0, 1.0)


def test_ansicht_macht_schemafarben_lesbar(app):
    """Eigener Hintergrund: Schemafarben werden nachgebessert, die eigene PMI-Farbe bleibt wie gewaehlt."""
    from types import SimpleNamespace
    from programm.ui.ansicht3d import PlatzhalterAnsicht
    a = PlatzhalterAnsicht()
    a.setze_thema(thema.THEMEN["dunkel"])
    g = SimpleNamespace(farbe=(1.0, 1.0, 1.0), erzeugt=True, vorschau=False)
    assert a.pmi_farbe(g) == thema.THEMEN["dunkel"]["pmi_erzeugt"]
    hell = ((0.95, 0.95, 0.95), (0.85, 0.85, 0.85))
    a.setze_farben(None, hell)
    assert thema.kleinster_kontrast(a.pmi_farbe(g), thema.hintergrund_3d({}, hell)) >= thema.MIN_KONTRAST
    a.setze_farben((1.0, 1.0, 0.0), hell)
    assert a.pmi_farbe(SimpleNamespace(farbe=None, erzeugt=False, vorschau=False)) == (1.0, 1.0, 0.0)


def test_einstellungen_warnen_bei_wenig_kontrast(app, tmp_path):
    from PySide6 import QtCore
    from programm.ui.einstellungen import EinstellungenDialog
    ein = QtCore.QSettings(str(tmp_path / "e.ini"), QtCore.QSettings.Format.IniFormat)
    ein.setValue("thema", "dunkel")
    ein.setValue("pmi_eigen", True)
    ein.setValue("pmi_eigene_farbe", "#202020")
    d = EinstellungenDialog(ein)
    assert not d.pmi_warnung.isHidden() and "Kontrast" in d.pmi_warnung.text()
    d.pmi_farbe.setze("#ffd040")
    assert d.pmi_warnung.isHidden()
    d.pmi_eigen.setChecked(False)
    d.pmi_farbe.setze("#202020")
    assert d.pmi_warnung.isHidden()  # ohne eigene Farbe kein Hinweis
