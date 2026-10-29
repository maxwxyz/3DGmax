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


def _feld_groesse(w: QtWidgets.QWidget) -> QtCore.QSize:
    """Groesse, die das Feld braucht - mit Stylesheet (vor dem ersten Zeigen ist es noch nicht angewandt, dann waere
    der Innenabstand nicht eingerechnet und der Text vorn abgeschnitten)."""
    w.ensurePolished()
    groesse = w.sizeHint()
    if isinstance(w, QtWidgets.QComboBox) and w.isEditable():  # Qt rechnet den Innenabstand hier zu knapp
        opt = QtWidgets.QStyleOptionComboBox()
        w.initStyleOption(opt)
        feld = w.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox, opt,
                                        QtWidgets.QStyle.SubControl.SC_ComboBoxEditField, w)
        text = max((w.fontMetrics().horizontalAdvance(w.itemText(i)) for i in range(w.count())), default=0)
        groesse.setWidth(max(groesse.width(), text + w.width() - feld.width() + 8))
    return groesse.boundedTo(w.maximumSize())


def spalten_anpassen(tabelle: QtWidgets.QTableWidget, hoechst: int | None = None, neu: bool = False,
                     strecken: bool = False):
    """Spalten so breit wie Kopf, Text und Feld in der Zelle (Auswahl mit Pfeil, Zahlenfeld mit Einheit), Text
    hoechstens `hoechst` px breit; Zeilen so hoch wie das hoechste Feld, Text einzeilig, Zahlen rechtsbuendig.
    ResizeToContents allein reicht nicht: es misst nur Text, nicht die Felder in den Zellen. Alle Spalten bleiben
    ziehbar (Interactive); von Hand gezogene Breiten bleiben bei jedem weiteren Fuellen, bis `neu` (neuer Inhalt,
    z. B. ein anderes Modell) sie vergisst. `strecken`: letzte Spalte fuellt die Breite der Leiste. Nach dem Fuellen
    aufrufen, nicht bei jeder Aenderung einer Zelle (Qt misst hoechstens 1000 Zeilen je Spalte)."""
    kopf = tabelle.horizontalHeader()
    if not hasattr(tabelle, "_eigene_breiten"):
        tabelle._passt_an = False
        kopf.sectionResized.connect(lambda s, _alt, breite: _von_hand(tabelle, s, breite))
    if neu or getattr(tabelle, "_spalten_zahl", None) != tabelle.columnCount():  # eigene Breiten vergessen
        tabelle._eigene_breiten, tabelle._spalten_zahl = {}, tabelle.columnCount()
    tabelle.setWordWrap(False)
    tabelle.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
    # pixelweise: ein Feld, das den Fokus bekommt, rollt die Tabelle nicht gleich um eine ganze Spalte weiter
    tabelle.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
    kopf.setStretchLastSection(strecken)
    hoechst = hoechst or textbreite_hoechst(tabelle)
    gesperrt = tabelle.blockSignals(True)  # Ausrichtung und Tooltips sind keine Aenderung durch den Nutzer
    tabelle._passt_an = True
    try:
        zahlen_rechts(tabelle)
        for s in range(tabelle.columnCount()):
            kopf.setSectionResizeMode(s, QtWidgets.QHeaderView.ResizeMode.Interactive)
            if tabelle.isColumnHidden(s):
                continue
            felder = [w for z in range(tabelle.rowCount()) if (w := tabelle.cellWidget(z, s)) is not None]
            breite = max([kopf.sectionSizeHint(s), min(tabelle.sizeHintForColumn(s), hoechst)] +
                         [_feld_groesse(w).width() + 2 for w in felder])
            tabelle.setColumnWidth(s, tabelle._eigene_breiten.get(s, breite))
            for w in felder:
                # Fokus nur per Klick: sonst springt der Fokus beim Oeffnen des Fensters in ein Zellfeld und die
                # Tabelle rollt seitlich weg
                w.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
                if isinstance(w, QtWidgets.QComboBox) and w.lineEdit() is not None:  # vorn nicht abgeschnitten
                    w.lineEdit().setCursorPosition(0)
        zeilen_hoehe(tabelle)
        _gekuerzt_im_tooltip(tabelle)
    finally:
        tabelle._passt_an = False
        tabelle.blockSignals(gesperrt)


def automatisch_anpassen(tabelle: QtWidgets.QTableWidget, **art):
    """Fuer Tabellen, die zeilenweise wachsen (z. B. Messungen): nach neuen Zeilen einmal anpassen (gesammelt, nicht
    je Zeile); von Hand gezogene Breiten bleiben."""
    zeit = QtCore.QTimer(tabelle)
    zeit.setSingleShot(True)
    zeit.setInterval(0)
    zeit.timeout.connect(lambda: spalten_anpassen(tabelle, **art))
    tabelle.model().rowsInserted.connect(lambda *_a: zeit.start())
    tabelle.model().modelReset.connect(zeit.start)


