"""Startbild fuer den PyInstaller-Starter (Windows/Linux) erzeugen: packaging/startbild.png.

    pixi run python packaging/startbild.py

Gleiches Aussehen wie das Qt-Startbild (programm.app.startbild_pixmap), zweisprachige Unterzeile, ohne Version
(das Bild liegt fest im Repository). Ausgabe mit Pixeldichte 1, weil der Starter nicht skaliert.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def main():
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])  # noqa: F841 - fuer Schriften
    from programm.app import startbild_pixmap
    ziel = os.path.join(ROOT, "packaging", "startbild.png")
    startbild_pixmap("wird gestartet … / starting …", k=1.0).save(ziel, "PNG")
    print(ziel)


if __name__ == "__main__":
    main()
