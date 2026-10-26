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
    """Tabelle aller PMI mit Artfilter, Suche (Wert, Bezug, Name, Ansicht) und Kontextmenue."""

    gewaehlt = QtCore.Signal(list)  # Liste von Pmi
    befehl = QtCore.Signal(str, object)  # Kontextmenue: ("zoomen"|"ausrichten"|"ansicht", Wert)

    SPALTEN = ("Nr", "Art", "Name", "Wert", "Bezüge", "Ansichten", "Flächen")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        oben = QtWidgets.QHBoxLayout()
        self.art = QtWidgets.QComboBox()
        for text, art in ((tr("Alle Arten"), None), (tr("Maße"), MASS), (tr("Toleranzen"), TOLERANZ),
                          (tr("Bezüge"), BEZUG), (tr("Hinweise"), HINWEIS)):
            self.art.addItem(text, art)
        self.suche = QtWidgets.QLineEdit()
        self.suche.setPlaceholderText(tr("Suchen: Wert, Bezug, Name, Ansicht (z. B. 0.5, A, MBD_A)"))
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
        self.tabelle.setWordWrap(False)
        self.tabelle.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._menue)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i in (0, 1, 2, 4, 5, 6):
            kopf.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tabelle, 1)
        self.pmi: list = []
        self.ansichten_je_pmi: dict[int, list[str]] = {}
        self.ansichten: list = []
        self.nur_nummern: set[int] | None = None
        self.art.currentIndexChanged.connect(self._filtern)
        self.suche.textChanged.connect(self._filtern)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)

    def zeige(self, pmi: list, ansichten: list | None = None):
        self.pmi = pmi
        self.ansichten = list(ansichten or [])
        self.ansichten_je_pmi = {}
        for a in self.ansichten:
            for nr in a.pmi_nummern:
                self.ansichten_je_pmi.setdefault(nr, []).append(a.name)
        self.nur_nummern = None
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(pmi))
        for z, p in enumerate(pmi):
            namen = self.ansichten_je_pmi.get(p.nummer, [])
            werte = (str(p.nummer), tr(ART_TEXT.get(p.art, p.art)), p.name, p.wert_text(), p.bezug_text(),
                     ", ".join(namen), str(len(p.flaechen)))
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s in (0, 6):
                    it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if s == 3:
                    it.setToolTip(_tooltip(p))
                if s == 5 and namen:
                    it.setToolTip(tr("In Ansichten: {}").format(", ".join(namen)))
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
            text = " ".join((p.wert_text(), p.bezug_text(), p.name, p.typ, tr(ART_TEXT.get(p.art, "")),
                             " ".join(self.ansichten_je_pmi.get(p.nummer, [])), " ".join(p.modifikatoren))).lower()
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

    def gewaehlte(self) -> list:
        return [self.pmi[z] for z in sorted({i.row() for i in self.tabelle.selectedIndexes()})]

    def _auswahl(self):
        self.gewaehlt.emit(self.gewaehlte())

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

    # --- Bezuege ---

    def waehle_bezuege(self, auswahl: list) -> int:
        """Bezuege der gewaehlten Toleranzen waehlen (Gruppen wie E-F-G einzeln)."""
        namen = set()
        for p in auswahl:
            for b in p.bezuege:
                namen |= set(b.name.split("-"))
        return self.waehle(lambda q: q.art == BEZUG and q.typ == "Datum" and q.name in namen)

    def waehle_mit_bezug(self, auswahl: list) -> int:
        """Alle Toleranzen, die einen der gewaehlten Bezuege verwenden."""
        namen = {p.name for p in auswahl if p.art == BEZUG}
        return self.waehle(lambda q: q.art == TOLERANZ and any(set(b.name.split("-")) & namen for b in q.bezuege))

    # --- Kontextmenue ---

    def _menue(self, pos):
        auswahl = self.gewaehlte()
        m = QtWidgets.QMenu(self)
        a_zoom = m.addAction(tr("Auf Auswahl zoomen"))
        a_normal = m.addAction(tr("Normal auf Auswahl ausrichten"))
        m.addSeparator()
        a_bez = m.addAction(tr("Bezüge dieser Toleranz wählen"))
        a_mit = m.addAction(tr("Toleranzen mit diesem Bezug wählen"))
        a_bez.setEnabled(any(p.bezuege for p in auswahl))
        a_mit.setEnabled(any(p.art == BEZUG for p in auswahl))
        m.addSeparator()
        menue_ansicht = m.addMenu(tr("In Ansicht zeigen"))
        namen = sorted({n for p in auswahl for n in self.ansichten_je_pmi.get(p.nummer, [])})
        for n in namen:
            menue_ansicht.addAction(n).setData(n)
        menue_ansicht.setEnabled(bool(namen))
        m.addSeparator()
        a_kopie = m.addAction(tr("Kopieren"))
        for a in (a_zoom, a_normal, a_kopie):
            a.setEnabled(bool(auswahl))
        gewaehlt = m.exec(self.tabelle.viewport().mapToGlobal(pos))
        if gewaehlt is None:
            return
        if gewaehlt is a_zoom:
            self.befehl.emit("zoomen", auswahl)
        elif gewaehlt is a_normal:
            self.befehl.emit("ausrichten", auswahl)
        elif gewaehlt is a_bez:
            self.waehle_bezuege(auswahl)
        elif gewaehlt is a_mit:
            self.waehle_mit_bezug(auswahl)
        elif gewaehlt is a_kopie:
            self.kopiere(auswahl)
        elif gewaehlt.data():
            self.befehl.emit("ansicht", gewaehlt.data())

    def kopiere(self, auswahl: list):
        zeilen = ["\t".join((str(p.nummer), tr(ART_TEXT.get(p.art, p.art)), p.name, p.wert_text(), p.bezug_text()))
                  for p in auswahl]
        QtWidgets.QApplication.clipboard().setText("\n".join(zeilen))


