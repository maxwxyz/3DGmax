"""Sperrzustand als gewaehltes Rechenmodell mit Eingangs- und Abtriebsmomenten."""

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.differentialsperre import Sperrvorgabe


def _modellnamen():
    return {"offen": tr("Offen"), "gesperrt": tr("Formschlüssig gesperrt"), "tbr": tr("Teilgesperrt (TBR)"),
            "lamelle": tr("Lamellenkupplung (Seitenrad A–B)")}


def _momenttext(fall):
    bereiche = fall["seitenmomente_a_b"]
    if bereiche is not None:
        (lo, hi), (lo_b, hi_b) = bereiche
        if (lo, hi) != (lo_b, hi_b):
            return tr("A {:g} bis {:g} Nm, B {:g} bis {:g} Nm, zusammen {:g} Nm").format(
                lo, hi, lo_b, hi_b, fall["steg_antriebsmoment"])
        if lo == hi:
            return tr("Je Seite {:g} Nm").format(lo)
        return tr("Je Seite {:g} bis {:g} Nm, zusammen {:g} Nm").format(lo, hi, fall["steg_antriebsmoment"])
    if fall["status"] == "kupplungsmoment_fehlt":
        return tr("Maximales Kupplungsmoment zwischen A und B für diesen Betriebspunkt eingeben.")
    if fall["status"] == "lastabhaengig":
        return tr("Die Lastreaktionen bestimmen die Momentenaufteilung.")
    if fall["status"] == "drehzahlwiderspruch":
        return tr("Drehzahlvorgaben widersprechen sich.")
    return tr("Für die Momentenaufteilung das Steg-Antriebsmoment vorgeben.")


def _annahme(modell):
    if modell == "lamelle":
        return tr("Die Lamellenkupplung überträgt höchstens M_K zwischen den Seitenrädern A und B. "
                  "Im stationären Zugbetrieb mit zwei nichtnegativen Seitenmomenten gilt M_A + M_B = M_C "
                  "und |M_A − M_B| ≤ 2 M_K. Bei Schlupf wirkt Reibung der Relativdrehung entgegen.")
    return tr("Grenzen für stationären Zugbetrieb mit gleichgerichteten Abtriebsmomenten, ohne Vorspannung und äußeres "
              "Verlustmoment. Beide Seitenmomente ergeben zusammen das Stegmoment. Bei bekannter Differenzdrehzahl begrenzt passive Reibung das Moment der schnelleren Seite.")


