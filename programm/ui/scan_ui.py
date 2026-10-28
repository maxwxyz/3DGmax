"""Scan gegen Toleranzen pruefen: Netz laden, ausrichten, je PMI bewerten (Hintergrund), Ergebnisliste."""

from __future__ import annotations

import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import scanpruefung as sp

STATUS_TEXT = {sp.OK: "✓ i. O.", sp.NOK: "✗ n. i. O.", sp.GRENZ: "≈ am Grenzwert", sp.OFFEN: "– nicht auswertbar"}
STATUS_FARBE = {sp.OK: "#1f9d55", sp.NOK: "#d6342c", sp.GRENZ: "#c98a00", sp.OFFEN: "#7a7f87"}


class ScanLader(QtCore.QThread):
    """Scan laden, Bestpassung + Feinausrichtung, Zuordnung zu den CAD-Flaechen, Bewertung."""

    fertig = QtCore.Signal(object)  # dict
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(str)

    def __init__(self, erg, pfad: str, parent=None, bezug: tuple | None = None, start=None, anlage: bool = False):
        super().__init__(parent)
        self.erg, self.pfad, self.bezug = erg, pfad, bezug  # bezug: Bezugssystem fuer 3-2-1 (None: Bestpassung)
        self.anlage = anlage  # Bezuege als anliegende Flaechen (ISO 5459) statt Gauss-Ausgleich
        self.startlage = start  # 4x4 Scan -> CAD von Hand (Punktpaare) statt der Grobausrichtung (nicht "start":
        # das ist QThread.start)
        self.abgebrochen = False

    def run(self):
        import numpy as np
        from ..kern import abweichung, ausrichten
        from ..kern.laden import lade_modell
        from .lader import Abbruch, melder
        melde = melder(self, self.stand.emit)  # zwischen den Schritten abbrechbar
        try:
            from ..kern import punktwolke
            melde(tr("Scan laden …"))
            wolke = punktwolke.ist_punktwolke(self.pfad)
            if wolke:
                roh = punktwolke.lies_punkte(self.pfad)
                netze = [(roh if len(roh) <= 400_000 else
                          roh[np.random.default_rng(4).choice(len(roh), 400_000, replace=False)],
                          np.zeros((0, 3), dtype=int))]
                probe = netze[0][0]
            else:
                scan = lade_modell(self.pfad)
                probe = sp.scan_punkte(scan, None)
                netze = ausrichten.tesselliere(scan.flaechen)
            melde(tr("Scan ausrichten …"))
            if self.startlage is not None:
                grob = ausrichten.Ausrichtung(np.asarray(self.startlage, float), "punkte", 0.0, 0.0)
            elif wolke:
                grob = ausrichten.richte_aus(self.erg.modell.flaechen, None, 0.05, punkte_b=probe)
            else:
                grob = ausrichten.richte_aus(self.erg.modell.flaechen, scan.flaechen, 0.05)
            matrix = sp.feinausrichten(self.erg.modell, probe, grob.matrix)
            if self.bezug:
                melde(tr("Am Bezugssystem {} ausrichten …").format("|".join(self.bezug)))
                stufen = [sp.bezug_flaechen(self.erg.pmi, b) for b in self.bezug]
                matrix = sp.richte_nach_bezug(self.erg.modell, probe, matrix, [s for s in stufen if s],
                                              anlage=self.anlage)
            melde(tr("Abweichungen berechnen …"))
            punkte = [p @ matrix[:3, :3].T + matrix[:3, 3] for p, _ in netze]
            alle = np.vstack([p for p in punkte if len(p)])
            z = sp.zuordnen(self.erg.modell, alle, nur=sp.pmi_flaechen(self.erg.pmi))  # exakt nur an PMI-Flaechen
            werte, k = [], 0
            for p in punkte:
                werte.append(z.abstand[k:k + len(p)])
                k += len(p)
            karte = abweichung.Karte([(p, t) for p, (_, t) in zip(punkte, netze)], werte, 0.0)
            melde(tr("Toleranzen bewerten …"))
            ergebnisse = sp.bewerte(self.erg.pmi, self.erg.modell, z)
            self.fertig.emit({"karte": karte, "ergebnisse": ergebnisse, "ausrichtung": grob, "matrix": matrix,
                              "pfad": self.pfad, "bezug": self.bezug, "punktwolke": wolke,
                              "punkte": int(sum(len(p) for p, _ in netze))})
        except Abbruch:
            return
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")


