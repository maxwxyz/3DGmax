"""Arbeitsbereiche (UI-Plan Stufe 2): je Aufgabe die Seitenleisten, die dazugehoeren - statt zehn Leisten, die sich
gegenseitig verdecken. Die Leiste oben schaltet um; oeffnet ein Werkzeug eine Leiste eines anderen Bereichs, folgt die
Leiste (die Leiste wird nicht versteckt). Menues und Kurzbefehle bleiben vollstaendig."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr

# (Schluessel, Name, Tooltip, Leisten) - Leisten als Namen der Attribute dock_<name> im Hauptfenster
BEREICHE = (
    ("ansehen", "Ansehen", "Modell, PMI und gespeicherte Ansichten lesen", ("baum", "ansichten", "pmi")),
    ("vergleichen", "Vergleichen & Prüfen", "Zwei Stände vergleichen und die Änderungen prüfen, Scan gegen "
                                            "Toleranzen prüfen", ("baum", "aenderungen", "scan", "pmi")),
    ("messen", "Messen & Analysieren", "Messen, Analysen (Entformung, Krümmung, Wandstärke), Kommentare",
     ("baum", "messen", "analyse", "kommentare")),
    ("tolerieren", "Tolerieren", "PMI und Toleranzzonen, PMI anlegen, Toleranzkette, Funktion → Tolerierung",
     ("baum", "pmi")),
    ("zusammenbau", "Zusammenbau", "Teile verbinden, Wiggle, Baugruppenvariation, Kollisionen",
     ("baum", "zusammenbau", "kollision")),
)
GEMEINSAM = {"baum", "pmi", "ansichten"}  # in mehreren Bereichen: oeffnen sie sich, bleibt der Bereich


def leisten(schluessel: str) -> tuple:
    return next((b[3] for b in BEREICHE if b[0] == schluessel), ())


def bereich_von(leiste: str) -> str | None:
    """Erster Bereich, zu dem eine (nicht gemeinsame) Leiste gehoert."""
    if leiste in GEMEINSAM:
        return None
    return next((b[0] for b in BEREICHE if leiste in b[3]), None)


class Bereichsleiste(QtWidgets.QTabBar):
    """Reiter der Arbeitsbereiche; gewaehlt meldet den Schluessel."""

    gewaehlt = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setDrawBase(False)
        for schluessel, name, tipp, _ in BEREICHE:
            i = self.addTab(tr(name).replace("&", "&&"))  # "&" ist sonst ein Tastenkuerzel-Zeichen
            self.setTabData(i, schluessel)
            self.setTabToolTip(i, tr(tipp))
        self.setToolTip(tr("Arbeitsbereich: zeigt die Seitenleisten für diese Aufgabe"))
        self.currentChanged.connect(lambda i: self.gewaehlt.emit(self.tabData(i)) if i >= 0 else None)

    def schluessel(self) -> str:
        return self.tabData(self.currentIndex())

    def zeige(self, schluessel: str, melden: bool = True):
        i = next((i for i in range(self.count()) if self.tabData(i) == schluessel), -1)
        if i < 0 or i == self.currentIndex():
            return
        self.blockSignals(not melden)
        self.setCurrentIndex(i)
        self.blockSignals(False)
