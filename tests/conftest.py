import os
import sys

import pytest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
DATEN = os.path.join(WURZEL, "tests", "daten")


def pfad(name):
    return os.path.join(DATEN, name)


@pytest.fixture(scope="session")
def ctc01():
    from programm.kern.laden import lade_step
    return lade_step(pfad("nist_ctc_01_asme1_ap242-e1.stp"))


@pytest.fixture(scope="session")
def ftc10():
    from programm.kern.laden import lade_step
    return lade_step(pfad("nist_ftc_10_asme1_ap242-e2.stp"))


@pytest.fixture(scope="session")
def ftc07():
    from programm.kern.laden import lade_step
    return lade_step(pfad("nist_ftc_07_asme1_ap242-e2.stp"))


def testdatei(name: str, url: str) -> str:
    """Fremde Testdatei ohne klare Lizenz: lokal aus daten/ oder einmalig laden (Cache), sonst Test ueberspringen."""
    import urllib.request
    for ordner in (os.path.join(WURZEL, "daten", "qif"), os.environ.get("DG_TESTDATEN") or "",
                   os.path.join(os.path.expanduser("~"), ".cache", "3dgmax")):
        if ordner and os.path.isfile(os.path.join(ordner, name)):
            return os.path.join(ordner, name)
    ordner = os.environ.get("DG_TESTDATEN") or os.path.join(os.path.expanduser("~"), ".cache", "3dgmax")
    ziel = os.path.join(ordner, name)
    try:
        os.makedirs(ordner, exist_ok=True)
        anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (3DGmax-Test)"})
        with urllib.request.urlopen(anfrage, timeout=120) as r, open(ziel + ".tmp", "wb") as f:
            f.write(r.read())
        os.replace(ziel + ".tmp", ziel)
    except Exception as e:  # noqa: BLE001 - ohne Netz ueberspringen
        pytest.skip(f"Testdatei {name} nicht verfuegbar: {e}")
    return ziel


QIF_URL = "https://raw.githubusercontent.com/QualityInformationFramework/qif-community/master/samples/NISTmodels/"


@pytest.fixture(scope="session")
def qif_ctc01():
    """NIST CTC-01 als QIF 3.0 (qif-community, Lizenz nicht angegeben: nicht im Repo, beim Test geladen)."""
    return testdatei("nist_ctc_01_asme1_ap242.qif", QIF_URL + "nist_ctc_01_asme1_ap242.qif")


# --- Oberflaeche ohne Bildschirm; echte Einstellungen nie beruehren ---
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DG_LANG"] = "de"


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    os.environ["DG_EINSTELLUNGEN"] = str(tmp_path_factory.mktemp("ein") / "einstellungen.ini")
    from PySide6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def fenster(app, tmp_path, monkeypatch):
    monkeypatch.setenv("DG_EINSTELLUNGEN", str(tmp_path / "einstellungen.ini"))
    from programm.ui.hauptfenster import Hauptfenster
    f = Hauptfenster()
    f.show()
    yield f
    f.close()
    f.deleteLater()
    _weg_damit(app)


def _weg_damit(app):
    """Geschlossene Fenster wirklich loeschen: ohne Ereignisschleife bleiben sie sonst bis zum Ende der Sitzung,
    und jedes setStyleSheet (Thema, Einstellungen) poliert alle alten Widgets mit - unter Windows bis zur Zeitgrenze."""
    from PySide6 import QtCore, QtWidgets
    for w in app.topLevelWidgets():  # nur eigene Fenster, keine Qt-Helfer (Tooltip, Menues)
        if isinstance(w, (QtWidgets.QMainWindow, QtWidgets.QDialog)) and not w.isVisible() and w.parent() is None:
            w.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


@pytest.fixture
def fenster_ctc01(fenster):
    fenster.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    return fenster


@pytest.fixture(autouse=True)
def keine_modalen_dialoge(monkeypatch):
    """Modale Dialoge wuerden ohne Bildschirm ewig warten (CI) -> sofort zurueck, Meldung merken."""
    from PySide6 import QtWidgets
    meldungen = []

    def merke(*args, **kw):
        meldungen.append(args[2] if len(args) > 2 else "")
        return QtWidgets.QMessageBox.StandardButton.Ok

    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QtWidgets.QMessageBox, name, merke)
    monkeypatch.setattr(QtWidgets.QDialog, "exec", lambda self: 0)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    return meldungen
