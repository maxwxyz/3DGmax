"""App-Symbole aus packaging/logo.svg erzeugen: programm/icon.png, icon.ico, icon.icns (icns nur auf macOS).

Aufruf: pixi run python packaging/make_icon.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtSvg, QtWidgets  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(WURZEL, "packaging", "logo.svg")
ZIEL = os.path.join(WURZEL, "programm")


def bild(groesse: int) -> QtGui.QImage:
    img = QtGui.QImage(groesse, groesse, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    QtSvg.QSvgRenderer(SVG).render(p)
    p.end()
    return img


def main():
    QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    bild(512).save(os.path.join(ZIEL, "icon.png"))
    bild(256).save(os.path.join(ZIEL, "icon.ico"))
    if sys.platform == "darwin" and shutil.which("iconutil"):
        satz = os.path.join(tempfile.mkdtemp(), "icon.iconset")
        os.makedirs(satz)
        for g in (16, 32, 128, 256, 512):
            bild(g).save(os.path.join(satz, f"icon_{g}x{g}.png"))
            bild(2 * g).save(os.path.join(satz, f"icon_{g}x{g}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", satz, "-o", os.path.join(ZIEL, "icon.icns")], check=True)
    print("Symbole erzeugt in", ZIEL)


if __name__ == "__main__":
    main()
