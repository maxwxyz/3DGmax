"""Bildschirmfotos fuer die Anleitungen erzeugen (deutsch und englisch).

    pixi run python packaging/doc_screenshots.py            (braucht eine Grafikausgabe, sonst xvfb-run davor)

Schreibt programm/doc_img/de/*.png und programm/doc_img/en/*.png. Beispiele: die NIST-Testmodelle und die eigene
Testbaugruppe aus tests/daten. Beruehrt keine Nutzereinstellungen (eigene Einstellungsdatei je Sprache). Die
3D-Ansicht (OpenGL) erscheint nicht in QWidget.grab(); ihr Bild wird ueber View.Dump eingesetzt.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "programm", "doc_img")
DATEN = os.path.join(ROOT, "tests", "daten")

SZENEN = r'''
import os, sys, tempfile, time
sys.path.insert(0, sys.argv[2])
from PySide6 import QtCore, QtGui, QtWidgets
app = QtWidgets.QApplication([])
from programm.ui.hauptfenster import Hauptfenster
OUT, DATEN = sys.argv[1], sys.argv[3]
TMP = tempfile.mkdtemp()


def pump(n=30):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.02)


def speichern(bild, name):
    """PNG mit 256-Farben-Palette (klein genug fuer das Repository)."""
    flags = QtCore.Qt.ImageConversionFlag.AvoidDither
    bild.convertToFormat(QtGui.QImage.Format.Format_Indexed8, flags).save(os.path.join(OUT, name + ".png"), "PNG", 0)


def foto(name, w=None):
    """Fenster mit eingesetztem 3D-Bild speichern."""
    w = w or f
    pump()
    bild = w.grab().toImage()
    if w is f and f.stapel.currentWidget() is f.ansicht and hasattr(f.ansicht, "d"):
        f.ansicht._neu_zeichnen()
        pump(10)
        datei = os.path.join(TMP, "3d.png")
        f.ansicht.d.View.Dump(datei)
        v = f.ansicht.viewer
        ort = v.mapTo(f, QtCore.QPoint(0, 0))
        drei = QtGui.QImage(datei).scaled(v.width(), v.height())
        maler = QtGui.QPainter(bild)
        maler.drawImage(ort, drei)
        maler.end()
    speichern(bild, name)
    print("Bild", name, flush=True)


def waehle_erste(bedingung):
    """Genau eine PMI waehlen (bei einer zeigt die Ansicht auch ihr Bezugssystem)."""
    erste = next((p for p in f.erg.pmi if bedingung(p)), None)
    f.pmi.waehle(lambda p: p is erste)


def warte(bedingung, sekunden=120):
    t0 = time.time()
    while not bedingung() and time.time() - t0 < sekunden:
        pump(5)


def leere_statuszeile():
    f.pmi.waehle(lambda p: False)
    f._schnell_pmi, f._schnell_formen = [], []
    f._schnell_zeigen()
    f.statusBar().clearMessage()


f = Hauptfenster()
f.resize(1440, 880)
f.show()
pump(50)
foto("start")

f.lade(os.path.join(DATEN, "nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
pump(60)
f.ansicht.standard("iso")
pump(40)
foto("modell")

waehle_erste(lambda p: p.typ == "Position" and bool(p.bezuege))
pump(40)
foto("pmi")
leere_statuszeile()

if f.erg.ansichten:
    f.ansichten.liste.setCurrentRow(0)
    pump(60)
    foto("ansicht")

f.aktionen["schnitt_x"].trigger()
pump(40)
foto("schnitt")
f.aktionen["schnitt_aus"].trigger()
f.ansicht.standard("iso")
pump(30)

f.aktionen["messen"].setChecked(True)
f._messen_umschalten()
f.messen.setze_modus("radius")
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
zylinder = [x for x in f.erg.modell.flaechen if BRepAdaptor_Surface(x).GetType() == GeomAbs_Cylinder]
if zylinder:
    g = GProp_GProps()
    brepgprop.SurfaceProperties(zylinder[0], g)
    c = g.CentreOfMass()
    f.messen.element(zylinder[0], (c.X(), c.Y(), c.Z()))
pump(40)
foto("messen")
f.messen.loesche_alle()
f.aktionen["messen"].setChecked(False)
f._messen_umschalten()
f.dock_messen.hide()

f.aktionen["zeichnung_pmi"].setChecked(True)
svg = os.path.join(TMP, "zeichnung.svg")
f.exportiere_zeichnung("blatt", svg)
from PySide6 import QtSvg
r = QtSvg.QSvgRenderer(svg)
groesse = r.defaultSize().scaled(1400, 990, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
blatt = QtGui.QImage(groesse, QtGui.QImage.Format.Format_RGB888)
blatt.fill(QtGui.QColor("white"))
maler = QtGui.QPainter(blatt)
r.render(maler)
maler.end()
speichern(blatt, "zeichnung")
print("Bild zeichnung", flush=True)

f.aktionen["grafik"].trigger()
f.pruefe_scan(os.path.join(DATEN, "varianten", "ctc01_scan_fehler.ply"), warten=True)
waehle_erste(lambda p: p.typ == "Flatness")
f.scan.tabelle.selectRow(next(i for i, e in enumerate(f.scan.ergebnisse) if e.pmi.typ == "Flatness"))
f.ansicht.standard("iso")
pump(60)
foto("scan")
f.scan_aus()
f.aktionen["grafik"].trigger()
leere_statuszeile()

f.lade(os.path.join(DATEN, "nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
pump(60)
f.aktionen["grafik"].trigger()
f.aktionen["toleranzzone"].setChecked(True)
waehle_erste(lambda p: p.material == "M" and len(p.flaechen) > 2)
f.ansicht.standard("iso")
pump(60)
foto("toleranzzone")
f.aktionen["toleranzzone"].setChecked(False)
f._zone_aktualisieren([])
f.aktionen["fokus"].setChecked(True)
f._fokus_umschalten()
waehle_erste(lambda p: p.typ == "Symmetry")
pump(60)
foto("fokus")
f.aktionen["fokus"].setChecked(False)
f._fokus_umschalten()
f.aktionen["grafik"].trigger()
leere_statuszeile()

alt, neu = os.path.join(DATEN, "baugruppe.stp"), os.path.join(DATEN, "baugruppe_b.stp")
f.lade(alt, warten=True)
f.starte_vergleich({"alt": alt, "neu": neu, "toleranz": 0.01, "suchweite": 2.0}, warten=True)
pump(80)
f.ansicht.standard("iso")
pump(40)
foto("vergleich")
f.aenderungen.start.click()
pump(40)
foto("pruefen")
f.aenderungen.karte_an.setChecked(True)  # wie ein Klick: berechnen (Hintergrund), dann zeigen
warte(lambda: f.ansicht.abweichung is not None)
pump(40)
foto("farbkarte")
f.aenderungen.karte_an.setChecked(False)
f.beende_vergleich()
pump(20)
leere_statuszeile()
f.lade(neu, warten=True)
pump(40)
f.aktionen["explosion"].trigger()
f.explosion_regler.setValue(60)
f.ansicht.standard("iso")
pump(60)
foto("explosion")
pump(20)
app.exit(0)
'''


def main():
    os.makedirs(OUT, exist_ok=True)
    skript = os.path.join(tempfile.mkdtemp(), "szenen.py")
    with open(skript, "w", encoding="utf-8") as f:
        f.write(SZENEN)
    for sprache in ("de", "en"):
        ziel = os.path.join(OUT, sprache)
        os.makedirs(ziel, exist_ok=True)
        env = dict(os.environ, DG_LANG=sprache,
                   DG_EINSTELLUNGEN=os.path.join(tempfile.mkdtemp(), "einstellungen.ini"))
        subprocess.run([sys.executable, skript, ziel, ROOT, DATEN], env=env, check=True)
        print(sprache, sorted(os.listdir(ziel)))


if __name__ == "__main__":
    main()
