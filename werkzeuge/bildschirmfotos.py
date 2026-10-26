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
os.environ.setdefault("DG_LANG", "de")  # Doku-Bilder auf Deutsch (DG_LANG=en fuer englische)

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

    def messen():
        from programm.kern import messen as km
        f._schnitt(None)
        f.ansichten.liste.setCurrentRow(0)
        f.ansicht.standard("iso")
        f.aktionen["messen"].trigger()
        fl = f.erg.modell.flaechen
        zyl = [p for p in f.erg.pmi if p.typ == "Size_Diameter" and p.flaechen][:2]
        f.messen.fang.setChecked(False)
        for p in zyl:
            fz = fl[sorted(p.flaechen)[0]]
            c = km._mittelpunkt(fz)
            f.messen.setze_modus("radius")
            f.messen.element(fz, (c.X(), c.Y(), c.Z()))
        a, b = km._mittelpunkt(fl[0]), km._mittelpunkt(fl[40])
        f.messen.setze_modus("abstand")
        f.messen.element(fl[0], (a.X(), a.Y(), a.Z()))
        f.messen.element(fl[40], (b.X(), b.Y(), b.Z()))

    def vergleich():
        f.messen.loesche_alle()
        f.aktionen["messen_ende"].trigger()
        d = os.path.join(WURZEL, "tests", "daten")
        f.starte_vergleich({"alt": os.path.join(d, "nist_ctc_01_asme1_ap242-e1.stp"),
                            "neu": os.path.join(d, "varianten", "ctc01_geo_pmi.stp"),
                            "toleranz": 0.01, "suchweite": 2.0}, warten=True)
        f.aenderungen.pruefen_starten()
        f.aenderungen.gehe(+1)
        f.aenderungen.gehe(+1)

    schritte += [start, lambda: foto(f, os.path.join(ziel, f"geladen_{thema}.png")), pmi_waehlen,
                 lambda: foto(f, os.path.join(ziel, f"pmi_{thema}.png")), ansicht,
                 lambda: foto(f, os.path.join(ziel, f"ansicht_{thema}.png")),
                 lambda: f._schnitt("x"), lambda: foto(f, os.path.join(ziel, f"schnitt_{thema}.png")),
                 messen, lambda: foto(f, os.path.join(ziel, f"messen_{thema}.png")),
                 vergleich, lambda: foto(f, os.path.join(ziel, f"vergleich_{thema}.png"))]
    QtCore.QTimer.singleShot(800, weiter)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
