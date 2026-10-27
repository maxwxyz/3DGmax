"""Fenster Stueckliste: Positionen mit Anzahl, Volumen und Masse; Doppelklick isoliert das Teil."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import eigenschaften as ek
from ..kern import stueckliste as sl


class StuecklisteFenster(QtWidgets.QDialog):
    isolieren = QtCore.Signal(set)  # Blattnummern

    def __init__(self, wurzel, einstellungen, speicherpfad, parent=None, datei=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Stückliste"))
        self.resize(760, 420)
        self.ein = einstellungen
        self.speicherpfad = speicherpfad
        self.liste = sl.ergaenze_sachnummern(sl.positionen(wurzel), datei)
        self.dichte = float(self.ein.value("dichte", ek.DICHTE_STAHL))
        lay = QtWidgets.QVBoxLayout(self)
        gesamt = sum(p.anzahl for p in self.liste)
        info = QtWidgets.QLabel(tr("{} Positionen, {} Teile · Dichte {:.3f} g/cm³ (wie in den Modelleigenschaften), "
                                   "bei bekanntem Werkstoff dessen Dichte").format(len(self.liste), gesamt, self.dichte))
        info.setObjectName("leise")
        lay.addWidget(info)
        self.tabelle = QtWidgets.QTableWidget(0, len(sl.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in sl.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setShowGrid(False)
        self.tabelle.setToolTip(tr("Doppelklick: nur dieses Teil zeigen"))
        zeilen = sl.zeilen(self.liste, self.dichte)
        self.tabelle.setRowCount(len(zeilen))
        for z, werte in enumerate(zeilen):
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s in (0, 3, 4, 5, 6):
                    it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.tabelle.setItem(z, s, it)
        self.tabelle.resizeColumnsToContents()
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.cellDoubleClicked.connect(lambda z, _s: self.isolieren.emit(set(self.liste[z].nummern)))
        lay.addWidget(self.tabelle, 1)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        export = knoepfe.addButton(tr("Als CSV speichern …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        kopie = knoepfe.addButton(tr("Kopieren"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        export.clicked.connect(lambda: self.speichere())
        kopie.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(
            sl.als_csv(self.liste, self.dichte).replace(";", "\t")))
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def speichere(self, pfad: str = "") -> str | None:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Stückliste speichern"), self.speicherpfad,
                                                            "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(sl.als_csv(self.liste, self.dichte))
        return pfad
