"""Modell im Hintergrund laden (STEP lesen, PMI, Ansichten, Grafik, Baum, Farben)."""

from __future__ import annotations

import traceback
from dataclasses import dataclass

from PySide6 import QtCore


@dataclass
class Ergebnis:
    pfad: str
    modell: object
    pmi: list
    ansichten: list
    baum: object
    farben: dict
    grafik: dict
    norm: object = None  # kern.norm.Norm (erkannt)


def lade_alles(pfad: str, fortschritt=lambda text: None) -> Ergebnis:
    from ..i18n import tr
    from ..kern.ansichten import _laengen_skala, lies_ansichten
    from ..kern.baum import lies_baum
    from ..kern.farben import flaechen_farben
    from ..kern.laden import lade_modell
    from ..kern.pmi_lesen import ergaenze_hinweise, lies_pmi
    from ..kern.praesentation import lies_grafik

    from ..kern.laden import ENDUNGEN_JT
    jt = pfad.lower().endswith(ENDUNGEN_JT)
    fortschritt(tr("JT wird umgewandelt (TKJT) – große Dateien brauchen einige Minuten …") if jt else
                tr("Geometrie lesen …"))
    modell = lade_modell(pfad)
    fortschritt(tr("PMI lesen …"))
    pmi = lies_pmi(modell)
    fortschritt(tr("Struktur und Grafik …"))
    if modell.datei:
        grafik = lies_grafik(modell.datei, _laengen_skala(modell.datei))
    elif getattr(modell, "qif", None) is not None:
        from ..kern import qif_grafik
        grafik = qif_grafik.grafik(modell.qif)
    elif getattr(modell, "prc", None) is not None:
        from ..kern.praesentation import prc_grafik
        grafik = prc_grafik(modell.prc)
    else:
        grafik = {}
    pmi = ergaenze_hinweise(pmi, grafik)
    if modell.datei:
        from ..kern.praesentation import in_teillage
        in_teillage(grafik, pmi, modell)  # Baugruppe: Grafik eines Teils an die Lage seiner Instanz
    ansichten = lies_ansichten(modell, pmi)
    from ..kern import pmi_erzeugen
    # Darstellung fuer PMI ohne Grafik in der Datei (Schreibebene aus der Ansicht, die sie zeigt)
    grafik.update(pmi_erzeugen.ergaenze(pmi, grafik, modell, ansichten))
    from ..kern import norm
    erkannt = norm.erkenne(pfad, pmi)
    norm.setze(pmi, erkannt.art)
    return Ergebnis(pfad, modell, pmi, ansichten, lies_baum(modell), flaechen_farben(modell), grafik, erkannt)


class Abbruch(Exception):
    """Hintergrundrechnung vom Nutzer abgebrochen (Ergebnis wird verworfen)."""


def melder(lader, melde):
    """Fortschritt melden; beendet die Rechnung, sobald der Nutzer abgebrochen hat."""
    def f(wert):
        if getattr(lader, "abgebrochen", False):
            raise Abbruch
        melde(wert)
    return f


class Lader(QtCore.QThread):
    fertig = QtCore.Signal(object)  # Ergebnis
    fehler = QtCore.Signal(str)
    stand = QtCore.Signal(str)

    def __init__(self, pfad: str, parent=None):
        super().__init__(parent)
        self.pfad = pfad
        self.abgebrochen = False

    def run(self):
        try:
            erg = lade_alles(self.pfad, self.stand.emit)
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            if not self.abgebrochen:
                self.fehler.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")
            return
        if not self.abgebrochen:
            self.fertig.emit(erg)
