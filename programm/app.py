"""Programmstart: pixi run python -m programm.app [datei.stp] [--selbsttest]."""

from __future__ import annotations

import os
import sys


def selbsttest() -> int:
    """Prueft Laden und PMI an einem eingebauten Beispiel; Rueckgabe 0 = in Ordnung."""
    from .ui.lader import lade_alles
    hier = os.path.dirname(os.path.abspath(__file__))
    kandidaten = [os.path.join(hier, "beispiele", "nist_ctc_01_asme1_ap242-e1.stp"),
                  os.path.join(os.path.dirname(hier), "tests", "daten", "nist_ctc_01_asme1_ap242-e1.stp")]
    pfad = next((p for p in kandidaten if os.path.isfile(p)), None)
    if pfad is None:
        print("SELBSTTEST FEHLER: Beispieldatei fehlt")
        return 2
    erg = lade_alles(pfad)
    ok = len(erg.modell.flaechen) == 117 and len(erg.pmi) == 23 and len(erg.ansichten) == 1
    print(f"SELBSTTEST {'OK' if ok else 'FEHLER'}: {len(erg.modell.flaechen)} Flaechen, "
          f"{len(erg.pmi)} PMI, {len(erg.ansichten)} Ansichten, {len(erg.grafik)} Grafiken")
    return 0 if ok else 1


def main(argv=None) -> int:
    """Optionen: datei.stp, --selbsttest, --bild ausgabe.png (Modell laden, 3D-Bild speichern, beenden)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selbsttest" in argv:
        return selbsttest()
    bild = argv[argv.index("--bild") + 1] if "--bild" in argv else None
    if bild:
        import tempfile
        os.environ.setdefault("DG_EINSTELLUNGEN", os.path.join(tempfile.mkdtemp(), "einstellungen.ini"))
        argv.remove(bild)
    from PySide6 import QtCore, QtWidgets
    QtCore.QCoreApplication.setOrganizationName("3DGmax")
    QtCore.QCoreApplication.setApplicationName("3DGmax")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    from PySide6 import QtGui
    from .i18n import HIER
    symbol = os.path.join(HIER, "icon.png")
    if os.path.isfile(symbol):
        app.setWindowIcon(QtGui.QIcon(symbol))
    from .ui.hauptfenster import Hauptfenster
    fenster = Hauptfenster()
    fenster.show()
    dateien = [a for a in argv if not a.startswith("-")]
    if bild:
        def speichern():
            ok = fenster.ansicht.bild(os.path.abspath(bild))
            print(f"BILD {'OK' if ok else 'FEHLER'}: {bild}", flush=True)
            app.exit(0 if ok else 1)
        if dateien:
            fenster.lade(os.path.abspath(dateien[0]), warten=True)
        QtCore.QTimer.singleShot(1500, speichern)
        return app.exec()
    if dateien:
        fenster.lade(os.path.abspath(dateien[0]))
    QtCore.QTimer.singleShot(300, fenster.erster_start)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
