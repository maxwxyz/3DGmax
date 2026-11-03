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


def paar_werte(p: Paar) -> dict:
    """Weitere Groessen eines Radpaars: Uebersetzung, Gesamtueberdeckung, Kopfspiele, Flankenspiele, spezifisches
    Gleiten (nur Aussenradpaar), Summe der Profilverschiebungen, Drehrichtung."""
    a, b = p.a, p.b
    innen = a.innen  # a ist beim Hohlradpaar das Hohlrad
    klein, gross = (b, a) if innen or abs(a.z) > abs(b.z) else (a, b)
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
        c_ritzel = p.abstand - a.da / 2 - b.df / 2
        c_gegen = p.abstand - b.da / 2 - a.df / 2
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

def _gleiche_achse(a: Verzahnung, b: Verzahnung, toleranz: float = 1e-3) -> bool:
    if abs(abs(float(a.richtung @ b.richtung)) - 1) > 1e-6:
        return False
    q = b.punkt - a.punkt
    return float(np.linalg.norm(q - a.richtung * float(q @ a.richtung))) < toleranz * max(a.d, b.d, 1.0)


def wellen(liste: list[Verzahnung]) -> list[list[int]]:
    """Gruppen gleichachsiger Raeder (Indizes) - Annahme: gleiche Achse = gleiche Welle (eine durchgehende Welle mit
    Lagern zwischen koaxialen Stufen laesst sich aus der Geometrie allein nicht unterscheiden)."""
    gruppen: list[list[int]] = []
    for i, v in enumerate(liste):
        g = next((g for g in gruppen if _gleiche_achse(liste[g[0]], v)), None)
        if g is None:
            gruppen.append([i])
        else:
            g.append(i)
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

    def zeilen(self, liste: list[Verzahnung]) -> list[tuple[str, str]]:
        zs, zp, zr, n = self.z_sonne, self.z_planet, self.z_hohlrad, len(self.planeten)
        montage = (zs + zr) / n
        return [(tr("Sonne / Planeten / Hohlrad"), f"{zs} / {zp} / {zr}"),
                (tr("Anzahl Planeten"), str(n)),
                (tr("Standübersetzung i0 (Steg fest)"), _g(-zr / zs, 4)),
                (tr("Übersetzung Sonne → Steg (Hohlrad fest)"), _g(1 + zr / zs, 4)),
                (tr("Übersetzung Hohlrad → Steg (Sonne fest)"), _g(1 + zs / zr, 4)),
                (tr("Montagebedingung (zs + zr) / n"),
                 f"{_g(montage, 3)} – " + (tr("erfüllt") if abs(montage - round(montage)) < 1e-9 else
                                           tr("nicht ganzzahlig: gleich verteilte Planeten nicht montierbar"))),
                (tr("Teilung der Planeten"), self._teilung(liste))]

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


def planetensaetze(liste: list[Verzahnung], paare: list[Paar]) -> list[Planetensatz]:
    """Hohlrad und gleichachsige Sonne mit mindestens zwei Planeten, die mit beiden kaemmen."""
    idx = {id(v): i for i, v in enumerate(liste)}
    nachbarn: dict[int, set[int]] = {}
    for p in paare:
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
            planeten = sorted(nachbarn.get(r, set()) & nachbarn.get(s, set()))
            if len(planeten) < 2:
                continue
            zp = {liste[i].z for i in planeten}
            satz = Planetensatz(s, r, planeten, sonne.z, min(zp), hohl.z)
            if len(zp) > 1:
                satz.hinweise.append(tr("Planeten mit verschiedenen Zähnezahlen: {}").format(sorted(zp)))
            if hohl.z != sonne.z + 2 * min(zp):
                satz.hinweise.append(tr("zr ≠ zs + 2 zp – Profilverschiebung oder Planeten mit Stufen"))
            out.append(satz)
    return out


@dataclass
class Stufe:
    antrieb: int  # Rad (Index) der treibenden Welle
    abtrieb: int
    u: float  # Uebersetzung z_abtrieb / z_antrieb
    gegenlaeufig: bool


