"""Vergleich in der Oberflaeche: Dialog, Hintergrundrechnung, Aenderungsliste mit Pruefrundgang, Abschluss."""

from __future__ import annotations

import os
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import pruefung

STATUS_TEXT = {"geaendert": "geändert", "neu": "neu", "entfernt": "entfernt", "entfallen": "entfallen",
               "geometrie": "Geometrie unter PMI geändert"}
PRUEF_TEXT = {"offen": "offen", "geprueft": "geprüft", "abgelehnt": "abgelehnt"}
KATEGORIE_TEXT = {"geometrie": "Geometrie", "pmi": "PMI"}


class VergleichDialog(QtWidgets.QDialog):
    """Alten und neuen Stand waehlen, Toleranz und Suchweite."""

    def __init__(self, alt: str = "", parent=None, zuletzt: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Zwei Stände vergleichen"))
        self.setMinimumWidth(560)
        form = QtWidgets.QFormLayout(self)
        self.alt = self._dateizeile(alt)
        self.neu = self._dateizeile("")
        form.addRow(tr("Alter Stand"), self.alt[0])
        form.addRow(tr("Neuer Stand"), self.neu[0])
        self.toleranz = QtWidgets.QDoubleSpinBox()
        self.toleranz.setDecimals(3)
        self.toleranz.setRange(0.001, 10.0)
        self.toleranz.setSingleStep(0.005)
        self.toleranz.setValue(0.01)
        self.toleranz.setSuffix(" mm")
        self.toleranz.setToolTip(tr("Bis zu dieser Abweichung gilt eine Fläche als gleich"))
        self.suchweite = QtWidgets.QDoubleSpinBox()
        self.suchweite.setDecimals(1)
        self.suchweite.setRange(0.1, 100.0)
        self.suchweite.setValue(2.0)
        self.suchweite.setSuffix(" mm")
        self.suchweite.setToolTip(tr("Bis zu dieser Abweichung gilt eine Fläche als geändert, darüber als neu/entfernt"))
        form.addRow(tr("Toleranz"), self.toleranz)
        form.addRow(tr("Suchweite"), self.suchweite)
        hinweis = QtWidgets.QLabel(tr("Liegen die Stände verschoben, werden sie automatisch per Bestpassung ausgerichtet."))
        hinweis.setObjectName("leise")
        hinweis.setWordWrap(True)
        form.addRow(hinweis)
        self.knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                                  QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.knoepfe.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(tr("Vergleichen"))
        self.knoepfe.accepted.connect(self.accept)
        self.knoepfe.rejected.connect(self.reject)
        form.addRow(self.knoepfe)
        for feld in (self.alt[1], self.neu[1]):
            feld.textChanged.connect(self._pruefe)
        self._pruefe()

    def _dateizeile(self, pfad):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        feld = QtWidgets.QLineEdit(pfad)
        knopf = QtWidgets.QPushButton(tr("Wählen …"))
        knopf.clicked.connect(lambda: self._waehle(feld))
        lay.addWidget(feld, 1)
        lay.addWidget(knopf)
        return w, feld

    def _waehle(self, feld):
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("STEP-Datei öffnen"), os.path.dirname(feld.text()),
                                                        "STEP (*.stp *.step *.STP *.STEP)")
        if pfad:
            feld.setText(pfad)

    def _pruefe(self):
        ok = all(os.path.isfile(f.text()) for f in (self.alt[1], self.neu[1]))
        self.knoepfe.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def werte(self) -> dict:
        return {"alt": self.alt[1].text(), "neu": self.neu[1].text(), "toleranz": self.toleranz.value(),
                "suchweite": self.suchweite.value()}


