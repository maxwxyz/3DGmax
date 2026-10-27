"""Vergleich in der Oberflaeche: Dialog, Hintergrundrechnung, Aenderungsliste mit Pruefrundgang, Abschluss."""

from __future__ import annotations

import os
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import pruefung

STATUS_TEXT = {"geaendert": "geändert", "neu": "neu", "entfernt": "entfernt", "entfallen": "entfallen",
               "geometrie": "Geometrie unter PMI geändert", "verschoben": "verschoben",
               "grafik": "Darstellung geändert"}
PRUEF_TEXT = {"offen": "offen", "geprueft": "geprüft", "abgelehnt": "abgelehnt"}
KATEGORIE_TEXT = {"geometrie": "Geometrie", "pmi": "PMI", "baugruppe": "Baugruppe"}


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
                                                        "Modelle (*.stp *.step *.p21 *.stpz *.stepz *.gz *.qif *.prc *.pdf *.igs *.iges *.stl *.obj *.gltf *.glb *.3mf *.ply)")
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

    def __init__(self, werte: dict, alt_geladen=None, parent=None, neu_geladen=None, ausrichtung=None):
        super().__init__(parent)
        self.werte = werte
        self.alt_geladen = alt_geladen
        self.neu_geladen = neu_geladen
        self.ausrichtung = ausrichtung
        self.abgebrochen = False

    def run(self):
        from ..kern import vergleich
        from .lader import lade_alles
        try:
            w = self.werte
            alt = self.alt_geladen if self.alt_geladen is not None and \
                os.path.samefile(self.alt_geladen.pfad, w["alt"]) else lade_alles(w["alt"], self.stand.emit)
            self.stand.emit(tr("Neuen Stand laden …"))
            neu = self.neu_geladen if self.neu_geladen is not None else lade_alles(w["neu"], self.stand.emit)
            v = vergleich.vergleiche(alt, neu, w["toleranz"], w["suchweite"], ausrichtung=self.ausrichtung,
                                     fortschritt=lambda t: self.stand.emit(tr(t)))
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            if not self.abgebrochen:
                self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        if not self.abgebrochen:
            self.fertig.emit(v)


class KartenLader(QtCore.QThread):
    """Abweichungs-Farbkarte im Hintergrund berechnen."""

    fertig = QtCore.Signal(object)  # Karte
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(int)  # Prozent

    def __init__(self, vergleich, parent=None):
        super().__init__(parent)
        self.vergleich = vergleich
        self.abgebrochen = False

    def run(self):
        from ..kern import abweichung
        from .lader import Abbruch, melder
        v = self.vergleich
        try:
            karte = abweichung.berechne(v.alt.modell, v.neu.modell, v.ausrichtung,
                                        fortschritt=melder(self, lambda a: self.stand.emit(int(a * 100))))
        except Abbruch:
            return
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        self.fertig.emit(karte)


class MaterialLader(QtCore.QThread):
    """Materialvergleich (Boolesche Operationen) im Hintergrund."""

    fertig = QtCore.Signal(object)
    fehler = QtCore.Signal(str)

    def __init__(self, vergleich, parent=None):
        super().__init__(parent)
        self.vergleich = vergleich
        self.abgebrochen = False

    def run(self):
        from ..kern import vergleich_volumen
        v = self.vergleich
        try:
            self.fertig.emit(vergleich_volumen.berechne(v.alt.modell.form, v.neu.modell.form, v.ausrichtung.gp_trsf(),
                                                        v.toleranz))
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(tr(str(e)))


SPALTEN_TIPP = {"Merkmal": "Was sich geändert hat (Feld der PMI, Abweichung, Lage, Volumen)",
               "Alt": "Wert im alten Stand", "Neu": "Wert im neuen Stand",
               "Δ": "Differenz neu − alt bzw. Betrag der Abweichung oder Verschiebung",
               "Tendenz": "Toleranz enger (strenger, oft teurer) oder weiter als vorher"}


