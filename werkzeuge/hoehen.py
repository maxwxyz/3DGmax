"""Bedienelemente finden, die nicht die gemeinsame Hoehe haben (Regel: Knoepfe, Auswahllisten, Zahlen- und
Eingabefelder sind ueberall gleich hoch, siehe ui/thema.bedien_hoehe).

Aufruf: QT_QPA_PLATFORM=offscreen pixi run python werkzeuge/hoehen.py
Baut das Hauptfenster mit seinen Docks und alle Dialoge aus programm/ui (wie werkzeuge/tooltips.py) und listet je
Fenster die Elemente mit abweichender Hoehe. Gemessen wird die Hoehe, die das Element im Layout bekommt (Groessenvorschlag
in den Grenzen von Mindest- und Hoechstmass), also auch bei verborgenen Leisten. Beruehrt die echten Einstellungen nicht.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DG_EINSTELLUNGEN", os.path.join(tempfile.mkdtemp(), "einstellungen.ini"))

from PySide6 import QtWidgets  # noqa: E402

ARTEN = (QtWidgets.QPushButton, QtWidgets.QToolButton, QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox,
         QtWidgets.QLineEdit)
TOLERANZ = 1  # px


def hoehe(w: QtWidgets.QWidget) -> int:
    """Hoehe im Layout: Vorschlag in den Grenzen des Elements (feste Hoehe der Bedienelemente)."""
    w.ensurePolished()
    return max(w.minimumHeight(), min(w.sizeHint().height(), w.maximumHeight()))


def _innen(w: QtWidgets.QWidget) -> bool:
    """Qt-Innereien: Feld in Drehfeld/Auswahl, Editor einer Tabelle, Knoepfe von Reitern, Docks, Menues."""
    p = w.parentWidget()
    if isinstance(p, (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox, QtWidgets.QTabBar, QtWidgets.QDockWidget,
                      QtWidgets.QMenuBar, QtWidgets.QLineEdit, QtWidgets.QAbstractScrollArea)):
        return True
    return w.objectName().startswith("qt_") or type(w).__name__ in ("QScrollBar",)


def abweichend(fenster: QtWidgets.QWidget, soll: int) -> list[str]:
    """Beschreibung der Bedienelemente mit anderer Hoehe als soll."""
    funde = []
    for w in fenster.findChildren(QtWidgets.QWidget):
        if not isinstance(w, ARTEN) or _innen(w):
            continue
        h = hoehe(w)
        if abs(h - soll) > TOLERANZ:
            text = w.text() if isinstance(w, (QtWidgets.QAbstractButton, QtWidgets.QLineEdit)) else \
                w.currentText() if isinstance(w, QtWidgets.QComboBox) else ""
            funde.append(f"{type(w).__name__:14} {h:3d} px {text[:40]!r}")
    return funde


def main(argv) -> int:
    app = QtWidgets.QApplication(argv[:1])  # noqa: F841
    import tooltips
    from programm.ui import thema
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    soll = thema.bedien_hoehe()
    summe = 0
    for name, fenster in [("Hauptfenster", f)] + list(tooltips.dialoge(f)):
        funde = abweichend(fenster, soll)
        if funde:
            print(f"\n== {name} ({len(funde)})")
            print("\n".join("   " + x for x in sorted(set(funde))))
            summe += len(funde)
    print(f"\n{summe} Bedienelemente nicht {soll} px hoch")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
