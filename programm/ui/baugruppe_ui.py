"""Leiste Zusammenbau: Teile per Flaechenpaar fangen, Verbindungen, offene Freiheitsgrade und Wiggle."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import verbindung as vb


def _tabelle(spalten) -> QtWidgets.QTableWidget:
    t = QtWidgets.QTableWidget(0, len(spalten))
    t.setHorizontalHeaderLabels([tr(s) for s in spalten])
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class BaugruppePanel(QtWidgets.QWidget):
    verbinden = QtCore.Signal(float)  # Versatz in mm
    entfernen = QtCore.Signal(int)  # Nummer der Verbindung
    zuruecksetzen = QtCore.Signal()
    wiggle = QtCore.Signal(object)  # Knotennummer oder None (aus)
    toleranz = QtCore.Signal(int, float)  # Nummer der Verbindung, neuer Spielraum (mm)

    VERBINDUNG_SPALTEN = ("Nr", "Teil", "Gegenteil", "Art", "Versatz", "Erfüllt", "Spielraum", "Herkunft")
    TEIL_SPALTEN = ("Teil", "Freiheitsgrade", "Lagestreuung X/Y/Z", "Offene Bewegungen")
    WIGGLE_ART = (("frei", "Freie Freiheitsgrade"), ("toleranz", "Innerhalb der Toleranzen"))

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        hinweis = QtWidgets.QLabel(tr("Erst eine Fläche am Teil wählen, das sich bewegen soll, dann mit Strg/⌘ die "
                                      "Gegenfläche am anderen Teil: zwei Ebenen liegen danach aufeinander, zwei "
                                      "Zylinder sind koaxial. Die Freiheitsgrade zeigen, was noch offen ist."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        reihe.addWidget(QtWidgets.QLabel(tr("Versatz")))
        self.versatz = QtWidgets.QDoubleSpinBox()
        self.versatz.setRange(-1000.0, 1000.0)
        self.versatz.setDecimals(3)
        self.versatz.setSuffix(" mm")
        self.versatz.setToolTip(tr("Abstand zwischen zwei Ebenen (0: Berührung)"))
        reihe.addWidget(self.versatz)
        self.knopf = QtWidgets.QPushButton(tr("Verbinden"))
        self.knopf.clicked.connect(lambda: self.verbinden.emit(self.versatz.value()))
        reihe.addWidget(self.knopf, 1)
        lay.addLayout(reihe)
        self.verbindungen = _tabelle(self.VERBINDUNG_SPALTEN)
        self.verbindungen.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)
        self.verbindungen.setToolTip(tr("Spielraum per Doppelklick ändern: eben ± entlang der Normalen, koaxial "
                                        "radiales Spiel (mm)"))
        self.verbindungen.itemChanged.connect(self._spielraum_geaendert)
        lay.addWidget(self.verbindungen, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.weg = QtWidgets.QPushButton(tr("Verbindung entfernen"))
        self.weg.clicked.connect(self._entfernen)
        self.zurueck = QtWidgets.QPushButton(tr("Zurücksetzen"))
        self.zurueck.setToolTip(tr("Alle Verbindungen entfernen, Teile wieder wie in der Datei"))
        self.zurueck.clicked.connect(self.zuruecksetzen.emit)
        reihe.addWidget(self.weg)
        reihe.addStretch(1)
        reihe.addWidget(self.zurueck)
        lay.addLayout(reihe)
        self.teile = _tabelle(self.TEIL_SPALTEN)
        self.teile.itemSelectionChanged.connect(self._teil_gewaehlt)
        lay.addWidget(self.teile, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.wiggle_an = QtWidgets.QPushButton(tr("Wiggle"))
        self.wiggle_an.setCheckable(True)
        self.wiggle_an.setToolTip(tr("Gewähltes Teil in seinen offenen Freiheitsgraden hin und her bewegen"))
        self.wiggle_an.toggled.connect(self._teil_gewaehlt)
        self.wiggle_art = QtWidgets.QComboBox()
        for schluessel, text in self.WIGGLE_ART:
            self.wiggle_art.addItem(tr(text), schluessel)
        self.wiggle_art.currentIndexChanged.connect(self._teil_gewaehlt)
        self.faktor = QtWidgets.QDoubleSpinBox()
        self.faktor.setRange(1.0, 1000.0)
        self.faktor.setValue(10.0)
        self.faktor.setPrefix("× ")
        self.faktor.setToolTip(tr("Überhöhung der Bewegung innerhalb der Toleranzen (1 = wahre Größe)"))
        self.weg_mm = QtWidgets.QDoubleSpinBox()
        self.weg_mm.setRange(0.1, 1000.0)
        self.weg_mm.setValue(5.0)
        self.weg_mm.setSuffix(" mm")
        self.winkel = QtWidgets.QDoubleSpinBox()
        self.winkel.setRange(1.0, 180.0)
        self.winkel.setValue(15.0)
        self.winkel.setSuffix(" °")
        reihe.addWidget(self.wiggle_an)
        reihe.addWidget(self.wiggle_art)
        reihe.addWidget(self.faktor)
        reihe.addWidget(QtWidgets.QLabel(tr("Weg")))
        reihe.addWidget(self.weg_mm)
        reihe.addWidget(QtWidgets.QLabel(tr("Winkel")))
        reihe.addWidget(self.winkel)
        reihe.addStretch(1)
        lay.addLayout(reihe)
        self._nummern: list[int] = []
        self._teil_nummern: list[int] = []
        self.zeige(vb.Baugruppe(), {})

    def zeige(self, baugruppe: vb.Baugruppe, namen: dict[int, str], streuung: dict | None = None):
        """streuung: Knotennummer -> (Verschiebung X/Y/Z in mm, freie Freiheitsgrade)."""
        verletzt = {v.nummer for v in baugruppe.verletzt()}
        streuung = streuung or {}
        t = self.verbindungen
        t.blockSignals(True)
        t.setRowCount(len(baugruppe.verbindungen))
        self._nummern = [v.nummer for v in baugruppe.verbindungen]
        for z, v in enumerate(baugruppe.verbindungen):
            werte = (str(v.nummer), namen.get(v.teil, str(v.teil)), namen.get(v.gegen_teil, str(v.gegen_teil)),
                     tr(vb.ART_TEXT[v.art]), f"{v.versatz:g}" if v.art == vb.EBEN else "",
                     tr("nein") if v.nummer in verletzt else tr("ja"),
                     (f"±{v.toleranz:.4g}" if v.art == vb.EBEN else f"{v.toleranz:.4g}"), v.quelle)
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s != 6:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 5 and v.nummer in verletzt:
                    it.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                t.setItem(z, s, it)
        t.blockSignals(False)
        t.resizeColumnsToContents()
        teile = baugruppe.teile()
        self._teil_nummern = teile
        t = self.teile
        t.blockSignals(True)
        t.setRowCount(len(teile))
        for z, nr in enumerate(teile):
            if baugruppe.fest(nr):
                werte = (namen.get(nr, str(nr)), "–", "", tr("fest (Bezugsteil)"))
            else:
                basis = baugruppe.freiheitsgrade(nr)
                texte = vb.beschreibe(basis)
                weg = streuung.get(nr)
                lage = "" if weg is None else "±" + " / ".join(f"{x:.3f}" for x in weg[0])
                werte = (namen.get(nr, str(nr)), str(len(basis)), lage, "; ".join(texte) if texte else tr("bestimmt"))
            for s, w in enumerate(werte):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        t.blockSignals(False)
        t.resizeColumnsToContents()
        for k in (self.weg, self.zurueck):
            k.setEnabled(bool(baugruppe.verbindungen))
        self.wiggle_an.setEnabled(bool(teile))

    def _spielraum_geaendert(self, it):
        if it.column() != 6 or it.row() >= len(self._nummern):
            return
        try:
            wert = abs(float(it.text().replace("±", "").replace(",", ".")))
        except ValueError:
            return
        self.toleranz.emit(self._nummern[it.row()], wert)

    def _entfernen(self):
        zeilen = {i.row() for i in self.verbindungen.selectedIndexes()}
        if len(zeilen) == 1:
            self.entfernen.emit(self._nummern[zeilen.pop()])

    def gewaehltes_teil(self):
        zeilen = {i.row() for i in self.teile.selectedIndexes()}
        return self._teil_nummern[zeilen.pop()] if len(zeilen) == 1 else None

    def _teil_gewaehlt(self, *_):
        self.wiggle.emit(self.gewaehltes_teil() if self.wiggle_an.isChecked() else None)
