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


def _startzeit_melden(zeiten: dict, fenster):
    """--startzeit: Dauer der Startphasen in der Statuszeile und in einer Datei (fuer Messungen auf Windows/macOS)."""
    import tempfile
    import time
    zeiten["3D bereit"] = time.perf_counter()
    namen = list(zeiten)
    from .i18n import tr
    text = ", ".join(f"{tr(b)}: {zeiten[b] - zeiten[a]:.2f} s" for a, b in zip(namen, namen[1:]))
    gesamt = zeiten[namen[-1]] - zeiten[namen[0]]
    pfad = os.path.join(tempfile.gettempdir(), "3DGmax-startzeit.txt")
    with open(pfad, "a", encoding="utf-8") as f:
        f.write(f"gesamt {gesamt:.2f} s – {text}\n")
    fenster.statusBar().showMessage(tr("Start {:.2f} s – {} ({})").format(gesamt, text, pfad), 30000)
    for name in ("Qt", "Module", "Fenster", "3D bereit"):  # Phasennamen fuer die Uebersetzungspruefung
        tr(name)
    print(f"STARTZEIT gesamt {gesamt:.2f} s – {text}", flush=True)


def startbild_pixmap(unterzeile: str, k: float = 2.0):
    """Bild des Startfensters: Symbol, Name, Unterzeile (k: Pixeldichte, scharf auf Retina/HiDPI)."""
    from PySide6 import QtCore, QtGui
    from .i18n import HIER
    bild = QtGui.QPixmap(int(420 * k), int(200 * k))
    bild.setDevicePixelRatio(k)
    bild.fill(QtGui.QColor("#f4f6f9"))
    maler = QtGui.QPainter(bild)
    maler.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    maler.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    symbol = QtGui.QPixmap(os.path.join(HIER, "icon.png"))
    if not symbol.isNull():
        maler.drawPixmap(QtCore.QRect(28, 46, 96, 96), symbol)
    maler.setPen(QtGui.QColor("#1d2330"))
    schrift = maler.font()
    schrift.setPointSize(26)
    schrift.setBold(True)
    maler.setFont(schrift)
    maler.drawText(QtCore.QRect(146, 56, 260, 44), QtCore.Qt.AlignmentFlag.AlignLeft, "3DGmax")
    schrift.setPointSize(11)
    schrift.setBold(False)
    maler.setFont(schrift)
    maler.setPen(QtGui.QColor("#5a6475"))
    maler.drawText(QtCore.QRect(148, 102, 260, 22), QtCore.Qt.AlignmentFlag.AlignLeft, unterzeile)
    maler.end()
    return bild


class _StarterBild:
    """Startbild des PyInstaller-Starters weiterverwenden (gleiche Schnittstelle wie QSplashScreen): kein Wechsel
    auf ein zweites Bild, das je nach Bildschirmskalierung anders gross waere und springen wuerde."""

    def __init__(self, modul):
        self._m = modul

    def showMessage(self, text, *_):  # noqa: N802 - wie QSplashScreen
        try:
            self._m.update_text(text)
        except Exception:  # noqa: BLE001 - Starterbild schon zu
            pass

    def finish(self, _fenster):
        starter_bild_zu()


def startbild(app):
    """Startbild direkt nach Qt (vor OCCT und Hauptfenster), damit sofort sichtbar ist, dass die App startet; im
    gebauten Programm unter Windows/Linux bleibt das Bild des Starters bis zum Hauptfenster stehen."""
    from PySide6 import QtCore, QtGui, QtWidgets
    from .i18n import tr
    from .version import VERSION
    try:
        if "_PYI_SPLASH_IPC" not in os.environ:  # kein Starterbild (macOS, nicht gebaut): pyi_splash meldet sonst laut
            raise ImportError
        import pyi_splash
        if pyi_splash.is_alive():
            s = _StarterBild(pyi_splash)
            s.showMessage(tr("3D-Module werden geladen …"))
            return s
    except Exception:  # noqa: BLE001 - nicht gebaut oder Starter ohne Bildschirm
        pass
    s = QtWidgets.QSplashScreen(startbild_pixmap(tr("Version {}").format(VERSION)))
    s.showMessage(tr("3D-Module werden geladen …"), QtCore.Qt.AlignmentFlag.AlignBottom |
                  QtCore.Qt.AlignmentFlag.AlignHCenter, QtGui.QColor("#5a6475"))
    s.show()
    app.processEvents()
    starter_bild_zu()
    return s


