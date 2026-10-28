"""Mausrad ueber Zahlenfeldern und Auswahllisten: ohne Fokus rollt es die umgebende Tabelle bzw. Leiste statt den
Wert zu aendern (sonst verstellt das Rollen durch eine Tabelle versehentlich Werte). Mit Fokus (angeklickt) aendert
das Rad den Wert wie gewohnt."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

FELDER = (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)


class Radsperre(QtCore.QObject):
    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        typ = ev.type()
        if typ == QtCore.QEvent.Type.Polish and isinstance(obj, FELDER):
            obj.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)  # das Rad allein gibt keinen Fokus
        elif typ == QtCore.QEvent.Type.Wheel and isinstance(obj, FELDER) and not obj.hasFocus():
            rollbereich = obj.parentWidget()
            while rollbereich is not None and not isinstance(rollbereich, QtWidgets.QAbstractScrollArea):
                rollbereich = rollbereich.parentWidget()
            if rollbereich is not None:
                QtWidgets.QApplication.sendEvent(rollbereich.viewport(), ev.clone())
            return True  # Wert bleibt
        return False


def installieren(app: QtWidgets.QApplication):
    """Einmal je Anwendung."""
    if getattr(app, "_radsperre", None) is None:
        app._radsperre = Radsperre(app)
        app.installEventFilter(app._radsperre)
