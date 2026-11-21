"""Fertigungsgrenzen auf den Zylinderflaechen eines ausgewaehlten Sitzpaars."""

from collections import defaultdict
from dataclasses import dataclass
from math import dist, isclose, isfinite

from ..i18n import tr
from .merkmale import AUSGENOMMEN
from .pmi import MASS


@dataclass(frozen=True)
class Sitzmass:
    nennwert: float
    unten: float
    oben: float
    beleg: str


def _sitzmass(sitz, p):
    if p.nennwert is None or not isfinite(p.nennwert) or p.nennwert <= 0:
        return None
    if not p.flaechen.issubset(sitz.flaechen) or p.kanten:
        return None
    if p.passung:
        klasse = p.klassen_abmasse()
        if not klasse or p.passung[0].isupper() != sitz.innen:
            return None
        # Bei doppelter Angabe muessen Zahlenwerte und Toleranzklasse uebereinstimmen.
        if p.oben is not None or p.unten is not None:
            if p.oben is None or p.unten is None or any(abs(a-b) > 1e-8 for a, b in zip(p.abmasse(), klasse)):
                return None
    elif p.oben is None or p.unten is None:
        return None
    oben, unten = p.grenzen()
    if not all(v is not None and isfinite(v) and v > 0 for v in (p.nennwert, unten, oben)) or unten > oben:
        return None
    # Modelle koennen am Nennmass oder innerhalb des Fertigungsintervalls liegen.
    if abs(sitz.d_mm-p.nennwert) > 1e-6 and not unten-1e-6 <= sitz.d_mm <= oben+1e-6:
        return None
    kennung = f"PMI {p.nummer}"
    if p.step_id > 0 and p.quelle in ("step", "qif"):
        kennung = f"{p.quelle.upper()} #{p.step_id}"
    return Sitzmass(p.nennwert, unten, oben, f"{kennung} · {p.wert_text()}")


def sitzmasse(sitze, pmi):
    """Je Sitz hoechstens eine eindeutige Durchmessertoleranz ueber die Flaechen belegen."""
    je_flaeche = defaultdict(list)
    for p in pmi:
        if (p.art == MASS and p.typ == "Size_Diameter" and p.semantisch and not AUSGENOMMEN.intersection(p.modifikatoren)
                and (p.passung or p.oben is not None or p.unten is not None)):
            for nr in p.flaechen:
                je_flaeche[nr].append(p)
    ergebnis = {}
    for sitz in sitze:
        treffer = {id(p): p for nr in sitz.flaechen for p in je_flaeche.get(nr, ())}
        if len(treffer) == 1:
            mass = _sitzmass(sitz, next(iter(treffer.values())))
            if mass:
                ergebnis[sitz] = mass
    return ergebnis


def passungsvorgaben(welle, bohrung, laenge, sitze, masse):
    """Quellwerte am gemeinsamen Nennmass mit den Belegen beider Vorkommen liefern."""
    werte = {"d": welle.d_mm, "l": laenge}
    quellen = {}

    def quelle(s):
        return f"{s.teil} (#{s.nummer})"

    w, b = masse.get(welle), masse.get(bohrung)
    if w and b and not isclose(w.nennwert, b.nennwert, abs_tol=1e-6, rel_tol=0):
        hinweis = tr("Die Sitz-PMI nennen unterschiedliche Nenndurchmesser. Gemeinsames Nennmaß und Abmaße prüfen.")
    else:
        if w or b:
            werte["d"] = (w or b).nennwert
        belege = []
        for s, mass, suffix in ((welle, w, "w"), (bohrung, b, "n")):
            if mass is None:
                continue
            beleg = f"{quelle(s)} · {mass.beleg}"
            belege.append(beleg)
            for k, grenze in (("ei_", mass.unten), ("es_", mass.oben)):
                feld = k+suffix
                werte[feld] = round(1000*(grenze-werte["d"]), 9)
                quellen[feld] = beleg
        if belege:
            quellen["d"] = " / ".join(belege)
        hinweis = "" if w and b else tr("Fehlende oder mehrdeutige Sitz-PMI: offene Fertigungsabmaße ergänzen.")
    # Durchgehender koaxialer Aussenmantel auf genau der Laenge der Nabenbohrung.
    mantel = [s for s in sitze if s.nummer == bohrung.nummer and not s.innen and s.d_mm > bohrung.d_mm
              and abs(s.laenge_mm-bohrung.laenge_mm) <= 1e-6 and dist(s.mitte_mm, bohrung.mitte_mm) <= 1e-6
              and abs(abs(sum(a*b for a, b in zip(s.richtung, bohrung.richtung)))-1) < 1e-9]
    if len(mantel) == 1:
        werte["da"] = mantel[0].d_mm
        quellen["da"] = quelle(mantel[0]) + " · " + tr("Außenzylinder")
    return werte, quellen, hinweis