class SperrenEditor(QtWidgets.QWidget):
    geaendert = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.vorgaben = {}
        self.stege = {}
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.satz = QtWidgets.QComboBox()
        lay.addWidget(self.satz)
        reihe = QtWidgets.QHBoxLayout()
        self.modell = QtWidgets.QComboBox()
        self.modell.setAccessibleName(tr("Sperrmodell im Betriebspunkt"))
        for key, name in _modellnamen().items():
            self.modell.addItem(name, key)
        reihe.addWidget(QtWidgets.QLabel(tr("Sperrmodell")))
        reihe.addWidget(self.modell)
        self.nutze_moment = QtWidgets.QCheckBox(tr("Steg-Antriebsmoment"))
        reihe.addWidget(self.nutze_moment)
        self.moment = QtWidgets.QDoubleSpinBox()
        self.moment.setAccessibleName(tr("Steg-Antriebsmoment"))
        self.moment.setDecimals(3)
        self.moment.setRange(0., 1e12)
        self.moment.setSuffix(" Nm")
        self.moment.setKeyboardTracking(False)
        reihe.addWidget(self.moment)
        self.tbr_label = QtWidgets.QLabel("TBR")
        self.tbr_label.setToolTip(tr("Maximales Verhältnis des höheren zum niedrigeren Seitenmoment im Zugbetrieb."))
        self.tbr = QtWidgets.QDoubleSpinBox()
        self.tbr.setAccessibleName("TBR")
        self.tbr.setRange(1., 1e4)
        self.tbr.setDecimals(3)
        self.tbr.setSingleStep(.25)
        self.tbr.setToolTip(self.tbr_label.toolTip())
        self.tbr.setKeyboardTracking(False)
        reihe.addWidget(self.tbr_label)
        reihe.addWidget(self.tbr)
        self.lamelle_label = QtWidgets.QLabel(tr("M_K max."))
        self.lamelle = QtWidgets.QDoubleSpinBox()
        self.lamelle.setAccessibleName(tr("Maximales Kupplungsmoment A–B"))
        self.lamelle.setDecimals(3)
        self.lamelle.setRange(-.001, 1e12)
        self.lamelle.setSpecialValueText(tr("unbekannt"))
        self.lamelle.setSuffix(" Nm")
        self.lamelle.setValue(self.lamelle.minimum())
        self.lamelle.setKeyboardTracking(False)
        self.lamelle.setToolTip(_annahme("lamelle"))
        self.lamelle_label.setToolTip(self.lamelle.toolTip())
        reihe.addWidget(self.lamelle_label)
        reihe.addWidget(self.lamelle)
        lay.addLayout(reihe)
        self.text = QtWidgets.QLabel()
        self.text.setWordWrap(True)
        lay.addWidget(self.text)
        self.satz.currentIndexChanged.connect(self._lesen)
        self.modell.currentIndexChanged.connect(self._schreiben)
        self.nutze_moment.toggled.connect(self._schreiben)
        self.tbr.valueChanged.connect(self._schreiben)
        self.moment.valueChanged.connect(self._schreiben)
        self.lamelle.valueChanged.connect(self._schreiben)

    def setze_betrieb(self, b):
        self.stege = {}
        vorher = self.satz.currentData()
        with QtCore.QSignalBlocker(self.satz):
            self.satz.clear()
            for s in b.saetze:
                if s["art"] not in ("kegel", "schraegraddifferential"):
                    continue
                steg = s["wellen"][2]
                key = tuple(s["raeder"])
                self.stege[steg] = key
                self.satz.addItem(b.namen[steg], key)
            pos = next((i for i in range(self.satz.count()) if self.satz.itemData(i) == vorher), 0)
            self.satz.setCurrentIndex(pos)
        self.setVisible(bool(self.stege))
        self.satz.setVisible(len(self.stege) > 1)
        self._lesen()

    def _lesen(self):
        if not self.stege:
            return
        v = self.vorgaben.get(tuple(self.satz.currentData()), Sperrvorgabe())
        with (QtCore.QSignalBlocker(self.modell), QtCore.QSignalBlocker(self.nutze_moment),
              QtCore.QSignalBlocker(self.moment), QtCore.QSignalBlocker(self.tbr), QtCore.QSignalBlocker(self.lamelle)):
            self.modell.setCurrentIndex(self.modell.findData(v.art))
            self.nutze_moment.setChecked(v.steg_moment is not None)
            self.moment.setValue(v.steg_moment or 0.)
            self.tbr.setValue(v.tbr or 1.)
            self.lamelle.setValue(v.kupplungsmoment_max if v.kupplungsmoment_max is not None else self.lamelle.minimum())
        self._felder()
        self._ergebnis_anzeigen()

    def _felder(self):
        self.moment.setEnabled(self.nutze_moment.isChecked())
        for feld in (self.lamelle_label, self.lamelle):
            feld.setVisible(self.modell.currentData() == "lamelle")
        for feld in (self.tbr_label, self.tbr):
            feld.setVisible(self.modell.currentData() == "tbr")

    def _schreiben(self):
        self._felder()
        art = self.modell.currentData()
        self.vorgaben[tuple(self.satz.currentData())] = Sperrvorgabe(
            art, self.moment.value() if self.nutze_moment.isChecked() else None,
            tbr=self.tbr.value() if art == "tbr" else None,
            kupplungsmoment_max=self.lamelle.value() if art == "lamelle" and self.lamelle.value() >= 0 else None)
        self.geaendert.emit()

    def parameter(self):
        return {steg: self.vorgaben[key] for steg, key in self.stege.items() if key in self.vorgaben}

    def zeige(self, ergebnis):
        self.faelle = ergebnis["differentialsperren"]
        self._ergebnis_anzeigen()

    def _ergebnis_anzeigen(self):
        if not self.stege:
            return
        key = tuple(self.satz.currentData())
        fall = next((f for f in getattr(self, "faelle", ()) if self.stege.get(f["wellen_a_b_steg"][2]) == key), None)
        if fall:
            beschreibung = tr("Gewählte Betriebsannahme") + " · " + _momenttext(fall)
            self.text.setToolTip(_annahme(fall["modell"]))
            if fall["modell"] in ("tbr", "lamelle"):
                beschreibung += "\n" + _annahme(fall["modell"])
            self.text.setText(beschreibung)


def sperrzeilen(ergebnis, wellenname):
    zeilen = []
    for fall in ergebnis["differentialsperren"]:
        steg = fall["wellen_a_b_steg"][2]
        zeilen.append((tr("Sperrmodell im Betriebspunkt"), f"{wellenname(steg)} · {_modellnamen()[fall['modell']]}"))
        if fall["steg_antriebsmoment"] is not None:
            zeilen.append((tr("Steg-Antriebsmoment"), f"{fall['steg_antriebsmoment']:g} Nm"))
        if fall["modell"] == "tbr":
            zeilen.append(("TBR", f"{fall['tbr']:g}"))
        if fall["modell"] == "lamelle":
            mk = fall["kupplungsmoment_max"]
            zeilen.append((tr("Maximales Kupplungsmoment A–B"), f"{mk:g} Nm" if mk is not None else tr("unbekannt")))
        zeilen.append((tr("Seitenmomente"), _momenttext(fall)))
        if fall["modell"] == "lamelle" or fall["seitenmomente_a_b"] is not None:
            zeilen.append((tr("Modellannahmen"), _annahme(fall["modell"])))
    return zeilen
