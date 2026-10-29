"""Fenster 2D-Toleranzkette: Vektorzug von Hand mit Auswahlfeldern, Skizze, Ergebnis linear (DLM) und nichtlinear
(Monte Carlo); Uebernahme der linearisierten Kette in das 1D-Kettenfenster (kern.kette2d)."""

from __future__ import annotations

import math

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import kette2d as k2
from ..kern import toleranzkette as tk
from .tabellen import erste_spalte_fest, spalten_anpassen
from .bewertung_ui import BewertungLeiste
from .werkstoff_wahl import WaermeZeile, werkstoff_feld, werkstoff_wert

SPALTEN = (("Name", "Bezeichnung des Segments (z. B. Bauteil oder Maß)"),
           ("Länge", "Nennlänge des Segments in mm"),
           ("oben", "Oberes Abmaß der Länge in mm"),
           ("unten", "Unteres Abmaß der Länge in mm"),
           ("Winkel", "Winkel zum vorigen Segment in Grad (erstes Segment: zur X-Achse); positiv gegen den "
                      "Uhrzeigersinn"),
           ("oben °", "Oberes Abmaß des Winkels in Grad"),
           ("unten °", "Unteres Abmaß des Winkels in Grad"),
           ("Verteilung", "Streuung von Länge und Winkel in der Fertigung"),
           ("Werkstoff", "Eigener Werkstoff des Segments für die Wärmeausdehnung; „wie Kette“: der Werkstoff der Kette"))
SP_VERTEILUNG, SP_WERKSTOFF = len(SPALTEN) - 2, len(SPALTEN) - 1
VORLAGEN = {"winkel": ("Rechter Winkel (3-4-5)", [k2.Segment("Schenkel 1", 30, 0.1, -0.1),
                                                   k2.Segment("Schenkel 2", 40, 0.1, -0.1, 90, 0.5, -0.5)]),
            "hebel": ("Hebel mit Lagerabstand", [k2.Segment("Gestell", 80, 0.05, -0.05),
                                                  k2.Segment("Hebel", 50, 0.1, -0.1, 120, 0.25, -0.25),
                                                  k2.Segment("Koppel", 60, 0.1, -0.1, 100, 0.25, -0.25)])}


