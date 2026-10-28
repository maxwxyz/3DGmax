"""Fenster Toleranzkette: Glieder aus der PMI-Liste oder der 3D-Auswahl, Verteilung und Cp je Glied, Ergebnis
arithmetisch, statistisch und Monte Carlo (das anwendbare fett), Histogramm, Planspiel mit Vergleich zum Ist."""

from __future__ import annotations

import copy
import html

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import toleranzkette as tk
from .fluss import FlussLayout
from .tabellen import AENDERBAR_FARBE, leer_hinweis  # getoent: Zellen, die man aendern kann


def _z(x: float, vorzeichen: str = "") -> str:
    """Zahl mit vier Stellen, ohne "-0.0000"."""
    x = round(float(x), 4) + 0.0
    return f"{x:{vorzeichen}.4f}"


SP_RICHTUNG, SP_NENN, SP_HOCH, SP_MIN, SP_TOL, SP_VERTEILUNG, SP_CP, SP_VERSATZ, SP_FAKTOR, SP_ANTEIL = \
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11
SP_STREUUNG = len(tk.SPALTEN)  # nur im Fenster: Bild der Verteilung des Glieds mit seinen Grenzen
SP_FERTIGUNG = len(tk.SPALTEN) + 1  # nur im Fenster: Fertigungsverfahren (kostenoptimale Verteilung)
# Erklaerung je Spalte der Gliedertabelle (Tooltip im Kopf und in den Zellen)
SPALTEN_HILFE = {
    "Glied": "Name des Glieds (aus der PMI, der 3D-Auswahl oder eigene Angabe); in Klammern Stellglied, fest, "
             "Korrelationsgruppe",
    "Richtung": "+ vergrößert das Schlussmaß, − verkleinert es (Doppelklick kehrt um)",
    "Nennmaß": "Nennmaß des Glieds in mm (Lagetoleranzen: 0, sie wirken nur als Abweichung)",
    "Höchstmaß": "Größtes zulässiges Maß (Nennmaß + oberes Abmaß)",
    "Mindestmaß": "Kleinstes zulässiges Maß (Nennmaß + unteres Abmaß)",
    "Toleranz": "Toleranzbreite T = Höchstmaß − Mindestmaß",
    "Quelle": "Woher die Werte stammen: PMI-Maß, Lagetoleranz, Allgemeintoleranz (ISO 2768/22081), Längenbereich "
              "oder eigene Angabe; rot: ohne Toleranz",
    "Verteilung": "Wie die Istmaße in der Fertigung streuen: Normal (Serie, σ = T/(6·Cp)), Dreieck (Kleinserie), "
                  "Trapez, Gleich (Einzelteil, jeder Wert gleich wahrscheinlich), Betrag 1./2. Art (Form, Position: "
                  "einseitig ab dem Mindestmaß), aus Messwerten",
    "Cp / Form": "Normal: Prozessfähigkeit Cp des Glieds (leer: Cp der Kette); Trapez: Anteil des flachen Teils "
                 "(0 = Dreieck, 1 = Rechteck)",
    "Versatz": "Mittenversatz des Prozesses gegen die Toleranzmitte in mm (ergibt Cpk < Cp)",
    "Faktor": "Empfindlichkeit: wie stark das Glied auf das Schlussmaß wirkt (1 = direkt, z. B. 2 bei einem "
              "Hebel 2:1)",
    "Anteil": "Anteil des Glieds an der Streuung des Schlussmaßes (Varianzanteil) – hier lohnt sich Einengen",
    "Streuung": "Verteilung des Glieds (Monte-Carlo-Werte) zwischen Mindest- und Höchstmaß (rote Linien)",
    "Fertigung": "Fertigungsverfahren des Glieds mit erreichbarem IT-Grad (fein … grob) und Kostenfaktor – Grundlage "
                 "der kostenoptimalen Verteilung; daneben der IT-Grad der jetzigen Toleranz",
}
# Erklaerung je Verfahren der Ergebnistabelle (Tooltip in der ersten Spalte)
VERFAHREN_HILFE = {
    "wc": "Arithmetisch (Worst Case): alle Glieder gleichzeitig an der ungünstigsten Grenze – Schlussmaß = Summe der "
          "Nennmaße, Breite = Summe der Toleranzen. Sicher (100 %), aber bei vielen Gliedern unwirtschaftlich eng. "
          "Gilt, solange weniger als 4 Glieder wirksam zur Streuung beitragen.",
    "rss": "Statistisch (RSS, Root Sum Square): die Streuungen der Glieder addieren sich quadratisch – σ² = Σ "
           "(Faktor · σᵢ)², Ergebnis Mitte ± 3σ (99,73 %). Setzt unabhängige Glieder und genug Beitragsleister "
           "(≥ 4 wirksame) voraus; Bender-Zuschlag oder Mittenverschiebung über die Auswahl oben.",
    "mc": "Monte Carlo: 200 000 Ketten werden aus den Verteilungen der Glieder ausgewürfelt und summiert; das "
          "Ergebnis sind die 0,135-%- und 99,865-%-Quantile. Erfasst schiefe Verteilungen, Korrelation und "
          "Messwerte ohne Annahme einer Normalverteilung.",
    "temp": "Das anwendbare Verfahren bei der Grenztemperatur: jedes Glied dehnt sich um ΔL = α · L · (T − 20 °C) "
            "mit dem Werkstoff seines Bauteils",
    "cpk": "Cpk: Abstand der Mitte zur näheren Anforderungsgrenze in Vielfachen von 3σ (≥ 1,33 üblich gefordert)",
    "aus": "Anteil der Monte-Carlo-Ketten außerhalb der Anforderung (ppm = Teile pro Million)",
}
METHODEN = (("rss", "RSS", "Varianzen addieren, Schlussmaß ±3σ"),
            ("bender", "RSS × Bender-Faktor", "Zuschlag auf das RSS (Bender 1962: 1,5) für zu optimistisch angegebene "
                                               "Toleranzen"),
            ("verschiebung", "Mittenverschiebung", "Je Glied darf die Mitte um den Anteil m der halben Toleranz wandern "
                                                   "(arithmetisch), der Rest streut statistisch"))
PLAN_FARBE = QtGui.QColor(255, 196, 0, 40)  # Tabelle im Planspiel leicht getoent


def _paar(*widgets) -> QtWidgets.QWidget:
    """Zusammengehoerige Elemente, die im Fliesslayout nicht getrennt umbrechen (z. B. Beschriftung und Feld)."""
    w = QtWidgets.QWidget()
    lay = QtWidgets.QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for x in widgets:
        lay.addWidget(x)
    return w




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


def streuung(g, cp: float, klassen: int = 24) -> tuple:
    """Bild der Verteilung eines Glieds: (relative Hoehen je Klasse, Bereich lo/hi, Mindest-, Hoechstmass); feste
    Zufallszahlen, damit das Bild beim Neuzeichnen nicht zittert."""
    import numpy as np
    werte = g.ziehe(np.random.default_rng(7), 4000, cp)
    rand = 0.2 * (g.toleranz or 1e-3)
    lo, hi = min(g.mindest - rand, float(werte.min())), max(g.hoechst + rand, float(werte.max()))
    n, _ = np.histogram(werte, np.linspace(lo, hi, klassen + 1))
    return tuple((n / (n.max() or 1)).tolist()), lo, hi, g.mindest, g.hoechst


class StreuungsBild(QtWidgets.QStyledItemDelegate):
    """Kleines Histogramm des Glieds mit Mindest- und Hoechstmass (rot) in der Zelle."""

    def paint(self, maler, option, index):
        super().paint(maler, option, index)
        daten = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if not daten:
            return
        hoehen, lo, hi, mindest, hoechst = daten
        r = option.rect.adjusted(6, 4, -6, -4)
        breite = r.width() / len(hoehen)
        farbe = option.palette.color(QtGui.QPalette.ColorRole.Highlight)
        farbe.setAlpha(150)
        maler.save()
        for k, v in enumerate(hoehen):
            h = v * r.height()
            maler.fillRect(QtCore.QRectF(r.left() + k * breite, r.bottom() - h, breite, h), farbe)
        maler.setPen(QtGui.QPen(QtGui.QColor("#c0392b"), 1.4))
        for v in (mindest, hoechst):
            x = r.left() + (v - lo) / ((hi - lo) or 1) * r.width()
            maler.drawLine(QtCore.QPointF(x, r.top()), QtCore.QPointF(x, r.bottom()))
        maler.restore()

    def sizeHint(self, option, index):
        return QtCore.QSize(110, 24)


