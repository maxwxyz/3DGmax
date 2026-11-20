"""Bemasste rechteckige Platte aus einer PDF-Zeichnung als STEP speichern."""

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.zeichnungsabgleich import Blattangabe
from ..kern.zeichnungsblatt import Zeichnungsblatt
from ..kern.zeichnungskoerper import plattenmasse, rechteckansicht, schreibe_platte
from .zeichnungsabgleich_ui import Blattansicht


class Plattendialog(QtWidgets.QDialog):
    def __init__(self, doc, pfad, parent=None):
        super().__init__(parent)
        self.doc, self.pfad = doc, Path(pfad)
        self.blatt = None
        self.konturen = [None, None]
        self.marken = {}
        self.vorne_offen = False
        self.setWindowTitle(tr("Platte aus 2D-Zeichnung") + " – " + self.pfad.name)
        self.resize(1000, 700)
        layout = QtWidgets.QVBoxLayout(self)
        werkzeug = QtWidgets.QHBoxLayout()
        layout.addLayout(werkzeug)
        self.seite = QtWidgets.QSpinBox()
        self.seite.setRange(1, len(doc))
        werkzeug.addWidget(QtWidgets.QLabel(tr("Blatt")))
        werkzeug.addWidget(self.seite)
        self.auswahl = QtWidgets.QComboBox()
        self.auswahl.addItems([tr("Grundriss (Breite × Höhe)"), tr("Vorderansicht (Breite × Dicke)"),
                               tr("Breitenmaß"), tr("Höhenmaß"), tr("Dickenmaß")])
        werkzeug.addWidget(QtWidgets.QLabel(tr("Einrahmen")))
        werkzeug.addWidget(self.auswahl)
        self.vorne_entfernen = QtWidgets.QPushButton(tr("Vorderansicht entfernen"))
        self.vorne_entfernen.clicked.connect(self._ohne_vorderansicht)
        werkzeug.addWidget(self.vorne_entfernen)
        self.einheit = QtWidgets.QComboBox()
        for name, wert in ((tr("Zeichnungseinheit wählen"), None), ("mm", 1.), (tr("Zoll"), 25.4)):
            self.einheit.addItem(name, wert)
        werkzeug.addWidget(self.einheit)
        werkzeug.addStretch()
        fit = QtWidgets.QPushButton(tr("Blatt einpassen"))
        werkzeug.addWidget(fit)
        self.ansicht = Blattansicht()
        fit.clicked.connect(self.ansicht.einpassen)
        layout.addWidget(self.ansicht, 1)
        self.hinweis = QtWidgets.QLabel(tr("Die Außenkontur einer rechteckigen Platte ohne Innenkonturen mit etwas Rand einrahmen. "
                                            "Maßzahlen einzeln einrahmen oder eingeben. Eine Vorderansicht ist optional."))
        self.hinweis.setWordWrap(True)
        layout.addWidget(self.hinweis)
        zeile = QtWidgets.QHBoxLayout()
        layout.addLayout(zeile)
        self.texte = []
        for name in (tr("Breite"), tr("Höhe"), tr("Dicke")):
            feld = QtWidgets.QLineEdit()
            zeile.addWidget(QtWidgets.QLabel(name))
            zeile.addWidget(feld)
            self.texte.append(feld)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        knoepfe.button(QtWidgets.QDialogButtonBox.StandardButton.Close).setText(tr("Schließen"))
        self.speichern = knoepfe.addButton(tr("STEP mit Bemaßung speichern …"), knoepfe.ButtonRole.ActionRole)
        layout.addWidget(knoepfe)
        knoepfe.rejected.connect(self.reject)
        self.speichern.clicked.connect(self._export)
        self.ansicht.bereich.connect(self._bereich)
        self.seite.valueChanged.connect(self._seite)
        self.auswahl.currentIndexChanged.connect(self._markieren)
        self.einheit.currentIndexChanged.connect(self._pruefen)
        for feld in self.texte:
            feld.textChanged.connect(self._pruefen)
        self._seite()

    def showEvent(self, e):
        super().showEvent(e)
        self.ansicht.einpassen()

    def _seite(self):
        from pypdfium2 import PdfiumError
        try:
            neu = Zeichnungsblatt(self.doc, self.seite.value()-1)
        except (PdfiumError, ValueError) as e:
            if self.blatt is None:
                raise
            with QtCore.QSignalBlocker(self.seite):
                self.seite.setValue(self.blatt.nummer+1)
            self.status.setText(str(e))
            return
        if self.blatt is not None:
            self.blatt.schliesse()
        self.blatt = neu
        self.ansicht.zeige(self.blatt.bild)
        self._markieren()
        self._pruefen()

    def _markieren(self):
        sichtbar = [a for a in self.marken.values() if a.seite == self.blatt.nummer]
        self.ansicht.markiere(sichtbar, self.marken.get(self.auswahl.currentIndex()))

    def _bereich(self, box):
        i = self.auswahl.currentIndex()
        self.marken.pop(i, None)
        if i < 2:
            wert = rechteckansicht(self.blatt.bild, box)
            self.konturen[i] = wert
            if i == 1:
                self.vorne_offen = wert is None
        else:
            wert = self.blatt.lies(box)
            self.texte[i-2].setText(wert)
        if wert:
            self.marken[i] = Blattangabe(self.blatt.nummer, box, self.auswahl.currentText())
        self._markieren()
        self._pruefen()
        if not wert:
            self.status.setText(tr("Keine einzelne geschlossene Rechteckkontur im Ausschnitt.") if i < 2
                                else tr("Maßzahl nicht eindeutig lesbar. Den Wert aus der Zeichnung eingeben."))

    def _ohne_vorderansicht(self):
        self.konturen[1] = None
        self.vorne_offen = False
        self.marken.pop(1, None)
        self._markieren()
        self._pruefen()

    def _masse(self):
        if self.vorne_offen:
            raise ValueError(tr("Die Vorderansicht erneut einrahmen oder entfernen."))
        return plattenmasse([feld.text() for feld in self.texte], self.einheit.currentData(), *self.konturen)

    def _pruefen(self):
        self.vorne_entfernen.setEnabled(self.vorne_offen or self.konturen[1] is not None)
        try:
            masse = self._masse()
        except ValueError as e:
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
        else:
            self.status.setText(tr("Platte {} × {} × {} mm").format(*(f"{p.nennwert:g}" for p in masse)))
            self.speichern.setEnabled(True)

    def _export(self):
        ziel, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("STEP mit Bemaßung speichern …"),
                                                        str(self.pfad.with_name(self.pfad.stem + ".stp")), "STEP (*.stp *.step)")
        if not ziel:
            return
        try:
            if Path(ziel).resolve() == self.pfad.resolve():
                raise ValueError(tr("Für das STEP-Modell eine eigene Zieldatei wählen."))
            schreibe_platte(ziel, self._masse())
        except (OSError, ValueError, RuntimeError) as e:
            QtWidgets.QMessageBox.warning(self, tr("Platte aus 2D-Zeichnung"), str(e))
            return
        self.status.setText(tr("STEP-Modell mit drei bemaßten Flächenpaaren gespeichert: {}").format(ziel))


def oeffne_plattenzeichnung(fenster):
    import pypdfium2 as pdf
    pfad, _ = QtWidgets.QFileDialog.getOpenFileName(fenster, tr("2D-Zeichnung öffnen"), "", "PDF (*.pdf)")
    if not pfad:
        return
    doc = None
    try:
        doc = pdf.PdfDocument(pfad)
        if not len(doc):
            raise ValueError(tr("Die Zeichnung enthält keine Seiten."))
        dialog = Plattendialog(doc, pfad, fenster)
    except (pdf.PdfiumError, OSError, ValueError) as e:
        if doc is not None:
            doc.close()
        QtWidgets.QMessageBox.warning(fenster, tr("2D-Zeichnung öffnen"), str(e))
        return

    def schliessen():
        dialog.blatt.schliesse()
        doc.close()

    dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.finished.connect(schliessen)
    dialog.show()
    return dialog
