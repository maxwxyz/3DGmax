"""Vorauslegung mit expliziten Lasten, Einheiten und Geltungsbereichen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import hypot, isfinite, pi, radians, tan


@dataclass(frozen=True)
class Verfahren:
    titel: str
    annahme: str
    eingaben: tuple[str, ...]
    ausgaben: tuple[str, ...]
    rechnen: Callable[..., tuple[float, ...]]


def _welle(d, t, tau):
    return 16000 * t / (pi * d**3), (16000 * t / (pi * tau)) ** (1 / 3)


def _lagerwelle(d, spannweite, x, f, t):
    if x > spannweite:
        raise ValueError("x")
    rechts = f * (x / spannweite)
    links = f - rechts
    mb = links * x
    sigma = 32 * mb / (pi * d**3)
    tau = 16000 * t / (pi * d**3)
    return links, rechts, mb / 1000, sigma, hypot(sigma, 3**.5 * tau)


def _buchse(d, l, f, n, pzul):
    p = f / (d * l)
    v = pi * d * n / 60000
    return p, v, p * v, f / (d * pzul)


def _reibsitz(d, l, t, mu, p):
    faktor = pi * mu * d**2 * l / 2000
    return t / faktor, p * faktor


def _pressverband(d, l, da, ew, nw, en, nn, umin, umax, mu, t):
    if da <= d:
        raise ValueError("da")
    if umax < umin:
        raise ValueError("umax")
    # Lame-Loesung bei freien Stirnseiten, wirksames diametrales Uebermass in Mikrometern.
    q = d / da
    nachgiebigkeit = (1 - nw) / ew + ((1 + q*q) / (1 - q*q) + nn) / en
    skala = 1000 * d * nachgiebigkeit
    p1, p2 = umin / skala, umax / skala
    bedarf, tragmoment = _reibsitz(d, l, t, mu, p1)
    return p1, p2, tragmoment, bedarf * skala


def _stirnrad(z1, z2, m, alpha, t):
    d1, d2 = z1 * m, z2 * m
    ft = 2000 * t / d1
    return d1, d2, (d1 + d2) / 2, z2 / z1, ft, ft * tan(radians(alpha))


def _lager(c, p, n, exponent):
    l10 = (c / p) ** exponent
    return l10, 1e6 * l10 / (60 * n)


# Kennung, Beschriftung und Einheit der editierbaren Eingaben
FELDER = {
    "d": ("Sitzdurchmesser", "mm"), "l": ("Wirksame Länge", "mm"),
    "t": ("Drehmoment (Betrag)", "N·m"), "tau": ("Zulässige Schubspannung", "MPa"),
    "f": ("Radiallast", "N"), "n": ("Drehzahl (Betrag)", "min⁻¹"),
    "pzul": ("Zulässige Flächenpressung", "MPa"), "mu": ("Haftreibungszahl", ""),
    "p": ("Angenommener Fugendruck", "MPa"), "c": ("Dynamische Tragzahl C", "kN"),
    "peq": ("Äquivalente dynamische Lagerlast P", "kN"),
    "z1": ("Zähnezahl Ritzel", ""), "z2": ("Zähnezahl Rad", ""),
    "m": ("Modul", "mm"), "alpha": ("Eingriffswinkel", "°"),
    "tau_max": ("Schubspannung am Rand", "MPa"), "d_min": ("Mindestdurchmesser", "mm"),
    "p_m": ("Mittlere Flächenpressung", "MPa"), "v": ("Gleitgeschwindigkeit", "m/s"),
    "pv": ("Druck-Geschwindigkeits-Produkt", "MPa·m/s"), "l_min": ("Mindestlänge aus Pressung", "mm"),
    "p_min": ("Erforderlicher Fugendruck", "MPa"), "t_max": ("Übertragbares Drehmoment", "N·m"),
    "d1": ("Teilkreisdurchmesser Ritzel", "mm"), "d2": ("Teilkreisdurchmesser Rad", "mm"),
    "a": ("Achsabstand", "mm"), "i": ("Übersetzungsbetrag", ""),
    "ft": ("Umfangskraft", "N"), "fr": ("Radialkraft", "N"),
    "da": ("Nabenaußendurchmesser", "mm"),
    "ew": ("Elastizitätsmodul Welle", "MPa"), "en": ("Elastizitätsmodul Nabe", "MPa"),
    "nw": ("Querkontraktionszahl Welle", ""), "nn": ("Querkontraktionszahl Nabe", ""),
    "umin": ("Kleinstes wirksames Übermaß", "µm"), "umax": ("Größtes wirksames Übermaß", "µm"),
    "p1": ("Kleinster Fugendruck", "MPa"), "p2": ("Größter Fugendruck", "MPa"),
    "t1": ("Reibmoment bei Mindestübermaß", "N·m"), "u_req": ("Erforderliches wirksames Übermaß", "µm"),
    "span": ("Lagerabstand", "mm"), "x": ("Lastabstand ab Lager A", "mm"),
    "quer": ("Querlast am Rad", "N"), "ra": ("Radiale Lagerreaktion A", "N"),
    "rb": ("Radiale Lagerreaktion B", "N"), "mb": ("Maximales Biegemoment", "N·m"),
    "sigma": ("Biegerandspannung", "MPa"), "sigma_v": ("Vergleichsspannung nach von Mises", "MPa"),
    "l10": ("Nominelle Lebensdauer L10", "10⁶ U"), "l10h": ("Nominelle Lebensdauer L10h", "h"),
}

_LAGER = "Konstante äquivalente Lagerlast und Drehzahl, 90 % Zuverlässigkeit. Tragzahl aus dem Lagerkatalog."
VERFAHREN = {
    "stirnrad": Verfahren("Geradverzahntes Stirnradpaar", "Außenverzahnung ohne Profilverschiebung, Nennkräfte am Ritzel.",
                         ("z1", "z2", "m", "alpha", "t"), ("d1", "d2", "a", "i", "ft", "fr"), _stirnrad),
    "welle": Verfahren("Vollwelle unter Torsion", "Glatter, voller Rundquerschnitt unter reinem statischem Drehmoment.",
                       ("d", "t", "tau"), ("tau_max", "d_min"), _welle),
    "lagerwelle": Verfahren("Zweifach gelagerte Vollwelle",
                            "Einzellast zwischen zwei idealen Stützen, gleicher Vollquerschnitt und konstantes Drehmoment. Statischer Nennspannungsnachweis ohne Kerben.",
                            ("d", "span", "x", "quer", "t"), ("ra", "rb", "mb", "sigma", "sigma_v"), _lagerwelle),
    "buchse": Verfahren("Radiales Gleitlager", "Stationäre Radiallast auf der projizierten Lagerfläche. Grenzpressung aus den Werkstoffdaten.",
                        ("d", "l", "f", "n", "pzul"), ("p_m", "v", "pv", "l_min"), _buchse),
    "reibsitz": Verfahren("Zylindrischer Reibsitz", "Gleichmäßiger Fugendruck und reine Drehmomentübertragung durch Haftreibung.",
                         ("d", "l", "t", "mu", "p"), ("p_min", "t_max"), _reibsitz),
    "pressverband": Verfahren("Elastischer Pressverband",
                              "Vollwelle und konzentrische dickwandige Nabe mit freien Stirnseiten. Wirksame Übermaße nach Glättung bei Betriebstemperatur, rein elastisch und unter Torsion.",
                              ("d", "l", "da", "ew", "nw", "en", "nn", "umin", "umax", "mu", "t"),
                              ("p1", "p2", "t1", "u_req"), _pressverband),
    "kugellager": Verfahren("Kugellager", _LAGER, ("c", "peq", "n"), ("l10", "l10h"),
                            lambda c, p, n: _lager(c, p, n, 3)),
    "rollenlager": Verfahren("Rollenlager", _LAGER, ("c", "peq", "n"), ("l10", "l10h"),
                             lambda c, p, n: _lager(c, p, n, 10 / 3)),
}


def berechne(art, eingaben):
    verfahren = VERFAHREN[art]
    werte = []
    for feld in verfahren.eingaben:
        wert = eingaben.get(feld)
        if type(wert) not in (int, float) or not isfinite(wert):
            raise ValueError(feld)
        if feld in ("nw", "nn"):
            if not -1 < wert < .5:
                raise ValueError(feld)
        elif wert < 0:
            raise ValueError(feld)
        if wert == 0 and feld not in ("t", "f", "x", "quer", "umin", "umax", "nw", "nn") and not (feld == "n" and art == "buchse"):
            raise ValueError(feld)
        if feld in ("z1", "z2") and (wert < 3 or not float(wert).is_integer()):
            raise ValueError(feld)
        if feld == "alpha" and wert >= 90:
            raise ValueError(feld)
        werte.append(wert)
    ergebnisse = dict(zip(verfahren.ausgaben, verfahren.rechnen(*werte), strict=True))
    if not all(isfinite(v) for v in ergebnisse.values()):
        raise ValueError(verfahren.eingaben[0])
    return ergebnisse


def schreibe_sitzteil(ziel, d, laenge, bohrung=None):
    """Nenngeometrie mit semantischen und grafischen Durchmesser- und Laengenmassen."""
    from .drehzeichnung import schreibe_drehteil
    from .pmi import MASS, Pmi
    masse = (d, laenge) if bohrung is None else (d, laenge, bohrung)
    if any(not isfinite(v) or v <= 1e-6 for v in masse) or (bohrung is not None and d - bohrung <= 1e-6):
        raise ValueError("d")
    abschnitt = (Pmi(MASS, "Location_LinearDistance", nennwert=laenge), Pmi(MASS, "Size_Diameter", nennwert=d))
    innen = None if bohrung is None else Pmi(MASS, "Size_Diameter", nennwert=bohrung)
    return schreibe_drehteil(ziel, [abschnitt], bohrung=innen)
