"""Maschinenelemente auslegen, gemessene Sitzmasse uebernehmen."""

import json
from math import hypot, isfinite
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.maschinenelemente import FELDER, VERFAHREN, berechne
from .lader import Abbruch, Modellauftrag


class Stirnradexport(Modellauftrag):
    def __init__(self, pfad, eingaben, breiten):
        super().__init__()
        self.pfad, self.eingaben, self.breiten = pfad, eingaben, breiten
        self.fehler = ""

    def abbrechen(self):
        self.abgebrochen = True

    def _pruefe(self):
        if self.abgebrochen:
            raise Abbruch

    def run(self):
        try:
            from ..kern.stirnradgeometrie import schreibe_stirnradpaar
            schreibe_stirnradpaar(self.pfad, self.eingaben, *self.breiten, pruefe=self._pruefe)
        except Abbruch:
            pass
        except Exception as e:  # noqa: BLE001 - Schreibfehler im Dialog melden
            self.fehler = str(e)


def beschriftung(feld):
    name, einheit = FELDER[feld]
    return f"{tr(name)} [{einheit}]" if einheit else tr(name)


class AuslegungFenster(QtWidgets.QDialog):
    def __init__(self, parent=None, *, art="stirnrad", messwerte=None, quelle=""):
        super().__init__(parent)
        self.setWindowTitle(tr("Maschinenelement auslegen"))
        self.resize(510, 430)
        self.werte = {}
        self.messwerte = dict(messwerte or {})
        self.quelle = quelle
        self.felder = {}
        self.zusatz = {}
        self.breitenfelder = {}
        self.paarauftrag = None
        lay = QtWidgets.QVBoxLayout(self)
        self.wahl = QtWidgets.QComboBox()
        self.wahl.setToolTip(tr("Element und Berechnungsverfahren wählen"))
        for kennung, verfahren in VERFAHREN.items():
            self.wahl.addItem(tr(verfahren.titel), kennung)
        self.wahl.setCurrentIndex(self.wahl.findData(art))
        lay.addWidget(self.wahl)
        self.annahme = QtWidgets.QLabel()
        self.annahme.setWordWrap(True)
        lay.addWidget(self.annahme)
        self.form = QtWidgets.QFormLayout()
        lay.addLayout(self.form)
        self.ergebnis = QtWidgets.QLabel()
        self.ergebnis.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.ergebnis.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.ergebnis)
        self.lagerwelle = QtWidgets.QPushButton(tr("Zahnkräfte auf eine Lagerwelle übernehmen …"))
        self.lagerwelle.setToolTip(tr("Resultierende Querlast und Ritzeldrehmoment in die Wellenrechnung übernehmen"))
        self.lagerwelle.clicked.connect(self._lagerwelle)
        lay.addWidget(self.lagerwelle, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.step = QtWidgets.QPushButton()
        self.step.clicked.connect(self._step)
        lay.addWidget(self.step, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        lay.addStretch()
        knoepfe = QtWidgets.QDialogButtonBox()
        self.speichern = knoepfe.addButton(tr("Berechnung speichern …"), knoepfe.ButtonRole.ActionRole)
        self.speichern.setToolTip(tr("Eingaben, Herkunft, Einheiten und Ergebnis als JSON sichern"))
        self.speichern.clicked.connect(self._speichern)
        oeffnen = knoepfe.addButton(tr("Berechnung öffnen …"), knoepfe.ButtonRole.ActionRole)
        oeffnen.setToolTip(tr("Gespeicherte Eingaben laden und erneut berechnen"))
        oeffnen.clicked.connect(self._oeffnen)
        knoepfe.addButton(knoepfe.StandardButton.Close).clicked.connect(self.close)
        lay.addWidget(knoepfe)
        self.wahl.currentIndexChanged.connect(self._aufbauen)
        self._aufbauen()

    def _aufbauen(self):
        self.felder.clear()
        self.breitenfelder.clear()
        while self.form.rowCount():
            self.form.removeRow(0)
        self.art = self.wahl.currentData()
        verfahren = VERFAHREN[self.art]
        self.annahme.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        quelle = tr("Übernommene Werte aus {}").format(self.quelle) if self.quelle else ""
        self.annahme.setText("\n".join(filter(None, (tr(verfahren.annahme), quelle))))
        self.lagerwelle.setVisible(self.art == "stirnrad")
        self.step.setVisible(self.art in ("stirnrad", "welle", "lagerwelle", "buchse", "reibsitz"))
        if self.art == "stirnrad":
            self.step.setText(tr("Stirnradpaar mit PMI als STEP …"))
            self.step.setToolTip(tr("Ritzel und Rad am Nennachsabstand speichern. Unterhalb des Grundkreises verläuft der Zahnfuß radial."))
        else:
            self.step.setText(tr("Wellenabschnitt mit PMI als STEP …") if self.art in ("welle", "lagerwelle")
                              else tr("Buchse / Nabe mit PMI als STEP …"))
            self.step.setToolTip(tr("Nenngeometrie mit Durchmesser- und Längenmaßen als STEP AP242 speichern"))
        for k in verfahren.eingaben:
            feld = QtWidgets.QLineEdit()
            wert = self.werte.get(self.art, {}).get(k)
            if wert is None and k in self.messwerte:
                wert = str(self.messwerte[k])
            feld.setText(wert or "")
            feld.setToolTip(beschriftung(k))
            if k in self.messwerte:
                feld.setToolTip(tr("Ursprünglich übernommen: {}").format(self.messwerte[k]))
            self.form.addRow(beschriftung(k), feld)
            self.felder[k] = feld
            feld.textChanged.connect(self._rechnen)
        if self.art == "stirnrad":
            for k, text in (("b1", tr("Zahnbreite Ritzel [mm]")), ("b2", tr("Zahnbreite Rad [mm]"))):
                feld = QtWidgets.QLineEdit()
                wert = self.zusatz.get(self.art, {}).get(k, self.messwerte.get(k))
                if wert is not None:
                    feld.setText(str(wert))
                feld.setPlaceholderText(tr("Für den STEP-Export"))
                if k in self.messwerte:
                    feld.setToolTip(tr("Ursprünglich übernommen: {}").format(self.messwerte[k]))
                self.form.addRow(text, feld)
                self.breitenfelder[k] = feld
                feld.textChanged.connect(self._rechnen)
        self._rechnen()

    def _paargeometrie(self):
        breiten = {}
        for k, feld in self.breitenfelder.items():
            try:
                b = float(feld.text().replace(",", "."))
            except ValueError:
                continue
            if isfinite(b) and b > 1e-6:
                breiten[k] = b
        self.zusatz[self.art] = breiten
        if len(breiten) != 2:
            return None
        try:
            eingaben = {k: float(self.felder[k].text().replace(",", ".")) for k in ("z1", "z2", "m", "alpha")}
            berechne("stirnrad", {**eingaben, "t": 0.})
        except (ValueError, ArithmeticError):
            return None
        return eingaben, (breiten["b1"], breiten["b2"])

    def _rechnen(self):
        texte = {k: feld.text() for k, feld in self.felder.items()}
        self.werte[self.art] = texte
        self.lagerwelle.setEnabled(False)
        self.speichern.setEnabled(False)
        self.daten = None
        geom = self._paargeometrie() if self.art == "stirnrad" else self._masse()
        self.step.setEnabled(geom is not None and self.paarauftrag is None)
        if not all(t.strip() for t in texte.values()):
            self.ergebnis.setText(tr("Fehlende Eingaben ergänzen."))
            return
        eingaben = {}
        try:
            for k, t in texte.items():
                eingaben[k] = float(t.strip().replace(",", "."))
            ausgaben = berechne(self.art, eingaben)
        except (ValueError, ArithmeticError) as e:
            feld = e.args[0] if e.args and e.args[0] in FELDER else k
            self.ergebnis.setText(tr("Eingabe prüfen: {}").format(beschriftung(feld)))
            return
        self.ergebnis.setText("\n".join(f"{beschriftung(k)}   {v:.6g}" for k, v in ausgaben.items()))
        einheiten = {k: FELDER[k][1] for k in (*eingaben, *ausgaben)}
        self.daten = dict(format="3dgmax-auslegung", version=1, verfahren=self.art, eingaben=eingaben,
                          ergebnisse=ausgaben, einheiten=einheiten, modellquelle=self.quelle,
                          uebernommene_masse=self.messwerte, geometrie=self.zusatz.get(self.art, {}))
        self.speichern.setEnabled(True)
        self.lagerwelle.setEnabled(self.art == "stirnrad")

    def _lagerwelle(self):
        kraft = self.daten["ergebnisse"]
        quelle = tr("Stirnradpaar, Ritzel") + (" · " + self.quelle if self.quelle else "")
        return zeige_auslegung(self, art="lagerwelle", quelle=quelle,
                               messwerte={"quer": hypot(kraft["ft"], kraft["fr"]), "t": self.daten["eingaben"]["t"]})

    def _masse(self):
        if "d" not in self.felder:
            return None
        try:
            d = float(self.felder["d"].text().replace(",", "."))
            l = float(self.felder["l"].text().replace(",", ".")) if "l" in self.felder else 0
        except ValueError:
            return None
        if not isfinite(d) or d <= 1e-6 or ("l" in self.felder and (not isfinite(l) or l <= 1e-6)):
            return None
        return d, l

    def _stirnrad_step(self):
        geom = self._paargeometrie()
        if self.paarauftrag is not None or geom is None:
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, self.step.text(), "stirnradpaar.step", "STEP (*.step *.stp)")
        if not pfad:
            return
        self.paarauftrag = Stirnradexport(pfad, *geom)
        self.fortschritt = QtWidgets.QProgressDialog(tr("Stirnradpaar und Maßangaben werden geschrieben …"),
                                                    tr("Abbrechen"), 0, 0, self)
        self.fortschritt.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.fortschritt.canceled.connect(self.paarauftrag.abbrechen)
        self.paarauftrag.finished.connect(self._export_beendet)
        self.step.setEnabled(False)
        self.fortschritt.show()
        self.paarauftrag.starte()

    def _export_beendet(self):
        fehler = self.paarauftrag.fehler
        self.paarauftrag = None
        self.fortschritt.reset()
        self.fortschritt.deleteLater()
        self._rechnen()
        if fehler:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), fehler)

    def done(self, result):
        if self.paarauftrag:
            self.paarauftrag.abbrechen()
        super().done(result)

    def _step(self):
        if self.art == "stirnrad":
            return self._stirnrad_step()
        from ..kern.maschinenelemente import schreibe_sitzteil
        d, l = self._masse()
        welle = self.art in ("welle", "lagerwelle")
        feld = "laenge_mm" if welle else "aussendurchmesser_mm"
        start = self.zusatz.get(self.art, {}).get(feld, self.messwerte.get("l", d) if welle else d * 1.5)
        grenze = .00001 if welle else d + .00001
        if grenze > 1e7:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), tr("Maße außerhalb des STEP-Exportbereichs."))
            return
        wert, ok = QtWidgets.QInputDialog.getDouble(self, self.step.text(),
                       tr("Abschnittslänge [mm]") if welle else tr("Außendurchmesser [mm]"),
                       start, grenze, 1e7, 5)
        if not ok:
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, self.step.text(), self.art + ".step", "STEP (*.step *.stp)")
        if pfad:
            try:
                if welle:
                    schreibe_sitzteil(pfad, d, wert)
                else:
                    schreibe_sitzteil(pfad, wert, l, d)
            except (RuntimeError, ValueError, OSError) as e:
                QtWidgets.QMessageBox.warning(self, self.windowTitle(), str(e))
                return
            self.zusatz[self.art] = {feld: wert}
            self._rechnen()

    def _speichern(self):
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Berechnung speichern …"), self.art + ".json", "JSON (*.json)")
        if pfad and self.daten:
            datei = QtCore.QSaveFile(pfad)
            inhalt = json.dumps(self.daten, ensure_ascii=False, indent=2).encode("utf-8")
            if (not datei.open(QtCore.QIODevice.OpenModeFlag.WriteOnly) or datei.write(inhalt) != len(inhalt)
                    or not datei.commit()):
                QtWidgets.QMessageBox.warning(self, self.windowTitle(), datei.errorString())

    def _oeffnen(self):
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Berechnung öffnen …"), "", "JSON (*.json)")
        if not pfad:
            return
        try:
            d = json.loads(Path(pfad).read_text(encoding="utf-8"))
            if d["format"] != "3dgmax-auslegung" or d["version"] != 1:
                raise ValueError
            art, eingaben = d["verfahren"], d["eingaben"]
            if not isinstance(eingaben, dict):
                raise ValueError
            berechne(art, eingaben)
            messwerte = d.get("uebernommene_masse", {})
            if not isinstance(messwerte, dict) or not isinstance(d.get("modellquelle", ""), str):
                raise ValueError
            geometrie = d.get("geometrie", {})
            if not all(isinstance(v, dict) and all(type(x) in (int, float) and isfinite(x) and x >= 0
                                                   for x in v.values()) for v in (messwerte, geometrie)):
                raise ValueError
        except (KeyError, ValueError, TypeError, ArithmeticError, OSError):
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), tr("Die Datei enthält keine gültige Auslegung."))
            return
        self.zusatz = {art: geometrie}
        self.quelle, self.messwerte = d.get("modellquelle", ""), messwerte
        self.werte = {art: {k: str(eingaben[k]) for k in VERFAHREN[art].eingaben}}
        with QtCore.QSignalBlocker(self.wahl):
            self.wahl.setCurrentIndex(self.wahl.findData(art))
        self._aufbauen()


def zeige_auslegung(parent, **vorgaben):
    dialog = AuslegungFenster(parent, **vorgaben)
    dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.show()
    return dialog
