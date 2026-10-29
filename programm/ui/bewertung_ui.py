"""Anforderung, Ampel und manuelle Freigabe einer Schlussgroesse - gemeinsam fuer die 2D- und 3D-Kette (die 1D-Kette
hat dieselben Teile in ihrem Fenster): Grenzen der Schlussgroesse, Bewertung nach kern.toleranzkette.bewertung und
Freigabe mit Name, Datum und Kommentar."""

from __future__ import annotations

import html

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from .fluss import FlussLayout

AMPEL_FARBEN = {"gruen": "#2e9e48", "gelb": "#e0a800", "rot": "#c0392b"}


def ampel_html(stufe: str, text: str, freigabe: dict) -> str:
    """Ampel (farbiger Punkt mit Begruendung) und manuelle Freigabe als Rich Text; "" ohne beides."""
    teile = []
    if stufe:
        teile.append(f"<span style='color:{AMPEL_FARBEN[stufe]}; font-size:16px'>●</span> {html.escape(text)}")
    if freigabe.get("geprueft"):
        teile.append("✔ " + html.escape(tr("manuell freigegeben: {} {}").format(
            freigabe.get("name", ""), freigabe.get("datum", "")).strip() +
            (" – " + freigabe["kommentar"] if freigabe.get("kommentar") else "")))
    return "<br>".join(teile)


class BewertungLeiste(QtWidgets.QWidget):
    """Anforderung an die Schlussgroesse, Ampel und Freigabe; geaendert meldet jede Eingabe."""

    geaendert = QtCore.Signal()

    def __init__(self, einheit: str = " mm", parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        reihe = FlussLayout()
        self.anforderung = QtWidgets.QCheckBox(tr("Anforderung an die Schlussgröße"))
        self.anforderung.setToolTip(tr("Grenzen der Schlussgröße (z. B. Spalt): daraus Ampel, Cpk und Anteil "
                                       "außerhalb (nichtlinear per Monte Carlo)"))
        self.unten, self.oben = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for k in (self.unten, self.oben):
            k.setRange(-100000.0, 100000.0)
            k.setDecimals(3)
            k.setSuffix(einheit)
            k.setEnabled(False)
            k.setToolTip(tr("Untere und obere Grenze der Schlussgröße"))
            k.valueChanged.connect(lambda _v: self.geaendert.emit())
        self.anforderung.toggled.connect(self._anforderung_an)
        reihe.addWidget(self.anforderung)
        for w in (self.unten, QtWidgets.QLabel("…"), self.oben):
            reihe.addWidget(w)
        lay.addLayout(reihe)
        self.ampel = QtWidgets.QLabel("")
        self.ampel.setWordWrap(True)
        self.ampel.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.ampel.setVisible(False)
        lay.addWidget(self.ampel)
        frei = QtWidgets.QHBoxLayout()
        self.geprueft = QtWidgets.QCheckBox(tr("Kette i. O. / geprüft"))
        self.geprueft.setToolTip(tr("Manuelle Freigabe, auch abweichend vom Ergebnis (z. B. Funktion im Versuch "
                                    "nachgewiesen) – mit Name, Datum und Kommentar in der Kettendatei und im Projekt"))
        self.pruefer = QtWidgets.QLineEdit()
        self.pruefer.setPlaceholderText(tr("Name"))
        self.pruefer.setToolTip(tr("Name der Person, die die Kette freigibt"))
        self.pruefer.setMaximumWidth(160)
        self.kommentar = QtWidgets.QLineEdit()
        self.kommentar.setPlaceholderText(tr("Kommentar zur Freigabe"))
        self.kommentar.setToolTip(tr("Begründung der Freigabe, z. B. Versuch, Erfahrung, Abstimmung"))
        self.datum = QtWidgets.QLabel("")
        self.datum.setObjectName("leise")
        self.geprueft.toggled.connect(self._freigabe_umgeschaltet)
        for w in (self.pruefer, self.kommentar):
            w.editingFinished.connect(self.geaendert.emit)
        for w in (self.geprueft, self.pruefer, self.kommentar, self.datum):
            frei.addWidget(w, 1 if w is self.kommentar else 0)
        lay.addLayout(frei)

    def _anforderung_an(self, an: bool):
        self.unten.setEnabled(an)
        self.oben.setEnabled(an)
        self.geaendert.emit()

    def _freigabe_umgeschaltet(self, an: bool):
        import datetime
        import getpass
        if an and not self.pruefer.text():
            try:
                self.pruefer.setText(getpass.getuser())
            except Exception:  # noqa: BLE001 - ohne Benutzername bleibt das Feld leer
                pass
        self.datum.setText(datetime.date.today().isoformat() if an else "")
        self.geaendert.emit()

    def anforderung_werte(self) -> tuple[float, float] | None:
        return (self.unten.value(), self.oben.value()) if self.anforderung.isChecked() else None

    def freigabe(self) -> dict:
        """Manuelle Freigabe ({} ohne Freigabe und Kommentar)."""
        if not self.geprueft.isChecked() and not self.kommentar.text():
            return {}
        return {"geprueft": self.geprueft.isChecked(), "name": self.pruefer.text(), "datum": self.datum.text(),
                "kommentar": self.kommentar.text()}

    def setze(self, anforderung: tuple | None, freigabe: dict):
        widgets = (self.anforderung, self.unten, self.oben, self.geprueft)
        for w in widgets:
            w.blockSignals(True)
        self.anforderung.setChecked(bool(anforderung))
        self.unten.setEnabled(bool(anforderung))
        self.oben.setEnabled(bool(anforderung))
        if anforderung:
            self.unten.setValue(anforderung[0])
            self.oben.setValue(anforderung[1])
        self.geprueft.setChecked(bool(freigabe.get("geprueft")))
        self.pruefer.setText(freigabe.get("name", ""))
        self.kommentar.setText(freigabe.get("kommentar", ""))
        self.datum.setText(freigabe.get("datum", ""))
        for w in widgets:
            w.blockSignals(False)

    def zeige(self, stufe: str, text: str):
        inhalt = ampel_html(stufe, text, self.freigabe())
        self.ampel.setText(inhalt)
        self.ampel.setVisible(bool(inhalt))
