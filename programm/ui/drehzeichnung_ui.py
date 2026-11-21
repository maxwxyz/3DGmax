"""Bemasste Welle in der Laengsansicht eines PDF erfassen."""

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.axialbohrung import Gegenbohrungen, Sacklochspur, Stufenbohrspur, stirnringe
from ..kern.drehzeichnung import Bohrspitze, axiale_tiefe, axiales_bohrmass, drehprofil, drehmasse, schreibe_drehteil, stufenmasse, gegenbohrmasse
from ..kern.drehkegel import Kegelkontur, kegelkontur, kegelmasse, schreibe_kegel
from ..kern.plattenbohrung import kegelwinkelmass
from ..kern.zeichnungsansicht import Blattgeometrie
from ..kern.zeichnungsabgleich import Blattangabe
from .zeichnungsabgleich_ui import Blattansicht
from .zeichnungsdialog import Koerperdialog


def _tiefenbezug():
    feld = QtWidgets.QComboBox()
    feld.addItem(tr("Tiefenbezug wählen"),None)
    feld.addItem(tr("Tiefe bis zum Zylinderende"),False)
    feld.addItem(tr("Tiefe bis zur Bohrspitze"),True)
    return feld


def _bohrspitze(text, bezug):
    winkel = kegelwinkelmass(text)
    if not winkel or bezug is None:
        raise ValueError(tr("Für die gezeichnete Bohrspitze Spitzenwinkel und Tiefenbezug angeben."))
    return Bohrspitze(winkel,bezug)


