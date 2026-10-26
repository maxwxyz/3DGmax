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
    sachnummer: str = ""  # Produktkennung laut Datei (STEP PRODUCT.id)

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


def sachnummern(datei) -> dict[str, str]:
    """Produktname -> Produktkennung aus einer STEP-Datei (PRODUCT(id, name, ...)); leer ohne Datei."""
    out = {}
    if datei is None:
        return out
    for e in datei.of_type("PRODUCT"):
        a = e.args("PRODUCT")
        if len(a) >= 2 and isinstance(a[0], str) and isinstance(a[1], str) and a[0] and a[0] != a[1]:
            out.setdefault(a[1], a[0])
    return out


def ergaenze_sachnummern(liste: list[Position], datei) -> list[Position]:
    nummern = sachnummern(datei)
    for p in liste:
        p.sachnummer = nummern.get(p.name, "")
    return liste


SPALTEN = ("Pos", "Sachnummer", "Benennung", "Anzahl", "Volumen je Stück (cm³)", "Masse je Stück (kg)", "Masse gesamt (kg)",
           "Baugruppe")


def zeilen(liste: list[Position], dichte: float) -> list[list[str]]:
    return [[str(p.pos), p.sachnummer, p.name, str(p.anzahl), f"{p.volumen / 1000:.3f}", f"{p.masse(dichte):.4f}",
             f"{p.masse(dichte) * p.anzahl:.4f}", ", ".join(p.baugruppen)] for p in liste]


def als_csv(liste: list[Position], dichte: float) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    for z in zeilen(liste, dichte):
        w.writerow([x.replace(".", ",") if i in (4, 5, 6) else x for i, x in enumerate(z)])
    return puffer.getvalue()
