"""Bemasste rechteckige Platte aus einer PDF-Zeichnung als STEP speichern."""

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.zeichnungsabgleich import Blattangabe, lese_angabe
from ..kern.zeichnungsblatt import Zeichnungsblatt
from ..kern.zeichnungsansicht import Blattgeometrie
from ..kern.plattenbohrung import plattenumriss, sollbohrungen, tiefenmass
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
        self.ringe = []
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
        for name, wert in ((tr("Zeichnungseinheit wählen"), None), (tr("mm"), 1.), (tr("Zoll"), 25.4)):
            self.einheit.addItem(name, wert)
        werkzeug.addWidget(self.einheit)
        werkzeug.addStretch()
        fit = QtWidgets.QPushButton(tr("Blatt einpassen"))
        werkzeug.addWidget(fit)
        self.ansicht = Blattansicht()
        fit.clicked.connect(self.ansicht.einpassen)
        layout.addWidget(self.ansicht, 1)
        self.hinweis = QtWidgets.QLabel(tr("Die Außenkontur der rechteckigen Platte mit etwas Rand einrahmen. Bohrungen dürfen als einzelne Kreise sichtbar sein. "
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
        self.bohrfeld = QtWidgets.QGroupBox(tr("Bohrungen im Grundriss"))
        inhalt = QtWidgets.QVBoxLayout(self.bohrfeld)
        hinweis = QtWidgets.QLabel(tr("X und Y ab der linken unteren Ecke sowie den Durchmesser aus der Zeichnung eingeben. "
                                     "Die erste Spalte zeigt Schätzwerte. Für ein Maß aus dem PDF die Bohrung und das Maß unter „Einrahmen“ wählen."))
        hinweis.setWordWrap(True)
        inhalt.addWidget(hinweis)
        self.bohrtabelle = QtWidgets.QTableWidget(0, 6)
        self.bohrtabelle.setHorizontalHeaderLabels([tr("Geschätzt (X / Y / ⌀, mm)"), tr("X (mm)"), tr("Y (mm)"), tr("Durchmesser (mm)"),
                                                 tr("Bohrungsende"), tr("Tiefe (mm)")])
        self.bohrtabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.bohrtabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.bohrtabelle.setMaximumHeight(140)
        inhalt.addWidget(self.bohrtabelle)
        self.durchgehend = QtWidgets.QCheckBox(tr("Alle aufgeführten Bohrungen sind Durchgangsbohrungen"))
        inhalt.addWidget(self.durchgehend)
        layout.addWidget(self.bohrfeld)
        self.bohrfeld.hide()
        self.bohrtabelle.cellChanged.connect(self._pruefen)
        self.bohrtabelle.currentCellChanged.connect(self._markieren)
        self.durchgehend.toggled.connect(self._alle_durch)
        self.ansicht.kreis_gewaehlt.connect(self._bohrung_waehlen)
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
        self.geometrie = None
        self.ansicht.zeige(self.blatt.bild)
        self._markieren()
        self._pruefen()

    def _markieren(self):
        sichtbar = [a for a in self.marken.values() if a.seite == self.blatt.nummer]
        self.ansicht.markiere(sichtbar, self.marken.get(self._markenschluessel()))
        grundriss = self.marken.get(0)
        kreise = [q.kreis for q in self.ringe] if grundriss and grundriss.seite == self.blatt.nummer else []
        i = self.bohrtabelle.currentRow()
        self.ansicht.zeige_kreise(kreise, kreise[i] if 0 <= i < len(kreise) else None)

    def _markenschluessel(self):
        feld = self.auswahl.currentIndex()
        return feld if feld < 5 else (self.bohrtabelle.currentRow(), feld)

    def _bohrung_waehlen(self, kreis):
        for i, ring in enumerate(self.ringe):
            if ring.kreis == kreis:
                self.bohrtabelle.setCurrentCell(i, 1)
                break

    def _grundriss(self, box):
        umfang = rechteckansicht(self.blatt.bild, box)
        self.ringe = []
        if not umfang:
            if self.geometrie is None:
                self.geometrie = Blattgeometrie(self.blatt)
            ergebnis = plattenumriss(self.blatt.bild, box, self.geometrie.im_bereich(box))
            if ergebnis is not None:
                umfang, self.ringe = ergebnis
        with QtCore.QSignalBlocker(self.bohrtabelle), QtCore.QSignalBlocker(self.durchgehend):
            self.durchgehend.setChecked(False)
            self.bohrtabelle.setRowCount(0)
            self.bohrtabelle.setRowCount(len(self.ringe))
            for i in range(len(self.ringe)):
                for j in (0, 1, 2, 3, 5):
                    item = QtWidgets.QTableWidgetItem()
                    if j == 5:
                        item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                    if j == 0:
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.bohrtabelle.setItem(i, j, item)
                art = QtWidgets.QComboBox()
                art.addItems([tr("Offen"), tr("Durchgang"), tr("Flachboden von oben")])
                self.bohrtabelle.setCellWidget(i, 4, art)
                art.currentIndexChanged.connect(lambda _, zeile=i: self._bohrart(zeile))
            self.durchgehend.setEnabled(True)
            if self.ringe:
                self.bohrtabelle.setCurrentCell(0, 1)
        self.marken = {k: v for k, v in self.marken.items() if isinstance(k, int)}
        with QtCore.QSignalBlocker(self.auswahl):
            while self.auswahl.count() > 5:
                self.auswahl.removeItem(5)
            if self.ringe:
                self.auswahl.addItems([tr("X-Maß der gewählten Bohrung"), tr("Y-Maß der gewählten Bohrung"),
                                       tr("Durchmesser der gewählten Bohrung"), tr("Tiefe der gewählten Bohrung")])
        self.bohrfeld.setVisible(bool(self.ringe))
        return umfang

    def _alle_durch(self, aktiv):
        for i in range(len(self.ringe)):
            art = self.bohrtabelle.cellWidget(i, 4)
            with QtCore.QSignalBlocker(art):
                art.setCurrentIndex(1 if aktiv else 0)
        self._pruefen()

    def _bohrart(self, zeile):
        arten = [self.bohrtabelle.cellWidget(i, 4).currentIndex() for i in range(len(self.ringe))]
        with QtCore.QSignalBlocker(self.durchgehend):
            self.durchgehend.setChecked(all(a == 1 for a in arten))
            self.durchgehend.setEnabled(2 not in arten)
        item = self.bohrtabelle.item(zeile, 5)
        with QtCore.QSignalBlocker(self.bohrtabelle):
            if arten[zeile] == 2:
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setText("")
                item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                self.marken.pop((zeile, 8), None)
        self._markieren()
        self._pruefen()

    def _bereich(self, box):
        i = self.auswahl.currentIndex()
        schluessel = self._markenschluessel()
        self.marken.pop(schluessel, None)
        if i < 2:
            wert = self._grundriss(box) if i == 0 else rechteckansicht(self.blatt.bild, box)
            self.konturen[i] = wert
            if i == 1:
                self.vorne_offen = wert is None
        elif i < 5:
            wert = self.blatt.lies(box)
            self.texte[i-2].setText(wert)
        else:
            zeile = self.bohrtabelle.currentRow()
            if zeile < 0:
                return
            if i == 8 and self.bohrtabelle.cellWidget(zeile, 4).currentIndex() != 2:
                self.status.setText(tr("Für ein Tiefenmaß zuerst eine Bohrung mit flachem Grund wählen."))
                return
            wert = self.blatt.lies(box)
            lesen = tiefenmass if i == 8 else lese_angabe
            faktor = self.einheit.currentData()
            if lesen(wert, faktor) is None:
                wert = ""
            elif faktor == 25.4 and lesen(wert, None) is None:
                # Die Bohrungstabelle verwendet mm, eine gedruckte Zollangabe eindeutig erhalten.
                wert += " in"
            self.bohrtabelle.item(zeile, 5 if i == 8 else i-4).setText(wert)
        if wert:
            self.marken[schluessel] = Blattangabe(self.blatt.nummer, box, self.auswahl.currentText())
        self._markieren()
        self._pruefen()
        if not wert:
            self.status.setText(tr("Die Auswahl muss eine geschlossene Rechteckkontur enthalten. Im Grundriss sind einzelne Bohrkreise zulässig.") if i < 2
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

    def _bohrungen(self, masse):
        if not self.ringe:
            return []
        tiefen = []
        for i in range(len(self.ringe)):
            art = self.bohrtabelle.cellWidget(i, 4).currentIndex()
            if art == 0:
                raise ValueError(tr("Für Bohrung {} das Bohrungsende anhand der Zeichnung wählen.").format(i+1))
            tiefen.append(self.bohrtabelle.item(i, 5).text() if art == 2 else None)
        werte = [[self.bohrtabelle.item(i, j).text() for j in (1, 2, 3)] for i in range(len(self.ringe))]
        return sollbohrungen(self.ringe, werte, masse, self.konturen[0], tiefen=tiefen)

    def _pruefen(self):
        self.vorne_entfernen.setEnabled(self.vorne_offen or self.konturen[1] is not None)
        try:
            masse = self._masse()
        except ValueError as e:
            with QtCore.QSignalBlocker(self.bohrtabelle):
                for i in range(len(self.ringe)):
                    self.bohrtabelle.item(i, 0).setText("")
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
            return
        with QtCore.QSignalBlocker(self.bohrtabelle):
            for i, q in enumerate(self.ringe):
                x, y = masse[0].nennwert, masse[1].nennwert
                self.bohrtabelle.item(i, 0).setText(f"{q.x*x:.2f} / {q.y*y:.2f} / ⌀{2*q.r*x:.2f}")
        try:
            self._bohrungen(masse)
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
            masse = self._masse()
            bohrungen = self._bohrungen(masse)
            anzahl = schreibe_platte(ziel, masse, bohrungen)
        except (OSError, ValueError, RuntimeError) as e:
            QtWidgets.QMessageBox.warning(self, tr("Platte aus 2D-Zeichnung"), str(e))
            return
        self.status.setText(tr("STEP-Modell mit {} bemaßten Merkmalen unter {} gespeichert.").format(anzahl, ziel))


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
