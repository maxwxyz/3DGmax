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
    a.animation = False  # Pruefungen erwarten die Kamera sofort am Ziel
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
    w = (a.viewer.width() - 80, 80)
    ergebnis["wuerfel_treffer"] = a._wuerfel_unter_maus(*w) is not None
    kante = (a._wuerfel.Size() + a._wuerfel.BoxFacetExtension()) / 2 / getattr(a, "_wuerfel_k", 1.0)
    unten = (w[0], w[1] + round(kante))  # Mitte der abgeschraegten unteren Kante vorne/unten
    maus(T.MouseButtonPress, unten); maus(T.MouseButtonRelease, unten)
    d = cam.Direction()
    ergebnis["wuerfel_klick"] = abs(d.Y() - 1.0) > 0.1 and abs(d.Z()) > 0.1  # schraeg von vorne unten
    d0 = (d.X(), d.Y(), d.Z())
    maus(T.MouseButtonPress, w)
    for i in range(1, 6):
        maus(T.MouseMove, (w[0] + 12 * i, w[1]), B.NoButton, B.LeftButton)
    maus(T.MouseButtonRelease, (w[0] + 60, w[1]))
    d = cam.Direction()
    ergebnis["wuerfel_ziehen"] = (d.X(), d.Y(), d.Z()) != d0
    # Kameraverlauf: vorne -> oben, zurueck -> vorne, vor -> oben; Perspektive umschaltbar
    a.standard("vorne"); a._kamera_merken()
    a.standard("oben"); a._kamera_merken()
    ok = a.kamera_zurueck() and abs(cam.Direction().Y() - 1.0) < 1e-6
    ok = ok and a.kamera_vor() and abs(cam.Direction().Z() + 1.0) < 1e-6
    a.setze_perspektive(True)
    from OCC.Core.Graphic3d import Graphic3d_Camera
    ok = ok and cam.ProjectionType() == Graphic3d_Camera.Projection_Perspective
    a.setze_perspektive(False)
    ergebnis["kameraverlauf"] = ok
    a.setze_auswahl([f.erg.modell.flaechen[0]])
    ergebnis["schnittbox"] = a.schnittbox_um_auswahl() and len(a._box_ebenen) == 6
    a.schnittbox(None)
    ergebnis["schnittbox_aus"] = a._box_ebenen == []
    a.setze_auswahl([])
    # Drehpunkt per Mitteltaste: bleibt beim Zoomen und Verschieben fest, Kreuz sichtbar
    a.standard("iso")
    mitte_px = (a.viewer.width() / 2, a.viewer.height() / 2)
    a._zentriere(*mitte_px)
    dp = a._drehpunkt
    a._zoome(1.3, mitte_px[0] + 120, mitte_px[1] + 60)
    a._verschiebe(40, -25)
    ergebnis["drehpunkt_fest"] = dp is not None and a._mitte() is dp and a._drehpunkt_ais is None
    a._mitte_cache = a._mitte()
    a._fuehre_aus(("drehen", 5, 0))  # Kreuz nur waehrend des Drehens
    ergebnis["kreuz_beim_drehen"] = a._drehpunkt_ais is not None
    a._zeige_drehpunkt(an=False)
    a.alles_zeigen()
    ergebnis["drehpunkt_zurueck"] = a._drehpunkt is None and a._drehpunkt_ais is None
    # Kamerafahrt: nach dem Ende am Ziel
    a.animation = True
    a.standard("oben")
    for _ in range(40):
        QtWidgets.QApplication.processEvents()
        if not a._fahrt_uhr.isActive():
            break
        import time; time.sleep(0.02)
    ergebnis["fahrt"] = not a._fahrt_uhr.isActive() and abs(cam.Direction().Z() + 1.0) < 1e-6
    a.animation = False
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
    # Grafik-Schalter (G, erzeugte PMI) und mehrere Schnittebenen in der echten 3D-Ansicht
    f.aktionen["grafik_erzeugt"].trigger(); f.aktionen["grafik"].trigger()  # bei Grafik aus ist "erzeugt" gesperrt
    aus = not a.grafik_an and not a.erzeugt_an
    f.aktionen["grafik"].trigger(); f.aktionen["grafik_erzeugt"].trigger()
    ergebnis["grafik_schalter"] = aus and a.grafik_an and a.erzeugt_an
    f.aktionen["schnitt_x"].trigger(); f.aktionen["schnitt_merken"].trigger(); f.aktionen["schnitt_y"].trigger()
    f.aktionen["schnitt_kette"].trigger()
    ergebnis["schnitt_kette"] = len(a._clips) == 1 and a._clips[0].NbChainNextPlanes() == 2
    f.aktionen["schnitt_kette"].trigger()
    ergebnis["schnitt_zwei"] = len(a._clips) == 2
    f.aktionen["schnitt_aus"].trigger()
    ergebnis["schnitt_aus"] = a._clips == [] and a.schnitt_ebenen == []
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
    assert all(v for k, v in erg.items() if k != "text"), [k for k, v in erg.items() if not v and k != "text"]
