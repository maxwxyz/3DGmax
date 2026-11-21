"""Bemasste Welle in der Laengsansicht eines PDF erfassen."""

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.axialbohrung import Sacklochspur, Stufenbohrspur, stirnringe
from ..kern.drehzeichnung import Bohrspitze, axiale_tiefe, axiales_bohrmass, drehprofil, drehmasse, schreibe_drehteil, stufenmasse
from ..kern.plattenbohrung import kegelwinkelmass
from ..kern.zeichnungsansicht import Blattgeometrie
from ..kern.zeichnungsabgleich import Blattangabe
from .zeichnungsabgleich_ui import Blattansicht
from .zeichnungsdialog import Koerperdialog


class Drehteildialog(Koerperdialog):
    def __init__(self, doc, pfad, parent=None):
        super().__init__(doc, pfad, tr("Welle aus 2D-Zeichnung"), parent)
        self.kontur, self.sitze, self.massmarken = [], [], {}
        self.spur = self.stirn = None
        self.senkrecht = False
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
                               tr("Stirnansicht der Hohlwelle"), tr("Durchmesser der Axialbohrung"),
                               tr("Tiefe der Axialbohrung"), tr("Spitzenwinkel der gewählten Bohrung")])
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
                                      "Je Abschnitt Länge und Ø-Maß eingeben oder einrahmen. Bei einer Bohrspitze den Tiefenbezug "
                                      "und den eingeschlossenen Winkel aus der Zeichnung übernehmen. Alle Bohrtiefen ab der Eintrittsfläche angeben. Für einen Durchgang ohne Wandlinien die Stirnansicht und das Durchgangsmaß angeben."))
        hinweis.setWordWrap(True)
        layout.addWidget(hinweis)
        self.tabelle = QtWidgets.QTableWidget(0,2)
        self.tabelle.setHorizontalHeaderLabels([tr("Abschnittslänge"), tr("Abschnittsdurchmesser")])
        self.tabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tabelle.setMaximumHeight(170)
        layout.addWidget(self.tabelle)
        bohrzeile = QtWidgets.QHBoxLayout()
        layout.addLayout(bohrzeile)
        self.bohrart = QtWidgets.QLabel(tr("Axialbohrung"))
        bohrzeile.addWidget(self.bohrart)
        self.bohrtext = QtWidgets.QLineEdit()
        self.bohrtext.setPlaceholderText(tr("Ø-Maß laut Zeichnung"))
        bohrzeile.addWidget(self.bohrtext)
        self.tiefentext = QtWidgets.QLineEdit()
        self.tiefentext.setPlaceholderText(tr("Tiefe bis zum flachen Grund"))
        self.tiefentext.textChanged.connect(self._pruefen)
        bohrzeile.addWidget(self.tiefentext)
        self.stirn_entfernen = QtWidgets.QPushButton(tr("Stirnansicht entfernen"))
        self.stirn_entfernen.clicked.connect(self._ohne_stirnansicht)
        bohrzeile.addWidget(self.stirn_entfernen)
        self.bohrstufen = QtWidgets.QTableWidget(0,2)
        self.bohrstufen.setHorizontalHeaderLabels([tr("Stufendurchmesser"),tr("Tiefe ab Eintrittsfläche")])
        self.bohrstufen.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.bohrstufen.setMaximumHeight(140)
        self.bohrstufen.cellChanged.connect(self._pruefen)
        self.bohrstufen.currentCellChanged.connect(self._pruefen)
        layout.addWidget(self.bohrstufen)
        self.spitzenzeile = QtWidgets.QWidget()
        spitzenlayout = QtWidgets.QHBoxLayout(self.spitzenzeile)
        spitzenlayout.setContentsMargins(0,0,0,0)
        spitzenlayout.addWidget(QtWidgets.QLabel(tr("Spitzenwinkel (°)")))
        self.winkeltext = QtWidgets.QLineEdit()
        self.winkeltext.textChanged.connect(self._pruefen)
        spitzenlayout.addWidget(self.winkeltext)
        self.tiefenbezug = QtWidgets.QComboBox()
        self.tiefenbezug.addItem(tr("Tiefenbezug wählen"),None)
        self.tiefenbezug.addItem(tr("Tiefe bis zum Zylinderende"),False)
        self.tiefenbezug.addItem(tr("Tiefe bis zur Bohrspitze"),True)
        self.tiefenbezug.currentIndexChanged.connect(self._pruefen)
        spitzenlayout.addWidget(self.tiefenbezug)
        layout.addWidget(self.spitzenzeile)
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

    def _stufentabelle(self):
        stufen = self.spur.stufen if isinstance(self.spur,Stufenbohrspur) else ()
        with QtCore.QSignalBlocker(self.bohrstufen):
            self.bohrstufen.setRowCount(0)
            self.bohrstufen.setRowCount(len(stufen))
            for i,(_,tiefe) in enumerate(stufen):
                self.bohrstufen.setItem(i,0,QtWidgets.QTableWidgetItem())
                item = QtWidgets.QTableWidgetItem()
                if tiefe is None:
                    item.setText(tr("Durchgang"))
                    item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                self.bohrstufen.setItem(i,1,item)
            if stufen:
                self.bohrstufen.setCurrentCell(0,0)

    def _bereich(self, box):
        i = self.auswahl.currentIndex()
        if i < 2:
            self.senkrecht = bool(i)
            self.kontur, self.spur = drehprofil(self.blatt.bild,box,senkrecht=self.senkrecht)
            self.stirn = None
            self._stufentabelle()
            with QtCore.QSignalBlocker(self.winkeltext), QtCore.QSignalBlocker(self.tiefenbezug):
                self.winkeltext.clear()
                self.tiefenbezug.setCurrentIndex(0)
            with QtCore.QSignalBlocker(self.bohrtext):
                self.bohrtext.clear()
            with QtCore.QSignalBlocker(self.tiefentext):
                self.tiefentext.clear()
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
        elif i == 7:
            wert = self.blatt.lies(box)
            self.winkeltext.setText(wert)
            self.massmarken.pop("winkel",None)
            if wert:
                self.massmarken["winkel"] = Blattangabe(self.blatt.nummer,box,wert)
        elif i in (5,6):
            wert = self.blatt.lies(box)
            if isinstance(self.spur, Stufenbohrspur):
                zeile = self.bohrstufen.currentRow()
                if zeile < 0 or (i == 6 and self.spur.stufen[zeile][1] is None):
                    return
                self.bohrstufen.item(zeile,i-5).setText(wert)
                marke = ("stufe",zeile,i-5)
            else:
                feld, marke = (self.bohrtext,"bohrung") if i == 5 else (self.tiefentext,"tiefe")
                feld.setText(wert)
            self.massmarken.pop(marke,None)
            if wert:
                self.massmarken[marke] = Blattangabe(self.blatt.nummer,box,wert)
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
        if isinstance(self.spur, Stufenbohrspur):
            texte = [(self.bohrstufen.item(i,0).text(), self.bohrstufen.item(i,1).text() if t is not None else "")
                     for i,(_,t) in enumerate(self.spur.stufen)]
            spitze = None
            if self.spur.spitzenhoehe:
                winkel = kegelwinkelmass(self.winkeltext.text())
                bezug = self.tiefenbezug.currentData()
                if not winkel or bezug is None:
                    raise ValueError(tr("Für die gezeichnete Bohrspitze Spitzenwinkel und Tiefenbezug angeben."))
                spitze = Bohrspitze(winkel,bezug)
            profil = stufenmasse(self.kontur,masse,self.spur,self.stirn,texte,faktor,spitze)
            dm,tiefe = profil[-1]
            return masse,dm,tiefe,self.spur.von_rechts,profil[:-1],spitze
        tiefe = axiale_tiefe(self.spur, self.tiefentext.text(), faktor)
        bohrung = axiales_bohrmass(self.kontur, masse, self.spur, self.stirn, self.bohrtext.text(), faktor, tiefe)
        return masse, bohrung, tiefe, isinstance(self.spur,Sacklochspur) and self.spur.von_rechts,(),None

    def _pruefen(self):
        blind = isinstance(self.spur, Sacklochspur)
        gestuft = isinstance(self.spur, Stufenbohrspur)
        spitz = gestuft and bool(self.spur.spitzenhoehe)
        self.spitzenzeile.setVisible(spitz)
        self.auswahl.model().item(7).setEnabled(spitz)
        self.bohrstufen.setVisible(gestuft)
        self.bohrtext.setVisible(not gestuft)
        self.tiefentext.setVisible(blind)
        zeile = self.bohrstufen.currentRow()
        mit_tiefe = blind or (gestuft and zeile >= 0 and self.spur.stufen[zeile][1] is not None)
        self.auswahl.model().item(6).setEnabled(mit_tiefe)
        if not mit_tiefe and self.auswahl.currentIndex() == 6:
            self.auswahl.setCurrentIndex(5)
        if gestuft and len(self.spur.stufen) > 1:
            if self.senkrecht:
                seite = tr("Stufenbohrung von unten") if self.spur.von_rechts else tr("Stufenbohrung von oben")
            else:
                seite = tr("Stufenbohrung von rechts") if self.spur.von_rechts else tr("Stufenbohrung von links")
            self.bohrart.setText(seite)
        elif blind or spitz:
            if self.senkrecht:
                seite = tr("Sackloch von unten") if self.spur.von_rechts else tr("Sackloch von oben")
            else:
                seite = tr("Sackloch von rechts") if self.spur.von_rechts else tr("Sackloch von links")
            self.bohrart.setText(seite)
        else:
            self.bohrart.setText(tr("Axialbohrung"))
        self.bohrtext.setEnabled(bool(self.kontur))
        self.stirn_entfernen.setEnabled(self.stirn is not None)
        for i in (2,3,4,5):
            self.auswahl.model().item(i).setEnabled(bool(self.kontur))
        try:
            masse, bohrung, tiefe, _, _, _ = self._masse()
        except ValueError as e:
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
            return
        status = tr("Hohlwelle mit {} Abschnitten, Gesamtlänge {} mm.") if bohrung else tr("Vollwelle mit {} Abschnitten, Gesamtlänge {} mm.")
        if gestuft and len(self.spur.stufen) > 1:
            status = tr("Welle mit Stufenbohrung und {} Außenabschnitten, Gesamtlänge {} mm.")
        elif tiefe:
            status = tr("Welle mit Sackloch und {} Abschnitten, Gesamtlänge {} mm.")
        self.status.setText(status.format(len(masse), f"{sum(p.nennwert for p,_ in masse):g}"))
        self.speichern.setEnabled(True)

    def _schreibe(self, ziel):
        return schreibe_drehteil(ziel, *self._masse())
