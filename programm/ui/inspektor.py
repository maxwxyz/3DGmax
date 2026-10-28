"""Kontext-Inspektor (UI-Plan Stufe 3): zur aktuellen Auswahl (Flaeche/Kante, Teil oder PMI) die Eigenschaften und die
passenden Befehle an einer Stelle - statt sie in Menues und Kontextmenues zu suchen."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from .fluss import FlussLayout


class InspektorPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.titel = QtWidgets.QLabel("")
        self.titel.setWordWrap(True)
        self.titel.setStyleSheet("font-weight: 600;")
        lay.addWidget(self.titel)
        self.leer = QtWidgets.QLabel(tr("Nichts gewählt – eine Fläche oder Kante im Modell, ein Teil in der Struktur "
                                        "oder eine PMI in der Liste anklicken: hier stehen dann ihre Eigenschaften und "
                                        "was man damit tun kann."))
        self.leer.setWordWrap(True)
        self.leer.setObjectName("leise")
        lay.addWidget(self.leer)
        self.tabelle = QtWidgets.QTableWidget(0, 2)
        self.tabelle.horizontalHeader().setVisible(False)
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.setShowGrid(False)
        lay.addWidget(self.tabelle, 3)
        titel = QtWidgets.QLabel(tr("Aktionen"))
        titel.setObjectName("leise")
        self._aktionen_titel = titel
        lay.addWidget(titel)
        self._aktionen = QtWidgets.QWidget()
        self._fluss = FlussLayout(self._aktionen)
        lay.addWidget(self._aktionen)
        lay.addStretch(1)  # ohne Auswahl: Hinweis oben, nicht mittig
        self.knoepfe: list[QtWidgets.QToolButton] = []
        self.zeige("", [], [])

    def zeige(self, titel: str, eigenschaften: list[tuple[str, str]], aktionen: list):
        """eigenschaften: [(Name, Wert)]; aktionen: QActions (Text und Tooltip aus der Aktion, Zustand live)."""
        leer = not titel
        self.leer.setVisible(leer)
        self.titel.setVisible(not leer)
        self.titel.setText(titel)
        self.tabelle.setVisible(not leer)
        self.tabelle.setRowCount(len(eigenschaften))
        for z, (name, wert) in enumerate(eigenschaften):
            self.tabelle.setItem(z, 0, QtWidgets.QTableWidgetItem(name))
            self.tabelle.setItem(z, 1, QtWidgets.QTableWidgetItem(wert))
        self.tabelle.resizeColumnToContents(0)
        while self._fluss.count():
            w = self._fluss.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.knoepfe = []
        for a in aktionen:
            k = QtWidgets.QToolButton()
            k.setDefaultAction(a)
            self._fluss.addWidget(k)
            self.knoepfe.append(k)
        self._aktionen_titel.setVisible(bool(aktionen))
        self._aktionen.setVisible(bool(aktionen))
