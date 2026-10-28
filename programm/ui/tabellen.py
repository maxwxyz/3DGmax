"""Gemeinsames fuer Tabellen: aenderbare Zellen sichtbar machen (leicht getoent) und mit einem Klick bearbeiten
(UI-Plan Stufe 2: sichtbare Bedienbarkeit statt versteckter Doppelklicks)."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

AENDERBAR_FARBE = QtGui.QColor(37, 99, 235, 34)  # Zellen, die man aendern kann
EIN_KLICK = (QtWidgets.QAbstractItemView.EditTrigger.CurrentChanged |
             QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked |
             QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked |
             QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed |
             QtWidgets.QAbstractItemView.EditTrigger.AnyKeyPressed)


class AenderbarDelegate(QtWidgets.QStyledItemDelegate):
    """Toent jede Zelle, deren Eintrag aenderbar ist; alles andere wie gewohnt."""

    def initStyleOption(self, option, index):  # noqa: N802 - Qt
        super().initStyleOption(option, index)
        if index.flags() & QtCore.Qt.ItemFlag.ItemIsEditable and \
                option.backgroundBrush.style() == QtCore.Qt.BrushStyle.NoBrush:  # eigene Farbe der Zelle geht vor
            option.backgroundBrush = QtGui.QBrush(AENDERBAR_FARBE)


def aenderbar_machen(tabelle: QtWidgets.QAbstractItemView):
    """Aenderbare Zellen getoent und mit einem Klick bearbeitbar (nicht aenderbare Zellen muessen das Flag
    ItemIsEditable abgeschaltet haben)."""
    tabelle.setItemDelegate(AenderbarDelegate(tabelle))
    tabelle.setEditTriggers(EIN_KLICK)


class _LeerHinweis(QtCore.QObject):
    """Zeichnet in eine leere Tabelle einen Satz, was zu tun ist (UI-Plan: leere Zustaende sagen den naechsten
    Schritt)."""

    def __init__(self, tabelle: QtWidgets.QAbstractItemView, text: str):
        super().__init__(tabelle)
        self.tabelle, self.text = tabelle, text
        tabelle.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        if ev.type() == QtCore.QEvent.Type.Paint and self.tabelle.model() is not None and \
                self.tabelle.model().rowCount() == 0 and self.text:
            maler = QtGui.QPainter(obj)
            farbe = self.tabelle.palette().color(QtGui.QPalette.ColorRole.PlaceholderText)
            maler.setPen(farbe)
            r = obj.rect().adjusted(12, 12, -12, -12)
            maler.drawText(r, int(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop |
                                  QtCore.Qt.TextFlag.TextWordWrap), self.text)
            maler.end()
        return False


def leer_hinweis(tabelle: QtWidgets.QAbstractItemView, text: str) -> _LeerHinweis:
    """Hinweis in der leeren Tabelle (verschwindet mit der ersten Zeile)."""
    h = _LeerHinweis(tabelle, text)
    tabelle._leer_hinweis = h
    return h
