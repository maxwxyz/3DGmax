"""Leiste Zusammenbau: Teile per Flaechenpaar fangen, Verbindungen, offene Freiheitsgrade und Wiggle; Messgroessen
(Spalt, Buendigkeit) mit Worst Case, Monte Carlo und Beitragenden."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import baugruppe_mass as bm
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
    umkehren = QtCore.Signal(int)  # Nummer der Verbindung
    tauschen = QtCore.Signal(int)
    mass_anlegen = QtCore.Signal()
    mass_entfernen = QtCore.Signal(int)  # Nummer der Messgroesse
    soll = QtCore.Signal(int, str)  # Nummer der Messgroesse, Soll-Text
    mass_pdf = QtCore.Signal()

    VERBINDUNG_SPALTEN = ("Nr", "Teil", "Gegenteil", "Art", "Versatz", "Erfüllt", "Spielraum", "Herkunft")
    TEIL_SPALTEN = ("Teil", "Freiheitsgrade", "Lagestreuung X/Y/Z", "Offene Bewegungen")
    WIGGLE_ART = (("frei", "Freie Freiheitsgrade"), ("toleranz", "Innerhalb der Toleranzen"))
    MASS_SPALTEN = ("Nr", "Messgröße", "Nennwert", "Worst Case", "Monte Carlo (99,73 %)", "Soll", "Außerhalb", "Cpk")
    BEITRAG_SPALTEN = ("Verbindung", "Art", "Bereich", "Anteil Worst Case", "Anteil statistisch")

    def __init__(self, parent=None):
        super().__init__(parent)
        aussen = QtWidgets.QVBoxLayout(self)
        aussen.setContentsMargins(0, 0, 0, 0)
        self.reiter = QtWidgets.QTabWidget()
        self.reiter.setDocumentMode(True)
        aussen.addWidget(self.reiter)
        seite = QtWidgets.QWidget()
        self.reiter.addTab(seite, tr("Verbindungen"))
        lay = QtWidgets.QVBoxLayout(seite)
        lay.setContentsMargins(6, 6, 6, 6)
        hinweis = QtWidgets.QLabel(tr("Erst eine Fläche am Teil wählen, das sich bewegen soll, dann mit Strg/⌘ die "
                                      "Gegenfläche am anderen Teil: zwei Ebenen liegen aufeinander, zwei Zylinder "
                                      "sind koaxial, Zylinder auf Ebene ist ein Bolzen im Langloch, Kugel auf Ebene "
                                      "ein Punktkontakt, zwei Kugeln ein Kugelgelenk. Die Freiheitsgrade zeigen, was "
                                      "noch offen ist."))
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
        self.verbindungen.setToolTip(tr("Spielraum per Doppelklick ändern: eben, Langloch und Punkt ± entlang der "
                                        "Normalen, koaxial und Kugel radiales Spiel (mm)"))
        self.verbindungen.itemChanged.connect(self._spielraum_geaendert)
        lay.addWidget(self.verbindungen, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.weg = QtWidgets.QPushButton(tr("Verbindung entfernen"))
        self.weg.clicked.connect(self._entfernen)
        self.umkehr_knopf = QtWidgets.QPushButton(tr("Umkehren"))
        self.umkehr_knopf.setToolTip(tr("Bewegtes Teil an der gewählten Verbindung um 180° drehen: Zylinder Ende gegen "
                                        "Ende, auf einer Ebene halb herum"))
        self.umkehr_knopf.clicked.connect(lambda: self._fuer_gewaehlte(self.umkehren))
        self.tausch_knopf = QtWidgets.QPushButton(tr("Teile tauschen"))
        self.tausch_knopf.setToolTip(tr("Das andere Teil der gewählten Verbindung bewegt sich (Bezugsteil wechselt)"))
        self.tausch_knopf.clicked.connect(lambda: self._fuer_gewaehlte(self.tauschen))
        self.zurueck = QtWidgets.QPushButton(tr("Zurücksetzen"))
        self.zurueck.setToolTip(tr("Alle Verbindungen entfernen, Teile wieder wie in der Datei"))
        self.zurueck.clicked.connect(self.zuruecksetzen.emit)
        reihe.addWidget(self.weg)
        reihe.addWidget(self.umkehr_knopf)
        reihe.addWidget(self.tausch_knopf)
        reihe.addStretch(1)
        reihe.addWidget(self.zurueck)
        lay.addLayout(reihe)
        self.teile = _tabelle(self.TEIL_SPALTEN)
        self.teile.itemSelectionChanged.connect(self._teil_gewaehlt)
        lay.addWidget(self.teile, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.wiggle_an = QtWidgets.QPushButton(tr("▶ Wiggle"))
        self.wiggle_an.setCheckable(True)
        self.wiggle_an.setToolTip(tr("Gewähltes Teil in seinen offenen Freiheitsgraden hin und her bewegen"))
        self.wiggle_an.toggled.connect(
            lambda an: self.wiggle_an.setText(tr("⏸ Anhalten") if an else tr("▶ Wiggle")))  # Zustand sichtbar
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
        self._mass_nummern: list[int] = []
        self._ergebnisse: dict = {}
        self._baue_masse()
        self.zeige(vb.Baugruppe(), {})

    def _baue_masse(self):
        seite = QtWidgets.QWidget()
        self.reiter.addTab(seite, tr("Messgrößen"))
        lay = QtWidgets.QVBoxLayout(seite)
        lay.setContentsMargins(6, 6, 6, 6)
        hinweis = QtWidgets.QLabel(tr("Zwei parallele Ebenen an verschiedenen Teilen wählen (erst die gemessene, dann "
                                      "mit Strg/⌘ die Bezugsfläche): gegenüberliegend ergibt einen Spalt, "
                                      "gleichgerichtet eine Bündigkeit. Alle Verbindungen streuen in ihren "
                                      "Spielräumen; Soll per Doppelklick, z. B. 3,8 … 4,2."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.mass_knopf = QtWidgets.QPushButton(tr("Messgröße aus Auswahl"))
        self.mass_knopf.clicked.connect(self.mass_anlegen.emit)
        self.mass_weg = QtWidgets.QPushButton(tr("Entfernen"))
        self.mass_weg.clicked.connect(self._mass_entfernen)
        self.mass_pdf_knopf = QtWidgets.QPushButton(tr("Als PDF …"))
        self.mass_pdf_knopf.clicked.connect(self.mass_pdf.emit)
        reihe.addWidget(self.mass_knopf, 1)
        reihe.addWidget(self.mass_weg)
        reihe.addWidget(self.mass_pdf_knopf)
        lay.addLayout(reihe)
        self.masse = _tabelle(self.MASS_SPALTEN)
        self.masse.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)
        self.masse.itemChanged.connect(self._soll_geaendert)
        self.masse.itemSelectionChanged.connect(self._zeige_beitraege)
        lay.addWidget(self.masse, 1)
        titel = QtWidgets.QLabel(tr("Beitragende der gewählten Messgröße"))
        titel.setObjectName("leise")
        lay.addWidget(titel)
        self.beitraege = _tabelle(self.BEITRAG_SPALTEN)
        self.beitraege.setToolTip(tr("Bereich: Worst-Case-Breite, wenn nur diese Verbindung streut; statistisch: "
                                     "Varianzanteil aus Monte Carlo"))
        lay.addWidget(self.beitraege, 1)
        self.mass_hinweis = QtWidgets.QLabel("")
        self.mass_hinweis.setWordWrap(True)
        lay.addWidget(self.mass_hinweis)

    def zeige_masse(self, baugruppe: vb.Baugruppe, namen: dict[int, str], ergebnisse: dict):
        """ergebnisse: Nummer der Messgroesse -> baugruppe_mass.Ergebnis."""
        self._ergebnisse = ergebnisse
        self._arten = {v.nummer: v.art for v in baugruppe.verbindungen}
        t = self.masse
        alt = self.gewaehlte_messgroesse()
        t.blockSignals(True)
        t.setRowCount(len(baugruppe.masse))
        self._mass_nummern = [m.nummer for m in baugruppe.masse]
        for z, m in enumerate(baugruppe.masse):
            e = ergebnisse.get(m.nummer)
            werte = [str(m.nummer), bm.text(m, namen)]
            if e is None:
                werte += [""] * 3
            else:
                werte += [f"{e.nenn:.4f}", f"{e.wc_min:.4f} … {e.wc_max:.4f}", f"{e.mc_min:.4f} … {e.mc_max:.4f}"]
            werte.append(bm.soll_text(m))
            werte.append("" if e is None or e.aussen is None else f"{e.aussen:.2%}")
            werte.append("" if e is None or e.cpk is None else f"{e.cpk:.2f}")
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s != 5:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 6 and e is not None and e.aussen:
                    it.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                t.setItem(z, s, it)
        t.blockSignals(False)
        t.resizeColumnsToContents()
        if alt in self._mass_nummern:
            t.selectRow(self._mass_nummern.index(alt))
        elif self._mass_nummern:
            t.selectRow(len(self._mass_nummern) - 1)
        for k in (self.mass_weg, self.mass_pdf_knopf):
            k.setEnabled(bool(baugruppe.masse))
        self._zeige_beitraege()

    def gewaehlte_messgroesse(self):
        zeilen = {i.row() for i in self.masse.selectedIndexes()}
        return self._mass_nummern[zeilen.pop()] if len(zeilen) == 1 else None

    def _zeige_beitraege(self):
        e = self._ergebnisse.get(self.gewaehlte_messgroesse())
        t = self.beitraege
        liste = e.beitraege if e is not None else []
        t.setRowCount(len(liste))
        for z, b in enumerate(liste):
            werte = (str(b.verbindung), tr(vb.ART_TEXT.get(self._arten.get(b.verbindung), "")), f"{b.bereich:.4f}",
                     f"{b.anteil_wc:.0%}", f"{b.anteil_var:.0%}")
            for s, w in enumerate(werte):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        t.resizeColumnsToContents()
        if e is None:
            self.mass_hinweis.setText("")
        elif e.unbestimmt:
            self.mass_hinweis.setText(tr("Die Messgröße hängt von offenen Freiheitsgraden ab: diese bleiben in "
                                         "Nennlage – erst die Teile vollständig verbinden."))
        else:
            self.mass_hinweis.setText(tr("Mittelwert {:.4f} mm, σ {:.4f} mm").format(e.mittel, e.std))

    def _soll_geaendert(self, it):
        if it.column() == 5 and it.row() < len(self._mass_nummern):
            self.soll.emit(self._mass_nummern[it.row()], it.text())

    def _mass_entfernen(self):
        nr = self.gewaehlte_messgroesse()
        if nr is not None:
            self.mass_entfernen.emit(nr)

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
                     tr(vb.ART_TEXT[v.art]), f"{v.versatz:g}" if v.art in vb.MIT_VERSATZ else "",
                     tr("nein") if v.nummer in verletzt else tr("ja"),
                     (f"±{v.toleranz:.4g}" if v.art in vb.MIT_VERSATZ else f"{v.toleranz:.4g}"), v.quelle)
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
        for k in (self.weg, self.zurueck, self.umkehr_knopf, self.tausch_knopf):
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
        self._fuer_gewaehlte(self.entfernen)

    def _fuer_gewaehlte(self, signal):
        zeilen = {i.row() for i in self.verbindungen.selectedIndexes()}
        if len(zeilen) == 1:
            signal.emit(self._nummern[zeilen.pop()])

    def gewaehltes_teil(self):
        zeilen = {i.row() for i in self.teile.selectedIndexes()}
        return self._teil_nummern[zeilen.pop()] if len(zeilen) == 1 else None

    def _teil_gewaehlt(self, *_):
        self.wiggle.emit(self.gewaehltes_teil() if self.wiggle_an.isChecked() else None)
