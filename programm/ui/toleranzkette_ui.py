"""Fenster Toleranzkette: Glieder aus der PMI-Liste oder der 3D-Auswahl, Verteilung und Cp je Glied, Ergebnis
arithmetisch, statistisch und Monte Carlo (das anwendbare fett), Histogramm, Planspiel mit Vergleich zum Ist."""

from __future__ import annotations

import copy
import html

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import toleranzkette as tk

def _z(x: float, vorzeichen: str = "") -> str:
    """Zahl mit vier Stellen, ohne "-0.0000"."""
    x = round(float(x), 4) + 0.0
    return f"{x:{vorzeichen}.4f}"


SP_RICHTUNG, SP_NENN, SP_HOCH, SP_MIN, SP_TOL, SP_VERTEILUNG, SP_CP, SP_VERSATZ, SP_ANTEIL = 1, 2, 3, 4, 5, 7, 8, 9, 10
PLAN_FARBE = QtGui.QColor(255, 196, 0, 40)  # Tabelle im Planspiel leicht getoent


class AnteilBalken(QtWidgets.QStyledItemDelegate):
    """Anteil als kleiner Balken mit Prozentzahl (Wert 0..1 in UserRole)."""

    def paint(self, maler, option, index):
        super().paint(maler, option, index)
        wert = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if wert is None:
            return
        r = option.rect.adjusted(3, 5, -42, -5)
        maler.save()
        maler.setPen(QtCore.Qt.PenStyle.NoPen)
        maler.setBrush(option.palette.color(QtGui.QPalette.ColorRole.Mid))
        maler.drawRoundedRect(r, 2, 2)
        maler.setBrush(option.palette.color(QtGui.QPalette.ColorRole.Highlight))
        maler.drawRoundedRect(QtCore.QRect(r.left(), r.top(), int(r.width() * min(1.0, wert)), r.height()), 2, 2)
        maler.setPen(option.palette.color(QtGui.QPalette.ColorRole.Text))
        maler.drawText(option.rect.adjusted(0, 0, -4, 0), QtCore.Qt.AlignmentFlag.AlignRight |
                       QtCore.Qt.AlignmentFlag.AlignVCenter, f"{wert:.0%}")
        maler.restore()

    def sizeHint(self, option, index):
        return QtCore.QSize(110, super().sizeHint(option, index).height())


