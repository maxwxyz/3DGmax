"""Seitenleiste Kommentare: anlegen an der Auswahl, Liste, erledigt/loeschen, Export."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import kommentare as km
from .tabellen import aenderbar_machen, leer_hinweis
from .panel_aufbau import zweck_zeile


class KommentarDialog(QtWidgets.QDialog):
    def __init__(self, ziel_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Kommentar"))
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("An: {}").format(ziel_text))
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        self.art = QtWidgets.QComboBox()
        self.art.setToolTip(tr("Art des Kommentars: Hinweis, Frage oder Änderungsvorschlag"))
        for schluessel, text in km.ART.items():
            self.art.addItem(tr(text), schluessel)
        lay.addWidget(self.art)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setPlaceholderText(tr("Kommentar, Frage oder Änderungsvorschlag"))
        lay.addWidget(self.text)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.resize(420, 220)


class KommentarPanel(QtWidgets.QWidget):
    neu = QtCore.Signal()  # Kommentar an der aktuellen Auswahl anlegen
    gewaehlt = QtCore.Signal(object)  # Kommentar oder None
    geaendert = QtCore.Signal()  # Liste geaendert (Markierungen neu zeichnen)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kommentare: list[km.Kommentar] = []
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(zweck_zeile(tr("Anmerkungen an Flächen, Teilen oder PMI festhalten und abhaken – sie "
                                     "werden im Projekt gespeichert")))
        oben = QtWidgets.QHBoxLayout()
        self.plus = QtWidgets.QPushButton(tr("＋ Kommentar"))
        self.plus.setObjectName("primaer")
        self.plus.setToolTip(tr("Kommentar an den gewählten Flächen oder PMI anlegen (K)"))
        self.nur_offen = QtWidgets.QCheckBox(tr("Nur offene"))
        self.nur_offen.setToolTip(tr("Erledigte Kommentare ausblenden"))
        oben.addWidget(self.plus)
        oben.addStretch(1)
        oben.addWidget(self.nur_offen)
        lay.addLayout(oben)
        self.tabelle = QtWidgets.QTableWidget(0, 4)
        leer_hinweis(self.tabelle, tr("Noch keine Kommentare – Element im Modell wählen und „＋ Kommentar“"))
        self.tabelle.setHorizontalHeaderLabels([tr("Nr"), tr("Art"), tr("Status"), tr("Text")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        aenderbar_machen(self.tabelle)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.setToolTip(tr("Doppelklick auf den Text ändert ihn"))
        lay.addWidget(self.tabelle, 1)
        unten = QtWidgets.QHBoxLayout()
        self.erledigt = QtWidgets.QPushButton(tr("Erledigt"))
        self.erledigt.setToolTip(tr("Gewählten Kommentar als erledigt markieren (nochmals: wieder offen)"))
        self.loeschen = QtWidgets.QPushButton(tr("Löschen"))
        self.loeschen.setToolTip(tr("Gewählten Kommentar löschen"))
        unten.addWidget(self.erledigt)
        unten.addWidget(self.loeschen)
        unten.addStretch(1)
        lay.addLayout(unten)
        self.plus.clicked.connect(self.neu.emit)
        self.nur_offen.toggled.connect(self._filtern)
        self.tabelle.itemSelectionChanged.connect(lambda: self.gewaehlt.emit(self.gewaehlter()))
        self.tabelle.itemChanged.connect(self._text_geaendert)
        self.erledigt.clicked.connect(self._erledigt)
        self.loeschen.clicked.connect(self._loeschen)
        self._knoepfe()

    def setze(self, liste: list):
        self.kommentare = list(liste)
        self._fuelle()

    def fuege_hinzu(self, k: km.Kommentar):
        self.kommentare.append(k)
        self._fuelle()
        self.tabelle.selectRow(len(self.kommentare) - 1)

    def naechste_nummer(self) -> int:
        return max((k.nummer for k in self.kommentare), default=0) + 1

    def gewaehlter(self):
        z = self.tabelle.currentRow()
        return self.kommentare[z] if 0 <= z < len(self.kommentare) and self.tabelle.selectedItems() else None

    def _fuelle(self):
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(self.kommentare))
        for z, k in enumerate(self.kommentare):
            for s, w in enumerate((str(k.nummer), tr(km.ART.get(k.art, k.art)), tr(km.STATUS.get(k.status, k.status)),
                                   k.text)):
                it = QtWidgets.QTableWidgetItem(w)
                if s != 3:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 3:
                    it.setToolTip(f"{k.autor} · {k.datum}")
                t.setItem(z, s, it)
        t.resizeColumnsToContents()
        t.blockSignals(False)
        self._filtern()
        self._knoepfe()
        self.geaendert.emit()

    def _filtern(self):
        for z, k in enumerate(self.kommentare):
            self.tabelle.setRowHidden(z, self.nur_offen.isChecked() and k.status == "erledigt")

    def _knoepfe(self):
        da = bool(self.kommentare)
        self.erledigt.setEnabled(da)
        self.loeschen.setEnabled(da)

    def _text_geaendert(self, it):
        if it.column() == 3 and 0 <= it.row() < len(self.kommentare):
            self.kommentare[it.row()].text = it.text()
            self.geaendert.emit()

    def _erledigt(self):
        k = self.gewaehlter()
        if k is not None:
            k.status = "offen" if k.status == "erledigt" else "erledigt"
            self._fuelle()

    def _loeschen(self):
        k = self.gewaehlter()
        if k is not None:
            self.kommentare.remove(k)
            self._fuelle()
