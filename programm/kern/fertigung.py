"""Fertigungsverfahren mit erreichbaren ISO-Toleranzgraden und relativen Kosten (ohne Qt).

Richtwerte fuer die kostenoptimale Toleranzverteilung (PLAN §8.33): je Verfahren der feinste wirtschaftlich
erreichbare IT-Grad (darunter nur mit Nacharbeit) und der grobe Grad, ab dem eine weitere Toleranz keine Kosten mehr
spart, dazu ein relativer Kostenfaktor des Verfahrens. Die Grade folgen der verbreiteten Zuordnung "Verfahren ->
ISO-Toleranzgrad" der Fertigungstechnik-Literatur; sie sind Anhaltswerte und haengen von Maschine, Werkstoff und
Groesse ab - deshalb im Programm je Glied anpassbar.

Kostenmodell (Kehrwert, Chase/Greenwood): Kosten(T) = Faktor * T_grob / T fuer T_fein <= T <= T_grob; engere
Toleranzen als T_fein sind mit dem Verfahren nicht erreichbar, weitere als T_grob kosten nicht weniger.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import iso286


@dataclass(frozen=True)
class Verfahren:
    name: str
    it_fein: int  # feinster wirtschaftlich erreichbarer IT-Grad
    it_grob: int  # ab hier spart eine groessere Toleranz nichts mehr
    kosten: float  # relativer Kostenfaktor des Verfahrens (Drehen = 1)


VERFAHREN = {
    "drehen": Verfahren("Drehen", 7, 11, 1.0),
    "fraesen": Verfahren("Fräsen", 8, 11, 1.2),
    "bohren": Verfahren("Bohren", 10, 13, 0.6),
    "reiben": Verfahren("Reiben", 6, 9, 1.5),
    "schleifen": Verfahren("Schleifen", 5, 7, 2.5),
    "honen": Verfahren("Honen / Läppen", 4, 6, 4.0),
    "raeumen": Verfahren("Räumen", 6, 8, 1.8),
    "druckguss": Verfahren("Druckguss", 11, 14, 0.5),
    "sandguss": Verfahren("Sandguss", 14, 16, 0.3),
    "schmieden": Verfahren("Schmieden", 14, 16, 0.4),
    "stanzen": Verfahren("Stanzen / Biegen (Blech)", 10, 13, 0.4),
    "laser": Verfahren("Laserschneiden", 12, 14, 0.5),
    "spritzguss": Verfahren("Spritzguss", 9, 13, 0.4),
    "additiv": Verfahren("Additiv (Metall)", 11, 14, 3.0),
    "zukauf": Verfahren("Zukaufteil / Norm (fest)", 0, 0, 0.0),
}
STANDARD = "drehen"


def _it_mm(grad: int, nennmass: float) -> float:
    """Grundtoleranz in mm; Nennmasse ausserhalb von ISO 286 (0 oder > 500 mm) an die Bereichsgrenze gesetzt."""
    d = min(max(abs(nennmass), 1.0), 500.0)
    wert = iso286.it(grad, d)
    return (wert or 0.0) / 1000.0


def grenzen(verfahren: str, nennmass: float) -> tuple[float, float]:
    """(T_fein, T_grob) in mm fuer das Verfahren beim Nennmass."""
    v = VERFAHREN.get(verfahren, VERFAHREN[STANDARD])
    return _it_mm(v.it_fein, nennmass), _it_mm(v.it_grob, nennmass)


def kosten(verfahren: str, nennmass: float, toleranz: float) -> float:
    """Relative Kosten einer Toleranz (Kehrwertmodell, zwischen T_fein und T_grob begrenzt)."""
    v = VERFAHREN.get(verfahren, VERFAHREN[STANDARD])
    if v.kosten <= 0:
        return 0.0
    fein, grob = grenzen(verfahren, nennmass)
    t = min(max(toleranz, fein), grob) if grob > 0 else toleranz
    return v.kosten * grob / t if t > 0 else float("inf")


def it_grad(toleranz: float, nennmass: float) -> int | None:
    """Groebster IT-Grad, dessen Grundtoleranz in die Toleranz passt (z. B. 0,025 mm bei 40 mm -> IT7); None, wenn
    die Toleranz enger als IT1 ist."""
    passend = [g for g in sorted(iso286.IT) if _it_mm(g, nennmass) <= toleranz + 1e-12]
    return passend[-1] if passend else None