def starter_bild_zu():
    """Startbild des PyInstaller-Starters (Windows/Linux, erscheint vor Python) schliessen."""
    try:
        if "_PYI_SPLASH_IPC" not in os.environ:
            return
        import pyi_splash
        pyi_splash.close()
    except Exception:  # noqa: BLE001 - nicht gebaut (ImportError) oder Starter ohne Bildschirm (KeyError)
        pass


def datei_oeffner(app):
    """macOS: Finder (Doppelklick, Oeffnen mit, Ablegen auf das Symbol) schickt Dateien als QFileOpenEvent statt als
    Argument. Vor dem Fenster eintreffende Dateien werden gemerkt, danach direkt geladen."""
    from PySide6 import QtCore

    class Oeffner(QtCore.QObject):
        def __init__(self):
            super().__init__(app)
            self.fenster = None
            self.offen: list[str] = []

        def eventFilter(self, obj, ev):
            if ev.type() == QtCore.QEvent.Type.FileOpen and ev.file():
                pfad = os.path.abspath(ev.file())
                if self.fenster is None:
                    self.offen.append(pfad)
                else:
                    self.fenster.lade(pfad)
                return True
            return False

        def bereit(self, fenster) -> list[str]:
            """Fenster steht: ab jetzt direkt laden; liefert die bis dahin gemeldeten Dateien."""
            self.fenster = fenster
            offen, self.offen = self.offen, []
            return offen

    oeffner = Oeffner()
    app.installEventFilter(oeffner)
    return oeffner


def groesse_einstellen():
    """Groesse der Oberflaeche (Ansicht > Groesse der Oberflaeche) vor dem Anlegen der QApplication setzen; eine
    gesetzte Umgebungsvariable QT_SCALE_FACTOR hat Vorrang."""
    if os.environ.get("QT_SCALE_FACTOR"):
        return
    from .ui.groesse import gespeicherte_skalierung
    v = gespeicherte_skalierung()
    if abs(v - 1.0) > 0.01:
        os.environ["QT_SCALE_FACTOR"] = f"{v:.2f}"


def main(argv=None) -> int:
    """Optionen: datei.stp, --selbsttest, --bild ausgabe.png (Modell laden, 3D-Bild speichern, beenden),
    --startzeit (Dauer der Startphasen messen)."""
    import time
    zeiten = {"Start": time.perf_counter()}
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selbsttest" in argv or "--bild" in argv:
        starter_bild_zu()
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
    groesse_einstellen()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    from .i18n import qt_uebersetzung
    qt_uebersetzung(app)
    oeffner = datei_oeffner(app)
    zeiten["Qt"] = time.perf_counter()
    from PySide6 import QtGui
    from .i18n import HIER, tr
    symbol = os.path.join(HIER, "icon.png")
    if os.path.isfile(symbol):
        app.setWindowIcon(QtGui.QIcon(symbol))
    start = None if bild else startbild(app)
    from .ui.hauptfenster import Hauptfenster
    zeiten["Module"] = time.perf_counter()
    if start is not None:
        start.showMessage(tr("Fenster wird aufgebaut …"), QtCore.Qt.AlignmentFlag.AlignBottom |
                          QtCore.Qt.AlignmentFlag.AlignHCenter, QtGui.QColor("#5a6475"))
        app.processEvents()
    fenster = Hauptfenster()
    fenster.show()
    if start is not None:
        start.finish(fenster)
    zeiten["Fenster"] = time.perf_counter()
    if "--startzeit" in argv:
        def warte_3d():
            if getattr(fenster.ansicht, "_bereit", True) or time.perf_counter() - zeiten["Fenster"] > 10:
                _startzeit_melden(zeiten, fenster)  # nach 10 s ohne 3D-Ansicht trotzdem melden
            else:
                QtCore.QTimer.singleShot(20, warte_3d)
        QtCore.QTimer.singleShot(0, warte_3d)
    app.processEvents()  # Dateien aus dem Finder, die mit dem Start kommen
    dateien = [a for a in argv if not a.startswith("-")] + oeffner.bereit(fenster)
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
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
