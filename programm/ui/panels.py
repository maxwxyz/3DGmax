"""Seitenleisten: Baugruppenbaum, PMI-Liste, gespeicherte Ansichten."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern.pmi import BEZUG, HINWEIS, MASS, TOLERANZ

ART_TEXT = {MASS: "Maß", TOLERANZ: "Toleranz", BEZUG: "Bezug", HINWEIS: "Hinweis"}


class BaumPanel(QtWidgets.QWidget):
    """Struktur mit Haken zum Ein-/Ausblenden; Kontextmenue: isolieren, transparent."""

    sichtbar_geaendert = QtCore.Signal(set, bool)  # Blatt-Nummern, sichtbar
    isolieren = QtCore.Signal(object)  # set oder None (alle zeigen)
    transparent = QtCore.Signal(set, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.baum = QtWidgets.QTreeWidget()
        self.baum.setHeaderHidden(True)
        self.baum.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.baum.customContextMenuRequested.connect(self._menue)
        self.baum.itemChanged.connect(self._haken)
        lay.addWidget(self.baum)
        self._transparent: set[int] = set()

    def zeige(self, wurzel):
        self.baum.blockSignals(True)
        self.baum.clear()
        self._transparent = set()
        if wurzel is not None:
            self.baum.addTopLevelItem(self._eintrag(wurzel))
            self.baum.expandToDepth(1)
        self.baum.blockSignals(False)

    def _eintrag(self, k):
        it = QtWidgets.QTreeWidgetItem([k.name + (tr(" (Hilfsgeometrie)") if k.hilfsgeometrie else "")])
        it.setData(0, QtCore.Qt.ItemDataRole.UserRole, k)
        flags = it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
        it.setFlags(flags)
        it.setCheckState(0, QtCore.Qt.CheckState.Unchecked if k.hilfsgeometrie else QtCore.Qt.CheckState.Checked)
        for kind in k.kinder:
            it.addChild(self._eintrag(kind))
        return it

    @staticmethod
    def blaetter(it) -> set[int]:
        k = it.data(0, QtCore.Qt.ItemDataRole.UserRole)
        return {b.nummer for b in k.blaetter() if not b.hilfsgeometrie}

    def _haken(self, it, _spalte):
        an = it.checkState(0) == QtCore.Qt.CheckState.Checked
        self.baum.blockSignals(True)
        _setze_kinder(it, it.checkState(0))
        self.baum.blockSignals(False)
        self.sichtbar_geaendert.emit(self.blaetter(it), an)

    def gewaehlte_blaetter(self) -> set[int]:
        out = set()
        for it in self.baum.selectedItems():
            out |= self.blaetter(it)
        return out

    def _menue(self, pos):
        it = self.baum.itemAt(pos)
        m = QtWidgets.QMenu(self)
        a_iso = m.addAction(tr("Isolieren"))
        a_alle = m.addAction(tr("Alle zeigen"))
        a_tr = m.addAction(tr("Transparent ein/aus"))
        a_iso.setEnabled(it is not None)
        a_tr.setEnabled(it is not None)
        gewaehlt = m.exec(self.baum.viewport().mapToGlobal(pos))
        if gewaehlt is a_iso:
            self.isolieren.emit(self.blaetter(it))
        elif gewaehlt is a_alle:
            self.alle_zeigen()
        elif gewaehlt is a_tr:
            self.schalte_transparent(self.blaetter(it))

    def schalte_transparent(self, nummern: set[int]):
        an = not nummern <= self._transparent
        self._transparent = (self._transparent | nummern) if an else (self._transparent - nummern)
        self.transparent.emit(nummern, an)

    def alle_zeigen(self):
        self.baum.blockSignals(True)
        for i in range(self.baum.topLevelItemCount()):
            _setze_kinder(self.baum.topLevelItem(i), QtCore.Qt.CheckState.Checked, hilfe_auslassen=True)
        self.baum.blockSignals(False)
        self.isolieren.emit(None)


def _setze_kinder(it, zustand, hilfe_auslassen=False):
    k = it.data(0, QtCore.Qt.ItemDataRole.UserRole)
    if not (hilfe_auslassen and k is not None and k.hilfsgeometrie):
        it.setCheckState(0, zustand)
    for i in range(it.childCount()):
        _setze_kinder(it.child(i), zustand, hilfe_auslassen)


class PmiPanel(QtWidgets.QWidget):
    """Tabelle aller PMI mit Artfilter und Suche."""

    gewaehlt = QtCore.Signal(list)  # Liste von Pmi

    SPALTEN = ("Nr", "Art", "Wert", "Bezüge", "Flächen")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        oben = QtWidgets.QHBoxLayout()
        self.art = QtWidgets.QComboBox()
        for text, art in (("Alle Arten", None), ("Maße", MASS), ("Toleranzen", TOLERANZ), ("Bezüge", BEZUG)):
            self.art.addItem(tr(text), art)
        self.suche = QtWidgets.QLineEdit()
        self.suche.setPlaceholderText(tr("Suchen (z. B. 0.5, A, ⌀)"))
        self.suche.setClearButtonEnabled(True)
        oben.addWidget(self.art)
        oben.addWidget(self.suche, 1)
        lay.addLayout(oben)
        self.hinweis = QtWidgets.QLabel("")
        self.hinweis.setObjectName("leise")
        lay.addWidget(self.hinweis)
        self.tabelle = QtWidgets.QTableWidget(0, len(self.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in self.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setAlternatingRowColors(True)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i in (0, 1, 3, 4):
            kopf.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tabelle, 1)
        self.pmi: list = []
        self.nur_nummern: set[int] | None = None
        self.art.currentIndexChanged.connect(self._filtern)
        self.suche.textChanged.connect(self._filtern)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)

    def zeige(self, pmi: list):
        self.pmi = pmi
        self.nur_nummern = None
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(pmi))
        for z, p in enumerate(pmi):
            werte = (str(p.nummer), tr(ART_TEXT.get(p.art, p.art)), p.wert_text(), p.bezug_text(),
                     str(len(p.flaechen)))
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s in (0, 4):
                    it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if s == 2:
                    it.setToolTip(_tooltip(p))
                t.setItem(z, s, it)
        t.blockSignals(False)
        self._filtern()

    def nur_ansicht(self, nummern: set[int] | None):
        self.nur_nummern = None if nummern is None else set(nummern)
        self._filtern()

    def _passt(self, p) -> bool:
        art = self.art.currentData()
        if art is not None and p.art != art:
            return False
        if self.nur_nummern is not None and p.nummer not in self.nur_nummern:
            return False
        s = self.suche.text().strip().lower()
        if s:
            text = " ".join((p.wert_text(), p.bezug_text(), p.name, p.typ, tr(ART_TEXT.get(p.art, "")))).lower()
            return all(teil in text for teil in s.split())
        return True

    def _filtern(self):
        sichtbar = 0
        for z, p in enumerate(self.pmi):
            zeigen = self._passt(p)
            self.tabelle.setRowHidden(z, not zeigen)
            sichtbar += zeigen
        self.hinweis.setText(tr("{} von {} PMI").format(sichtbar, len(self.pmi)))

    def sichtbare(self) -> list:
        return [p for z, p in enumerate(self.pmi) if not self.tabelle.isRowHidden(z)]

    def _auswahl(self):
        zeilen = sorted({i.row() for i in self.tabelle.selectedIndexes()})
        self.gewaehlt.emit([self.pmi[z] for z in zeilen])

    def waehle(self, pred) -> int:
        """Zeilen waehlen, fuer die pred(pmi) gilt; gibt die Anzahl zurueck."""
        t = self.tabelle
        t.blockSignals(True)
        t.clearSelection()
        erste = None
        n = 0
        modus = QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows
        for z, p in enumerate(self.pmi):
            if pred(p):
                if t.isRowHidden(z):
                    t.setRowHidden(z, False)
                t.selectionModel().select(t.model().index(z, 0), modus)
                erste = z if erste is None else erste
                n += 1
        t.blockSignals(False)
        if erste is not None:
            t.scrollToItem(t.item(erste, 0))
        self._auswahl()
        return n


def _tooltip(p) -> str:
    teile = [p.name or p.typ, tr("Typ: {}").format(p.typ)]
    if p.modifikatoren:
        teile.append(tr("Modifikatoren: {}").format(", ".join(p.modifikatoren)))
    teile.append(tr("Flächen: {}").format(len(p.flaechen)))
    if not p.semantisch:
        teile.append(tr("nur grafisch (keine auswertbare Semantik)"))
    return "\n".join(teile)


class AnsichtenPanel(QtWidgets.QWidget):
    """Gespeicherte Ansichten des Modells."""

    gewaehlt = QtCore.Signal(object)  # Ansicht oder None (alle PMI)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.liste = QtWidgets.QListWidget()
        lay.addWidget(self.liste)
        self.ansichten: list = []
        self.liste.currentRowChanged.connect(self._zeile)

    def zeige(self, ansichten: list):
        self.ansichten = ansichten
        self.liste.blockSignals(True)
        self.liste.clear()
        self.liste.addItem(tr("(Keine Ansicht – alle PMI)"))
        for a in ansichten:
            n = len(a.pmi_nummern)
            it = QtWidgets.QListWidgetItem(f"{a.name}   ({tr('{} PMI').format(n)})")
            if n == 0:
                it.setForeground(QtGui.QBrush(self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText)))
            self.liste.addItem(it)
        self.liste.setCurrentRow(0)
        self.liste.blockSignals(False)

    def _zeile(self, z):
        self.gewaehlt.emit(None if z <= 0 else self.ansichten[z - 1])
