"""Einstellungen: Kamerasteuerung, Farbschema, Sprache."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

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
        self.pmi_eigen = QtWidgets.QCheckBox(tr("Eigene PMI-Farbe"))
        self.pmi_farbe = FarbKnopf(ein.value("pmi_eigene_farbe", "#d4145a"))
        reihe = QtWidgets.QHBoxLayout()
        reihe.addWidget(self.pmi_eigen)
        reihe.addWidget(self.pmi_farbe)
        reihe.addStretch(1)
        form.addRow(tr("PMI-Farbe"), self.kontrast)
        form.addRow("", reihe)
        self.draht_kontrast = QtWidgets.QCheckBox(tr("Kanten in Kontrastfarbe"))
        self.draht_kontrast.setToolTip(tr("Aus: Kanten in der Bauteil- bzw. Flächenfarbe (auf hellem Grund oft schwach)"))
        form.addRow(tr("Drahtmodell"), self.draht_kontrast)
        self.hg_eigen = QtWidgets.QCheckBox(tr("Eigener Hintergrund"))
        self.hg_oben = FarbKnopf(ein.value("hg_oben", "#dfe5ee"))
        self.hg_unten = FarbKnopf(ein.value("hg_unten", "#a9b3c2"))
        reihe2 = QtWidgets.QHBoxLayout()
        reihe2.addWidget(self.hg_eigen)
        reihe2.addWidget(QtWidgets.QLabel(tr("oben")))
        reihe2.addWidget(self.hg_oben)
        reihe2.addWidget(QtWidgets.QLabel(tr("unten")))
        reihe2.addWidget(self.hg_unten)
        reihe2.addStretch(1)
        form.addRow(tr("Hintergrund"), reihe2)
        self.pmi_eigen.toggled.connect(self._aktiv)
        self.hg_eigen.toggled.connect(self._aktiv)
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
        self.draht_kontrast.setChecked(ein.value("draht_kontrast", True, type=bool))
        self.pmi_eigen.setChecked(ein.value("pmi_eigen", False, type=bool))
        self.hg_eigen.setChecked(ein.value("hg_eigen", False, type=bool))
        self._aktiv()
        self._hilfe()

    def _aktiv(self):
        self.pmi_farbe.setEnabled(self.pmi_eigen.isChecked())
        self.kontrast.setEnabled(not self.pmi_eigen.isChecked())
        for k in (self.hg_oben, self.hg_unten):
            k.setEnabled(self.hg_eigen.isChecked())

    @staticmethod
    def _setze(combo, wert):
        i = combo.findData(wert)
        combo.setCurrentIndex(max(i, 0))

    def _hilfe(self):
        self.steuerung_hilfe.setText(tr(STEUERUNG_TEXT[self.steuerung.currentData()][1]))

    def werte(self) -> dict:
        return {"navigation": self.steuerung.currentData(), "thema": self.thema.currentData(),
                "sprache": self.sprache.currentData(), "pmi_kontrast": self.kontrast.isChecked(),
                "draht_kontrast": self.draht_kontrast.isChecked(),
                "pmi_eigen": self.pmi_eigen.isChecked(), "pmi_eigene_farbe": self.pmi_farbe.farbe,
                "hg_eigen": self.hg_eigen.isChecked(), "hg_oben": self.hg_oben.farbe, "hg_unten": self.hg_unten.farbe}


class FarbKnopf(QtWidgets.QPushButton):
    """Knopf, der eine Farbe zeigt und per Farbwahl aendert (Wert als #rrggbb)."""

    def __init__(self, farbe: str, parent=None):
        super().__init__(parent)
        self.farbe = farbe
        self.setFixedWidth(44)
        self.clicked.connect(self._waehle)
        self._zeige()

    def _zeige(self):
        self.setStyleSheet(f"background: {self.farbe}; border: 1px solid #888; border-radius: 4px;")
        self.setToolTip(self.farbe)

    def _waehle(self):
        f = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.farbe), self, tr("Farbe wählen"))
        if f.isValid():
            self.farbe = f.name()
            self._zeige()


def rgb(hexfarbe: str) -> tuple[float, float, float]:
    c = QtGui.QColor(hexfarbe)
    return (c.redF(), c.greenF(), c.blueF())