class Histogramm(QtWidgets.QWidget):
    """Schlussmass nach dem gewaehlten Verfahren: Worst Case als Band (alle Werte darin moeglich, keine Verteilung),
    statistisch als Normalverteilung (Mitte, halbe Breite = 3 sigma), Monte Carlo als Histogramm; "alle" ueberlagert
    die drei. Linien: Worst Case (gestrichelt), Anforderung (rot, ziehbar: grenze_gezogen). Im Planspiel das Ist als
    Umriss dahinter (Monte Carlo). Maus: Wert und Anteil darunter/darueber nach dem gezeigten Verfahren."""
    NAMEN = {"wc": "Worst Case", "rss": "Statistisch", "mc": "Monte Carlo", "alle": "Alle überlagert"}
    grenze_gezogen = QtCore.Signal(int, float)  # 0 untere, 1 obere Grenze; neuer Wert in mm

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 100)  # wird bei kleinem Fenster einfach kleiner
        self.setMouseTracking(True)
        self.e = self.ist = None
        self.anforderung = None
        self.art, self.halb = "mc", 0.0  # gezeigtes Verfahren, halbe statistische Breite
        self._maus = None  # x-Position der Maus (Pixel) fuer die Anzeige
        self._ziehen = None  # Nummer der gezogenen Grenze

    def zeige(self, e, ist=None, anforderung=None, art: str = "mc", halb: float | None = None):
        """art: "wc", "rss", "mc" oder "alle"; halb: halbe statistische Breite (Standard: RSS)."""
        self.e, self.ist, self.anforderung, self.art = e, ist, anforderung, art
        self.halb = halb if halb is not None else getattr(e, "rss", 0.0)  # Messgroessen im Zusammenbau: ohne RSS
        self.update()

    def wert_bei(self, px: float) -> float:
        lo, hi = self._bereich()
        return lo + px / max(self.width(), 1) * (hi - lo)

    def _px(self, wert: float) -> float:
        lo, hi = self._bereich()
        return (wert - lo) / (hi - lo) * self.width()

    def anteil_unter(self, wert: float) -> float | None:
        """Anteil kleiner als der Wert (0..1): statistisch aus der Normalverteilung, sonst aus den Monte-Carlo-Proben;
        None beim Worst Case (dort gibt es keine Verteilung)."""
        import math
        import numpy as np
        if self.e is None or self.art == "wc":
            return None
        if self.art == "rss":
            s = self.halb / 3 or 1e-12
            return 0.5 * (1 + math.erf((wert - self.e.mitte) / (s * math.sqrt(2))))
        if self.e.proben is None or not len(self.e.proben):
            return None
        return float(np.mean(self.e.proben < wert))

    def mousePressEvent(self, ev):
        if self.e is None or not self.anforderung:
            return
        x = ev.position().x()
        nah = min(range(2), key=lambda i: abs(self._px(self.anforderung[i]) - x))
        if abs(self._px(self.anforderung[nah]) - x) <= 6:
            self._ziehen = nah

    def mouseMoveEvent(self, ev):
        self._maus = ev.position().x()
        if self._ziehen is not None and self.anforderung:
            self.grenze_gezogen.emit(self._ziehen, round(self.wert_bei(self._maus), 4))
        elif self.anforderung and self.e is not None:
            nah = any(abs(self._px(v) - self._maus) <= 6 for v in self.anforderung)
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor if nah else QtCore.Qt.CursorShape.ArrowCursor)
        self.update()

    def mouseReleaseEvent(self, _ev):
        self._ziehen = None

    def leaveEvent(self, _ev):
        self._maus = None
        self.update()

    def _bereich(self):
        werte = [x for e in (self.e, self.ist) if e is not None for x in (e.wc_min, e.wc_max)]
        if self.anforderung:
            werte += list(self.anforderung)
        lo, hi = min(werte), max(werte)
        rand = (hi - lo) * 0.05 or 0.01
        return lo - rand, hi + rand

    def _dichten(self, kanten):
        """Dichten je Verfahren auf den Klassen (gleicher Massstab fuer das Ueberlagern): {art: (e, Werte)}."""
        import numpy as np
        breite = kanten[1] - kanten[0]
        mitten = (kanten[:-1] + kanten[1:]) / 2
        aus = {}
        zeigen = ("wc", "rss", "mc") if self.art == "alle" else (self.art,)
        if "mc" in zeigen:
            for name, e in (("ist", self.ist), ("mc", self.e)):
                if e is not None and e.proben is not None and len(e.proben):
                    n, _ = np.histogram(e.proben, kanten)
                    aus[name] = n / (len(e.proben) * breite)
        if "rss" in zeigen and self.halb > 0:
            s = self.halb / 3
            aus["rss"] = np.exp(-0.5 * ((mitten - self.e.mitte) / s) ** 2) / (s * np.sqrt(2 * np.pi))
        if "wc" in zeigen and self.e.wc_max > self.e.wc_min:
            aus["wc"] = np.where((mitten >= self.e.wc_min) & (mitten <= self.e.wc_max),
                                 1.0 / (self.e.wc_max - self.e.wc_min), 0.0)
        return aus

    def paintEvent(self, _ev):
        import numpy as np
        if self.e is None:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height() - 14
        lo, hi = self._bereich()
        x = lambda v: (v - lo) / (hi - lo) * w  # noqa: E731
        kanten = np.linspace(lo, hi, 81)
        pal = self.palette()
        dichten = self._dichten(kanten)
        hoch = max((float(d.max()) for d in dichten.values()), default=0.0) or 1.0
        if self.art != "alle" and "wc" in dichten:  # Worst Case allein: Band ueber die volle Hoehe
            hoch = float(dichten["wc"].max()) or 1.0

        def weg(d):
            pfad = QtGui.QPainterPath(QtCore.QPointF(0, h))
            for k, c in enumerate(d):
                y = h - c / hoch * (h - 18)
                pfad.lineTo(x(kanten[k]), y)
                pfad.lineTo(x(kanten[k + 1]), y)
            pfad.lineTo(w, h)
            return pfad
        markiert = pal.color(QtGui.QPalette.ColorRole.Highlight)
        if "wc" in dichten:
            farbe = pal.color(QtGui.QPalette.ColorRole.Text)
            farbe.setAlpha(28)
            p.fillPath(weg(dichten["wc"]), farbe)
        if "ist" in dichten:
            p.setPen(QtGui.QPen(pal.color(QtGui.QPalette.ColorRole.Mid), 1.2))
            p.drawPath(weg(dichten["ist"]))
        if "mc" in dichten:
            farbe = QtGui.QColor(markiert)
            farbe.setAlpha(120)
            p.fillPath(weg(dichten["mc"]), farbe)
        if "rss" in dichten:
            mitten = (kanten[:-1] + kanten[1:]) / 2
            kurve = QtGui.QPainterPath()
            for k, c in enumerate(dichten["rss"]):
                punkt = QtCore.QPointF(x(mitten[k]), h - c / hoch * (h - 18))
                kurve.moveTo(punkt) if k == 0 else kurve.lineTo(punkt)
            if self.art == "rss":
                flaeche = QtGui.QPainterPath(kurve)
                flaeche.lineTo(x(mitten[-1]), h)
                flaeche.lineTo(x(mitten[0]), h)
                farbe = QtGui.QColor(markiert)
                farbe.setAlpha(70)
                p.fillPath(flaeche, farbe)
            p.setPen(QtGui.QPen(QtGui.QColor("#1f6fd1"), 1.8))
            p.drawPath(kurve)
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
                   tr("{} · gestrichelt: Worst Case · rot: Anforderung (ziehbar)").format(tr(self.NAMEN[self.art])))
        if self._maus is not None and 0 <= self._maus <= w:
            wert = self.wert_bei(self._maus)
            unter = self.anteil_unter(wert)
            p.setPen(QtGui.QPen(pal.color(QtGui.QPalette.ColorRole.Text), 1, QtCore.Qt.PenStyle.DotLine))
            p.drawLine(QtCore.QPointF(self._maus, 0), QtCore.QPointF(self._maus, h))
            text = f"{wert:.4f} mm" if unter is None else tr("{} mm · darunter {} · darüber {}").format(
                f"{wert:.4f}", f"{unter * 100:.2f} %", f"{(1 - unter) * 100:.2f} %")
            breite = p.fontMetrics().horizontalAdvance(text) + 8
            links = min(max(self._maus + 6, 0), w - breite)
            p.setPen(pal.color(QtGui.QPalette.ColorRole.Text))
            p.drawText(QtCore.QRectF(links, 2, breite, 16), QtCore.Qt.AlignmentFlag.AlignLeft, text)
        p.end()


