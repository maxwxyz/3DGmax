"""Leiste Kollisionen und Abstaende: Umfang und Grenzen waehlen, Befunde mit Pruefstatus, Auswahl zeigt den Befund."""

from __future__ import annotations

import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import kollision as ko

ART_FARBE = {ko.KOLLISION: "#c0392b", ko.ZU_NAH: "#d35400", ko.KONTAKT: "#2471a3", ko.ZU_WEIT: "#7d3c98"}
UMFANG = (("alle", "Alle Teile untereinander"), ("gegen", "Gewählte Teile gegen den Rest"),
          ("auswahl", "Gewählte Teile untereinander"))


class KollisionLader(QtCore.QThread):
    fertig = QtCore.Signal(object)  # Liste der Befunde
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(int)

    def __init__(self, teile, gruppe_b, einstellung, parent=None, grenzen: dict | None = None,
                 gepaart: set | None = None, bereiche: list | None = None):
        super().__init__(parent)
        self.teile, self.gruppe_b, self.einstellung = teile, gruppe_b, einstellung
        self.grenzen = grenzen  # Grenzlagen der Toleranzen je Teil: zusaetzlich pruefen
        self.gepaart = gepaart  # direkt verbundene Paare (in den Grenzlagen nicht melden)
        self.bereiche = bereiche or []  # je offenem Freiheitsgrad: (Teil, andere, Bewegung, bis, Text, Einheit)
        self.freie_bereiche: list[tuple] = []  # Ergebnis: (Teil, Text, unten, oben, Einheit)
        self.abgebrochen = False

    def run(self):
        from .lader import Abbruch, melder
        try:
            melde = melder(self, lambda a: self.stand.emit(int(a * 100)))
            anteile = 1 + bool(self.grenzen) + len(self.bereiche)  # Abschnitte des Fortschritts
            befunde = ko.pruefe(self.teile, self.gruppe_b, self.einstellung, fortschritt=lambda a: melde(a / anteile))
            if self.grenzen:
                befunde = befunde + ko.pruefe_grenzlagen(self.teile, self.grenzen, self.gruppe_b, self.einstellung,
                                                         fortschritt=lambda a: melde((1 + a) / anteile),
                                                         gepaart=self.gepaart)
            for k, (teil, andere, bewegung, bis, text, einheit) in enumerate(self.bereiche):
                start = 1 + bool(self.grenzen) + k
                unten, oben, grenzen = ko.freier_bereich(teil, andere, bewegung, bis, e=self.einstellung,
                                                         fortschritt=lambda a, s=start: melde((s + a) / anteile))
                self.freie_bereiche.append((teil.name, text, unten, oben, einheit))
                for x in grenzen:
                    x.bewegung = f"{text} {x.bewegung} {einheit}"
                befunde = befunde + grenzen
            for i, x in enumerate(befunde, 1):
                x.nummer = i
        except Abbruch:
            return
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        self.fertig.emit(befunde)


def _mm(minimum: float, wert: float, ausgeschaltet: bool) -> QtWidgets.QDoubleSpinBox:
    k = QtWidgets.QDoubleSpinBox()
    k.setDecimals(3)
    k.setRange(minimum, 1000.0)
    k.setSuffix(" mm")
    if ausgeschaltet:
        k.setSpecialValueText(tr("aus"))
    k.setValue(wert)
    return k


