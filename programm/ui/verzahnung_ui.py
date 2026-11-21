"""Fenster Verzahnung erkennen (PLAN §8.27): Zahnraddaten der gewaehlten Teile als Tabelle, Export CSV/JSON."""

from __future__ import annotations

import csv
import json
import os
import traceback

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import passverzahnung as pv
from ..kern import verzahnung as vz
from ..kern import verzahnung_daten as vd
from ..kern.kronenradpaar import kronenradpaare
from ..kern.verzahnung_sonder import Schneckenpaar, kegelpaar_kandidaten, schneckenpaar_kandidaten
from .lader import Modellauftrag
from .tabellen import spalten_anpassen


class VerzahnungLader(Modellauftrag):
    fertig = QtCore.Signal(object)  # Liste der Verzahnungen
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(int)

    def __init__(self, teile: list, parent=None, *, teilnummern=(), mit_sitzen=False):
        super().__init__(parent)
        self.teile = teile  # [(Name, Form)]
        self.mit_sitzen = mit_sitzen
        self.sitze = []
        self.sitzpaare = []
        self.teilnummern = teilnummern
        self.quellen = {}

    def run(self):
        from .lader import Abbruch, melder
        out = []
        try:
            def pruefe():
                if self.abgebrochen:
                    raise Abbruch
            melde = melder(self, lambda a: self.stand.emit(int(a * 100)))
            for i, (name, form) in enumerate(self.teile):
                melde(i / max(len(self.teile), 1))
                if self.mit_sitzen:
                    from ..kern import zylindersitze
                    nr = self.teilnummern[i] if self.teilnummern else i
                    try:
                        self.sitze.extend(zylindersitze.erkenne(form, nr, name, pruefe))
                    except RuntimeError:
                        # Defekte analytische Flaechen duerfen die Zahnpruefung nicht unterbrechen.
                        pass
                try:
                    for v in vz.erkenne_koerper(form, name, steckprofile=True, sonderprofile=True):
                        if self.teilnummern:
                            self.quellen[id(v)] = self.teilnummern[i]
                        out.append(v)
                        melde(i / len(self.teile))
                except Abbruch:
                    raise
                except Exception:  # noqa: BLE001 - ein Teil darf die Suche nicht abbrechen
                    continue
            if self.sitze:
                self.sitzpaare = zylindersitze.paare(self.sitze, pruefe)
            melde(1.0)
        except Abbruch:
            return
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        self.fertig.emit(out)


