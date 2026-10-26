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
B = QtCore.Qt.MouseButton
def maus(typ, pos, knopf=B.LeftButton, knoepfe=None):
    v = f.ansicht.viewer
    if knoepfe is None:
        knoepfe = knopf if typ != QtCore.QEvent.Type.MouseButtonRelease else B.NoButton
    ev = QtGui.QMouseEvent(typ, QtCore.QPointF(*pos), v.mapToGlobal(QtCore.QPointF(*pos)), knopf, knoepfe,
                           QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(v, ev)
def los():
    f.lade(os.path.join(sys.argv[1], "tests", "daten", "nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    QtCore.QTimer.singleShot(800, pruefe)
def pruefe():
    try:
        pruefe_alles()
    except Exception as e:
        import traceback
        print("ERGEBNIS", {"fehler": False, "text": repr(e)}, flush=True)
        traceback.print_exc()
    app.quit()
def pruefe_alles():
    a = f.ansicht; cam = a.d.View.Camera()
    mitte = (a.viewer.width() / 2, a.viewer.height() / 2)
    e0 = cam.Eye().Coord()
    T = QtCore.QEvent.Type
    # CATIA: Mitte halten + links halten, ziehen = drehen
    beide = B.MiddleButton | B.LeftButton
    maus(T.MouseButtonPress, mitte, B.MiddleButton)
    maus(T.MouseButtonPress, mitte, B.LeftButton, beide)
    maus(T.MouseMove, (mitte[0] + 80, mitte[1] + 20), B.NoButton, beide)
    maus(T.MouseButtonRelease, (mitte[0] + 80, mitte[1] + 20), B.LeftButton, B.MiddleButton)
    maus(T.MouseButtonRelease, (mitte[0] + 80, mitte[1] + 20), B.MiddleButton, B.NoButton)
    ergebnis["drehen"] = cam.Eye().Coord() != e0
    c0 = cam.Center().Coord()
    maus(T.MouseButtonPress, mitte, B.MiddleButton)
    maus(T.MouseMove, (mitte[0] + 60, mitte[1]), B.NoButton, B.MiddleButton)
    maus(T.MouseButtonRelease, (mitte[0] + 60, mitte[1]), B.MiddleButton, B.NoButton)
    ergebnis["schieben"] = cam.Center().Coord() != c0
    # Ansichtswuerfel: Klick auf die Ecke (Mitte des Wuerfels in Iso) richtet aus, Ziehen dreht
    a.standard("vorne")
    w = (a.viewer.width() - 100, 100)
    maus(T.MouseButtonPress, w); maus(T.MouseButtonRelease, w)
    d = cam.Direction()
    ergebnis["wuerfel_klick"] = abs(d.Y() - 1.0) < 1e-6  # Klick auf "Vorne": Blick entlang +Y
    d0 = (d.X(), d.Y(), d.Z())
    maus(T.MouseButtonPress, w)
    for i in range(1, 6):
        maus(T.MouseMove, (w[0] + 12 * i, w[1]), B.NoButton, B.LeftButton)
    maus(T.MouseButtonRelease, (w[0] + 60, w[1]))
    d = cam.Direction()
    ergebnis["wuerfel_ziehen"] = (d.X(), d.Y(), d.Z()) != d0
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
    ergebnis["auswahl3d"] = len(a.auswahl3d) == 1
    a.richte_normal_aus(set(), list(a.auswahl3d))
    ergebnis["schnitt_auswahl"] = a.schnitt_aus_auswahl()
    a.schnitt("auswahl", a.schnitt_anteil_von_punkt("auswahl") or 0.5)
    ergebnis["schnitt_ebene"] = a._clip is not None
    a.schnitt(None)
    # Schnitt aus Blickrichtung folgt der Kamera
    a.schnitt_aus_blick(); a.schnitt("blick", 0.5)
    n0 = tuple(round(x, 6) for x in a.schnitt_eigen[1])
    maus(T.MouseButtonPress, mitte, B.MiddleButton)
    maus(T.MouseButtonPress, mitte, B.LeftButton, beide)
    maus(T.MouseMove, (mitte[0] + 60, mitte[1] + 30), B.NoButton, beide)
    maus(T.MouseButtonRelease, (mitte[0] + 60, mitte[1] + 30), B.LeftButton, B.MiddleButton)
    maus(T.MouseButtonRelease, (mitte[0] + 60, mitte[1] + 30), B.MiddleButton, B.NoButton)
    ergebnis["schnitt_live"] = tuple(round(x, 6) for x in a.schnitt_eigen[1]) != n0
    a.schnitt(None)
    ergebnis["liste"] = len(f.pmi.tabelle.selectedIndexes()) >= 0
    # Messmodus: Klick liefert Element und Punkt, Messung wird gezeichnet
    elemente = []
    a.element_gewaehlt.connect(lambda form, p: elemente.append((form, p)))
    f.aktionen["messen"].trigger(); f.messen.setze_modus("koordinaten")
    maus(T.MouseButtonPress, mitte); maus(T.MouseButtonRelease, mitte)
    ergebnis["punkt_unter_maus"] = a._punkt_unter_maus(*mitte) is not None  # Drehpunkt, Bildmitte
    ergebnis["messklick"] = bool(elemente) and len(f.messen.messungen) == 1 and bool(a._mess_ais)
    pfad = os.path.join(tempfile.mkdtemp(), "b.png")
    ergebnis["bild"] = f.ansicht.bild(pfad) and os.path.getsize(pfad) > 1000
    print("ERGEBNIS", ergebnis, flush=True)
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
    assert all(v for k, v in erg.items() if k != "text"), erg
