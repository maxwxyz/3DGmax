"""Auslegungsbefunde fuer Verzahnungen (PLAN §8.27a, ohne Qt): aus der erkannten Geometrie die Auslegungsentscheidungen
und die Philosophie dahinter ablesen - Reverse Engineering. Nur Analyse.

Je Befund: Bereich (Rad, Stufe, Satz), Thema, gemessener Wert, Einordnung (die erkennbare Entscheidung) und die
Regel bzw. der uebliche Bereich mit Quelle. Die Regeln sind die verbreiteten Faustwerte der Lehrbuecher und Normen
(Bezugsprofil ISO 53, Begriffe ISO 21771, Profilverschiebung DIN 3992, Niemann/Winter "Maschinenelemente" Bd. II,
Linke "Stirnradverzahnung"); sie ordnen ein, sie bewerten nicht. Was die Geometrie nicht zeigt, bleibt offen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..i18n import tr
from . import verzahnung_daten as vd
from .verzahnung import Paar, Verzahnung

Q_ISO53 = "ISO 53 (Bezugsprofil)"
Q_DIN3992 = "DIN 3992 (Profilverschiebung)"
Q_NIEMANN = "Niemann/Winter, Maschinenelemente Bd. II"
Q_LINKE = "Linke, Stirnradverzahnung"
Q_ISO21771 = "ISO 21771"


@dataclass
class Befund:
    bereich: str  # Rad, Stufe oder Satz (Name)
    thema: str
    wert: str
    einordnung: str
    quelle: str

    def zeile(self) -> tuple[str, str, str, str, str]:
        return (self.bereich, tr(self.thema), self.wert, self.einordnung, self.quelle)


def _g(w: float, n: int = 3) -> str:
    return f"{w:.{n}f}".rstrip("0").rstrip(".")


def rad_befunde(v: Verzahnung) -> list[Befund]:
    """Bezugsprofil (Kopf-/Fusshoehe), Schraegung, Korrekturen eines Rads."""
    out = []
    w = vd.stirnwerte(v)
    if not w:
        return out
    ha, hf = w["ha_stern"] - (v.x if not v.innen else -v.x), w["hf_stern"] + (v.x if not v.innen else -v.x)
    if 0.95 <= ha <= 1.05 and 1.15 <= hf <= 1.4:
        profil = tr("Normprofil (ha* ≈ 1, hf* ≈ 1,25)")
    elif ha > 1.1:
        profil = tr("Hochverzahnung (verlängerter Kopf) – meist für hohe Profilüberdeckung und leiseren Lauf")
    elif ha < 0.9:
        profil = tr("Kurz- bzw. Stumpfverzahnung – tragfähiger Zahnfuß, kleinere Überdeckung")
    else:
        profil = tr("vom Normprofil abweichend")
    out.append(Befund(v.teil, "Bezugsprofil", f"ha* {_g(ha)}, hf* {_g(hf)}", profil, Q_ISO53))
    if not v.beta:
        art = tr("Geradverzahnung – keine Axialkraft, einfach zu fertigen")
    elif v.beta <= 15.5:
        art = tr("Schrägverzahnung im üblichen Bereich 8–15° – leiser Lauf bei mäßiger Axialkraft")
    elif v.beta <= 30:
        art = tr("starke Schrägung (über 15°) – hohe Sprungüberdeckung, große Axialkraft (oft Doppelschrägung)")
    else:
        art = tr("sehr große Schrägung – ungewöhnlich für Leistungsgetriebe")
    hand = {"rechts": tr("rechtssteigend"), "links": tr("linkssteigend")}.get(v.hand, "")
    out.append(Befund(v.teil, "Schrägungswinkel", f"{_g(v.beta, 2)}° {hand}".strip(), art, Q_NIEMANN))
    if not v.innen and v.z < 17:
        grenze = (14 - v.z) / 17  # praktische Grenze bei alpha_n = 20 Grad (Unterschnitt erlaubt bis z' = 14)
        ok = v.x >= grenze - 0.02
        out.append(Befund(v.teil, "Unterschnitt", f"z = {v.z}, x = {_g(v.x)} (min ≈ {_g(grenze)})",
                          tr("Profilverschiebung gegen Unterschnitt gewählt") if ok else
                          tr("Unterschnitt zu erwarten – Fußform prüfen"), Q_DIN3992))
    p = vd.profil(v)
    if p is not None:
        if p.ca:
            out.append(Befund(v.teil, "Kopfrücknahme", f"Cα = {_g(p.ca, 4)} mm = {_g(p.ca / v.mn, 4)} mn",
                              tr("Kopfrücknahme vorgesehen – mildert den Eingriffsstoß unter Last (Geräusch, "
                                 "Fressen); Betrag passt zu einer Auslegung für eine bestimmte Last"), Q_NIEMANN))
        else:
            out.append(Befund(v.teil, "Kopfrücknahme", tr("keine"),
                              tr("keine Profilkorrektur modelliert (Nennzahnrad oder Korrektur nur in der "
                                 "Zeichnung)"), Q_NIEMANN))
    cb = vd.breitenballigkeit(v)
    if cb is not None and p is not None and abs(cb) > p.toleranz:
        out.append(Befund(v.teil, "Breitenballigkeit", f"Cβ = {_g(cb, 4)} mm",
                          tr("Breitenballigkeit vorgesehen – gleicht Fluchtungsfehler und Verformung aus"), Q_NIEMANN))
    return out


def stufen_befunde(p: Paar) -> list[Befund]:
    """Profilverschiebung, Gleiten, Ueberdeckungen, Breiten, Zaehnezahlen, Spiele eines Radpaars."""
    w = vd.paar_werte(p)
    name = f"{p.a.teil} – {p.b.teil}"
    out = []
    sx = w["summe_x"]
    if abs(sx) <= 0.05:
        art = tr("V-Null-Getriebe: Achsabstand = Null-Achsabstand, Profilverschiebungen gleichen sich aus")
    elif sx > 0:
        art = tr("V-Plus-Getriebe: Achsabstand vergrößert – höhere Fuß- und Flankentragfähigkeit oder "
                 "vorgegebener Achsabstand")
    else:
        art = tr("V-Minus-Getriebe: Achsabstand verkleinert – höhere Profilüberdeckung, geringere Tragfähigkeit")
    out.append(Befund(name, "Summe der Profilverschiebungen", f"Σx = {_g(sx)}", art, Q_DIN3992))
    if w["gleiten"]:
        g1, g2 = abs(w["gleiten"][0]), abs(w["gleiten"][1])
        verh = max(g1, g2) / max(min(g1, g2), 1e-9)
        if verh <= 1.25:
            art = tr("ausgeglichenes spezifisches Gleiten an beiden Füßen – Verteilung auf Verschleiß/Fressen "
                     "ausgelegt")
        elif g1 > g2:
            art = tr("Gleiten am Fuß des kleinen Rads deutlich größer – Verteilung eher auf Festigkeit oder "
                     "ohne Gleitausgleich")
        else:
            art = tr("Gleiten am Fuß des großen Rads größer – kleines Rad stark positiv verschoben")
        out.append(Befund(name, "Aufteilung der Profilverschiebung",
                          f"ζ {w['klein']} {_g(w['gleiten'][0], 2)}, ζ {w['gross']} {_g(w['gleiten'][1], 2)}",
                          art, Q_DIN3992))
    ea, eb = p.eps_alpha, p.eps_beta
    if ea >= 2.0:
        art = tr("Hochüberdeckung (εα ≥ 2): stets zwei Zahnpaare im Eingriff – geräuscharm ausgelegt")
    elif ea >= 1.2:
        art = tr("übliche Profilüberdeckung 1,2–2")
    else:
        art = tr("kleine Profilüberdeckung unter 1,2 – Eingriffsstoß, eher laut")
    out.append(Befund(name, "Profilüberdeckung", f"εα = {_g(ea)}", art, Q_NIEMANN))
    if eb > 0:
        nah = abs(eb - round(eb)) <= 0.1 and round(eb) >= 1
        out.append(Befund(name, "Sprungüberdeckung", f"εβ = {_g(eb)}",
                          tr("ganzzahlige Sprungüberdeckung – konstante Kontaktlinienlänge, geringe "
                             "Steifigkeitsschwankung (Geräusch)") if nah else
                          tr("Sprungüberdeckung nicht ganzzahlig") if eb >= 1 else
                          tr("Sprungüberdeckung unter 1"), Q_LINKE))
    klein = p.b if (p.a.innen or abs(p.a.z) > abs(p.b.z)) else p.a
    bd = min(p.a.b, p.b.b) / klein.d if klein.d else float("nan")
    bm = min(p.a.b, p.b.b) / klein.mn if klein.mn else float("nan")
    out.append(Befund(name, "Breitenverhältnis", f"b/d1 = {_g(bd)}, b/mn = {_g(bm, 1)}",
                      tr("übliche Breite") if 0.3 <= bd <= 1.2 and 8 <= bm <= 45 else
                      tr("schmal – eher Bauraum oder leichte Last") if bd < 0.3 or bm < 8 else
                      tr("breit – hohe Last, empfindlich für Fluchtungsfehler (Breitenballigkeit üblich)"), Q_NIEMANN))
    z1, z2 = abs(p.a.z), abs(p.b.z)
    ggt = math.gcd(z1, z2)
    if ggt == 1:
        art = tr("teilerfremde Zähnezahlen (\"hunting tooth\") – jeder Zahn trifft jeden Gegenzahn, gleichmäßiger "
                 "Verschleiß und Einlauf")
    elif min(z1, z2) and max(z1, z2) % min(z1, z2) == 0:
        art = tr("ganzzahlige Übersetzung – dieselben Zähne kämmen immer miteinander (Fehler wiederholen sich)")
    else:
        art = tr("gemeinsamer Teiler {} – Zahnpaarungen wiederholen sich nach {} Umdrehungen").format(
            ggt, max(z1, z2) // ggt)
    out.append(Befund(name, "Zähnezahlen", f"{min(z1, z2)} : {max(z1, z2)} (ggT {ggt})", art, Q_NIEMANN))
    c = min(w["c_klein"], w["c_gross"]) / p.a.mn if p.a.mn else float("nan")
    out.append(Befund(name, "Kopfspiel", f"c = {_g(c, 3)} mn",
                      tr("Kopfspiel des Bezugsprofils (0,25 mn)") if 0.2 <= c <= 0.3 else
                      tr("Kopfspiel kleiner als im Bezugsprofil – z. B. Hochverzahnung") if c < 0.2 else
                      tr("großes Kopfspiel – Kopfkreise gekürzt"), Q_ISO53))
    a = p.abstand
    glatt = abs(a - round(a)) < 0.005 or abs(a * 2 - round(a * 2)) < 0.005
    out.append(Befund(name, "Achsabstand", f"a = {_g(a, 3)} mm",
                      tr("glatter Achsabstand – Profilverschiebung passt die Verzahnung an einen vorgegebenen "
                         "Achsabstand an") if glatt and abs(sx) > 0.05 else
                      tr("glatter Achsabstand") if glatt else tr("Achsabstand folgt aus der Verzahnung"), Q_DIN3992))
    return out


def getriebe_befunde(liste: list[Verzahnung], paare: list[Paar]) -> list[Befund]:
    """Stufenaufteilung mehrstufiger Getriebe und Befunde der Planetensaetze."""
    out = []
    saetze = vd.planetensaetze(liste, paare)
    stufen, _ziel = vd.stufen(liste, paare, saetze)
    if len(stufen) >= 2:
        us = [s.u for s in stufen]
        gesamt = math.prod(us)
        out.append(Befund(tr("Getriebe"), "Stufenaufteilung", " · ".join(_g(u, 2) for u in us) + f" = {_g(gesamt, 2)}",
                          tr("erste Stufe mit der größten Übersetzung – übliche Aufteilung für gleich große Räder "
                             "auf den Zwischenwellen bzw. kleinen Bauraum") if us[0] >= max(us[1:]) else
                          tr("spätere Stufe mit größerer Übersetzung – eher auf Tauchschmierung bzw. "
                             "Drehmomentverlauf ausgelegt"), Q_NIEMANN))
    for n, s in enumerate(saetze, 1):
        name = tr("Planetensatz {}").format(n)
        anz = len(s.planeten)
        zs, zr = s.z_sonne, s.z_hohlrad
        out.append(Befund(name, "Planetenzahl", str(anz),
                          tr("Montagebedingung erfüllt: gleich verteilte Planeten") if (zs + zr) % anz == 0 else
                          tr("Montagebedingung nicht erfüllt – ungleiche Teilung nötig"), Q_NIEMANN))
        gleich = zs % anz == 0 and zr % anz == 0
        out.append(Befund(name, "Phasenlage der Planeten", f"zs/n = {_g(zs / anz, 3)}, zr/n = {_g(zr / anz, 3)}",
                          tr("gleichphasiger Eingriff: alle Planeten greifen gleichzeitig – einfache Montage, "
                             "Anregung addiert sich") if gleich else
                          tr("sequenzieller Eingriff (Phasenversatz) – Anregungen der Planeten heben sich teilweise "
                             "auf, geräuschärmer"), tr("Literatur zur Planetenphasenlage (z. B. Parker, Kahraman)")))
        i = 1 + zr / zs
        out.append(Befund(name, "Übersetzung", f"i = {_g(i, 3)}",
                          tr("üblicher Bereich 3–10") if 3 <= i <= 10 else tr("außerhalb des üblichen Bereichs 3–10"),
                          Q_NIEMANN))
        out.append(Befund(name, "Zähnezahlen", f"{zs} / {s.z_planet} / {zr}",
                          tr("zr = zs + 2 zp: ohne Profilverschiebungsausgleich") if zr == zs + 2 * s.z_planet else
                          tr("zr ≠ zs + 2 zp: Profilverschiebung zum Ausgleich des Achsabstands"), Q_DIN3992))
    return out


def alle(liste: list[Verzahnung], paare: list[Paar]) -> list[Befund]:
    out = [b for v in liste for b in rad_befunde(v)]
    out += [b for p in paare for b in stufen_befunde(p)]
    return out + getriebe_befunde(liste, paare)


SPALTEN = ("Bereich", "Thema", "Wert", "Einordnung", "Quelle")
THEMEN = (  # fuer die Uebersetzung (werkzeuge/tr_texte.py)
          "Achsabstand", "Aufteilung der Profilverschiebung", "Bezugsprofil", "Breitenballigkeit",
          "Breitenverhältnis", "Kopfrücknahme", "Kopfspiel", "Phasenlage der Planeten", "Planetenzahl",
          "Profilüberdeckung", "Schrägungswinkel", "Sprungüberdeckung", "Stufenaufteilung",
          "Summe der Profilverschiebungen", "Unterschnitt", "Zähnezahlen", "Übersetzung")


def als_dicts(befunde: list[Befund]) -> list[dict]:
    return [{"bereich": b.bereich, "thema": b.thema, "wert": b.wert, "einordnung": b.einordnung, "quelle": b.quelle}
            for b in befunde]
