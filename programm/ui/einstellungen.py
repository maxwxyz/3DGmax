"""Einstellungen: Kamerasteuerung, Farbschema, Sprache."""

from __future__ import annotations

from PySide6 import QtWidgets

from ..i18n import tr

STEUERUNG_TEXT = {
    "catia": ("CATIA",
              "Mitteltaste ziehen: verschieben · Mitteltaste halten + links/rechts halten: drehen · "
              "Mitteltaste halten, links/rechts klicken, ziehen: zoomen · Mitteltaste klicken: Bildmitte · "
              "Mausrad: zoomen"),
    "klassisch": ("Klassisch",
                  "Linke Taste ziehen: drehen · Mitte/rechts oder Umschalt + links: verschieben · "
                  "Mausrad: zoomen · Doppelklick: Drehpunkt"),
}


class EinstellungenDialog(QtWidgets.QDialog):
    def __init__(self, ein, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Einstellungen"))
        self.setMinimumWidth(520)
        self.ein = ein
        form = QtWidgets.QFormLayout(self)
        self.steuerung = QtWidgets.QComboBox()
        for schluessel, (name, _) in STEUERUNG_TEXT.items():
            self.steuerung.addItem(tr(name), schluessel)
        self.steuerung_hilfe = QtWidgets.QLabel()
        self.steuerung_hilfe.setObjectName("leise")
        self.steuerung_hilfe.setWordWrap(True)
        self.steuerung.currentIndexChanged.connect(self._hilfe)
        form.addRow(tr("Kamerasteuerung"), self.steuerung)
        form.addRow("", self.steuerung_hilfe)
        self.thema = QtWidgets.QComboBox()
        for schluessel, name in (("auto", "Wie System"), ("hell", "Hell"), ("dunkel", "Dunkel")):
            self.thema.addItem(tr(name), schluessel)
        form.addRow(tr("Farbschema"), self.thema)
        self.kontrast = QtWidgets.QCheckBox(tr("PMI-Farbe für guten Kontrast anpassen"))
        self.kontrast.setToolTip(tr("Aus: Farben aus der Datei (z. B. weiß aus CATIA), auch wenn sie schlecht lesbar sind"))
        form.addRow(tr("PMI-Farbe"), self.kontrast)
        self.sprache = QtWidgets.QComboBox()
        for schluessel, name in (("auto", tr("Wie System")), ("de", "Deutsch"), ("en", "English")):
            self.sprache.addItem(name, schluessel)
        form.addRow(tr("Sprache (nach Neustart)"), self.sprache)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        form.addRow(knoepfe)
        self._setze(self.steuerung, ein.value("navigation", "catia"))
        self._setze(self.thema, ein.value("thema", "auto"))
        self._setze(self.sprache, ein.value("sprache", "auto"))
        self.kontrast.setChecked(ein.value("pmi_kontrast", True, type=bool))
        self._hilfe()

    @staticmethod
    def _setze(combo, wert):
        i = combo.findData(wert)
        combo.setCurrentIndex(max(i, 0))

    def _hilfe(self):
        self.steuerung_hilfe.setText(tr(STEUERUNG_TEXT[self.steuerung.currentData()][1]))

    def werte(self) -> dict:
        return {"navigation": self.steuerung.currentData(), "thema": self.thema.currentData(),
                "sprache": self.sprache.currentData(), "pmi_kontrast": self.kontrast.isChecked()}
