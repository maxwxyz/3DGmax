"""Maus in Tabellen, app-weit (ein Filter fuer alle Tabellen):
- Mausrad ueber Zahlenfeldern und Auswahllisten rollt die umgebende Tabelle bzw. Leiste statt den Wert zu aendern
  (sonst verstellt das Rollen durch eine Tabelle versehentlich Werte). Werte aendern sich nur per Klick:
  Auswahllisten nie per Rad (wie unter macOS), Felder in Tabellenzellen nie (sie behalten nach der Wahl den Fokus, das
  naechste Rollen der Tabelle wuerde sie sonst verstellen), andere Zahlenfelder nur, wenn sie angeklickt wurden.
- Ein Feld in einer Tabellenzelle, das den Fokus ohne Klick bzw. Tab bekommt (Rad, Ueberfahren, Fensterwechsel, Code),
  waehlt seine Zeile nicht: Qt setzt sonst die aktuelle Zelle auf das Feld und waehlt damit die Zeile.
- Mittlere Maustaste rollt wie im Browser (`autorollen`)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

FELDER = (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)
GRUND = QtCore.Qt.FocusReason
TASTE_FOKUS = (GRUND.TabFocusReason, GRUND.BacktabFocusReason, GRUND.ShortcutFocusReason)
KLICK = QtCore.Qt.MouseButton.LeftButton | QtCore.Qt.MouseButton.RightButton
FOKUS = (QtCore.QEvent.Type.FocusIn, QtCore.QEvent.Type.FocusOut)


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


def zellfeld(w: QtWidgets.QWidget) -> tuple[QtWidgets.QAbstractItemView, QtCore.QModelIndex] | None:
    """Tabelle und Zelle, wenn `w` (oder ein Elternteil) ein Feld in einer Tabellenzelle ist."""
    while w is not None and not w.isWindow():
        eltern = w.parentWidget()
        tabelle = eltern.parentWidget() if eltern is not None else None
        if isinstance(tabelle, QtWidgets.QAbstractItemView) and eltern is tabelle.viewport():
            index = tabelle.indexAt(w.geometry().center())
            return (tabelle, index) if index.isValid() and tabelle.indexWidget(index) is w else None
        w = eltern
    return None


def fokus_waehlt(ev) -> bool:
    """Darf der Fokus die Zeile waehlen? Nur per Klick mit linker oder rechter Taste (das Rad und die mittlere Taste
    zum Rollen geben den Fokus mit demselben Grund) oder per Tastatur."""
    if ev.reason() == GRUND.MouseFocusReason:
        return bool(QtWidgets.QApplication.mouseButtons() & KLICK)
    return ev.reason() in TASTE_FOKUS


class Radsperre(QtCore.QObject):
    def __init__(self, eltern=None):
        super().__init__(eltern)
        self._innen = False  # ein Fokusereignis wird gerade selbst zugestellt

    def eventFilter(self, obj, ev):  # noqa: N802 - Qt
        typ = ev.type()
        if typ == QtCore.QEvent.Type.Polish and isinstance(obj, FELDER):
            obj.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)  # das Rad allein gibt keinen Fokus
        elif typ == QtCore.QEvent.Type.Wheel and isinstance(obj, FELDER) and not rad_aendert(obj):
            rollbereich = _rollbereich(obj)
            if rollbereich is not None:
                QtWidgets.QApplication.sendEvent(rollbereich.viewport(), ev.clone())
            return True  # Wert bleibt
        elif typ in FOKUS and not self._innen and not fokus_waehlt(ev) and \
                (tabelle := self._tabelle_zum_fokus(obj, typ)) is not None:
            self._ohne_wahl(obj, ev, tabelle)
            return True
        return False

    @staticmethod
    def _tabelle_zum_fokus(obj, typ) -> QtWidgets.QAbstractItemView | None:
        """Tabelle, deren Zeile Qt wegen dieses Fokuswechsels waehlen wuerde: beim Fokus fuer ein Zellfeld (FocusIn
        des Feldes) und beim Verlassen der Tabelle oder eines offenen Zelleditors in eines ihrer Zellfelder (FocusOut;
        der Editor schliesst dabei, und Qt setzt die aktuelle Zelle auf das Feld)."""
        if not isinstance(obj, QtWidgets.QWidget):
            return None
        if typ == QtCore.QEvent.Type.FocusIn:
            zelle = zellfeld(obj)
            return zelle[0] if zelle is not None else None
        neu = QtWidgets.QApplication.focusWidget()
        zelle = zellfeld(neu) if neu is not None else None
        return zelle[0] if zelle is not None and (obj is zelle[0] or zelle[0].isAncestorOf(obj)) else None

    def _ohne_wahl(self, obj, ev, tabelle: QtWidgets.QAbstractItemView):
        """Ereignis zustellen, ohne dass sich Auswahl und aktuelle Zelle der Tabelle aendern: Signale der Auswahl
        gesperrt, danach beides wie vorher (Qt setzt sie beim Fokus fuer ein Zellfeld auf dessen Zeile)."""
        wahl = tabelle.selectionModel()
        if wahl is None:
            QtWidgets.QApplication.sendEvent(obj, ev)
            return
        auswahl, aktuell = wahl.selection(), QtCore.QPersistentModelIndex(wahl.currentIndex())
        gesperrt = wahl.blockSignals(True)
        self._innen = True
        try:
            QtWidgets.QApplication.sendEvent(obj, ev)
        finally:
            self._innen = False
            wahl.select(auswahl, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
            wahl.setCurrentIndex(QtCore.QModelIndex(aktuell), QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
            wahl.blockSignals(gesperrt)
            tabelle.viewport().update()


def installieren(app: QtWidgets.QApplication):
    """Einmal je Anwendung."""
    if getattr(app, "_radsperre", None) is None:
        app._radsperre = Radsperre(app)
        app.installEventFilter(app._radsperre)
        from . import autorollen
        autorollen.installieren(app)
