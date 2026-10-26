"""Fenster mit den Befunden der PMI-Pruefung; Doppelklick waehlt die PMI in der Liste."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr


class PruefFenster(QtWidgets.QDialog):
    pmi_waehlen = QtCore.Signal(list)  # Nummern

    def __init__(self, befunde: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("PMI prüfen"))
        self.resize(760, 460)
        self.befunde = befunde
        lay = QtWidgets.QVBoxLayout(self)
        zaehler = {s: sum(b.stufe == s for b in befunde) for s in ("Fehler", "Warnung", "Hinweis")}
        kopf = QtWidgets.QLabel(tr("{} Fehler, {} Warnungen, {} Hinweise – Doppelklick wählt die PMI").format(
            zaehler["Fehler"], zaehler["Warnung"], zaehler["Hinweis"]))
        lay.addWidget(kopf)
        self.tabelle = QtWidgets.QTableWidget(len(befunde), 3)
        self.tabelle.setHorizontalHeaderLabels([tr("Stufe"), tr("Befund"), tr("PMI")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for z, b in enumerate(befunde):
            nummern = ", ".join(map(str, b.nummern[:12])) + (" …" if len(b.nummern) > 12 else "")
            for s, w in enumerate((tr(b.stufe), tr(b.text) if "{" not in b.text else b.text, nummern)):
                self.tabelle.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        self.tabelle.resizeColumnToContents(0)
        self.tabelle.cellDoubleClicked.connect(lambda z, _s: self.pmi_waehlen.emit(list(self.befunde[z].nummern)))
        lay.addWidget(self.tabelle, 1)
        knopf = QtWidgets.QPushButton(tr("Schließen"))
        knopf.clicked.connect(self.accept)
        lay.addWidget(knopf, 0, QtCore.Qt.AlignmentFlag.AlignRight)
