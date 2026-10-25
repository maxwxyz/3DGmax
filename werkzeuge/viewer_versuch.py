"""Mini-Versuch: OCCT-Viewer in PySide6 mit PMI-Liste, Hervorhebung, Flaechen-Klick, Ansichten.

Aufruf: pixi run python werkzeuge/viewer_versuch.py datei.stp [--bild out.png] [--pmi NR] [--ansicht NAME]
Mit --bild wird nach dem Anzeigen ein Bildschirmfoto gespeichert und beendet.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OCC.Display.backend import load_backend  # noqa: E402

load_backend("pyside6")
from OCC.Core.AIS import AIS_ColoredShape  # noqa: E402
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB  # noqa: E402
from OCC.Display.qtDisplay import qtViewer3d  # noqa: E402
from PySide6 import QtCore, QtWidgets  # noqa: E402

from programm.kern.ansichten import lies_ansichten  # noqa: E402
from programm.kern.laden import lade_step  # noqa: E402
from programm.kern.pmi_lesen import lies_pmi  # noqa: E402

GRAU = Quantity_Color(0.72, 0.74, 0.78, Quantity_TOC_RGB)
ORANGE = Quantity_Color(1.0, 0.45, 0.0, Quantity_TOC_RGB)


class Fenster(QtWidgets.QMainWindow):
    def __init__(self, pfad: str):
        super().__init__()
        self.setWindowTitle(f"3DGmax Versuch – {os.path.basename(pfad)}")
        self.modell = lade_step(pfad)
        self.pmi = lies_pmi(self.modell)
        self.ansichten = lies_ansichten(self.modell, self.pmi)
        self.viewer = qtViewer3d(self)
        self.liste = QtWidgets.QListWidget()
        self.wahl = QtWidgets.QComboBox()
        self.wahl.addItems(["(alle PMI)"] + [a.name for a in self.ansichten])
        links = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(links)
        lay.addWidget(QtWidgets.QLabel("Gespeicherte Ansicht"))
        lay.addWidget(self.wahl)
        lay.addWidget(QtWidgets.QLabel("PMI"))
        lay.addWidget(self.liste)
        teiler = QtWidgets.QSplitter()
        teiler.addWidget(links)
        teiler.addWidget(self.viewer)
        teiler.setSizes([380, 900])
        self.setCentralWidget(teiler)
        self.resize(1300, 800)
        self.liste.currentRowChanged.connect(self._pmi_gewaehlt)
        self.wahl.currentIndexChanged.connect(self._ansicht_gewaehlt)
        self._fuelle_liste(self.pmi)

    def start_viewer(self):
        self.viewer.InitDriver()
        d = self.viewer._display
        self.ais = AIS_ColoredShape(self.modell.form)
        self.ais.SetColor(GRAU)
        d.Context.Display(self.ais, True)
        d.Context.SetDisplayMode(self.ais, 1, True)
        d.Context.Activate(self.ais, 4)  # 4 = Flaechen waehlbar
        d.register_select_callback(self._flaeche_geklickt)
        d.View_Iso()
        d.FitAll()

    def _fuelle_liste(self, pmi):
        self.liste.blockSignals(True)
        self.liste.clear()
        self.sichtbar = pmi
        for p in pmi:
            self.liste.addItem(f"{p.nummer:3d}  {p.wert_text()}")
        self.liste.blockSignals(False)

    def hebe_hervor(self, flaechen: set[int]):
        self.ais.ClearCustomAspects()
        for i in flaechen:
            self.ais.SetCustomColor(self.modell.flaechen[i], ORANGE)
        self.viewer._display.Context.Redisplay(self.ais, True)

    def _pmi_gewaehlt(self, zeile: int):
        if 0 <= zeile < len(self.sichtbar):
            self.hebe_hervor(self.sichtbar[zeile].flaechen)

    def _flaeche_geklickt(self, formen, *_):
        for f in formen:
            idx = self.modell.flaechen_index(f)
            treffer = [i for i, p in enumerate(self.sichtbar) if idx in p.flaechen]
            self.statusBar().showMessage(
                f"Fläche {idx}: {len(treffer)} PMI – " + ", ".join(self.sichtbar[i].wert_text() for i in treffer))
            if treffer:
                self.liste.setCurrentRow(treffer[0])

    def _ansicht_gewaehlt(self, i: int):
        if i == 0:
            self._fuelle_liste(self.pmi)
            return
        a = self.ansichten[i - 1]
        self._fuelle_liste([p for p in self.pmi if p.nummer in a.pmi_nummern])
        v = self.viewer._display.View
        v.SetProj(*(-c for c in a.richtung))
        v.SetUp(*a.oben)
        self.viewer._display.FitAll()


def main(argv):
    app = QtWidgets.QApplication(argv)
    f = Fenster(argv[1])
    f.show()
    f.start_viewer()
    if "--ansicht" in argv:
        f.wahl.setCurrentText(argv[argv.index("--ansicht") + 1])
    if "--pmi" in argv:
        f.liste.setCurrentRow(int(argv[argv.index("--pmi") + 1]) - 1)
    if "--bild" in argv:
        ziel = argv[argv.index("--bild") + 1]

        def foto():
            app.processEvents()
            f.grab().save(ziel.replace(".png", "_fenster.png"))
            f.viewer._display.View.Dump(ziel)
            app.quit()
        QtCore.QTimer.singleShot(1500, foto)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
