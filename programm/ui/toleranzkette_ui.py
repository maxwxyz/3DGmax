"""Fenster Toleranzkette: Masse aus der PMI-Liste uebernehmen, Richtung setzen, Ergebnis nach drei Verfahren."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import toleranzkette as tk


class ToleranzketteFenster(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Toleranzkette"))
        self.resize(720, 460)
        self.glieder: list[tk.Glied] = []
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Maße in der PMI-Liste wählen und übernehmen; Richtung + vergrößert, − verkleinert "
                                      "das Schlussmaß. Statistik: Normalverteilung, Toleranz = ±3σ · Cp."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        self.tabelle = QtWidgets.QTableWidget(0, len(tk.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in tk.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        kopf.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)  # lange Namen ohne Querlauf
        lay.addWidget(self.tabelle, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.plus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (+)"))
        self.minus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (−)"))
        self.drehen = QtWidgets.QPushButton(tr("Richtung umkehren"))
        self.weg = QtWidgets.QPushButton(tr("Entfernen"))
        for k in (self.plus, self.minus, self.drehen, self.weg):
            reihe.addWidget(k)
        reihe.addStretch(1)
        reihe.addWidget(QtWidgets.QLabel(tr("Prozessfähigkeit Cp")))
        self.cp = QtWidgets.QDoubleSpinBox()
        self.cp.setRange(0.5, 3.0)
        self.cp.setSingleStep(0.1)
        self.cp.setDecimals(2)
        self.cp.setValue(1.0)
        self.cp.setToolTip(tr("Statistik: σ = Toleranz / (6 · Cp); 1,0 = ±3σ, 1,33 = ±4σ"))
        self.cp.valueChanged.connect(self._fuelle)
        reihe.addWidget(self.cp)
        lay.addLayout(reihe)
        self.ergebnis = QtWidgets.QLabel("")
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lay.addWidget(self.ergebnis)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        self.export = knoepfe.addButton(tr("Als CSV speichern …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
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

    def _fuelle(self):
        t = self.tabelle
        t.setRowCount(len(self.glieder))
        for z, g in enumerate(self.glieder):
            werte = (g.name, "+" if g.richtung > 0 else "−", f"{g.nenn:.4g}", f"{g.hoechst:.4g}", f"{g.mindest:.4g}",
                     f"{g.toleranz:.4g}")
            for s, w in enumerate(werte):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        self.e = tk.berechne(self.glieder, k=3.0 * self.cp.value())
        e = self.e
        if not self.glieder:
            self.ergebnis.setText(tr("Noch keine Glieder."))
        else:
            self.ergebnis.setText(
                f"<b>{tr('Schlussmaß')}</b> {e.nenn:.4f} mm &nbsp; · &nbsp; "
                f"<b>{tr('Worst Case')}</b> {e.wc_min:.4f} … {e.wc_max:.4f} mm "
                f"(±{(e.wc_max - e.wc_min) / 2:.4f}) <br>"
                f"<b>{tr('Statistisch (RSS)')}</b> {e.mitte:.4f} ± {e.rss:.4f} mm (Cp {self.cp.value():.2f}) "
                f"&nbsp; · &nbsp; "
                f"<b>{tr('Monte Carlo')}</b> {e.mc_min:.4f} … {e.mc_max:.4f} mm (99,73 %)")
        self.export.setEnabled(bool(self.glieder))

    def speichere(self, pfad: str = "") -> str | None:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Toleranzkette speichern"), "toleranzkette.csv",
                                                            "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(tk.als_csv(self.glieder, self.e))
        return pfad
