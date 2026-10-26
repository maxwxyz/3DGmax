"""Stueckliste (BOM) aus dem Baugruppenbaum: gleiche Teile zusammengefasst mit Anzahl, Volumen, Masse (ohne Qt)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from ..i18n import tr
from .eigenschaften import berechne


@dataclass
class Position:
    pos: int
    name: str
    anzahl: int
    volumen: float  # mm3 je Stueck
    oberflaeche: float  # mm2 je Stueck
    baugruppen: list[str] = field(default_factory=list)  # in welchen Baugruppen es vorkommt
    nummern: list[int] = field(default_factory=list)  # Blattnummern der Exemplare (Ansicht)

    def masse(self, dichte: float) -> float:
        """Masse je Stueck in kg bei Dichte g/cm3."""
        return self.volumen * dichte * 1e-6


def _grundname(name: str) -> str:
    """'Schraube M6x25:3' -> 'Schraube M6x25' (Exemplar-Nummern der CAD-Systeme entfernen)."""
    return re.sub(r"(:\d+|\s*\(\d+\)|_\d+)$", "", name.strip())


def positionen(wurzel) -> list[Position]:
    """Blaetter nach gleicher Geometrie (gleiche TShape) und gleichem Grundnamen gruppieren."""
    gruppen: list[tuple[object, Position]] = []

    def gehe(k, pfad):
        for kind in k.kinder:
            if kind.kinder:
                gehe(kind, pfad + [kind.name])
            elif not kind.hilfsgeometrie:
                name = _grundname(kind.name)
                for form, pos in gruppen:
                    if pos.name == name and form.IsPartner(kind.form):
                        pos.anzahl += 1
                        pos.nummern.append(kind.nummer)
                        if pfad and pfad[-1] not in pos.baugruppen:
                            pos.baugruppen.append(pfad[-1])
                        break
                else:
                    w = berechne(kind.form)
                    gruppen.append((kind.form, Position(len(gruppen) + 1, name, 1, w.volumen, w.oberflaeche,
                                                        [pfad[-1]] if pfad else [], [kind.nummer])))

    if not wurzel.kinder and not wurzel.hilfsgeometrie:
        w = berechne(wurzel.form)
        return [Position(1, _grundname(wurzel.name), 1, w.volumen, w.oberflaeche, [], [wurzel.nummer])]
    gehe(wurzel, [])
    return [p for _, p in gruppen]


SPALTEN = ("Pos", "Benennung", "Anzahl", "Volumen je Stück (cm³)", "Masse je Stück (kg)", "Masse gesamt (kg)",
           "Baugruppe")


def zeilen(liste: list[Position], dichte: float) -> list[list[str]]:
    return [[str(p.pos), p.name, str(p.anzahl), f"{p.volumen / 1000:.3f}", f"{p.masse(dichte):.4f}",
             f"{p.masse(dichte) * p.anzahl:.4f}", ", ".join(p.baugruppen)] for p in liste]


def als_csv(liste: list[Position], dichte: float) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    for z in zeilen(liste, dichte):
        w.writerow([x.replace(".", ",") if i in (3, 4, 5) else x for i, x in enumerate(z)])
    return puffer.getvalue()
