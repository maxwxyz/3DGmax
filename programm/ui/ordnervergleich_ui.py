"""Ordnervergleich in der Oberflaeche: zwei Ordner waehlen, Hintergrundrechnung, Uebersicht."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import ordnervergleich as ov
from .tabellen import spalten_anpassen

STATUS_TEXT = {ov.GLEICH: "gleich", ov.GEAENDERT: "geändert", ov.NUR_ALT: "nur alt", ov.NUR_NEU: "nur neu",
               ov.FEHLER: "Fehler", "": "…"}


class OrdnerLader(QtCore.QThread):
    paar_fertig = QtCore.Signal(int)
    fertig = QtCore.Signal()

    def __init__(self, liste, toleranz, suchweite, parent=None):
        super().__init__(parent)
        self.liste, self.toleranz, self.suchweite = liste, toleranz, suchweite
        self.abgebrochen = False

    def run(self):
        from .lader import lade_alles
        for i, p in enumerate(self.liste):
            if self.abgebrochen:
                return
            ov.vergleiche_paar(p, self.toleranz, self.suchweite, lade_alles)
            self.paar_fertig.emit(i)
        self.fertig.emit()


class OrdnerVergleich(QtWidgets.QDialog):
    """Uebersicht: Datei, Status, PMI-/Geometrieaenderungen; Doppelklick oeffnet den Vergleich."""

    oeffnen = QtCore.Signal(object)  # kern.vergleich.Vergleich

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Ordnervergleich"))
        self.resize(820, 520)
        self.liste: list = []
        self.lader: OrdnerLader | None = None
        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.alt = self._zeile()
        self.neu = self._zeile()
        form.addRow(tr("Ordner alter Stand"), self.alt[0])
        form.addRow(tr("Ordner neuer Stand"), self.neu[0])
        lay.addLayout(form)
        reihe = QtWidgets.QHBoxLayout()
        self.start = QtWidgets.QPushButton(tr("Vergleichen"))
        self.start.setToolTip(tr("Alle gleichnamigen Modelle der beiden Ordner vergleichen"))
        self.start.setObjectName("primaer")
        self.start.clicked.connect(self.starte)
        self.stand = QtWidgets.QLabel("")
        self.stand.setObjectName("leise")
        reihe.addWidget(self.stand, 1)
        reihe.addWidget(self.start)
        lay.addLayout(reihe)
        self.tabelle = QtWidgets.QTableWidget(0, 5)
        self.tabelle.setHorizontalHeaderLabels([tr("Datei"), tr("Status"), tr("PMI"), tr("Geometrie"), tr("Hinweis")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.cellDoubleClicked.connect(self._doppelklick)
        lay.addWidget(self.tabelle, 1)
        hinweis = QtWidgets.QLabel(tr("Zuordnung über den Dateinamen; Revisionskennungen am Ende (z. B. _rev_b) "
                                      "werden ignoriert. Doppelklick öffnet den Vergleich."))
        hinweis.setObjectName("leise")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)
        for feld in (self.alt[1], self.neu[1]):
            feld.textChanged.connect(self._pruefe)
        self._pruefe()

    def _zeile(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        feld = QtWidgets.QLineEdit()
        feld.setToolTip(tr("Pfad des Ordners (eintippen oder „Wählen …“)"))
        knopf = QtWidgets.QPushButton(tr("Wählen …"))
        knopf.setToolTip(tr("Ordner auswählen"))
        knopf.clicked.connect(lambda: self._waehle(feld))
        lay.addWidget(feld, 1)
        lay.addWidget(knopf)
        return w, feld

    def _waehle(self, feld):
        ordner = QtWidgets.QFileDialog.getExistingDirectory(self, tr("Ordner wählen"), feld.text())
        if ordner:
            feld.setText(ordner)

    def _pruefe(self):
        self.start.setEnabled(all(os.path.isdir(f.text()) for f in (self.alt[1], self.neu[1])))

    def starte(self, warten: bool = False):
        self.liste = ov.paare(self.alt[1].text(), self.neu[1].text())
        self.tabelle.setRowCount(len(self.liste))
        for z in range(len(self.liste)):
            self._zeige(z)
        spalten_anpassen(self.tabelle, strecken=True, neu=True)  # neue Ordner: Breiten neu
        self.start.setEnabled(False)
        self.lader = OrdnerLader(self.liste, 0.01, 2.0, self)
        self.lader.paar_fertig.connect(self._zeige)
        self.lader.fertig.connect(self._fertig)
        self.stand.setText(tr("Vergleiche {} Paare …").format(len(self.liste)))
        self.lader.start()
        if warten:
            self.lader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def _zeige(self, z):
        p = self.liste[z]
        name = os.path.basename(p.neu or p.alt)
        if p.alt and p.neu and os.path.basename(p.alt) != os.path.basename(p.neu):
            name = f"{os.path.basename(p.alt)} → {os.path.basename(p.neu)}"
        werte = (name, tr(STATUS_TEXT.get(p.status, p.status)),
                 str(p.pmi_aenderungen) if p.vergleich else "", str(p.geo_aenderungen) if p.vergleich else "",
                 p.meldung)
        for s, w in enumerate(werte):
            self.tabelle.setItem(z, s, QtWidgets.QTableWidgetItem(w))

    def _fertig(self):
        z = {k: sum(p.status == k for p in self.liste) for k in STATUS_TEXT}
        self.stand.setText(tr("{} gleich, {} geändert, {} nur alt, {} nur neu, {} Fehler").format(
            z[ov.GLEICH], z[ov.GEAENDERT], z[ov.NUR_ALT], z[ov.NUR_NEU], z[ov.FEHLER]))
        spalten_anpassen(self.tabelle, strecken=True)  # Ergebnisse sind da; gezogene Breiten bleiben
        self._pruefe()

    def _doppelklick(self, z, _s):
        p = self.liste[z]
        if p.vergleich is not None:
            self.oeffnen.emit(p.vergleich)

    def closeEvent(self, ev):
        if self.lader is not None and self.lader.isRunning():
            self.lader.abgebrochen = True
            self.lader.wait(60000)
        super().closeEvent(ev)