class Histogramm(QtWidgets.QWidget):
    """Monte-Carlo-Werte des Schlussmasses als Histogramm; Linien: Worst Case (gestrichelt), Anforderung (rot).
    Im Planspiel das Ist als Umriss dahinter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.e = self.ist = None
        self.anforderung = None

    def zeige(self, e, ist=None, anforderung=None):
        self.e, self.ist, self.anforderung = e, ist, anforderung
        self.update()

    def _bereich(self):
        werte = [x for e in (self.e, self.ist) if e is not None for x in (e.wc_min, e.wc_max)]
        if self.anforderung:
            werte += list(self.anforderung)
        lo, hi = min(werte), max(werte)
        rand = (hi - lo) * 0.05 or 0.01
        return lo - rand, hi + rand

    def paintEvent(self, _ev):
        import numpy as np
        if self.e is None or self.e.proben is None or not len(self.e.proben):
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height() - 14
        lo, hi = self._bereich()
        x = lambda v: (v - lo) / (hi - lo) * w  # noqa: E731
        kanten = np.linspace(lo, hi, 81)
        pal = self.palette()
        for e, fuellen in ((self.ist, False), (self.e, True)):
            if e is None or e.proben is None:
                continue
            n, _ = np.histogram(e.proben, kanten)
            hoch = n.max() or 1
            weg = QtGui.QPainterPath(QtCore.QPointF(0, h))
            for k, c in enumerate(n):
                y = h - c / hoch * (h - 4)
                weg.lineTo(x(kanten[k]), y)
                weg.lineTo(x(kanten[k + 1]), y)
            weg.lineTo(w, h)
            farbe = pal.color(QtGui.QPalette.ColorRole.Highlight)
            if fuellen:
                farbe.setAlpha(120)
                p.fillPath(weg, farbe)
            else:
                p.setPen(QtGui.QPen(pal.color(QtGui.QPalette.ColorRole.Mid), 1.2))
                p.drawPath(weg)
        p.setPen(QtGui.QPen(pal.color(QtGui.QPalette.ColorRole.Text), 1, QtCore.Qt.PenStyle.DashLine))
        for v in (self.e.wc_min, self.e.wc_max):
            p.drawLine(QtCore.QPointF(x(v), 0), QtCore.QPointF(x(v), h))
        if self.anforderung:
            p.setPen(QtGui.QPen(QtGui.QColor("#c0392b"), 1.6))
            for v in self.anforderung:
                p.drawLine(QtCore.QPointF(x(v), 0), QtCore.QPointF(x(v), h))
        p.setPen(pal.color(QtGui.QPalette.ColorRole.PlaceholderText))
        schrift = p.font()
        schrift.setPointSizeF(schrift.pointSizeF() * 0.85)
        p.setFont(schrift)
        p.drawText(QtCore.QRectF(0, h, w, 14), QtCore.Qt.AlignmentFlag.AlignLeft, f"{lo:.3f}")
        p.drawText(QtCore.QRectF(0, h, w, 14), QtCore.Qt.AlignmentFlag.AlignRight, f"{hi:.3f}")
        p.drawText(QtCore.QRectF(0, h, w, 14), QtCore.Qt.AlignmentFlag.AlignHCenter,
                   tr("Monte Carlo · gestrichelt: Worst Case · rot: Anforderung"))
        p.end()


class ToleranzketteFenster(QtWidgets.QDialog):
    flaechen_zeigen = QtCore.Signal(set)  # Flaechen der gewaehlten Glieder (aus der 3D-Auswahl)

    ERGEBNIS_ZEILEN = (("wc", "Arithmetisch (Worst Case)"), ("rss", "Statistisch (RSS, ±3σ)"),
                       ("mc", "Monte Carlo (99,73 %)"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Toleranzkette"))
        self.resize(1000, 640)
        self.glieder: list[tk.Glied] = []
        self._ist: list[tk.Glied] | None = None  # Planspiel: Kopie der echten Kette
        self._ist_cp = 1.0
        self.e_ist = None
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Maße in der PMI-Liste wählen und übernehmen, oder Flächen im Modell in "
                                      "Kettenreihenfolge wählen (Strg/⌘) und „Aus 3D-Auswahl“. Richtung + vergrößert, − "
                                      "verkleinert das Schlussmaß (Doppelklick kehrt um). Verteilung je Glied nach "
                                      "Fertigungsart."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        lay.addLayout(self._baue_eingaben())
        self.plan_leiste = self._baue_planleiste()
        lay.addWidget(self.plan_leiste)
        self.tabelle = QtWidgets.QTableWidget(0, len(tk.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in tk.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.itemSelectionChanged.connect(self._zeige_flaechen)
        self.tabelle.cellDoubleClicked.connect(self._doppelklick)
        self.tabelle.itemChanged.connect(self._wert_geaendert)
        self.tabelle.setItemDelegateForColumn(SP_ANTEIL, AnteilBalken(self.tabelle))
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        kopf.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)  # lange Namen ohne Querlauf
        lay.addWidget(self.tabelle, 3)
        lay.addLayout(self._baue_anforderung())
        self.ergebnisse = QtWidgets.QTableWidget(0, 0)
        self.ergebnisse.verticalHeader().setVisible(False)
        self.ergebnisse.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ergebnisse.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.ergebnisse.horizontalHeader().setStretchLastSection(False)
        lay.addWidget(self.ergebnisse)
        self.ergebnis = QtWidgets.QLabel("")  # Schlussmass und Begruendung des anwendbaren Verfahrens
        self.ergebnis.setWordWrap(True)
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lay.addWidget(self.ergebnis)
        self.histogramm = Histogramm()
        lay.addWidget(self.histogramm, 1)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        self.export = knoepfe.addButton(tr("Als CSV speichern …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.pdf = knoepfe.addButton(tr("PDF-Bericht …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.export.clicked.connect(lambda: self.speichere())
        self._fuelle()

    # --- Aufbau ---

    def _baue_eingaben(self):
        reihe = QtWidgets.QHBoxLayout()
        self.plus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (+)"))
        self.minus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (−)"))
        self.auswahl = QtWidgets.QPushButton(tr("＋ Aus 3D-Auswahl"))
        self.auswahl.setToolTip(tr("Flächen in Kettenreihenfolge: je zwei aufeinanderfolgende bilden ein Glied"))
        self.drehen = QtWidgets.QPushButton(tr("Richtung umkehren"))
        self.drehen.setToolTip(tr("Gewählte Glieder umkehren (auch per Doppelklick auf die Richtung)"))
        self.weg = QtWidgets.QPushButton(tr("Entfernen"))
        for k in (self.plus, self.minus, self.auswahl, self.drehen, self.weg):
            reihe.addWidget(k)
        self.drehen.clicked.connect(self._drehen)
        self.weg.clicked.connect(self._entfernen)
        self.lage = QtWidgets.QCheckBox(tr("Lagetoleranzen"))
        self.lage.setChecked(True)
        self.lage.setToolTip(tr("Position, Symmetrie, Koaxialität und Profil mit Bezug an der ersten und letzten Fläche "
                                "als eigene Glieder (Zwischenflächen heben sich auf)"))
        reihe.addWidget(self.lage)
        reihe.addStretch(1)
        reihe.addWidget(QtWidgets.QLabel(tr("Prozessfähigkeit Cp")))
        self.cp = QtWidgets.QDoubleSpinBox()
        self.cp.setRange(0.5, 3.0)
        self.cp.setSingleStep(0.1)
        self.cp.setDecimals(2)
        self.cp.setValue(1.0)
        self.cp.setToolTip(tr("Cp der Kette für normalverteilte Glieder ohne eigenen Wert: σ = Toleranz / (6 · Cp); "
                              "1,0 = ±3σ, 1,33 = ±4σ"))
        self.cp.valueChanged.connect(self._rechne)
        reihe.addWidget(self.cp)
        self.plan_knopf = QtWidgets.QPushButton(tr("Planspiel …"))
        self.plan_knopf.setToolTip(tr("Werte vorübergehend ändern und mit dem Ist vergleichen, ohne die Kette zu "
                                      "verändern"))
        self.plan_knopf.clicked.connect(self.starte_planspiel)
        reihe.addWidget(self.plan_knopf)
        return reihe

    def _baue_planleiste(self) -> QtWidgets.QFrame:
        leiste = QtWidgets.QFrame()
        leiste.setObjectName("planspiel")
        leiste.setStyleSheet("#planspiel { background: rgba(255, 196, 0, 0.18); border-radius: 4px; }")
        reihe = QtWidgets.QHBoxLayout(leiste)
        reihe.setContentsMargins(8, 4, 8, 4)
        text = QtWidgets.QLabel(tr("<b>Planspiel</b> – Werte per Doppelklick ändern; geänderte Zellen sind fett, "
                                   "das Ergebnis steht neben dem Ist. Die Kette selbst bleibt unverändert."))
        text.setWordWrap(True)
        reihe.addWidget(text, 1)
        self.uebernehmen = QtWidgets.QPushButton(tr("Übernehmen"))
        self.uebernehmen.setToolTip(tr("Planspiel wird zur Kette"))
        self.verwerfen = QtWidgets.QPushButton(tr("Verwerfen"))
        self.verwerfen.setToolTip(tr("Zurück zum Ist"))
        self.uebernehmen.clicked.connect(lambda: self.beende_planspiel(True))
        self.verwerfen.clicked.connect(lambda: self.beende_planspiel(False))
        reihe.addWidget(self.uebernehmen)
        reihe.addWidget(self.verwerfen)
        leiste.hide()
        return leiste

    def _baue_anforderung(self):
        reihe = QtWidgets.QHBoxLayout()
        self.anforderung = QtWidgets.QCheckBox(tr("Anforderung an das Schlussmaß"))
        self.anforderung.setToolTip(tr("Grenzen des Schlussmaßes (z. B. Spalt): Cp, Cpk und Anteil außerhalb"))
        self.unten, self.oben = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for k in (self.unten, self.oben):
            k.setRange(-100000.0, 100000.0)
            k.setDecimals(3)
            k.setSuffix(" mm")
            k.setEnabled(False)
            k.valueChanged.connect(self._rechne)
        self.anforderung.toggled.connect(self._anforderung_an)
        reihe.addWidget(self.anforderung)
        reihe.addWidget(self.unten)
        reihe.addWidget(QtWidgets.QLabel("…"))
        reihe.addWidget(self.oben)
        reihe.addStretch(1)
        return reihe

    # --- Glieder ---

    @property
    def im_planspiel(self) -> bool:
        return self._ist is not None

    def leeren(self):
        """Neues Modell: die Glieder verweisen auf PMI des alten Modells."""
        self._ist = None
        self.plan_leiste.hide()
        self.glieder = []
        self._fuelle()

    def ergaenze(self, glieder: list):
        """Glieder aus der 3D-Auswahl anhaengen."""
        self.glieder.extend(glieder)
        self._fuelle()

    def uebernimm(self, pmi_liste: list, richtung: int = 1) -> int:
        n = 0
        for p in pmi_liste:
            g = tk.glied_von_pmi(p, richtung)
            if g is not None:
                self.glieder.append(g)
                n += 1
        self._fuelle()
        return n

    def _drehen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}):
            self.glieder[z].richtung *= -1
        self._fuelle()

    def _doppelklick(self, zeile: int, spalte: int):
        if spalte == SP_RICHTUNG and zeile < len(self.glieder):
            self.glieder[zeile].richtung *= -1
            self._fuelle()

    def _entfernen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}, reverse=True):
            del self.glieder[z]
            if self.im_planspiel and z < len(self._ist):
                del self._ist[z]  # Zeilen von Ist und Planspiel bleiben einander zugeordnet
        self._fuelle()

    def _zeige_flaechen(self):
        zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
        self.flaechen_zeigen.emit({f for z in zeilen if z < len(self.glieder) for f in self.glieder[z].flaechen})

    # --- Planspiel ---

    def starte_planspiel(self):
        if self.im_planspiel or not self.glieder:
            return
        self._ist = copy.deepcopy(self.glieder)
        self._ist_cp = self.cp.value()
        self.plan_leiste.show()
        self._fuelle()

    def beende_planspiel(self, uebernehmen: bool):
        if not self.im_planspiel:
            return
        if not uebernehmen:
            self.glieder = self._ist
            self.cp.blockSignals(True)
            self.cp.setValue(self._ist_cp)
            self.cp.blockSignals(False)
        self._ist = None
        self.e_ist = None
        self.plan_leiste.hide()
        self._fuelle()

    def _ist_glied(self, z: int):
        return self._ist[z] if self.im_planspiel and z < len(self._ist) else None

    def _wert_geaendert(self, it):
        """Planspiel: Nennmass, Grenzen oder Toleranz in der Tabelle geaendert (Toleranz: symmetrisch zur Mitte)."""
        z, s = it.row(), it.column()
        if not self.im_planspiel or z >= len(self.glieder) or s not in (SP_NENN, SP_HOCH, SP_MIN, SP_TOL):
            return
        try:
            wert = float(it.text().replace(",", ".").replace("±", ""))
        except ValueError:
            QtCore.QTimer.singleShot(0, self._fuelle)  # alten Wert wieder zeigen
            return
        g = self.glieder[z]
        if s == SP_NENN:
            d = wert - g.nenn
            g.nenn, g.hoechst, g.mindest = wert, g.hoechst + d, g.mindest + d
        elif s == SP_HOCH:
            g.hoechst = max(wert, g.mindest)
        elif s == SP_MIN:
            g.mindest = min(wert, g.hoechst)
        else:
            m, h = g.mitte, abs(wert) / 2
            g.hoechst, g.mindest = m + h, m - h
        self._rechne()
        QtCore.QTimer.singleShot(0, self._fuelle)  # Markierung; nicht waehrend des Editierens die Zellen ersetzen

    # --- Anzeige ---

    def _zelle(self, z: int, s: int, text: str, ist_text: str | None, aenderbar: bool):
        it = QtWidgets.QTableWidgetItem(text)
        if not aenderbar:
            it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        if self.im_planspiel:
            it.setBackground(PLAN_FARBE)
            if ist_text is not None and ist_text != text:
                schrift = it.font()
                schrift.setBold(True)
                it.setFont(schrift)
                it.setToolTip(tr("Ist: {}").format(ist_text))
        self.tabelle.setItem(z, s, it)

    @staticmethod
    def _texte(g) -> tuple[str, ...]:
        return (g.name, "+" if g.richtung > 0 else "−", "–" if g.quelle == "lage" else f"{g.nenn:.4g}",
                f"{g.hoechst:.4g}", f"{g.mindest:.4g}", f"{g.toleranz:.4g}", tr(tk.QUELLE[g.quelle]))

    def _fuelle(self):
        t = self.tabelle
        t.blockSignals(True)
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked if self.im_planspiel
                          else QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setRowCount(len(self.glieder))
        for z, g in enumerate(self.glieder):
            ist = self._ist_glied(z)
            vorher = None if ist is None else self._texte(ist)
            for s, w in enumerate(self._texte(g)):
                aenderbar = s in (SP_HOCH, SP_MIN, SP_TOL) or (s == SP_NENN and g.quelle != "lage")
                self._zelle(z, s, w, None if vorher is None else vorher[s], aenderbar)
            t.item(z, SP_RICHTUNG).setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if vorher is None or vorher[SP_RICHTUNG] == self._texte(g)[SP_RICHTUNG]:
                t.item(z, SP_RICHTUNG).setToolTip(tr("Doppelklick kehrt die Richtung um"))
            if g.quelle == "ohne":
                t.item(z, 6).setForeground(QtGui.QColor("#c0392b"))
            self._widgets(z, g, ist)
            self._zelle(z, SP_ANTEIL, "", None, False)
        t.blockSignals(False)
        self._rechne()

    def _widgets(self, z: int, g, ist):
        """Verteilung, Cp bzw. Trapezform und Versatz als Eingabefelder; im Planspiel geaenderte fett."""
        t = self.tabelle
        art = QtWidgets.QComboBox()
        for schluessel, text in tk.VERTEILUNG.items():
            art.addItem(tr(text), schluessel)
        art.setCurrentIndex(max(0, art.findData(g.verteilung)))
        art.setToolTip(tr("Serie: normal (Toleranz = ±3σ · Cp); Kleinserie: Dreieck; Einzelteil: gleichverteilt; "
                          "Trapez: dazwischen"))
        art.currentIndexChanged.connect(lambda _i, g=g, a=art: self._setze(g, "verteilung", a.currentData()))
        t.setCellWidget(z, SP_VERTEILUNG, art)
        if g.verteilung == "trapez":
            feld = QtWidgets.QDoubleSpinBox()
            feld.setRange(0.0, 1.0)
            feld.setSingleStep(0.1)
            feld.setDecimals(2)
            feld.setPrefix("a = ")
            feld.setToolTip(tr("Flacher Anteil des Trapezes: 0 = Dreieck, 1 = Rechteck"))
            feld.setValue(g.form)
            feld.valueChanged.connect(lambda w, g=g: self._setze(g, "form", w))
            name = "form"
        else:
            feld = QtWidgets.QDoubleSpinBox()
            feld.setRange(0.0, 3.0)
            feld.setSingleStep(0.1)
            feld.setDecimals(2)
            feld.setSpecialValueText(tr("Kette"))  # 0: Cp der Kette
            feld.setValue(g.cp or 0.0)
            feld.setEnabled(g.verteilung == "normal")
            feld.valueChanged.connect(lambda w, g=g: self._setze(g, "cp", w or None))
            name = "cp"
        t.setCellWidget(z, SP_CP, feld)
        versatz = QtWidgets.QDoubleSpinBox()
        versatz.setRange(-1000.0, 1000.0)
        versatz.setDecimals(4)
        versatz.setSingleStep(0.01)
        versatz.setToolTip(tr("Mittenversatz des Prozesses gegen die Toleranzmitte (mm): Cpk < Cp"))
        versatz.setValue(g.versatz)
        versatz.valueChanged.connect(lambda w, g=g: self._setze(g, "versatz", w))
        t.setCellWidget(z, SP_VERSATZ, versatz)
        if ist is not None:
            for w, feldname in ((art, "verteilung"), (feld, name), (versatz, "versatz")):
                if getattr(g, feldname) != getattr(ist, feldname):
                    schrift = w.font()
                    schrift.setBold(True)
                    w.setFont(schrift)
                    w.setToolTip(tr("Ist: {}").format(getattr(ist, feldname)))

    def _setze(self, g, feld: str, wert):
        setattr(g, feld, wert)
        self._rechne()
        if feld == "verteilung" or self.im_planspiel:
            QtCore.QTimer.singleShot(0, self._fuelle)  # Eingabefelder neu aufbauen (Cp/Form, Markierung)

    def _anforderung_an(self, an: bool):
        for k in (self.unten, self.oben):
            k.setEnabled(an)
        if an and self.glieder and self.unten.value() == self.oben.value() == 0:
            for k, w in ((self.unten, self.e.wc_min), (self.oben, self.e.wc_max)):  # Vorschlag: Worst Case
                k.blockSignals(True)
                k.setValue(round(w, 3))
                k.blockSignals(False)
        self._rechne()

    def anforderung_werte(self):
        return (self.unten.value(), self.oben.value()) if self.anforderung.isChecked() else None

    def _rechne(self):
        anforderung = self.anforderung_werte()
        self.e = tk.berechne(self.glieder, cp=self.cp.value(), anforderung=anforderung)
        self.e_ist = tk.berechne(self._ist, cp=self._ist_cp, anforderung=anforderung) if self.im_planspiel else None
        for z, anteil in enumerate(self.e.anteile):
            it = self.tabelle.item(z, SP_ANTEIL)
            if it is not None:
                it.setData(QtCore.Qt.ItemDataRole.UserRole, anteil)
        self._zeige_ergebnis()
        self.histogramm.zeige(self.e if self.glieder else None, self.e_ist, anforderung)
        for k in (self.export, self.pdf):
            k.setEnabled(bool(self.glieder))
        self.plan_knopf.setEnabled(bool(self.glieder) and not self.im_planspiel)

    @staticmethod
    def _werte(e, art: str) -> tuple[float, float]:
        if art == "wc":
            return e.wc_min, e.wc_max
        if art == "rss":
            return e.mitte - e.rss, e.mitte + e.rss
        return e.mc_min, e.mc_max

    def ergebnis_zeilen(self) -> tuple[list[str], list[tuple[list[str], bool]]]:
        """(Spaltenkoepfe, [(Zellen, fett)]) der Ergebnistabelle, auch fuer den Bericht. Fett: das anwendbare
        Verfahren (statistisch ab genug wirksamen Beitragsleistern, sonst arithmetisch)."""
        e, ist = self.e, self.e_ist
        if ist is None:
            koepfe = [tr("Verfahren"), tr("Minimum"), tr("Maximum"), tr("Breite")]
        else:
            koepfe = [tr("Verfahren"), tr("Ist"), tr("Planspiel"), tr("Δ Breite")]
        zeilen = []
        for art, text in self.ERGEBNIS_ZEILEN:
            fett = (art == "rss" and e.statistisch) or (art == "wc" and not e.statistisch)
            lo, hi = self._werte(e, art)
            name = ("✓ " if fett else "") + tr(text)
            if ist is None:
                zellen = [name, _z(lo), _z(hi), _z(hi - lo)]
            else:
                ilo, ihi = self._werte(ist, art)
                zellen = [name, f"{_z(ilo)} … {_z(ihi)}", f"{_z(lo)} … {_z(hi)}", _z((hi - lo) - (ihi - ilo), "+")]
            zeilen.append((zellen, fett))
        if e.cp is not None:
            for name, wert in (("Cpk", lambda x: f"{x.cpk:.2f}"),
                               (tr("außerhalb (Monte Carlo)"), lambda x: f"{x.mc_ausserhalb * 1e6:.0f} ppm")):
                zellen = [name, "", "", wert(e)] if ist is None else [name, wert(ist), wert(e), ""]
                zeilen.append((zellen, False))
        return koepfe, zeilen

    def _zeige_ergebnis(self):
        t = self.ergebnisse
        if not self.glieder:
            t.setRowCount(0)
            t.setColumnCount(0)
            self.ergebnis.setText(tr("Noch keine Glieder."))
            return
        koepfe, zeilen = self.ergebnis_zeilen()
        t.setColumnCount(len(koepfe))
        t.setHorizontalHeaderLabels(koepfe)
        t.setRowCount(len(zeilen))
        for z, (zellen, fett) in enumerate(zeilen):
            for s, w in enumerate(zellen):
                it = QtWidgets.QTableWidgetItem(w)
                if fett:
                    schrift = it.font()
                    schrift.setBold(True)
                    it.setFont(schrift)
                t.setItem(z, s, it)
        t.resizeColumnsToContents()
        t.setFixedHeight(t.horizontalHeader().sizeHint().height() + sum(t.rowHeight(z) for z in range(t.rowCount()))
                         + 2 * t.frameWidth())
        e = self.e
        text = f"<b>{tr('Schlussmaß')}</b> {_z(e.nenn)} mm &nbsp; · &nbsp; {html.escape(tk.anwendbar_text(e))}"
        if self.e_ist is not None and self.e_ist.statistisch != e.statistisch:
            text += " &nbsp; · &nbsp; " + html.escape(tr("Ist: {}").format(tk.anwendbar_text(self.e_ist)))
        self.ergebnis.setText(text)

    def speichere(self, pfad: str = "") -> str | None:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Toleranzkette speichern"), "toleranzkette.csv",
                                                            "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(tk.als_csv(self.glieder, self.e, self.cp.value()))
        return pfad
