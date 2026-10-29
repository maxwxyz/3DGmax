"""Fenster Messergebnisse (QIF): Istwerte je Merkmal mit Status der Datei und eigener Bewertung."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import qif_ergebnisse as qe
from .tabellen import spalten_anpassen

SPALTEN = ("Ballon", "Merkmal", "Wert", "Obere Grenze", "Untere Grenze", "Messwert", "Status (Datei)", "Bewertung")
FARBE = {qe.GUT: "#2e9d47", qe.SCHLECHT: "#c0392b"}


class MessergebnisseFenster(QtWidgets.QDialog):
    gewaehlt = QtCore.Signal(object)  # Pmi des Merkmals

    def __init__(self, merkmale: list, messung: dict, angaben: dict, frei: int, parent=None):
        """messung: Ballonnummer -> (Messwert, Bewertung); frei: Messungen ohne zugeordnetes Merkmal."""
        super().__init__(parent)
        self.setWindowTitle(tr("Messergebnisse"))
        self.merkmale = [m for m in merkmale if m.ballon in messung]
        self.messung = messung
        lay = QtWidgets.QVBoxLayout(self)
        gut = sum(1 for _, u in messung.values() if u == qe.GUT)
        schlecht = sum(1 for _, u in messung.values() if u == qe.SCHLECHT)
        kopf = tr("{} Merkmale gemessen: {} i. O., {} n. i. O.").format(len(messung), gut, schlecht)
        if angaben.get("status"):
            kopf += " · " + tr("Gesamtstatus der Datei: {}").format(angaben["status"])
        if frei:
            kopf += " · " + tr("{} Messungen ohne passendes Merkmal").format(frei)
        lay.addWidget(QtWidgets.QLabel(kopf))
        self.tabelle = QtWidgets.QTableWidget(len(self.merkmale), len(SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        z = lambda x: "" if x is None else f"{x:.4f}".rstrip("0").rstrip(".")  # noqa: E731
        for r, m in enumerate(self.merkmale):
            w, urteil = messung[m.ballon]
            oben, unten = m.grenzen()
            werte = (str(m.ballon), tr(m.pmi.merkmal()), m.pmi.wert_text(), z(oben), z(unten),
                     z(w.wert) if w is not None else "", w.status if w is not None else "",
                     {qe.GUT: tr("i. O."), qe.SCHLECHT: tr("n. i. O.")}.get(urteil, "–"))
            for s, t in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(t)
                if s == 7 and urteil in FARBE:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(FARBE[urteil])))
                self.tabelle.setItem(r, s, it)
        spalten_anpassen(self.tabelle, strecken=True)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)
        lay.addWidget(self.tabelle, 1)
        lay.addWidget(QtWidgets.QLabel(tr("Die Merkmalsliste (CSV/PDF) übernimmt die Messwerte, solange das Modell "
                                          "geladen ist.")))
        schliessen = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        schliessen.rejected.connect(self.close)
        lay.addWidget(schliessen)
        self.resize(820, 420)

    def _auswahl(self):
        zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
        if len(zeilen) == 1:
            self.gewaehlt.emit(self.merkmale[zeilen.pop()].pmi)
