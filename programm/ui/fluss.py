"""Fliesslayout: Bedienelemente nebeneinander, die bei wenig Breite in die naechste Zeile umbrechen (Qt hat keins
eingebaut; nach dem Qt-Beispiel "Flow Layout"). So bleiben Fenster mit langen Knopfreihen verkleinerbar."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class FlussLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, abstand: int = 6):
        super().__init__(parent)
        self._elemente: list[QtWidgets.QLayoutItem] = []
        self.setSpacing(abstand)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # noqa: N802 - Qt-Schnittstelle
        self._elemente.append(item)

    def count(self):
        return len(self._elemente)

    def itemAt(self, i):  # noqa: N802
        return self._elemente[i] if 0 <= i < len(self._elemente) else None

    def takeAt(self, i):  # noqa: N802
        return self._elemente.pop(i) if 0 <= i < len(self._elemente) else None

    def expandingDirections(self):  # noqa: N802
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, breite):  # noqa: N802
        return self._ordne(QtCore.QRect(0, 0, breite, 0), nur_messen=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._ordne(rect, nur_messen=False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        """Breitestes Element (umbrechen bis auf eine Spalte), Hoehe einer Zeile."""
        groesse = QtCore.QSize()
        for item in self._elemente:
            groesse = groesse.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return groesse + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _ordne(self, rect, nur_messen: bool) -> int:
        """Elemente zeilenweise einordnen; Rueckgabe: benoetigte Hoehe."""
        m = self.contentsMargins()
        flaeche = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, zeile = flaeche.x(), flaeche.y(), 0
        for item in self._elemente:
            if item.widget() is not None and item.widget().isHidden():
                continue
            w = item.sizeHint()
            if x + w.width() > flaeche.right() + 1 and zeile > 0:  # naechste Zeile
                x, y, zeile = flaeche.x(), y + zeile + self.spacing(), 0
            if not nur_messen:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), w))
            x += w.width() + self.spacing()
            zeile = max(zeile, w.height())
        return y + zeile - rect.y() + m.bottom()


def fluss_zeile(*widgets, abstand: int = 6) -> QtWidgets.QWidget:
    """Widget mit Fliesslayout fuer eine umbrechende Knopfreihe."""
    w = QtWidgets.QWidget()
    lay = FlussLayout(w, abstand)
    for x in widgets:
        lay.addWidget(x)
    return w


class _HoeheNachBreite(QtCore.QObject):
    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        if ev.type() == QtCore.QEvent.Type.Resize and obj.layout() is not None:
            hoehe = obj.layout().minimumHeightForWidth(obj.width())
            if hoehe > 0 and hoehe != obj.minimumHeight():
                obj.setMinimumHeight(hoehe)
        return False


def hoehe_nach_breite(widget: QtWidgets.QWidget):
    """Fuer Teile eines QSplitter mit umbrechenden Zeilen: Mindesthoehe passend zur Breite. Der Teiler fragt nur die
    Mindesthoehe ohne Breite - bei schmalem Fenster ueberlappten sonst die umgebrochenen Zeilen."""
    filter_ = _HoeheNachBreite(widget)
    widget.installEventFilter(filter_)
    widget._hoehe_nach_breite = filter_