class Drehteildialog(Koerperdialog):
    def __init__(self, doc, pfad, parent=None):
        super().__init__(doc, pfad, tr("Welle aus 2D-Zeichnung"), parent)
        self.kontur, self.sitze, self.massmarken = [], [], {}
        self.spur = self.stirn = self.stirn2 = None
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
                               tr("Tiefe der Axialbohrung"), tr("Spitzenwinkel der gewählten Bohrung"),
                               tr("Zweite Stirnansicht"),tr("Zweiter Stirndurchmesser"),tr("Eingeschlossener Kegelwinkel")])
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
        hinweis = QtWidgets.QLabel(tr("Die Längsansicht einer gestuften Welle oder eines Kegelstumpfs einrahmen. "
                                      "Je Abschnitt Länge und Ø-Maß eingeben oder einrahmen. Bei einer Bohrspitze den Tiefenbezug "
                                      "und den eingeschlossenen Winkel aus der Zeichnung übernehmen. Jede Bohrtiefe ab der zugehörigen Eintrittsfläche angeben. Für einen Durchgang ohne Wandlinien die Stirnansicht und das Durchgangsmaß angeben."))
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
        self.tiefenbezug = _tiefenbezug()
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
        if self.stirn2 is not None and (self.auswahl.currentIndex() == 8 or self.stirn is None):
            self.stirn2 = None
            self.massmarken.pop("stirn2",None)
        else:
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
        stufen = self.spur.stufen if isinstance(self.spur,(Stufenbohrspur,Gegenbohrungen)) else ()
        with QtCore.QSignalBlocker(self.bohrstufen):
            self.bohrstufen.setRowCount(0)
            kopf = [tr("Stufendurchmesser"),tr("Tiefe ab Eintrittsfläche")]
            spitzzeilen = set()
            if isinstance(self.spur,Gegenbohrungen) and any(self.spur.spitzen):
                kopf.extend((tr("Spitzenwinkel (°)"),tr("Tiefenbezug")))
                enden = (len(self.spur.links)-1, len(self.spur.links)+len(self.spur.rechts)-1)
                spitzzeilen = {z for z,h in zip(enden,self.spur.spitzen,strict=True) if h}
            self.bohrstufen.setColumnCount(len(kopf))
            self.bohrstufen.setHorizontalHeaderLabels(kopf)
            self.bohrstufen.setRowCount(len(stufen))
            for i,(_,tiefe) in enumerate(stufen):
                if isinstance(self.spur,Gegenbohrungen):
                    if i < len(self.spur.links):
                        name = tr("Oben") if self.senkrecht else tr("Links")
                    elif i < len(self.spur.links)+len(self.spur.rechts):
                        name = tr("Unten") if self.senkrecht else tr("Rechts")
                    else:
                        name = tr("Gemeinsamer Kern")
                    self.bohrstufen.setVerticalHeaderItem(i,QtWidgets.QTableWidgetItem(name))
                self.bohrstufen.setItem(i,0,QtWidgets.QTableWidgetItem())
                item = QtWidgets.QTableWidgetItem()
                if tiefe is None:
                    item.setText(tr("Durchgang"))
                    item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                self.bohrstufen.setItem(i,1,item)
                if i in spitzzeilen:
                    self.bohrstufen.setItem(i,2,QtWidgets.QTableWidgetItem())
                    bezug = _tiefenbezug()
                    self.bohrstufen.setCellWidget(i,3,bezug)
                    bezug.currentIndexChanged.connect(self._pruefen)
                elif spitzzeilen:
                    for j in (2,3):
                        leer = QtWidgets.QTableWidgetItem()
                        leer.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                        self.bohrstufen.setItem(i,j,leer)
            if stufen:
                self.bohrstufen.setCurrentCell(0,0)

    def _bereich(self, box):
        i = self.auswahl.currentIndex()
        if i < 2:
            self.senkrecht = bool(i)
            self.kontur, self.spur = drehprofil(self.blatt.bild,box,senkrecht=self.senkrecht)
            if not self.kontur:
                kegel = kegelkontur(self.blatt.bild,box,self.senkrecht)
                if kegel:
                    self.kontur = [kegel]
            self.stirn = self.stirn2 = None
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
                kopf = [tr("Abschnittslänge"),tr("Abschnittsdurchmesser")]
                if self._kegel():
                    kopf = [tr("Abschnittslänge"),tr("Ø oben") if self.senkrecht else tr("Ø links"),
                            tr("Ø unten") if self.senkrecht else tr("Ø rechts"),tr("Kegelwinkel (optional)")]
                self.tabelle.setColumnCount(len(kopf))
                self.tabelle.setHorizontalHeaderLabels(kopf)
                self.tabelle.setRowCount(len(self.kontur))
                for zeile in range(len(self.kontur)):
                    for spalte in range(len(kopf)):
                        self.tabelle.setItem(zeile,spalte,QtWidgets.QTableWidgetItem())
                if self.kontur:
                    self.tabelle.setCurrentCell(0,0)
        elif i in (4,8):
            if self.geometrie is None:
                self.geometrie = Blattgeometrie(self.blatt)
            ringe = stirnringe(self.blatt.bild,box,self.geometrie.im_bereich(box))
            if i == 4:
                self.stirn = ringe
                marke = "stirn"
            else:
                self.stirn2 = ringe
                marke = "stirn2"
            self.massmarken.pop(marke,None)
            if ringe:
                self.massmarken[marke] = Blattangabe(self.blatt.nummer,box,self.auswahl.currentText())
        elif i == 7:
            wert = self.blatt.lies(box)
            marke = "winkel"
            if isinstance(self.spur,Gegenbohrungen):
                zeile = self.bohrstufen.currentRow()
                if self.bohrstufen.cellWidget(zeile,3) is None:
                    return
                self.bohrstufen.item(zeile,2).setText(wert)
                marke = ("winkel",zeile)
            else:
                self.winkeltext.setText(wert)
            self.massmarken.pop(marke,None)
            if wert:
                self.massmarken[marke] = Blattangabe(self.blatt.nummer,box,wert)
        elif i in (5,6):
            wert = self.blatt.lies(box)
            if isinstance(self.spur,(Stufenbohrspur,Gegenbohrungen)):
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
            zeile, spalte = self.tabelle.currentRow(), i-7 if i in (9,10) else i-2
            if zeile < 0:
                return
            wert = self.blatt.lies(box)
            self.tabelle.item(zeile,spalte).setText(wert)
            self.massmarken.pop((zeile,spalte),None)
            if wert:
                self.massmarken[zeile,spalte] = Blattangabe(self.blatt.nummer,box,wert)
        self._markieren()
        self._pruefen()

    def _kegel(self):
        return bool(self.kontur) and isinstance(self.kontur[0],Kegelkontur)

    def _masse(self):
        zeilen = [(self.tabelle.item(i,0).text(), self.tabelle.item(i,1).text()) for i in range(len(self.kontur))]
        faktor = self.einheit.currentData()
        masse = drehmasse(self.kontur, zeilen, faktor)
        if self._kegel():
            ende,winkel = kegelmasse(self.kontur[0],masse,self.tabelle.item(0,2).text(),self.tabelle.item(0,3).text(),faktor)
            return masse,dict(ende=ende,winkel=winkel)
        if isinstance(self.spur,(Stufenbohrspur,Gegenbohrungen)):
            texte = [(self.bohrstufen.item(i,0).text(), self.bohrstufen.item(i,1).text() if t is not None else "")
                     for i,(_,t) in enumerate(self.spur.stufen)]
            if isinstance(self.spur,Gegenbohrungen):
                spitzen = []
                for zeile in (len(self.spur.links)-1, len(self.spur.links)+len(self.spur.rechts)-1):
                    bezug = self.bohrstufen.cellWidget(zeile,3)
                    spitzen.append(_bohrspitze(self.bohrstufen.item(zeile,2).text(),bezug.currentData()) if bezug else None)
                gegen = gegenbohrmasse(self.kontur,masse,self.spur,(self.stirn,self.stirn2),texte,faktor,tuple(spitzen))
                return masse,dict(gegen=gegen)
            spitze = None
            if self.spur.spitzenhoehe:
                spitze = _bohrspitze(self.winkeltext.text(),self.tiefenbezug.currentData())
            profil = stufenmasse(self.kontur,masse,self.spur,self.stirn,texte,faktor,spitze)
            dm,tiefe = profil[-1]
            return masse,dict(bohrung=dm,tiefe=tiefe,rechts=self.spur.von_rechts,stufen=profil[:-1],spitze=spitze)
        tiefe = axiale_tiefe(self.spur, self.tiefentext.text(), faktor)
        bohrung = axiales_bohrmass(self.kontur, masse, self.spur, self.stirn, self.bohrtext.text(), faktor, tiefe)
        return masse,dict(bohrung=bohrung,tiefe=tiefe,rechts=isinstance(self.spur,Sacklochspur) and self.spur.von_rechts)

    def _pruefen(self):
        blind = isinstance(self.spur, Sacklochspur)
        gegen = isinstance(self.spur,Gegenbohrungen)
        gestuft = isinstance(self.spur,(Stufenbohrspur,Gegenbohrungen))
        spitz = isinstance(self.spur,Stufenbohrspur) and bool(self.spur.spitzenhoehe)
        self.auswahl.model().item(8).setEnabled(gegen)
        if gegen:
            self.auswahl.setItemText(4,tr("Stirnansicht von oben") if self.senkrecht else tr("Stirnansicht von links"))
            self.auswahl.setItemText(8,tr("Stirnansicht von unten") if self.senkrecht else tr("Stirnansicht von rechts"))
        else:
            self.auswahl.setItemText(4,tr("Stirnansicht der Hohlwelle"))
            self.auswahl.setItemText(8,tr("Zweite Stirnansicht"))
        self.spitzenzeile.setVisible(spitz)
        mit_winkel = spitz or (gegen and self.bohrstufen.cellWidget(self.bohrstufen.currentRow(),3) is not None)
        self.auswahl.model().item(7).setEnabled(mit_winkel)
        if not mit_winkel and self.auswahl.currentIndex() == 7:
            self.auswahl.setCurrentIndex(5)
        self.bohrstufen.setVisible(gestuft)
        kegel = self._kegel()
        self.bohrart.setVisible(not kegel)
        self.bohrtext.setVisible(not gestuft and not kegel)
        self.stirn_entfernen.setVisible(not kegel)
        self.auswahl.model().item(9).setEnabled(kegel)
        self.auswahl.model().item(10).setEnabled(kegel)
        self.auswahl.setItemText(3,tr("Erster Stirndurchmesser") if kegel else tr("Abschnittsdurchmesser"))
        self.tiefentext.setVisible(blind)
        zeile = self.bohrstufen.currentRow()
        mit_tiefe = blind or (gestuft and zeile >= 0 and self.spur.stufen[zeile][1] is not None)
        self.auswahl.model().item(6).setEnabled(mit_tiefe)
        if not mit_tiefe and self.auswahl.currentIndex() == 6:
            self.auswahl.setCurrentIndex(5)
        if gegen:
            self.bohrart.setText(tr("Axialbohrungen von beiden Stirnseiten"))
        elif gestuft and len(self.spur.stufen) > 1:
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
        self.stirn_entfernen.setEnabled(self.stirn is not None or self.stirn2 is not None)
        for i in (2,3,4,5):
            self.auswahl.model().item(i).setEnabled(bool(self.kontur) and (i < 4 or not kegel))
        try:
            masse, daten = self._masse()
        except ValueError as e:
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
            return
        status = tr("Hohlwelle mit {} Abschnitten, Gesamtlänge {} mm.") if daten.get("bohrung") else tr("Vollwelle mit {} Abschnitten, Gesamtlänge {} mm.")
        if kegel:
            self.status.setText(tr("Kegelstumpf mit einer Länge von {} mm.").format(f"{masse[0][0].nennwert:g}"))
            self.speichern.setEnabled(True)
            return
        if gegen:
            status = (tr("Welle mit gemeinsamer Kernbohrung und {} Außenabschnitten, Gesamtlänge {} mm.")
                      if self.spur.kern is not None else tr("Welle mit getrennten Sacklöchern und {} Außenabschnitten, Gesamtlänge {} mm."))
        elif gestuft and len(self.spur.stufen) > 1:
            status = tr("Welle mit Stufenbohrung und {} Außenabschnitten, Gesamtlänge {} mm.")
        elif daten.get("tiefe"):
            status = tr("Welle mit Sackloch und {} Abschnitten, Gesamtlänge {} mm.")
        self.status.setText(status.format(len(masse), f"{sum(p.nennwert for p,_ in masse):g}"))
        self.speichern.setEnabled(True)

    def _schreibe(self, ziel):
        masse, daten = self._masse()
        if self._kegel():
            return schreibe_kegel(ziel,masse,**daten)
        return schreibe_drehteil(ziel,masse,**daten)
