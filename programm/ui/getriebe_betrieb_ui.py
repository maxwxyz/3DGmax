"""Betriebspunkt mit vorgegebenen Drehzahlen, Differentialachsen und drehfesten Kopplungen."""

from __future__ import annotations

from itertools import combinations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.getriebe_betrieb import Betriebsmodell


def _wert(zahl):
    return "–" if zahl is None else f"{zahl:.9g}"


class BetriebspunktSeite(QtWidgets.QWidget):
    achseGeaendert = QtCore.Signal()

    def __init__(self, liste, paare, hat_schneckenstufe=False):
        super().__init__()
        self.standardmodell = Betriebsmodell(liste, paare)
        self.modell = self.standardmodell
        self.paare = paare
        self.hat_schneckenstufe = hat_schneckenstufe
        self.varianten = {}
        self.vorgaben = {}
        self.kopplungen = set()
        lay = QtWidgets.QVBoxLayout(self)
        self.wellentrennung = QtWidgets.QCheckBox(tr("Koaxiale Räder auf getrennten Wellen ansetzen"))
        self.wellentrennung.setToolTip(tr("Koppeln Sie drehfest verbundene Wellen anschließend paarweise. "
                                        "Ein Wechsel setzt die Drehzahlvorgaben und Kopplungen zurück."))
        self.trennbar = self.standardmodell.trennbar
        self.wellentrennung.setVisible(self.trennbar)
        self.wellentrennung.toggled.connect(self._wellen_wechseln)
        lay.addWidget(self.wellentrennung)
        form = QtWidgets.QFormLayout()
        for k, gruppe in enumerate(self.modell.differentiale):
            if len(gruppe) <= 1:
                continue
            wahl = QtWidgets.QComboBox()
            wahl.addItem(tr("Trägerachse auswählen"), None)
            for i, satz in enumerate(gruppe):
                wahl.addItem(satz.name(liste), i)
            form.addRow(tr("Differential {} · Seitenräder").format(k + 1), wahl)
            self.varianten[k] = wahl
            wahl.currentIndexChanged.connect(self._aufbauen)
        if self.varianten:
            lay.addLayout(form)
        hilfe = QtWidgets.QLabel(tr("Aktivieren Sie bekannte Drehzahlen. 0 hält die Welle fest. "
                                    "Das Vorzeichen gibt den Drehsinn um die jeweilige positive Achse an."))
        hilfe.setWordWrap(True)
        lay.addWidget(hilfe)
        if self.hat_schneckenstufe:
            grenze = QtWidgets.QLabel(self.grenze())
            grenze.setWordWrap(True)
            lay.addWidget(grenze)
        self.tabelle = QtWidgets.QTableWidget(0, len(self.spalten()))
        self.tabelle.verticalHeader().hide()
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setHorizontalHeaderLabels(self.spalten())
        self.tabelle.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tabelle.setColumnWidth(1, 178)
        for c in (2, 3, 4):
            self.tabelle.horizontalHeader().setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tabelle, 1)
        self.kupplungsgruppe = QtWidgets.QGroupBox(tr("Koaxiale Wellen drehfest koppeln"))
        koppellay = QtWidgets.QVBoxLayout(self.kupplungsgruppe)
        self.kupplungen = QtWidgets.QListWidget()
        self.kupplungen.setMaximumHeight(86)
        self.kupplungen.itemChanged.connect(self._gekoppelt)
        koppellay.addWidget(self.kupplungen)
        lay.addWidget(self.kupplungsgruppe)
        self._aufbauen()

    @staticmethod
    def spalten():
        return [tr("Welle"), tr("Vorgabe (1/min)"), tr("Drehzahl (1/min)"), tr("Status"), tr("Positive Achse (X, Y, Z)")]

    def achswahl(self):
        return {k: w.currentData() for k, w in self.varianten.items() if w.currentData() is not None}

    def _wellen_wechseln(self, getrennt):
        self.modell = (Betriebsmodell(self.standardmodell.liste, self.paare, getrennte_wellen=True)
                       if getrennt else self.standardmodell)
        self.vorgaben.clear()
        self.kopplungen.clear()
        self._aufbauen()

    def _aufbauen(self):
        self.betrieb = self.modell.betrieb(self.achswahl())
        b = self.betrieb
        # Nach einer Achswahl koennen Stege andere Indizes haben. Eingaben gehoeren zur konkreten Welle.
        self.schluessel = {i: ("welle", i) for i in b.ports}
        self.rollen = {i: {} for i in b.ports}
        for s in b.saetze:
            a, seite_b, steg = s["wellen"]
            if s["art"] == "planet":
                self.rollen[a]["sonne"] = tr("Sonne")
                self.rollen[seite_b]["hohlrad"] = tr("Hohlrad")
            else:
                self.rollen[a]["seitenrad_a"] = tr("Seitenrad A")
                self.rollen[seite_b]["seitenrad_b"] = tr("Seitenrad B")
            self.rollen[steg]["steg"] = tr("Steg")
            self.schluessel[s["wellen"][2]] = (s["art"], *s["raeder"], tuple(s["umlaufraeder"]))
        self.tabelle.setRowCount(0)
        self.tabelle.setRowCount(len(b.ports))
        self.eingaben = {}
        for r, i in enumerate(b.ports):
            welle = QtWidgets.QTableWidgetItem(self._wellenname(i))
            welle.setToolTip(welle.text())
            self.tabelle.setItem(r, 0, welle)
            zelle = QtWidgets.QWidget()
            lay = QtWidgets.QHBoxLayout(zelle)
            lay.setContentsMargins(3, 0, 3, 0)
            an = QtWidgets.QCheckBox()
            an.setAccessibleName(tr("Drehzahl vorgeben") + " · " + self._wellenname(i))
            feld = QtWidgets.QDoubleSpinBox()
            feld.setDecimals(6)
            feld.setRange(-1e12, 1e12)
            feld.setKeyboardTracking(False)
            feld.setAccessibleName(self.spalten()[1] + " · " + self._wellenname(i))
            schluessel = self.schluessel[i]
            an.setChecked(schluessel in self.vorgaben)
            feld.setEnabled(an.isChecked())
            feld.setValue(self.vorgaben.get(schluessel, 0.))
            lay.addWidget(an)
            lay.addWidget(feld, 1)
            self.tabelle.setCellWidget(r, 1, zelle)
            self.eingaben[i] = (an, feld)
            an.toggled.connect(feld.setEnabled)
            an.toggled.connect(self._rechnen)
            feld.valueChanged.connect(self._rechnen)
        self.kupplungen.clear()
        for i, j in combinations(b.ports, 2):
            if not b.koppelbar(i, j):
                continue
            item = QtWidgets.QListWidgetItem(f"{self._wellenname(i)} ↔ {self._wellenname(j)}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, (i, j))
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            key = frozenset((self.schluessel[i], self.schluessel[j]))
            item.setCheckState(QtCore.Qt.CheckState.Checked if key in self.kopplungen else QtCore.Qt.CheckState.Unchecked)
            self.kupplungen.addItem(item)
        self.kupplungsgruppe.setVisible(self.kupplungen.count() > 0)
        self._rechnen()
        self.achseGeaendert.emit()

    def _wellenname(self, i):
        teile = [f"W{i + 1}"]
        # Der Name des virtuellen Stegs enthaelt seine Rolle bereits.
        teile.extend(wort for key, wort in self.rollen[i].items() if key != "steg")
        return " · ".join([*teile, self.betrieb.namen[i]])

    def _gekoppelt(self, item):
        i, j = item.data(QtCore.Qt.ItemDataRole.UserRole)
        key = frozenset((self.schluessel[i], self.schluessel[j]))
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            self.kopplungen.add(key)
        else:
            self.kopplungen.discard(key)
        self._rechnen()

    def _rechnen(self):
        drehzahlen = {}
        for i, (an, feld) in self.eingaben.items():
            key = self.schluessel[i]
            if an.isChecked():
                self.vorgaben[key] = drehzahlen[i] = feld.value()
            else:
                self.vorgaben.pop(key, None)
        paare = []
        for r in range(self.kupplungen.count()):
            item = self.kupplungen.item(r)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                paare.append(tuple(item.data(QtCore.Qt.ItemDataRole.UserRole)))
        self.ergebnis = self.betrieb.auswerten(drehzahlen, paare)
        for r, zeile in enumerate(self.wellenzeilen()):
            for c in (2, 3, 4):
                self.tabelle.setItem(r, c, QtWidgets.QTableWidgetItem(zeile[c]))

    @staticmethod
    def grenze():
        return tr("Schneckenstufen sind im Kraftfluss enthalten. Der Betriebspunkt berechnet die Drehzahlen der übrigen Stufen.")

    def achse(self, i):
        return self.betrieb.positive_achse(i) + 0.0

    def wellenzeilen(self):
        status = {"widerspruch": tr("Widerspruch"), "frei": tr("unbestimmt"), "bestimmt": tr("bestimmt")}
        return [(self._wellenname(w["id"]), _wert(w["vorgabe"]), _wert(w["drehzahl"]), status[w["status"]],
                 ", ".join(f"{x:.4g}" for x in self.achse(w["id"])))
                for w in self.ergebnis["wellen"]]

    def daten(self):
        achsen = []
        for k, gruppe in enumerate(self.modell.differentiale):
            wahl = self.varianten[k].currentData() if k in self.varianten else 0
            achsen.append({"gruppe": k, "auswahl": wahl,
                           "varianten": [{"seitenraeder": [s.a, s.b], "umlaufraeder": list(s.umlauf),
                                          "name": s.name(self.modell.liste)} for s in gruppe]})
        wellen = [dict(w, positive_achse=self.achse(w["id"]).tolist(), rollen=list(self.rollen[w["id"]]))
                  for w in self.ergebnis["wellen"]]
        return {**self.ergebnis, "wellen": wellen, "differentialachsen": achsen,
                "getrennte_wellen": self.wellentrennung.isChecked(),
                "schneckenstufen_ausgenommen": self.hat_schneckenstufe}

    def bedingungen(self):
        zeilen = [(tr("Berechnungsumfang"), self.grenze())] if self.hat_schneckenstufe else []
        if self.trennbar:
            annahme = (tr("Getrennte Wellen mit einzeln gewählten Kopplungen") if self.wellentrennung.isChecked()
                       else tr("Koaxiale Räder auf gemeinsamer Welle"))
            zeilen.append((tr("Wellenzuordnung im Betriebspunkt"), annahme))
        for gruppe in self.daten()["differentialachsen"]:
            wahl = gruppe["auswahl"]
            name = gruppe["varianten"][wahl]["name"] if wahl is not None else tr("Trägerachse auswählen")
            zeilen.append((tr("Differential {} · Seitenräder").format(gruppe["gruppe"] + 1), name))
        for i, j in self.ergebnis["kupplungen"]:
            zeilen.append((tr("Drehfeste Kopplung"), f"{self._wellenname(i)} ↔ {self._wellenname(j)}"))
        return zeilen

    def verfuegbar(self):
        return bool(self.betrieb.ports or self.modell.differentiale)
