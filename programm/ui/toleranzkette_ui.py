"""Fenster Toleranzkette: Glieder aus der PMI-Liste oder der 3D-Auswahl, Verteilung und Cp je Glied, Ergebnis nach
Worst Case, statistisch und Monte Carlo mit Beitragsanteilen."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import toleranzkette as tk


class ToleranzketteFenster(QtWidgets.QDialog):
    flaechen_zeigen = QtCore.Signal(set)  # Flaechen der gewaehlten Glieder (aus der 3D-Auswahl)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Toleranzkette"))
        self.resize(940, 480)
        self.glieder: list[tk.Glied] = []
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Maße in der PMI-Liste wählen und übernehmen, oder Flächen im Modell in "
                                      "Kettenreihenfolge wählen (Strg/⌘) und „Aus 3D-Auswahl“: Richtung aus der "
                                      "Geometrie, Werte aus den PMI, sonst Allgemeintoleranz. Richtung + vergrößert, − "
                                      "verkleinert das Schlussmaß. Statistik: normal (Toleranz = ±3σ · Cp) oder "
                                      "gleichverteilt."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        self.tabelle = QtWidgets.QTableWidget(0, len(tk.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in tk.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.itemSelectionChanged.connect(self._zeige_flaechen)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        kopf.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)  # lange Namen ohne Querlauf
        lay.addWidget(self.tabelle, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.plus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (+)"))
        self.minus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (−)"))
        self.auswahl = QtWidgets.QPushButton(tr("＋ Aus 3D-Auswahl"))
        self.auswahl.setToolTip(tr("Flächen in Kettenreihenfolge: je zwei aufeinanderfolgende bilden ein Glied"))
        self.drehen = QtWidgets.QPushButton(tr("Richtung umkehren"))
        self.weg = QtWidgets.QPushButton(tr("Entfernen"))
        for k in (self.plus, self.minus, self.auswahl, self.drehen, self.weg):
            reihe.addWidget(k)
        self.lage = QtWidgets.QCheckBox(tr("Lagetoleranzen"))
        self.lage.setChecked(True)
        self.lage.setToolTip(tr("Position, Symmetrie, Koaxialität und Profil mit Bezug an der ersten und letzten Fläche "
                                "als eigene Glieder (Zwischenflächen heben sich auf)"))
        reihe.addWidget(self.lage)
        reihe.addStretch(1)
        reihe.addWidget(QtWidgets.QLabel(tr("Prozessfähigkeit Cp")))
        self.cp = QtWidgets.QDoubleSpinBox()
        self.cp.setRange(0.5, 3.0)
        self.cp.setSingleStep(0.1)
        self.cp.setDecimals(2)
        self.cp.setValue(1.0)
        self.cp.setToolTip(tr("Cp der Kette für Glieder ohne eigenen Wert: σ = Toleranz / (6 · Cp); 1,0 = ±3σ, "
                              "1,33 = ±4σ"))
        self.cp.valueChanged.connect(self._fuelle)
        reihe.addWidget(self.cp)
        lay.addLayout(reihe)
        self.ergebnis = QtWidgets.QLabel("")
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lay.addWidget(self.ergebnis)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        self.export = knoepfe.addButton(tr("Als CSV speichern …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.pdf = knoepfe.addButton(tr("PDF-Bericht …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.drehen.clicked.connect(self._drehen)
        self.weg.clicked.connect(self._entfernen)
        self.export.clicked.connect(lambda: self.speichere())
        self._fuelle()

    def leeren(self):
        """Neues Modell: die Glieder verweisen auf PMI des alten Modells."""
        self.glieder = []
        self._fuelle()

    def ergaenze(self, glieder: list):
        """Glieder aus der 3D-Auswahl anhaengen."""
        self.glieder.extend(glieder)
        self._fuelle()

    def uebernimm(self, pmi_liste: list, richtung: int = 1) -> int:
        n = 0
        for p in pmi_liste:
            g = tk.glied_von_pmi(p, richtung)
            if g is not None:
                self.glieder.append(g)
                n += 1
        self._fuelle()
        return n

    def _drehen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}):
            self.glieder[z].richtung *= -1
        self._fuelle()

    def _entfernen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}, reverse=True):
            del self.glieder[z]
        self._fuelle()

    def _zeige_flaechen(self):
        zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
        self.flaechen_zeigen.emit({f for z in zeilen if z < len(self.glieder) for f in self.glieder[z].flaechen})

    def _verteilung(self, g, wert):
        g.verteilung = wert
        self._rechne()

    def _cp_glied(self, g, wert):
        g.cp = wert or None  # 0 = Cp der Kette
        self._rechne()

    def _fuelle(self):
        t = self.tabelle
        t.setRowCount(len(self.glieder))
        for z, g in enumerate(self.glieder):
            werte = (g.name, "+" if g.richtung > 0 else "−", f"{g.nenn:.4g}", f"{g.hoechst:.4g}", f"{g.mindest:.4g}",
                     f"{g.toleranz:.4g}", tr(tk.QUELLE[g.quelle]))
            for s, w in enumerate(werte):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
            if g.quelle == "ohne":
                t.item(z, 6).setForeground(QtGui.QColor("#c0392b"))
            if g.quelle == "lage":
                t.item(z, 2).setText("–")  # Verschiebung um die Nennlage
            art = QtWidgets.QComboBox()
            for schluessel, text in tk.VERTEILUNG.items():
                art.addItem(tr(text), schluessel)
            art.setCurrentIndex(max(0, art.findData(g.verteilung)))
            art.currentIndexChanged.connect(lambda _i, g=g, a=art: self._verteilung(g, a.currentData()))
            t.setCellWidget(z, 7, art)
            cp = QtWidgets.QDoubleSpinBox()
            cp.setRange(0.0, 3.0)
            cp.setSingleStep(0.1)
            cp.setDecimals(2)
            cp.setSpecialValueText(tr("Kette"))  # 0: Cp der Kette
            cp.setValue(g.cp or 0.0)
            cp.valueChanged.connect(lambda w, g=g: self._cp_glied(g, w))
            t.setCellWidget(z, 8, cp)
        self._rechne()

    def _rechne(self):
        t = self.tabelle
        for z, g in enumerate(self.glieder):
            w = t.cellWidget(z, 8)
            if w is not None:
                w.setEnabled(g.verteilung == "normal")
        self.e = tk.berechne(self.glieder, cp=self.cp.value())
        e = self.e
        for z, anteil in enumerate(e.anteile):
            t.setItem(z, 9, QtWidgets.QTableWidgetItem(f"{anteil:.0%}"))
        if not self.glieder:
            self.ergebnis.setText(tr("Noch keine Glieder."))
        else:
            self.ergebnis.setText(
                f"<b>{tr('Schlussmaß')}</b> {e.nenn:.4f} mm &nbsp; · &nbsp; "
                f"<b>{tr('Worst Case')}</b> {e.wc_min:.4f} … {e.wc_max:.4f} mm "
                f"(±{(e.wc_max - e.wc_min) / 2:.4f}) <br>"
                f"<b>{tr('Statistisch (RSS)')}</b> {e.mitte:.4f} ± {e.rss:.4f} mm (±3σ) "
                f"&nbsp; · &nbsp; "
                f"<b>{tr('Monte Carlo')}</b> {e.mc_min:.4f} … {e.mc_max:.4f} mm ({tr('99,73 %')})")
        self.export.setEnabled(bool(self.glieder))
        self.pdf.setEnabled(bool(self.glieder))

    def speichere(self, pfad: str = "") -> str | None:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Toleranzkette speichern"), "toleranzkette.csv",
                                                            "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(tk.als_csv(self.glieder, self.e, self.cp.value()))
        return pfad
