"""Fenster 3D-Toleranzkette: Glieder (Lagen) als Liste, gefuehrter Editor je Glied (sechs Komponenten mit Nennwert
und Abmassen), Funktionspunkt und Schlussgroesse per Auswahl; Ergebnis linear und nichtlinear, Anzeige im Modell und
Uebernahme in das 1D-Kettenfenster (kern.kette3d)."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import kette3d as k3
from ..kern import toleranzkette as tk
from .tabellen import zahlen_rechts, zeilen_hoehe
from .werkstoff_wahl import WaermeZeile, werkstoff_feld, werkstoff_wert

VORLAGEN = {
    "turm": ("Sockel mit Arm (Kippung wirkt als Hebel)",
             lambda: k3.Kette3D([k3.glied("Sockel", z=(20, 0.05, -0.05), rx=(0, 0.05, -0.05), ry=(0, 0.05, -0.05)),
                                 k3.glied("Arm", x=(100, 0.1, -0.1), rz=(90, 0.1, -0.1))], schluss="z")),
    "stapel": ("Drei Platten gestapelt, Punkt auf dem Deckel",
               lambda: k3.Kette3D([k3.glied("Grundplatte", z=(10, 0.05, -0.05), rx=(0, 0.02, -0.02),
                                            ry=(0, 0.02, -0.02)),
                                   k3.glied("Zwischenplatte", x=(0, 0.1, -0.1), y=(0, 0.1, -0.1),
                                            z=(15, 0.05, -0.05), rx=(0, 0.02, -0.02), ry=(0, 0.02, -0.02)),
                                   k3.glied("Deckel", x=(40, 0.05, -0.05), z=(8, 0.05, -0.05),
                                            rz=(0, 0.05, -0.05))],
                                  punkt=(0, 0, 0), schluss="z")),
}
SPALTEN_EDITOR = (("Nennwert", "Nennwert der Komponente (mm bzw. Grad)"),
                  ("oben", "Oberes Abmaß (mm bzw. Grad)"), ("unten", "Unteres Abmaß (mm bzw. Grad)"))


class Kette3DFenster(QtWidgets.QDialog):
    uebernehmen = QtCore.Signal(list)  # linearisierte Glieder fuer das 1D-Kettenfenster
    zeigen = QtCore.Signal(object)  # Linien fuer die 3D-Ansicht (wie Kettenbild) oder None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("3D-Toleranzkette"))
        self.resize(1100, 600)
        self.kette = k3.Kette3D()
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Jedes Glied ist eine Lage relativ zum vorigen (z. B. Bauteil auf Bauteil): "
                                      "Verschiebung und Drehung mit Abmaßen. Am Ende sitzt der Funktionspunkt; die "
                                      "Schlussgröße wird linearisiert und nichtlinear per Monte Carlo geprüft."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.plus = QtWidgets.QPushButton(tr("＋ Glied"))
        self.plus.setToolTip(tr("Glied (Lage) anhängen – Werte unten im Editor eintragen"))
        self.plus.clicked.connect(lambda: self.neues_glied())
        self.weg = QtWidgets.QPushButton(tr("－ Entfernen"))
        self.weg.setToolTip(tr("Gewähltes Glied entfernen"))
        self.weg.clicked.connect(self._entfernen)
        self.vorlage = QtWidgets.QComboBox()
        self.vorlage.addItem(tr("Vorlage …"), "")
        for schluessel, (name, _) in VORLAGEN.items():
            self.vorlage.addItem(tr(name), schluessel)
        self.vorlage.setToolTip(tr("Beispielkette laden, um die Eingabe kennenzulernen"))
        self.vorlage.activated.connect(lambda _i: self.lade_vorlage(self.vorlage.currentData()))
        self.oeffnen_knopf = QtWidgets.QPushButton(tr("Öffnen …"))
        self.oeffnen_knopf.setToolTip(tr("Gespeicherte {}-Kette laden").format("3D"))
        self.oeffnen_knopf.clicked.connect(lambda: self.oeffne())
        self.speichern_knopf = QtWidgets.QPushButton(tr("Speichern …"))
        self.speichern_knopf.setToolTip(tr("{}-Kette als Datei speichern (auch im Projekt enthalten)").format("3D"))
        self.speichern_knopf.clicked.connect(lambda: self.speichere())
        for w in (self.plus, self.weg, self.vorlage, self.oeffnen_knopf, self.speichern_knopf):
            reihe.addWidget(w)
        reihe.addStretch(1)
        lay.addLayout(reihe)
        mitte = QtWidgets.QHBoxLayout()
        self.liste = QtWidgets.QListWidget()
        self.liste.setToolTip(tr("Glieder in Kettenreihenfolge (Basis zuerst); Doppelklick benennt um"))
        self.liste.currentRowChanged.connect(self._glied_gewaehlt)
        self.liste.itemChanged.connect(self._umbenannt)
        mitte.addWidget(self.liste, 1)
        rechts = QtWidgets.QVBoxLayout()
        self.editor_titel = QtWidgets.QLabel("")
        rechts.addWidget(self.editor_titel)
        self.editor = QtWidgets.QTableWidget(len(k3.KOMPONENTEN), len(SPALTEN_EDITOR))
        self.editor.setHorizontalHeaderLabels([tr(n) for n, _ in SPALTEN_EDITOR])
        self.editor.setVerticalHeaderLabels([tr(k3.KOMPONENTEN_TEXT[c]) for c in k3.KOMPONENTEN])
        for i, (_, hilfe) in enumerate(SPALTEN_EDITOR):
            self.editor.horizontalHeaderItem(i).setToolTip(tr(hilfe))
        self.editor.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.editor.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        # nur Felder, keine Zellen: keine Auswahl- oder Fokusmarkierung hinter den Feldern
        self.editor.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.editor.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.editor.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._baue_felder()
        self._editor_hoehe()
        rechts.addWidget(self.editor)
        vert = QtWidgets.QHBoxLayout()
        vert.addWidget(QtWidgets.QLabel(tr("Verteilung des Glieds")))
        self.verteilung = QtWidgets.QComboBox()
        for schluessel, text in tk.VERTEILUNG.items():
            if schluessel != "messwerte":
                self.verteilung.addItem(tr(text), schluessel)
        self.verteilung.setToolTip(tr("Streuung aller Komponenten dieses Glieds in der Fertigung"))
        self.verteilung.currentIndexChanged.connect(self._verteilung_geaendert)
        vert.addWidget(self.verteilung, 1)
        rechts.addLayout(vert)
        stoff = QtWidgets.QHBoxLayout()
        stoff.addWidget(QtWidgets.QLabel(tr("Werkstoff des Glieds")))
        self.werkstoff = werkstoff_feld("", tr("wie Kette"), tr("Eigener Werkstoff dieses Glieds für die "
                                                                "Wärmeausdehnung der Verschiebungen; „wie Kette“: der "
                                                                "Werkstoff der Kette"))
        self.werkstoff.currentTextChanged.connect(self._werkstoff_geaendert)
        stoff.addWidget(self.werkstoff, 1)
        rechts.addLayout(stoff)
        rechts.addStretch(1)
        mitte.addLayout(rechts, 3)
        lay.addLayout(mitte, 1)
        form = QtWidgets.QGridLayout()
        self.schluss = QtWidgets.QComboBox()
        for schluessel, name in k3.SCHLUSS.items():
            self.schluss.addItem(tr(name), schluessel)
        self.schluss.setToolTip(tr("Welche Größe die Funktion bestimmt: Lage des Funktionspunkts in einer Richtung, "
                                   "sein Abstand zu einem Zielpunkt oder der Winkel seiner Richtung zu einer "
                                   "Zielrichtung"))
        self.schluss.currentIndexChanged.connect(self._schluss_geaendert)
        self.punkt = self._vektor(tr("Funktionspunkt im letzten Glied (mm)"), "punkt")
        self.richtung = self._vektor(tr("Richtung am Funktionspunkt (für den Winkel)"), "richtung")
        self.ziel = self._vektor(tr("Zielpunkt (Abstand) bzw. Zielrichtung (Winkel) in der Basis"), "ziel")
        for z, (text, w) in enumerate(((tr("Schlussgröße"), self.schluss), (tr("Funktionspunkt"), self.punkt),
                                       (tr("Richtung"), self.richtung), (tr("Ziel"), self.ziel))):
            form.addWidget(QtWidgets.QLabel(text), z // 2, (z % 2) * 2)
            form.addWidget(w, z // 2, (z % 2) * 2 + 1)
        lay.addLayout(form)
        self.waerme = WaermeZeile()
        self.waerme.geaendert.connect(self._waerme_geaendert)
        lay.addWidget(self.waerme)
        self.ergebnis = QtWidgets.QLabel("")
        self.ergebnis.setWordWrap(True)
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.ergebnis)
        knoepfe = QtWidgets.QHBoxLayout()
        self.im_modell = QtWidgets.QPushButton(tr("Im 3D zeigen"))
        self.im_modell.setCheckable(True)
        self.im_modell.setToolTip(tr("Lagen der Glieder als Linienzug mit Achsenkreuzen und den Funktionspunkt in der "
                                     "3D-Ansicht zeigen"))
        self.im_modell.toggled.connect(lambda an: (self.im_modell.setText(tr("Im 3D ausblenden") if an else
                                                                          tr("Im 3D zeigen")), self._zeigen()))
        self.in_kette = QtWidgets.QPushButton(tr("In Toleranzkette übernehmen"))
        self.in_kette.setObjectName("primaer")
        self.in_kette.setToolTip(tr("Linearisierte Kette (je tolerierte Komponente ein Glied mit ihrer Empfindlichkeit "
                                    "als Faktor) ins Fenster Toleranzkette: dort Anforderung, Ampel, Histogramm, "
                                    "Kostenoptimierung und Bericht"))
        self.in_kette.clicked.connect(lambda: self.uebernehmen.emit(k3.als_glieder(self.kette)))
        knoepfe.addWidget(self.im_modell)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.in_kette)
        lay.addLayout(knoepfe)
        self._fuelle()

    # --- Aufbau ---

    def _vektor(self, hilfe: str, attr: str) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        felder = []
        for i, achse in enumerate("XYZ"):
            f = QtWidgets.QDoubleSpinBox()
            f.setRange(-1e5, 1e5)
            f.setDecimals(3)
            f.setPrefix(f"{achse} ")
            f.setToolTip(hilfe)
            f.valueChanged.connect(lambda v, i=i, attr=attr: self._vektor_geaendert(attr, i, v))
            h.addWidget(f)
            felder.append(f)
        w.felder = felder
        return w

    def _setze_vektor(self, w, werte):
        for f, v in zip(w.felder, werte):
            f.blockSignals(True)
            f.setValue(float(v))
            f.blockSignals(False)

    # --- Bearbeiten ---

    def neues_glied(self, g: k3.Glied3D | None = None) -> k3.Glied3D:
        self.kette.glieder.append(g or k3.Glied3D(tr("Glied {}").format(len(self.kette.glieder) + 1)))
        self._fuelle()
        self.liste.setCurrentRow(len(self.kette.glieder) - 1)
        return self.kette.glieder[-1]

    def setze_kette(self, kette):
        """Kette uebernehmen (aus Datei oder Projekt)."""
        self.kette = kette
        self._fuelle()

    def speichere(self, pfad: str = "") -> str | None:
        from ..kern import kette_datei
        endung = kette_datei.ENDUNG_3D
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Kette speichern"), "kette" + endung,
                                                            tr("3D-Kette (*{})").format(endung))
        return kette_datei.speichere_raum(pfad, self.kette) if pfad else None

    def oeffne(self, pfad: str = "") -> bool:
        from ..kern import kette_datei
        endung = kette_datei.ENDUNG_3D
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Kette öffnen"), "",
                                                            tr("3D-Kette (*{})").format(endung))
        if not pfad:
            return False
        try:
            kette = kette_datei.lade_raum(pfad)
        except (OSError, ValueError, KeyError) as fehler:
            QtWidgets.QMessageBox.warning(self, tr("Kette öffnen"), str(fehler))
            return False
        if not isinstance(kette, k3.Kette3D):
            self.ergebnis.setText(tr("Diese Datei enthält eine andere Art von Kette."))
            return False
        self.setze_kette(kette)
        return True

    def lade_vorlage(self, schluessel: str):
        if not schluessel:
            return
        self.kette = VORLAGEN[schluessel][1]()
        self.vorlage.setCurrentIndex(0)
        self._fuelle()
        self.liste.setCurrentRow(0)

    def _entfernen(self):
        z = self.liste.currentRow()
        if 0 <= z < len(self.kette.glieder):
            del self.kette.glieder[z]
            self._fuelle()

    def _umbenannt(self, it):
        z = self.liste.row(it)
        if 0 <= z < len(self.kette.glieder):
            self.kette.glieder[z].name = it.text()
            self._rechne()

    def _verteilung_geaendert(self, *_):
        z = self.liste.currentRow()
        if 0 <= z < len(self.kette.glieder):
            self.kette.glieder[z].verteilung = self.verteilung.currentData()
            self._rechne()

    def _werkstoff_geaendert(self, *_):
        z = self.liste.currentRow()
        if 0 <= z < len(self.kette.glieder):
            self.kette.glieder[z].werkstoff = werkstoff_wert(self.werkstoff)
            self._rechne()

    def _waerme_geaendert(self):
        self.kette.werkstoff, self.kette.temperaturen = self.waerme.wert(), self.waerme.temperaturen()
        self._rechne()

    def _schluss_geaendert(self, *_):
        self.kette.schluss = self.schluss.currentData()
        self._rechne()

    def _vektor_geaendert(self, attr: str, i: int, v: float):
        werte = list(getattr(self.kette, attr))
        werte[i] = v
        setattr(self.kette, attr, tuple(werte))
        self._rechne()

    def _baue_felder(self):
        """Die 18 Zahlenfelder einmal anlegen; ein anderes Glied setzt nur ihre Werte (neue Felder je Wahl lagen
        bis zum Aufraeumen ueber den alten)."""
        self._felder = {}
        for r, c in enumerate(k3.KOMPONENTEN):
            dreh = c.startswith("r")
            for s, feld in enumerate(("nenn", "oben", "unten")):
                f = QtWidgets.QDoubleSpinBox()
                f.setRange(-360.0 if dreh else -1e5, 360.0 if dreh else 1e5)
                f.setDecimals(3)
                f.setSuffix(" °" if dreh else " mm")
                f.setToolTip(tr(k3.KOMPONENTEN_TEXT[c]) + " – " + tr(SPALTEN_EDITOR[s][1]))
                f.valueChanged.connect(lambda v, c=c, feld=feld: self._komponente_geaendert(c, feld, v))
                self.editor.setCellWidget(r, s, f)
                self._felder[c, feld] = f
        zahlen_rechts(self.editor)

    def _komponente_geaendert(self, c: str, feld: str, v: float):
        z = self.liste.currentRow()
        if 0 <= z < len(self.kette.glieder):
            setattr(self.kette.glieder[z].werte[c], feld, v)
            self._rechne()

    def _glied_gewaehlt(self, z: int):
        """Editor mit den sechs Komponenten des gewaehlten Glieds fuellen."""
        gewaehlt = 0 <= z < len(self.kette.glieder)
        self.editor.setEnabled(gewaehlt)
        if not gewaehlt:
            self.editor_titel.setText(tr("Kein Glied gewählt"))
            return
        g = self.kette.glieder[z]
        self.editor_titel.setText("<b>" + tr("Glied: {}").format(g.name) + "</b>")
        for (c, feld), f in self._felder.items():
            f.blockSignals(True)
            f.setValue(getattr(g.werte[c], feld))
            f.blockSignals(False)
        self.verteilung.blockSignals(True)
        self.verteilung.setCurrentIndex(max(0, self.verteilung.findData(g.verteilung)))
        self.verteilung.blockSignals(False)
        self.werkstoff.blockSignals(True)
        self.werkstoff.setCurrentText(g.werkstoff or self.werkstoff.itemText(0))
        self.werkstoff.blockSignals(False)

    def _editor_hoehe(self):
        """Editor genau so hoch wie seine sechs Zeilen; Zeilen so hoch wie die Zahlenfelder."""
        e = self.editor
        e.setFixedHeight(e.horizontalHeader().sizeHint().height() + len(k3.KOMPONENTEN) * zeilen_hoehe(e)
                         + 2 * e.frameWidth())

    def _fuelle(self):
        self.liste.blockSignals(True)
        zeile = self.liste.currentRow()
        self.liste.clear()
        for g in self.kette.glieder:
            it = QtWidgets.QListWidgetItem(g.name)
            it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            self.liste.addItem(it)
        self.liste.blockSignals(False)
        self.liste.setCurrentRow(min(max(zeile, 0), len(self.kette.glieder) - 1))
        self._glied_gewaehlt(self.liste.currentRow())
        self.schluss.blockSignals(True)
        self.schluss.setCurrentIndex(max(0, self.schluss.findData(self.kette.schluss)))
        self.schluss.blockSignals(False)
        for w, attr in ((self.punkt, "punkt"), (self.richtung, "richtung"), (self.ziel, "ziel")):
            self._setze_vektor(w, getattr(self.kette, attr))
        self.waerme.setze(self.kette.werkstoff, self.kette.temperaturen)
        self._rechne()

    # --- Ergebnis und Anzeige ---

    def ergebnisse(self, kette: k3.Kette3D | None = None) -> dict:
        """Wie die 2D-Kette; mit Grenztemperaturen dazu "temperaturen": [(T, Ergebnis bei T)]."""
        k = kette or self.kette
        if not k.glieder:
            return {}
        e = tk.berechne(k3.als_glieder(k), proben=20_000)
        mc = k3.monte_carlo(k, 3000)
        out = {"nenn": k3.schlussgroesse(k), "wc": (e.wc_min, e.wc_max), "rss": (e.mitte - e.rss, e.mitte + e.rss),
               "mc": tuple(float(x) for x in np.quantile(mc, [0.00135, 0.99865])),
               "empfindlichkeit": k3.empfindlichkeiten(k)}
        if kette is None and k.temperaturen:
            out["temperaturen"] = [(t, self.ergebnisse(k3.bei_temperatur(k, t))) for t in k.temperaturen]
        return out

    def _rechne(self):
        self.in_kette.setEnabled(bool(self.kette.glieder))
        self._zeigen()
        r = self.ergebnisse()
        if not r:
            self.ergebnis.setText(tr("Noch keine Glieder – „＋ Glied“ oder eine Vorlage wählen."))
            return
        einheit = "°" if self.kette.schluss == "winkel" else " mm"
        z = lambda a, b: f"{a:.4f} … {b:.4f}{einheit}"  # noqa: E731
        toleriert = {k: d for k, d in r["empfindlichkeit"].items()
                     if self.kette.glieder[k[0]].werte[k[1]].oben != self.kette.glieder[k[0]].werte[k[1]].unten}
        groesste = sorted(toleriert.items(), key=lambda kv: -abs(kv[1]))[:3]
        teile = ", ".join(f"{self.kette.glieder[i].name} ({tr(k3.KOMPONENTEN_TEXT[c])}) {d:+.3g}"
                          for (i, c), d in groesste if abs(d) > 1e-12)
        warnung = ""
        mc_breite = r["mc"][1] - r["mc"][0]
        if self.kette.schluss == "abstand" and abs(r["nenn"]) < max(mc_breite, 1e-6):
            warnung = "<br><span style='color:#c0392b'>" + tr(
                "Abstand am Nennwert fast 0: nicht linearisierbar (wie eine Positionsabweichung) – das nichtlineare "
                "Monte-Carlo-Ergebnis gilt; für die Kette X-, Y- und Z-Lage einzeln betrachten") + "</span>"
        self.ergebnis.setText(
            f"<b>{tr('Schlussgröße')}</b> {r['nenn']:.4f}{einheit} &nbsp;·&nbsp; "
            f"{tr('Worst Case')} {z(*r['wc'])} &nbsp;·&nbsp; RSS {z(*r['rss'])} &nbsp;·&nbsp; "
            f"{tr('Monte Carlo nichtlinear')} {z(*r['mc'])}<br>{tr('Größte Empfindlichkeiten')}: {teile}" + "".join(
                f"<br><b>{tr('Bei {} °C').format(f'{t:g}')}</b> {w['nenn']:.4f}{einheit} &nbsp;·&nbsp; "
                f"{tr('Worst Case')} {z(*w['wc'])} &nbsp;·&nbsp; {tr('Monte Carlo nichtlinear')} {z(*w['mc'])}"
                for t, w in r.get("temperaturen", [])) + warnung)

    def linien(self) -> list:
        """Linienzug der Glied-Ursprunge, Achsenkreuz je Lage (X rot, Y gruen, Z blau), Funktionspunkt."""
        if not self.kette.glieder:
            return []
        lagen = k3.lagen(self.kette)
        groesse = max(1.0, max(float(np.linalg.norm(t)) for _, t in lagen))
        a = 0.08 * groesse
        out, vorher = [], np.zeros(3)
        for g, (r, t) in zip(self.kette.glieder, lagen):
            if np.linalg.norm(t - vorher) > 1e-9:  # Glied ohne Versatz: nur Achsenkreuz, keine gestapelte Beschriftung
                out.append((tuple(vorher), tuple(t), g.name, (0.13, 0.42, 0.85), 3.0))
            for achse, farbe in ((0, (0.75, 0.22, 0.17)), (1, (0.18, 0.62, 0.28)), (2, (0.13, 0.42, 0.85))):
                out.append((tuple(t), tuple(t + r[:, achse] * a), "", farbe, 1.5))
            vorher = t
        p, _ = k3.funktionspunkt(self.kette)
        out.append((tuple(vorher), tuple(p), tr("Funktionspunkt"), (0.90, 0.55, 0.10), 2.0))
        if self.kette.basis is not None:  # Basis liegt im Modell (z. B. Bezugsebene einer Messgroesse)
            m = np.asarray(self.kette.basis, float)
            welt = lambda x: tuple(m[:3, :3] @ np.asarray(x, float) + m[:3, 3])  # noqa: E731
            out = [(welt(a), welt(b), *rest) for a, b, *rest in out]
        return out

    def _zeigen(self):
        self.zeigen.emit(self.linien() if self.im_modell.isChecked() else None)
