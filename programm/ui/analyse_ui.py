"""Seitenleiste Analyse: Entformungsschraege, Kruemmungsradius, Wandstaerke als Farbkarte."""

from __future__ import annotations

import traceback

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import analyse as an
from .panel_aufbau import zweck_zeile

ARTEN = ((an.ENTFORMUNG, "Entformungsschräge"), (an.KRUEMMUNG, "Krümmungsradius"), (an.WANDSTAERKE, "Wandstärke"))
RICHTUNGEN = (("blick", "Blickrichtung (zum Betrachter)"), ("+z", "+Z"), ("-z", "−Z"), ("+y", "+Y"), ("-y", "−Y"),
              ("+x", "+X"), ("-x", "−X"))
HINWEIS = {
    an.ENTFORMUNG: "Grün: genug Schräge zur Ausformrichtung, blau: zur Gegenseite, rot: weniger als der "
                   "Mindestwinkel (senkrecht oder Hinterschnitt).",
    an.KRUEMMUNG: "Kleinster Hauptkrümmungsradius je Stelle: rot klein, blau groß, ebene Flächen grau.",
    an.WANDSTAERKE: "Abstand von der Oberfläche ins Material bis zur Gegenfläche (Strahlverfahren): rot dünn, "
                    "blau dick, grau ohne Gegenfläche.",
}


class AnalyseLader(QtCore.QThread):
    fertig = QtCore.Signal(object)
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(int)

    def __init__(self, art, teile, richtung, parent=None):
        super().__init__(parent)
        self.art, self.teile, self.richtung = art, teile, richtung
        self.abgebrochen = False

    def run(self):
        from .lader import Abbruch, melder
        try:
            karte = an.berechne(self.art, self.teile, self.richtung,
                                fortschritt=melder(self, lambda a: self.stand.emit(int(a * 100))))
        except Abbruch:
            return
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        self.fertig.emit(karte)


class AnalysePanel(QtWidgets.QWidget):
    berechnen = QtCore.Signal(str, dict)  # Art, Werte
    aus = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(zweck_zeile(tr("Formanalysen am Modell als Farbkarte: Entformungsschräge, Krümmung oder "
                                     "Wandstärke")))
        self.art = QtWidgets.QComboBox()
        self.art.setToolTip(tr("Art der Analyse: Entformung, Krümmung oder Wandstärke"))
        for schluessel, text in ARTEN:
            self.art.addItem(tr(text), schluessel)
        lay.addWidget(self.art)
        form = self._form = QtWidgets.QFormLayout()
        self.richtung = QtWidgets.QComboBox()
        self.richtung.setToolTip(tr("Entformungsrichtung (Zugrichtung des Werkzeugs)"))
        for schluessel, text in RICHTUNGEN:
            self.richtung.addItem(tr(text) if schluessel == "blick" else text, schluessel)
        self.mindest = QtWidgets.QDoubleSpinBox()
        self.mindest.setToolTip(tr("Mindest-Entformungsschräge: flachere Flächen werden markiert"))
        self.mindest.setRange(0.0, 30.0)
        self.mindest.setDecimals(1)
        self.mindest.setValue(1.0)
        self.mindest.setSuffix(" °")
        self.klein = QtWidgets.QDoubleSpinBox()
        self.klein.setToolTip(tr("Krümmung: Radien bis zu diesem Wert erscheinen rot (enge Rundungen)"))
        self.klein.setRange(0.01, 1000.0)
        self.klein.setValue(1.0)
        self.klein.setSuffix(" mm")
        self.gross = QtWidgets.QDoubleSpinBox()
        self.gross.setToolTip(tr("Krümmung: Radien ab diesem Wert erscheinen blau (fast eben)"))
        self.gross.setRange(0.1, 100000.0)
        self.gross.setValue(50.0)
        self.gross.setSuffix(" mm")
        self._zeilen = {}
        for name, text, w in (("richtung", tr("Ausformrichtung"), self.richtung),
                              ("mindest", tr("Mindestwinkel"), self.mindest),
                              ("klein", tr("Radius klein"), self.klein), ("gross", tr("Radius groß"), self.gross)):
            form.addRow(text, w)
            self._zeilen[name] = w
        lay.addLayout(form)
        self.hinweis = QtWidgets.QLabel("")
        self.hinweis.setWordWrap(True)
        self.hinweis.setObjectName("leise")
        lay.addWidget(self.hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.start = QtWidgets.QPushButton(tr("Berechnen"))
        self.start.setObjectName("primaer")
        self.start.setToolTip(tr("Gewählte Analyse für das Modell berechnen und als Farbkarte zeigen"))
        self.start.setObjectName("primaer")
        self.ende = QtWidgets.QPushButton(tr("Analyse aus"))
        self.ende.setToolTip(tr("Farbkarte ausblenden, normale Darstellung"))
        reihe.addWidget(self.ende)
        reihe.addStretch(1)
        reihe.addWidget(self.start)
        lay.addLayout(reihe)
        lay.addStretch(1)
        self.art.currentIndexChanged.connect(self._art_geaendert)
        self.start.clicked.connect(lambda: self.berechnen.emit(self.art.currentData(), self.werte()))
        self.ende.clicked.connect(self.aus.emit)
        self._art_geaendert()

    def _art_geaendert(self):
        art = self.art.currentData()
        sichtbar = {"richtung": art == an.ENTFORMUNG, "mindest": art == an.ENTFORMUNG,
                    "klein": art == an.KRUEMMUNG, "gross": art == an.KRUEMMUNG}
        form = self._form
        for name, w in self._zeilen.items():
            w.setVisible(sichtbar[name])
            form.labelForField(w).setVisible(sichtbar[name])
        self.hinweis.setText(tr(HINWEIS[art]))

    def werte(self) -> dict:
        return {"richtung": self.richtung.currentData(), "mindest": self.mindest.value(),
                "klein": self.klein.value(), "gross": max(self.gross.value(), self.klein.value() * 1.01)}