def _tooltip(p) -> str:
    teile = [p.name or p.typ, tr("Typ: {}").format(p.typ)]
    if p.modifikatoren:
        teile.append(tr("Modifikatoren: {}").format(", ".join(p.modifikatoren)))
    teile.append(tr("Flächen: {}").format(len(p.flaechen)))
    if not p.semantisch:
        teile.append(tr("nur grafisch (keine auswertbare Semantik)"))
    return "\n".join(teile)


class AnsichtenPanel(QtWidgets.QWidget):
    """Gespeicherte Ansichten des Modells (mit Suche nach Name)."""

    gewaehlt = QtCore.Signal(object)  # Ansicht oder None (alle PMI)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.suche = QtWidgets.QLineEdit()
        self.suche.setPlaceholderText(tr("Ansicht suchen"))
        self.suche.setClearButtonEnabled(True)
        self.suche.textChanged.connect(self._filtern)
        lay.addWidget(self.suche)
        self.liste = QtWidgets.QListWidget()
        lay.addWidget(self.liste)
        reihe = QtWidgets.QHBoxLayout()
        self.zurueck = QtWidgets.QPushButton("◀")
        self.zurueck.setToolTip(tr("Vorherige Ansicht (Bild auf)"))
        self.vor = QtWidgets.QPushButton("▶")
        self.vor.setToolTip(tr("Nächste Ansicht (Bild ab)"))
        self.zurueck.clicked.connect(lambda: self.gehe(-1))
        self.vor.clicked.connect(lambda: self.gehe(+1))
        reihe.addWidget(self.zurueck)
        reihe.addWidget(self.vor)
        lay.addLayout(reihe)
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

    def _filtern(self):
        s = self.suche.text().strip().lower()
        for z, a in enumerate(self.ansichten, 1):
            self.liste.item(z).setHidden(bool(s) and s not in a.name.lower())

    def gehe(self, schritt: int):
        """Naechste/vorherige sichtbare Ansicht mit PMI (Durchklicken der Captures)."""
        kandidaten = [z for z, a in enumerate(self.ansichten, 1)
                      if not self.liste.item(z).isHidden() and a.pmi_nummern] or \
            [z for z in range(1, self.liste.count()) if not self.liste.item(z).isHidden()]
        if not kandidaten:
            return
        jetzt = self.liste.currentRow()
        if schritt > 0:
            ziel = next((z for z in kandidaten if z > jetzt), kandidaten[0])
        else:
            ziel = next((z for z in reversed(kandidaten) if z < jetzt), kandidaten[-1])
        self.liste.setCurrentRow(ziel)

    def waehle_name(self, name: str):
        for z, a in enumerate(self.ansichten, 1):
            if a.name == name:
                self.liste.setCurrentRow(z)
                return
