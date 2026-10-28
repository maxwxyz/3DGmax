"""Bedienelemente ohne Tooltip finden (Regel: alles, was nicht selbsterklaerend ist, bekommt eine Erklaerung).

Aufruf: QT_QPA_PLATFORM=offscreen pixi run python werkzeuge/tooltips.py [--alle]
Baut das Hauptfenster mit seinen Docks und alle Dialoge aus programm/ui, die sich mit dem Hauptfenster als Elternteil
anlegen lassen, und listet Knoepfe, Eingabefelder, Auswahllisten und Kontrollkaestchen ohne Tooltip - je Fenster mit
Klasse und Text. Selbsterklaerende Standardknoepfe (OK, Schliessen, Abbrechen ...) zaehlen nicht, ausser mit --alle.
Beruehrt die echten Einstellungen nicht.
"""

from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DG_EINSTELLUNGEN"] = os.path.join(tempfile.mkdtemp(), "einstellungen.ini")

from PySide6 import QtWidgets  # noqa: E402

SELBSTERKLAEREND = {"OK", "Schließen", "Abbrechen", "Speichern", "Öffnen", "Ja", "Nein", "Übernehmen", "Hilfe",
                    "Close", "Cancel", "Save", "Open", "Yes", "No", "Apply", "Help", "Zurücksetzen", "Reset"}
ARTEN = (QtWidgets.QAbstractButton, QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox,
         QtWidgets.QSlider)


def _ort(w) -> str:
    """Wo ein Element ohne Text sitzt: Klassen der Eltern bis zum Fenster, dazu ein Nachbar-Label."""
    kette, p = [], w.parentWidget()
    while p is not None and len(kette) < 4:
        name = p.objectName() or type(p).__name__
        if isinstance(p, QtWidgets.QDockWidget):
            name = f"Dock '{p.windowTitle()}'"
        elif isinstance(p, QtWidgets.QGroupBox):
            name = f"Gruppe '{p.title()}'"
        kette.append(name)
        p = p.parentWidget()
    lay = w.parentWidget().layout() if w.parentWidget() is not None else None
    nachbar = ""
    if lay is not None:
        i = lay.indexOf(w)
        for j in (i - 1, i + 1):
            it = lay.itemAt(j) if 0 <= j < lay.count() else None
            if it is not None and isinstance(it.widget(), QtWidgets.QLabel) and it.widget().text():
                nachbar = f" neben '{it.widget().text()[:40]}'"
                break
    return " < ".join(kette) + nachbar


def ohne_tooltip(fenster: QtWidgets.QWidget, alle: bool = False) -> list[str]:
    """Beschreibung der Bedienelemente des Fensters ohne Tooltip."""
    funde = []
    for w in fenster.findChildren(QtWidgets.QWidget):
        if not isinstance(w, ARTEN) or w.toolTip():
            continue
        if isinstance(w, QtWidgets.QLineEdit) and isinstance(w.parent(), (QtWidgets.QAbstractSpinBox,
                                                                            QtWidgets.QComboBox)):
            continue  # Innenleben eines Drehfelds oder einer Auswahlliste
        if isinstance(w.parent(), (QtWidgets.QTableView, QtWidgets.QDockWidget, QtWidgets.QLineEdit,
                                   QtWidgets.QMenuBar)) or type(w).__name__ in ("QScrollBar", "QTabBar"):
            continue  # Qt-Innereien: Dock-Titelknoepfe, Loeschknopf im Suchfeld, Menue-Ueberlauf
        if w.objectName().startswith("qt_"):
            continue  # Qt-eigene Knoepfe (z. B. Ueberlauf der Werkzeugleiste)
        text = w.text() if isinstance(w, QtWidgets.QAbstractButton) else \
            w.placeholderText() if isinstance(w, QtWidgets.QLineEdit) else ""
        if not alle and text.replace("&", "") in SELBSTERKLAEREND:
            continue
        if isinstance(w, QtWidgets.QAbstractButton) and not text and w.icon().isNull():
            continue  # interne Knoepfe ohne Text und Symbol (z. B. Ecke einer Tabelle)
        funde.append(f"{type(w).__name__:14} {text!r}" + ("" if text else f"  in {_ort(w)}"))
    return funde


def dialoge(eltern):
    """Alle QDialog/QWidget-Fensterklassen aus programm/ui, die sich mit dem Hauptfenster anlegen lassen."""
    import programm.ui as paket
    for info in pkgutil.iter_modules(paket.__path__):
        try:
            modul = importlib.import_module(f"programm.ui.{info.name}")
        except Exception:  # noqa: BLE001 - Module mit Zusatzabhaengigkeiten auslassen
            continue
        for name, cls in inspect.getmembers(modul, inspect.isclass):
            if cls.__module__ != modul.__name__ or not issubclass(cls, QtWidgets.QDialog):
                continue
            for args in ((eltern,), (eltern, eltern), ()):
                try:
                    yield f"{info.name}.{name}", cls(*args)
                    break
                except Exception:  # noqa: BLE001 - Dialoge mit Pflichtangaben auslassen
                    continue


def main(argv) -> int:
    alle = "--alle" in argv
    app = QtWidgets.QApplication(argv[:1])  # noqa: F841
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    summe = 0
    for name, fenster in [("Hauptfenster", f)] + list(dialoge(f)):
        funde = ohne_tooltip(fenster, alle)
        if funde:
            print(f"\n== {name} ({len(funde)})")
            print("\n".join("   " + x for x in sorted(set(funde))))
            summe += len(funde)
    print(f"\n{summe} Bedienelemente ohne Tooltip")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
