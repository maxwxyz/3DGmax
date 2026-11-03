"""Fenster Verzahnung erkennen (PLAN §8.27): Zahnraddaten der gewaehlten Teile als Tabelle, Export CSV/JSON."""

from __future__ import annotations

import json
import os
import traceback

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import verzahnung as vz
from ..kern import verzahnung_daten as vd
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
        lay.addWidget(QtWidgets.QLabel(tr("Aus der Geometrie erkannt (Stirnschnitte, Evolventen-Fit), abgeleitet nach "
                                          "ISO 21771; Formkreise und Flankenkorrekturen aus der Zahndicke über dem "
                                          "Radius. „nicht bestimmbar“ statt geschätzter Werte.")))
        self.tabelle = QtWidgets.QTableWidget()
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.tabelle, 1)
        self.paare = vz.paare(self.liste)
        self.paar_tabelle = QtWidgets.QTableWidget()
        self.paar_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.paar_titel = QtWidgets.QLabel(tr("<b>Radpaare</b> (parallele Achsen, Abstand passend)"))
        lay.addWidget(self.paar_titel)
        lay.addWidget(self.paar_tabelle)
        self.getriebe_tabelle = QtWidgets.QTableWidget()
        self.getriebe_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.getriebe_titel = QtWidgets.QLabel(tr("<b>Getriebe</b> (Stufen über gleichachsige Räder, Planetensätze)"))
        lay.addWidget(self.getriebe_titel)
        lay.addWidget(self.getriebe_tabelle)
        self.befund_tabelle = QtWidgets.QTableWidget()
        self.befund_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.befund_titel = QtWidgets.QLabel(tr("<b>Auslegungsbefunde</b> – welche Entscheidungen die Geometrie "
                                                "zeigt, eingeordnet nach den üblichen Regeln (mit Quelle)"))
        self.befund_titel.setWordWrap(True)
        lay.addWidget(self.befund_titel)
        lay.addWidget(self.befund_tabelle)
        self.hinweise = QtWidgets.QLabel("")
        self.hinweise.setWordWrap(True)
        lay.addWidget(self.hinweise)
        reihe = QtWidgets.QHBoxLayout()
        self.csv = QtWidgets.QPushButton(tr("CSV speichern …"))
        self.csv.clicked.connect(lambda: self.speichere("csv"))
        self.json = QtWidgets.QPushButton(tr("JSON speichern …"))
        self.json.setToolTip(tr("Werte je Rad für den Import in Verzahnungs- und Systemprogramme"))
        self.json.clicked.connect(lambda: self.speichere("json"))
        self.rexs = QtWidgets.QPushButton(tr("REXS speichern …"))
        self.rexs.setToolTip(tr("Räder, Stufen, Wellen und Planetensätze als REXS-Modell (offenes Austauschformat für "
                                "Getriebedaten der FVA, Version 1.7), z. B. für Auslegungs- und Nachrechenprogramme"))
        self.rexs.clicked.connect(lambda: self.speichere("rexs"))
        reihe.addWidget(self.csv)
        reihe.addWidget(self.json)
        reihe.addWidget(self.rexs)
        reihe.addStretch(1)
        schliessen = QtWidgets.QPushButton(tr("Schließen"))
        schliessen.clicked.connect(self.close)
        reihe.addWidget(schliessen)
        lay.addLayout(reihe)
        self.resize(760, 460)
        self._fuelle()

    def _fuelle(self):
        t = self.tabelle
        zeilen = [vd.rad_alle_zeilen(v) for v in self.liste]
        namen, werte = vd.tabelle(zeilen)
        herkunft = {e[0]: e[2] for z in zeilen for e in z}
        t.setRowCount(len(namen))
        t.setColumnCount(len(self.liste) + 1)
        t.setHorizontalHeaderLabels([v.teil for v in self.liste] + [tr("Herkunft")])
        t.setVerticalHeaderLabels(namen)
        for s, spalte in enumerate(werte):
            for r, wert in enumerate(spalte):
                t.setItem(r, s, QtWidgets.QTableWidgetItem(wert))
        for r, n in enumerate(namen):
            t.setItem(r, len(self.liste), QtWidgets.QTableWidgetItem(herkunft.get(n, "")))
        spalten_anpassen(t)
        pt = self.paar_tabelle
        namen, werte = vd.tabelle([p.zeilen() + vd.paar_zeilen(p) for p in self.paare])
        pt.setRowCount(len(namen))
        pt.setColumnCount(len(self.paare))
        pt.setHorizontalHeaderLabels([f"{p.a.teil} – {p.b.teil}" for p in self.paare])
        pt.setVerticalHeaderLabels(namen)
        for s, spalte in enumerate(werte):
            for r, wert in enumerate(spalte):
                pt.setItem(r, s, QtWidgets.QTableWidgetItem(wert))
        spalten_anpassen(pt)
        for w in (pt, self.paar_titel):
            w.setVisible(bool(self.paare))
        getriebe = vd.getriebe_zeilen(self.liste, self.paare) if self.paare else []
        gt = self.getriebe_tabelle
        gt.setRowCount(len(getriebe))
        gt.setColumnCount(1)
        gt.setHorizontalHeaderLabels([tr("Wert")])
        gt.setVerticalHeaderLabels([a for a, _ in getriebe])
        for r, (_a, b) in enumerate(getriebe):
            gt.setItem(r, 0, QtWidgets.QTableWidgetItem(b))
        spalten_anpassen(gt)
        for w in (gt, self.getriebe_titel):
            w.setVisible(bool(getriebe))
        from ..kern import verzahnung_auslegung as va
        befunde = va.alle(self.liste, self.paare)
        bt = self.befund_tabelle
        bt.setRowCount(len(befunde))
        bt.setColumnCount(len(va.SPALTEN))
        bt.setHorizontalHeaderLabels([tr(s) for s in va.SPALTEN])
        bt.verticalHeader().setVisible(False)
        for r, b in enumerate(befunde):
            for s, text in enumerate(b.zeile()):
                it = QtWidgets.QTableWidgetItem(text)
                it.setToolTip(text)
                bt.setItem(r, s, it)
        spalten_anpassen(bt)
        for w in (bt, self.befund_titel):
            w.setVisible(bool(befunde))
        texte = [f"{v.teil}: {h}" for v in self.liste for h in v.hinweise]
        texte += [f"{p.a.teil} – {p.b.teil}: {h}" for p in self.paare for h in p.hinweise]
        self.hinweise.setText("\n".join(texte) if texte else ("" if self.liste else tr("Keine Verzahnung gefunden.")))
        for k in (self.csv, self.json, self.rexs):
            k.setEnabled(bool(self.liste))

    def speichere(self, art: str, pfad: str = "") -> str | None:
        endung = {"csv": ".csv", "json": ".json", "rexs": ".rexsj"}[art]
        filter_ = {"csv": "CSV (*.csv)", "json": "JSON (*.json)", "rexs": tr("REXS-Modell (*.rexsj *.rexs.json)")}[art]
        pfad = pfad or QtWidgets.QFileDialog.getSaveFileName(self, tr("Verzahnung speichern"),
                                                             self.basis + "_verzahnung" + endung, filter_)[0]
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig" if art == "csv" else "utf-8") as f:
            if art == "csv":
                f.write(vd.als_csv(self.liste, self.paare))
            elif art == "rexs":
                from ..kern import rexs
                from ..version import VERSION
                json.dump(rexs.modell(self.liste, self.paare, os.path.basename(self.basis) or "3DGmax", VERSION), f,
                          ensure_ascii=False, indent=1)
            else:
                json.dump({"format": "3dgmax-verzahnung", "version": 2, **vd.datenblatt(self.liste, self.paare)}, f,
                          ensure_ascii=False, indent=1)
        return pfad
