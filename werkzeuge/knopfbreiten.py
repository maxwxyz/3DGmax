"""Knoepfe finden, die breiter als ihr Inhalt sind (Regel: Knoepfe nutzen nie die ganze Leisten- oder Fensterbreite;
kein Dehnfaktor, keine Expanding-Breite, eine Knopfreihe endet mit einer Dehnung).

Aufruf: QT_QPA_PLATFORM=offscreen pixi run python werkzeuge/knopfbreiten.py
Zieht jede Seitenleiste des Hauptfensters (herausgeloest) und jeden Dialog aus programm/ui (wie werkzeuge/tooltips.py)
breit auf und listet sichtbare Knoepfe, die mehr als ZUGABE px breiter sind als ihr Groessenvorschlag. Beruehrt die
echten Einstellungen nicht.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DG_EINSTELLUNGEN", os.path.join(tempfile.mkdtemp(), "einstellungen.ini"))

from PySide6 import QtWidgets  # noqa: E402

ZUGABE = 40  # px ueber dem Groessenvorschlag
BREIT = (1400, 900)  # so breit aufgezogen zeigt sich jede Dehnung


def _ausgenommen(k: QtWidgets.QAbstractButton) -> bool:
    """Qt-Innereien und Werkzeugleisten (Reiter, Docktitel, Rollleisten, Knoepfe in Werkzeugleisten)."""
    w = k.parentWidget()
    while w is not None:
        if isinstance(w, (QtWidgets.QToolBar, QtWidgets.QTabBar, QtWidgets.QMenuBar, QtWidgets.QAbstractSpinBox,
                          QtWidgets.QComboBox, QtWidgets.QCalendarWidget)):
            return True
        if w.isWindow():
            break
        w = w.parentWidget()
    return k.objectName().startswith("qt_") or not isinstance(k, (QtWidgets.QPushButton, QtWidgets.QToolButton))


def _sichtbare(fenster: QtWidgets.QWidget) -> list[str]:
    funde = []
    for k in fenster.findChildren(QtWidgets.QAbstractButton):
        if _ausgenommen(k) or not k.isVisibleTo(fenster) or k.width() <= k.sizeHint().width() + ZUGABE:
            continue
        funde.append(f"{type(k).__name__:12} {k.width():4d} px statt {k.sizeHint().width():3d} {k.text()[:40]!r}")
    return funde


def zu_breit(fenster: QtWidgets.QWidget) -> list[str]:
    """Beschreibung der sichtbaren Knoepfe, die breiter als ihr Inhalt (plus Zugabe) sind - auf jeder Seite der
    Reiter und Stapel im Fenster."""
    app = QtWidgets.QApplication.instance()
    funde = _sichtbare(fenster)
    for stapel in fenster.findChildren(QtWidgets.QStackedWidget):
        if not stapel.isVisibleTo(fenster):
            continue
        alt = stapel.currentIndex()
        for i in range(stapel.count()):
            stapel.setCurrentIndex(i)
            _warte(app)
            funde += _sichtbare(stapel)
        stapel.setCurrentIndex(alt)
    return list(dict.fromkeys(funde))


def _warte(app):
    for _ in range(5):
        app.processEvents()


def fenster_breit(hauptfenster) -> list[tuple[str, QtWidgets.QWidget]]:
    """Alle Seitenleisten (herausgeloest, breit) und Dialoge (breit) gezeigt; Liste (Name, Fenster) zum Pruefen."""
    import tooltips
    app = QtWidgets.QApplication.instance()
    hauptfenster.resize(*BREIT)
    hauptfenster.show()
    for name in hauptfenster.WERKZEUG_LEISTEN:  # Werkzeugleisten unten anlegen
        anlegen = {"kette": "zeige_toleranzkette"}.get(name, f"zeige_{name}")
        getattr(hauptfenster, anlegen)(nur_anlegen=True)
    liste = []
    for d in hauptfenster.findChildren(QtWidgets.QDockWidget):
        if d.widget() is None:
            continue
        d.setFloating(True)
        d.show()
        for werkzeug in d.findChildren(QtWidgets.QDialog):  # Werkzeugfenster in der Leiste (sonst verborgen)
            werkzeug.show()
        d.resize(*BREIT)
        liste.append((d.objectName(), d))
    _warte(app)
    for name, dlg in tooltips.dialoge(hauptfenster):
        dlg.resize(*BREIT)
        dlg.show()
        liste.append((name, dlg))
    _warte(app)
    return liste


def main(argv) -> int:
    app = QtWidgets.QApplication(argv[:1])  # noqa: F841
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    summe = 0
    for name, fenster in fenster_breit(f):
        funde = zu_breit(fenster)
        if funde:
            print(f"\n== {name} ({len(funde)})")
            print("\n".join("   " + x for x in sorted(set(funde))))
            summe += len(funde)
    print(f"\n{summe} Knöpfe breiter als ihr Inhalt")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
