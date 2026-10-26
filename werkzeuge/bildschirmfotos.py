"""Bildschirmfotos der App fuer Doku und Abnahme (braucht echten Bildschirm, kein offscreen).

Aufruf: pixi run python werkzeuge/bildschirmfotos.py [ausgabeordner] [--thema hell|dunkel]
Beruehrt die echten Einstellungen nicht (eigene INI im Ausgabeordner).
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DG_EINSTELLUNGEN"] = os.path.join(tempfile.mkdtemp(), "einstellungen.ini")

from PySide6 import QtCore, QtWidgets  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELL = os.path.join(WURZEL, "tests", "daten", "nist_ftc_10_asme1_ap242-e2.stp")


def foto(fenster, pfad):
    """Ganzes Fenster inkl. OpenGL (Bildschirm-Abgriff) und die 3D-Ansicht einzeln."""
    QtWidgets.QApplication.processEvents()
    bild = fenster.screen().grabWindow(0, fenster.frameGeometry().x(), fenster.frameGeometry().y(),
                                       fenster.frameGeometry().width(), fenster.frameGeometry().height())
    bild.save(pfad)
    fenster.ansicht.bild(pfad.replace(".png", "_3d.png"))


def main(argv):
    ziel = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else os.path.join(WURZEL, "docs", "bilder")
    os.makedirs(ziel, exist_ok=True)
    thema = argv[argv.index("--thema") + 1] if "--thema" in argv else "hell"
    app = QtWidgets.QApplication(argv[:1])
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    f.setze_thema(thema)
    f.resize(1500, 900)
    f.show()
    schritte = []

    def weiter():
        if schritte:
            schritte.pop(0)()
            QtCore.QTimer.singleShot(1200, weiter)
        else:
            app.quit()

    def start():
        foto(f, os.path.join(ziel, f"start_{thema}.png"))
        f.lade(MODELL, warten=True)

    def pmi_waehlen():
        f.pmi.waehle(lambda p: p.nummer == 33)

    def ansicht():
        f.ansichten.liste.setCurrentRow(2)

    schritte += [start, lambda: foto(f, os.path.join(ziel, f"geladen_{thema}.png")), pmi_waehlen,
                 lambda: foto(f, os.path.join(ziel, f"pmi_{thema}.png")), ansicht,
                 lambda: foto(f, os.path.join(ziel, f"ansicht_{thema}.png")),
                 lambda: f._schnitt("x"), lambda: foto(f, os.path.join(ziel, f"schnitt_{thema}.png"))]
    QtCore.QTimer.singleShot(800, weiter)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
