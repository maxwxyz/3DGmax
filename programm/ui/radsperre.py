"""Mausrad ueber Zahlenfeldern und Auswahllisten: rollt die umgebende Tabelle bzw. Leiste statt den Wert zu aendern
(sonst verstellt das Rollen durch eine Tabelle versehentlich Werte). Werte aendern sich nur per Klick: Auswahllisten
nie per Rad (wie unter macOS), Felder in Tabellenzellen nie (sie behalten nach der Wahl den Fokus, das naechste Rollen
der Tabelle wuerde sie sonst verstellen), andere Zahlenfelder nur, wenn sie angeklickt wurden (Fokus)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

FELDER = (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)


def _rollbereich(feld: QtWidgets.QWidget) -> QtWidgets.QAbstractScrollArea | None:
    w = feld.parentWidget()
    while w is not None and not isinstance(w, QtWidgets.QAbstractScrollArea):
        w = w.parentWidget()
    return w


def rad_aendert(feld: QtWidgets.QWidget) -> bool:
    """Darf das Rad den Wert dieses Feldes aendern?"""
    if isinstance(feld, QtWidgets.QComboBox) or not feld.hasFocus():
        return False
    return not isinstance(_rollbereich(feld), QtWidgets.QAbstractItemView)  # Feld in einer Tabellenzelle


class Radsperre(QtCore.QObject):
    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        typ = ev.type()
        if typ == QtCore.QEvent.Type.Polish and isinstance(obj, FELDER):
            obj.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)  # das Rad allein gibt keinen Fokus
        elif typ == QtCore.QEvent.Type.Wheel and isinstance(obj, FELDER) and not rad_aendert(obj):
            rollbereich = _rollbereich(obj)
            if rollbereich is not None:
                QtWidgets.QApplication.sendEvent(rollbereich.viewport(), ev.clone())
            return True  # Wert bleibt
        return False


def installieren(app: QtWidgets.QApplication):
    """Einmal je Anwendung."""
    if getattr(app, "_radsperre", None) is None:
        app._radsperre = Radsperre(app)
        app.installEventFilter(app._radsperre)
