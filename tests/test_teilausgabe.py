"""Rechtsklick und Dateimenue mit einzelnen Vorkommen, Gruppen und Netzen."""

from pathlib import Path

import numpy as np
import pytest
from PySide6 import QtCore, QtTest, QtWidgets

from tests.conftest import pfad


def _mitten(formen):
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    punkte = []
    for form in formen:
        g = GProp_GProps()
        brepgprop.SurfaceProperties(form, g)
        punkte.append(tuple(g.CentreOfMass().Coord()))
    return sorted(punkte)


def test_step_aufruf_fuer_mehrfachauswahl(fenster, tmp_path, monkeypatch):
    from programm.ui.lader import lade_alles
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    baum = f.baum
    knoten = list(f.erg.baum.blaetter())
    a, b = next((a, b) for i, a in enumerate(knoten) for b in knoten[i+1:]
                if a.form.IsPartner(b.form) and not a.form.IsSame(b.form))
    assert not f.aktionen["teilausgabe"].isEnabled()
    baum.baum.setCurrentItem(baum._knoten[a.nummer])
    baum._knoten[b.nummer].setSelected(True)
    t = np.eye(4)
    t[2, 3] = 27
    f.baugruppe.lagen[a.nummer] = t
    ziel = str(tmp_path / "Paar.step")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (ziel, "STEP (*.step *.stp)"))
    f.aktionen["teilausgabe"].trigger()
    erg = lade_alles(ziel)
    beide = list(erg.baum.blaetter())
    assert sorted(k.name for k in beide) == sorted([a.name, b.name])
    a_mitte, = _mitten([a.form])
    soll = sorted([tuple(np.array(a_mitte)+t[:3, 3]), *_mitten([b.form])])
    assert np.asarray(_mitten([k.form for k in beide])) == pytest.approx(np.asarray(soll))
    assert len(f.erg.baum.kinder) and baum.exportauswahl() == {a.nummer,b.nummer}

    def export():
        menue = QtWidgets.QApplication.activePopupWidget()
        aktion = next(a for a in menue.actions() if "exportieren" in a.text())
        QtTest.QTest.mouseClick(menue, QtCore.Qt.MouseButton.LeftButton, pos=menue.actionGeometry(aktion).center())
    QtCore.QTimer.singleShot(0, export)
    def schliesse_menue():
        menue = QtWidgets.QApplication.activePopupWidget()
        if menue:
            menue.close()
    QtCore.QTimer.singleShot(1200, schliesse_menue)
    ziel = str(tmp_path / "Einzeln.step")
    c = next(k for k in knoten if k.nummer not in (a.nummer, b.nummer) and not k.hilfsgeometrie)
    it = baum._knoten[c.nummer]
    baum.baum.scrollToItem(it)
    baum._menue(baum.baum.visualItemRect(it).center())
    teil, = lade_alles(ziel).baum.blaetter()
    assert teil.name == c.name and baum.exportauswahl() == {c.nummer}
    assert _mitten([teil.form])[0] == pytest.approx(_mitten([c.form])[0])


def test_gruppe_und_kind_quelle_geschuetzt(fenster, tmp_path, monkeypatch):
    from programm.kern.baum import lies_baum
    from programm.kern.laden import lade_step
    f = fenster
    f.lade(pfad("baugruppe.stp"), warten=True)
    root = f.baum.baum.topLevelItem(0)
    f.baum.baum.setCurrentItem(root)
    root.child(0).setSelected(True)
    text = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda parent, titel, msg: text.append(msg))
    assert f.exportiere_baumauswahl(f.erg.pfad) is None and text
    ziel = f.exportiere_baumauswahl(str(tmp_path/"Alle.step"))
    assert sorted(k.name for k in lies_baum(lade_step(ziel)).blaetter()) == sorted(k.name for k in f.erg.baum.blaetter())


def test_netzexport(fenster, tmp_path, monkeypatch):
    from tests.test_verzahnung_mesh import _radnetz, _schreibe
    from programm.kern.laden import lade_modell
    datei = tmp_path / "Rad.obj"
    _schreibe(datei, [_radnetz(17)])
    f = fenster
    f.lade(str(datei), warten=True)
    f.baum.baum.setCurrentItem(f.baum.baum.topLevelItem(0))
    ziel = tmp_path/"Rad-export.stl"
    assert f.exportiere_baumauswahl(str(ziel))
    assert lade_modell(str(ziel)).flaechen
    anders = Path(tmp_path/"vorhanden.step")
    anders.write_text("ursprünglich")
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *args: None)
    assert not f.exportiere_baumauswahl(str(anders)) and anders.read_text() == "ursprünglich"


def test_step_flaechenfarbe_erhalten(tmp_path):
    from programm.kern.teilausgabe import speichere
    from programm.ui.lader import lade_alles
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    farbe = (.23, .66, .15)
    ziel = tmp_path / "Farbe.step"
    speichere(ziel, erg.baum, {k.nummer for k in erg.baum.blaetter()}, {}, erg.modell, {0: farbe})
    alt, = lade_alles(str(ziel)).farben.values()
    assert alt == pytest.approx(farbe)