class Skizze(QtWidgets.QWidget):
    """Vektorzug masstaeblich: Segmente mit Namen, Schlussvektor gestrichelt rot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 220)
        self.kette: k2.Kette2D | None = None

    def paintEvent(self, _ev):
        if self.kette is None or not self.kette.segmente:
            return
        pts = k2.punkte(self.kette)
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        groesse = float(max(hi - lo)) or 1.0
        rand = 28
        m = min(self.width() - 2 * rand, self.height() - 2 * rand) / groesse
        mitte = (lo + hi) / 2

        def xy(p):
            return QtCore.QPointF(self.width() / 2 + (p[0] - mitte[0]) * m, self.height() / 2 - (p[1] - mitte[1]) * m)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        farbe = pal.color(QtGui.QPalette.ColorRole.Highlight)
        for i, s in enumerate(self.kette.segmente):
            a, b = xy(pts[i]), xy(pts[i + 1])
            p.setPen(QtGui.QPen(farbe, 2.2))
            p.drawLine(a, b)
            p.setBrush(farbe)
            p.drawEllipse(b, 3, 3)
            p.setPen(pal.color(QtGui.QPalette.ColorRole.Text))
            p.drawText((a + b) / 2 + QtCore.QPointF(4, -4), s.name)
        p.setPen(QtGui.QPen(QtGui.QColor("#c0392b"), 1.8, QtCore.Qt.PenStyle.DashLine))
        p.drawLine(xy(pts[-1]), xy(pts[0]))
        p.setPen(QtGui.QColor("#c0392b"))
        mitte_s = (xy(pts[-1]) + xy(pts[0])) / 2
        p.drawText(mitte_s + QtCore.QPointF(-p.fontMetrics().horizontalAdvance(tr("Schluss")) / 2, -8), tr("Schluss"))
        p.end()


class Kette2DFenster(QtWidgets.QDialog):
    uebernehmen = QtCore.Signal(list)  # linearisierte Glieder fuer das 1D-Kettenfenster

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("2D-Toleranzkette"))
        self.resize(1250, 560)
        self.kette = k2.Kette2D()
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Kette als Vektorzug in einer Ebene: je Segment Länge und Winkel zum vorigen "
                                      "Segment mit Abmaßen. Die Schlussgröße wird linearisiert (Empfindlichkeiten) "
                                      "und zusätzlich nichtlinear per Monte Carlo geprüft."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.plus = QtWidgets.QPushButton(tr("＋ Segment"))
        self.plus.setToolTip(tr("Segment anhängen (Länge 10 mm, Winkel 0° zum vorigen)"))
        self.plus.clicked.connect(lambda: self.neues_segment())
        self.weg = QtWidgets.QPushButton(tr("－ Entfernen"))
        self.weg.setToolTip(tr("Gewählte Segmente entfernen"))
        self.weg.clicked.connect(self._entfernen)
        self.vorlage = QtWidgets.QComboBox()
        self.vorlage.addItem(tr("Vorlage …"), "")
        for schluessel, (name, _) in VORLAGEN.items():
            self.vorlage.addItem(tr(name), schluessel)
        self.vorlage.setToolTip(tr("Beispielkette laden, um die Eingabe kennenzulernen"))
        self.vorlage.activated.connect(lambda _i: self.lade_vorlage(self.vorlage.currentData()))
        self.schluss = QtWidgets.QComboBox()
        for schluessel, name in k2.SCHLUSS.items():
            self.schluss.addItem(tr(name), schluessel)
        self.schluss.setToolTip(tr("Welche Größe die Funktion bestimmt: Abstand vom Ende zum Anfang des Zugs, sein X- "
                                   "oder Y-Anteil oder die Richtung des letzten Segments"))
        self.schluss.currentIndexChanged.connect(self._schluss_geaendert)
        self.oeffnen_knopf = QtWidgets.QPushButton(tr("Öffnen …"))
        self.oeffnen_knopf.setToolTip(tr("Gespeicherte {}-Kette laden").format("2D"))
        self.oeffnen_knopf.clicked.connect(lambda: self.oeffne())
        self.speichern_knopf = QtWidgets.QPushButton(tr("Speichern …"))
        self.speichern_knopf.setToolTip(tr("{}-Kette als Datei speichern (auch im Projekt enthalten)").format("2D"))
        self.speichern_knopf.clicked.connect(lambda: self.speichere())
        for w in (self.plus, self.weg, self.vorlage, self.oeffnen_knopf, self.speichern_knopf):
            reihe.addWidget(w)
        reihe.addStretch(1)
        reihe.addWidget(QtWidgets.QLabel(tr("Schlussgröße")))
        reihe.addWidget(self.schluss)
        lay.addLayout(reihe)
        mitte = QtWidgets.QHBoxLayout()
        self.tabelle = QtWidgets.QTableWidget(0, len(SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(n) for n, _ in SPALTEN])
        for i, (_, hilfe) in enumerate(SPALTEN):
            self.tabelle.horizontalHeaderItem(i).setToolTip(tr(hilfe))
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.itemChanged.connect(self._name_geaendert)
        erste_spalte_fest(self.tabelle)  # Name bleibt beim Querrollen stehen
        mitte.addWidget(self.tabelle, 5)
        self.skizze = Skizze()
        mitte.addWidget(self.skizze, 2)
        lay.addLayout(mitte, 1)
        self.waerme = WaermeZeile()
        self.waerme.geaendert.connect(self._waerme_geaendert)
        lay.addWidget(self.waerme)
        self.bewertung = BewertungLeiste()
        self.bewertung.geaendert.connect(self._bewertung_geaendert)
        lay.addWidget(self.bewertung)
        self.ergebnis = QtWidgets.QLabel("")
        self.ergebnis.setWordWrap(True)
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.ergebnis)
        knoepfe = QtWidgets.QHBoxLayout()
        self.in_kette = QtWidgets.QPushButton(tr("In Toleranzkette übernehmen"))
        self.in_kette.setObjectName("primaer")
        self.in_kette.setToolTip(tr("Linearisierte Kette (je Länge und Winkel ein Glied mit seiner Empfindlichkeit als "
                                    "Faktor) ins Fenster Toleranzkette: dort Anforderung, Ampel, Histogramm, "
                                    "Kostenoptimierung und Bericht"))
        self.in_kette.clicked.connect(lambda: self.uebernehmen.emit(k2.als_glieder(self.kette)))
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.in_kette)
        lay.addLayout(knoepfe)
        self._fuelle()

    # --- Bearbeiten ---

    def neues_segment(self, segment: k2.Segment | None = None):
        n = len(self.kette.segmente) + 1
        self.kette.segmente.append(segment or k2.Segment(tr("Segment {}").format(n), 10.0))
        self._fuelle()
        return self.kette.segmente[-1]

    def setze_kette(self, kette):
        """Kette uebernehmen (aus Datei oder Projekt)."""
        self.kette = kette
        self._fuelle()

    def speichere(self, pfad: str = "") -> str | None:
        from ..kern import kette_datei
        endung = kette_datei.ENDUNG_2D
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Kette speichern"), "kette" + endung,
                                                            tr("2D-Kette (*{})").format(endung))
        return kette_datei.speichere_raum(pfad, self.kette) if pfad else None

    def oeffne(self, pfad: str = "") -> bool:
        from ..kern import kette_datei
        endung = kette_datei.ENDUNG_2D
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Kette öffnen"), "",
                                                            tr("2D-Kette (*{})").format(endung))
        if not pfad:
            return False
        try:
            kette = kette_datei.lade_raum(pfad)
        except (OSError, ValueError, KeyError) as fehler:
            QtWidgets.QMessageBox.warning(self, tr("Kette öffnen"), str(fehler))
            return False
        if not isinstance(kette, k2.Kette2D):
            self.ergebnis.setText(tr("Diese Datei enthält eine andere Art von Kette."))
            return False
        self.setze_kette(kette)
        return True

    def lade_vorlage(self, schluessel: str):
        if not schluessel:
            return
        import copy
        self.kette = k2.Kette2D(copy.deepcopy(VORLAGEN[schluessel][1]), self.kette.schluss)
        self.vorlage.setCurrentIndex(0)
        self._fuelle()

    def _entfernen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}, reverse=True):
            del self.kette.segmente[z]
        self._fuelle()

    def _bewertung_geaendert(self):
        self.kette.anforderung, self.kette.freigabe = self.bewertung.anforderung_werte(), self.bewertung.freigabe()
        self._rechne()

    def _waerme_geaendert(self):
        self.kette.werkstoff, self.kette.temperaturen = self.waerme.wert(), self.waerme.temperaturen()
        self._rechne()

    def _schluss_geaendert(self, *_):
        self.kette.schluss = self.schluss.currentData()
        self._rechne()

    def _name_geaendert(self, it):
        if it.column() == 0 and it.row() < len(self.kette.segmente):
            self.kette.segmente[it.row()].name = it.text()
            self.tabelle.blockSignals(True)
            spalten_anpassen(self.tabelle)  # laengerer Name: Spalte waechst mit
            self.tabelle.blockSignals(False)
            self.skizze.update()

    def _feld(self, s: k2.Segment, attr: str, lo: float, hi: float, dez: int, einheit: str, hilfe: str):
        w = QtWidgets.QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(dez)
        w.setSuffix(einheit)
        w.setValue(getattr(s, attr))
        w.setToolTip(tr(hilfe))
        w.valueChanged.connect(lambda v, s=s, attr=attr: (setattr(s, attr, v), self._rechne()))
        return w

    def _fuelle(self):
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(self.kette.segmente))
        hilfe = dict(SPALTEN)
        for z, s in enumerate(self.kette.segmente):
            name = QtWidgets.QTableWidgetItem(s.name)
            name.setToolTip(tr(hilfe["Name"]))
            t.setItem(z, 0, name)
            felder = (("laenge", 0.0, 1e5, 3, " mm", "Länge"), ("laenge_oben", -100.0, 100.0, 3, " mm", "oben"),
                      ("laenge_unten", -100.0, 100.0, 3, " mm", "unten"), ("winkel", -360.0, 360.0, 2, " °", "Winkel"),
                      ("winkel_oben", -45.0, 45.0, 3, " °", "oben °"), ("winkel_unten", -45.0, 45.0, 3, " °", "unten °"))
            for s_nr, (attr, lo, hi, dez, einheit, spalte) in enumerate(felder, start=1):
                t.setCellWidget(z, s_nr, self._feld(s, attr, lo, hi, dez, einheit, hilfe[spalte]))
            art = QtWidgets.QComboBox()
            for schluessel, text in tk.VERTEILUNG.items():
                if schluessel != "messwerte":
                    art.addItem(tr(text), schluessel)
            art.setCurrentIndex(max(0, art.findData(s.verteilung)))
            art.setToolTip(tr(hilfe["Verteilung"]))
            art.currentIndexChanged.connect(lambda _i, s=s, art=art: (setattr(s, "verteilung", art.currentData()),
                                                                      self._rechne()))
            t.setCellWidget(z, SP_VERTEILUNG, art)
            stoff = werkstoff_feld(s.werkstoff, tr("wie Kette"), tr(hilfe["Werkstoff"]))
            stoff.currentTextChanged.connect(lambda _t, s=s, f=stoff: (setattr(s, "werkstoff", werkstoff_wert(f)),
                                                                       self._rechne()))
            t.setCellWidget(z, SP_WERKSTOFF, stoff)
        spalten_anpassen(t)
        t.blockSignals(False)
        self.waerme.setze(self.kette.werkstoff, self.kette.temperaturen)
        self.bewertung.setze(self.kette.anforderung, self.kette.freigabe)
        self.schluss.blockSignals(True)
        self.schluss.setCurrentIndex(max(0, self.schluss.findData(self.kette.schluss)))
        self.schluss.blockSignals(False)
        self._rechne()

    # --- Ergebnis ---

    def ergebnisse(self, kette: k2.Kette2D | None = None) -> dict:
        """Nennwert, linear (Worst Case, RSS) und nichtlinear (Monte Carlo 99,73 %) der Schlussgroesse; mit
        Grenztemperaturen dazu "temperaturen": [(T, Ergebnis bei T)]."""
        k = kette or self.kette
        if not k.segmente:
            return {}
        e = tk.berechne(k2.als_glieder(k), proben=20_000, anforderung=k.anforderung)
        mc = k2.monte_carlo(k, 20_000)
        out = {"nenn": k2.schlussgroesse(k), "wc": (e.wc_min, e.wc_max), "rss": (e.mitte - e.rss, e.mitte + e.rss),
               "mc": tuple(float(x) for x in np.quantile(mc, [0.00135, 0.99865])),
               "empfindlichkeit": k2.empfindlichkeiten(k), "statistisch": e.statistisch}
        out["ampel"] = tk.bewertung_nichtlinear(e, k.anforderung, mc)
        if kette is None and k.temperaturen:
            out["temperaturen"] = [(t, self.ergebnisse(k2.bei_temperatur(k, t))) for t in k.temperaturen]
        return out

    def _rechne(self):
        self.skizze.kette = self.kette
        self.skizze.update()
        self.in_kette.setEnabled(bool(self.kette.segmente))
        r = self.ergebnisse()
        self.bewertung.zeige(*(r.get("ampel") or ("", "")))
        if not r:
            self.ergebnis.setText(tr("Noch keine Segmente – „＋ Segment“ oder eine Vorlage wählen."))
            return
        einheit = "°" if self.kette.schluss == "winkel" else " mm"
        z = lambda a, b: f"{a:.4f} … {b:.4f}{einheit}"  # noqa: E731
        groesste = sorted(r["empfindlichkeit"].items(), key=lambda kv: -abs(kv[1]))[:3]
        teile = ", ".join(f"{self.kette.segmente[i].name} ({tr('Winkel') if g == 'winkel' else tr('Länge')}) "
                          f"{d:+.3g}" for (i, g), d in groesste)
        self.ergebnis.setText(
            f"<b>{tr('Schlussgröße')}</b> {r['nenn']:.4f}{einheit} &nbsp;·&nbsp; "
            f"{tr('Worst Case')} {z(*r['wc'])} &nbsp;·&nbsp; RSS {z(*r['rss'])} &nbsp;·&nbsp; "
            f"{tr('Monte Carlo nichtlinear')} {z(*r['mc'])}<br>"
            f"{tr('Größte Empfindlichkeiten')}: {teile}" + "".join(
                f"<br><b>{tr('Bei {} °C').format(f'{t:g}')}</b> {w['nenn']:.4f}{einheit} &nbsp;·&nbsp; "
                f"{tr('Worst Case')} {z(*w['wc'])} &nbsp;·&nbsp; {tr('Monte Carlo nichtlinear')} {z(*w['mc'])}"
                for t, w in r.get("temperaturen", [])))