def stufen(liste: list[Verzahnung], paare: list[Paar], planeten: list[Planetensatz]) -> tuple[list[Stufe], dict]:
    """Stirnradstufen ohne Planetensaetze in Kraftflussreihenfolge ab der Welle des kleinsten Rads der ersten Stufe;
    dazu je erreichbarer Welle die Gesamtuebersetzung und Drehrichtung bezogen auf die erste Welle."""
    in_satz = {i for s in planeten for i in [s.sonne, s.hohlrad, *s.planeten]}
    idx = {id(v): i for i, v in enumerate(liste)}
    gruppen = wellen(liste)
    welle = {i: k for k, g in enumerate(gruppen) for i in g}
    kanten = []
    for p in paare:
        i, j = idx[id(p.a)], idx[id(p.b)]
        if i in in_satz and j in in_satz:
            continue
        kanten.append((i, j, not p.a.innen and not p.b.innen))
    if not kanten:
        return [], {}
    i, j, _ = kanten[0]
    start_rad = i if abs(liste[i].z) <= abs(liste[j].z) else j  # Antrieb: Welle des kleineren Rads
    ziel = {welle[start_rad]: (1.0, 1)}  # Welle -> (Uebersetzung n_start / n_welle, Richtung)
    out, offen = [], list(kanten)
    neu = True
    while neu:  # Kraftfluss: jede Stufe, deren treibende Welle schon erreicht ist
        neu = False
        for k in list(offen):
            i, j, aussen = k
            for an, ab in ((i, j), (j, i)):
                if welle[an] in ziel and welle[ab] not in ziel:
                    u = abs(liste[ab].z) / abs(liste[an].z)
                    i0, r0 = ziel[welle[an]]
                    ziel[welle[ab]] = (i0 * u, -r0 if aussen else r0)
                    out.append(Stufe(an, ab, u, aussen))
                    offen.remove(k)
                    neu = True
                    break
    return out, ziel


def getriebe_zeilen(liste: list[Verzahnung], paare: list[Paar]) -> list[tuple[str, str]]:
    """Zusammenfassung: Stufen mit Gesamtuebersetzung je Welle und Planetensaetze."""
    saetze = planetensaetze(liste, paare)
    st, ziel = stufen(liste, paare, saetze)
    zeilen = []
    for n, s in enumerate(st, 1):
        zeilen.append((tr("Stufe {}: {} → {}").format(n, liste[s.antrieb].teil, liste[s.abtrieb].teil),
                       f"u = {_g(s.u, 4)}" + (" " + tr("(gegenläufig)") if s.gegenlaeufig else "")))
    gruppen = wellen(liste)
    for k, (i_ges, richtung) in ziel.items():
        if i_ges == 1.0 and richtung == 1:
            continue
        name = " + ".join(liste[i].teil for i in gruppen[k])
        zeilen.append((tr("Gesamtübersetzung zur Welle {}").format(name),
                       f"i = {_g(i_ges, 4)}, " + (tr("gleiche Drehrichtung") if richtung > 0 else
                                                   tr("Gegendrehrichtung"))))
    for n, s in enumerate(saetze, 1):
        zeilen += [(tr("Planetensatz {}").format(n) + " – " + a, b) for a, b in s.zeilen(liste)]
        zeilen += [(tr("Planetensatz {}").format(n) + " – " + tr("Hinweis"), h) for h in s.hinweise]
    return zeilen


