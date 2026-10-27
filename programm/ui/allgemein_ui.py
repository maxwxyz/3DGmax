"""Dialog Allgemeintoleranzen: ISO 2768-1/-2 Klassen und ISO 22081 Profilwert fuer die Zonendarstellung."""

from __future__ import annotations

from PySide6 import QtWidgets

from ..i18n import tr
from ..kern.toleranzzone import ISO2768_1, ISO2768_2, Allgemein


class AllgemeinDialog(QtWidgets.QDialog):
    def __init__(self, wert: Allgemein | None, aus_datei: Allgemein | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Allgemeintoleranzen"))
        lay = QtWidgets.QFormLayout(self)
        hinweis = QtWidgets.QLabel(tr("Gelten für Flächen ohne eigene Maß- oder Toleranzangabe. Mit "
                                      "„Allgemeintoleranzen zeigen“ violett dargestellt: alle oder an der Auswahl."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addRow(hinweis)
        if aus_datei is not None:
            lay.addRow(QtWidgets.QLabel(tr("In der Datei angegeben: {}").format(aus_datei.text())))
        w = wert or aus_datei or Allgemein()
        self.laenge = QtWidgets.QComboBox()
        self.laenge.addItem(tr("keine"), "")
        for k in ISO2768_1:
            self.laenge.addItem(k, k)
        self.laenge.setCurrentIndex(max(0, self.laenge.findData(w.laenge)))
        lay.addRow(tr("ISO 2768-1 (Maße, Durchmesser)"), self.laenge)
        self.form = QtWidgets.QComboBox()
        self.form.addItem(tr("keine"), "")
        for k in ISO2768_2:
            self.form.addItem(k, k)
        self.form.setCurrentIndex(max(0, self.form.findData(w.form)))
        lay.addRow(tr("ISO 2768-2 (Ebenheit)"), self.form)
        self.profil_an = QtWidgets.QCheckBox(tr("ISO 22081 Flächenprofil"))
        self.profil = QtWidgets.QDoubleSpinBox()
        self.profil.setDecimals(3)
        self.profil.setRange(0.001, 100.0)
        self.profil.setSuffix(" mm")
        self.profil.setValue(w.profil or 1.0)
        self.profil_an.setChecked(bool(w.profil))
        self.profil.setEnabled(bool(w.profil))
        self.profil_an.toggled.connect(self.profil.setEnabled)
        lay.addRow(self.profil_an, self.profil)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addRow(knoepfe)

    def wert(self) -> Allgemein | None:
        a = Allgemein(self.laenge.currentData(), self.form.currentData(),
                      self.profil.value() if self.profil_an.isChecked() else None)
        return None if a.leer() else a
