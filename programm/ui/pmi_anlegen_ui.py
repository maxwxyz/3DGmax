"""Dialog PMI anlegen: Vorschlaege des Tolerierungsberaters fuer die Auswahl uebernehmen und anpassen."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.pmi import MASS
from .tabellen import spalten_anpassen


class PmiAnlegenDialog(QtWidgets.QDialog):
    SPALTEN = ("Übernehmen", "Merkmal", "Wert", "Toleranz / ±", "Passung", "Begründung")

    def __init__(self, vorschlaege: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("PMI anlegen"))
        self.resize(760, 300)
        self.vorschlaege = vorschlaege
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Vorschläge für die gewählten Flächen – Werte sind Startwerte (Nennmaß gemessen), "
                                      "bitte prüfen und anpassen."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        self.tabelle = QtWidgets.QTableWidget(len(vorschlaege), len(self.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in self.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        for z, v in enumerate(vorschlaege):
            p = v.pmi
            haken = QtWidgets.QTableWidgetItem()
            haken.setCheckState(QtCore.Qt.CheckState.Unchecked if getattr(v, "vorhanden", False) else
                                QtCore.Qt.CheckState.Checked)
            self.tabelle.setItem(z, 0, haken)
            grund = tr(v.grund) + (" – " + v.hinweis if getattr(v, "hinweis", "") else "")
            for s, text in ((1, tr(p.merkmal())), (2, p.wert_text()), (5, grund)):
                it = QtWidgets.QTableWidgetItem(text)
                it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.tabelle.setItem(z, s, it)
            tol = p.wert if p.art != MASS else (p.oben if p.oben is not None else "")
            self.tabelle.setItem(z, 3, QtWidgets.QTableWidgetItem("" if tol in ("", None) else f"{tol:g}"))
            self.tabelle.setItem(z, 4, QtWidgets.QTableWidgetItem(p.passung if p.art == MASS else ""))
        spalten_anpassen(self.tabelle, strecken=True)
        lay.addWidget(self.tabelle, 1)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def gewaehlte(self) -> list:
        """Uebernommene PMI mit den eingetragenen Werten."""
        out = []
        for z, v in enumerate(self.vorschlaege):
            if self.tabelle.item(z, 0).checkState() != QtCore.Qt.CheckState.Checked:
                continue
            p = v.pmi
            text = (self.tabelle.item(z, 3).text() or "").replace(",", ".").strip()
            try:
                wert = float(text) if text else None
            except ValueError:
                wert = None
            if p.art == MASS:
                p.passung = (self.tabelle.item(z, 4).text() or "").strip()
                if p.passung:
                    p.oben = p.unten = None
                elif wert is not None:
                    p.oben, p.unten = abs(wert), -abs(wert)
            elif wert is not None:
                p.wert = wert
            out.append(p)
        return out


class PmiBearbeitenDialog(QtWidgets.QDialog):
    """Werte einer Mass- oder Toleranz-PMI aendern."""

    def __init__(self, p, parent=None):
        super().__init__(parent)
        self.p = p
        self.setWindowTitle(tr("PMI bearbeiten"))
        lay = QtWidgets.QFormLayout(self)
        lay.addRow(QtWidgets.QLabel(f"{p.nummer}: {tr(p.merkmal())} – {p.wert_text()}"))
        self.felder = {}

        def zahl(wert, name, text):
            f = QtWidgets.QLineEdit("" if wert is None else f"{wert:g}")
            lay.addRow(tr(text), f)
            self.felder[name] = f

        if p.art == MASS:
            zahl(p.nennwert, "nennwert", "Nennmaß")
            zahl(p.oben, "oben", "Oberes Abmaß")
            zahl(p.unten, "unten", "Unteres Abmaß")
            self.passung = QtWidgets.QLineEdit(p.passung)
            lay.addRow(tr("Toleranzklasse"), self.passung)
        else:
            zahl(p.wert, "wert", "Toleranzwert")
            self.material = QtWidgets.QComboBox()
            for k, text in (("", "ohne"), ("M", "Maximum-Material Ⓜ"), ("L", "Minimum-Material Ⓛ")):
                self.material.addItem(tr(text), k)
            self.material.setCurrentIndex(max(self.material.findData(p.material), 0))
            lay.addRow(tr("Materialbedingung"), self.material)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addRow(knoepfe)

    def werte(self) -> dict:
        out = {}
        for name, f in self.felder.items():
            t = f.text().replace(",", ".").strip()
            try:
                out[name] = float(t) if t else None
            except ValueError:
                out[name] = getattr(self.p, name)
        if self.p.art == MASS:
            out["passung"] = self.passung.text().strip()
        else:
            out["material"] = self.material.currentData()
        return out