def datenblatt(liste: list[Verzahnung], paare: list[Paar]) -> dict:
    """Alles fuer den JSON-Export (Werte als Zahlen, mm und Grad)."""
    saetze = planetensaetze(liste, paare)
    st, ziel = stufen(liste, paare, saetze)
    gruppen = wellen(liste)
    raeder = []
    for v in liste:
        d = v.als_dict()
        d["abgeleitet"] = {k: (None if isinstance(w, float) and (w != w or w == float("inf")) else w)
                           for k, w in stirnwerte(v).items() if k != "summe_x"}
        k = kugelmass(v)
        d["kugelmass"] = {"DM": k[0], "Md": k[1]} if k else None
        p = profil(v)
        cb = breitenballigkeit(v)
        d["mikrogeometrie"] = None if p is None else {
            "dFf": p.dff, "dFa": p.dfa, "kopfruecknahme": p.ca or None, "kopfruecknahme_ab_d": p.dca if p.ca else None,
            "profilwinkelabweichung": p.fh_alpha if abs(p.fh_alpha) > p.toleranz else None,
            "breitenballigkeit": cb if cb is not None and abs(cb) > p.toleranz else None, "schwelle": p.toleranz}
        raeder.append(d)
    idx = {id(v): i for i, v in enumerate(liste)}
    return {"einheiten": {"laenge": "mm", "winkel": "Grad"},
            "zahnraeder": raeder,
            "paare": [{"a": p.a.teil, "b": p.b.teil, "abstand": p.abstand, "abstand_soll": p.abstand_soll,
                       "spiel": p.spiel,  # Schluessel wie in Version 1
                       "raeder": [idx[id(p.a)], idx[id(p.b)]], "achsabstand": p.abstand,
                       "achsabstand_spielfrei": p.abstand_soll, "alpha_wt": p.alpha_wt, "eps_alpha": p.eps_alpha,
                       "eps_beta": p.eps_beta, **{k: w for k, w in paar_werte(p).items() if k not in ("klein", "gross")}}
                      for p in paare],
            "wellen": gruppen,
            "stufen": [{"antrieb": s.antrieb, "abtrieb": s.abtrieb, "u": s.u, "gegenlaeufig": s.gegenlaeufig}
                       for s in st],
            "uebersetzung_je_welle": {str(k): {"i": i, "richtung": r} for k, (i, r) in ziel.items()},
            "planetensaetze": [{"sonne": s.sonne, "hohlrad": s.hohlrad, "planeten": s.planeten, "z_sonne": s.z_sonne,
                                "z_planet": s.z_planet, "z_hohlrad": s.z_hohlrad, "hinweise": s.hinweise}
                               for s in saetze],
            "auslegungsbefunde": _befunde(liste, paare)}


def _befunde(liste, paare) -> list[dict]:
    from . import verzahnung_auslegung as va
    return va.als_dicts(va.alle(liste, paare))


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
    return Profil(radien, abw, dff, dfa, ca, dca, fh, tol)


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
    if p.ca:
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


def rad_alle_zeilen(v: Verzahnung) -> list[tuple[str, str, str]]:
    """Alle Zeilen des Datenblatts eines Rads: gemessen, abgeleitet, Formkreise und Mikrogeometrie."""
    return v.zeilen() + rad_zeilen(v) + mikro_zeilen(v)


def tabelle(zeilen_je_spalte: list[list[tuple]]) -> tuple[list[str], list[list[str]]]:
    """Gemeinsame Zeilennamen (Reihenfolge des ersten Auftretens) und je Spalte die Werte ("–" wo eine fehlt)."""
    namen: list[str] = []
    for z in zeilen_je_spalte:
        for eintrag in z:
            if eintrag[0] not in namen:
                namen.append(eintrag[0])
    werte = [[next((e[1] for e in z if e[0] == n), "–") for n in namen] for z in zeilen_je_spalte]
    return namen, werte


def als_csv(liste: list[Verzahnung], paare: list[Paar]) -> str:
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
    if paare:
        w.writerow([])
        pz = [p.zeilen() + paar_zeilen(p) for p in paare]
        namen, werte = tabelle(pz)
        w.writerow([tr("Radpaar")] + [f"{p.a.teil} – {p.b.teil}" for p in paare])
        for i, n in enumerate(namen):
            w.writerow([n] + [s[i] for s in werte])
        getriebe = getriebe_zeilen(liste, paare)
        if getriebe:
            w.writerow([])
            w.writerow([tr("Getriebe")])
            for a, b in getriebe:
                w.writerow([a, b])
    from . import verzahnung_auslegung as va
    befunde = va.alle(liste, paare)
    if befunde:
        w.writerow([])
        w.writerow([tr("Auslegungsbefunde")])
        w.writerow([tr(s) for s in va.SPALTEN])
        for b in befunde:
            w.writerow(list(b.zeile()))
    return puffer.getvalue()
