"""3D-Ansicht auf echtem Bildschirm (nur mit DG_BILDSCHIRM=1, nicht offscreen):
Navigation, Drehpunkt, Flaechenklick, Hervorhebung, Bild."""

import os
import subprocess
import sys

import pytest

from tests.conftest import WURZEL

pytestmark = pytest.mark.skipif(not os.environ.get("DG_BILDSCHIRM"), reason="nur mit DG_BILDSCHIRM=1")

SKRIPT = r'''
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])
os.environ["DG_EINSTELLUNGEN"] = os.path.join(tempfile.mkdtemp(), "e.ini")
from PySide6 import QtCore, QtGui, QtWidgets
app = QtWidgets.QApplication([])
from programm.ui.hauptfenster import Hauptfenster
f = Hauptfenster(); f.resize(1200, 800); f.show()
ergebnis = {}
def maus(typ, pos, knopf=QtCore.Qt.MouseButton.LeftButton):
    v = f.ansicht.viewer
    ev = QtGui.QMouseEvent(typ, QtCore.QPointF(*pos), v.mapToGlobal(QtCore.QPointF(*pos)), knopf,
                           knopf if typ != QtCore.QEvent.Type.MouseButtonRelease else QtCore.Qt.MouseButton.NoButton,
                           QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(v, ev)
def los():
    f.lade(os.path.join(sys.argv[1], "tests", "daten", "nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    QtCore.QTimer.singleShot(800, pruefe)
def pruefe():
    a = f.ansicht; cam = a.d.View.Camera()
    mitte = (a.viewer.width() / 2, a.viewer.height() / 2)
    e0 = cam.Eye().Coord()
    T = QtCore.QEvent.Type
    maus(T.MouseButtonPress, mitte); maus(T.MouseMove, (mitte[0] + 80, mitte[1] + 20)); maus(T.MouseButtonRelease, (mitte[0] + 80, mitte[1] + 20))
    ergebnis["drehen"] = cam.Eye().Coord() != e0
    s0 = cam.Scale()
    rad = QtGui.QWheelEvent(QtCore.QPointF(*mitte), a.viewer.mapToGlobal(QtCore.QPointF(*mitte)), QtCore.QPoint(), QtCore.QPoint(0, 240),
                            QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier, QtCore.Qt.ScrollPhase.NoScrollPhase, False)
    QtWidgets.QApplication.sendEvent(a.viewer, rad)
    ergebnis["zoomen"] = cam.Scale() < s0
    a.standard("oben")
    treffer = []
    a.flaeche_gewaehlt.connect(treffer.append)
    maus(T.MouseButtonPress, mitte); maus(T.MouseButtonRelease, mitte)
    ergebnis["klick"] = bool(treffer) and treffer[0] >= 0
    ergebnis["liste"] = len(f.pmi.tabelle.selectedIndexes()) >= 0
    pfad = os.path.join(tempfile.mkdtemp(), "b.png")
    ergebnis["bild"] = f.ansicht.bild(pfad) and os.path.getsize(pfad) > 1000
    print("ERGEBNIS", ergebnis, flush=True)
    app.quit()
QtCore.QTimer.singleShot(500, los)
app.exec()
'''


def test_navigation_und_klick():
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    r = subprocess.run([sys.executable, "-c", SKRIPT, WURZEL], capture_output=True, text=True, env=env, timeout=120)
    zeile = next((z for z in r.stdout.splitlines() if z.startswith("ERGEBNIS")), "")
    assert zeile, r.stdout[-2000:] + r.stderr[-2000:]
    erg = eval(zeile.split(" ", 1)[1])  # noqa: S307 - eigene Ausgabe
    assert all(erg.values()), erg
