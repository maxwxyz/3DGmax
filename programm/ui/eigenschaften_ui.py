"""Dialog Modelleigenschaften: Masse, Volumen, Schwerpunkt, Groesse, Dateikopf."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import eigenschaften as ek


class EigenschaftenDialog(QtWidgets.QDialog):
    """Kennwerte fuer das ganze Modell oder die gewaehlten Teile; Dichte einstellbar (wird gemerkt)."""

    def __init__(self, form, pfad: str, datei, einstellungen, umfang: str, parent=None, norm_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("Modelleigenschaften"))
        self.ein = einstellungen
        self.werte = ek.berechne(form)
        self.kopf = ek.lies_kopf(pfad, datei)
        lay = QtWidgets.QVBoxLayout(self)
        titel = QtWidgets.QLabel(f"{os.path.basename(pfad)} – {umfang}")
        titel.setObjectName("titel")
        lay.addWidget(titel)
        form_lay = QtWidgets.QFormLayout()
        form_lay.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        w = self.werte
        self.dichte = QtWidgets.QDoubleSpinBox()
        self.dichte.setDecimals(3)
        self.dichte.setRange(0.001, 30.0)
        self.dichte.setSuffix(" g/cm³")
        self.dichte.setMaximumWidth(150)
        self.dichte.setValue(float(self.ein.value("dichte", ek.DICHTE_STAHL)))
        self.masse = QtWidgets.QLabel("")
        zeilen = [
            (tr("Volumen"), f"{w.volumen / 1000:.3f} cm³  ({w.volumen:.1f} mm³)"),
            (tr("Oberfläche"), f"{w.oberflaeche / 100:.2f} cm²  ({w.oberflaeche:.1f} mm²)"),
            (tr("Dichte"), self.dichte),
            (tr("Masse"), self.masse),
            (tr("Schwerpunkt"), "X {:.3f}  Y {:.3f}  Z {:.3f}".format(*w.schwerpunkt)),
            (tr("Größe (X × Y × Z)"), "{:.3f} × {:.3f} × {:.3f} mm".format(*w.groesse)),
            (tr("Körper / Flächen"), f"{w.koerper} / {w.flaechen}"),
        ]
        k = self.kopf
        datei_zeilen = [(tr("Norm"), norm_text), (tr("Schema"), k.schema), (tr("Erstellt"), k.zeit), (tr("Autor"), k.autor),
                        (tr("Organisation"), k.organisation), (tr("System"), k.system or k.praeprozessor),
                        (tr("Beschreibung"), k.beschreibung)]
        datei_zeilen += [(tr("Produkt"), " – ".join(x for x in p if x)) for p in k.produkte[:8]]
        for text, wert in zeilen:
            form_lay.addRow(text, wert if isinstance(wert, QtWidgets.QWidget) else self._wert(wert))
        trenner = QtWidgets.QLabel(tr("Datei"))
        trenner.setObjectName("leise")
        form_lay.addRow(trenner)
        for text, wert in datei_zeilen:
            if wert:
                form_lay.addRow(text, self._wert(wert))
        lay.addLayout(form_lay)
        hinweis = QtWidgets.QLabel(tr("Werte aus der exakten Geometrie (B-Rep), Längen in mm."))
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        kopie = knoepfe.addButton(tr("Kopieren"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        kopie.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.als_text()))
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self._zeilen = zeilen + datei_zeilen
        self.dichte.valueChanged.connect(self._masse)
        self._masse()

    @staticmethod
    def _wert(text: str) -> QtWidgets.QLabel:
        lab = QtWidgets.QLabel(text)
        lab.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setWordWrap(True)
        return lab

    def _masse(self):
        self.ein.setValue("dichte", self.dichte.value())
        self.masse.setText(f"{self.werte.masse(self.dichte.value()):.4f} kg")

    def als_text(self) -> str:
        out = []
        for text, wert in self._zeilen:
            if isinstance(wert, QtWidgets.QDoubleSpinBox):
                wert = f"{wert.value():.3f} g/cm³"
            elif isinstance(wert, QtWidgets.QLabel):
                wert = wert.text()
            if wert:
                out.append(f"{text}\t{wert}")
        return "\n".join(out)
