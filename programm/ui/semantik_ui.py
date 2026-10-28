"""Dialog "Semantisch machen": nur grafische PMI pruefen und als eigene PMI mit Semantik uebernehmen (Reparieren).

Nicht modal: waehrend der Dialog offen ist, lassen sich im Modell Flaechen waehlen und uebernehmen.
"""

from __future__ import annotations

import re

from PySide6 import QtWidgets

from ..i18n import tr
from ..kern.pmi import BEZUG, MASS, MERKMAL, TOL_SYMBOL, TOLERANZ, BezugsRef

MASS_TYPEN = ("Size_Diameter", "Size_Radius", "Size_Thickness", "Size_Angular", "Location_LinearDistance",
              "Location_Angular")  # in STEP schreibbar (step_schreiben)
ARTEN = ((TOLERANZ, "Toleranz"), (MASS, "Maß"), (BEZUG, "Bezug"))


def _zahl(text: str) -> float | None:
    t = text.replace(",", ".").strip()
    try:
        return float(t) if t else None
    except ValueError:
        return None


class SemantikDialog(QtWidgets.QDialog):
    """Art, Werte und Flaechen einer nur grafischen PMI; Startwerte aus pmi_reparieren.vorschlag."""

    def __init__(self, vorschlag, auswahl, zeigen, parent=None):
        super().__init__(parent)
        self.v, self.auswahl, self.zeigen = vorschlag, auswahl, zeigen
        self.flaechen = set(vorschlag.flaechen)
        self.setWindowTitle(tr("Semantisch machen"))
        lay = QtWidgets.QFormLayout(self)
        info = QtWidgets.QLabel(tr("Grafik „{}“ ohne Semantik in der Datei. Art, Werte und Flächen sind aus der "
                                   "Grafik vorgeschlagen – bitte prüfen. Die Grafik der Datei bleibt; beim Speichern "
                                   "als STEP wird die Semantik angehängt und mit ihr verknüpft.").format(
            vorschlag.nur_grafik_text))
        info.setWordWrap(True)
        info.setObjectName("leise")
        lay.addRow(info)
        self.art = QtWidgets.QComboBox()
        for k, text in ARTEN:
            self.art.addItem(tr(text), k)
        self.art.setCurrentIndex(max(self.art.findData(vorschlag.art), 0))
        self.typ = QtWidgets.QComboBox()
        lay.addRow(tr("Art"), self.art)
        lay.addRow(tr("Merkmal"), self.typ)
        self.felder: dict[str, QtWidgets.QWidget] = {}
        self._zeilen(lay)
        self.flaechen_text = QtWidgets.QLabel()
        uebernehmen = QtWidgets.QPushButton(tr("Auswahl übernehmen"))
        uebernehmen.setToolTip(tr("Die im Modell gewählten Flächen statt des Vorschlags verwenden"))
        uebernehmen.clicked.connect(self._auswahl_uebernehmen)
        zeile = QtWidgets.QHBoxLayout()
        zeile.addWidget(self.flaechen_text, 1)
        zeile.addWidget(uebernehmen)
        lay.addRow(tr("Flächen"), zeile)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self._pruefen)
        knoepfe.rejected.connect(self.reject)
        lay.addRow(knoepfe)
        self.art.currentIndexChanged.connect(self._art_gewechselt)
        self._art_gewechselt()
        self._flaechen_gesetzt()

    def _zeilen(self, lay):
        v = self.v

        def zahl(name, text, wert, tip=""):
            f = QtWidgets.QLineEdit("" if wert is None else f"{wert:g}")
            f.setToolTip(tr(tip) if tip else "")
            lay.addRow(tr(text), f)
            self.felder[name] = f

        zahl("nennwert", "Nennmaß", v.nennwert)
        zahl("oben", "Oberes Abmaß", v.oben)
        zahl("unten", "Unteres Abmaß", v.unten)
        self.felder["passung"] = QtWidgets.QLineEdit(v.passung)
        self.felder["passung"].setToolTip(tr("Toleranzklasse nach ISO 286, z. B. H7 (statt der Abmaße)"))
        lay.addRow(tr("Toleranzklasse"), self.felder["passung"])
        zahl("wert", "Toleranzwert", v.wert)
        self.felder["durchmesser"] = QtWidgets.QCheckBox(tr("Durchmesserzone ⌀"))
        self.felder["durchmesser"].setChecked("Diameter" in v.modifikatoren)
        lay.addRow("", self.felder["durchmesser"])
        self.felder["material"] = QtWidgets.QComboBox()
        for k, text in (("", "ohne"), ("M", "Maximum-Material Ⓜ"), ("L", "Minimum-Material Ⓛ")):
            self.felder["material"].addItem(tr(text), k)
        self.felder["material"].setCurrentIndex(max(self.felder["material"].findData(v.material), 0))
        lay.addRow(tr("Materialbedingung"), self.felder["material"])
        self.felder["bezuege"] = QtWidgets.QLineEdit(" ".join(b.name for b in sorted(v.bezuege, key=lambda b: b.stelle)))
        self.felder["bezuege"].setToolTip(tr("Bezugsbuchstaben in der Reihenfolge primär, sekundär, tertiär, z. B. A B C"))
        lay.addRow(tr("Bezüge"), self.felder["bezuege"])
        self.felder["name"] = QtWidgets.QLineEdit(v.name if v.art == BEZUG else "")
        self.felder["name"].setToolTip(tr("Bezugsbuchstabe, wie er in der Grafik steht"))
        lay.addRow(tr("Buchstabe"), self.felder["name"])
        self._lay = lay

    def _art_gewechselt(self):
        art = self.art.currentData()
        typen = {TOLERANZ: list(TOL_SYMBOL), MASS: list(MASS_TYPEN), BEZUG: ["Datum"]}[art]
        alt = self.typ.currentData() or self.v.typ
        self.typ.clear()
        for t in typen:
            self.typ.addItem(f"{TOL_SYMBOL.get(t, '')} {tr(MERKMAL.get(t, t))}".strip(), t)
        self.typ.setCurrentIndex(max(self.typ.findData(alt), 0))
        sichtbar = {MASS: {"nennwert", "oben", "unten", "passung"},
                    TOLERANZ: {"wert", "durchmesser", "material", "bezuege"}, BEZUG: {"name"}}[art]
        for name, f in self.felder.items():
            self._lay.setRowVisible(f, name in sichtbar)

    def _auswahl_uebernehmen(self):
        neu = self.auswahl()
        if neu:
            self.flaechen = set(neu)
            self._flaechen_gesetzt()

    def _flaechen_gesetzt(self):
        self.flaechen_text.setText(tr("{} gewählt").format(len(self.flaechen)) if self.flaechen else
                                   tr("keine – Flächen im Modell wählen und übernehmen"))
        self.zeigen(self.flaechen)

    def fehler(self) -> str:
        art = self.art.currentData()
        if not self.flaechen:
            return tr("Bitte Flächen wählen")
        if art == MASS and _zahl(self.felder["nennwert"].text()) is None:
            return tr("Bitte das Nennmaß angeben")
        if art == TOLERANZ and _zahl(self.felder["wert"].text()) is None:
            return tr("Bitte den Toleranzwert angeben")
        if art == BEZUG and not re.fullmatch(r"[A-Z]{1,2}", self.felder["name"].text().strip()):
            return tr("Bitte den Bezugsbuchstaben angeben")
        return ""

    def _pruefen(self):
        text = self.fehler()
        if text:
            QtWidgets.QMessageBox.information(self, tr("Semantisch machen"), text)
            return
        self.accept()

    def pmi(self):
        """Die gepruefte PMI (art, typ, Werte, Flaechen; Verweis auf den Callout bleibt)."""
        p, f = self.v, self.felder
        p.art, p.typ, p.flaechen = self.art.currentData(), self.typ.currentData(), set(self.flaechen)
        if p.art == MASS:
            p.nennwert, p.oben, p.unten = (_zahl(f[k].text()) for k in ("nennwert", "oben", "unten"))
            p.passung, p.grenzmass = f["passung"].text().strip(), False
        elif p.art == TOLERANZ:
            p.wert, p.material = _zahl(f["wert"].text()), f["material"].currentData()
            p.modifikatoren = [m for m in p.modifikatoren if m != "Diameter"] + \
                (["Diameter"] if f["durchmesser"].isChecked() else [])
            p.bezuege = [BezugsRef(n, k) for k, n in enumerate(f["bezuege"].text().upper().split()[:3], 1)]
        else:
            p.name = f["name"].text().strip()
        return p


def semantisch_machen(fenster, p):
    """Dialog fuer eine nur grafische PMI des Hauptfensters; OK legt sie als eigene PMI an (ersetzt den Eintrag)."""
    from ..kern import pmi_reparieren
    erg = fenster.erg
    if erg is None or not pmi_reparieren.reparierbar(p, erg.grafik):
        return None
    v = pmi_reparieren.vorschlag(p, erg.grafik[p.step_id], erg.modell)

    def auswahl():
        return {i for f in fenster.ansicht.auswahl3d for i in [erg.modell.flaechen_index(f)] if i is not None}

    d = SemantikDialog(v, auswahl, fenster.ansicht.hebe_flaechen, fenster)
    d.setModal(False)
    d.accepted.connect(lambda: fenster.fuege_pmi_hinzu([d.pmi()]))
    fenster._semantik_dialog = d  # nicht modal: Verweis halten
    d.show()
    return d
