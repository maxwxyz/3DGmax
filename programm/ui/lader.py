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

    fortschritt(tr("Geometrie lesen …"))
    modell = lade_modell(pfad)
    fortschritt(tr("PMI lesen …"))
    pmi = lies_pmi(modell)
    fortschritt(tr("Struktur und Grafik …"))
    grafik = lies_grafik(modell.datei, _laengen_skala(modell.datei)) if modell.datei else {}
    pmi = ergaenze_hinweise(pmi, grafik)
    ansichten = lies_ansichten(modell, pmi)
    from ..kern import norm
    erkannt = norm.erkenne(pfad, pmi)
    norm.setze(pmi, erkannt.art)
    return Ergebnis(pfad, modell, pmi, ansichten, lies_baum(modell), flaechen_farben(modell), grafik, erkannt)


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
