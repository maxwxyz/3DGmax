"""Rollen mit der mittleren Maustaste wie im Browser - in allen Tabellen, Listen, Baeumen und rollenden Leisten, auch
ueber Feldern in Tabellenzellen: Druecken setzt einen Anker (Marke), die Entfernung der Maus vom Anker gibt Richtung
und Tempo (um den Anker ein ruhiger Bereich). Nach dem Ziehen beendet das Loslassen das Rollen; nach einem kurzen
Klick rollt es weiter, bis zum naechsten Klick oder Esc. Nicht in der 3D-Ansicht (sie navigiert selbst mit der
mittleren Taste) und nicht in Aufklapplisten."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

BEREICHE = (QtWidgets.QAbstractItemView, QtWidgets.QScrollArea, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)
RUHE = 10  # px um den Anker ohne Rollen
TAKT = 16  # ms
TEMPO = 0.08  # px je Takt und px Abstand ausserhalb der Ruhe (100 px vom Anker: rund 450 px/s)
KLICK_ZEIT = 300  # ms: kuerzer und ohne Ziehen = Klick, das Rollen bleibt an
TYP = QtCore.QEvent.Type
MAUS = (TYP.MouseButtonPress, TYP.MouseButtonRelease, TYP.MouseButtonDblClick, TYP.MouseMove)


def _kann_rollen(bereich: QtWidgets.QAbstractScrollArea) -> bool:
    return any(b.maximum() > b.minimum() for b in (bereich.horizontalScrollBar(), bereich.verticalScrollBar()))


def rollbereich(w: QtWidgets.QWidget | None) -> QtWidgets.QAbstractScrollArea | None:
    """Naechster Rollbereich um `w`, der rollen kann (eine Tabelle, die nicht rollt, in einer rollenden Leiste: die
    Leiste; ueber der festen ersten Spalte die Tabelle darunter); None in der 3D-Ansicht und in Aufklapplisten."""
    if w is None or w.window().windowType() == QtCore.Qt.WindowType.Popup:
        return None
    while w is not None:
        if w.testAttribute(QtCore.Qt.WidgetAttribute.WA_PaintOnScreen):  # 3D-Ansicht (OpenGL zeichnet selbst)
            return None
        if isinstance(w, BEREICHE) and w.objectName() != "festeSpalte" and _kann_rollen(w):  # feste Spalte: Tabelle
            return w
        if w.isWindow():
            return None
        w = w.parentWidget()
    return None


def tempo(abstand: float) -> float:
    """Pixel je Takt fuer den Abstand der Maus vom Anker (mit Vorzeichen)."""
    rest = abs(abstand) - RUHE
    return 0.0 if rest <= 0 else (rest * TEMPO if abstand > 0 else -rest * TEMPO)


class _Anker(QtWidgets.QWidget):
    """Marke am Anker: Kreis mit Punkt und Pfeilen in die Richtungen, in die der Bereich rollen kann."""
    GROESSE = 30

    def __init__(self, bereich: QtWidgets.QAbstractScrollArea, quer: bool, hoch: bool):
        super().__init__(bereich)  # am Bereich, nicht am Viewport: rollt nicht mit dem Inhalt
        self.quer, self.hoch = quer, hoch
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(self.GROESSE, self.GROESSE)

    def paintEvent(self, _ev):  # noqa: N802 - Qt
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        farbe = self.palette().color(QtGui.QPalette.ColorRole.WindowText)
        grund = self.palette().color(QtGui.QPalette.ColorRole.Window)
        grund.setAlpha(225)
        p.setPen(QtGui.QPen(farbe, 1.2))
        p.setBrush(grund)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.drawEllipse(r)
        p.setBrush(farbe)
        m = r.center()
        p.drawEllipse(m, 2, 2)
        for dx, dy, an in ((0, -1, self.hoch), (0, 1, self.hoch), (-1, 0, self.quer), (1, 0, self.quer)):
            if an:
                spitze = m + QtCore.QPointF(dx, dy) * 11
                basis = m + QtCore.QPointF(dx, dy) * 6
                seite = QtCore.QPointF(dy, dx) * 3.5
                p.drawPolygon(QtGui.QPolygonF([spitze, basis + seite, basis - seite]))
        p.end()


class Autorollen(QtCore.QObject):
    def __init__(self, eltern=None):
        super().__init__(eltern)
        self.bereich: QtWidgets.QAbstractScrollArea | None = None
        self.anker = QtCore.QPoint()
        self.marke: _Anker | None = None
        self._rest = [0.0, 0.0]  # angefangene Schritte (quer, hoch)
        self._gezogen = False
        self._seit = QtCore.QElapsedTimer()
        self.uhr = QtCore.QTimer(self)
        self.uhr.setInterval(TAKT)
        self.uhr.timeout.connect(self.takt)
        app = QtWidgets.QApplication.instance()
        if app is not None:  # anderes Programm vorn: Rollen aus
            app.applicationStateChanged.connect(self._zustand)

    def _zustand(self, zustand):
        if zustand != QtCore.Qt.ApplicationState.ApplicationActive:
            self.beenden()

    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        typ = ev.type()
        if self.bereich is not None:
            return self._waehrend(ev, typ)
        if typ == TYP.MouseButtonPress and ev.button() == QtCore.Qt.MouseButton.MiddleButton and \
                isinstance(obj, QtWidgets.QWidget) and (bereich := rollbereich(obj)) is not None:
            self.starten(bereich, ev.globalPosition().toPoint())
            return True
        return False

    def _waehrend(self, ev, typ) -> bool:
        """Waehrend des Rollens gehoert die Maus dem Rollen (kein Waehlen, kein Ziehen, kein Hover)."""
        if typ == TYP.MouseButtonRelease and ev.button() == QtCore.Qt.MouseButton.MiddleButton:
            if self._gezogen or self._seit.elapsed() > KLICK_ZEIT:
                self.beenden()
            return True
        if typ == TYP.MouseButtonPress or (typ == TYP.KeyPress and ev.key() == QtCore.Qt.Key.Key_Escape):
            self.beenden()  # der Klick, der das Rollen beendet, wirkt sonst nicht
            return True
        if typ == TYP.MouseMove:
            self._gezogen |= (ev.globalPosition().toPoint() - self.anker).manhattanLength() > RUHE
        if typ == TYP.Wheel:  # wie im Browser: das Rad beendet das Rollen und rollt selbst
            self.beenden()
            return False
        return typ in MAUS

    def starten(self, bereich: QtWidgets.QAbstractScrollArea, anker: QtCore.QPoint):
        self.bereich, self.anker = bereich, QtCore.QPoint(anker)
        self._rest, self._gezogen = [0.0, 0.0], False
        self._seit.start()
        quer, hoch = (b.maximum() > b.minimum() for b in (bereich.horizontalScrollBar(), bereich.verticalScrollBar()))
        self.marke = _Anker(bereich, quer, hoch)
        self.marke.move(bereich.mapFromGlobal(anker) - QtCore.QPoint(_Anker.GROESSE // 2, _Anker.GROESSE // 2))
        self.marke.show()
        self.marke.raise_()
        form = QtCore.Qt.CursorShape
        QtWidgets.QApplication.setOverrideCursor(
            form.SizeAllCursor if quer and hoch else form.SizeVerCursor if hoch else form.SizeHorCursor)
        bereich.destroyed.connect(self._weg)
        self.uhr.start()

    def beenden(self):
        if self.bereich is None:
            return
        self.uhr.stop()
        try:
            self.bereich.destroyed.disconnect(self._weg)
        except (RuntimeError, TypeError):  # Bereich schon geloescht
            pass
        self.bereich = None
        if self.marke is not None:
            try:
                self.marke.deleteLater()
            except RuntimeError:
                pass
            self.marke = None
        QtWidgets.QApplication.restoreOverrideCursor()

    def _weg(self, *_):
        self.marke = None  # mit dem Bereich geloescht
        self.beenden()

    def takt(self):
        """Ein Schritt: je Richtung um das Tempo aus dem Abstand der Maus vom Anker (Bruchteile gesammelt). Die
        Leisten zaehlen in Zeilen (Tabelle zeilenweise) oder Pixeln: umgerechnet ueber Seite je Sichtbreite."""
        b = self.bereich
        if b is None or not b.isVisible():
            self.beenden()
            return
        d = QtGui.QCursor.pos() - self.anker
        self._gezogen |= d.manhattanLength() > RUHE
        sicht = b.viewport().size()
        for i, (leiste, abstand, laenge) in enumerate(((b.horizontalScrollBar(), d.x(), sicht.width()),
                                                       (b.verticalScrollBar(), d.y(), sicht.height()))):
            if leiste.maximum() <= leiste.minimum():
                continue
            self._rest[i] += tempo(abstand) * leiste.pageStep() / max(1, laenge)
            ganz = int(self._rest[i])
            if ganz:
                self._rest[i] -= ganz
                leiste.setValue(leiste.value() + ganz)


def installieren(app: QtWidgets.QApplication):
    """Einmal je Anwendung."""
    if getattr(app, "_autorollen", None) is None:
        app._autorollen = Autorollen(app)
        app.installEventFilter(app._autorollen)
