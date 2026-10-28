"""Werkstoffwahl fuer Ketten von Hand: Auswahlfeld mit der Bibliothek (Name frei eintragbar) und eine Zeile mit dem
Werkstoff der ganzen Kette und zwei Grenztemperaturen fuer die Waermeausdehnung (2D- und 3D-Kette)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import werkstoffe as ws


def werkstoff_feld(aktuell: str, leer_text: str, hilfe: str) -> QtWidgets.QComboBox:
    """Auswahl: erster Eintrag leer_text (= kein eigener Werkstoff), dann die Bibliothek; eigene Namen eintragbar
    (alpha per Stichwort, z. B. "S235" -> Stahl)."""
    feld = QtWidgets.QComboBox()
    feld.setEditable(True)
    feld.addItem(leer_text)
    feld.addItems(list(ws.BIBLIOTHEK))
    if aktuell:
        feld.setCurrentText(aktuell)
    feld.setToolTip(hilfe)
    return feld


def werkstoff_wert(feld: QtWidgets.QComboBox) -> str:
    """Gewaehlter Werkstoff; "" beim ersten Eintrag."""
    text = feld.currentText().strip()
    return "" if text == feld.itemText(0) else text


class WaermeZeile(QtWidgets.QWidget):
    """Werkstoff der Kette und Waermeausdehnung bei zwei Grenztemperaturen."""

    geaendert = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QtWidgets.QLabel(tr("Werkstoff der Kette")))
        self.werkstoff = werkstoff_feld("", tr("keiner"), tr("Werkstoff aller Glieder ohne eigenen Werkstoff; α aus "
                                                             "der Bibliothek, eigene Namen per Stichwort (z. B. S235 → "
                                                             "Stahl)"))
        self.werkstoff.currentTextChanged.connect(lambda _t: self.geaendert.emit())
        lay.addWidget(self.werkstoff)
        self.waerme = QtWidgets.QCheckBox(tr("Wärmeausdehnung bei"))
        self.waerme.setToolTip(tr("Schlussgröße zusätzlich bei zwei Grenztemperaturen: jede Länge wächst um "
                                  "ΔL = α · L · (T − 20 °C) mit dem Werkstoff ihres Glieds, Winkel bleiben"))
        self.waerme.toggled.connect(lambda _a: self.geaendert.emit())
        lay.addWidget(self.waerme)
        self.t1, self.t2 = (self._temperatur(v) for v in (-20.0, 80.0))
        lay.addWidget(self.t1)
        lay.addWidget(QtWidgets.QLabel(tr("und")))
        lay.addWidget(self.t2)
        lay.addStretch(1)

    def _temperatur(self, wert: float) -> QtWidgets.QDoubleSpinBox:
        f = QtWidgets.QDoubleSpinBox()
        f.setRange(-273.0, 1000.0)
        f.setDecimals(1)
        f.setSuffix(" °C")
        f.setValue(wert)
        f.setToolTip(tr("Grenztemperaturen (z. B. Kaltstart und Betrieb); Bezug ist 20 °C nach ISO 1"))
        f.valueChanged.connect(lambda _v: self.geaendert.emit())
        return f

    def setze(self, werkstoff: str, temperaturen: tuple | None):
        for w in (self.werkstoff, self.waerme, self.t1, self.t2):
            w.blockSignals(True)
        self.werkstoff.setCurrentText(werkstoff or self.werkstoff.itemText(0))
        self.waerme.setChecked(bool(temperaturen))
        if temperaturen:
            self.t1.setValue(temperaturen[0])
            self.t2.setValue(temperaturen[1])
        for w in (self.werkstoff, self.waerme, self.t1, self.t2):
            w.blockSignals(False)

    def wert(self) -> str:
        return werkstoff_wert(self.werkstoff)

    def temperaturen(self) -> tuple | None:
        return (self.t1.value(), self.t2.value()) if self.waerme.isChecked() else None
