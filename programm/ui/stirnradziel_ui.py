"""Aus einem Achsabstandsfenster und einer Zieluebersetzung ein Stirnradpaar waehlen."""

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.stirnradgeometrie import radpaarvorschlaege


class StirnradzielDialog(QtWidgets.QDialog):
    def __init__(self, parent, vorgaben):
        super().__init__(parent)
        self.setWindowTitle(tr("Zähnezahlen vorschlagen"))
        self.resize(640, 460)
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.felder = {}
        for k, text in (("i", tr("Zielübersetzung |i| = z₂/z₁")), ("a", tr("Zielachsabstand [mm]")),
                        ("da", tr("Zulässige Achsabstandsabweichung ± [mm]")),
                        ("m", tr("Modul [mm]")), ("alpha", tr("Eingriffswinkel [°]"))):
            feld = QtWidgets.QLineEdit(str(vorgaben.get(k, "")))
            form.addRow(text, feld)
            self.felder[k] = feld
        self.tabelle = QtWidgets.QTableWidget(0, 7)
        self.tabelle.setHorizontalHeaderLabels(["z₁", "z₂", "|i|", "Δi", "a [mm]", "Δa [mm]", "εα"])
        self.tabelle.verticalHeader().hide()
        self.tabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.tabelle)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.uebernehmen = knoepfe.addButton(tr("Zähnezahlen übernehmen"), knoepfe.ButtonRole.AcceptRole)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        layout.addWidget(knoepfe)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self._berechnen)
        for feld in self.felder.values():
            feld.textChanged.connect(self._geaendert)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)
        self.tabelle.itemDoubleClicked.connect(self.accept)
        self._berechnen()

    def _auswahl(self):
        self.uebernehmen.setEnabled(bool(self.tabelle.selectedItems()))

    def _geaendert(self):
        self.tabelle.setRowCount(0)
        self.uebernehmen.setEnabled(False)
        self.status.clear()
        self.timer.start()

    def _berechnen(self):
        self.timer.stop()
        self.tabelle.setRowCount(0)
        self.uebernehmen.setEnabled(False)
        if not all(f.text().strip() for f in self.felder.values()):
            self.status.setText(tr("Fehlende Eingaben ergänzen."))
            return
        try:
            self.werte = {k: float(f.text().replace(",", ".")) for k, f in self.felder.items()}
        except ValueError:
            self.status.setText(tr("Zielwerte, Modul und Eingriffswinkel prüfen."))
            return
        try:
            self.paare = radpaarvorschlaege(**self.werte)
        except (ValueError, ArithmeticError) as e:
            self.status.setText(str(e))
            return
        if not self.paare:
            self.status.setText(tr("Kein geometrisch geeignetes Paar im Achsabstandsfenster. Modul, Winkel oder Abstandsabweichung anpassen."))
            return
        self.status.setText(tr("Bis zu zwölf Paare nach Übersetzungsfehler, dann nach Achsabstandsfehler. εα ist die Profilüberdeckung."))
        self.tabelle.setRowCount(len(self.paare))
        for row, p in enumerate(self.paare):
            werte = (p.z1, p.z2, p.i, p.i-self.werte["i"], p.a, p.a-self.werte["a"], p.epsilon)
            for col, wert in enumerate(werte):
                item = QtWidgets.QTableWidgetItem(f"{wert:.7g}")
                self.tabelle.setItem(row, col, item)
        self.tabelle.selectRow(0)
