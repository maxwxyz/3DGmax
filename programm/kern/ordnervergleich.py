"""Ordnervergleich: Modelle zweier Staende paarweise zuordnen und vergleichen (Uebersicht).

Zuordnung ueber den Dateinamen ohne Endung; Revisionskennungen am Ende (z. B. _rev_b, -rc, ' rev c', _v2)
werden fuer die Zuordnung ignoriert, damit 'teil_rev_a.stp' und 'teil_rev_b.stp' ein Paar bilden.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

ENDUNGEN = (".stp", ".step", ".p21", ".igs", ".iges", ".stl", ".obj", ".gltf", ".glb", ".3mf")
_REVISION = re.compile(r"([ _\-.]?(rev|r|v|version|stand|idx|index)[ _\-.]?[a-z0-9]{1,3})$", re.I)

GLEICH, GEAENDERT, NUR_ALT, NUR_NEU, FEHLER = "gleich", "geaendert", "nur_alt", "nur_neu", "fehler"


@dataclass
class Paar:
    schluessel: str
    alt: str | None
    neu: str | None
    status: str = ""
    pmi_aenderungen: int = 0
    geo_aenderungen: int = 0
    meldung: str = ""
    vergleich: object = field(default=None, repr=False)


def schluessel(dateiname: str) -> str:
    stamm = os.path.splitext(os.path.basename(dateiname))[0].strip().lower()
    return _REVISION.sub("", stamm) or stamm


def dateien(ordner: str) -> list[str]:
    return sorted(os.path.join(ordner, f) for f in os.listdir(ordner) if f.lower().endswith(ENDUNGEN))


def paare(ordner_alt: str, ordner_neu: str) -> list[Paar]:
    alt = {schluessel(p): p for p in dateien(ordner_alt)}
    neu = {schluessel(p): p for p in dateien(ordner_neu)}
    out = []
    for k in sorted(set(alt) | set(neu)):
        p = Paar(k, alt.get(k), neu.get(k))
        if p.alt is None:
            p.status = NUR_NEU
        elif p.neu is None:
            p.status = NUR_ALT
        out.append(p)
    return out


def vergleiche_paar(p: Paar, toleranz: float = 0.01, suchweite: float = 2.0, lade=None):
    """Ein Paar vergleichen; lade(pfad) -> Ergebnis wie ui.lader.lade_alles."""
    from . import vergleich
    if p.alt is None or p.neu is None:
        return p
    try:
        v = vergleich.vergleiche(lade(p.alt), lade(p.neu), toleranz, suchweite)
    except Exception as e:  # noqa: BLE001 - eine defekte Datei darf den Ordnervergleich nicht abbrechen
        p.status, p.meldung = FEHLER, str(e)
        return p
    p.pmi_aenderungen = sum(a.kategorie == "pmi" for a in v.aenderungen)
    p.geo_aenderungen = sum(a.kategorie == "geometrie" for a in v.aenderungen)
    p.status = GLEICH if not v.aenderungen else GEAENDERT
    p.vergleich = v
    return p