class AenderungenPanel(QtWidgets.QWidget):
    """Nummerierte Aenderungen, Pruefstatus, Kommentar, Pruefrundgang, Abweichungs-Farbkarte."""

    gewaehlt = QtCore.Signal(object)  # Aenderung oder None
    abschliessen = QtCore.Signal()
    beenden = QtCore.Signal()
    karte = QtCore.Signal(bool, float)  # Farbkarte an/aus, Skalenende (0 = automatisch)
    material = QtCore.Signal(bool)  # Materialvergleich an/aus

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
                           (tr("Baugruppe"), "baugruppe"),
                           (tr("PMI"), "pmi")):
            self.filter.addItem(text, wert)
        self.start = QtWidgets.QPushButton(tr("Prüfen starten"))
        self.start.setObjectName("primaer")
        oben.addWidget(self.filter, 1)
        oben.addWidget(self.start)
        lay.addLayout(oben)
        reihe_karte = QtWidgets.QHBoxLayout()
        self.karte_an = QtWidgets.QCheckBox(tr("Abweichungs-Farbkarte"))
        self.karte_an.setToolTip(tr("Abstand des neuen zum alten Stand farbig: grün innerhalb der Toleranz, "
                                    "rot Aufmaß (+), blau Untermaß (−); Klick ins Modell zeigt den Wert"))
        self.skala = QtWidgets.QDoubleSpinBox()
        self.skala.setDecimals(3)
        self.skala.setRange(0.0, 1000.0)
        self.skala.setSingleStep(0.05)
        self.skala.setSuffix(" mm")
        self.skala.setSpecialValueText(tr("automatisch"))
        self.skala.setToolTip(tr("Skalenende ± (0 = automatisch)"))
        reihe_karte.addWidget(self.karte_an)
        reihe_karte.addStretch(1)
        reihe_karte.addWidget(QtWidgets.QLabel(tr("Skala ±")))
        reihe_karte.addWidget(self.skala)
        lay.addLayout(reihe_karte)
        self.material_an = QtWidgets.QCheckBox(tr("Material + / − (Volumen)"))
        self.material_an.setToolTip(tr("Hinzugekommenes Material grün, entferntes rot (exakt über Boolesche "
                                       "Operationen); Werte in der Statusleiste"))
        self.material_an.toggled.connect(self.material.emit)
        lay.addWidget(self.material_an)
        self.karte_an.toggled.connect(lambda an: self.karte.emit(an, self.skala.value()))
        self.skala.editingFinished.connect(
            lambda: self.karte_an.isChecked() and self.karte.emit(True, self.skala.value()))
        from ..kern.vergleich import SPALTEN as WERT_SPALTEN
        koepfe = ["Nr", "Art", "Änderung", *WERT_SPALTEN, "Prüfstatus"]
        self.tabelle = QtWidgets.QTableWidget(0, len(koepfe))
        self.tabelle.setHorizontalHeaderLabels([tr(k) for k in koepfe])
        for i, k in enumerate(koepfe):
            self.tabelle.horizontalHeaderItem(i).setToolTip(tr(SPALTEN_TIPP.get(k, "")))
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i in range(len(koepfe)):
            if i != 2:
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
        for box in (self.karte_an, self.material_an):  # neuer Vergleich: Farbkarte und Material aus
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
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
        titel = a.titel if a.kategorie in ("geometrie", "baugruppe") else \
            f"{tr(STATUS_TEXT.get(a.status, a.status))}: {a.titel.split(': ', 1)[-1]}"
        from ..kern.vergleich import spalten
        merkmal, alt, neu, delta, tendenz = spalten(a)
        werte = (str(a.nummer), tr(KATEGORIE_TEXT[a.kategorie]), tr(titel) if a.kategorie == "geometrie" else titel,
                 merkmal, alt, neu, delta, tendenz, tr(PRUEF_TEXT[a.pruefstatus]))
        for s, w in enumerate(werte):
            it = QtWidgets.QTableWidgetItem(w)
            if s == 2:
                it.setToolTip(a.beschreibung)
            elif s in (4, 5) and w:
                it.setToolTip(w)  # lange Werte (mehrere Felder) ganz zeigen
            elif s == 7 and w:
                it.setForeground(QtGui.QColor("#c0392b" if w == tr("enger") else "#2e7d32"))
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