class VerzahnungFenster(QtWidgets.QDialog):
    teile_gewaehlt = QtCore.Signal(set)

    def __init__(self, liste: list, basis: str, parent=None, *, quellen=None, umfang="", getriebe=False, sitze=(), sitzpaare=()):
        super().__init__(parent)
        self.quellen = quellen or {}
        self.setWindowTitle(tr("Getriebe – Stufen und Kraftfluss") if getriebe else tr("Verzahnung – Raddaten"))
        self.liste = list(liste)
        self.raeder = [v for v in self.liste if isinstance(v, vz.Verzahnung)]
        self.steckpaare = pv.paare([v for v in self.liste if isinstance(v, pv.Steckprofil)])
        self.sonderpaare = kegelpaar_kandidaten(self.liste) + schneckenpaar_kandidaten(self.liste) + kronenradpaare(self.liste)
        self.bezugsrad = None
        self.basis = basis  # Pfad ohne Endung fuer die Exporte
        lay = QtWidgets.QVBoxLayout(self)
        hilfe = (tr("Der Reiter Kraftfluss zeigt die Übersetzung jeder erkannten Stufe und die Gesamtübersetzungen ab der gewählten Bezugswelle.") if getriebe else
                 tr("Die Datenblätter zeigen Zahnform und Abmessungen. Eine Radspalte wählt das Bauteil im Modell."))
        beschreibung = QtWidgets.QLabel(f"{umfang}\n{hilfe}" if umfang else hilfe)
        beschreibung.setWordWrap(True)
        lay.addWidget(beschreibung)
        self.reiter = QtWidgets.QTabWidget()
        lay.addWidget(self.reiter, 1)
        self.tabelle = QtWidgets.QTableWidget()
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.reiter.addTab(self.tabelle, tr("Datenblätter"))
        self.paare = vz.paare(self.liste)
        self.paar_tabelle = QtWidgets.QTableWidget()
        self.paar_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.reiter.addTab(self.paar_tabelle, tr("Radpaare und Steckverbindungen"))
        self.getriebe_tabelle = QtWidgets.QTableWidget()
        self.getriebe_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.getriebeseite = QtWidgets.QWidget()
        self.reiter.addTab(self.getriebeseite, tr("Kraftfluss"))
        getriebelayout = QtWidgets.QVBoxLayout(self.getriebeseite)
        wahl = QtWidgets.QFormLayout()
        self.bezugswelle = QtWidgets.QComboBox()
        wahl.addRow(tr("Bezugswelle für die Übersetzung"), self.bezugswelle)
        getriebelayout.addLayout(wahl)
        annahme = QtWidgets.QLabel(tr("Der Kraftfluss fasst gleichachsige Räder festachsiger Stufen automatisch zusammen. "
                                     "Unabhängige Wellen und Kupplungen können Sie im Betriebspunkt zuordnen."))
        annahme.setWordWrap(True)
        getriebelayout.addWidget(annahme)
        getriebelayout.addWidget(self.getriebe_tabelle, 1)
        self.bezugswelle.currentIndexChanged.connect(self._bezug_geaendert)
        from .getriebe_betrieb_ui import BetriebspunktSeite
        self.betriebspunkt = BetriebspunktSeite(self.liste, self.paare,
                                                [p for p in self.sonderpaare if isinstance(p, Schneckenpaar)])
        self.betriebspunkt.achseGeaendert.connect(self._achse_geaendert)
        self.reiter.addTab(self.betriebspunkt, tr("Betriebspunkt"))
        self._reiter_zeigen(self.betriebspunkt, self.betriebspunkt.verfuegbar())
        self.befund_tabelle = QtWidgets.QTableWidget()
        self.befund_tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.reiter.addTab(self.befund_tabelle, tr("Auslegungsbefunde"))
        self.sitzseite = None
        if sitze:
            from .sitzanalyse_ui import Sitzanalyse
            from collections import defaultdict
            from ..kern.zylindersitze import kragensitze
            kegel = defaultdict(list)
            for v in self.liste:
                if getattr(v, "ruecksitze", None) and id(v) in self.quellen:
                    kegel[self.quellen[id(v)]].append(v)
            self.sitzseite = Sitzanalyse(sitze, sitzpaare, set(self.quellen.values()), basis,
                                         kragensitze(sitze, sitzpaare, kegel))
            self.sitzseite.teile_gewaehlt.connect(self.teile_gewaehlt)
            self.reiter.addTab(self.sitzseite, tr("Wellen und Sitze"))
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
        self.pdf = QtWidgets.QPushButton(tr("PDF speichern …"))
        self.pdf.setToolTip(tr("Datenblätter, Radpaare und Auslegungsbefunde mit Quellen als PDF speichern"))
        self.pdf.clicked.connect(lambda: self.speichere("pdf"))
        self.paar_auslegen = QtWidgets.QPushButton(tr("Stirnradpaar auslegen …"))
        self.paar_auslegen.setToolTip(tr("Zähnezahlen und übereinstimmende Bezugsdaten des gewählten Paars übernehmen"))
        self.paar_auslegen.setVisible(False)
        self.paar_auslegen.clicked.connect(self._paar_auslegen)
        reihe.addWidget(self.paar_auslegen)
        reihe.addWidget(self.csv)
        reihe.addWidget(self.json)
        reihe.addWidget(self.rexs)
        reihe.addWidget(self.pdf)
        reihe.addStretch(1)
        schliessen = QtWidgets.QPushButton(tr("Schließen"))
        schliessen.clicked.connect(self.close)
        reihe.addWidget(schliessen)
        lay.addLayout(reihe)
        self.resize(760, 460)
        self._fuelle()

        paare = [(p.a, p.b) for p in self.paare] + [(p.welle, p.nabe) for p in self.steckpaare] + [
            (p.a, p.b) for p in self.sonderpaare]
        for tabelle, profile in ((self.tabelle, [(v,) for v in self.liste]), (self.paar_tabelle, paare)):
            tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectColumns)
            tabelle.itemSelectionChanged.connect(lambda t=tabelle, p=profile: self._auswahl(t, p))

        self.paar_tabelle.itemSelectionChanged.connect(self._paar_pruefen)
        self.reiter.currentChanged.connect(self._paar_pruefen)

    def _paar_pruefen(self):
        s = self.paar_tabelle.currentColumn()
        paar = self.paare[s] if 0 <= s < len(self.paare) else None
        geeignet = paar and all(not v.innen and not v.welle and abs(v.beta) < .1 for v in (paar.a, paar.b))
        self.paar_auslegen.setVisible(bool(geeignet and self.reiter.currentWidget() is self.paar_tabelle
                                          and self.paar_tabelle.selectedIndexes()))

    def _paar_auslegen(self):
        from .maschinenelemente_ui import zeige_auslegung
        paar = self.paare[self.paar_tabelle.currentColumn()]
        a, b = sorted((paar.a, paar.b), key=lambda v: v.z)
        werte = {"z1": a.z, "z2": b.z, "b1": a.b, "b2": b.b}
        if a.mn > 0 and abs(a.mn - b.mn) < .001:
            werte["m"] = a.mn
        if a.alpha_n > 0 and abs(a.alpha_n - b.alpha_n) < .1:
            werte["alpha"] = a.alpha_n
        def name(v):
            nr = self.quellen.get(id(v))
            return v.teil if nr is None else f"{v.teil} (#{nr})"
        return zeige_auslegung(self, messwerte=werte, quelle=f"{self.basis} · {name(a)} / {name(b)}")

    def _auswahl(self, tabelle, profile):
        spalten = {i.column() for i in tabelle.selectedIndexes()}
        teile = {self.quellen[id(v)] for s in spalten if s < len(profile) for v in profile[s] if id(v) in self.quellen}
        self.teile_gewaehlt.emit(teile)

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
        paarzeilen = [p.zeilen() + vd.paar_zeilen(p) for p in self.paare] + [
            p.zeilen() for p in self.steckpaare + self.sonderpaare]
        namen, werte = vd.tabelle(paarzeilen)
        pt.setRowCount(len(namen))
        pt.setColumnCount(len(paarzeilen))
        pt.setHorizontalHeaderLabels([f"{p.a.teil} – {p.b.teil}" for p in self.paare] +
                                     [f"{p.welle.teil} – {p.nabe.teil}" for p in self.steckpaare] +
                                     [f"{p.a.teil} – {p.b.teil}" for p in self.sonderpaare])
        pt.setVerticalHeaderLabels(namen)
        for s, spalte in enumerate(werte):
            for r, wert in enumerate(spalte):
                pt.setItem(r, s, QtWidgets.QTableWidgetItem(wert))
        spalten_anpassen(pt)
        self._reiter_zeigen(pt, bool(paarzeilen))
        self._achse_geaendert()
        texte = [f"{v.teil}: {h}" for v in self.raeder for h in v.hinweise]
        texte += [f"{p.a.teil} – {p.b.teil}: {h}" for p in self.paare for h in p.hinweise]
        self.hinweise.setText("\n".join(texte) if texte else ("" if self.liste else tr("Keine auswertbare Verzahnung gefunden. Bei Netzmodellen müssen die Zahnflanken durch genügend Dreiecke aufgelöst sein.")))
        for k in (self.csv, self.json, self.pdf):
            k.setEnabled(bool(self.liste or self.sitzseite))
        self.rexs.setEnabled(bool(self.raeder))

    def _reiter_zeigen(self, seite, sichtbar):
        self.reiter.setTabVisible(self.reiter.indexOf(seite), sichtbar)

    def _achse_geaendert(self):
        ref = self.bezugswelle.currentData()
        with QtCore.QSignalBlocker(self.bezugswelle):
            self.bezugswelle.clear()
            self.bezugswelle.addItem(tr("Automatisch (kleinstes Rad einer Endwelle)"), None)
            gruppen, zuege, _ = vd._zuege(self.liste, self.paare, achswahl=self.betriebspunkt.achswahl())
            for k in sorted({k for zug in zuege for k in zug.ergebnis}):
                gruppe = gruppen[k]
                self.bezugswelle.addItem(" + ".join(self.liste[i].teil for i in gruppe), gruppe[0])
            self.bezugswelle.setCurrentIndex(max(0, self.bezugswelle.findData(ref)))
        self._bezug_geaendert()

    def _bezug_geaendert(self):
        self.bezugsrad = self.bezugswelle.currentData()
        getriebe = vd.getriebe_zeilen(self.liste, self.paare, self.bezugsrad, self.betriebspunkt.achswahl())
        gt = self.getriebe_tabelle
        gt.setRowCount(len(getriebe))
        gt.setColumnCount(1)
        gt.setHorizontalHeaderLabels([tr("Wert")])
        gt.setVerticalHeaderLabels([a for a, _ in getriebe])
        for r, (_a, b) in enumerate(getriebe):
            gt.setItem(r, 0, QtWidgets.QTableWidgetItem(b))
        spalten_anpassen(gt)
        self._reiter_zeigen(self.getriebeseite, bool(getriebe))
        self.bezugswelle.setEnabled(self.bezugswelle.count() > 1)
        from ..kern import verzahnung_auslegung as va
        befunde = va.alle(self.liste, self.paare, self.liste[self.bezugsrad] if self.bezugsrad is not None else None)
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
        self._reiter_zeigen(bt, bool(befunde))

    def speichere(self, art: str, pfad: str = "") -> str | None:
        endung = {"csv": ".csv", "json": ".json", "rexs": ".rexsj", "pdf": ".pdf"}[art]
        filter_ = {"csv": "CSV (*.csv)", "json": "JSON (*.json)", "pdf": "PDF (*.pdf)",
                   "rexs": tr("REXS-Modell (*.rexsj *.rexs.json)")}[art]
        pfad = pfad or QtWidgets.QFileDialog.getSaveFileName(self, tr("Verzahnung speichern"),
                                                             self.basis + "_verzahnung" + endung, filter_)[0]
        if not pfad:
            return None
        if art == "pdf":
            from .berichte import verzahnung_pdf
            return verzahnung_pdf(self, pfad)
        with open(pfad, "w", encoding="utf-8-sig" if art == "csv" else "utf-8") as f:
            if art == "csv":
                f.write(vd.als_csv(self.liste, self.paare, self.bezugsrad, self.betriebspunkt.achswahl()))
                if self.sitzseite:
                    writer = csv.writer(f, delimiter=";", lineterminator="\n")
                    writer.writerow([])
                    writer.writerow([tr("Wellen und Sitze"), self.sitzseite.hinweis])
                    writer.writerow(self.sitzseite.spalten)
                    writer.writerows(self.sitzseite.zeilen)
                if self.betriebspunkt.verfuegbar():
                    writer = csv.writer(f, delimiter=";", lineterminator="\n")
                    writer.writerow([])
                    writer.writerow([tr("Betriebspunkt")])
                    writer.writerows(self.betriebspunkt.bedingungen())
                    writer.writerow(self.betriebspunkt.spalten())
                    writer.writerows(self.betriebspunkt.wellenzeilen())
            elif art == "rexs":
                from ..kern import rexs
                from ..version import VERSION
                json.dump(rexs.modell(self.raeder, self.paare, os.path.basename(self.basis) or "3DGmax", VERSION), f,
                          ensure_ascii=False, indent=1)
            else:
                daten = vd.datenblatt(self.liste, self.paare, self.bezugsrad, self.betriebspunkt.achswahl())
                if self.sitzseite:
                    daten["wellen_und_sitze"] = self.sitzseite.daten()
                if self.betriebspunkt.verfuegbar():
                    daten["betriebspunkt"] = self.betriebspunkt.daten()
                json.dump({"format": "3dgmax-verzahnung", "version": 2, **daten}, f,
                          ensure_ascii=False, indent=1)
        return pfad