class VergleichsLader(QtCore.QThread):
    fertig = QtCore.Signal(object)
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(str)

    def __init__(self, werte: dict, alt_geladen=None, parent=None):
        super().__init__(parent)
        self.werte = werte
        self.alt_geladen = alt_geladen
        self.abgebrochen = False

    def run(self):
        from ..kern import vergleich
        from .lader import lade_alles
        try:
            w = self.werte
            alt = self.alt_geladen if self.alt_geladen is not None and \
                os.path.samefile(self.alt_geladen.pfad, w["alt"]) else lade_alles(w["alt"], self.stand.emit)
            self.stand.emit(tr("Neuen Stand laden …"))
            neu = lade_alles(w["neu"], self.stand.emit)
            v = vergleich.vergleiche(alt, neu, w["toleranz"], w["suchweite"], fortschritt=lambda t: self.stand.emit(tr(t)))
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            if not self.abgebrochen:
                self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        if not self.abgebrochen:
            self.fertig.emit(v)


class AenderungenPanel(QtWidgets.QWidget):
    """Nummerierte Aenderungen, Pruefstatus, Kommentar, Pruefrundgang."""

    gewaehlt = QtCore.Signal(object)  # Aenderung oder None
    abschliessen = QtCore.Signal()
    beenden = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vergleich = None
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.kopf = QtWidgets.QLabel("")
        self.kopf.setWordWrap(True)
        lay.addWidget(self.kopf)
        self.legende = QtWidgets.QLabel("")
        self.legende.setObjectName("leise")
        self.legende.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lay.addWidget(self.legende)
        oben = QtWidgets.QHBoxLayout()
        self.filter = QtWidgets.QComboBox()
        for text, wert in ((tr("Alle Änderungen"), None), (tr("Offen"), "offen"), (tr("Geometrie"), "geometrie"),
                           (tr("PMI"), "pmi")):
            self.filter.addItem(text, wert)
        self.start = QtWidgets.QPushButton(tr("Prüfen starten"))
        self.start.setObjectName("primaer")
        oben.addWidget(self.filter, 1)
        oben.addWidget(self.start)
        lay.addLayout(oben)
        self.tabelle = QtWidgets.QTableWidget(0, 4)
        self.tabelle.setHorizontalHeaderLabels([tr("Nr"), tr("Art"), tr("Änderung"), tr("Prüfstatus")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i in (0, 1, 3):
            kopf.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tabelle.setWordWrap(False)
        lay.addWidget(self.tabelle, 1)
        self.detail = QtWidgets.QLabel("")
        self.detail.setWordWrap(True)
        lay.addWidget(self.detail)
        self.kommentar = QtWidgets.QLineEdit()
        self.kommentar.setPlaceholderText(tr("Kommentar zur gewählten Änderung"))
        lay.addWidget(self.kommentar)
        reihe = QtWidgets.QHBoxLayout()
        self.zurueck = QtWidgets.QPushButton("◀")
        self.zurueck.setToolTip(tr("Vorherige Änderung"))
        self.geprueft = QtWidgets.QPushButton(tr("Geprüft"))
        self.abgelehnt = QtWidgets.QPushButton(tr("Abgelehnt"))
        self.offen = QtWidgets.QPushButton(tr("Offen"))
        self.vor = QtWidgets.QPushButton("▶")
        self.vor.setToolTip(tr("Nächste Änderung"))
        for k in (self.zurueck, self.geprueft, self.abgelehnt, self.offen, self.vor):
            reihe.addWidget(k)
        lay.addLayout(reihe)
        unten = QtWidgets.QHBoxLayout()
        self.ende_knopf = QtWidgets.QPushButton(tr("Vergleich beenden"))
        self.abschluss = QtWidgets.QPushButton(tr("Prüfung abschließen …"))
        unten.addWidget(self.ende_knopf)
        unten.addStretch(1)
        unten.addWidget(self.abschluss)
        lay.addLayout(unten)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)
        self.filter.currentIndexChanged.connect(self._filtern)
        self.start.clicked.connect(self.pruefen_starten)
        self.vor.clicked.connect(lambda: self.gehe(+1))
        self.zurueck.clicked.connect(lambda: self.gehe(-1))
        self.geprueft.clicked.connect(lambda: self.setze_status("geprueft"))
        self.abgelehnt.clicked.connect(lambda: self.setze_status("abgelehnt"))
        self.offen.clicked.connect(lambda: self.setze_status("offen", weiter=False))
        self.kommentar.editingFinished.connect(self._kommentar)
        self.abschluss.clicked.connect(self.abschliessen.emit)
        self.ende_knopf.clicked.connect(self.beenden.emit)
        for taste, slot in (("G", lambda: self.setze_status("geprueft")), ("A", lambda: self.setze_status("abgelehnt"))):
            QtGui.QShortcut(QtGui.QKeySequence(taste), self.tabelle, activated=slot)
        self._knoepfe()

    # --- Anzeige ---

    def zeige(self, vergleich, farben: dict | None = None):
        self.vergleich = vergleich
        t = self.tabelle
        t.blockSignals(True)
        if vergleich is None:
            t.setRowCount(0)
            self.kopf.setText("")
            self.legende.setText("")
        else:
            liste = vergleich.aenderungen
            t.setRowCount(len(liste))
            for z, a in enumerate(liste):
                self._zeile(z, a)
            z = vergleich.geo.zaehler
            self.kopf.setText(tr("{} → {}: {} Änderungen ({} PMI, {} Geometrie). Ausrichtung: {}.").format(
                os.path.basename(vergleich.alt.pfad), os.path.basename(vergleich.neu.pfad), len(liste),
                sum(a.kategorie == "pmi" for a in liste), sum(a.kategorie == "geometrie" for a in liste),
                tr({"gleich": "gleiche Lage", "bestpassung": "Bestpassung", "punkte": "Punktpaare"}
                   .get(vergleich.ausrichtung.methode, vergleich.ausrichtung.methode))))
            self.legende.setText(_legende(farben or {}, z))
        t.blockSignals(False)
        self._filtern()
        self._knoepfe()

    def _zeile(self, z, a):
        titel = a.titel if a.kategorie == "geometrie" else \
            f"{tr(STATUS_TEXT.get(a.status, a.status))}: {a.titel.split(': ', 1)[-1]}"
        werte = (str(a.nummer), tr(KATEGORIE_TEXT[a.kategorie]), tr(titel) if a.kategorie == "geometrie" else titel,
                 tr(PRUEF_TEXT[a.pruefstatus]))
        for s, w in enumerate(werte):
            it = QtWidgets.QTableWidgetItem(w)
            if s == 2:
                it.setToolTip(a.beschreibung)
            self.tabelle.setItem(z, s, it)

    def _filtern(self):
        wert = self.filter.currentData()
        for z, a in enumerate(self.vergleich.aenderungen if self.vergleich else []):
            zeigen = wert is None or a.pruefstatus == wert or a.kategorie == wert
            self.tabelle.setRowHidden(z, not zeigen)

    def gewaehlte(self):
        zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
        if not zeilen or self.vergleich is None:
            return None
        return self.vergleich.aenderungen[min(zeilen)]

    def _auswahl(self):
        a = self.gewaehlte()
        if a is not None:
            self.detail.setText(f"<b>{a.nummer}: {a.titel}</b><br>{a.beschreibung}")
            self.kommentar.setText(a.kommentar)
        else:
            self.detail.setText("")
            self.kommentar.clear()
        self._knoepfe()
        self.gewaehlt.emit(a)

    def _knoepfe(self):
        da = self.vergleich is not None and bool(self.vergleich.aenderungen)
        gewaehlt = self.gewaehlte() is not None
        for k in (self.geprueft, self.abgelehnt, self.offen, self.kommentar):
            k.setEnabled(gewaehlt)
        for k in (self.start, self.vor, self.zurueck, self.filter):
            k.setEnabled(da)
        self.abschluss.setEnabled(self.vergleich is not None)
        self.ende_knopf.setEnabled(self.vergleich is not None)

    # --- Pruefrundgang ---

    def waehle_zeile(self, z):
        self.tabelle.setRowHidden(z, False)
        self.tabelle.selectRow(z)
        self.tabelle.scrollToItem(self.tabelle.item(z, 0))

    def pruefen_starten(self):
        if not self.vergleich:
            return
        offen = [z for z, a in enumerate(self.vergleich.aenderungen) if a.pruefstatus == "offen"]
        self.waehle_zeile(offen[0] if offen else 0)
        self.tabelle.setFocus()

    def gehe(self, schritt: int):
        if not self.vergleich or not self.vergleich.aenderungen:
            return
        sichtbar = [z for z in range(self.tabelle.rowCount()) if not self.tabelle.isRowHidden(z)]
        if not sichtbar:
            return
        a = self.gewaehlte()
        jetzt = self.vergleich.aenderungen.index(a) if a is not None else -1
        if schritt > 0:
            ziel = next((z for z in sichtbar if z > jetzt), sichtbar[0])
        else:
            ziel = next((z for z in reversed(sichtbar) if z < jetzt), sichtbar[-1])
        self.waehle_zeile(ziel)

    def setze_status(self, status: str, weiter: bool = True):
        a = self.gewaehlte()
        if a is None:
            return
        self._kommentar()
        a.pruefstatus = status
        z = self.vergleich.aenderungen.index(a)
        self._zeile(z, a)
        offen = [i for i, x in enumerate(self.vergleich.aenderungen) if x.pruefstatus == "offen"]
        if weiter and offen:
            self.waehle_zeile(next((i for i in offen if i > z), offen[0]))

    def _kommentar(self):
        a = self.gewaehlte()
        if a is not None:
            a.kommentar = self.kommentar.text().strip()


def _legende(farben: dict, zaehler: dict) -> str:
    def feld(schluessel, text, anzahl):
        r, g, b = (int(255 * c) for c in farben.get(schluessel, (0.5, 0.5, 0.5)))
        return f"<span style='color: rgb({r},{g},{b})'>■</span> {text} ({anzahl})"
    return " &nbsp; ".join([feld("modell", tr("gleich"), zaehler.get("gleich", 0)),
                            feld("v_geaendert", tr("geändert"), zaehler.get("geaendert", 0)),
                            feld("v_neu", tr("neu"), zaehler.get("neu", 0)),
                            feld("v_entfernt", tr("entfernt"), zaehler.get("entfernt", 0))]) + \
        " &nbsp; " + tr("(Flächen)")


class AbschlussDialog(QtWidgets.QDialog):
    """Pruefer, Ergebnis, Bemerkung -> Protokoll (JSON + Text) mit Pruefsumme."""

    def __init__(self, vergleich, pruefer: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Prüfung abschließen"))
        self.vergleich = vergleich
        form = QtWidgets.QFormLayout(self)
        z = vergleich.zaehler()
        info = QtWidgets.QLabel(tr("{} geprüft, {} abgelehnt, {} offen").format(
            z.get("geprueft", 0), z.get("abgelehnt", 0), z.get("offen", 0)))
        form.addRow(info)
        self.pruefer = QtWidgets.QLineEdit(pruefer)
        self.ergebnis = QtWidgets.QComboBox()
        for e in pruefung.ERGEBNISSE:
            self.ergebnis.addItem(tr(e), e)
        self.bemerkung = QtWidgets.QPlainTextEdit()
        self.bemerkung.setMaximumHeight(90)
        form.addRow(tr("Prüfer"), self.pruefer)
        form.addRow(tr("Ergebnis"), self.ergebnis)
        form.addRow(tr("Bemerkung"), self.bemerkung)
        hinweis = QtWidgets.QLabel(tr("Das Protokoll erhält eine Prüfsumme (SHA-256) zur Erkennung späterer "
                                      "Änderungen. Es ist keine qualifizierte elektronische Signatur."))
        hinweis.setObjectName("leise")
        hinweis.setWordWrap(True)
        form.addRow(hinweis)
        self.knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save |
                                                  QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.knoepfe.accepted.connect(self.accept)
        self.knoepfe.rejected.connect(self.reject)
        form.addRow(self.knoepfe)
        self.pruefer.textChanged.connect(self._pruefe)
        self._pruefe()

    def _pruefe(self):
        self.knoepfe.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setEnabled(bool(self.pruefer.text().strip()))

    def werte(self) -> dict:
        return {"pruefer": self.pruefer.text().strip(), "ergebnis": self.ergebnis.currentData(),
                "bemerkung": self.bemerkung.toPlainText().strip()}
