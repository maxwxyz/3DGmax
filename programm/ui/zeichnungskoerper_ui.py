"""Bemasste rechteckige Platte aus einer PDF-Zeichnung als STEP speichern."""

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.zeichnungsabgleich import Blattangabe, lese_angabe
from ..kern.zeichnungsansicht import Blattgeometrie
from ..kern.plattenbohrung import plattenumriss, kegelwinkelmass, sollbohrungen
from ..kern.plattentasche import eckradiusmass, solltaschen
from ..kern.zeichnungskoerper import plattenmasse, rechteckansicht, schreibe_platte, tiefenmass
from .zeichnungsabgleich_ui import Blattansicht
from .zeichnungsdialog import Koerperdialog, oeffne_koerperzeichnung


OFFEN, DURCHGANG, FLACHBODEN, KEGELSENKUNG, SPITZE_ZYLINDERTIEFE, SPITZE_GESAMTTIEFE = range(6)
SPITZENFORMEN = (SPITZE_ZYLINDERTIEFE, SPITZE_GESAMTTIEFE)
MIT_TIEFENMASS = (FLACHBODEN, *SPITZENFORMEN)


class Plattendialog(Koerperdialog):
    def __init__(self, doc, pfad, parent=None):
        super().__init__(doc, pfad, tr("Platte aus 2D-Zeichnung"), parent)
        self.konturen = [None, None]
        self.marken = {}
        self.vorne_offen = False
        self.ringe = []
        self.taschen = []
        self.taschenmarken = []
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
        self.hinweis = QtWidgets.QLabel(tr("Die Außenkontur der rechteckigen Platte mit etwas Rand einrahmen. Bohrungen und rechteckige Taschen dürfen als geschlossene Innenkonturen sichtbar sein. "
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
        self.bohrtabelle = QtWidgets.QTableWidget(0, 7)
        self.bohrtabelle.setHorizontalHeaderLabels([tr("Geschätzt (X / Y / ⌀, mm)"), tr("X (mm)"), tr("Y (mm)"), tr("Durchmesser (mm)"),
                                                 tr("Bohrungsende"), tr("Tiefe (mm) / Senkwinkel (°)"), tr("Spitzenwinkel (°)")])
        self.bohrtabelle.setColumnHidden(6, True)
        self.bohrtabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.bohrtabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.bohrtabelle.setMaximumHeight(140)
        inhalt.addWidget(self.bohrtabelle)
        self.durchgehend = QtWidgets.QCheckBox(tr("Alle aufgeführten Bohrungen sind Durchgangsbohrungen"))
        inhalt.addWidget(self.durchgehend)
        self.innen = QtWidgets.QTabWidget()
        self.innen.addTab(self.bohrfeld, tr("Bohrungen"))
        taschenfeld = QtWidgets.QWidget()
        tl = QtWidgets.QVBoxLayout(taschenfeld)
        tip = QtWidgets.QLabel(tr("X und Y bezeichnen die Mitte ab der linken unteren Plattenecke. "
                                 "Breite und Höhe sind Außenmaße in X und Y. Für einen Durchbruch „Durchgang“ wählen, für eine Tasche die Tiefe von oben angeben."))
        tip.setWordWrap(True)
        tl.addWidget(tip)
        self.taschentabelle = QtWidgets.QTableWidget(0, 9)
        self.taschentabelle.setColumnHidden(7, True)
        self.taschentabelle.setColumnHidden(8, True)
        self.taschenfelder = [tr("X-Maß der gewählten Tasche"), tr("Y-Maß der gewählten Tasche"),
                              tr("Breite der gewählten Tasche"), tr("Höhe der gewählten Tasche"), tr("Tiefe der gewählten Tasche")]
        self.taschentabelle.setHorizontalHeaderLabels([tr("Geschätzt (X / Y / B / H, mm)"), tr("X (mm)"), tr("Y (mm)"),
                                                       tr("Breite (mm)"), tr("Höhe (mm)"), tr("Tiefe (mm)"), tr("Ausführung"), tr("Eckradius (mm)"), tr("Achsabstand (mm)")])
        self.taschentabelle.horizontalHeaderItem(8).setToolTip(tr("Bei Langlöchern kann der Achsabstand die Gesamtlänge ersetzen. Die kurze Seite immer angeben."))
        self.taschentabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.taschentabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.taschentabelle.setMaximumHeight(140)
        tl.addWidget(self.taschentabelle)
        self.innen.addTab(taschenfeld, tr("Taschen"))
        layout.addWidget(self.innen)
        self.innen.hide()
        self.taschentabelle.cellChanged.connect(self._pruefen)
        self.taschentabelle.currentCellChanged.connect(self._markieren)
        self.innen.currentChanged.connect(self._innentab)
        self.ansicht.gewaehlt.connect(self._tasche_waehlen)
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
        self.auswahl.currentIndexChanged.connect(self._werkzeug)
        self.einheit.currentIndexChanged.connect(self._pruefen)
        for feld in self.texte:
            feld.textChanged.connect(self._pruefen)
        self._seite()

    def _seite(self):
        self.geometrie = None
        super()._seite()

    def _markieren(self):
        sichtbar = [a for a in self.marken.values() if a.seite == self.blatt.nummer]
        taschen = [a for a in self.taschenmarken if a.seite == self.blatt.nummer]
        aktiv = self.marken.get(self._markenschluessel())
        j = self.taschentabelle.currentRow()
        if self.innen.currentIndex() == 1 and 0 <= j < len(taschen):
            aktiv = taschen[j]
        self.ansicht.markiere(sichtbar+taschen, aktiv, auswaehlbar=taschen)
        grundriss = self.marken.get(0)
        kreise = [q.kreis for q in self.ringe] if grundriss and grundriss.seite == self.blatt.nummer else []
        i = self.bohrtabelle.currentRow()
        self.ansicht.zeige_kreise(kreise, kreise[i] if self.innen.currentIndex() == 0 and 0 <= i < len(kreise) else None)

    def _markenschluessel(self):
        if (spalte := self.auswahl.currentData()) is not None:
            return ("tasche", self.taschentabelle.currentRow(), spalte)
        feld = self.auswahl.currentIndex()
        return feld if feld < 5 else (self.bohrtabelle.currentRow(), feld)

    def _innentab(self, index):
        if self.auswahl.currentIndex() >= 5:
            if index == 0 and self.auswahl.currentData() is not None:
                self.auswahl.setCurrentIndex(5)
            elif index == 1 and self.auswahl.currentData() is None:
                self.auswahl.setCurrentIndex(self.auswahl.findData(1))
        self._markieren()

    def _werkzeug(self):
        if self.auswahl.currentData() is not None:
            self.innen.setCurrentIndex(1)
        elif self.auswahl.currentIndex() >= 5:
            self.innen.setCurrentIndex(0)
        self._markieren()

    def _tasche_waehlen(self, marke):
        for i, a in enumerate(self.taschenmarken):
            if a is marke:
                self.innen.setCurrentIndex(1)
                self.taschentabelle.setCurrentCell(i, 1)
                break

    def _bohrung_waehlen(self, kreis):
        for i, ring in enumerate(self.ringe):
            if ring.kreis == kreis:
                self.innen.setCurrentIndex(0)
                self.bohrtabelle.setCurrentCell(i, 1)
                break

    def _grundriss(self, box):
        umfang = rechteckansicht(self.blatt.bild, box)
        self.ringe = []
        self.taschen = []
        if not umfang:
            if self.geometrie is None:
                self.geometrie = Blattgeometrie(self.blatt, mit_rundungen=True)
            ergebnis = plattenumriss(self.blatt.bild, box, self.geometrie.im_bereich(box), self.geometrie.rundungen)
            if ergebnis is not None:
                umfang, self.ringe, self.taschen = ergebnis
        with QtCore.QSignalBlocker(self.bohrtabelle), QtCore.QSignalBlocker(self.durchgehend):
            self.durchgehend.setChecked(False)
            self.bohrtabelle.setColumnHidden(6, True)
            self.bohrtabelle.setRowCount(0)
            self.bohrtabelle.setRowCount(len(self.ringe))
            for i, ring in enumerate(self.ringe):
                for j in (0, 1, 2, 3, 5, 6):
                    item = QtWidgets.QTableWidgetItem()
                    if j in (5,6):
                        item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                    if j == 0:
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    if ring.kern is not None and j in (1, 2):
                        item.setText(tr("wie Zeile {}").format(ring.kern+1))
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.bohrtabelle.setItem(i, j, item)
                art = QtWidgets.QComboBox()
                art.addItem(tr("Offen"), OFFEN)
                if ring.kern is None:
                    art.addItem(tr("Durchgang"), DURCHGANG)
                    art.addItem(tr("Flachboden von oben"), FLACHBODEN)
                    art.addItem(tr("Bohrspitze (Tiefe bis Zylinderende)"), SPITZE_ZYLINDERTIEFE)
                    art.addItem(tr("Bohrspitze (Gesamttiefe bis Spitze)"), SPITZE_GESAMTTIEFE)
                else:
                    art.addItem(tr("Zylindrische Stufe von oben"), FLACHBODEN)
                    if i+1 == len(self.ringe) or self.ringe[i+1].kern != ring.kern:
                        art.addItem(tr("Kegelsenkung von oben"), KEGELSENKUNG)
                self.bohrtabelle.setCellWidget(i, 4, art)
                art.currentIndexChanged.connect(lambda _, zeile=i: self._bohrart(zeile))
            self.durchgehend.setEnabled(all(r.kern is None for r in self.ringe))
            if self.ringe:
                self.bohrtabelle.setCurrentCell(0, 1)
        self.taschenmarken = [Blattangabe(self.blatt.nummer, q.box, tr("Langloch") if q.langloch else tr("Tasche")) for q in self.taschen]
        with QtCore.QSignalBlocker(self.taschentabelle):
            self.taschentabelle.setRowCount(0)
            self.taschentabelle.setRowCount(len(self.taschen))
            self.taschentabelle.setColumnHidden(7, not any(q.radius for q in self.taschen))
            self.taschentabelle.setColumnHidden(8, not any(q.langloch for q in self.taschen))
            for i, q in enumerate(self.taschen):
                for j in (0,1,2,3,4,5,7,8):
                    item = QtWidgets.QTableWidgetItem()
                    if j == 0:
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    if (j == 7 and not q.radius) or (j == 8 and not q.langloch):
                        item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                    self.taschentabelle.setItem(i, j, item)
                art = QtWidgets.QComboBox()
                art.addItems([tr("Flachboden von oben"), tr("Durchgang")])
                self.taschentabelle.setCellWidget(i, 6, art)
                art.currentIndexChanged.connect(lambda index, zeile=i: self._taschenart(zeile, index))
            if self.taschen:
                self.taschentabelle.setCurrentCell(0, 1)
        self.marken = {k: v for k, v in self.marken.items() if isinstance(k, int)}
        with QtCore.QSignalBlocker(self.auswahl):
            while self.auswahl.count() > 5:
                self.auswahl.removeItem(5)
            if self.ringe:
                self.auswahl.addItems([tr("X-Maß der gewählten Bohrung"), tr("Y-Maß der gewählten Bohrung"),
                                       tr("Durchmesser der gewählten Bohrung"), tr("Tiefe oder Senkwinkel der gewählten Bohrung"),
                                       tr("Spitzenwinkel der gewählten Bohrung")])
            if self.taschen:
                for j, text in enumerate(self.taschenfelder, 1):
                    self.auswahl.addItem(text, j)
                if any(q.langloch for q in self.taschen):
                    self.auswahl.addItem(tr("Achsabstand des gewählten Langlochs"), 8)
                if any(q.radius for q in self.taschen):
                    self.auswahl.addItem(tr("Eckradius der gewählten Tasche"), 7)
        self.innen.setTabVisible(0, bool(self.ringe))
        self.innen.setTabVisible(1, bool(self.taschen))
        self.innen.tabBar().setVisible(bool(self.ringe and self.taschen))
        self.innen.setVisible(bool(self.ringe or self.taschen))
        return umfang

    def _alle_durch(self, aktiv):
        for i in range(len(self.ringe)):
            art = self.bohrtabelle.cellWidget(i, 4)
            with QtCore.QSignalBlocker(art):
                art.setCurrentIndex(1 if aktiv else 0)
        self._pruefen()

    def _bohrart(self, zeile):
        arten = [self.bohrtabelle.cellWidget(i, 4).currentData() for i in range(len(self.ringe))]
        self.bohrtabelle.setColumnHidden(6, not any(a in SPITZENFORMEN for a in arten))
        with QtCore.QSignalBlocker(self.durchgehend):
            self.durchgehend.setChecked(all(a == DURCHGANG for a in arten))
            self.durchgehend.setEnabled(not any(a in MIT_TIEFENMASS for a in arten) and all(r.kern is None for r in self.ringe))
        self._tiefenfeld(self.bohrtabelle, zeile, arten[zeile] in SPITZENFORMEN, (zeile, 9), spalte=6)
        self._tiefenfeld(self.bohrtabelle, zeile, arten[zeile] not in (OFFEN, DURCHGANG), (zeile, 8))

        self._markieren()
        self._pruefen()

    def _taschenart(self, zeile, index):
        self._tiefenfeld(self.taschentabelle, zeile, index == 0, ("tasche", zeile, 5))
        self._markieren()
        self._pruefen()

    def _tiefenfeld(self, tabelle, zeile, aktiv, schluessel, spalte=5):
        item = tabelle.item(zeile, spalte)
        with QtCore.QSignalBlocker(tabelle):
            item.setText("")
            self.marken.pop(schluessel, None)
            if aktiv:
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)

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
            taschenspalte = self.auswahl.currentData()
            tabelle = self.taschentabelle if taschenspalte is not None else self.bohrtabelle
            zeile = tabelle.currentRow()
            if zeile < 0:
                return
            if taschenspalte is None and i == 8 and self.bohrtabelle.cellWidget(zeile, 4).currentData() in (OFFEN, DURCHGANG):
                self.status.setText(tr("Zuerst die Bohrungsausführung für Tiefe oder Senkwinkel wählen."))
                return
            if taschenspalte is None and i == 9 and self.bohrtabelle.cellWidget(zeile, 4).currentData() not in SPITZENFORMEN:
                self.status.setText(tr("Für einen Spitzenwinkel zuerst eine Bohrung mit Bohrspitze wählen."))
                return
            if taschenspalte == 8 and not self.taschen[zeile].langloch:
                self.status.setText(tr("Für den Achsabstand ein Langloch wählen."))
                return
            if taschenspalte == 7 and not self.taschen[zeile].radius:
                self.status.setText(tr("Für einen Eckradius eine gerundete Tasche wählen."))
                return
            if taschenspalte == 5 and self.taschentabelle.cellWidget(zeile, 6).currentIndex() == 1:
                self.status.setText(tr("Ein Durchbruch hat kein Tiefenmaß."))
                return
            if taschenspalte is None and i in (5, 6) and self.ringe[zeile].kern is not None:
                self.status.setText(tr("X und Y in der Zeile der innersten Bohrung angeben."))
                return
            wert = self.blatt.lies(box)
            spalte = taschenspalte if taschenspalte is not None else {8: 5, 9: 6}.get(i, i-4)
            lesen = tiefenmass if spalte == 5 else lese_angabe
            if taschenspalte == 7:
                lesen = eckradiusmass
            elif taschenspalte is None and (i == 9 or (i == 8 and tabelle.cellWidget(zeile, 4).currentData() == KEGELSENKUNG)):
                lesen = kegelwinkelmass
            faktor = self.einheit.currentData()
            if lesen(wert, faktor) is None:
                wert = ""
            elif faktor == 25.4 and lesen(wert, None) is None:
                # Die Bohrungstabelle verwendet mm, eine gedruckte Zollangabe eindeutig erhalten.
                wert += " in"
            tabelle.item(zeile, spalte).setText(wert)
        if wert:
            self.marken[schluessel] = Blattangabe(self.blatt.nummer, box, self.auswahl.currentText())
        self._markieren()
        self._pruefen()
        if not wert:
            self.status.setText(tr("Die Auswahl muss eine geschlossene Rechteckkontur enthalten. Im Grundriss sind einzelne Bohrkreise, Rechtecktaschen und Langlöcher zulässig.") if i < 2
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
        tiefen, winkel, spitzen, gesamt = [], {}, {}, set()
        for i in range(len(self.ringe)):
            art = self.bohrtabelle.cellWidget(i, 4).currentData()
            if art == OFFEN:
                raise ValueError(tr("Für Bohrung {} das Bohrungsende anhand der Zeichnung wählen.").format(i+1))
            text = self.bohrtabelle.item(i, 5).text()
            tiefen.append(text if art in MIT_TIEFENMASS else None)
            if art == KEGELSENKUNG:
                winkel[i] = text
            if art == SPITZE_GESAMTTIEFE:
                gesamt.add(i)
            if art in SPITZENFORMEN:
                spitzen[i] = self.bohrtabelle.item(i, 6).text()
        werte = [[self.bohrtabelle.item(i, j).text() for j in (1, 2, 3)] for i in range(len(self.ringe))]
        return sollbohrungen(self.ringe, werte, masse, self.konturen[0], tiefen=tiefen, senkwinkel=winkel,
                             spitzenwinkel=spitzen, bis_spitze=gesamt)

    def _innenkonturen(self, masse):
        bohrungen = self._bohrungen(masse)
        zeilen = [[self.taschentabelle.item(i,j).text() for j in range(1,6)] for i in range(len(self.taschen))]
        for i, zeile in enumerate(zeilen):
            if self.taschentabelle.cellWidget(i, 6).currentIndex() == 1:
                zeile[-1] = None
            zeile.extend(self.taschentabelle.item(i,j).text() for j in (7,8))
        taschen = solltaschen(self.taschen, zeilen, masse, self.konturen[0], bohrungen)
        return bohrungen, taschen

    def _pruefen(self):
        self.vorne_entfernen.setEnabled(self.vorne_offen or self.konturen[1] is not None)
        try:
            masse = self._masse()
        except ValueError as e:
            with QtCore.QSignalBlocker(self.bohrtabelle):
                for i in range(len(self.ringe)):
                    self.bohrtabelle.item(i, 0).setText("")
            with QtCore.QSignalBlocker(self.taschentabelle):
                for i in range(len(self.taschen)):
                    self.taschentabelle.item(i, 0).setText("")
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
            return
        with QtCore.QSignalBlocker(self.bohrtabelle):
            for i, q in enumerate(self.ringe):
                x, y = masse[0].nennwert, masse[1].nennwert
                self.bohrtabelle.item(i, 0).setText(f"{q.x*x:.2f} / {q.y*y:.2f} / ⌀{2*q.r*x:.2f}")
        with QtCore.QSignalBlocker(self.taschentabelle):
            x, y = masse[0].nennwert, masse[1].nennwert
            for i, q in enumerate(self.taschen):
                werte = (q.x*x, q.y*y, q.breite*x, q.hoehe*y)
                text = " / ".join(f"{v:.2f}" for v in werte)
                if q.langloch:
                    text = tr("Langloch") + " " + text
                elif q.radius:
                    text += f" / R{q.radius*x:.2f}"
                self.taschentabelle.item(i, 0).setText(text)
        try:
            self._innenkonturen(masse)
        except ValueError as e:
            self.status.setText(str(e))
            self.speichern.setEnabled(False)
        else:
            self.status.setText(tr("Platte {} × {} × {} mm").format(*(f"{p.nennwert:g}" for p in masse)))
            self.speichern.setEnabled(True)

    def _schreibe(self, ziel):
        masse = self._masse()
        bohrungen, taschen = self._innenkonturen(masse)
        return schreibe_platte(ziel, masse, bohrungen, taschen)


def oeffne_plattenzeichnung(fenster):
    return oeffne_koerperzeichnung(fenster, Plattendialog)
