"""Gemeinsames fuer Tabellen: aenderbare Zellen sichtbar machen (leicht getoent) und mit einem Klick bearbeiten
(UI-Plan Stufe 2: sichtbare Bedienbarkeit statt versteckter Doppelklicks); Spaltenbreiten nach Kopf, Text und
Zellfeldern (lesbare Tabellen)."""

from __future__ import annotations

import re

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


ZAHL = re.compile(r"^[−+-]?\d[\d.,]*(\s?(ppm|%|mm|°|°C))?$")  # Zahl mit Einheit: rechtsbuendig
RAND = 12  # Luft rechts und links in der Spalte (Rahmen der Zelle, Gitterlinie)


def textbreite_hoechst(tabelle: QtWidgets.QAbstractItemView) -> int:
    """Breiteste Textspalte: etwa 48 Zeichen; laengere Texte enden mit … (ganzer Text im Tooltip)."""
    return 48 * tabelle.fontMetrics().averageCharWidth()


def _feld_breite(w: QtWidgets.QWidget) -> int:
    return min(w.sizeHint().width(), w.maximumWidth())


def spalten_anpassen(tabelle: QtWidgets.QTableWidget, hoechst: int | None = None):
    """Spalten so breit wie Kopf, Text und Feld in der Zelle (Auswahl mit Pfeil, Zahlenfeld mit Einheit), Text
    hoechstens `hoechst` px breit; Zeilen so hoch wie das hoechste Feld, Text einzeilig, Zahlen rechtsbuendig.
    ResizeToContents allein reicht nicht: es misst nur Text, nicht die Felder in den Zellen. Von Hand gezogene
    Spaltenbreiten bleiben."""
    kopf = tabelle.horizontalHeader()
    if not hasattr(tabelle, "_eigene_breiten"):
        tabelle._passt_an = False
        kopf.sectionResized.connect(lambda s, _alt, neu: _von_hand(tabelle, s, neu))
    if getattr(tabelle, "_spalten_zahl", None) != tabelle.columnCount():  # andere Spalten: eigene Breiten vergessen
        tabelle._eigene_breiten, tabelle._spalten_zahl = {}, tabelle.columnCount()
    tabelle.setWordWrap(False)
    tabelle.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
    # pixelweise: ein Feld, das den Fokus bekommt, rollt die Tabelle nicht gleich um eine ganze Spalte weiter
    tabelle.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
    kopf.setStretchLastSection(False)
    hoechst = hoechst or textbreite_hoechst(tabelle)
    zahlen_rechts(tabelle)
    tabelle._passt_an = True
    try:
        for s in range(tabelle.columnCount()):
            kopf.setSectionResizeMode(s, QtWidgets.QHeaderView.ResizeMode.Interactive)
            if tabelle.isColumnHidden(s):
                continue
            felder = [w for z in range(tabelle.rowCount()) if (w := tabelle.cellWidget(z, s)) is not None]
            breite = max([kopf.sectionSizeHint(s), min(tabelle.sizeHintForColumn(s), hoechst)] +
                         [_feld_breite(w) + 2 for w in felder])
            tabelle.setColumnWidth(s, tabelle._eigene_breiten.get(s, breite))
    finally:
        tabelle._passt_an = False
    zeilen_hoehe(tabelle)
    _gekuerzt_im_tooltip(tabelle)


def _von_hand(tabelle: QtWidgets.QTableWidget, s: int, breite: int):
    """Mit der Maus gezogene Spaltenbreite merken (gilt auch nach dem naechsten Fuellen)."""
    if not tabelle._passt_an and QtWidgets.QApplication.mouseButtons() != QtCore.Qt.MouseButton.NoButton:
        tabelle._eigene_breiten[s] = breite


def zahlen_rechts(tabelle: QtWidgets.QTableWidget):
    """Zahlen (auch mit Einheit) und Zahlenfelder rechtsbuendig, damit die Stellen untereinander stehen."""
    rechts = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
    for z in range(tabelle.rowCount()):
        for s in range(tabelle.columnCount()):
            it, w = tabelle.item(z, s), tabelle.cellWidget(z, s)
            if it is not None and ZAHL.match(it.text().strip()):
                it.setTextAlignment(rechts)
            if isinstance(w, QtWidgets.QAbstractSpinBox):
                w.setAlignment(rechts)


def _gekuerzt_im_tooltip(tabelle: QtWidgets.QTableWidget):
    """Gekuerzter Text (…) steht ganz im Tooltip."""
    fm = tabelle.fontMetrics()
    for z in range(tabelle.rowCount()):
        for s in range(tabelle.columnCount()):
            it = tabelle.item(z, s)
            if it is None or not it.text() or it.text() in it.toolTip():
                continue
            if fm.horizontalAdvance(it.text()) + RAND > tabelle.columnWidth(s):
                it.setToolTip(it.text() + ("\n" + it.toolTip() if it.toolTip() else ""))


def zeilen_hoehe(tabelle: QtWidgets.QTableWidget) -> int:
    """Zeilen so hoch wie das hoechste Feld in einer Zelle (mindestens Schrift plus Luft); gibt die Hoehe zurueck."""
    hoehe = max([tabelle.fontMetrics().height() + 12] +
                [w.sizeHint().height() for z in range(tabelle.rowCount()) for s in range(tabelle.columnCount())
                 if (w := tabelle.cellWidget(z, s)) is not None])
    tabelle.verticalHeader().setDefaultSectionSize(hoehe)
    for z in range(tabelle.rowCount()):
        tabelle.setRowHeight(z, hoehe)
    return hoehe


def inhalt_breite(tabelle: QtWidgets.QTableWidget) -> int:
    """Breite, in die alle sichtbaren Spalten ohne Querlaufleiste passen."""
    kopf = tabelle.verticalHeader()
    return sum(tabelle.columnWidth(s) for s in range(tabelle.columnCount()) if not tabelle.isColumnHidden(s)) + \
        2 * tabelle.frameWidth() + (kopf.width() if kopf.isVisible() else 0)