class KollisionPanel(QtWidgets.QWidget):
    starten = QtCore.Signal(dict)  # Umfang und Grenzen
    gewaehlt = QtCore.Signal(object)  # Befund oder None
    beenden = QtCore.Signal()
    pdf = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        form = QtWidgets.QFormLayout()
        self.umfang = QtWidgets.QComboBox()
        self.umfang.setToolTip(tr("Welche Paare geprüft werden: alle Teile untereinander, die gewählten untereinander "
                                  "oder die gewählten gegen den Rest"))
        for schluessel, text in UMFANG:
            self.umfang.addItem(tr(text), schluessel)
        self.kontakt = _mm(0.0, 0.01, False)
        self.kontakt.setToolTip(tr("Bis zu diesem Abstand gilt eine Berührung als Kontakt"))
        self.mindest = _mm(0.0, 0.0, True)
        self.mindest.setToolTip(tr("Paare mit kleinerem Abstand melden (Freigang)"))
        self.hoechst = _mm(0.0, 0.0, True)
        self.hoechst.setToolTip(tr("Paare mit größerem Abstand melden – nur „gegen den Rest“"))
        self.kontakte = QtWidgets.QCheckBox(tr("Kontakte melden"))
        self.kontakte.setToolTip(tr("Auch Berührungen (Abstand bis zur Kontaktgrenze) als Befund melden, nicht nur "
                                    "Durchdringungen"))
        self.kontakte.setChecked(True)
        self.grenzlagen = QtWidgets.QCheckBox(tr("Auch in den Grenzlagen der Toleranzen"))
        self.grenzlagen.setToolTip(tr("Zusammenbau: jedes verbundene Teil zusätzlich an den Grenzen seines Spielraums "
                                      "prüfen – gemeldet wird, was erst dort kollidiert oder zu nah kommt"))
        form.addRow(tr("Prüfen"), self.umfang)
        form.addRow(tr("Kontakt bis"), self.kontakt)
        form.addRow(tr("Mindestabstand"), self.mindest)
        form.addRow(tr("Höchstabstand"), self.hoechst)
        form.addRow("", self.kontakte)
        form.addRow("", self.grenzlagen)
        self.bereich = QtWidgets.QCheckBox(tr("Bewegungsbereich offener Freiheitsgrade"))
        self.bereich.setToolTip(tr("Zusammenbau: jedes Teil entlang jedes offenen Freiheitsgrads bis zur ersten "
                                   "Kollision bewegen – ergibt den freien Bereich je Freiheitsgrad"))
        self.bereich_mm = QtWidgets.QDoubleSpinBox()
        self.bereich_mm.setRange(0.1, 10000.0)
        self.bereich_mm.setValue(50.0)
        self.bereich_mm.setPrefix("± ")
        self.bereich_mm.setSuffix(" mm")
        self.bereich_grad = QtWidgets.QDoubleSpinBox()
        self.bereich_grad.setRange(0.1, 180.0)
        self.bereich_grad.setValue(180.0)
        self.bereich_grad.setPrefix("± ")
        self.bereich_grad.setSuffix(" °")
        for k in (self.bereich_mm, self.bereich_grad):
            k.setToolTip(tr("Geprüfter Bereich je Richtung: Verschiebung in mm, Drehung in Grad"))
        zeile = QtWidgets.QHBoxLayout()
        zeile.addWidget(self.bereich)
        zeile.addWidget(self.bereich_mm)
        zeile.addWidget(self.bereich_grad)
        form.addRow("", zeile)
        self.bereich.toggled.connect(self._aktiv)
        lay.addLayout(form)
        self.start = QtWidgets.QPushButton(tr("Prüfen"))
        self.start.setToolTip(tr("Kollisionsprüfung mit den Einstellungen oben starten"))
        self.start.clicked.connect(lambda: self.starten.emit(self.werte()))
        lay.addWidget(self.start)
        self.umfang.currentIndexChanged.connect(self._aktiv)
        self.kopf = QtWidgets.QLabel("")
        self.kopf.setWordWrap(True)
        lay.addWidget(self.kopf)
        self.tabelle = QtWidgets.QTableWidget(0, len(ko.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in ko.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)
        self.tabelle.itemChanged.connect(self._kommentar)
        lay.addWidget(self.tabelle, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.csv = QtWidgets.QPushButton(tr("CSV speichern …"))
        self.csv.setToolTip(tr("Befunde als Tabelle (CSV) speichern"))
        self.csv.clicked.connect(lambda: self.speichere_csv())
        self.aus = QtWidgets.QPushButton(tr("Befunde ausblenden"))
        self.aus.setToolTip(tr("Markierte Durchdringungen und Abstände im Modell ausblenden"))
        self.aus.clicked.connect(self.beenden.emit)
        reihe.addWidget(self.csv)
        self.pdf_knopf = QtWidgets.QPushButton(tr("PDF-Bericht …"))
        self.pdf_knopf.setToolTip(tr("Bericht mit Bild je Befund als PDF"))
        self.pdf_knopf.clicked.connect(self.pdf.emit)
        self.pdf_knopf.setEnabled(False)
        reihe.addWidget(self.pdf_knopf)
        reihe.addStretch(1)
        reihe.addWidget(self.aus)
        lay.addLayout(reihe)
        self.befunde: list[ko.Befund] = []
        self._aktiv()
        self.zeige([], "")

    def _aktiv(self):
        self.hoechst.setEnabled(self.umfang.currentData() == "gegen")
        self.bereich_mm.setEnabled(self.bereich.isChecked())
        self.bereich_grad.setEnabled(self.bereich.isChecked())

    def werte(self) -> dict:
        return {"umfang": self.umfang.currentData(), "kontakt": self.kontakt.value(), "mindest": self.mindest.value(),
                "hoechst": self.hoechst.value(), "kontakte": self.kontakte.isChecked(),
                "grenzlagen": self.grenzlagen.isChecked(), "bereich": self.bereich.isChecked(),
                "bereich_mm": self.bereich_mm.value(), "bereich_grad": self.bereich_grad.value()}

    def zeige(self, befunde: list, kopf: str):
        self.befunde = list(befunde)
        self.kopf.setText(kopf)
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(self.befunde))
        for z, b in enumerate(self.befunde):
            art = tr(ko.ART_TEXT[b.art]) + (" " + tr("(Grenzlage {})").format(b.grenzlage) if b.grenzlage else "")
            art += " " + tr("(bei {})").format(b.bewegung) if b.bewegung else ""
            ca = "≈ " if b.netz else ""  # aus Dreiecksnetzen genaehert
            werte = (str(b.nummer), b.a.name, b.b.name, art, f"{ca}{b.abstand:.3f}",
                     f"{ca}{b.volumen:.2f}" if b.volumen else "", f"{ca}{b.tiefe:.3f}" if b.tiefe else "")
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if b.netz and s >= 4:
                    it.setToolTip(tr("Netzteil: aus Dreiecken genähert (genau etwa bis zur Netzfeinheit)"))
                it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 3:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(ART_FARBE[b.art])))
                t.setItem(z, s, it)
            status = QtWidgets.QComboBox()
            for schluessel, text in ko.STATUS.items():
                status.addItem(tr(text), schluessel)
            status.setCurrentIndex(max(0, status.findData(b.status)))
            status.currentIndexChanged.connect(lambda _i, b=b, k=status: setattr(b, "status", k.currentData()))
            t.setCellWidget(z, 7, status)
            t.setItem(z, 8, QtWidgets.QTableWidgetItem(b.kommentar))  # Doppelklick: Kommentar
        t.blockSignals(False)
        t.resizeColumnsToContents()
        self.csv.setEnabled(bool(self.befunde))
        self.pdf_knopf.setEnabled(bool(self.befunde))
        self.aus.setEnabled(bool(self.befunde))

    def _kommentar(self, it):
        if it.column() == 8 and it.row() < len(self.befunde):
            self.befunde[it.row()].kommentar = it.text()

    def _auswahl(self):
        zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
        self.gewaehlt.emit(self.befunde[zeilen.pop()] if len(zeilen) == 1 else None)

    def zaehler(self) -> dict:
        out = {k: 0 for k in ko.ART_TEXT}
        for b in self.befunde:
            out[b.art] += 1
        return out

    def speichere_csv(self, pfad: str = "") -> bool:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("CSV speichern"), "kollisionen.csv", "CSV (*.csv)")
        if not pfad:
            return False
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(ko.als_csv(self.befunde))
        return True
