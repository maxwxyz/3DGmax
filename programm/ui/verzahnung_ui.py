"""Fenster Verzahnung erkennen (PLAN §8.27): Zahnraddaten der gewaehlten Teile als Tabelle, Export CSV/JSON."""

from __future__ import annotations

import json
import traceback

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import verzahnung as vz
from .tabellen import spalten_anpassen


class VerzahnungLader(QtCore.QThread):
    fertig = QtCore.Signal(object)  # Liste der Verzahnungen
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(int)

    def __init__(self, teile: list, parent=None):
        super().__init__(parent)
        self.teile = teile  # [(Name, Form)]
        self.abgebrochen = False

    def run(self):
        from .lader import Abbruch, melder
        out = []
        try:
            melde = melder(self, lambda a: self.stand.emit(int(a * 100)))
            for i, (name, form) in enumerate(self.teile):
                melde(i / max(len(self.teile), 1))
                try:
                    v = vz.erkenne(form, name)
                except Exception:  # noqa: BLE001 - ein Teil darf die Suche nicht abbrechen
                    v = None
                if v is not None:
                    out.append(v)
            melde(1.0)
        except Abbruch:
            return
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        self.fertig.emit(out)


class VerzahnungFenster(QtWidgets.QDialog):
    def __init__(self, liste: list, basis: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Verzahnung"))
        self.liste = list(liste)
        self.basis = basis  # Pfad ohne Endung fuer die Exporte
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(tr("Aus der Geometrie erkannt (Stirnschnitte, Evolventen-Fit). Abgeleitete Werte "
                                          "gelten für Evolventenverzahnungen ohne Flankenkorrekturen.")))
        self.tabelle = QtWidgets.QTableWidget()
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.tabelle, 1)
        self.paare = vz.paare(self.liste)
        self.paar_tabelle = QtWidgets.QTableWidget()
        self.paar_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.paar_titel = QtWidgets.QLabel(tr("<b>Radpaare</b> (parallele Achsen, Abstand passend)"))
        lay.addWidget(self.paar_titel)
        lay.addWidget(self.paar_tabelle)
        self.hinweise = QtWidgets.QLabel("")
        self.hinweise.setWordWrap(True)
        lay.addWidget(self.hinweise)
        reihe = QtWidgets.QHBoxLayout()
        self.csv = QtWidgets.QPushButton(tr("CSV speichern …"))
        self.csv.clicked.connect(lambda: self.speichere("csv"))
        self.json = QtWidgets.QPushButton(tr("JSON speichern …"))
        self.json.setToolTip(tr("Werte je Rad für den Import in Verzahnungs- und Systemprogramme"))
        self.json.clicked.connect(lambda: self.speichere("json"))
        reihe.addWidget(self.csv)
        reihe.addWidget(self.json)
        reihe.addStretch(1)
        schliessen = QtWidgets.QPushButton(tr("Schließen"))
        schliessen.clicked.connect(self.close)
        reihe.addWidget(schliessen)
        lay.addLayout(reihe)
        self.resize(760, 460)
        self._fuelle()

    def _fuelle(self):
        t = self.tabelle
        zeilen = [v.zeilen() for v in self.liste]
        namen = [z[0] for z in zeilen[0]] if zeilen else []
        t.setRowCount(len(namen))
        t.setColumnCount(len(self.liste) + 1)
        t.setHorizontalHeaderLabels([v.teil for v in self.liste] + [tr("Herkunft")])
        t.setVerticalHeaderLabels(namen)
        for s, z in enumerate(zeilen):
            for r, (_n, wert, _h) in enumerate(z):
                t.setItem(r, s, QtWidgets.QTableWidgetItem(wert))
        for r, (_n, _w, herkunft) in enumerate(zeilen[0] if zeilen else []):
            t.setItem(r, len(self.liste), QtWidgets.QTableWidgetItem(herkunft))
        spalten_anpassen(t)
        pt = self.paar_tabelle
        pz = [p.zeilen() for p in self.paare]
        pt.setRowCount(len(pz[0]) if pz else 0)
        pt.setColumnCount(len(self.paare))
        pt.setHorizontalHeaderLabels([f"{p.a.teil} – {p.b.teil}" for p in self.paare])
        pt.setVerticalHeaderLabels([n for n, _ in pz[0]] if pz else [])
        for s, z in enumerate(pz):
            for r, (_n, wert) in enumerate(z):
                pt.setItem(r, s, QtWidgets.QTableWidgetItem(wert))
        spalten_anpassen(pt)
        for w in (pt, self.paar_titel):
            w.setVisible(bool(self.paare))
        texte = [f"{v.teil}: {h}" for v in self.liste for h in v.hinweise]
        texte += [f"{p.a.teil} – {p.b.teil}: {h}" for p in self.paare for h in p.hinweise]
        self.hinweise.setText("\n".join(texte) if texte else ("" if self.liste else tr("Keine Verzahnung gefunden.")))
        for k in (self.csv, self.json):
            k.setEnabled(bool(self.liste))

    def speichere(self, art: str, pfad: str = "") -> str | None:
        endung = ".csv" if art == "csv" else ".json"
        pfad = pfad or QtWidgets.QFileDialog.getSaveFileName(self, tr("Verzahnung speichern"),
                                                             self.basis + "_verzahnung" + endung,
                                                             "CSV (*.csv)" if art == "csv" else "JSON (*.json)")[0]
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig" if art == "csv" else "utf-8") as f:
            if art == "csv":
                f.write(vz.als_csv(self.liste))
            else:
                paare = [{"a": p.a.teil, "b": p.b.teil, **{k: getattr(p, k) for k in (
                    "abstand", "abstand_soll", "alpha_wt", "eps_alpha", "eps_beta", "spiel")}} for p in self.paare]
                json.dump({"format": "3dgmax-verzahnung", "version": 1, "zahnraeder": [v.als_dict() for v in self.liste],
                           "paare": paare}, f, ensure_ascii=False, indent=1)
        return pfad