class ScanPanel(QtWidgets.QWidget):
    """Ergebnis der Scanpruefung je PMI; Doppelklick waehlt die PMI (Flaechen, Zone)."""

    gewaehlt = QtCore.Signal(object)  # Pmi
    beenden = QtCore.Signal()
    neu_auswerten = QtCore.Signal(object)  # Bezugssystem (Tupel) oder None fuer Bestpassung
    manuell = QtCore.Signal()  # Startlage von Hand (Punktpaare)
    bericht = QtCore.Signal()

    SPALTEN = ("Nr", "PMI", "Ergebnis", "Istwert", "Zulässig", "Punkte", "Auswertung")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.kopf = QtWidgets.QLabel("")
        self.kopf.setWordWrap(True)
        lay.addWidget(self.kopf)
        reihe = QtWidgets.QHBoxLayout()
        reihe.addWidget(QtWidgets.QLabel(tr("Ausrichtung")))
        self.ausrichtung = QtWidgets.QComboBox()
        self.ausrichtung.setToolTip(tr("Bestpassung über alle Punkte oder 3-2-1 am Bezugssystem der Zeichnung"))
        reihe.addWidget(self.ausrichtung, 1)
        self.anlage = QtWidgets.QCheckBox(tr("Anlage (ISO 5459)"))
        self.anlage.setToolTip(tr("Bezüge als anliegende Flächen außen am Material (größter Abstand minimal) statt "
                                  "Gauß-Ausgleich; empfindlich für Ausreißer im Scan"))
        reihe.addWidget(self.anlage)
        self.neu = QtWidgets.QPushButton(tr("Neu auswerten"))
        self.neu.clicked.connect(lambda: self.neu_auswerten.emit(self.gewaehlter_bezug()))
        reihe.addWidget(self.neu)
        self.manuell_knopf = QtWidgets.QPushButton(tr("Von Hand …"))
        self.manuell_knopf.setToolTip(tr("Startlage über Punktpaare Scan ↔ Modell (z. B. bei wenig Überdeckung oder "
                                         "symmetrischen Teilen); danach Feinausrichtung"))
        self.manuell_knopf.clicked.connect(self.manuell.emit)
        reihe.addWidget(self.manuell_knopf)
        lay.addLayout(reihe)
        self.setze_bezugssysteme([])
        self.tabelle = QtWidgets.QTableWidget(0, len(self.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in self.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)
        lay.addWidget(self.tabelle, 1)
        hinweis = QtWidgets.QLabel(tr("Näherung für die Sichtprüfung: Formtoleranzen als Spannweite, Achsen und "
                                      "Maße über Ausgleichszylinder; Messunsicherheit ±{} mm.").format(sp.UNSICHERHEIT))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.csv = QtWidgets.QPushButton(tr("CSV speichern …"))
        self.csv.clicked.connect(self.speichere_csv)
        self.pdf = QtWidgets.QPushButton(tr("Prüfbericht (PDF) …"))
        self.pdf.clicked.connect(self.bericht.emit)
        self.aus = QtWidgets.QPushButton(tr("Scan ausblenden"))
        self.aus.clicked.connect(self.beenden.emit)
        reihe.addWidget(self.csv)
        reihe.addWidget(self.pdf)
        reihe.addStretch(1)
        reihe.addWidget(self.aus)
        lay.addLayout(reihe)
        self.ergebnisse: list = []

    def setze_bezugssysteme(self, systeme: list, gewaehlt=None):
        """Auswahl der Ausrichtung: Bestpassung und die Bezugssysteme der Toleranzen."""
        self.ausrichtung.blockSignals(True)
        self.ausrichtung.clear()
        self.ausrichtung.addItem(tr("Bestpassung"), None)
        for drf in systeme:
            self.ausrichtung.addItem(tr("Bezugssystem {} (3-2-1)").format("|".join(drf)), tuple(drf))
        ziel = tuple(gewaehlt) if gewaehlt else None  # findData vergleicht Tupel nicht zuverlaessig
        i = next((k for k in range(self.ausrichtung.count())
                  if (tuple(self.ausrichtung.itemData(k)) if self.ausrichtung.itemData(k) else None) == ziel), 0)
        self.ausrichtung.setCurrentIndex(i)
        self.ausrichtung.blockSignals(False)

    def gewaehlter_bezug(self):
        d = self.ausrichtung.currentData()
        return tuple(d) if d else None

    def zeige(self, ergebnisse: list, kopf: str):
        self.ergebnisse = list(ergebnisse)
        self.kopf.setText(kopf)
        self.tabelle.setRowCount(len(self.ergebnisse))
        for z, e in enumerate(self.ergebnisse):
            werte = (str(e.pmi.nummer), e.pmi.wert_text(), tr(STATUS_TEXT[e.status]),
                     "" if e.ist is None else f"{e.ist:.4f}", "" if e.zulaessig is None else f"{e.zulaessig:.4f}",
                     str(e.punkte), e.text)
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s == 2:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(STATUS_FARBE[e.status])))
                self.tabelle.setItem(z, s, it)
        self.tabelle.resizeColumnsToContents()

    def zaehler(self) -> dict:
        out = {k: 0 for k in STATUS_TEXT}
        for e in self.ergebnisse:
            out[e.status] += 1
        return out

    def _auswahl(self):
        zeilen = {i.row() for i in self.tabelle.selectedItems()}
        if len(zeilen) == 1:
            self.gewaehlt.emit(self.ergebnisse[zeilen.pop()].pmi)

    def als_csv(self) -> str:
        import csv
        import io
        puffer = io.StringIO()
        w = csv.writer(puffer, delimiter=";")
        w.writerow([tr(s) for s in self.SPALTEN])
        for e in self.ergebnisse:
            zahl = (lambda x: "" if x is None else f"{x:.4f}".replace(".", ","))
            w.writerow([e.pmi.nummer, e.pmi.wert_text(), tr(STATUS_TEXT[e.status]), zahl(e.ist), zahl(e.zulaessig),
                        e.punkte, e.text])
        return puffer.getvalue()

    def speichere_csv(self, pfad: str = "") -> bool:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("CSV speichern"), "scanpruefung.csv", "CSV (*.csv)")
        if not pfad:
            return False
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(self.als_csv())
        return True