class AusrichtPanel(QtWidgets.QDialog):
    """Manuell ausrichten: Elementpaare neu -> alt (Punkte, ebene Flaechen, Achsen), bis die Lage eindeutig ist."""

    ausrichten = QtCore.Signal(object)  # kern.ausrichten.Ausrichtung (B -> A)
    beendet = QtCore.Signal()

    ART_TEXT = {"punkt": "Punkt", "ebene": "Ebene", "achse": "Achse"}

    def __init__(self, trsf_jetzt, toleranz=lambda: 1.0, parent=None):
        super().__init__(parent)
        import numpy as np
        self.setWindowTitle(tr("Manuell ausrichten"))
        self.setMinimumWidth(560)
        self.m_jetzt = np.asarray(trsf_jetzt, float)  # aktuelle Abbildung B -> Anzeige (A)
        self.toleranz = toleranz
        self.paare: list = []  # (art, (ort_b, richtung_b) Original B, (ort_a, richtung_a))
        self.offen = None  # Element neu (Originalsystem), wartet auf Gegenstueck
        self.ergebnis = None
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Abwechselnd ein Element am neuen Stand und das passende am alten Stand (blau, "
                                      "durchscheinend) anklicken: Punkte (Fang an Ecken, Kantenmitten, Kreismitten), "
                                      "ebene Flächen oder Achsen (Bohrung, Kreiskante). Z. B. drei Flächen oder drei "
                                      "Punkte – so viele, bis die Lage eindeutig ist."))
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)
        self.stand = QtWidgets.QLabel("")
        self.stand.setObjectName("leise")
        self.stand.setWordWrap(True)
        lay.addWidget(self.stand)
        self.fang = QtWidgets.QCheckBox(tr("Fangen an Endpunkt, Mitte, Kreismitte"))
        self.fang.setChecked(True)
        lay.addWidget(self.fang)
        self.tabelle = QtWidgets.QTableWidget(0, 4)
        self.tabelle.setHorizontalHeaderLabels([tr("Nr"), tr("Art"), tr("Neu"), tr("Alt")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tabelle, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.weg = QtWidgets.QPushButton(tr("Letztes entfernen"))
        self.los = QtWidgets.QPushButton(tr("Ausrichten und neu vergleichen"))
        self.los.setObjectName("primaer")
        ende = QtWidgets.QPushButton(tr("Abbrechen"))
        for k in (self.weg, ende, self.los):
            reihe.addWidget(k)
        lay.addLayout(reihe)
        self.weg.clicked.connect(self.entferne_letztes)
        self.los.clicked.connect(self._ausrichten)
        ende.clicked.connect(self.close)
        self._zeige()

    def punkt(self, seite: str, form, punkt):
        import numpy as np
        from OCC.Core.gp import gp_Pnt
        from ..kern import ausrichten, messen
        p = gp_Pnt(*punkt)
        gefangen = False
        if self.fang.isChecked():
            art_fang, p = messen.fange(form, p, self.toleranz())
            gefangen = not art_fang.startswith("auf ")
        art, ort, richtung = ausrichten.element_von(form, (p.X(), p.Y(), p.Z()), gefangen)
        if seite == "neu":
            inv = np.linalg.inv(self.m_jetzt)
            self.offen = (art, (inv[:3, :3] @ ort + inv[:3, 3], None if richtung is None else inv[:3, :3] @ richtung))
        elif self.offen is not None:
            if self.offen[0] != art:
                self.stand.setText(tr("Gegenstück muss dieselbe Art haben ({}), gewählt: {}").format(
                    tr(self.ART_TEXT[self.offen[0]]), tr(self.ART_TEXT[art])))
                return
            self.paare.append((art, self.offen[1], (ort, richtung)))
            self.offen = None
        self._zeige()

    def entferne_letztes(self):
        if self.offen is not None:
            self.offen = None
        elif self.paare:
            self.paare.pop()
        self._zeige()

    def _zeige(self):
        from ..kern import ausrichten
        self.tabelle.setRowCount(len(self.paare))
        for z, (art, (ob, _), (oa, _)) in enumerate(self.paare):
            werte = (str(z + 1), tr(self.ART_TEXT[art]), ", ".join(f"{x:.2f}" for x in ob),
                     ", ".join(f"{x:.2f}" for x in oa))
            for s, w in enumerate(werte):
                self.tabelle.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        self.ergebnis = None
        if self.paare:
            try:
                self.ergebnis = ausrichten.richte_nach_elementen(self.paare)
            except ValueError:
                self.ergebnis = None
        if self.offen is not None:
            text = tr("Jetzt das passende Element am alten Stand (blau) wählen: {}").format(
                tr(self.ART_TEXT[self.offen[0]]))
        elif self.ergebnis is not None:
            text = tr("Lage eindeutig (Rest {:.4f} mm) – weitere Elemente verbessern die Ausrichtung").format(
                self.ergebnis.mittel)
        else:
            text = tr("{} Paare – Lage noch nicht eindeutig, nächstes Element am neuen Stand wählen").format(
                len(self.paare))
        self.stand.setText(text)
        self.los.setEnabled(self.ergebnis is not None)
        self.weg.setEnabled(bool(self.paare) or self.offen is not None)

    def berechne(self):
        from ..kern import ausrichten
        return ausrichten.richte_nach_elementen(self.paare)

    def _ausrichten(self):
        try:
            a = self.berechne()
        except ValueError as e:
            self.stand.setText(tr(str(e)))
            return
        self.ausrichten.emit(a)
        self.close()

    def closeEvent(self, ev):
        self.beendet.emit()
        super().closeEvent(ev)


MODI = (("vergleich", "Vergleich", "Neuer Stand nach Status gefärbt, entfernte Flächen des alten Stands rot"),
        ("alt", "Alt", "Nur der alte Stand"),
        ("neu", "Neu", "Nur der neue Stand"),
        ("ueberlagern", "Überlagern", "Neuer Stand, darüber der alte durchscheinend"),
        ("nebeneinander", "Nebeneinander", "Links alt, rechts neu, Kameras gekoppelt"),
        ("blinken", "Blinken", "Wechselt zwischen alt und neu; Leertaste wechselt von Hand"))
BLINK_TAKTE = ((300, "0,3 s"), (600, "0,6 s"), (1000, "1 s"), (2000, "2 s"))


class VergleichsmodusLeiste(QtWidgets.QFrame):
    """Leiste ueber der 3D-Ansicht im Vergleich: Modus, Aenderungen hervorheben, Blinktakt und Pause."""

    modus = QtCore.Signal(str)
    hervorheben = QtCore.Signal(bool)
    takt = QtCore.Signal(int)  # ms
    pause = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("vergleichsmodus")
        reihe = QtWidgets.QHBoxLayout(self)
        reihe.setContentsMargins(8, 3, 8, 3)
        reihe.addWidget(QtWidgets.QLabel(tr("Ansicht:")))
        self.gruppe = QtWidgets.QButtonGroup(self)
        self.knoepfe = {}
        for i, (schluessel, text, tipp) in enumerate(MODI, 1):
            k = QtWidgets.QToolButton()
            k.setText(tr(text))
            k.setCheckable(True)
            k.setAutoRaise(True)
            k.setToolTip(f"{tr(tipp)} (Alt+{i})")
            k.setShortcut(QtGui.QKeySequence(f"Alt+{i}"))
            self.gruppe.addButton(k)
            self.knoepfe[schluessel] = k
            k.clicked.connect(lambda _=False, s=schluessel: self.modus.emit(s))
            reihe.addWidget(k)
        self.knoepfe["vergleich"].setChecked(True)
        reihe.addSpacing(12)
        self.hervor = QtWidgets.QCheckBox(tr("Änderungen hervorheben"))
        self.hervor.setChecked(True)
        self.hervor.setToolTip(tr("In Alt, Neu, Nebeneinander und Blinken geänderte Flächen und PMI farbig zeigen"))
        self.hervor.toggled.connect(self.hervorheben.emit)
        reihe.addWidget(self.hervor)
        self.blink = QtWidgets.QWidget()
        b = QtWidgets.QHBoxLayout(self.blink)
        b.setContentsMargins(12, 0, 0, 0)
        self.takt_wahl = QtWidgets.QComboBox()
        for ms, text in BLINK_TAKTE:
            self.takt_wahl.addItem(text, ms)
        self.takt_wahl.setCurrentIndex(1)
        self.takt_wahl.setToolTip(tr("Blinkgeschwindigkeit"))
        self.takt_wahl.currentIndexChanged.connect(lambda _i: self.takt.emit(self.takt_wahl.currentData()))
        self.pause_knopf = QtWidgets.QPushButton()
        self.pause_knopf.setCheckable(True)
        self.pause_knopf.toggled.connect(self._pause)
        self._pause(False)
        self.stand = QtWidgets.QLabel("")
        self.stand.setMinimumWidth(40)
        for w in (self.takt_wahl, self.pause_knopf, self.stand):
            b.addWidget(w)
        reihe.addWidget(self.blink)
        reihe.addStretch(1)
        self.blink.setVisible(False)
        self.setStyleSheet("#vergleichsmodus { border-bottom: 1px solid palette(mid); }")

    def _pause(self, an: bool):
        self.pause_knopf.setText(tr("▶ Weiter") if an else tr("⏸ Anhalten"))
        self.pause_knopf.setToolTip(tr("Blinken fortsetzen") if an else tr("Blinken anhalten (Leertaste wechselt "
                                                                          "von Hand)"))
        self.pause.emit(an)

    def setze(self, modus: str):
        self.knoepfe[modus].setChecked(True)
        self.blink.setVisible(modus == "blinken")

    def zeige_stand(self, alt: bool | None):
        self.stand.setText("" if alt is None else tr("alt") if alt else tr("neu"))