class WerkstoffDialog(QtWidgets.QDialog):
    """Werkstoff und Ausdehnungskoeffizient je Bauteil der Kette (aus der Datei vorbelegt, sonst Bibliothek)."""

    def __init__(self, fenster, parent=None):
        super().__init__(parent)
        from ..kern import werkstoffe as ws
        self.setWindowTitle(tr("Werkstoffe der Kette"))
        self.resize(560, 300)
        self.fenster = fenster
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Werkstoff je Bauteil (aus der Datei, wenn angegeben); α in 10⁻⁶/K wird aus der "
                                      "Bibliothek gesetzt und lässt sich ändern."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        teile = fenster.teile()
        self.tabelle = QtWidgets.QTableWidget(len(teile), 5)
        self.tabelle.setHorizontalHeaderLabels([tr("Bauteil"), tr("Werkstoff"), tr("α (10⁻⁶/K)"),
                                                tr("Temperatur 1"), tr("Temperatur 2")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        for z, teil in enumerate(teile):
            w = fenster.werkstoffe.get(teil, {})
            self.tabelle.setItem(z, 0, QtWidgets.QTableWidgetItem(teil))
            name = QtWidgets.QComboBox()
            name.setEditable(True)
            name.addItems(([w["name"]] if w.get("name") and w["name"] not in ws.BIBLIOTHEK else []) +
                          list(ws.BIBLIOTHEK))
            name.setCurrentText(w.get("name", ""))
            alpha = QtWidgets.QDoubleSpinBox()
            alpha.setRange(0.0, 500.0)
            alpha.setDecimals(1)
            alpha.setSpecialValueText(tr("unbekannt"))
            alpha.setValue(w.get("alpha") or 0.0)
            name.currentTextChanged.connect(lambda t, a=alpha: a.setValue(ws.alpha_fuer(t) or a.value()))
            name.currentTextChanged.connect(lambda t, teil=teil, a=alpha: fenster.setze_werkstoff(teil, t, a.value()))
            alpha.valueChanged.connect(lambda v, teil=teil, n=name: fenster.setze_werkstoff(teil, n.currentText(), v))
            self.tabelle.setCellWidget(z, 1, name)
            self.tabelle.setCellWidget(z, 2, alpha)
            for s, schluessel in ((3, "t1"), (4, "t2")):  # eigene Temperatur des Bauteils, sonst die der Kette
                feld = QtWidgets.QDoubleSpinBox()
                feld.setRange(-274.0, 1000.0)
                feld.setDecimals(1)
                feld.setSuffix(" °C")
                feld.setSpecialValueText(tr("wie Kette"))
                feld.setValue(w[schluessel] if w.get(schluessel) is not None else -274.0)
                feld.setToolTip(tr("Eigene Temperatur dieses Bauteils im Grenzfall (z. B. kühleres Gehäuse); "
                                   "ganz links: Temperatur der Kette"))
                feld.valueChanged.connect(lambda v, teil=teil, k=schluessel: fenster.setze_teiltemperatur(
                    teil, k, None if v <= -273.95 else v))
                self.tabelle.setCellWidget(z, s, feld)
        lay.addWidget(self.tabelle, 1)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)


class MesswerteDialog(QtWidgets.QDialog):
    """Messwerte eines Glieds einfuegen oder aus CSV laden; Vorschau mit n, Mittelwert und Standardabweichung."""

    def __init__(self, glied, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Messwerte – {}").format(glied.name))
        self.glied = glied
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(tr("Messwerte des Maßes (Istmaße in mm) einfügen – eine Zeile oder je Zeile ein "
                                          "Wert; Dezimalkomma geht. Bei mehreren Spalten zählt die gewählte Spalte.")))
        self.text = QtWidgets.QPlainTextEdit("\n".join(f"{w:g}" for w in glied.messwerte))
        lay.addWidget(self.text, 1)
        zeile = QtWidgets.QHBoxLayout()
        laden = QtWidgets.QPushButton(tr("CSV laden …"))
        laden.clicked.connect(self._laden)
        zeile.addWidget(laden)
        zeile.addWidget(QtWidgets.QLabel(tr("Spalte")))
        self.spalte = QtWidgets.QSpinBox()
        self.spalte.setRange(0, 99)
        self.spalte.setSpecialValueText(tr("letzte"))
        zeile.addWidget(self.spalte)
        zeile.addStretch(1)
        lay.addLayout(zeile)
        self.info = QtWidgets.QLabel("")
        lay.addWidget(self.info)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.text.textChanged.connect(self._vorschau)
        self.spalte.valueChanged.connect(self._vorschau)
        self._vorschau()

    def werte(self) -> list[float]:
        return tk.messwerte_aus_text(self.text.toPlainText(), self.spalte.value())

    def _vorschau(self):
        import numpy as np
        w = self.werte()
        if len(w) < 2:
            self.info.setText(tr("{} Werte – mindestens zwei nötig").format(len(w)))
            return
        g = copy.copy(self.glied)
        g.messwerte, g.verteilung = tuple(w), "messwerte"
        cpk = g.cpk()
        self.info.setText(tr("n = {}, Mittelwert {:.4f}, σ = {:.4f}, Cpk {}").format(
            len(w), float(np.mean(w)), g.sigma(), f"{cpk:.2f}" if cpk is not None else "–"))

    def _laden(self, pfad: str = ""):
        pfad = pfad or QtWidgets.QFileDialog.getOpenFileName(self, tr("Messwerte laden"), "",
                                                             tr("CSV/Text (*.csv *.txt);;Alle Dateien (*)"))[0]
        if pfad:
            with open(pfad, encoding="utf-8-sig", errors="replace") as f:
                self.text.setPlainText(f.read())


class ToleranzketteFenster(QtWidgets.QDialog):
    flaechen_zeigen = QtCore.Signal(set)  # Flaechen der gewaehlten Glieder (aus der 3D-Auswahl)
    schluss_aus_auswahl = QtCore.Signal()  # Richtungen aus dem Schlussmass (zwei Flaechen in der 3D-Auswahl)
    oeffnen = QtCore.Signal()  # Kettendatei oeffnen (Hauptfenster laedt ggf. das Modell)
    strecke_zeigen = QtCore.Signal(object)  # Glied beim Ablaufen (Glied) oder None
    bild_zeigen = QtCore.Signal(object)  # ganze Kette im 3D: (Glieder, Text des Schlussmasses, Ist-Glieder) oder None
    schluss_wiggle = QtCore.Signal(bool)  # Schlussflaechen zwischen den Worst-Case-Grenzen pendeln lassen

    ERGEBNIS_ZEILEN = (("wc", "Arithmetisch (Worst Case)"), ("rss", "Statistisch (RSS, ±3σ)"),
                       ("mc", "Monte Carlo (99,73 %)"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Toleranzkette"))
        self.resize(1150, 760)
        self.glieder: list[tk.Glied] = []
        self._ist: list[tk.Glied] | None = None  # Planspiel: Kopie der echten Kette
        self._ist_cp = 1.0
        self.e_ist = None
        self.kosten_hinweis = ""  # Ergebnis der kostenoptimalen Verteilung (im Planspiel)
        self.szenarien: dict[str, tuple[float, list]] = {}  # gemerkte Planspiele: Name -> (Cp, Glieder)
        self.werkstoffe: dict = {}  # Bauteil -> {"name": Werkstoff, "alpha": 1e-6/K}
        self.teil_von = lambda flaechen: ""  # Bauteil zu Flaechen (setzt das Hauptfenster)
        self.e_temp: list = []  # (Temperatur, Ergebnis) bei Waermeausdehnung
        self.modell_pfad = ""
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
        self._szenarien_liste()
        lay.addWidget(self.plan_leiste)
        self.tabelle = QtWidgets.QTableWidget(0, len(tk.SPALTEN) + 2)
        leer_hinweis(self.tabelle, tr("Noch keine Glieder – „＋ Hinzufügen“: aus der PMI-Liste, aus der 3D-Auswahl "
                                      "oder leer zum Eintragen"))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in tk.SPALTEN] + [tr("Streuung"), tr("Fertigung")])
        for i, name in enumerate(tk.SPALTEN + ("Streuung", "Fertigung")):
            self.tabelle.horizontalHeaderItem(i).setToolTip(tr(SPALTEN_HILFE[name]))
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.itemSelectionChanged.connect(self._zeige_flaechen)
        self.tabelle.cellDoubleClicked.connect(self._doppelklick)
        self.tabelle.itemChanged.connect(self._wert_geaendert)
        self.tabelle.setItemDelegateForColumn(SP_ANTEIL, AnteilBalken(self.tabelle))
        self.tabelle.setItemDelegateForColumn(SP_STREUUNG, StreuungsBild(self.tabelle))
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        kopf.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)  # lange Namen ohne Querlauf
        self.tabelle.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._kontextmenue)
        # Glieder oben, Ergebnis unten; der Teiler laesst sich ziehen
        self.teiler = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.teiler.setChildrenCollapsible(False)
        self.teiler.addWidget(self.tabelle)
        unten = self._unten = QtWidgets.QWidget()
        unten_lay = QtWidgets.QVBoxLayout(unten)
        unten_lay.setContentsMargins(0, 0, 0, 0)
        unten_lay.addLayout(self._baue_anforderung())
        unten_lay.addLayout(self._baue_temperatur())
        self.ergebnisse = QtWidgets.QTableWidget(0, 0)
        self.ergebnisse.verticalHeader().setVisible(False)
        self.ergebnisse.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ergebnisse.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.ergebnisse.horizontalHeader().setStretchLastSection(False)
        self.ergebnisse.setToolTip(tr("Zeile anklicken: das Histogramm zeigt nur dieses Verfahren (erneut klicken: wieder "
                                      "alle überlagert)"))
        self.ergebnisse.cellClicked.connect(self._verfahren_gewaehlt)
        self.hist_art = None  # None: das anwendbare Verfahren (✓) zeigen
        # so breit wie der Inhalt, bei kleinem Fenster schmaler mit Querlaufleiste (kein Mindestmass des Fensters)
        self.ergebnisse.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)
        self.ergebnisse.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ergebnisse.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.ergebnisse.horizontalScrollBar().rangeChanged.connect(lambda *_: self._ergebnis_hoehe())
        self.ergebnis = QtWidgets.QLabel("")  # Schlussmass und Begruendung des anwendbaren Verfahrens
        self.ergebnis.setWordWrap(True)
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.histogramm = Histogramm()  # rechts neben der Ergebnistabelle
        self.histogramm.grenze_gezogen.connect(self._grenze_gezogen)
        self.ampel = QtWidgets.QLabel("")  # Anforderung eingehalten? gruen / gelb / rot mit Begruendung
        self.ampel.setWordWrap(True)
        self.ampel.setMinimumWidth(160)
        self.ampel.setMaximumWidth(520)
        self.ampel.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.alle_ueberlagern = QtWidgets.QCheckBox(tr("Alle Verfahren im Histogramm überlagern"))
        self.alle_ueberlagern.setToolTip(tr("Worst Case als Band, statistisch als Kurve, Monte Carlo als Histogramm"))
        self.alle_ueberlagern.setChecked(True)  # Vorgabe: alle Verfahren; eine Ergebniszeile waehlt eines
        self.alle_ueberlagern.toggled.connect(lambda _an: self._zeige_histogramm())
        links = QtWidgets.QVBoxLayout()
        links.addWidget(self.ampel)
        links.addWidget(self.ergebnisse)
        links.addStretch(1)
        rechts = QtWidgets.QVBoxLayout()
        rechts.addWidget(self.histogramm, 1)
        rechts.addWidget(self.alle_ueberlagern)
        nebeneinander = QtWidgets.QHBoxLayout()
        nebeneinander.addLayout(links)
        nebeneinander.addLayout(rechts, 1)
        unten_lay.addLayout(nebeneinander, 1)
        unten_lay.addWidget(self.ergebnis)
        unten_lay.addLayout(self._baue_freigabe())
        self.teiler.addWidget(unten)
        self.teiler.setStretchFactor(0, 3)
        self.teiler.setStretchFactor(1, 2)
        lay.addWidget(self.teiler, 1)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        self.kette_oeffnen = knoepfe.addButton(tr("Kette öffnen …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.kette_oeffnen.setToolTip(tr("Gespeicherte Kette (.3dgkette) laden, auch mit ihrem Modell"))
        self.kette_oeffnen.clicked.connect(self.oeffnen.emit)
        self.kette_speichern = knoepfe.addButton(tr("Kette speichern …"),
                                                 QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.kette_speichern.setToolTip(tr("Kette mit Werten, Temperaturen und Werkstoffen speichern, um später "
                                           "weiterzuarbeiten"))
        self.kette_speichern.clicked.connect(lambda: self.speichere_kette())
        self.export = knoepfe.addButton(tr("Als CSV speichern …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.export.setToolTip(tr("Glieder und Ergebnisse als Tabelle (CSV) speichern"))
        self.pdf = knoepfe.addButton(tr("PDF-Bericht …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.pdf.setToolTip(tr("Bericht mit Bild der Kette, Ergebnis, Bewertung, Freigabe und Histogramm als PDF"))
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)
        self.export.clicked.connect(lambda: self.speichere())
        self._methode_gewaehlt()

    # --- Aufbau ---

    def _baue_eingaben(self):
        reihe = FlussLayout()  # bricht bei wenig Breite um, das Fenster bleibt verkleinerbar
        self.plus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (+)"))
        self.plus.setToolTip(tr("In der PMI-Liste gewählte Maße als Glieder anhängen, die das Schlussmaß vergrößern"))
        self.minus = QtWidgets.QPushButton(tr("＋ Gewählte Maße (−)"))
        self.minus.setToolTip(tr("In der PMI-Liste gewählte Maße als Glieder anhängen, die das Schlussmaß verkleinern"))
        self.auswahl = QtWidgets.QPushButton(tr("＋ Aus 3D-Auswahl"))
        self.auswahl.setToolTip(tr("Flächen in Kettenreihenfolge: je zwei aufeinanderfolgende bilden ein Glied"))
        self.drehen = QtWidgets.QPushButton(tr("Richtung umkehren"))
        self.drehen.setToolTip(tr("Gewählte Glieder umkehren (auch per Doppelklick auf die Richtung)"))
        self.weg = QtWidgets.QPushButton(tr("－ Entfernen"))
        self.weg.setToolTip(tr("Gewählte Glieder aus der Kette entfernen"))
        self.neu_glied = QtWidgets.QPushButton(tr("＋ Glied"))
        self.neu_glied.setToolTip(tr("Leeres Glied anhängen, um die Kette von Hand aufzubauen (auch ohne Modell): Name, "
                                     "Nennmaß, Höchst- und Mindestmaß per Doppelklick eintragen, Richtung per "
                                     "Doppelklick umkehren"))
        self.neu_glied.clicked.connect(lambda: self.neues_glied())
        self.bereich = QtWidgets.QPushButton(tr("＋ Längenbereich …"))
        self.bereich.setToolTip(tr("Feder, Passscheibe oder Stellschraube als Glied zwischen kleinster und größter "
                                   "Länge"))
        self.bereich.clicked.connect(self._bereich_dialog)
        self.schluss = QtWidgets.QPushButton(tr("Richtungen aus Schlussmaß"))
        self.schluss.setToolTip(tr("Zwei Flächen des Schlussmaßes im Modell wählen (erst die ebene, Strg/⌘ dann die "
                                   "zweite): Reihenfolge und Vorzeichen aller Glieder folgen aus der Geometrie"))
        self.schluss.clicked.connect(self.schluss_aus_auswahl.emit)
        self.ablauf = QtWidgets.QPushButton(tr("▶ Ablaufen"))
        self.ablauf.setCheckable(True)
        self.ablauf.setToolTip(tr("Glieder nacheinander im Modell zeigen, um die Richtungen zu prüfen"))
        self.ablauf.toggled.connect(self._ablauf)
        self._ablauf_uhr = QtCore.QTimer(self)
        self._ablauf_uhr.setInterval(900)
        self._ablauf_uhr.timeout.connect(self._ablauf_schritt)
        self.bild3d = QtWidgets.QPushButton(tr("Kette im 3D"))
        self.bild3d.setCheckable(True)
        self.bild3d.setToolTip(tr("Alle Glieder als Pfeile mit Maß und Toleranz im Modell: Maße grün (+) und rot (−), "
                                  "Lagetoleranzen violett, Längenbereiche orange, Schlussmaß blau; im Planspiel "
                                  "geänderte Glieder zusätzlich grau mit dem Ist-Wert"))
        self.bild3d.toggled.connect(lambda _an: self._bild_senden())
        self.wiggle = QtWidgets.QPushButton()  # nur Symbol: Abspielen / Anhalten
        self.wiggle.setCheckable(True)
        self._wiggle_symbol(False)
        self.wiggle.toggled.connect(self._wiggle_symbol)
        self.wiggle.toggled.connect(self.schluss_wiggle.emit)
        self.drehen.clicked.connect(self._drehen)
        self.weg.clicked.connect(self._entfernen)
        self.lage = QtWidgets.QCheckBox(tr("Lagetoleranzen"))
        self.lage.setChecked(True)
        self.lage.setToolTip(tr("Position, Symmetrie, Koaxialität und Profil mit Bezug an der ersten und letzten Fläche "
                                "als eigene Glieder (Zwischenflächen heben sich auf)"))
        self.mitte_anfang = QtWidgets.QCheckBox(tr("Anfang: Mittelebene"))
        self.mitte_anfang.setToolTip(tr("Die ersten zwei gewählten Flächen (z. B. Flanken einer Nut) bilden eine "
                                        "Mittelebene als Kettenanfang: halbe Breite mit Faktor 0,5"))
        self.mitte_ende = QtWidgets.QCheckBox(tr("Ende: Mittelebene"))
        self.mitte_ende.setToolTip(tr("Die letzten zwei gewählten Flächen bilden eine Mittelebene als Kettenende: "
                                      "halbe Breite mit Faktor 0,5"))
        # wenige Knoepfe sichtbar: Hinzufuegen und Kettenbefehle als Menues (die Knoepfe/Schalter bleiben als
        # Objekte erhalten - das Hauptfenster und Tests haengen an ihren Signalen)
        reihe.addWidget(self._menue_knopf(tr("＋ Hinzufügen"), tr("Glieder anhängen: leer, aus der PMI-Liste, aus der "
                                                                 "3D-Auswahl oder als Längenbereich"),
                                          (self.neu_glied, self.plus, self.minus, self.auswahl, self.bereich)))
        reihe.addWidget(self.weg)
        reihe.addWidget(self._menue_knopf(tr("Kette"), tr("Richtungen und Optionen der Kette"),
                                          (self.drehen, self.schluss, None, self.lage, self.mitte_anfang,
                                           self.mitte_ende)))
        for k in (self.ablauf, self.bild3d, self.wiggle):
            reihe.addWidget(k)
        cp_text = QtWidgets.QLabel(tr("Prozessfähigkeit Cp"))
        self.cp = QtWidgets.QDoubleSpinBox()
        self.cp.setToolTip(tr("Prozessfähigkeit der Kette: normalverteilte Glieder streuen mit σ = T / (6 · Cp); 1,33 "
                              "übliche Serie, 1,0 gerade fähig"))
        self.cp.setRange(0.5, 3.0)
        self.cp.setSingleStep(0.1)
        self.cp.setDecimals(2)
        self.cp.setValue(1.0)
        self.cp.setToolTip(tr("Cp der Kette für normalverteilte Glieder ohne eigenen Wert: σ = Toleranz / (6 · Cp); "
                              "1,0 = ±3σ, 1,33 = ±4σ"))
        self.cp.valueChanged.connect(self._rechne)
        reihe.addWidget(_paar(cp_text, self.cp))
        self.methode = QtWidgets.QComboBox()
        for schluessel, text, tipp in METHODEN:
            self.methode.addItem(tr(text), schluessel)
            self.methode.setItemData(self.methode.count() - 1, tr(tipp), QtCore.Qt.ItemDataRole.ToolTipRole)
        self.methode.setToolTip(tr("Statistisches Verfahren für das Schlussmaß"))
        self.methode_wert = QtWidgets.QDoubleSpinBox()
        self.methode_wert.setToolTip(tr("Bender-Faktor (× auf das RSS) bzw. Anteil m der halben Toleranz, um den jede "
                                        "Mitte wandern darf"))
        self.methode_wert.setDecimals(2)
        self.methode_wert.setSingleStep(0.05)
        self.methode.currentIndexChanged.connect(self._methode_gewaehlt)
        self.methode_wert.valueChanged.connect(self._rechne)
        reihe.addWidget(_paar(self.methode, self.methode_wert))
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
        self.verteilen = QtWidgets.QPushButton(tr("Toleranzen verteilen …"))
        self.verteilen.setToolTip(tr("Nicht feste Toleranzen so setzen, dass das Schlussmaß die Zielbreite erreicht"))
        self.verteilen.clicked.connect(self._verteilen_dialog)
        reihe.addWidget(self.verteilen)
        self.szenario = QtWidgets.QComboBox()
        self.szenario.setToolTip(tr("Gemerktes Szenario ins Planspiel laden"))
        self.szenario.activated.connect(lambda i: self.lade_szenario(self.szenario.itemData(i)))
        reihe.addWidget(self.szenario)
        merken = QtWidgets.QPushButton(tr("Merken …"))
        merken.setToolTip(tr("Planspiel als Szenario unter einem Namen merken (wird mit der Kette gespeichert)"))
        merken.clicked.connect(lambda: self.merke_szenario())
        reihe.addWidget(merken)
        self.vergleichen = QtWidgets.QPushButton(tr("Vergleichen …"))
        self.vergleichen.setToolTip(tr("Ist und alle gemerkten Szenarien nebeneinander"))
        self.vergleichen.clicked.connect(lambda: self.zeige_szenarien())
        reihe.addWidget(self.vergleichen)
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
        self.unten.setToolTip(tr("Untere und obere Grenze des Schlussmaßes (auch im Histogramm ziehbar)"))
        self.oben.setToolTip(self.unten.toolTip())
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

    def _ergebnis_hoehe(self):
        """Ergebnistabelle so hoch wie ihre Zeilen, plus Querlaufleiste, wenn sie schmaler als ihr Inhalt ist."""
        t = self.ergebnisse
        leiste = t.horizontalScrollBar()
        hoehe = t.horizontalHeader().sizeHint().height() + sum(t.rowHeight(z) for z in range(t.rowCount())) \
            + 2 * t.frameWidth() + (leiste.sizeHint().height() if leiste.maximum() > 0 else 0)
        if t.height() != hoehe or t.minimumHeight() != hoehe:
            t.setFixedHeight(hoehe)

    def _ampel_hoehe(self):
        """Feste Hoehe der umbrechenden Ampelzeile bei ihrer aktuellen Breite, damit das Layout sie einrechnet
        (sonst ueberlappt der Text darunter die Ergebnistabelle); folgt der Fensterbreite."""
        breite = max(self.ampel.minimumWidth(), min(self.ampel.maximumWidth(), self.ampel.width()))
        hoehe = self.ampel.heightForWidth(breite) if self.ampel.text() else 0
        if self.ampel.height() != hoehe or self.ampel.minimumHeight() != hoehe:
            self.ampel.setFixedHeight(hoehe)

    def resizeEvent(self, ev):  # noqa: N802 - Qt
        super().resizeEvent(ev)
        # breit und niedrig (Leiste unter der 3D-Ansicht): Glieder links, Ergebnis rechts; sonst untereinander
        quer = self.width() > 1.6 * self.height()
        richtung = QtCore.Qt.Orientation.Horizontal if quer else QtCore.Qt.Orientation.Vertical
        if self.teiler.orientation() != richtung:
            self.teiler.setOrientation(richtung)
            self._unten.setMinimumHeight(0)
            QtCore.QTimer.singleShot(0, self._unten_hoehe)
        QtCore.QTimer.singleShot(0, self._ampel_hoehe)  # nach dem Layout: neue Breite der Ampelzeile

    def _unten_hoehe(self):
        """Ergebnisbereich nicht kleiner als sein Inhalt (feste Ergebnistabelle samt Ampel), sonst ueberlappt er."""
        self._unten.layout().activate()
        noetig = self._unten.layout().minimumSize().height()
        self._unten.setMinimumHeight(noetig)
        if self.teiler.orientation() == QtCore.Qt.Orientation.Horizontal:
            return  # nebeneinander: die Hoehe gibt die Leiste vor
        oben, unten = self.teiler.sizes()
        if unten < noetig:  # Teiler nach oben schieben, die Glieder behalten den Rest
            self.teiler.setSizes([max(oben + unten - noetig, 80), noetig])

    def _baue_freigabe(self):
        """Manuelle Freigabe: Kette als in Ordnung und geprueft markieren, unabhaengig vom Ergebnis, mit Kommentar."""
        reihe = QtWidgets.QHBoxLayout()
        self.geprueft = QtWidgets.QCheckBox(tr("Kette i. O. / geprüft"))
        self.geprueft.setToolTip(tr("Manuelle Freigabe, auch abweichend vom Ergebnis (z. B. Funktion im Versuch "
                                    "nachgewiesen) – mit Name, Datum und Kommentar im Bericht und in der Kettendatei"))
        self.pruefer = QtWidgets.QLineEdit()
        self.pruefer.setToolTip(tr("Name der Person, die die Kette freigibt"))
        self.pruefer.setPlaceholderText(tr("Name"))
        self.pruefer.setMaximumWidth(160)
        self.pruef_kommentar = QtWidgets.QLineEdit()
        self.pruef_kommentar.setToolTip(tr("Begründung der Freigabe, z. B. Versuch, Erfahrung, Abstimmung – erscheint "
                                           "im Bericht"))
        self.pruef_kommentar.setPlaceholderText(tr("Kommentar zur Freigabe"))
        self.pruef_datum = QtWidgets.QLabel("")
        self.pruef_datum.setObjectName("leise")
        self.geprueft.toggled.connect(self._freigabe_umgeschaltet)
        for w in (self.geprueft, self.pruefer, self.pruef_kommentar, self.pruef_datum):
            reihe.addWidget(w, 1 if w is self.pruef_kommentar else 0)
        return reihe

    def _freigabe_umgeschaltet(self, an: bool):
        import datetime
        import getpass
        if an:
            if not self.pruefer.text():
                try:
                    self.pruefer.setText(getpass.getuser())
                except Exception:  # noqa: BLE001 - ohne Benutzername bleibt das Feld leer
                    pass
            self.pruef_datum.setText(datetime.date.today().isoformat())
        else:
            self.pruef_datum.setText("")
        self._zeige_ampel()

    @property
    def freigabe(self) -> dict:
        """Manuelle Freigabe fuer Datei und Bericht ({} ohne Freigabe und Kommentar)."""
        if not self.geprueft.isChecked() and not self.pruef_kommentar.text():
            return {}
        return {"geprueft": self.geprueft.isChecked(), "name": self.pruefer.text(),
                "datum": self.pruef_datum.text(), "kommentar": self.pruef_kommentar.text()}

    def setze_freigabe(self, f: dict):
        self.geprueft.blockSignals(True)
        self.geprueft.setChecked(bool(f.get("geprueft")))
        self.geprueft.blockSignals(False)
        self.pruefer.setText(f.get("name", ""))
        self.pruef_kommentar.setText(f.get("kommentar", ""))
        self.pruef_datum.setText(f.get("datum", ""))
        self._zeige_ampel()

    def bewertung(self) -> tuple[str, str]:
        """Ampel der Anforderung nach dem anwendbaren Verfahren (kern.toleranzkette.bewertung)."""
        e = getattr(self, "e", None)
        if e is None or not self.glieder:
            return "", ""
        return tk.bewertung(e, self.anforderung_werte(), self._werte(e, "rss" if e.statistisch else "wc"))

    AMPEL_FARBEN = {"gruen": "#2e9e48", "gelb": "#e0a800", "rot": "#c0392b"}

    def _zeige_ampel(self):
        stufe, text = self.bewertung()
        teile = []
        if stufe:
            teile.append(f"<span style='color:{self.AMPEL_FARBEN[stufe]}; font-size:16px'>●</span> "
                         f"{html.escape(text)}")
        f = self.freigabe
        if f.get("geprueft"):
            teile.append("✔ " + html.escape(tr("manuell freigegeben: {} {}").format(f["name"], f["datum"]).strip()
                                            + (" – " + f["kommentar"] if f["kommentar"] else "")))
        self.ampel.setText("<br>".join(teile))
        self.ampel.setVisible(bool(teile))
        self._ampel_hoehe()
        QtCore.QTimer.singleShot(0, self._unten_hoehe)

    def _verfahren_gewaehlt(self, zeile: int, _spalte: int):
        """Zeile der Ergebnistabelle: Histogramm nur mit diesem Verfahren (nochmals: wieder alle ueberlagert)."""
        arten = [a for a, _ in self.ERGEBNIS_ZEILEN]
        if zeile >= len(arten):
            return
        art = arten[zeile]
        zurueck = self.hist_art == art and not self.alle_ueberlagern.isChecked()
        self.hist_art = None if zurueck else art
        self.alle_ueberlagern.blockSignals(True)
        self.alle_ueberlagern.setChecked(zurueck)
        self.alle_ueberlagern.blockSignals(False)
        self._zeige_histogramm()

    def histogramm_art(self) -> str:
        """Gezeigtes Verfahren: "alle", die angeklickte Zeile oder das anwendbare (✓)."""
        if self.alle_ueberlagern.isChecked():
            return "alle"
        if self.hist_art:
            return self.hist_art
        return "rss" if self.e.statistisch else "wc"

    def _zeige_histogramm(self):
        e = getattr(self, "e", None)
        if e is None or not self.glieder:
            self.histogramm.zeige(None)
            return
        lo, hi = self._werte(e, "rss")
        self.histogramm.zeige(e, self.e_ist, self.anforderung_werte(), self.histogramm_art(), (hi - lo) / 2)
        art = self.histogramm_art()
        for z, (a, _) in enumerate(self.ERGEBNIS_ZEILEN):  # gezeigte Zeile markieren
            for s in range(self.ergebnisse.columnCount()):
                it = self.ergebnisse.item(z, s)
                if it is not None:
                    it.setBackground(self.palette().color(QtGui.QPalette.ColorRole.AlternateBase)
                                     if a == art else QtGui.QBrush())

    def _baue_temperatur(self):
        reihe = QtWidgets.QHBoxLayout()
        self.waerme = QtWidgets.QCheckBox(tr("Wärmeausdehnung bei"))
        self.waerme.setToolTip(tr("Schlussmaß zusätzlich bei zwei Grenztemperaturen: ΔL = α · L · (T − 20 °C) je "
                                  "Glied mit dem Werkstoff seines Bauteils"))
        self.t1, self.t2 = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        self.t1.setToolTip(tr("Grenztemperaturen (z. B. Kaltstart und Betrieb); Bezug ist 20 °C nach ISO 1"))
        self.t2.setToolTip(self.t1.toolTip())
        for k, w in ((self.t1, -20.0), (self.t2, 80.0)):
            k.setRange(-273.0, 1000.0)
            k.setDecimals(1)
            k.setSuffix(" °C")
            k.setValue(w)
            k.setEnabled(False)
            k.valueChanged.connect(self._rechne)
        self.waerme.toggled.connect(lambda an: (self.t1.setEnabled(an), self.t2.setEnabled(an), self._rechne()))
        self.werkstoff_knopf = QtWidgets.QPushButton(tr("Werkstoffe …"))
        self.werkstoff_knopf.setToolTip(tr("Werkstoff und Ausdehnungskoeffizient je Bauteil, auch eigene Temperaturen"))
        self.werkstoff_knopf.clicked.connect(lambda: WerkstoffDialog(self, self).open())
        reihe.addWidget(self.waerme)
        reihe.addWidget(self.t1)
        reihe.addWidget(QtWidgets.QLabel(tr("und")))
        reihe.addWidget(self.t2)
        reihe.addWidget(self.werkstoff_knopf)
        reihe.addStretch(1)
        return reihe

    def _methode_gewaehlt(self, *_):
        art = self.methode.currentData()
        self.methode_wert.blockSignals(True)
        if art == "bender":
            self.methode_wert.setRange(1.0, 3.0)
            self.methode_wert.setPrefix("× ")
            self.methode_wert.setValue(tk.BENDER)
        elif art == "verschiebung":
            self.methode_wert.setRange(0.0, 1.0)
            self.methode_wert.setPrefix("m = ")
            self.methode_wert.setValue(tk.VERSCHIEBUNG)
        self.methode_wert.blockSignals(False)
        self.methode_wert.setVisible(art != "rss")
        self._rechne()

    def verteile(self, ziel: float, art: str = "varianz", statistisch: bool = True) -> bool:
        """Im Planspiel die nicht festen Toleranzen auf die Zielbreite des Schlussmasses verteilen; art "kosten":
        kostenoptimal nach den Fertigungsverfahren der Glieder (Ergebnis und Kosten in der Statuszeile)."""
        if not self.im_planspiel:
            self.starte_planspiel()
        self.kosten_hinweis = ""
        if art == "kosten":
            v = tk.verteile_kostenoptimal(self.glieder, ziel, statistisch, self.cp.value())
            neu = v.glieder
            self.kosten_hinweis = " ".join([tr("Fertigungskosten (relativ) {:.2f} → {:.2f}").format(
                v.kosten_vorher, v.kosten_nachher)] + v.hinweise)
        else:
            neu = tk.verteile_toleranzen(self.glieder, ziel, art, statistisch, self.cp.value())
        if all(a.toleranz == b.toleranz for a, b in zip(neu, self.glieder)):
            return False
        self.glieder = neu
        self._fuelle()
        return True

    def _verteilen_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(tr("Toleranzen verteilen"))
        form = QtWidgets.QFormLayout(d)
        ziel = QtWidgets.QDoubleSpinBox()
        ziel.setRange(0.0001, 100000.0)
        ziel.setDecimals(4)
        ziel.setSuffix(" mm")
        a = self.anforderung_werte()
        ziel.setValue((a[1] - a[0]) if a else (self.e.wc_max - self.e.wc_min))
        art = QtWidgets.QComboBox()
        art.addItem(tr("Gleiche Varianz je Glied (angleichen)"), "varianz")
        art.addItem(tr("Proportional zu den jetzigen Toleranzen"), "proportional")
        art.addItem(tr("Kostenoptimal nach Fertigungsverfahren"), "kosten")
        art.setToolTip(tr("Angleichen: jedes Glied gleicher Varianzanteil; proportional: alle mit demselben Faktor; "
                          "kostenoptimal: geringste Fertigungskosten – billige Verfahren bekommen weite, teure enge "
                          "Toleranzen, je Glied zwischen feinstem und grobem IT-Grad seines Verfahrens"))
        ziel.setToolTip(tr("Gewünschte Breite des Schlussmaßes (Vorgabe: Breite der Anforderung)"))
        basis = QtWidgets.QComboBox()
        basis.addItem(tr("Statistisch (±3σ)"), True)
        basis.addItem(tr("Arithmetisch (Worst Case)"), False)
        basis.setCurrentIndex(0 if self.e.statistisch else 1)
        basis.setToolTip(tr("Ziel als ±3σ (statistisch) oder als Summe der Toleranzen (Worst Case)"))
        for text, w in ((tr("Zielbreite des Schlussmaßes"), ziel), (tr("Verfahren"), art), (tr("Grundlage"), basis)):
            form.addRow(text, w)
        hinweis = QtWidgets.QLabel(tr("Feste Glieder (Rechtsklick) bleiben; das Ergebnis erscheint im Planspiel."))
        hinweis.setObjectName("leise")
        form.addRow(hinweis)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(d.accept)
        knoepfe.rejected.connect(d.reject)
        form.addRow(knoepfe)
        d.accepted.connect(lambda: self.verteile(ziel.value(), art.currentData(), basis.currentData()))
        d.open()
        return d

    def teile(self) -> list[str]:
        return sorted({g.teil for g in self.glieder if g.teil} | set(self.werkstoffe))

    def setze_werkstoff(self, teil: str, name: str, alpha: float | None):
        self.werkstoffe.setdefault(teil, {}).update({"name": name, "alpha": alpha or None})
        self._rechne()

    def setze_teiltemperatur(self, teil: str, schluessel: str, wert: float | None):
        """Eigene Temperatur eines Bauteils im Grenzfall t1/t2 (None: Temperatur der Kette)."""
        self.werkstoffe.setdefault(teil, {})[schluessel] = wert
        self._rechne()

    def _je_teil(self, fall: int) -> dict:
        schluessel = ("t1", "t2")[fall]
        return {t: w[schluessel] for t, w in self.werkstoffe.items() if w.get(schluessel) is not None}

    def temperaturen(self):
        return (self.t1.value(), self.t2.value()) if self.waerme.isChecked() else None

    def _alpha(self) -> dict:
        return {t: w["alpha"] for t, w in self.werkstoffe.items() if w.get("alpha")}

    # --- Glieder ---

    def _teile_setzen(self, glieder):
        for g in glieder:
            if not g.teil and g.flaechen:
                g.teil = self.teil_von(g.flaechen)

    def ergaenze_bereich(self, name: str, mindest: float, hoechst: float, richtung: int = 1,
                         stellglied: bool = False):
        self.glieder.append(tk.bereich_glied(name, mindest, hoechst, richtung, stellglied))
        self._fuelle()

    def _bereich_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(tr("Längenbereich"))
        form = QtWidgets.QFormLayout(d)
        name = QtWidgets.QLineEdit(tr("Feder"))
        lo, hi = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for k in (lo, hi):
            k.setRange(-100000.0, 100000.0)
            k.setDecimals(3)
            k.setSuffix(" mm")
        richtung = QtWidgets.QComboBox()
        richtung.addItem(tr("+ vergrößert das Schlussmaß"), 1)
        richtung.addItem(tr("− verkleinert das Schlussmaß"), -1)
        stell = QtWidgets.QCheckBox(tr("Stellglied (Bereich wird berechnet)"))
        for text, w in ((tr("Name"), name), (tr("Kleinste Länge"), lo), (tr("Größte Länge"), hi),
                        (tr("Richtung"), richtung), ("", stell)):
            form.addRow(text, w)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(d.accept)
        knoepfe.rejected.connect(d.reject)
        form.addRow(knoepfe)
        d.accepted.connect(lambda: self.ergaenze_bereich(name.text(), lo.value(), hi.value(), richtung.currentData(),
                                                         stell.isChecked()))
        d.open()
        return d

    def _kontextmenue(self, pos):
        z = self.tabelle.rowAt(pos.y())
        if not 0 <= z < len(self.glieder):
            return
        g = self.glieder[z]
        m = QtWidgets.QMenu(self)
        stell = m.addAction(tr("Als Stellglied"))
        stell.setCheckable(True)
        stell.setChecked(g.stellglied)
        stell.setToolTip(tr("Nötigen Bereich dieses Glieds für die Anforderung berechnen"))
        fest = m.addAction(tr("Fest beim Verteilen"))
        fest.setCheckable(True)
        fest.setChecked(g.fest)
        korr = m.addAction(tr("Korrelation …"))
        korr.setToolTip(tr("Gewählte Glieder streuen gemeinsam (gleiches Teil, gleiche Aufspannung oder Prozess)"))
        umkehren = m.addAction(tr("Richtung umkehren"))
        weg = m.addAction(tr("Entfernen"))
        gewaehlt = m.exec(self.tabelle.viewport().mapToGlobal(pos))
        if gewaehlt is korr:
            zeilen = sorted({i.row() for i in self.tabelle.selectedIndexes()} | {z})
            self.korrelation_dialog(zeilen)
        if gewaehlt is stell:
            self.setze_stellglied(z, stell.isChecked())
        elif gewaehlt is fest:
            g.fest = fest.isChecked()
            self._fuelle()
        elif gewaehlt is umkehren:
            self._doppelklick(z, SP_RICHTUNG)
        elif gewaehlt is weg:
            self.tabelle.selectRow(z)
            self._entfernen()

    def korrelation_dialog(self, zeilen: list[int]):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(tr("Korrelation"))
        form = QtWidgets.QFormLayout(d)
        form.addRow(QtWidgets.QLabel(tr("Glieder einer Gruppe streuen gemeinsam, z. B. Maße desselben Teils aus einer "
                                        "Aufspannung. ρ = 0: unabhängig, 1: voll korreliert.")))
        gruppe = QtWidgets.QComboBox()
        gruppe.setEditable(True)
        vorhanden = sorted({g.gruppe for g in self.glieder if g.gruppe})
        gruppe.addItems(vorhanden or [tr("Gruppe 1")])
        erstes = self.glieder[zeilen[0]]
        if erstes.gruppe:
            gruppe.setCurrentText(erstes.gruppe)
        rho = QtWidgets.QDoubleSpinBox()
        rho.setRange(0.0, 1.0)
        rho.setSingleStep(0.1)
        rho.setDecimals(2)
        rho.setValue(erstes.rho if erstes.gruppe else 0.8)
        form.addRow(tr("Gruppe"), gruppe)
        form.addRow("ρ", rho)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        aufheben = knoepfe.addButton(tr("Aufheben"), QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        aufheben.clicked.connect(lambda: (self.setze_korrelation(zeilen, "", 0.0), d.reject()))
        knoepfe.accepted.connect(d.accept)
        knoepfe.rejected.connect(d.reject)
        form.addRow(knoepfe)
        if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.setze_korrelation(zeilen, gruppe.currentText().strip(), rho.value())

    def setze_korrelation(self, zeilen: list[int], gruppe: str, rho: float):
        """Glieder einer Korrelationsgruppe zuordnen (leere Gruppe oder rho 0: unabhaengig)."""
        for z in zeilen:
            if z < len(self.glieder):
                g = self.glieder[z]
                g.gruppe, g.rho = (gruppe, rho) if gruppe and rho > 0 else ("", 0.0)
        self._fuelle()

    def setze_stellglied(self, z: int, an: bool):
        for i, g in enumerate(self.glieder):
            g.stellglied = an and i == z  # hoechstens ein Stellglied
        self._fuelle()

    def setze_glieder(self, glieder: list):
        """Glieder ersetzen (z. B. in Kettenreihenfolge aus dem Schlussmass)."""
        self.glieder = list(glieder)
        self._fuelle()

    def _ablauf(self, an: bool):
        self.ablauf.setText(tr("⏸ Anhalten") if an else tr("▶ Ablaufen"))
        self._ablauf_nr = -1
        if an and self.glieder:
            self._ablauf_uhr.start()
            self._ablauf_schritt()
        else:
            self._ablauf_uhr.stop()
            self.tabelle.clearSelection()
            self.strecke_zeigen.emit(None)
            self._bild_senden()

    def _ablauf_schritt(self):
        """Naechstes Glied waehlen (hebt seine Flaechen hervor) und Richtung und Wert nennen."""
        if not self.glieder:
            self.ablauf.setChecked(False)
            return
        self._ablauf_nr = (self._ablauf_nr + 1) % len(self.glieder)
        g = self.glieder[self._ablauf_nr]
        self.tabelle.selectRow(self._ablauf_nr)
        self.strecke_zeigen.emit(g)
        self.ergebnis.setText(html.escape(tr("Glied {} von {}: {} {} – {}").format(
            self._ablauf_nr + 1, len(self.glieder), "+" if g.richtung > 0 else "−", _z(abs(g.nenn)), g.name)))

    def _menue_knopf(self, text: str, tipp: str, eintraege) -> QtWidgets.QToolButton:
        """Knopf mit Menue: Knoepfe werden Befehle (Klick loest den Knopf aus), Schalter abhakbare Eintraege (beide
        Richtungen abgeglichen), None ein Trenner."""
        knopf = QtWidgets.QToolButton()
        knopf.setText(text)
        knopf.setToolTip(tipp)
        knopf.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menue = QtWidgets.QMenu(knopf)
        menue.setToolTipsVisible(True)
        for e in eintraege:
            if e is None:
                menue.addSeparator()
                continue
            a = menue.addAction(e.text())
            a.setToolTip(e.toolTip())
            if isinstance(e, QtWidgets.QCheckBox):
                a.setCheckable(True)
                a.setChecked(e.isChecked())
                a.toggled.connect(e.setChecked)
                e.toggled.connect(a.setChecked)
            else:
                a.triggered.connect(e.click)
        knopf.setMenu(menue)
        return knopf

    def _wiggle_symbol(self, an: bool):
        """Abspielen- bzw. Anhalten-Symbol ohne Text; der Tooltip sagt, was ein Klick tut."""
        bild = QtWidgets.QStyle.StandardPixmap.SP_MediaPause if an else QtWidgets.QStyle.StandardPixmap.SP_MediaPlay
        self.wiggle.setIcon(self.style().standardIcon(bild))
        self.wiggle.setToolTip(tr("Wiggle der Schlussflächen anhalten") if an else
                               tr("Wiggle der Schlussflächen: die Endfläche der Kette pendelt zwischen Worst-Case-"
                                  "Minimum und -Maximum (überhöht), grün in der Anforderung, rot außerhalb"))

    def schluss_text(self) -> str:
        """Beschriftung des Schlussmasses im 3D: Nennmass, Worst Case und statistisches Ergebnis."""
        e = self.e
        return tr("Schlussmaß {}  WC {} … {}  RSS ±{}").format(_z(e.nenn), _z(e.wc_min), _z(e.wc_max), _z(e.rss))

    def _bild_senden(self):
        """Kettenbild an die 3D-Ansicht (nur wenn eingeschaltet und die Kette nicht gerade abgelaufen wird)."""
        if self.ablauf.isChecked():
            return
        if self.bild3d.isChecked() and self.glieder and getattr(self, "e", None) is not None:
            zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
            hervor = min(zeilen) if len(zeilen) == 1 else None
            self.bild_zeigen.emit((list(self.glieder), self.schluss_text(), self._ist if self.im_planspiel else None,
                                   hervor))
        else:
            self.bild_zeigen.emit(None)

    # --- Datei ---

    def als_datei(self):
        from ..kern import kette_datei
        glieder, cp = (self._ist, self._ist_cp) if self.im_planspiel else (self.glieder, self.cp.value())
        return kette_datei.KettenDatei(glieder, cp, self.anforderung_werte(), self.temperaturen(),
                                       dict(self.werkstoffe), self.modell_pfad, szenarien=dict(self.szenarien),
                                       freigabe=self.freigabe)

    def lade_datei(self, k):
        """Kettendatei uebernehmen (Glieder, Cp, Anforderung, Temperaturen, Werkstoffe)."""
        self.beende_planspiel(False)
        self.werkstoffe = dict(k.werkstoffe)
        for feld, wert in ((self.cp, k.cp),):
            feld.blockSignals(True)
            feld.setValue(wert)
            feld.blockSignals(False)
        if k.anforderung:
            self.anforderung.setChecked(True)
            self.unten.setValue(k.anforderung[0])
            self.oben.setValue(k.anforderung[1])
        else:
            self.anforderung.setChecked(False)
        if k.temperaturen:
            self.t1.setValue(k.temperaturen[0])
            self.t2.setValue(k.temperaturen[1])
        self.waerme.setChecked(bool(k.temperaturen))
        self.glieder = list(k.glieder)
        self.szenarien = dict(k.szenarien)
        self._szenarien_liste()
        self.setze_freigabe(k.freigabe)
        self._fuelle()

    def speichere_kette(self, pfad: str = "") -> str | None:
        from ..kern import kette_datei
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Kette speichern"), "kette" + kette_datei.ENDUNG,
                                                            tr("Toleranzkette (*.3dgkette)"))
        if not pfad:
            return None
        return kette_datei.speichere(pfad, self.als_datei())

    @property
    def im_planspiel(self) -> bool:
        return self._ist is not None

    def leeren(self):
        """Neues Modell: die Glieder verweisen auf PMI des alten Modells."""
        self._ist = None
        self.plan_leiste.hide()
        self.glieder = []
        self.szenarien = {}
        self._szenarien_liste()
        self.setze_freigabe({})
        self._fuelle()

    def ergaenze(self, glieder: list):
        """Glieder aus der 3D-Auswahl anhaengen."""
        self._teile_setzen(glieder)
        self.glieder.extend(glieder)
        self._fuelle()

    def uebernimm(self, pmi_liste: list, richtung: int = 1) -> int:
        n = 0
        for p in pmi_liste:
            g = tk.glied_von_pmi(p, richtung)
            if g is not None:
                self._teile_setzen([g])
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
        if self.ablauf.isChecked():
            return  # beim Ablaufen zeigt der Rundgang das Glied
        if self.bild3d.isChecked():
            self._bild_senden()  # Kettenbild mit dem gewaehlten Glied hervorgehoben
        else:  # nur der Pfeil des gewaehlten Glieds
            self.strecke_zeigen.emit(self.glieder[min(zeilen)] if len(zeilen) == 1 and min(zeilen) < len(self.glieder)
                                     else None)

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
        self.kosten_hinweis = ""
        self.plan_leiste.hide()
        self._fuelle()

    # --- Szenarien ---

    def _szenarien_liste(self):
        self.szenario.blockSignals(True)
        self.szenario.clear()
        self.szenario.addItem(tr("Szenario …"), None)
        for name in self.szenarien:
            self.szenario.addItem(name, name)
        self.szenario.blockSignals(False)
        self.vergleichen.setEnabled(bool(self.szenarien))

    def merke_szenario(self, name: str = "") -> str | None:
        """Aktuelles Planspiel unter einem Namen merken (gleicher Name ersetzt)."""
        if not self.im_planspiel:
            return None
        if not name:
            name, ok = QtWidgets.QInputDialog.getText(self, tr("Szenario merken"), tr("Name"),
                                                      text=tr("Szenario {}").format(len(self.szenarien) + 1))
            if not ok or not name.strip():
                return None
        self.szenarien[name.strip()] = (self.cp.value(), copy.deepcopy(self.glieder))
        self._szenarien_liste()
        self.szenario.setCurrentIndex(self.szenario.findData(name.strip()))
        return name.strip()

    def lade_szenario(self, name):
        if name not in self.szenarien:
            return
        self.starte_planspiel()
        cp, glieder = self.szenarien[name]
        if len(glieder) != len(self._ist):  # Kette inzwischen geaendert: Zeilen passen nicht mehr
            QtWidgets.QMessageBox.information(self, tr("Szenario"), tr("Die Kette hat inzwischen andere Glieder – "
                                                                       "das Szenario passt nicht mehr."))
            return
        self.glieder = copy.deepcopy(glieder)
        self.cp.blockSignals(True)
        self.cp.setValue(cp)
        self.cp.blockSignals(False)
        self._fuelle()

    def szenario_zeilen(self) -> tuple[list[str], list[list[str]]]:
        """Vergleich Ist und gemerkte Szenarien: anwendbares Verfahren, Bereich, Breite, Cpk, ausserhalb."""
        anforderung = self.anforderung_werte()
        para = self._methode_parameter()
        ist = self._ist if self.im_planspiel else self.glieder
        ist_cp = self._ist_cp if self.im_planspiel else self.cp.value()
        koepfe = [tr("Szenario"), tr("Verfahren"), tr("Minimum"), tr("Maximum"), tr("Breite"), "Cpk",
                  tr("außerhalb (Monte Carlo)")]
        zeilen = []
        for name, (cp, glieder) in [(tr("Ist"), (ist_cp, ist))] + list(self.szenarien.items()):
            e = tk.berechne(glieder, cp=cp, anforderung=anforderung, **para)
            art = "rss" if e.statistisch else "wc"
            lo, hi = self._werte(e, art)
            zeilen.append([name, tr(dict(self.ERGEBNIS_ZEILEN)[art]), _z(lo), _z(hi), _z(hi - lo),
                           f"{e.cpk:.2f}" if e.cpk is not None else "–",
                           f"{e.mc_ausserhalb * 1e6:.0f} ppm" if e.mc_ausserhalb is not None else "–"])
        return koepfe, zeilen

    def zeige_szenarien(self) -> QtWidgets.QDialog:
        koepfe, zeilen = self.szenario_zeilen()
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(tr("Szenarien vergleichen"))
        lay = QtWidgets.QVBoxLayout(d)
        t = QtWidgets.QTableWidget(len(zeilen), len(koepfe))
        t.setHorizontalHeaderLabels(koepfe)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for z, zellen in enumerate(zeilen):
            for s, w in enumerate(zellen):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        t.resizeColumnsToContents()
        lay.addWidget(t)
        knopf = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        knopf.rejected.connect(d.reject)
        lay.addWidget(knopf)
        d.resize(760, 120 + 30 * len(zeilen))
        d.show()
        return d

    def _ist_glied(self, z: int):
        return self._ist[z] if self.im_planspiel and z < len(self._ist) else None

    def neues_glied(self, name: str = "", nenn: float = 10.0, oben: float = 0.1, unten: float = -0.1,
                    richtung: int = 1):
        """Glied von Hand anhaengen (eigene Angabe); die neue Zeile wird gewaehlt und der Name bearbeitet."""
        self.glieder.append(tk.Glied(name or tr("Glied {}").format(len(self.glieder) + 1), nenn, nenn + oben,
                                     nenn + unten, richtung, quelle="eigen"))
        self._fuelle()
        z = len(self.glieder) - 1
        self.tabelle.selectRow(z)
        if self.isVisible():
            self.tabelle.editItem(self.tabelle.item(z, 0))
        return self.glieder[-1]

    def _wert_geaendert(self, it):
        """Name, Nennmass, Grenzen oder Toleranz in der Tabelle geaendert (Toleranz: symmetrisch zur Mitte); im
        Planspiel alle Glieder, sonst nur von Hand angelegte."""
        z, s = it.row(), it.column()
        if z >= len(self.glieder) or s not in (0, SP_NENN, SP_HOCH, SP_MIN, SP_TOL):
            return
        if not self.im_planspiel and self.glieder[z].quelle not in ("eigen", "ohne"):
            return
        if s == 0:  # Name (ohne die angehaengten Marken)
            self.glieder[z].name = it.text().split("  [")[0].strip() or self.glieder[z].name
            QtCore.QTimer.singleShot(0, self._fuelle)
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
        if aenderbar:  # erkennbar machen: getoent, Hinweis; ein Klick in die Zelle bearbeitet
            it.setBackground(AENDERBAR_FARBE)
            it.setToolTip(tr("Klicken zum Ändern"))
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
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.CurrentChanged |
                          QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked |
                          QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked |
                          QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed)  # welche Zelle: aenderbar unten
        t.setRowCount(len(self.glieder))
        for z, g in enumerate(self.glieder):
            ist = self._ist_glied(z)
            vorher = None if ist is None else self._texte(ist)
            for s, w in enumerate(self._texte(g)):
                von_hand = g.quelle in ("eigen", "ohne")  # von Hand angelegt: immer bearbeitbar, auch der Name
                aenderbar = (self.im_planspiel or von_hand) and (
                    s in (SP_HOCH, SP_MIN, SP_TOL) or (s == SP_NENN and g.quelle != "lage") or (s == 0 and von_hand))
                self._zelle(z, s, w, None if vorher is None else vorher[s], aenderbar)
            t.item(z, SP_RICHTUNG).setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if vorher is None or vorher[SP_RICHTUNG] == self._texte(g)[SP_RICHTUNG]:
                t.item(z, SP_RICHTUNG).setToolTip(tr("Doppelklick kehrt die Richtung um"))
            if g.quelle == "ohne":
                t.item(z, 6).setForeground(QtGui.QColor("#c0392b"))
            if g.stellglied or g.fest or g.gruppe:
                marken = [tr("Stellglied")] * g.stellglied + [tr("fest")] * g.fest + \
                    [f"{g.gruppe} ρ {g.rho:.2g}"] * bool(g.gruppe)
                t.item(z, 0).setText(f"{g.name}  [{', '.join(marken)}]")
            if g.teil:
                t.item(z, 0).setToolTip(tr("Bauteil: {}").format(g.teil))
            self._widgets(z, g, ist)
            self._zelle(z, SP_ANTEIL, "", None, False)
            self._zelle(z, SP_STREUUNG, "", None, False)
            self._fertigung(z, g, ist)
            for s, name in enumerate(tk.SPALTEN + ("Streuung",)):  # Erklaerung je Zelle (eigene Hinweise gehen vor)
                it = t.item(z, s)
                if it is not None and not it.toolTip():
                    it.setToolTip(tr(SPALTEN_HILFE[name]))
                elif it is not None and it.toolTip() == tr("Klicken zum Ändern"):
                    it.setToolTip(tr(SPALTEN_HILFE[name]) + "\n" + tr("Klicken zum Ändern"))
        t.blockSignals(False)
        self._rechne()

    def _fertigung(self, z: int, g, ist):
        """Auswahl des Fertigungsverfahrens mit dem IT-Grad der jetzigen Toleranz (nicht bei Lagetoleranzen)."""
        from ..kern import fertigung as fe
        if g.quelle == "lage":
            self._zelle(z, SP_FERTIGUNG, "–", None, False)
            return
        w = QtWidgets.QComboBox()
        for schluessel, v in fe.VERFAHREN.items():
            text = tr(v.name) if not v.kosten else f"{tr(v.name)} (IT{v.it_fein}–{v.it_grob})"
            w.addItem(text, schluessel)
        w.setCurrentIndex(max(0, w.findData(g.verfahren or fe.STANDARD)))
        grad = fe.it_grad(g.toleranz, g.nenn) if g.nenn else None
        w.setToolTip(tr(SPALTEN_HILFE["Fertigung"]) + ("\n" + tr("Jetzige Toleranz: IT{}").format(grad) if grad else ""))
        if ist is not None and (ist.verfahren or fe.STANDARD) != (g.verfahren or fe.STANDARD):
            schrift = w.font()
            schrift.setBold(True)
            w.setFont(schrift)
        w.currentIndexChanged.connect(lambda _i, g=g, w=w: self._setze(g, "verfahren", w.currentData()))
        self.tabelle.setCellWidget(z, SP_FERTIGUNG, w)

    def _widgets(self, z: int, g, ist):
        """Verteilung, Cp bzw. Trapezform und Versatz als Eingabefelder; im Planspiel geaenderte fett."""
        t = self.tabelle
        art = QtWidgets.QComboBox()
        for schluessel, text in tk.VERTEILUNG.items():
            art.addItem(tr(text), schluessel)
        art.setCurrentIndex(max(0, art.findData(g.verteilung)))
        art.setToolTip(tr("Serie: normal (Toleranz = ±3σ · Cp); Kleinserie: Dreieck; Einzelteil: gleichverteilt; "
                          "Trapez: dazwischen; Betrag 1./2. Art: Form-, Lauf- und Positionsabweichungen ab 0 (schief)"))
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
        elif g.verteilung == "messwerte":
            feld = QtWidgets.QPushButton(tr("n = {}, σ = {:.4g} …").format(len(g.messwerte), g.sigma())
                                         if g.gemessen else tr("Messwerte …"))
            feld.setToolTip(tr("Messwerte eingeben oder laden: Mittelwert und Standardabweichung ergeben die "
                               "Verteilung"))
            feld.clicked.connect(lambda _c=False, g=g: self.messwerte_eingeben(g))
            name = "messwerte"
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
        versatz.setValue(g.wirk_versatz)
        if g.gemessen:  # aus den Messwerten
            versatz.setEnabled(False)
            versatz.setToolTip(tr("Mittelwert der Messwerte gegen die Toleranzmitte (mm)"))
        versatz.valueChanged.connect(lambda w, g=g: self._setze(g, "versatz", w))
        t.setCellWidget(z, SP_VERSATZ, versatz)
        faktor = QtWidgets.QDoubleSpinBox()
        faktor.setRange(0.001, 1000.0)
        faktor.setDecimals(3)
        faktor.setSingleStep(0.1)
        faktor.setToolTip(tr("Empfindlichkeit: wie stark das Glied auf das Schlussmaß wirkt (1 = direkt, z. B. 2 bei "
                             "einem Hebel 2:1)"))
        faktor.setValue(g.faktor)
        faktor.valueChanged.connect(lambda w, g=g: self._setze(g, "faktor", w))
        t.setCellWidget(z, SP_FAKTOR, faktor)
        if ist is not None:
            for w, feldname in ((art, "verteilung"), (feld, name), (versatz, "versatz"), (faktor, "faktor")):
                if getattr(g, feldname) != getattr(ist, feldname):
                    schrift = w.font()
                    schrift.setBold(True)
                    w.setFont(schrift)
                    w.setToolTip(tr("Ist: {}").format(getattr(ist, feldname)))

    def messwerte_eingeben(self, g, werte: list[float] | None = None) -> bool:
        """Dialog fuer die Messwerte des Glieds (werte: ohne Dialog setzen, fuer Tests)."""
        if werte is None:
            d = MesswerteDialog(g, self)
            if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return False
            werte = d.werte()
        self._setze(g, "messwerte", tuple(werte))
        QtCore.QTimer.singleShot(0, self._fuelle)
        return True

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

    def _grenze_gezogen(self, nr: int, wert: float):
        """Anforderungsgrenze im Histogramm gezogen: untere (0) oder obere (1) Grenze uebernehmen."""
        (self.unten if nr == 0 else self.oben).setValue(wert)

    def anforderung_werte(self):
        return (self.unten.value(), self.oben.value()) if self.anforderung.isChecked() else None

    def _rechne(self):
        anforderung = self.anforderung_werte()
        para = self._methode_parameter()
        self.e = tk.berechne(self.glieder, cp=self.cp.value(), anforderung=anforderung, **para)
        self.e_ist = tk.berechne(self._ist, cp=self._ist_cp, anforderung=anforderung, **para) \
            if self.im_planspiel else None
        temps = self.temperaturen()
        self.e_temp = [(t, tk.berechne(tk.thermisch(self.glieder, self._alpha(), t, self._je_teil(i)),
                                       cp=self.cp.value(), anforderung=anforderung, **para))
                       for i, t in enumerate(temps)] if temps and self.glieder else []
        for z, anteil in enumerate(self.e.anteile):
            it = self.tabelle.item(z, SP_ANTEIL)
            if it is not None:
                it.setData(QtCore.Qt.ItemDataRole.UserRole, anteil)
        for z, g in enumerate(self.glieder):
            it = self.tabelle.item(z, SP_STREUUNG)
            if it is not None:
                it.setData(QtCore.Qt.ItemDataRole.UserRole, streuung(g, self.cp.value()))
        self._zeige_ergebnis()
        self._zeige_histogramm()
        self._zeige_ampel()
        self._bild_senden()
        for k in (self.export, self.pdf):
            k.setEnabled(bool(self.glieder))
        self.plan_knopf.setEnabled(bool(self.glieder) and not self.im_planspiel)

    def _methode_parameter(self) -> dict:
        art = self.methode.currentData() if hasattr(self, "methode") else "rss"
        if art == "bender":
            return {"bender": self.methode_wert.value()}
        if art == "verschiebung":
            return {"verschiebung": self.methode_wert.value()}
        return {}

    def _werte(self, e, art: str) -> tuple[float, float]:
        if art == "wc":
            return e.wc_min, e.wc_max
        if art == "rss":
            halb = {"bender": e.bender, "verschiebung": e.verschiebung}.get(self.methode.currentData(), e.rss)
            return e.mitte - halb, e.mitte + halb
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
            if art == "rss" and self.methode.currentData() != "rss":
                text = self.methode.currentText() + (f" ({self.methode_wert.prefix()}{self.methode_wert.value():g})")
            name = ("✓ " if fett else "") + tr(text)
            if ist is None:
                zellen = [name, _z(lo), _z(hi), _z(hi - lo)]
            else:
                ilo, ihi = self._werte(ist, art)
                zellen = [name, f"{_z(ilo)} … {_z(ihi)}", f"{_z(lo)} … {_z(hi)}", _z((hi - lo) - (ihi - ilo), "+")]
            zeilen.append((zellen, fett))
        for t, et in self.e_temp:  # Waermeausdehnung: das anwendbare Verfahren bei jeder Grenztemperatur
            art = "rss" if et.statistisch else "wc"
            lo, hi = self._werte(et, art)
            name = tr("{} bei {:g} °C").format(tr(dict(self.ERGEBNIS_ZEILEN)[art]), t)
            if self._je_teil(self.e_temp.index((t, et))):
                name += " " + tr("(mit Bauteiltemperaturen)")
            zellen = [name, _z(lo), _z(hi), _z(hi - lo)] if ist is None else [name, "", f"{_z(lo)} … {_z(hi)}", ""]
            zeilen.append((zellen, False))
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
        hilfe = [VERFAHREN_HILFE[a] for a, _ in self.ERGEBNIS_ZEILEN] + [VERFAHREN_HILFE["temp"]] * len(self.e_temp)
        if self.e.cp is not None:
            hilfe += [VERFAHREN_HILFE["cpk"], VERFAHREN_HILFE["aus"]]
        for z, (zellen, fett) in enumerate(zeilen):
            for s, w in enumerate(zellen):
                it = QtWidgets.QTableWidgetItem(w)
                if z < len(hilfe):
                    it.setToolTip(tr(hilfe[z]) + ("\n\n" + tr("Klick: im Histogramm zeigen") if z < 3 else ""))
                if fett:
                    schrift = it.font()
                    schrift.setBold(True)
                    it.setFont(schrift)
                t.setItem(z, s, it)
        t.resizeColumnsToContents()
        inhalt = sum(t.columnWidth(s) for s in range(t.columnCount())) + 2 * t.frameWidth()
        t.setMaximumWidth(inhalt)
        t.setMinimumWidth(min(inhalt, 160))
        self.ampel.setMaximumWidth(max(inhalt, 320))
        self._ergebnis_hoehe()
        self._ampel_hoehe()
        e = self.e
        text = f"<b>{tr('Schlussmaß')}</b> {_z(e.nenn)} mm &nbsp; · &nbsp; {html.escape(tk.anwendbar_text(e))}"
        anforderung = self.anforderung_werte()
        bereich = tk.stellbereich(self.glieder, anforderung) if anforderung else None
        if bereich is not None:
            stell = next(g for g in self.glieder if g.stellglied)
            text += "<br>" + html.escape(
                tr("Stellglied {}: nötig {} … {} mm").format(stell.name, _z(bereich[0]), _z(bereich[1])) if
                bereich[0] <= bereich[1] else tr("Stellglied {}: Anforderung im Worst Case nicht einstellbar").format(
                    stell.name))
        ohne = [t for t in {g.teil for g in self.glieder if g.teil} if not self._alpha().get(t)]
        if self.e_temp and ohne:
            text += "<br>" + html.escape(tr("Ohne Werkstoff (keine Ausdehnung): {}").format(", ".join(sorted(ohne))))
        if self.e_ist is not None and self.e_ist.statistisch != e.statistisch:
            text += " &nbsp; · &nbsp; " + html.escape(tr("Ist: {}").format(tk.anwendbar_text(self.e_ist)))
        if self.im_planspiel and self.kosten_hinweis:
            text += "<br>" + html.escape(self.kosten_hinweis)
        self.ergebnis.setText(text)
        QtCore.QTimer.singleShot(0, self._unten_hoehe)

    def speichere(self, pfad: str = "") -> str | None:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Toleranzkette speichern"), "toleranzkette.csv",
                                                            "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(tk.als_csv(self.glieder, self.e, self.cp.value()))
        return pfad
