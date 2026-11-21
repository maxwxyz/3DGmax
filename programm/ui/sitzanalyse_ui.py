"""Sitzbefunde mit den zugehoerigen Bauteilen und der Vorauslegung verbinden."""

from dataclasses import asdict

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from .maschinenelemente_ui import zeige_auslegung
from .tabellen import spalten_anpassen


class Sitzanalyse(QtWidgets.QWidget):
    teile_gewaehlt = QtCore.Signal(set)

    def __init__(self, sitze, paare, radnummern, basis, kragen=()):
        super().__init__()
        self.sitze = sitze
        self.paare = paare
        self.kragen = set(kragen)
        self.basis = basis
        self.radnummern = radnummern
        self.belege = []
        self.zeilen = []
        self.spalten = [tr("Befund"), tr("Bauteil / Partner"), tr("Durchmesser [mm]"),
                        tr("Länge [mm]"), tr("Bohrung − Zapfen [mm]")]
        self.hinweis = tr("Sitzpaare sind gleichachsige Zylinder mit axialer Überdeckung. Lagerbauart, Passung und Kraftübertragung erfordern weitere Angaben.")
        lay = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(self.hinweis)
        label.setWordWrap(True)
        lay.addWidget(label)
        for p in paare:
            art = tr("Möglicher Kragen einer Anlaufscheibe oder Buchse") if p in self.kragen else tr("Mögliches Sitzpaar")
            self._zeile(art, p.zapfen, p.ueberdeckung_mm, p.bohrung, p.differenz_mm)
        for s in sitze:
            self._zeile(tr("Bohrung") if s.innen else tr("Außenzylinder"), s, s.laenge_mm)
        self.tabelle = QtWidgets.QTableWidget(len(self.zeilen), len(self.spalten))
        self.tabelle.setHorizontalHeaderLabels(self.spalten)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, zeile in enumerate(self.zeilen):
            for c, text in enumerate(zeile):
                self.tabelle.setItem(r, c, QtWidgets.QTableWidgetItem(text))
        spalten_anpassen(self.tabelle)
        lay.addWidget(self.tabelle)
        self.auslegen = QtWidgets.QPushButton(tr("Gewählte Sitzmaße zur Auslegung übernehmen …"))
        self.auslegen.setToolTip(tr("Durchmesser und gemessene Länge mit Bauteilbezug in die Auslegung übernehmen"))
        self.auslegen.setEnabled(False)
        self.auslegen.clicked.connect(self._auslegen)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)
        lay.addWidget(self.auslegen, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

    def _name(self, sitz):
        text = f"{sitz.teil} (#{sitz.nummer})"
        return text + " · " + tr("Verzahnung") if sitz.nummer in self.radnummern else text

    def _zeile(self, art, sitz, laenge, partner=None, differenz=None):
        name = self._name(sitz)
        if partner:
            name += " / " + self._name(partner)
        self.zeilen.append([art, name, f"{sitz.d_mm:.6g}", f"{laenge:.6g}",
                            f"{differenz:.6g}" if differenz is not None else ""])
        self.belege.append((sitz, partner, laenge))

    def _auswahl(self):
        auswahl = self.tabelle.selectionModel().selectedRows()
        self.auslegen.setEnabled(bool(auswahl))
        if auswahl:
            a, b, _ = self.belege[auswahl[0].row()]
            self.teile_gewaehlt.emit({s.nummer for s in (a, b) if s})
        else:
            self.teile_gewaehlt.emit(set())

    def _auslegen(self):
        r = self.tabelle.currentRow()
        a, b, laenge = self.belege[r]
        return zeige_auslegung(self, art="reibsitz" if b else "buchse" if a.innen else "welle",
                               messwerte={"d": a.d_mm, "l": laenge},
                               quelle=f"{self.basis} · {self.zeilen[r][1]}")

    def daten(self):
        return {"zylinder": [asdict(s) for s in self.sitze],
                "sitzpaare": [asdict(p) for p in self.paare],
                "kragensitze": [asdict(p) for p in self.paare if p in self.kragen],
                "verzahnte_teilnummern": sorted(self.radnummern)}
