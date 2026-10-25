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
