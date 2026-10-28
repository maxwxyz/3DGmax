"""Merkmalsliste (Bill of Characteristics) mit Ballonnummern fuer Pruefplanung und Erstmusterpruefung.

Merkmale sind pruefbare Masse und Form-/Lagetoleranzen. Nicht dazu gehoeren Bezuege, Hinweise sowie
theoretisch genaue Masse und Hilfsmasse. Die Ballonnummer ist die laufende Nummer in der Liste (Reihenfolge der PMI).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from ..i18n import tr
from .pmi import MASS, TOLERANZ

AUSGENOMMEN = {"Theoretisch", "Hilfsmass"}


@dataclass
class Merkmal:
    ballon: int
    pmi: object  # Pmi

    def grenzen(self) -> tuple[float | None, float | None]:
        """(obere, untere) Grenze: Hoechst-/Mindestmass bei Massen, Toleranzwert/0 bei Form und Lage."""
        p = self.pmi
        if p.art == MASS:
            return p.grenzen()
        return (p.wert, 0.0) if p.wert is not None else (None, None)


def ist_merkmal(p) -> bool:
    if p.art == TOLERANZ:
        return True
    return p.art == MASS and p.nennwert is not None and not (set(p.modifikatoren) & AUSGENOMMEN)


def liste(pmi: list) -> list[Merkmal]:
    return [Merkmal(i, p) for i, p in enumerate((p for p in pmi if ist_merkmal(p)), 1)]


def ballon_je_pmi(merkmale: list[Merkmal]) -> dict[int, int]:
    """PMI-Nummer -> Ballonnummer."""
    return {m.pmi.nummer: m.ballon for m in merkmale}


def _z(x) -> str:
    return "" if x is None else f"{x:.4f}".rstrip("0").rstrip(".")


SPALTEN = ("Ballon", "Nr", "Merkmal", "Wert", "Nennmaß", "Obere Grenze", "Untere Grenze", "Bezüge", "Ansichten",
           "Flächen", "Messwert", "i. O.", "Bemerkung")


def zeilen(merkmale: list[Merkmal], ansichten: list | None = None, messung: dict | None = None) -> list[list[str]]:
    """messung: Ballonnummer -> (Messwert, Bewertung) aus kern.qif_ergebnisse (fuellt Messwert und i. O.)."""
    je_pmi: dict[int, list[str]] = {}
    for a in ansichten or []:
        for nr in a.pmi_nummern:
            je_pmi.setdefault(nr, []).append(a.name)
    out = []
    for m in merkmale:
        p = m.pmi
        oben, unten = m.grenzen()
        out.append([str(m.ballon), str(p.nummer), tr(p.merkmal()), p.wert_text(),
                    _z(p.nennwert if p.art == MASS else None), _z(oben), _z(unten), p.bezug_text(),
                    ", ".join(je_pmi.get(p.nummer, [])), str(len(p.flaechen)), "", "", ""])
        w, urteil = (messung or {}).get(m.ballon, (None, ""))
        if w is not None and w.wert is not None:
            out[-1][10] = _z(w.wert)
            out[-1][11] = {"gut": tr("ja"), "schlecht": tr("nein")}.get(urteil, "")
    return out


def als_csv(merkmale: list[Merkmal], ansichten: list | None = None, messung: dict | None = None) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    for z in zeilen(merkmale, ansichten, messung):
        w.writerow([x.replace(".", ",") if i in (4, 5, 6, 10) else x for i, x in enumerate(z)])
    return puffer.getvalue()


def anker(p, grafik: dict, flaechen_mitte=None):
    """Ort des Ballons: Ecke der Beschriftung aus der Datei, sonst Mitte der zugeordneten Flaechen."""
    for g in grafik.values():
        if p.step_id and p.step_id in g.pmi_ids and not g.doppelt:
            if g.platzhalter:
                ph = g.platzhalter[0]
                return tuple(float(c) for c in ph.ursprung + ph.y * ph.hoehe)
            grenzen = g.grenzen()
            if grenzen is not None:
                return tuple(float(c) for c in grenzen[1])  # obere Ecke der Beschriftung
    if flaechen_mitte is not None and p.flaechen:
        return flaechen_mitte(p.flaechen)
    return None
