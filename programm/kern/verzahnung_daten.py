"""Datenblatt der Verzahnungen (PLAN §8.27, naechste Stufe; ohne Qt): alles, was Auslegungs- und Nachrechenprogramme
als Eingabe erwarten und sich aus der erkannten Geometrie (kern.verzahnung) bestimmen laesst - je Rad, je Paar, je
Getriebestufe und Planetensatz. Jeder Wert mit Herkunft; was sich nicht bestimmen laesst, steht als "nicht
bestimmbar" statt einer Schaetzung. Nur Analyse vorhandener Geometrie.

Formeln nach ISO 21771 (Begriffe und Bestimmungsgroessen fuer Stirnraeder):
- Stirnmodul mt = mn / cos beta, Stirneingriffswinkel tan alpha_t = tan alpha_n / cos beta,
  Grundschraegungswinkel sin beta_b = sin beta * cos alpha_n, Steigungshoehe pz = pi * d / tan beta.
- Zahndicke im Normalschnitt sn = mn * (pi/2 + 2 x tan alpha_n) (Aussenrad), Lueckenweite en = pi mn - sn;
  Hohlrad: en = mn * (pi/2 - 2 x tan alpha_n).
- Mass ueber Kugeln/Rollen: inv alpha_Mt = inv alpha_t + DM / (mn z cos alpha_n) - pi / (2 z) + 2 x tan alpha_n / z
  (Aussenrad; Hohlrad mit umgekehrten Vorzeichen), dM = d cos alpha_t / cos alpha_Mt, Md = dM + DM bei gerader,
  dM cos(90 Grad / z) + DM bei ungerader Zaehnezahl (Hohlrad: Mass zwischen den Kugeln, - DM).
- Paar: Uebersetzung u = |z2 / z1|, Gesamtueberdeckung eps_gamma = eps_alpha + eps_beta, Kopfspiel aus Achsabstand
  und Kopf-/Fusskreisen, Flankenspiel normal jn, im Stirnschnitt jt = jn / (cos alpha_n cos beta), radial
  jr = jt / (2 tan alpha_wt), spezifisches Gleiten am Fuss zeta = 1 - rho_gegen / (u rho) (Aussenradpaar).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr
from .verzahnung import Paar, Verzahnung

NICHT = "nicht bestimmbar"
KUGELN = (0.5, 0.6, 0.7, 0.8, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 9.0,
          10.0, 12.0, 14.0, 16.0, 18.0, 20.0)  # uebliche Messkugeldurchmesser (mm)


def _g(w: float, n: int = 4) -> str:
    return f"{w:.{n}f}".rstrip("0").rstrip(".") if w == w else tr(NICHT)


def _inv(a: float) -> float:
    return math.tan(a) - a


def _ainv(wert: float) -> float:
    """Umkehrung der Evolventenfunktion (Halbieren, inv ist monoton auf [0, 1,5])."""
    lo, hi = 1e-9, 1.5
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _inv(m) < wert else (lo, m)
    return (lo + hi) / 2


def stirnwerte(v: Verzahnung) -> dict:
    """Abgeleitete Groessen eines Rads (ISO 21771); leer ohne Modul."""
    if not v.mn:
        return {}
    b = math.radians(v.beta)
    an = math.radians(v.alpha_n)
    at = math.atan(math.tan(an) / math.cos(b))
    mt = v.mn / math.cos(b)
    bb = math.asin(math.sin(b) * math.cos(an))
    if v.innen:
        ha, hf = (v.d - v.da) / 2, (v.df - v.d) / 2
        en = v.mn * (math.pi / 2 - 2 * v.x * math.tan(an))
        sn = math.pi * v.mn - en
    else:
        ha, hf = (v.da - v.d) / 2, (v.d - v.df) / 2
        sn = v.mn * (math.pi / 2 + 2 * v.x * math.tan(an))
        en = math.pi * v.mn - sn
    return {"mt": mt, "alpha_t": math.degrees(at), "beta_b": math.degrees(bb),
            "pz": math.pi * v.d / math.tan(b) if v.beta else float("inf"),
            "ha": ha, "hf": hf, "h": ha + hf, "ha_stern": ha / v.mn, "hf_stern": hf / v.mn, "sn": sn, "en": en}


def kugelmass(v: Verzahnung, dm: float | None = None) -> tuple[float, float] | None:
    """(Kugeldurchmesser DM, Mass ueber bzw. zwischen den Kugeln Md); DM als ueblicher Durchmesser nahe 1,68 mn,
    der im Zahnluecke am Teilkreis anliegt. None ohne Modul."""
    if not v.mn:
        return None
    dm = dm or min(KUGELN, key=lambda k: abs(k - 1.68 * v.mn))
    an = math.radians(v.alpha_n)
    at = math.atan(math.tan(an) / math.cos(math.radians(v.beta)))
    s = 1 if not v.innen else -1
    wert = _inv(at) + s * (dm / (v.mn * v.z * math.cos(an)) - math.pi / (2 * v.z)) + 2 * v.x * math.tan(an) / v.z
    amt = _ainv(wert)
    dmk = v.d * math.cos(at) / math.cos(amt)
    mitte = dmk if v.z % 2 == 0 else dmk * math.cos(math.pi / (2 * v.z))
    return dm, mitte + s * dm


def rad_zeilen(v: Verzahnung) -> list[tuple[str, str, str]]:
    """Weitere Zeilen des Datenblatts eines Rads (Groesse, Wert, Herkunft) nach den gemessenen."""
    w = stirnwerte(v)
    if not w:
        return []
    iso = "ISO 21771"
    zeilen = [(tr("Stirnmodul mt"), _g(w["mt"]), iso),
              (tr("Stirneingriffswinkel αt"), f"{_g(w['alpha_t'], 3)}°", iso),
              (tr("Grundschrägungswinkel βb"), f"{_g(w['beta_b'], 3)}°", iso),
              (tr("Steigungshöhe pz"), _g(w["pz"], 2) if v.beta else "–", iso),
              (tr("Kopfhöhe ha / ha*"), f"{_g(w['ha'], 3)} / {_g(w['ha_stern'], 3)}", tr("aus da und d")),
              (tr("Fußhöhe hf / hf*"), f"{_g(w['hf'], 3)} / {_g(w['hf_stern'], 3)}", tr("aus df und d")),
              (tr("Zahnhöhe h"), _g(w["h"], 3), tr("aus da und df")),
              (tr("Zahndicke sn (Normalschnitt)"), _g(w["sn"], 4), iso),
              (tr("Lückenweite en (Normalschnitt)"), _g(w["en"], 4), iso)]
    k = kugelmass(v)
    if k:
        zeilen.append((tr("Maß zwischen Kugeln Md") if v.innen else tr("Maß über Kugeln Md"),
                       f"{_g(k[1], 4)} (DM {_g(k[0], 3)})", iso))
    return zeilen


def ritzel_und_rad(p: Paar):
    """Ritzel und Gegenrad als Objekte, auch bei gleichen Anzeigenamen."""
    a, b = p.a, p.b
    return (b, a) if a.innen or abs(a.z) > abs(b.z) else (a, b)


def paar_werte(p: Paar) -> dict:
    """Weitere Groessen eines Radpaars: Uebersetzung, Gesamtueberdeckung, Kopfspiele, Flankenspiele, spezifisches
    Gleiten (nur Aussenradpaar), Summe der Profilverschiebungen, Drehrichtung."""
    a, b = p.a, p.b
    innen = a.innen  # a ist beim Hohlradpaar das Hohlrad
    klein, gross = ritzel_und_rad(p)
    u = abs(gross.z) / abs(klein.z)
    cb = math.cos(math.radians(a.beta))
    awt = math.radians(p.alpha_wt)
    jt = p.spiel / (math.cos(math.radians(a.alpha_n)) * cb)
    jr = jt / (2 * math.tan(awt)) if awt > 1e-9 else float("nan")
    if innen:  # Ritzel b im Hohlrad a: Kopfkreis innen
        c_ritzel = a.df / 2 - p.abstand - b.da / 2  # Kopf des Ritzels zum Fuss des Hohlrads
        c_gegen = a.da / 2 - p.abstand - b.df / 2  # Kopf des Hohlrads zum Fuss des Ritzels
        gleiten = None
    else:
        c_ritzel = p.abstand - klein.da / 2 - gross.df / 2
        c_gegen = p.abstand - gross.da / 2 - klein.df / 2
        rho = lambda v: math.sqrt(max((v.da / 2) ** 2 - (v.db / 2) ** 2, 0.0))  # noqa: E731
        strecke = p.abstand * math.sin(awt)
        # Fuss des kleinen Rads: Eingriffsbeginn am Kopf des grossen Rads (und umgekehrt)
        r_gross_kopf = rho(gross)
        r_klein_fuss = strecke - r_gross_kopf
        r_klein_kopf = rho(klein)
        r_gross_fuss = strecke - r_klein_kopf
        gleiten = (1 - r_gross_kopf / (u * r_klein_fuss) if r_klein_fuss > 0 else float("nan"),
                   1 - u * r_klein_kopf / r_gross_fuss if r_gross_fuss > 0 else float("nan"))
    return {"u": u, "eps_gamma": p.eps_alpha + p.eps_beta, "c_klein": c_ritzel, "c_gross": c_gegen,
            "jn": p.spiel, "jt": jt, "jr": jr, "gleiten": gleiten, "summe_x": (b.x - a.x) if innen else a.x + b.x,
            "gegenlaeufig": not innen, "klein": klein.teil, "gross": gross.teil}


def paar_zeilen(p: Paar) -> list[tuple[str, str]]:
    w = paar_werte(p)
    gleiten = w["gleiten"] or (float("nan"), float("nan"))  # Hohlradpaar: nicht berechnet
    return [(tr("Übersetzung u"), f"{_g(w['u'], 4)} ({w['gross']} : {w['klein']})"),
            (tr("Gesamtüberdeckung εγ"), _g(w["eps_gamma"], 3)),
            (tr("Summe der Profilverschiebungen"), _g(w["summe_x"], 3)),
            (tr("Kopfspiel am Fuß des größeren Rads"), _g(w["c_klein"], 3)),
            (tr("Kopfspiel am Fuß des kleineren Rads"), _g(w["c_gross"], 3)),
            (tr("Drehflankenspiel jt (Stirnschnitt)"), _g(w["jt"], 4)),
            (tr("Radialspiel jr"), _g(w["jr"], 4)),
            (tr("Drehrichtung"), tr("gegenläufig") if w["gegenlaeufig"] else tr("gleichläufig (Hohlrad)")),
            (tr("Spezifisches Gleiten am Fuß des kleineren Rads"), _g(gleiten[0], 3)),
            (tr("Spezifisches Gleiten am Fuß des größeren Rads"), _g(gleiten[1], 3))]


# --- Wellen, Stufen, Planetensaetze ---

def _achsmass(rad):
    if hasattr(rad, "d"):
        return rad.d
    kopf = getattr(rad, "kopf", 0.)
    return 2 * float(np.max(kopf))


def _gleiche_achse(a: Verzahnung, b: Verzahnung, toleranz: float = 1e-3) -> bool:
    if abs(abs(float(a.richtung @ b.richtung)) - 1) > 1e-6:
        return False
    q = b.punkt - a.punkt
    return float(np.linalg.norm(q - a.richtung * float(q @ a.richtung))) < toleranz * max(_achsmass(a), _achsmass(b), 1.0)


def _koerperkennung(rad, i):
    kennung = getattr(rad, "koerper_id", None)
    return ("band", i) if kennung is None else ("koerper", kennung)


def wellen(liste, planeten=(), *, getrennte_wellen=False) -> list[list[int]]:
    """Bestaetigte Koerper bleiben drehfest. Sonstige gleichachsige Raeder optional zusammenfassen."""
    koerper = {}
    for i, rad in enumerate(liste):
        if hasattr(rad, "richtung"):
            koerper.setdefault(_koerperkennung(rad, i), []).append(i)
    if getrennte_wellen:
        return list(koerper.values())
    unabhaengig = {i for s in planeten for i in s}
    gruppen = []
    for teile in koerper.values():
        gruppe = None
        if unabhaengig.isdisjoint(teile):
            gruppe = next((g for g in gruppen if unabhaengig.isdisjoint(g) and
                           _gleiche_achse(liste[g[0]], liste[teile[0]])), None)
        if gruppe is None:
            gruppen.append(teile)
        else:
            gruppe.extend(teile)
    return gruppen


@dataclass
class Planetensatz:
    sonne: int
    hohlrad: int
    planeten: list[int]
    z_sonne: int
    z_planet: int
    z_hohlrad: int
    hinweise: list[str] = field(default_factory=list)

    planeten_ring: list[int] = field(default_factory=list)  # je Bolzen das hohlradseitige Band
    z_planet_ring: int | None = None

    @property
    def gestuft(self):
        return bool(self.planeten_ring)

    @property
    def umlaufraeder(self):
        return [*self.planeten, *self.planeten_ring]

    @property
    def zentralraeder(self):
        return [self.sonne, self.hohlrad]

    @property
    def teile(self):
        return {*self.zentralraeder, *self.umlaufraeder}

    @property
    def eingriffe(self):
        return [paar for a, b in zip(self.planeten, self.planeten_ring or self.planeten)
                for paar in ((self.sonne, a), (self.hohlrad, b))]

    @property
    def koeffizienten(self):
        if self.gestuft:
            return self.z_sonne * self.z_planet_ring, self.z_hohlrad * self.z_planet
        return self.z_sonne, self.z_hohlrad

    def titel(self, nr):
        return (tr("Stufenplanetensatz {}") if self.gestuft else tr("Planetensatz {}")).format(nr)

    def betriebsfaelle(self):
        """Drehzahlverhaeltnisse fuer vorgegebene Rollen; Geometrie allein legt sie nicht fest."""
        zs, zr = self.koeffizienten
        return [{"art": "planet", "fest": "hohlrad", "antrieb": "sonne", "abtrieb": "steg", "i": 1 + zr / zs},
                {"art": "planet", "fest": "sonne", "antrieb": "hohlrad", "abtrieb": "steg", "i": 1 + zs / zr},
                {"art": "stern", "fest": "steg", "antrieb": "sonne", "abtrieb": "hohlrad", "i": -zr / zs},
                {"art": "differential", "fest": None, "i": None}]

    def zeilen(self, liste: list[Verzahnung]) -> list[tuple[str, str]]:
        zs, zp, zr, n = self.z_sonne, self.z_planet, self.z_hohlrad, len(self.planeten)
        ks, kr = self.koeffizienten
        if self.gestuft:
            zaehne = (tr("Sonne / Sonnenband / Hohlradband / Hohlrad"), f"{zs} / {zp} / {self.z_planet_ring} / {zr}")
            namen = [f"{liste[a].teil} / {liste[b].teil}" for a, b in zip(self.planeten, self.planeten_ring)]
            montage = (tr("Montage der Stufenplaneten"), tr("Bandphasen und gleichzeitiger Eingriff sind ungeprüft."))
        else:
            zaehne = (tr("Sonne / Planeten / Hohlrad"), f"{zs} / {zp} / {zr}")
            namen = [liste[i].teil for i in self.planeten]
            wert = (zs + zr) / n
            montage = (tr("Montagebedingung (zs + zr) / n"),
                       f"{_g(wert, 3)} – " + (tr("erfüllt") if abs(wert - round(wert)) < 1e-9 else
                                              tr("nicht ganzzahlig: gleich verteilte Planeten nicht montierbar")))
        return [zaehne, (tr("Sonne / Hohlrad"), f"{liste[self.sonne].teil} / {liste[self.hohlrad].teil}"),
                (tr("Umlaufräder"), ", ".join(namen)), (tr("Anzahl Planeten"), str(n)),
                (tr("Standübersetzung i0 (Steg fest)"), _g(-kr / ks, 4)),
                (tr("Übersetzung Sonne → Steg (Hohlrad fest)"), _g(1 + kr / ks, 4)),
                (tr("Übersetzung Hohlrad → Steg (Sonne fest)"), _g(1 + ks / kr, 4)),
                montage, (tr("Teilung der Planeten"), self._teilung(liste)),
                (tr("Sternbetrieb (Steg fest)"), f"nS / nR = {_g(-kr / ks)}"),
                (tr("Dreiwellenbetrieb (kein Glied fest)"), f"{ks} nS + {kr} nR = {ks + kr} nC"),
                (tr("Drehzahlrollen"), tr("nS: Sonne, nR: Hohlrad, nC: Steg"))]

    def als_dict(self):
        ks, kr = self.koeffizienten
        return {"sonne": self.sonne, "hohlrad": self.hohlrad, "planeten": self.planeten,
                "gestuft": self.gestuft, "planeten_ring": self.planeten_ring, "umlaufraeder": self.umlaufraeder,
                "z_sonne": self.z_sonne, "z_planet": self.z_planet, "z_planet_ring": self.z_planet_ring,
                "z_hohlrad": self.z_hohlrad, "hinweise": self.hinweise, "rollen": ["sonne", "hohlrad", "steg"],
                "koeffizienten": [ks, kr, -(ks + kr)],
                "gleichung": "zS zP2 nS + zR zP1 nR = (zS zP2 + zR zP1) nC" if self.gestuft else
                             "zS nS + zR nR = (zS + zR) nC",
                "betriebsfaelle": self.betriebsfaelle(),
                **({"bandphasen_geprueft": False, "montierbarkeit": "unbestimmt",
                    "kinematik_voraussetzung": "gleichzeitiger_eingriff"} if self.gestuft else {})}

    def _teilung(self, liste: list[Verzahnung]) -> str:
        s = liste[self.sonne]
        u = np.cross(s.richtung, [1.0, 0, 0] if abs(s.richtung[0]) < 0.9 else [0, 1.0, 0])
        u /= np.linalg.norm(u)
        w = np.cross(s.richtung, u)
        winkel = sorted(math.degrees(math.atan2(float((liste[i].punkt - s.punkt) @ w),
                                                float((liste[i].punkt - s.punkt) @ u))) % 360 for i in self.planeten)
        abst = [(b - a) % 360 for a, b in zip(winkel, winkel[1:] + winkel[:1])]
        gleich = max(abst) - min(abst) < 0.5
        return ", ".join(f"{a:.1f}°" for a in abst) + (" – " + tr("gleich verteilt") if gleich else "")


def eingriff_moeglich(p: Paar) -> bool:
    """Positive Eingriffsstrecke und zueinander passende Steigungshaende eines Zylinderpaars."""
    a, b = p.a, p.b
    return p.eps_alpha > 0 and (not (a.beta and b.beta) or (a.hand == b.hand) == (a.innen or b.innen))


def _bandgruppen(liste, nachbarn):
    gruppen = {}
    for i in sorted(nachbarn):
        if not liste[i].innen:
            gruppen.setdefault(_koerperkennung(liste[i], i), []).append(i)
    return gruppen


def _planetenbaender(liste, sonnenseite, ringseite):
    """Je gemeinsamem Bolzen genau ein Band pro Eingriff. Koaxialitaet allein koppelt keine Planeten."""
    links = _bandgruppen(liste, sonnenseite)
    rechts = _bandgruppen(liste, ringseite)
    paare = []
    for koerper in links:
        if koerper not in rechts:
            continue
        if len(links[koerper]) != 1 or len(rechts[koerper]) != 1:
            return [], []  # Die Zuordnung der Baender auf diesem Koerper ist mehrdeutig.
        a, b = links[koerper][0], rechts[koerper][0]
        if not _gleiche_achse(liste[a], liste[b]) or any(_gleiche_achse(liste[a], liste[i]) for i, _ in paare):
            return [], []
        paare.append((a, b))
    if len(paare) < 2:
        return [], []
    a, b = map(list, zip(*paare))
    if a == b:
        return a, []
    if any(i == j for i, j in paare) or len({(liste[i].z, liste[j].z) for i, j in paare}) != 1:
        return [], []  # Kein einheitliches Stufenplanetenprofil auf allen Bolzen.
    return a, b


def _nur_satzkontakte(satz, nachbarn):
    """Ein zusaetzlicher innerer Zahneingriff kann einen Freiheitsgrad des Satzes sperren."""
    teile = satz.teile
    ist = {frozenset((i, j)) for i in teile for j in nachbarn[i] & teile if i < j}
    return ist == {frozenset(paar) for paar in satz.eingriffe}


def umlaufsaetze(liste: list[Verzahnung], paare: list[Paar]):
    """Planeten- und Ravigneauxsaetze aus demselben Netz moeglicher Eingriffe, ohne doppelte Grundstufe."""
    from . import ravigneaux
    idx = {id(v): i for i, v in enumerate(liste)}
    nachbarn: dict[int, set[int]] = {}
    for p in paare:
        if not isinstance(p, Paar) or not eingriff_moeglich(p):
            continue
        i, j = idx[id(p.a)], idx[id(p.b)]
        nachbarn.setdefault(i, set()).add(j)
        nachbarn.setdefault(j, set()).add(i)
    out = []
    for r, hohl in enumerate(liste):
        if not hohl.innen:
            continue
        for s, sonne in enumerate(liste):
            if sonne.innen or s == r or not _gleiche_achse(sonne, hohl):
                continue
            planeten, ringbaender = _planetenbaender(liste, nachbarn.get(s, ()), nachbarn.get(r, ()))
            if not planeten:
                continue
            zp = {liste[i].z for i in planeten}
            satz = Planetensatz(s, r, planeten, sonne.z, min(zp), hohl.z, planeten_ring=ringbaender,
                                z_planet_ring=liste[ringbaender[0]].z if ringbaender else None)
            if satz.gestuft:
                satz.hinweise.append(tr("Drehzahlen gelten bei gleichzeitigem Eingriff beider Planetenbänder."))
            elif len(zp) > 1:
                satz.hinweise.append(tr("Planeten mit verschiedenen Zähnezahlen: {}").format(sorted(zp)))
            if not satz.gestuft and hohl.z != sonne.z + 2 * min(zp):
                satz.hinweise.append(tr("zr ≠ zs + 2 zp – Profilverschiebung oder Planeten mit Stufen"))
            if _nur_satzkontakte(satz, nachbarn):
                out.append(satz)
    rv = ravigneaux.erkenne(liste, nachbarn, out)
    enthalten = {(p.sonne_lang, p.hohlrad) for p in rv}
    return [p for p in out if (p.sonne, p.hohlrad) not in enthalten], rv


def planetensaetze(liste: list[Verzahnung], paare: list[Paar]) -> list[Planetensatz]:
    return umlaufsaetze(liste, paare)[0]


def ravigneauxsaetze(liste: list[Verzahnung], paare: list[Paar]):
    return umlaufsaetze(liste, paare)[1]


@dataclass
class Stufe:
    antrieb: int
    abtrieb: int
    u: float
    gegenlaeufig: bool | None


@dataclass
class Kraftfluss:
    bezug: int  # Index der Bezugswelle
    stufen: list[Stufe]
    ergebnis: dict  # Welle -> (n_bezug / n_welle, Richtung bei parallelen Achsen)
    widerspruch: bool


def _kraftfluesse(liste, paare, planeten, bezugsrad=None, umlauf=()):
    """Festachsige Getriebezuege je Zusammenhang. Lose Raeder und Planeteneingriffe getrennt halten."""
    from collections import defaultdict, deque
    idx = {id(v): i for i, v in enumerate(liste)}
    gruppen = wellen(liste, planeten)
    welle = {i: k for k, g in enumerate(gruppen) for i in g}
    bewegt = {welle[i] for i in umlauf}
    # Auch beim direkten Aufruf mit Planetensatz-Indizes bleibt der Planetenbolzen eine bewegliche Achse.
    for s in planeten:
        ring = next((i for i in s if getattr(liste[i], "innen", False)), None)
        if ring is not None:
            bewegt.update(welle[i] for i in s if not _gleiche_achse(liste[i], liste[ring]))
    graph = defaultdict(list)
    for p in paare:
        i, j = idx[id(p.a)], idx[id(p.b)]
        if welle[i] in bewegt or welle[j] in bewegt or any(i in s and j in s for s in planeten):
            continue
        richtung = None
        if isinstance(p, Paar):
            if not eingriff_moeglich(p):
                continue
            richtung = 1 if p.a.innen or p.b.innen else -1
        graph[welle[i]].append((i, j, richtung))
        graph[welle[j]].append((j, i, richtung))
    def rang(k):
        # Endwelle mit kleinstem beteiligten Rad als nachvollziehbarer Standardbezug.
        rad = min((liste[i] for i, _, _ in graph[k]), key=lambda r: (r.z, r.teil))
        return (len(graph[k]) != 1, rad.z, rad.teil, tuple(rad.punkt))
    offen = set(graph)
    zuege = []
    while offen:
        start = welle.get(bezugsrad)
        if start not in offen:
            start = min(offen, key=rang)
        werte = {start: (1., 1)}
        stufen, widerspruch = [], False
        queue = deque([start])
        besucht = set()
        while queue:
            k = queue.popleft()
            offen.discard(k)
            faktor, vorzeichen = werte[k]
            for i, j, sinn in graph[k]:
                kante = tuple(sorted((i, j)))
                if kante in besucht:
                    continue
                besucht.add(kante)
                ab, u = welle[j], liste[j].z / liste[i].z
                vor = None if sinn is None or vorzeichen is None else sinn * vorzeichen
                stufen.append(Stufe(i, j, u, None if sinn is None else sinn < 0))
                if ab in werte:
                    bekannt, drehsinn = werte[ab]
                    if not math.isclose(bekannt, faktor * u) or (vor and drehsinn and vor != drehsinn):
                        widerspruch = True
                else:
                    werte[ab] = (faktor * u, vor)
                    queue.append(ab)
        zuege.append(Kraftfluss(start, stufen, werte, widerspruch))
    return gruppen, zuege


def _umlaufindizes(liste, paare):
    ids = [i for i, v in enumerate(liste) if isinstance(v, Verzahnung)]
    planeten, rv = umlaufsaetze([liste[i] for i in ids], paare)
    return planeten, rv, [{ids[i] for i in s.teile} for s in [*planeten, *rv]]


def _achswahl(varianten, nr, wahl):
    idx = (wahl or {}).get(nr, 0 if len(varianten) == 1 else None)
    if idx is not None and (not isinstance(idx, int) or idx not in range(len(varianten))):
        raise ValueError("Unbekannte Achsvariante")
    return idx


def _umlaufgruppen(gruppen, wahl):
    if wahl and any(k not in range(len(gruppen)) for k in wahl):
        raise ValueError("Unbekannte Differentialgruppe")
    mitglieder, umlauf = [], set()
    for nr, varianten in enumerate(gruppen):
        idx = _achswahl(varianten, nr, wahl)
        for s in varianten if idx is None else [varianten[idx]]:
            mitglieder.append(s.teile)
            umlauf.update(s.umlauf)
    return mitglieder, umlauf


def _differentialgruppen(liste, paare, kegel):
    from .getriebe_betrieb import differentialgruppen
    from .schraegraddifferential import schraegradgruppen
    return [*differentialgruppen(liste, kegel), *schraegradgruppen(liste, paare)]


def _zugdaten(liste, paare, bezugsrad, achswahl):
    from .verzahnung_sonder import kegelpaar_kandidaten, schneckenpaar_kandidaten
    saetze, rv, mitglieder = _umlaufindizes(liste, paare)
    kegel = kegelpaar_kandidaten(liste)
    diff = _differentialgruppen(liste, paare, kegel)
    weitere, umlauf = _umlaufgruppen(diff, achswahl)
    schnecken = schneckenpaar_kandidaten(liste)
    gruppen, zuege = _kraftfluesse(liste, [*paare, *kegel, *schnecken], mitglieder + weitere, bezugsrad, umlauf)
    return gruppen, zuege, saetze, diff, kegel, schnecken, rv


def _zuege(liste, paare, bezugsrad=None, achswahl=None):
    return _zugdaten(liste, paare, bezugsrad, achswahl)[:3]


def stufen(liste, paare, planeten, bezugsrad=None, achswahl=None):
    """Stufen und Wellenwerte aus den angegebenen Paaren ohne Eingriffe der Umlaufraeder."""
    from .verzahnung_sonder import kegelpaar_kandidaten
    _, _, mitglieder = _umlaufindizes(liste, [p for p in paare if isinstance(p, Paar)])
    if planeten:
        ids = [i for i, v in enumerate(liste) if isinstance(v, Verzahnung)]
        for s in planeten:
            gruppe = {ids[i] for i in s.teile}
            if gruppe not in mitglieder:
                mitglieder.append(gruppe)
    zylinderpaare = [p for p in paare if isinstance(p, Paar)]
    weitere, umlauf = _umlaufgruppen(_differentialgruppen(liste, zylinderpaare, kegelpaar_kandidaten(liste)), achswahl)
    _, zuege = _kraftfluesse(liste, paare, mitglieder + weitere, bezugsrad, umlauf)
    return _stufenwerte(zuege)


def _stufenwerte(zuege):
    return ([s for z in zuege for s in z.stufen],
            {k: v for z in zuege if not z.widerspruch for k, v in z.ergebnis.items()})


def _differentialgleichung(s):
    a, b, c = s.gleichungen[0]
    teiler = math.gcd(a, b, c)
    a, b, c = a // teiler, b // teiler, c // teiler
    formel = "nA + nB = 2 nC" if a == b == 1 else f"{a} nA + {b} nB = {-c} nC"
    return [a, b, c], formel


def _differential_zeilen(liste, gruppen, achswahl):
    zeilen = []
    for nr, varianten in enumerate(gruppen):
        schraeg = varianten[0].art == "schraegraddifferential"
        titel = (tr("Schrägraddifferential {}") if schraeg else tr("Symmetrisches Kegelraddifferential {}")).format(nr + 1)
        idx = _achswahl(varianten, nr, achswahl)
        wahl = tr("Achswahl offen") if idx is None else tr("Achse {}").format(idx + 1)
        zeilen.append((titel, wahl))
        for k, s in enumerate(varianten):
            name = tr("Achse {}").format(k + 1)
            seiten = f"{liste[s.a].teil} / {liste[s.b].teil}"
            zeilen.append((f"{titel} · {name} · " + tr("Seitenräder A / B"), seiten))
            if schraeg:
                paare = [f"{liste[i].teil} / {liste[j].teil}" for i, j in zip(s.umlauf[::2], s.umlauf[1::2])]
                zeilen.append((f"{titel} · {name} · " + tr("Ausgleichsradpaare A / B"), ", ".join(paare)))
            else:
                zeilen.append((f"{titel} · {name} · " + tr("Ausgleichsräder"), ", ".join(liste[i].teil for i in s.umlauf)))
        if schraeg:
            formel = _differentialgleichung(varianten[0])[1]
            zeilen.append((titel + " · " + tr("Drehzahlgleichung"), formel))
        else:
            zeilen.append((titel + " · " + tr("Drehzahlgleichung"), tr("nA + nB = 2 nC (nC: Stegdrehzahl)")))
        zeilen.append((titel + " · " + tr("Sperrwirkung und Torque Bias Ratio (TBR)"), tr("nicht bestimmbar")))
    return zeilen


def _differential_daten(liste, gruppen, achswahl):
    from .getriebe_betrieb import _positive_achse
    daten = []
    for nr, gruppe in enumerate(gruppen):
        idx = _achswahl(gruppe, nr, achswahl)
        varianten = []
        for s in gruppe:
            rad = liste[s.a]
            koeff, formel = _differentialgleichung(s)
            zusatz = {"ausgleichsradpaare": list(zip(s.umlauf[::2], s.umlauf[1::2])), "tbr": None,
                      "sperrwirkung": None} if s.art == "schraegraddifferential" else {}
            varianten.append({"seitenraeder": [s.a, s.b], "ausgleichsraeder": list(s.umlauf),
                              "stegachse": {"punkt": rad.punkt.tolist(), "richtung": _positive_achse(rad.richtung).tolist()},
                              "rollen": ["seitenrad_a", "seitenrad_b", "steg"],
                              "koeffizienten": koeff, "gleichung": formel, **zusatz})
        art = "schraegraddifferential" if gruppe[0].art == "schraegraddifferential" else "offenes_kegelraddifferential"
        daten.append({"art": art, "indexbezug": "kraftfluss.teile", "achswahl": idx,
                      "geometrie": "schraegraddifferential" if gruppe[0].art == "schraegraddifferential" else
                                   "symmetrisches_kegelraddifferential",
                      "sperrzustand": "unbekannt", "tbr": None,
                      "achswahl_erforderlich": idx is None, "varianten": varianten})
    return daten


def getriebe_zeilen(liste, paare, bezugsrad=None, achswahl=None):
    """Kraftfluss und bedingte Betriebsarten bei gegebenen oder noch offenen Achsen."""
    gruppen, zuege, saetze, diff, _, _, rv = _zugdaten(liste, paare, bezugsrad, achswahl)
    raeder = [v for v in liste if isinstance(v, Verzahnung)]
    zeilen = []
    for nr, zug in enumerate(zuege, 1):
        name = lambda k: " + ".join(liste[i].teil for i in gruppen[k])
        zeilen.append((tr("Getriebezug {} · Bezugswelle").format(nr), name(zug.bezug)))
        for n, s in enumerate(zug.stufen, 1):
            wert = f"u = {_g(s.u, 4)}"
            if s.gegenlaeufig is None:
                wert += " " + tr("(mögliche Paarung)")
            elif s.gegenlaeufig:
                wert += " " + tr("(gegenläufig)")
            zeilen.append((tr("Stufe {}: {} → {}").format(n, liste[s.antrieb].teil, liste[s.abtrieb].teil), wert))
        if zug.widerspruch:
            zeilen.append((tr("Kraftfluss"), tr("Widersprüchliche Übersetzungen oder Drehrichtungen im geschlossenen Zug")))
            continue
        for k, (gesamt, vor) in zug.ergebnis.items():
            if k == zug.bezug:
                continue
            wert = f"i = {_g(gesamt, 5)}"
            if vor is not None:
                wert += ", " + (tr("gleiche Drehrichtung") if vor > 0 else tr("Gegendrehrichtung"))
            zeilen.append((tr("Gesamtübersetzung zur Welle {}").format(name(k)), wert))
    for n, s in enumerate(saetze, 1):
        titel = s.titel(n)
        zeilen += [(titel + " – " + a, b) for a, b in s.zeilen(raeder)]
        zeilen += [(titel + " – " + tr("Hinweis"), h) for h in s.hinweise]
    for n, s in enumerate(rv, 1):
        zeilen += [(s.titel(n) + " – " + a, b) for a, b in s.zeilen(raeder)]
    return zeilen + _differential_zeilen(liste, diff, achswahl)


def datenblatt(liste: list, paare: list[Paar], bezugsrad=None, achswahl=None) -> dict:
    """Alles fuer den JSON-Export (Werte als Zahlen, mm und Grad)."""
    from . import passverzahnung as pv
    from .verzahnung_sonder import Sonderprofil, Taillenrad
    gruppen_alle, zuege, saetze, diff, kegel, schnecken, rv = _zugdaten(liste, paare, bezugsrad, achswahl)
    differentiale = _differential_daten(liste, diff, achswahl)
    teile = [v.teil for v in liste]
    bezug = liste[bezugsrad] if bezugsrad is not None else None
    sonder = [v for v in liste if isinstance(v, (Sonderprofil, Taillenrad))]
    profile = [v for v in liste if isinstance(v, pv.Steckprofil)]
    # Die aelteren JSON-Listen indizieren nur Zylinderraeder. Dieselben bekannten Umlaufachsen dort erhalten.
    zylinder_ids = [i for i, v in enumerate(liste) if isinstance(v, Verzahnung)]
    lokal = {i: k for k, i in enumerate(zylinder_ids)}
    weitere, umlauf = _umlaufgruppen(diff, achswahl)
    gruppierung = [s.teile for s in [*saetze, *rv]] + [{lokal[i] for i in g if i in lokal} for g in weitere]
    liste = [liste[i] for i in zylinder_ids]
    gruppen, zylinderzuege = _kraftfluesse(liste, paare, gruppierung, lokal.get(bezugsrad),
                                            [lokal[i] for i in umlauf if i in lokal])
    st, ziel = _stufenwerte(zylinderzuege)
    raeder = []
    for v in liste:
        d = v.als_dict()
        d["abgeleitet"] = {k: (None if isinstance(w, float) and (w != w or w == float("inf")) else w)
                           for k, w in stirnwerte(v).items() if k != "summe_x"}
        k = kugelmass(v)
        d["kugelmass"] = {"DM": k[0], "Md": k[1]} if k else None
        p = profil(v)
        from .flankentopografie import karte
        cb = breitenballigkeit(v)
        d["mikrogeometrie"] = None if p is None else {
            "dFf": p.dff, "dFa": p.dfa, "fussrundungsradius": v.fussradius, "kopffase_radial": v.kopffase,
            "kopfruecknahme": p.ca or None, "kopfruecknahme_ab_d": p.dca if p.ca else None,
            "profilwinkelabweichung": p.fh_alpha if abs(p.fh_alpha) > p.toleranz else None,
            "breitenballigkeit": cb if cb is not None and abs(cb) > p.toleranz else None, "schwelle": p.toleranz,
            "flankenkarte_stirnschnitt": karte(v, p)}
        raeder.append(d)
    idx = {id(v): i for i, v in enumerate(liste)}
    return {"einheiten": {"laenge": "mm", "winkel": "Grad"},
            "zahnraeder": raeder,
            "steckprofile": [v.als_dict() for v in profile],
            "sonderprofile": [v.als_dict() for v in sonder],
            "kegelpaar_kandidaten": [p.als_dict() for p in kegel],
            "schneckenpaar_kandidaten": [p.als_dict() for p in schnecken],
            "steckpaare": [p.als_dict() for p in pv.paare(profile)],
            "paare": [{"a": p.a.teil, "b": p.b.teil, "abstand": p.abstand, "abstand_soll": p.abstand_soll,
                       "spiel": p.spiel,  # Schluessel wie in Version 1
                       "raeder": [idx[id(p.a)], idx[id(p.b)]], "achsabstand": p.abstand,
                       "achsabstand_spielfrei": p.abstand_soll, "alpha_wt": p.alpha_wt, "eps_alpha": p.eps_alpha,
                       "eps_beta": p.eps_beta, **{k: w for k, w in paar_werte(p).items() if k not in ("klein", "gross")}}
                      for p in paare],
            "kraftfluss": {"annahme_koaxial_drehfest": True, "teile": teile, "wellen": gruppen_alle, "zuege": [
                {"bezugswelle": zug.bezug, "widerspruch": zug.widerspruch,
                 "stufen": [vars(s) for s in zug.stufen],
                 "wellenwerte": {} if zug.widerspruch else {str(k): {"i": i, "richtung": r}
                                                             for k, (i, r) in zug.ergebnis.items()}}
                for zug in zuege]},
            "wellen": gruppen,
            "stufen": [{"antrieb": s.antrieb, "abtrieb": s.abtrieb, "u": s.u, "gegenlaeufig": s.gegenlaeufig}
                       for s in st],
            "uebersetzung_je_welle": {str(k): {"i": i, "richtung": r} for k, (i, r) in ziel.items()},
            "differentialgruppen": differentiale,
            "planetensaetze": [s.als_dict() for s in saetze],
            "ravigneauxsaetze": [s.als_dict() for s in rv],
            "auslegungsbefunde": _befunde([*liste, *profile, *sonder], paare, bezug)}


def _befunde(liste, paare, bezug=None) -> list[dict]:
    from . import verzahnung_auslegung as va
    return va.als_dicts(va.alle(liste, paare, bezug))


# --- Formkreise und Mikrogeometrie aus der Zahndicke ueber dem Radius ---

def _halbwinkel(r: np.ndarray, z: int, innen: bool, radius: float) -> float:
    """Halber Zahnwinkel beim Radius: Anteil des Umfangs mit Zahn (aussen: Kontur ausserhalb, Hohlrad: innerhalb)."""
    zahn = r < radius if innen else r > radius
    return float(zahn.mean()) * math.pi / z


@dataclass
class Profil:
    """Profilabweichung je Flanke (mm normal zur Flanke, + = Material weggenommen) ueber dem Radius."""
    radien: np.ndarray
    abweichung: np.ndarray
    dff: float  # Fussformkreis-Durchmesser (Beginn der Evolvente)
    dfa: float  # Kopfformkreis-Durchmesser (Ende der Evolvente ohne Ruecknahme)
    ca: float  # Kopfruecknahme am Kopf (mm je Flanke), 0 = keine
    dca: float  # Beginn der Kopfruecknahme (Durchmesser)
    fh_alpha: float  # Profilwinkelabweichung ueber den Auswertebereich (mm, Steigung der Ausgleichsgeraden)
    toleranz: float  # Erkennungsschwelle (mm)
    grundradius: float  # an den fusseitigen Flankenbereich angepasst


def profil(v: Verzahnung, punkte: int = 120) -> Profil | None:
    """Profilabweichung im mittleren Stirnschnitt gegen die ideale Evolvente mit dem erkannten Grundkreis: halber
    Zahnwinkel psi(r) aus r(theta), Sollverlauf psi0 -/+ inv(alpha_r) (aussen/Hohlrad), psi0 aus dem mittleren Drittel
    der Flanke; Abweichung (psi_soll - psi) * rb je Flanke. Formkreise dort, wo die Abweichung die Schwelle verlaesst
    (sprunghaft: Fuss- bzw. Kopfform); stetig wachsend bis zum Kopf: Kopfruecknahme."""
    if v.r_mitte is None or not v.db or not v.mn:
        return None
    r = np.asarray(v.r_mitte, float)
    rb = v.db / 2
    r_min, r_max = float(r.min()), float(r.max())
    rand = 0.01 * (r_max - r_min)
    radien = np.linspace(max(r_min, rb) + rand, r_max - rand, punkte)
    psi = np.array([_halbwinkel(r, v.z, v.innen, x) for x in radien])
    s = -1.0 if v.innen else 1.0
    # Grundkreis fuer das Profil nur aus der fusseitigen Flankenhaelfte (dort reichen Kopfruecknahmen nicht hin):
    # psi + s inv(alpha_r) ist auf der Evolvente konstant
    fuss_seite = (radien >= radien[0] + 0.05 * (radien[-1] - radien[0])) & \
        (radien <= radien[0] + 0.3 * (radien[-1] - radien[0]))  # im Radius: die Waelzlaenge waechst unten schneller
    if v.innen:
        fuss_seite = (radien <= radien[-1] - 0.05 * (radien[-1] - radien[0])) & \
            (radien >= radien[-1] - 0.3 * (radien[-1] - radien[0]))

    def streuung(x):
        w = psi[fuss_seite] + s * np.array([_inv(math.acos(min(1.0, x / q))) for q in radien[fuss_seite]])
        return float(np.std(w))
    lo_rb, hi_rb = 0.97 * rb, min(1.03 * rb, 0.9999 * radien[fuss_seite].min() if fuss_seite.any() else rb)
    for _ in range(50):  # Goldener Schnitt
        a, b = lo_rb + 0.382 * (hi_rb - lo_rb), lo_rb + 0.618 * (hi_rb - lo_rb)
        lo_rb, hi_rb = (lo_rb, b) if streuung(a) < streuung(b) else (a, hi_rb)
    rb = (lo_rb + hi_rb) / 2
    inv_r = np.array([_inv(math.acos(min(1.0, rb / x))) for x in radien])
    psi0 = float(np.mean(psi[fuss_seite] + s * inv_r[fuss_seite]))
    lo, hi = radien[0] + (radien[-1] - radien[0]) / 3, radien[0] + 2 * (radien[-1] - radien[0]) / 3
    abw = (psi0 - s * inv_r - psi) * rb  # + = weniger Material (Zahn duenner bzw. Luecke weiter)
    if v.innen:
        abw = -abw
    tol = max(0.004, 0.003 * v.mn)
    i_mitte = int(np.argmin(np.abs(radien - (lo + hi) / 2)))
    unten = i_mitte
    while unten > 0 and abs(abw[unten - 1]) <= tol:
        unten -= 1
    oben = i_mitte
    while oben < len(radien) - 1 and abs(abw[oben + 1]) <= tol:
        oben += 1
    # Kopfseite: stetig wachsende Wegnahme bis zum Kopf = Ruecknahme (ein Kantenbruch springt)
    kopf = abw[oben + 1:]
    ca, dca = 0.0, 2 * radien[oben]
    if len(kopf) >= 3 and np.all(np.diff(kopf) > -tol / 2) and kopf[-1] > tol and \
            np.max(np.diff(np.concatenate([[abw[oben]], kopf]))) < 0.5 * kopf[-1]:
        # Gerade ueber der Waelzlaenge in der Ruecknahmezone: Wert am Kopfkreis und Nullstelle = Beginn
        zone = (np.arange(len(radien)) > oben) & (abw > tol / 2)
        lw = np.sqrt(np.maximum(radien[zone] ** 2 - rb ** 2, 0.0))
        k, d0 = np.polyfit(lw, abw[zone], 1)
        if k > 0:
            ls = max(-d0 / k, 0.0)
            la = math.sqrt(max((v.da / 2) ** 2 - rb ** 2, 0.0)) if not v.innen else float(lw.max())
            ca, dca = float(k * (la - ls)), 2 * math.sqrt(rb ** 2 + ls ** 2)
        else:
            ca = float(kopf[-1])
    nutz = slice(unten, oben + 1)
    walz = np.sqrt(np.maximum(radien[nutz] ** 2 - rb ** 2, 0.0))
    fh = float(np.polyfit(walz, abw[nutz], 1)[0] * (walz[-1] - walz[0])) if len(walz) > 2 else 0.0
    dff = 2 * radien[unten]
    dfa = 2 * (radien[oben] if not ca else radien[-1] + rand)
    if v.innen:
        dff, dfa = 2 * radien[oben], 2 * radien[unten]  # Hohlrad: Fuss aussen, Kopf innen
    if v.kopffase is not None:
        ca, dca = 0.0, 0.0  # Ruecknahme und ebene Fase sind sonst im Dickenverlauf nicht trennbar.
    return Profil(radien, abw, dff, dfa, ca, dca, fh, tol, rb)


def breitenballigkeit(v: Verzahnung) -> float | None:
    """Breitenballigkeit C_beta (mm je Flanke): Zahndickenaenderung der Schnitte entlang der Breite gegen die Mitte,
    Scheitel einer Parabel; None mit weniger als drei Schnitten."""
    if len(v.r_schnitte) < 3 or not v.db:
        return None
    radius = (v.d / 2) if v.d else float(np.mean(v.r_mitte))
    lagen = np.array([s for s, _ in v.r_schnitte])
    psi = np.array([_halbwinkel(np.asarray(r, float), v.z, v.innen, radius) for _, r in v.r_schnitte])
    rb = v.db / 2
    abw = (psi.max() - psi) * rb * (-1 if v.innen else 1)
    k = np.polyfit(lagen - lagen.mean(), abw, 2)
    halbe = (lagen.max() - lagen.min()) / 2
    return float(k[0] * halbe ** 2)


def mikro_zeilen(v: Verzahnung) -> list[tuple[str, str, str]]:
    p = profil(v)
    if p is None:
        return []
    quelle = tr("Zahndicke über dem Radius (mittlerer Stirnschnitt)")
    zeilen = [(tr("Fußformkreis dFf"), _g(p.dff, 3), quelle),
              (tr("Kopfformkreis dFa"), _g(p.dfa, 3), quelle)]
    quelle_form = tr("Wiederholte B-Rep-Flächen am Zahnprofil")
    zeilen += [(tr("Fußrundungsradius"), _g(v.fussradius, 4) if v.fussradius is not None else tr(NICHT), quelle_form),
               (tr("Kopffase, radiale Höhe"), _g(v.kopffase, 4) if v.kopffase is not None else tr(NICHT), quelle_form)]
    if v.kopffase is not None:
        zeilen.append((tr("Kopfrücknahme Cαa"), tr(NICHT), quelle))
    elif p.ca:
        zeilen.append((tr("Kopfrücknahme Cαa"), tr("{} ab d = {}").format(_g(p.ca, 4), _g(p.dca, 3)), quelle))
    else:
        zeilen.append((tr("Kopfrücknahme Cαa"), tr("keine modelliert"), quelle))
    zeilen.append((tr("Profilwinkelabweichung fHα"),
                   _g(p.fh_alpha, 4) if abs(p.fh_alpha) > p.toleranz else tr("keine modelliert"), quelle))
    cb = breitenballigkeit(v)
    zeilen.append((tr("Breitenballigkeit Cβ"),
                   tr(NICHT) if cb is None else (_g(cb, 4) if abs(cb) > p.toleranz else tr("keine modelliert")),
                   tr("Zahndicke der Stirnschnitte entlang der Breite")))
    return zeilen


def rad_alle_zeilen(v) -> list[tuple[str, str, str]]:
    """Alle Zeilen des Datenblatts eines Rads: gemessen, abgeleitet, Formkreise und Mikrogeometrie."""
    return v.zeilen() + rad_zeilen(v) + mikro_zeilen(v) if isinstance(v, Verzahnung) else v.zeilen()


def tabelle(zeilen_je_spalte: list[list[tuple]]) -> tuple[list[str], list[list[str]]]:
    """Gemeinsame Zeilennamen (Reihenfolge des ersten Auftretens) und je Spalte die Werte ("–" wo eine fehlt)."""
    namen: list[str] = []
    for z in zeilen_je_spalte:
        for eintrag in z:
            if eintrag[0] not in namen:
                namen.append(eintrag[0])
    werte = [[next((e[1] for e in z if e[0] == n), "–") for n in namen] for z in zeilen_je_spalte]
    return namen, werte


def als_csv(liste: list[Verzahnung], paare: list[Paar], bezugsrad=None, achswahl=None) -> str:
    """Datenblatt als CSV (Semikolon): Raeder spaltenweise mit Herkunft, darunter Paare und Getriebe."""
    import csv
    import io
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    zeilen = [rad_alle_zeilen(v) for v in liste]
    namen, werte = tabelle(zeilen)
    herkunft = {e[0]: e[2] for z in zeilen for e in z}
    w.writerow([tr("Größe")] + [v.teil for v in liste] + [tr("Herkunft")])
    for i, n in enumerate(namen):
        w.writerow([n] + [s[i] for s in werte] + [herkunft.get(n, "")])
    from . import passverzahnung as pv
    for paar in pv.paare([v for v in liste if isinstance(v, pv.Steckprofil)]):
        w.writerow([])
        w.writerow([tr("Steckverbindung"), paar.welle.teil, paar.nabe.teil])
        w.writerows(paar.zeilen())
    from .verzahnung_sonder import kegelpaar_kandidaten, schneckenpaar_kandidaten
    for paar in kegelpaar_kandidaten(liste) + schneckenpaar_kandidaten(liste):
        w.writerow([])
        w.writerow([tr("Radpaar"), paar.a.teil, paar.b.teil])
        w.writerows(paar.zeilen())
    if paare:
        w.writerow([])
        pz = [p.zeilen() + paar_zeilen(p) for p in paare]
        namen, werte = tabelle(pz)
        w.writerow([tr("Radpaar")] + [f"{p.a.teil} – {p.b.teil}" for p in paare])
        for i, n in enumerate(namen):
            w.writerow([n] + [s[i] for s in werte])
    getriebe = getriebe_zeilen(liste, paare, bezugsrad, achswahl)
    if getriebe:
        w.writerow([])
        w.writerow([tr("Getriebe")])
        w.writerows(getriebe)
    from . import verzahnung_auslegung as va
    befunde = va.alle(liste, paare, liste[bezugsrad] if bezugsrad is not None else None)
    if befunde:
        w.writerow([])
        w.writerow([tr("Auslegungsbefunde")])
        w.writerow([tr(s) for s in va.SPALTEN])
        for b in befunde:
            w.writerow(list(b.zeile()))
    from .flankentopografie import karte
    for rad in (v for v in liste if isinstance(v, Verzahnung)):
        raster = karte(rad, profil(rad))
        if raster is None:
            continue
        for seite, name in (("links_mm", tr("Linke Flanke")), ("rechts_mm", tr("Rechte Flanke"))):
            w.writerow([])
            w.writerow([rad.teil, name, tr("Flankenabweichung im Stirnschnitt (mm)")])
            w.writerow([tr("Axiallage / Radius (mm)"), *raster["radius_mm"]])
            w.writerows([s, *reihe] for s, reihe in zip(raster["axial_mm"], raster[seite]))
    return puffer.getvalue()
