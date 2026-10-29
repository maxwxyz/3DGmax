"""Fenster mit den Befunden der PMI-Pruefung; Doppelklick waehlt die PMI in der Liste."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from .tabellen import spalten_anpassen, textbreite_hoechst


class PruefFenster(QtWidgets.QDialog):
    pmi_waehlen = QtCore.Signal(list)  # Nummern
    flaechen_waehlen = QtCore.Signal(set)  # Flaechen ohne PMI (z. B. nicht tolerierte)

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
        from ..kern.plausibilitaet import KATEGORIE_TEXT
        self.tabelle = QtWidgets.QTableWidget(len(befunde), 4)
        self.tabelle.setHorizontalHeaderLabels([tr("Stufe"), tr("Kategorie"), tr("Befund"), tr("PMI")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        for z, b in enumerate(befunde):
            nummern = ", ".join(map(str, b.nummern[:12])) + (" …" if len(b.nummern) > 12 else "")
            if not b.nummern and b.flaechen:
                nummern = tr("{} Flächen").format(len(b.flaechen))
            werte = (tr(b.stufe), tr(KATEGORIE_TEXT.get(b.kategorie, b.kategorie)),
                     tr(b.text) if "{" not in b.text else b.text, nummern)
            for s, w in enumerate(werte):
                self.tabelle.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        spalten_anpassen(self.tabelle, hoechst=2 * textbreite_hoechst(self.tabelle), strecken=True)  # Befund: Saetze
        self.tabelle.cellDoubleClicked.connect(self._waehle)
        lay.addWidget(self.tabelle, 1)
        knopf = QtWidgets.QPushButton(tr("Schließen"))
        knopf.clicked.connect(self.accept)
        lay.addWidget(knopf, 0, QtCore.Qt.AlignmentFlag.AlignRight)

    def _waehle(self, zeile, _spalte=0):
        b = self.befunde[zeile]
        if b.nummern:
            self.pmi_waehlen.emit(list(b.nummern))
        elif b.flaechen:
            self.flaechen_waehlen.emit(set(b.flaechen))
