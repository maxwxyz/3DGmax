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


@pytest.fixture
def fenster_ctc01(fenster):
    fenster.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    return fenster
