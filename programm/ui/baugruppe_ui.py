"""Leiste Zusammenbau: Teile per Flaechenpaar fangen, Verbindungen, offene Freiheitsgrade und Wiggle; Messgroessen
(Spalt, Buendigkeit) mit Worst Case, Monte Carlo und Beitragenden."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import baugruppe_mass as bm
from ..kern import verbindung as vb
from . import thema
from .tabellen import aenderbar_machen, leer_hinweis, spalten_anpassen


def _tabelle(spalten) -> QtWidgets.QTableWidget:
    t = QtWidgets.QTableWidget(0, len(spalten))
    t.setHorizontalHeaderLabels([tr(s) for s in spalten])
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setStretchLastSection(True)
    return t


AMPEL = {"gruen": "#2e9e48", "gelb": "#c99400", "rot": "#c0392b"}  # Bewertung der Messgroessen

class BaugruppePanel(QtWidgets.QWidget):
    verbinden = QtCore.Signal(float)  # Versatz in mm
    verbinden_321 = QtCore.Signal(float)  # 3-2-1-Vorlage aus sechs gewaehlten Ebenen
    entfernen = QtCore.Signal(int)  # Nummer der Verbindung
    zuruecksetzen = QtCore.Signal()
    wiggle = QtCore.Signal(object)  # Knotennummer oder None (aus)
    toleranz = QtCore.Signal(int, float)  # Nummer der Verbindung, neuer Spielraum (mm)
    umkehren = QtCore.Signal(int)  # Nummer der Verbindung
    frei_bewegen = QtCore.Signal(list)  # Werte je offenem Freiheitsgrad (mm bzw. Grad) fuer das gewaehlte Teil
    frei_zurueck = QtCore.Signal()
    tauschen = QtCore.Signal(int)
    mass_anlegen = QtCore.Signal()
    mass_entfernen = QtCore.Signal(int)  # Nummer der Messgroesse
    neu_rechnen = QtCore.Signal()  # Temperatur oder Werkstoffe geaendert
    soll = QtCore.Signal(int, str)  # Nummer der Messgroesse, Soll-Text
    mass_pdf = QtCore.Signal()
    mass_kette = QtCore.Signal(int)  # Nummer der Messgroesse als 3D-Kette
    hinzufuegen = QtCore.Signal()  # weitere Datei ins Modell aufnehmen

    VERBINDUNG_SPALTEN = ("Nr", "Teil", "Gegenteil", "Art", "Versatz", "Erfüllt", "Spielraum", "Herkunft")
    TEIL_SPALTEN = ("Teil", "Freiheitsgrade", "Lagestreuung X/Y/Z", "Offene Bewegungen")
    WIGGLE_ART = (("frei", "Freie Freiheitsgrade"), ("toleranz", "Innerhalb der Toleranzen"))
    MASS_SPALTEN = ("Nr", "Messgröße", "Nennwert", "Worst Case", "Monte Carlo (99,73 %)", "Soll", "Außerhalb", "Cpk",
                    "Δ Wärme", "Bewertung")
    BEITRAG_SPALTEN = ("Verbindung", "Art", "Bereich", "Anteil Worst Case", "Anteil statistisch")

    def __init__(self, parent=None):
        super().__init__(parent)
        aussen = QtWidgets.QVBoxLayout(self)
        aussen.setContentsMargins(0, 0, 0, 0)
        self.reiter = QtWidgets.QTabWidget()
        self.reiter.setDocumentMode(True)
        aussen.addWidget(self.reiter)
        seite = QtWidgets.QWidget()
        self.reiter.addTab(seite, tr("Verbindungen"))
        lay = QtWidgets.QVBoxLayout(seite)
        lay.setContentsMargins(6, 6, 6, 6)
        hinweis = QtWidgets.QLabel(tr("Erst eine Fläche am Teil wählen, das sich bewegen soll, dann mit Strg/⌘ die "
                                      "Gegenfläche am anderen Teil: zwei Ebenen liegen aufeinander, zwei Zylinder "
                                      "sind koaxial, Zylinder auf Ebene ist ein Bolzen im Langloch, Kugel auf Ebene "
                                      "ein Punktkontakt, zwei Kugeln ein Kugelgelenk. Die Freiheitsgrade zeigen, was "
                                      "noch offen ist.") + " " +
                                   tr("Teile lassen sich auch im 3D mit der linken Maustaste ziehen (klassische "
                                      "Navigation: mit Alt): nur in den offenen Freiheitsgraden, an passenden "
                                      "Flächen rastet das Teil ein, Loslassen verbindet."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.hinzufuegen_knopf = QtWidgets.QPushButton(tr("Modell hinzufügen …"))
        self.hinzufuegen_knopf.setToolTip(tr("Weitere Datei als zusätzliche Teile aufnehmen; sie liegt zunächst neben "
                                             "dem Modell und wird dann hier verbunden"))
        self.hinzufuegen_knopf.clicked.connect(self.hinzufuegen.emit)
        reihe.addWidget(self.hinzufuegen_knopf)
        reihe.addStretch(1)
        lay.addLayout(reihe)
        reihe = QtWidgets.QHBoxLayout()
        reihe.addWidget(QtWidgets.QLabel(tr("Versatz")))
        self.versatz = QtWidgets.QDoubleSpinBox()
        self.versatz.setRange(-1000.0, 1000.0)
        self.versatz.setDecimals(3)
        self.versatz.setSuffix(" mm")
        self.versatz.setToolTip(tr("Abstand zwischen zwei Ebenen (0: Berührung)"))
        reihe.addWidget(self.versatz)
        self.knopf = QtWidgets.QPushButton(tr("Verbinden"))
        self.knopf.setObjectName("primaer")
        self.knopf.setToolTip(tr("Gewählte Flächen der beiden Teile verbinden: das zweite Teil rastet am ersten ein"))
        self.knopf.clicked.connect(lambda: self.verbinden.emit(self.versatz.value()))
        reihe.addWidget(self.knopf)
        self.knopf_321 = QtWidgets.QPushButton(tr("3-2-1"))
        self.knopf_321.setToolTip(tr("3-2-1-Vorlage: sechs Ebenen paarweise wählen (Teil, Gegenstück) – primär, "
                                     "sekundär, tertiär; das Teil wird in einem Schritt bestimmt"))
        self.knopf_321.clicked.connect(lambda: self.verbinden_321.emit(self.versatz.value()))
        reihe.addWidget(self.knopf_321)
        reihe.addStretch(1)  # Knoepfe so breit wie ihr Text, nicht ueber die ganze Leiste
        lay.addLayout(reihe)
        self.verbindungen = _tabelle(self.VERBINDUNG_SPALTEN)
        leer_hinweis(self.verbindungen, tr("Noch keine Verbindung – eine Fläche am Teil wählen, das sich bewegen soll, "
                                           "mit Strg/⌘ die Gegenfläche, dann „Verbinden“"))
        aenderbar_machen(self.verbindungen)  # Spielraum: getoent, ein Klick
        self.verbindungen.setToolTip(tr("Spielraum per Doppelklick ändern: eben, Langloch und Punkt ± entlang der "
                                        "Normalen, koaxial und Kugel radiales Spiel (mm)"))
        self.verbindungen.itemChanged.connect(self._spielraum_geaendert)
        lay.addWidget(self.verbindungen, 1)
        reihe = QtWidgets.QHBoxLayout()
        self.weg = QtWidgets.QPushButton(tr("Verbindung entfernen"))
        self.weg.setToolTip(tr("Gewählte Verbindung löschen; das Teil bleibt an seiner Stelle"))
        self.weg.clicked.connect(self._entfernen)
        self.umkehr_knopf = QtWidgets.QPushButton(tr("Umkehren"))
        self.umkehr_knopf.setToolTip(tr("Bewegtes Teil an der gewählten Verbindung um 180° drehen: Zylinder Ende gegen "
                                        "Ende, auf einer Ebene halb herum"))
        self.umkehr_knopf.clicked.connect(lambda: self._fuer_gewaehlte(self.umkehren))
        self.tausch_knopf = QtWidgets.QPushButton(tr("Teile tauschen"))
        self.tausch_knopf.setToolTip(tr("Das andere Teil der gewählten Verbindung bewegt sich (Bezugsteil wechselt)"))
        self.tausch_knopf.clicked.connect(lambda: self._fuer_gewaehlte(self.tauschen))
        self.zurueck = QtWidgets.QPushButton(tr("Zurücksetzen"))
        self.zurueck.setToolTip(tr("Alle Verbindungen entfernen, Teile wieder wie in der Datei"))
        self.zurueck.clicked.connect(self.zuruecksetzen.emit)
        reihe.addWidget(self.weg)
        reihe.addWidget(self.umkehr_knopf)
        reihe.addWidget(self.tausch_knopf)
        reihe.addStretch(1)
        reihe.addWidget(self.zurueck)
        lay.addLayout(reihe)
        self.teile = _tabelle(self.TEIL_SPALTEN)
        self.teile.itemSelectionChanged.connect(self._teil_gewaehlt)
        lay.addWidget(self.teile, 1)
        self.bewegen_box = QtWidgets.QGroupBox(tr("Teil bewegen – nur in offenen Freiheitsgraden"))
        self.bewegen_box.setToolTip(tr("Verschiebt bzw. dreht das gewählte Teil nur so, wie seine Verbindungen es "
                                       "erlauben; die Verbindungen bleiben erfüllt"))
        self._bewegen_lay = QtWidgets.QFormLayout(self.bewegen_box)
        self._frei_felder: list[QtWidgets.QDoubleSpinBox] = []
        self.bewegen_box.hide()
        lay.addWidget(self.bewegen_box)
        reihe = QtWidgets.QHBoxLayout()
        self.wiggle_an = thema.nur_symbol(QtWidgets.QPushButton())  # nur Symbol: Abspielen / Anhalten
        self.wiggle_an.setCheckable(True)
        self._wiggle_symbol(False)
        self.wiggle_an.toggled.connect(self._wiggle_symbol)  # Zustand sichtbar
        self.wiggle_an.toggled.connect(self._teil_gewaehlt)
        self.wiggle_art = QtWidgets.QComboBox()
        self.wiggle_art.setToolTip(tr("Wie bewegt wird: freie Freiheitsgrade oder innerhalb der Toleranzen bis zu den "
                                      "Grenzlagen"))
        for schluessel, text in self.WIGGLE_ART:
            self.wiggle_art.addItem(tr(text), schluessel)
        self.wiggle_art.currentIndexChanged.connect(self._teil_gewaehlt)
        self.faktor = QtWidgets.QDoubleSpinBox()
        self.faktor.setRange(1.0, 1000.0)
        self.faktor.setValue(10.0)
        self.faktor.setPrefix("× ")
        self.faktor.setToolTip(tr("Überhöhung der Bewegung innerhalb der Toleranzen (1 = wahre Größe)"))
        self.weg_mm = QtWidgets.QDoubleSpinBox()
        self.weg_mm.setToolTip(tr("Wiggle der freien Freiheitsgrade: Weg je Verschiebung"))
        self.weg_mm.setRange(0.1, 1000.0)
        self.weg_mm.setValue(5.0)
        self.weg_mm.setSuffix(" mm")
        self.winkel = QtWidgets.QDoubleSpinBox()
        self.winkel.setToolTip(tr("Wiggle der freien Freiheitsgrade: Winkel je Drehung"))
        self.winkel.setRange(1.0, 180.0)
        self.winkel.setValue(15.0)
        self.winkel.setSuffix(" °")
        reihe.addWidget(self.wiggle_an)
        reihe.addWidget(self.wiggle_art)
        reihe.addWidget(self.faktor)
        reihe.addWidget(QtWidgets.QLabel(tr("Weg")))
        reihe.addWidget(self.weg_mm)
        reihe.addWidget(QtWidgets.QLabel(tr("Winkel")))
        reihe.addWidget(self.winkel)
        reihe.addStretch(1)
        lay.addLayout(reihe)
        self._nummern: list[int] = []
        self._teil_nummern: list[int] = []
        self._mass_nummern: list[int] = []
        self._ergebnisse: dict = {}
        self._baue_masse()
        self.zeige(vb.Baugruppe(), {})

    def _wiggle_symbol(self, an: bool):
        """Abspielen- bzw. Anhalten-Symbol ohne Text; der Tooltip sagt, was ein Klick tut."""
        self.wiggle_an.setIcon(thema.symbol("anhalten" if an else "abspielen"))
        self.wiggle_an.setToolTip(tr("Wiggle anhalten") if an else
                                  tr("Wiggle: gewähltes Teil in seinen offenen Freiheitsgraden hin und her bewegen"))

    def _baue_masse(self):
        seite = QtWidgets.QWidget()
        self.reiter.addTab(seite, tr("Messgrößen"))
        lay = QtWidgets.QVBoxLayout(seite)
        lay.setContentsMargins(6, 6, 6, 6)
        hinweis = QtWidgets.QLabel(tr("Zwei parallele Ebenen an verschiedenen Teilen wählen (erst die gemessene, dann "
                                      "mit Strg/⌘ die Bezugsfläche): gegenüberliegend ergibt einen Spalt, "
                                      "gleichgerichtet eine Bündigkeit. Alle Verbindungen streuen in ihren "
                                      "Spielräumen; Soll per Doppelklick, z. B. 3,8 … 4,2."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.mass_knopf = QtWidgets.QPushButton(tr("Messgröße aus Auswahl"))
        self.mass_knopf.setObjectName("primaer")
        self.mass_knopf.setToolTip(tr("Messgröße (Spalt, Bündigkeit, Abstand) aus den gewählten Flächen zweier Teile "
                                      "anlegen"))
        self.mass_knopf.clicked.connect(self.mass_anlegen.emit)
        self.mass_weg = QtWidgets.QPushButton(tr("Entfernen"))
        self.mass_weg.setToolTip(tr("Gewählte Messgröße entfernen"))
        self.mass_weg.clicked.connect(self._mass_entfernen)
        self.mass_pdf_knopf = QtWidgets.QPushButton(tr("Als PDF …"))
        self.mass_pdf_knopf.setToolTip(tr("Bericht der Messgrößen mit Histogramm und Beitragsleistern als PDF"))
        self.mass_pdf_knopf.clicked.connect(self.mass_pdf.emit)
        self.am_punkt = QtWidgets.QCheckBox(tr("am Klickpunkt"))
        self.am_punkt.setToolTip(tr("Statt in der Flächenmitte am angeklickten Punkt der gemessenen Fläche messen "
                                    "(beliebige Fläche zur Ebene oder Achse der Bezugsfläche), z. B. den Spalt an "
                                    "einer Ecke"))
        reihe.addWidget(self.mass_knopf)
        reihe.addWidget(self.am_punkt)
        self.mass_kette_knopf = QtWidgets.QPushButton(tr("Als 3D-Kette"))
        self.mass_kette_knopf.setToolTip(tr("Gewählte Messgröße als 3D-Toleranzkette öffnen: je Teil auf dem "
                                            "Verbindungsweg ein Glied mit seinen Spielräumen, zum Bearbeiten und "
                                            "Übernehmen in die Toleranzkette"))
        self.mass_kette_knopf.clicked.connect(lambda: (nr := self.gewaehlte_messgroesse()) and
                                              self.mass_kette.emit(nr))
        reihe.addStretch(1)
        lay.addLayout(reihe)
        waerme = QtWidgets.QHBoxLayout()
        self.waerme = QtWidgets.QCheckBox(tr("Wärmeausdehnung bei"))
        self.waerme.setToolTip(tr("Messgrößen zusätzlich bei einer Betriebstemperatur: jedes Teil dehnt sich um seinen "
                                  "Fixierpunkt (Mitte seiner Verbindungen) mit dem Ausdehnungskoeffizienten seines "
                                  "Werkstoffs; Bezug 20 °C"))
        self.temperatur = QtWidgets.QDoubleSpinBox()
        self.temperatur.setRange(-273.0, 1000.0)
        self.temperatur.setDecimals(1)
        self.temperatur.setSuffix(" °C")
        self.temperatur.setValue(80.0)
        self.temperatur.setToolTip(tr("Temperatur aller Teile im Betrieb"))
        self.werkstoff_knopf = QtWidgets.QPushButton(tr("Werkstoffe …"))
        self.werkstoff_knopf.setToolTip(tr("Ausdehnungskoeffizient je Teil (vorbelegt aus der STEP-Datei)"))
        self.werkstoff_knopf.clicked.connect(self._werkstoffe_dialog)
        self.waerme.toggled.connect(lambda _an: self.neu_rechnen.emit())
        self.temperatur.editingFinished.connect(lambda: self.waerme.isChecked() and self.neu_rechnen.emit())
        for w in (self.waerme, self.temperatur, self.werkstoff_knopf):
            waerme.addWidget(w)
        waerme.addStretch(1)
        lay.addLayout(waerme)
        self.alpha: dict[int, float] = {}  # Teil (Knotennummer) -> 1e-6/K
        self.teil_namen: dict[int, str] = {}
        self.masse = _tabelle(self.MASS_SPALTEN)
        leer_hinweis(self.masse, tr("Noch keine Messgröße – zwei Flächen an verschiedenen Teilen wählen, dann "
                                    "„Messgröße aus Auswahl“"))
        aenderbar_machen(self.masse)  # Soll: getoent, ein Klick
        self.masse.itemChanged.connect(self._soll_geaendert)
        self.masse.itemSelectionChanged.connect(self._zeige_beitraege)
        self.masse.itemSelectionChanged.connect(
            lambda: self.mass_kette_knopf.setEnabled(self.gewaehlte_messgroesse() is not None))
        self.mass_kette_knopf.setEnabled(False)
        lay.addWidget(self.masse, 1)
        titel = QtWidgets.QLabel(tr("Beitragende der gewählten Messgröße"))
        titel.setObjectName("leise")
        lay.addWidget(titel)
        self.beitraege = _tabelle(self.BEITRAG_SPALTEN)
        self.beitraege.setToolTip(tr("Bereich: Worst-Case-Breite, wenn nur diese Verbindung streut; statistisch: "
                                     "Varianzanteil aus Monte Carlo. Bonus Ⓜ/Ⓛ: Spielraum, der mit der Abweichung "
                                     "der Istmaße vom MMC/LMC wächst (eigener Beitragender)"))
        lay.addWidget(self.beitraege, 1)
        self.mass_hinweis = QtWidgets.QLabel("")
        self.mass_hinweis.setWordWrap(True)
        lay.addWidget(self.mass_hinweis)
        unten = QtWidgets.QHBoxLayout()  # Nebenbefehle und Export unten (einheitlicher Panel-Aufbau)
        for w in (self.mass_weg, self.mass_kette_knopf):
            unten.addWidget(w)
        unten.addStretch(1)
        unten.addWidget(self.mass_pdf_knopf)
        lay.addLayout(unten)

    def zeige_masse(self, baugruppe: vb.Baugruppe, namen: dict[int, str], ergebnisse: dict):
        """ergebnisse: Nummer der Messgroesse -> baugruppe_mass.Ergebnis."""
        self._ergebnisse = ergebnisse
        self._arten = {v.nummer: v.art for v in baugruppe.verbindungen}
        t = self.masse
        alt = self.gewaehlte_messgroesse()
        t.blockSignals(True)
        t.setRowCount(len(baugruppe.masse))
        self._mass_nummern = [m.nummer for m in baugruppe.masse]
        for z, m in enumerate(baugruppe.masse):
            e = ergebnisse.get(m.nummer)
            werte = [str(m.nummer), bm.text(m, namen)]
            if e is None:
                werte += [""] * 3
            else:
                werte += [f"{e.nenn:.4f}", f"{e.wc_min:.4f} … {e.wc_max:.4f}", f"{e.mc_min:.4f} … {e.mc_max:.4f}"]
            werte.append(bm.soll_text(m))
            werte.append("" if e is None or e.aussen is None else f"{e.aussen:.2%}")
            werte.append("" if e is None or e.cpk is None else f"{e.cpk:.2f}")
            werte.append("" if e is None or e.waerme is None else f"{e.waerme:+.4f}")
            stufe, grund = bm.bewertung(e, m) if e is not None else ("", "")
            werte.append({"gruen": "● " + tr("eingehalten"), "gelb": "● " + tr("knapp"),
                          "rot": "● " + tr("nicht eingehalten")}.get(stufe, ""))
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s != 5:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 6 and e is not None and e.aussen:
                    it.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                if s == len(werte) - 1 and stufe:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(AMPEL[stufe])))
                    it.setToolTip(grund)
                t.setItem(z, s, it)
        t.blockSignals(False)
        spalten_anpassen(t, strecken=True)
        if alt in self._mass_nummern:
            t.selectRow(self._mass_nummern.index(alt))
        elif self._mass_nummern:
            t.selectRow(len(self._mass_nummern) - 1)
        for k in (self.mass_weg, self.mass_pdf_knopf):
            k.setEnabled(bool(baugruppe.masse))
        self._zeige_beitraege()

    def _werkstoffe_dialog(self):
        """Ausdehnungskoeffizient je Teil eintragen (1e-6/K)."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(tr("Werkstoffe"))
        form = QtWidgets.QFormLayout(d)
        felder = {}
        for nr, name in sorted(self.teil_namen.items(), key=lambda x: x[1]):
            f = QtWidgets.QDoubleSpinBox()
            f.setRange(0.0, 500.0)
            f.setDecimals(1)
            f.setSuffix(" ·10⁻⁶/K")
            f.setValue(self.alpha.get(nr, 0.0))
            f.setToolTip(tr("Ausdehnungskoeffizient α (Stahl 11,5, Aluminium 23, Messing 19, PA6 80)"))
            form.addRow(name, f)
            felder[nr] = f
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(d.accept)
        knoepfe.rejected.connect(d.reject)
        form.addRow(knoepfe)
        if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.alpha.update({nr: f.value() for nr, f in felder.items()})
            if self.waerme.isChecked():
                self.neu_rechnen.emit()

    def gewaehlte_messgroesse(self):
        zeilen = {i.row() for i in self.masse.selectedIndexes()}
        return self._mass_nummern[zeilen.pop()] if len(zeilen) == 1 else None

    def _zeige_beitraege(self):
        e = self._ergebnisse.get(self.gewaehlte_messgroesse())
        t = self.beitraege
        liste = e.beitraege if e is not None else []
        t.setRowCount(len(liste))
        for z, b in enumerate(liste):
            werte = (str(b.verbindung), bm.beitrag_art(b, self._arten), f"{b.bereich:.4f}", f"{b.anteil_wc:.0%}",
                     f"{b.anteil_var:.0%}")
            for s, w in enumerate(werte):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        spalten_anpassen(t, strecken=True)
        if e is None:
            self.mass_hinweis.setText("")
        elif e.unbestimmt:
            self.mass_hinweis.setText(tr("Die Messgröße hängt von offenen Freiheitsgraden ab: diese bleiben in "
                                         "Nennlage – erst die Teile vollständig verbinden."))
        else:
            self.mass_hinweis.setText(tr("Mittelwert {:.4f} mm, σ {:.4f} mm").format(e.mittel, e.std))

    def _soll_geaendert(self, it):
        if it.column() == 5 and it.row() < len(self._mass_nummern):
            self.soll.emit(self._mass_nummern[it.row()], it.text())

    def _mass_entfernen(self):
        nr = self.gewaehlte_messgroesse()
        if nr is not None:
            self.mass_entfernen.emit(nr)

    def zeige(self, baugruppe: vb.Baugruppe, namen: dict[int, str], streuung: dict | None = None):
        """streuung: Knotennummer -> (Verschiebung X/Y/Z in mm, freie Freiheitsgrade)."""
        verletzt = {v.nummer for v in baugruppe.verletzt()}
        streuung = streuung or {}
        t = self.verbindungen
        t.blockSignals(True)
        t.setRowCount(len(baugruppe.verbindungen))
        self._nummern = [v.nummer for v in baugruppe.verbindungen]
        for z, v in enumerate(baugruppe.verbindungen):
            werte = (str(v.nummer), namen.get(v.teil, str(v.teil)), namen.get(v.gegen_teil, str(v.gegen_teil)),
                     tr(vb.ART_TEXT[v.art]), f"{v.versatz:g}" if v.art in vb.MIT_VERSATZ else "",
                     tr("nein") if v.nummer in verletzt else tr("ja"),
                     (f"±{v.toleranz:.4g}" if v.art in vb.MIT_VERSATZ else f"{v.toleranz:.4g}"),
                     " ".join(x for x in (v.quelle, vb.bonus_text(v)) if x))
            for s, w in enumerate(werte):
                it = QtWidgets.QTableWidgetItem(w)
                if s == 6 and v.bonus > 0:
                    it.setToolTip(tr("Spielraum ohne Bonus; dazu kommt der Ⓜ/Ⓛ-Bonus {:.4g} (Bezugsverschiebung), "
                                     "voll genutzt im Worst Case").format(v.bonus))
                if s != 6:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 5 and v.nummer in verletzt:
                    it.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                t.setItem(z, s, it)
        t.blockSignals(False)
        spalten_anpassen(t, strecken=True)
        teile = baugruppe.teile()
        self._teil_nummern = teile
        t = self.teile
        t.blockSignals(True)
        t.setRowCount(len(teile))
        for z, nr in enumerate(teile):
            if baugruppe.fest(nr):
                werte = (namen.get(nr, str(nr)), "–", "", tr("fest (Bezugsteil)"))
            else:
                basis = baugruppe.freiheitsgrade(nr)
                texte = vb.beschreibe(basis)
                weg = streuung.get(nr)
                lage = "" if weg is None else "±" + " / ".join(f"{x:.3f}" for x in weg[0])
                werte = (namen.get(nr, str(nr)), str(len(basis)), lage, "; ".join(texte) if texte else tr("bestimmt"))
            for s, w in enumerate(werte):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        t.blockSignals(False)
        spalten_anpassen(t, strecken=True)
        for k in (self.weg, self.zurueck, self.umkehr_knopf, self.tausch_knopf):
            k.setEnabled(bool(baugruppe.verbindungen))
        self.wiggle_an.setEnabled(bool(teile))

    def _spielraum_geaendert(self, it):
        if it.column() != 6 or it.row() >= len(self._nummern):
            return
        try:
            wert = abs(float(it.text().replace("±", "").replace(",", ".")))
        except ValueError:
            return
        self.toleranz.emit(self._nummern[it.row()], wert)

    def _entfernen(self):
        self._fuer_gewaehlte(self.entfernen)

    def _fuer_gewaehlte(self, signal):
        zeilen = {i.row() for i in self.verbindungen.selectedIndexes()}
        if len(zeilen) == 1:
            signal.emit(self._nummern[zeilen.pop()])

    def gewaehltes_teil(self):
        zeilen = {i.row() for i in self.teile.selectedIndexes()}
        return self._teil_nummern[zeilen.pop()] if len(zeilen) == 1 else None

    def _teil_gewaehlt(self, *_):
        self.wiggle.emit(self.gewaehltes_teil() if self.wiggle_an.isChecked() else None)

    def zeige_freiheitsgrade(self, texte: list[str], drehung: list[bool]):
        """Je offenem Freiheitsgrad ein Feld (mm bzw. Grad); leer blendet die Gruppe aus."""
        while self._bewegen_lay.rowCount():
            self._bewegen_lay.removeRow(0)
        self._frei_felder = []
        for text, dreht in zip(texte, drehung):
            feld = QtWidgets.QDoubleSpinBox()
            feld.setRange(-360.0, 360.0) if dreht else feld.setRange(-10000.0, 10000.0)
            feld.setDecimals(2 if dreht else 3)
            feld.setSingleStep(5.0 if dreht else 0.5)
            feld.setSuffix(" °" if dreht else " mm")
            feld.valueChanged.connect(lambda _w: self.frei_bewegen.emit([f.value() for f in self._frei_felder]))
            self._frei_felder.append(feld)
            self._bewegen_lay.addRow(text, feld)
        if texte:
            zurueck = QtWidgets.QPushButton(tr("Zurück zur Ausgangslage"))
            zurueck.clicked.connect(self._frei_zuruecksetzen)
            self._bewegen_lay.addRow("", zurueck)
        self.bewegen_box.setVisible(bool(texte))

    def _frei_zuruecksetzen(self):
        for f in self._frei_felder:
            f.blockSignals(True)
            f.setValue(0.0)
            f.blockSignals(False)
        self.frei_zurueck.emit()