def _von_hand(tabelle: QtWidgets.QTableWidget, s: int, breite: int):
    """Mit der Maus am Spaltenkopf gezogene Breite merken (gilt auch nach dem naechsten Fuellen; nicht das Ziehen
    der Seitenleiste, das nur die gestreckte letzte Spalte aendert)."""
    if not tabelle._passt_an and tabelle.horizontalHeader().underMouse() and \
            QtWidgets.QApplication.mouseButtons() != QtCore.Qt.MouseButton.NoButton:
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
                [_feld_groesse(w).height() for z in range(tabelle.rowCount()) for s in range(tabelle.columnCount())
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


class _FesteSpalte(QtWidgets.QTableView):
    """Erste Spalte ueber der Tabelle (Qt-Beispiel "Frozen Column"): gleiches Modell, gleiche Auswahl; sie bleibt beim
    Querrollen stehen, rollt aber mit nach unten."""

    def __init__(self, tabelle: QtWidgets.QTableWidget):
        super().__init__(tabelle)
        self.tabelle = tabelle
        self.setObjectName("festeSpalte")
        self.setModel(tabelle.model())
        self.setSelectionModel(tabelle.selectionModel())
        self.setSelectionBehavior(tabelle.selectionBehavior())
        self.setSelectionMode(tabelle.selectionMode())
        self.setEditTriggers(tabelle.editTriggers())  # z. B. Name per Doppelklick aendern wie in der Tabelle
        bearbeitbar = tabelle.editTriggers() != QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus if bearbeitbar else QtCore.Qt.FocusPolicy.NoFocus)
        self.setAlternatingRowColors(tabelle.alternatingRowColors())
        self.setShowGrid(tabelle.showGrid())
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(tabelle.verticalScrollMode())
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.verticalHeader().hide()
        self.setWordWrap(False)
        self.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        kopf = self.horizontalHeader()
        kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        kopf.setHighlightSections(False)
        kopf.setDefaultAlignment(tabelle.horizontalHeader().defaultAlignment())
        # Rollen, Breite und Zeilenhoehen folgen der Tabelle
        self.verticalScrollBar().valueChanged.connect(tabelle.verticalScrollBar().setValue)
        tabelle.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        # Methoden statt Lambdas: Qt trennt sie, wenn diese Spalte vor der Tabelle geloescht wird
        tabelle.horizontalHeader().sectionResized.connect(self._spalte_geaendert)
        tabelle.verticalHeader().sectionResized.connect(self._zeile_geaendert)
        tabelle.horizontalHeader().geometriesChanged.connect(self.lage)
        for signal in (tabelle.model().rowsInserted, tabelle.model().rowsRemoved, tabelle.model().modelReset,
                       tabelle.model().columnsInserted):
            signal.connect(self._spaeter)
        # Klicks wie in der Tabelle selbst (Doppelklick, Klick, Kontextmenue)
        self.clicked.connect(lambda i: tabelle.cellClicked.emit(i.row(), i.column()))
        self.doubleClicked.connect(lambda i: tabelle.cellDoubleClicked.emit(i.row(), i.column()))
        self.customContextMenuRequested.connect(
            lambda pos: tabelle.customContextMenuRequested.emit(
                tabelle.viewport().mapFromGlobal(self.viewport().mapToGlobal(pos))))
        tabelle.installEventFilter(self)
        self.lage()


    def _spalte_geaendert(self, spalte: int, *_):
        if spalte == 0:
            self.lage()

    def _zeile_geaendert(self, zeile: int, _alt: int, hoehe: int):
        self.setRowHeight(zeile, hoehe)

    def _spaeter(self, *_):
        QtCore.QTimer.singleShot(0, self, self.lage)

    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        if obj is self.tabelle and ev.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show,
                                                 QtCore.QEvent.Type.LayoutRequest):
            QtCore.QTimer.singleShot(0, self.lage)
        return False

    def lage(self):
        """Ueber der ersten Spalte der Tabelle; nur mit Zeilen (sonst laege sie ueber dem Hinweis der leeren
        Tabelle)."""
        t = self.tabelle
        for s in range(1, self.model().columnCount()):
            self.setColumnHidden(s, True)
        self.setColumnWidth(0, t.columnWidth(0))
        for z in range(t.rowCount()):
            if self.rowHeight(z) != t.rowHeight(z):
                self.setRowHeight(z, t.rowHeight(z))
        self.horizontalHeader().setFixedHeight(t.horizontalHeader().height())
        rand = t.frameWidth()
        links = rand + (t.verticalHeader().width() if t.verticalHeader().isVisible() else 0)
        self.setGeometry(links, rand, t.columnWidth(0) + 1, t.viewport().height() + t.horizontalHeader().height())
        self.verticalScrollBar().setValue(t.verticalScrollBar().value())
        self.setVisible(t.rowCount() > 0 and not t.isColumnHidden(0))


def erste_spalte_fest(tabelle: QtWidgets.QTableWidget) -> _FesteSpalte:
    """Erste Spalte (z. B. Name des Glieds) bleibt beim Querrollen stehen. Sie darf keine Zellfelder haben."""
    f = _FesteSpalte(tabelle)
    tabelle._feste_spalte = f
    return f
