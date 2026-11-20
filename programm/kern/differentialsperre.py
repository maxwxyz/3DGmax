"""Explizite Betriebsannahmen eines symmetrischen Differentials. Drehmomente im Zugbetrieb."""

from __future__ import annotations

import math
from dataclasses import dataclass


QUELLE_TBR = "https://torsen.com/faqs/what-is-tbr/"
QUELLE_LAMELLE = "https://www.mathworks.com/help/sdl/ref/limitedslipdifferential.html"
QUELLE_SPERRE = "https://www.eaton.com/content/dam/eaton/products/differentials/eaton-ebook-5-things-differentials-epdl200-0617.pdf"


@dataclass(frozen=True)
class Sperrvorgabe:
    art: str = "offen"  # offen, gesperrt, tbr, lamelle
    steg_moment: float | None = None  # Betrag im Zugbetrieb [Nm]
    tbr: float | None = None
    kupplungsmoment_max: float | None = None  # Kapazitaet einer Kupplung von Seitenrad zu Seitenrad [Nm]

    def __post_init__(self):
        if self.art not in ("offen", "gesperrt", "tbr", "lamelle"):
            raise ValueError("Unbekanntes Sperrmodell")
        if self.steg_moment is not None and (not math.isfinite(self.steg_moment) or self.steg_moment < 0):
            raise ValueError("Ungueltiges Steg-Antriebsmoment")
        if self.art == "tbr":
            if self.tbr is None or not math.isfinite(self.tbr) or self.tbr < 1:
                raise ValueError("Drehmomentverhaeltnis TBR muss mindestens 1 sein")
        elif self.tbr is not None:
            raise ValueError("TBR nur fuer die Teilsperre")
        if self.kupplungsmoment_max is not None and (self.art != "lamelle" or
                not math.isfinite(self.kupplungsmoment_max) or self.kupplungsmoment_max < 0):
            raise ValueError("Ungueltiges maximales Seitenrad-Kupplungsmoment")


def sperrfaelle(betrieb, vorgaben):
    saetze = {s["wellen"][2]: s for s in betrieb.saetze if s["art"] in ("kegel", "schraegraddifferential")}
    if vorgaben and (set(vorgaben) - saetze.keys() or not all(isinstance(v, Sperrvorgabe) for v in vorgaben.values())):
        raise ValueError("Sperrvorgabe braucht einen aktiven Differentialsteg")
    gesperrt, faelle = [], []
    for steg, s in saetze.items():
        v = (vorgaben or {}).get(steg, Sperrvorgabe())
        a, b, _ = s["wellen"]
        if v.art == "gesperrt" and a != b:
            vorzeichen = 1 if betrieb.positive_achse(a) @ betrieb.positive_achse(b) > 0 else -1
            gesperrt.append(({a: 1, b: -vorzeichen}, 0.))
        faelle.append((s["wellen"], v))
    return gesperrt, faelle


def _ueberbrueckt(wellen, kupplungen):
    """Eine zusaetzliche Wellenverbindung kann Drehmoment am Differential vorbei uebertragen."""
    if not kupplungen:
        return False
    nachbarn = {}
    for a, b in kupplungen:
        nachbarn.setdefault(a, set()).add(b)
        nachbarn.setdefault(b, set()).add(a)
    for a in wellen[:2]:
        besucht, offen = {a}, [a]
        while offen:
            for i in nachbarn.get(offen.pop(), ()):
                if i not in besucht:
                    besucht.add(i)
                    offen.append(i)
        if any(i != a and i in besucht for i in wellen):
            return True
    return False


def _seitenbereiche(wellen, bereich, werte, betrieb):
    if bereich is None:
        return None
    a, b, steg = wellen
    na, nb, nc = (werte[i] for i in wellen)
    seiten = [bereich.copy(), bereich.copy()]
    if na is None or nb is None or nc is None or nc == 0 or bereich[0] == bereich[1]:
        return seiten
    # Moment als Zugbetrag relativ zur Stegdrehung. Passive Reibung darf keine Leistung erzeugen:
    # (MA-MB)*(nA-nB) <= 0 mit beiden Geschwindigkeiten in der positiven Antriebsrichtung.
    achse = betrieb.positive_achse(steg)
    na *= 1 if betrieb.positive_achse(a) @ achse > 0 else -1
    nb *= 1 if betrieb.positive_achse(b) @ achse > 0 else -1
    if na != nb:
        schnell = 0 if (na > nb) == (nc > 0) else 1
        halb = (bereich[0] + bereich[1]) / 2
        seiten[schnell][1] = seiten[1 - schnell][0] = halb
    return seiten


def momentdaten(faelle, kupplungen, konflikt, werte, betrieb):
    """Bereiche bei MA+MB=MC, begrenzt durch TBR oder die Kapazitaet einer direkten Seitenradkupplung."""
    ausgabe = []
    for wellen, v in faelle:
        tbr = v.tbr if v.art == "tbr" else 1. if v.art == "offen" else None
        bereich = None
        if konflikt.intersection(wellen):
            status = "drehzahlwiderspruch"
        elif v.art == "gesperrt" or len(set(wellen)) < 3 or _ueberbrueckt(wellen, kupplungen):
            status = "lastabhaengig"
        elif v.art == "lamelle" and v.kupplungsmoment_max is None:
            status = "kupplungsmoment_fehlt"
        elif v.steg_moment is None:
            status = "moment_fehlt"
        elif v.art == "lamelle":
            untergrenze = max(0., v.steg_moment / 2 - v.kupplungsmoment_max)
            bereich = [untergrenze, v.steg_moment - untergrenze]
            status = "kupplungsgrenzen"
        else:
            untergrenze = v.steg_moment / (1. + tbr)
            bereich = [untergrenze, v.steg_moment - untergrenze]
            status = "gleichverteilung" if tbr == 1 else "tbr_grenzen"
        seiten = _seitenbereiche(wellen, bereich, werte, betrieb)
        quelle = {"gesperrt": QUELLE_SPERRE, "lamelle": QUELLE_LAMELLE}.get(v.art, QUELLE_TBR)
        annahmen = ["zugbetrieb", "quasistatisch", "gleichgerichtete_abtriebsmomente",
                    "ohne_aeusseres_verlustmoment", "ma_plus_mb_gleich_mc", "passive_leistungsbilanz"]
        if v.art == "lamelle":
            annahmen += ["kupplung_zwischen_seitenraedern", "betragsdifferenz_ma_mb_max_zweimal_kupplungsmoment"]
        else:
            annahmen.append("ohne_vorspannung")
        ausgabe.append({"modell": v.art, "herkunft": "betriebsannahme", "wellen_a_b_steg": list(wellen), "tbr": tbr,
                        "steg_antriebsmoment": v.steg_moment, "seitenmomente_a_b": seiten,
                        "kupplungsmoment_max": v.kupplungsmoment_max, "einheit": "Nm", "status": status,
                        "quelle": quelle, "bedingungen": annahmen})
    return ausgabe
