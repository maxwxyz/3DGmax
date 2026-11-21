"""Bemasste Welle in der Laengsansicht eines PDF erfassen."""

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.axialbohrung import stirnringe
from ..kern.drehzeichnung import axiales_bohrmass, drehprofil, drehmasse, schreibe_drehteil
from ..kern.zeichnungsansicht import Blattgeometrie
from ..kern.zeichnungsabgleich import Blattangabe
from .zeichnungsabgleich_ui import Blattansicht
from .zeichnungsdialog import Koerperdialog


class Drehteildialog(Koerperdialog):
    def __init__(self, doc, pfad, parent=None):
        super().__init__(doc, pfad, tr("Welle aus 2D-Zeichnung"), parent)
        self.kontur, self.sitze, self.massmarken = [], [], {}
        self.spur = self.stirn = None
        self.geometrie = None
        self.resize(980,700)
        layout = QtWidgets.QVBoxLayout(self)
        leiste = QtWidgets.QHBoxLayout()
        layout.addLayout(leiste)
        self.seite = QtWidgets.QSpinBox()
        self.seite.setRange(1,len(doc))
        leiste.addWidget(QtWidgets.QLabel(tr("Blatt")))
        leiste.addWidget(self.seite)
        self.auswahl = QtWidgets.QComboBox()
        self.auswahl.addItems([tr("Längsansicht waagerecht"), tr("Längsansicht senkrecht"),
                               tr("Abschnittslänge"), tr("Abschnittsdurchmesser"),
                               tr("Stirnansicht der Hohlwelle"), tr("Durchmesser der Axialbohrung")])
        leiste.addWidget(QtWidgets.QLabel(tr("Einrahmen")))
        leiste.addWidget(self.auswahl)
        self.einheit = QtWidgets.QComboBox()
        for name, faktor in ((tr("Zeichnungseinheit wählen"),None),(tr("mm"),1.),(tr("Zoll"),25.4)):
            self.einheit.addItem(name,faktor)
        leiste.addWidget(self.einheit)
        leiste.addStretch()
        fit = QtWidgets.QPushButton(tr("Blatt einpassen"))
        leiste.addWidget(fit)
        self.ansicht = Blattansicht()
        fit.clicked.connect(self.ansicht.einpassen)
        layout.addWidget(self.ansicht,1)
        hinweis = QtWidgets.QLabel(tr("Die Längsansicht mit zylindrischen Abschnitten und rechtwinkligen Schultern einrahmen. "
                                      "Je Abschnitt Länge und Ø-Maß eingeben oder einrahmen. Für eine Axialbohrung ohne "
                                      "durchgehende Wandlinien zusätzlich die Stirnansicht und ein Durchgangsmaß angeben."))
        hinweis.setWordWrap(True)
        layout.addWidget(hinweis)
        self.tabelle = QtWidgets.QTableWidget(0,2)
        self.tabelle.setHorizontalHeaderLabels([tr("Abschnittslänge"), tr("Abschnittsdurchmesser")])
        self.tabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tabelle.setMaximumHeight(170)
        layout.addWidget(self.tabelle)
        bohrzeile = QtWidgets.QHBoxLayout()
        layout.addLayout(bohrzeile)
        bohrzeile.addWidget(QtWidgets.QLabel(tr("Durchgehende Axialbohrung")))
        self.bohrtext = QtWidgets.QLineEdit()
        self.bohrtext.setPlaceholderText(tr("Ø-Maß laut Zeichnung"))
        bohrzeile.addWidget(self.bohrtext)
        self.stirn_entfernen = QtWidgets.QPushButton(tr("Stirnansicht entfernen"))
        self.stirn_entfernen.clicked.connect(self._ohne_stirnansicht)
        bohrzeile.addWidget(self.stirn_entfernen)
        self.bohrtext.textChanged.connect(self._pruefen)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        knoepfe.button(knoepfe.StandardButton.Close).setText(tr("Schließen"))
        self.speichern = knoepfe.addButton(tr("STEP mit Bemaßung speichern …"), knoepfe.ButtonRole.ActionRole)
        layout.addWidget(knoepfe)
        knoepfe.rejected.connect(self.reject)
        self.speichern.clicked.connect(self._export)
        self.seite.valueChanged.connect(self._seite)
        self.tabelle.cellChanged.connect(self._pruefen)
        self.tabelle.currentCellChanged.connect(self._markieren)
        self.ansicht.bereich.connect(self._bereich)
        self.ansicht.gewaehlt.connect(self._sitz_waehlen)
        self.einheit.currentIndexChanged.connect(self._pruefen)
        self._seite()

    def _seite(self):
        self.geometrie = None
        super()._seite()

    def _ohne_stirnansicht(self):
        self.stirn = None
        self.massmarken.pop("stirn",None)
        self._markieren()
        self._pruefen()

    def _sitz_waehlen(self, marke):
        if marke in self.sitze:
            self.tabelle.setCurrentCell(self.sitze.index(marke), max(0,self.tabelle.currentColumn()))

    def _markieren(self):
        aktiv = self.tabelle.currentRow()
        marke = self.sitze[aktiv] if 0 <= aktiv < len(self.sitze) else None
        sichtbar = [m for m in (*self.sitze,*self.massmarken.values()) if m.seite == self.blatt.nummer]
        self.ansicht.markiere(sichtbar,marke,auswaehlbar=self.sitze)

    def _bereich(self, box):
        i = self.auswahl.currentIndex()
        if i < 2:
            self.kontur, self.spur = drehprofil(self.blatt.bild,box,senkrecht=bool(i))
            self.stirn = None
            with QtCore.QSignalBlocker(self.bohrtext):
                self.bohrtext.clear()
            self.sitze = [Blattangabe(self.blatt.nummer,s.box,str(n)) for n,s in enumerate(self.kontur,1)]
            self.massmarken.clear()
            with QtCore.QSignalBlocker(self.tabelle):
                self.tabelle.setRowCount(0)
                self.tabelle.setRowCount(len(self.kontur))
                for zeile in range(len(self.kontur)):
                    for spalte in range(2):
                        self.tabelle.setItem(zeile,spalte,QtWidgets.QTableWidgetItem())
                if self.kontur:
                    self.tabelle.setCurrentCell(0,0)
        elif i == 4:
            if self.geometrie is None:
                self.geometrie = Blattgeometrie(self.blatt)
            self.stirn = stirnringe(self.blatt.bild,box,self.geometrie.im_bereich(box))
            self.massmarken.pop("stirn",None)
            if self.stirn:
                self.massmarken["stirn"] = Blattangabe(self.blatt.nummer,box,self.auswahl.currentText())
        elif i == 5:
            wert = self.blatt.lies(box)
            self.bohrtext.setText(wert)
            self.massmarken.pop("bohrung",None)
            if wert:
                self.massmarken["bohrung"] = Blattangabe(self.blatt.nummer,box,wert)
        else:
            zeile, spalte = self.tabelle.currentRow(), i-2
            if zeile < 0:
                return
            wert = self.blatt.lies(box)
            self.tabelle.item(zeile,spalte).setText(wert)
            self.massmarken.pop((zeile,spalte),None)
            if wert:
                self.massmarken[zeile,spalte] = Blattangabe(self.blatt.nummer,box,wert)
        self._markieren()
        self._pruefen()

    def _masse(self):
        zeilen = [(self.tabelle.item(i,0).text(), self.tabelle.item(i,1).text()) for i in range(len(self.kontur))]
        faktor = self.einheit.currentData()
        masse = drehmasse(self.kontur, zeilen, faktor)
        bohrung = axiales_bohrmass(self.kontur, masse, self.spur, self.stirn, self.bohrtext.text(), faktor)
        return masse, bohrung

    def _pruefen(self):
        self.bohrtext.setEnabled(bool(self.kontur))
        self.stirn_entfernen.setEnabled(self.stirn is not None)
        for i in (2,3,4,5):
            self.auswahl.model().item(i).setEnabled(bool(self.kontur))
        try:
            masse, bohrung = self._masse()
        except ValueError as e:
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
            return
        status = tr("Hohlwelle mit {} Abschnitten, Gesamtlänge {} mm.") if bohrung else tr("Vollwelle mit {} Abschnitten, Gesamtlänge {} mm.")
        self.status.setText(status.format(len(masse), f"{sum(p.nennwert for p,_ in masse):g}"))
        self.speichern.setEnabled(True)

    def _schreibe(self, ziel):
        return schreibe_drehteil(ziel, *self._masse())
