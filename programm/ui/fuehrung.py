"""Gefuehrte Ablaeufe (UI-Plan Stufe 3): Schritt fuer Schritt durch eine Aufgabe, z. B. "Scan pruefen" oder "Spalt
messen". Jeder Schritt: kurze Erklaerung, ein Knopf, der ihn ausfuehrt, und ein Haken, sobald er erledigt ist (am
Zustand der App erkannt, nicht durch "Weiter"-Klicks). Fuer Einsteiger - Experten nutzen die Leisten direkt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6 import QtCore, QtWidgets

from ..i18n import tr


@dataclass
class Schritt:
    titel: str
    hilfe: str
    erledigt: Callable[[], bool]
    knopf: str = ""  # Text des Knopfs, der den Schritt ausfuehrt ("" = keiner)
    aktion: Callable[[], object] | None = None


class FuehrungPanel(QtWidgets.QWidget):
    """Zeigt einen Ablauf: Schrittliste mit Haken, den aktuellen Schritt mit Erklaerung und Knopf."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ablauf: tuple[str, list[Schritt]] | None = None
        self.aktuell = 0
        self._von_hand = False  # Schritt von Hand gewaehlt: nicht automatisch weiterspringen
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.titel = QtWidgets.QLabel("")
        self.titel.setStyleSheet("font-weight: 600;")
        lay.addWidget(self.titel)
        self.liste = QtWidgets.QListWidget()
        self.liste.setToolTip(tr("Schritte des Ablaufs; ✓ = erledigt. Klick wählt einen Schritt."))
        self.liste.currentRowChanged.connect(self._gewaehlt)
        lay.addWidget(self.liste)  # so hoch wie die Schritte; Erklaerung und Knopf bleiben darunter sichtbar
        self.schritt_titel = QtWidgets.QLabel("")
        self.schritt_titel.setStyleSheet("font-weight: 600;")
        lay.addWidget(self.schritt_titel)
        self.hilfe = QtWidgets.QLabel("")
        self.hilfe.setWordWrap(True)
        lay.addWidget(self.hilfe)
        reihe = QtWidgets.QHBoxLayout()
        self.zurueck = QtWidgets.QPushButton(tr("◀ Zurück"))
        self.zurueck.setToolTip(tr("Vorheriger Schritt"))
        self.zurueck.clicked.connect(lambda: self.gehe(self.aktuell - 1))
        self.machen = QtWidgets.QPushButton("")
        self.machen.setObjectName("primaer")
        self.machen.setToolTip(tr("Diesen Schritt ausführen"))
        self.machen.clicked.connect(self._ausfuehren)
        self.weiter = QtWidgets.QPushButton(tr("Weiter ▶"))
        self.weiter.setToolTip(tr("Nächster Schritt"))
        self.weiter.clicked.connect(lambda: self.gehe(self.aktuell + 1))
        reihe.addWidget(self.zurueck)
        reihe.addStretch(1)
        reihe.addWidget(self.machen)
        reihe.addWidget(self.weiter)
        lay.addLayout(reihe)
        lay.addStretch(1)
        self._uhr = QtCore.QTimer(self)  # Zustand der App regelmaessig pruefen (Haken, naechster Schritt)
        self._uhr.setInterval(500)
        self._uhr.timeout.connect(self.aktualisieren)
        self.setze(None)

    def setze(self, name: str | None, schritte: list[Schritt] | None = None):
        self.ablauf = (name, schritte) if name else None
        self.aktuell, self._von_hand = 0, False
        self.liste.blockSignals(True)
        self.liste.clear()
        for s in schritte or []:
            self.liste.addItem(tr(s.titel))
        self.liste.blockSignals(False)
        zeile = self.liste.sizeHintForRow(0) if self.liste.count() else 20
        self.liste.setFixedHeight(zeile * max(1, self.liste.count()) + 2 * self.liste.frameWidth() + 6)
        self.titel.setText(tr(name) if name else tr("Kein Ablauf gewählt – Hilfe › Geführt …"))
        self._uhr.start() if name else self._uhr.stop()
        self.aktualisieren()

    def schritte(self) -> list[Schritt]:
        return self.ablauf[1] if self.ablauf else []

    def aktualisieren(self):
        schritte = self.schritte()
        erledigt = []
        for i, s in enumerate(schritte):
            try:
                fertig = bool(s.erledigt())
            except Exception:  # noqa: BLE001 - Zustand noch nicht pruefbar (z. B. ohne Modell)
                fertig = False
            erledigt.append(fertig)
            it = self.liste.item(i)
            if it is not None:
                it.setText(("✓ " if fertig else "○ ") + tr(s.titel))
        if schritte and not self._von_hand:  # automatisch zum ersten offenen Schritt
            self.aktuell = next((i for i, f in enumerate(erledigt) if not f), len(schritte) - 1)
        self._zeige_schritt(erledigt)

    def _zeige_schritt(self, erledigt: list[bool]):
        schritte = self.schritte()
        da = bool(schritte)
        for w in (self.schritt_titel, self.hilfe, self.zurueck, self.machen, self.weiter):
            w.setVisible(da)
        if not da:
            return
        s = schritte[self.aktuell]
        alle = all(erledigt)
        self.schritt_titel.setText(tr("Schritt {} von {}: {}").format(self.aktuell + 1, len(schritte), tr(s.titel)) +
                                   ("  ✓" if erledigt[self.aktuell] else ""))
        self.hilfe.setText(tr(s.hilfe) + ("\n\n" + tr("Alle Schritte erledigt.") if alle else ""))
        self.machen.setVisible(bool(s.knopf and s.aktion))
        self.machen.setText(tr(s.knopf) if s.knopf else "")
        self.zurueck.setEnabled(self.aktuell > 0)
        self.weiter.setEnabled(self.aktuell < len(schritte) - 1)
        self.liste.blockSignals(True)
        self.liste.setCurrentRow(self.aktuell)
        self.liste.blockSignals(False)

    def gehe(self, i: int):
        if 0 <= i < len(self.schritte()):
            self.aktuell, self._von_hand = i, True
            self.aktualisieren()

    def _gewaehlt(self, zeile: int):
        if zeile >= 0:
            self.gehe(zeile)

    def _ausfuehren(self):
        s = self.schritte()[self.aktuell]
        self._von_hand = False  # nach der Aktion wieder dem Zustand folgen
        if s.aktion is not None:
            s.aktion()
        self.aktualisieren()
