"""Fenster Funktion -> Tolerierung: Funktionsrollen der Flaechen vergeben, Bezugssystem und ISO-GPS-Tolerierung
vorschlagen (kern.funktion) und als eigene PMI uebernehmen."""

from __future__ import annotations

import html

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import funktion as fu

ROLLEN_HILFE = {
    "auflage": "Fläche, mit der das Teil aufliegt oder anliegt – Kandidat für den Primärbezug",
    "zentrierung": "Bohrung oder Zapfen, der das Teil in der Ebene ausrichtet (Passung H7/h6)",
    "fuehrung": "Gleitende Führung mit Spiel (Passung H7/f7, Zylinderform)",
    "presssitz": "Fest gefügte Verbindung (Übermaßpassung H7/p6)",
    "verdrehsicherung": "Stift oder Bohrung gegen Verdrehen (Übergangspassung H7/m6, Position mit Ⓜ)",
    "dichtung": "Dichtfläche (Ebenheit, Rauheit, drallfrei)",
    "anschlag": "Anschlag, der eine Richtung begrenzt (Flächenprofil zum Bezugssystem)",
    "frei": "Ohne Funktion – Allgemeintoleranz genügt",
}


class FunktionFenster(QtWidgets.QDialog):
    flaechen_zeigen = QtCore.Signal(set)
    anlegen = QtCore.Signal(list)  # PMI-Vorschlaege (kern.pmi_vorschlag.Vorschlag) zum Uebernehmen

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Funktion → Tolerierung"))
        self.resize(640, 520)
        self.rollen: dict[int, str] = {}
        self.modell = None
        self.auswahl = lambda: []  # gewaehlte Flaechenindizes (setzt das Hauptfenster)
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Flächen im Modell wählen und ihre Funktion zuordnen. Daraus folgen das "
                                      "Bezugssystem (3-2-1 nach ISO 5459) und die Tolerierung nach ISO 1101/286 – "
                                      "als Startwerte, die Toleranzkette legt die Werte fest."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.rolle = QtWidgets.QComboBox()
        for schluessel, (name, _) in fu.ROLLEN.items():
            self.rolle.addItem(tr(name), schluessel)
            self.rolle.setItemData(self.rolle.count() - 1, tr(ROLLEN_HILFE[schluessel]),
                                   QtCore.Qt.ItemDataRole.ToolTipRole)
        self.rolle.setToolTip(tr("Funktion der gewählten Flächen"))
        self.setzen = QtWidgets.QPushButton(tr("Rolle für Auswahl"))
        self.setzen.setToolTip(tr("Den im Modell gewählten Flächen diese Funktion zuordnen"))
        self.setzen.clicked.connect(lambda: self.setze_rolle(self.auswahl(), self.rolle.currentData()))
        self.weg = QtWidgets.QPushButton(tr("Entfernen"))
        self.weg.setToolTip(tr("Rolle der in der Tabelle gewählten Flächen entfernen"))
        self.weg.clicked.connect(self._entfernen)
        for w in (self.rolle, self.setzen, self.weg):
            reihe.addWidget(w)
        reihe.addStretch(1)
        lay.addLayout(reihe)
        self.tabelle = QtWidgets.QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels([tr("Fläche"), tr("Geometrie"), tr("Funktion")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.itemSelectionChanged.connect(self._zeige)
        lay.addWidget(self.tabelle, 1)
        self.bezug_text = QtWidgets.QLabel("")
        self.bezug_text.setWordWrap(True)
        self.bezug_text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lay.addWidget(self.bezug_text)
        knoepfe = QtWidgets.QHBoxLayout()
        self.bezuege_knopf = QtWidgets.QPushButton(tr("Bezüge vorschlagen"))
        self.bezuege_knopf.setToolTip(tr("Bezugssystem A|B|C aus den Rollen: größte Auflage, Zentrierung, "
                                         "Verdrehsicherung bzw. Anschlag – die Bezugsflächen werden hervorgehoben"))
        self.bezuege_knopf.clicked.connect(self.zeige_bezuege)
        self.tol_knopf = QtWidgets.QPushButton(tr("Tolerierung vorschlagen …"))
        self.tol_knopf.setObjectName("primaer")
        self.tol_knopf.setToolTip(tr("Bezüge, Passungen, Form-, Richtungs- und Lagetoleranzen je Rolle vorschlagen und "
                                     "als eigene PMI übernehmen (danach als STEP speicherbar)"))
        self.tol_knopf.clicked.connect(lambda: self.anlegen.emit(self.vorschlaege()))
        knoepfe.addWidget(self.bezuege_knopf)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.tol_knopf)
        lay.addLayout(knoepfe)
        self._fuelle()

    def setze_modell(self, modell):
        if modell is not self.modell:
            self.modell = modell
            self.rollen = {}
            self._fuelle()

    def setze_rolle(self, flaechen, rolle: str) -> int:
        """Rolle fuer Flaechen (nur Ebenen und Zylinder); Anzahl der zugeordneten Flaechen."""
        n = 0
        for i in flaechen:
            if self.modell is not None and fu._geometrie(self.modell.flaechen[i]) is not None:
                self.rollen[i] = rolle
                n += 1
        self._fuelle()
        return n

    def _entfernen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}, reverse=True):
            self.rollen.pop(self.tabelle.item(z, 0).data(QtCore.Qt.ItemDataRole.UserRole), None)
        self._fuelle()

    def _fuelle(self):
        t = self.tabelle
        t.setRowCount(len(self.rollen))
        for z, (i, rolle) in enumerate(sorted(self.rollen.items())):
            g = fu._geometrie(self.modell.flaechen[i]) if self.modell is not None else None
            art = "" if g is None else (tr("Ebene") if g["art"] == "ebene" else
                                        tr("Bohrung ⌀{:g}").format(round(g["groesse"], 3)) if g["bohrung"] else
                                        tr("Zapfen ⌀{:g}").format(round(g["groesse"], 3)))
            for s, text in enumerate((str(i), art, tr(fu.ROLLEN[rolle][0]))):
                it = QtWidgets.QTableWidgetItem(text)
                it.setData(QtCore.Qt.ItemDataRole.UserRole, i)
                if s == 2:
                    it.setToolTip(tr(ROLLEN_HILFE[rolle]))
                t.setItem(z, s, it)
        t.resizeColumnsToContents()
        for k in (self.bezuege_knopf, self.tol_knopf):
            k.setEnabled(bool(self.rollen))

    def _zeige(self):
        self.flaechen_zeigen.emit({self.tabelle.item(i.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
                                   for i in self.tabelle.selectedIndexes()})

    def bezugssystem(self) -> fu.Bezugssystem:
        return fu.bezugssystem(self.modell, self.rollen)

    def zeige_bezuege(self) -> fu.Bezugssystem:
        s = self.bezugssystem()
        zeilen = [f"<b>{b.buchstabe}</b> ({tr('Ebene') if b.element == 'ebene' else tr('Achse')}, "
                  f"{tr('Fläche')} {b.flaeche}): {html.escape(tr(b.grund))}" for b in s.bezuege]
        zeilen += [html.escape(h) for h in s.hinweise]
        self.bezug_text.setText("<br>".join(zeilen))
        self.flaechen_zeigen.emit({b.flaeche for b in s.bezuege})
        return s

    def vorschlaege(self) -> list:
        return fu.tolerierung(self.modell, self.rollen, self.zeige_bezuege()) if self.rollen else []
