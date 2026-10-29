"""Zweidimensionale Toleranzkette als Vektorzug (PLAN §8.33 Stufe 4, ohne Qt).

Die Kette ist ein Zug von Segmenten in einer Ebene: jedes Segment hat eine Laenge und einen Winkel zum vorigen
Segment (das erste zur X-Achse), beide mit Abmassen und Verteilung. Die Schlussgroesse ist eine Funktion des Zugs:
Abstand vom Ende zum Anfang, X- oder Y-Anteil dieses Schlussvektors, oder die Richtung des letzten Segments.

Rechnung nach der Direkten Linearisierungsmethode (Vektorzug, Chase/Gao/Magleby): Empfindlichkeit jeder Groesse als
zentrale Differenz am Nennwert; daraus 1D-Glieder mit Faktor = |Empfindlichkeit| und Richtung = Vorzeichen, plus ein
Glied ohne Toleranz fuer den Linearisierungsrest, so dass das 1D-Werkzeug (Worst Case, RSS, Monte Carlo, Ampel,
Kostenoptimierung) die linearisierte Kette rechnet. Die nichtlineare Monte-Carlo-Rechnung (alle Groessen
ausgewuerfelt, Schlussgroesse exakt) prueft die Linearisierung.

Gleitende Kontakte (kinematische Anpassung, Chase/Gao): eine Laenge oder ein Winkel kann "frei" sein - z. B. der
Kontaktpunkt gleitet auf einer Flaeche. Dann ist der Zug geschlossen (Ende = Anfang) und genau zwei freie Groessen
ergeben sich aus dieser Schliessbedingung (Newton, je Monte-Carlo-Probe); Schlussgroesse ist meist eine freie Groesse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr
from .toleranzkette import Glied

SCHLUSS = {"abstand": "Abstand Ende – Anfang", "x": "X-Anteil des Schlussvektors",
           "y": "Y-Anteil des Schlussvektors", "winkel": "Richtung des letzten Segments (°)",
           "frei1": "1. freie Größe (gleitet)", "frei2": "2. freie Größe (gleitet)"}
FREI = {"": "–", "laenge": "Länge", "winkel": "Winkel"}  # gleitende (abhaengige) Groesse eines Segments


@dataclass
class Segment:
    name: str
    laenge: float
    laenge_oben: float = 0.1
    laenge_unten: float = -0.1
    winkel: float = 0.0  # Grad zum vorigen Segment (erstes: zur X-Achse)
    winkel_oben: float = 0.0
    winkel_unten: float = 0.0
    verteilung: str = "normal"  # Schluessel aus toleranzkette.VERTEILUNG (fuer beide Groessen)
    werkstoff: str = ""  # eigener Werkstoff (leer: der der Kette)
    frei: str = ""  # "laenge" oder "winkel": ergibt sich aus der Schliessbedingung (gleitender Kontakt)


@dataclass
class Kette2D:
    segmente: list[Segment] = field(default_factory=list)
    schluss: str = "abstand"
    werkstoff: str = ""  # Vorgabe fuer alle Segmente ohne eigenen Werkstoff
    temperaturen: tuple | None = None  # zwei Grenztemperaturen (°C) fuer die Waermeausdehnung, None: ohne
    anforderung: tuple | None = None  # Grenzen der Schlussgroesse (unten, oben), None: ohne
    freigabe: dict = field(default_factory=dict)  # manuelle Freigabe {"geprueft", "name", "datum", "kommentar"}


def aus_punkten(punkte, namen: list[str] | None = None, toleranz=None) -> list[Segment]:
    """Segmente eines Zugs durch die Punkte (2D, in Reihenfolge): Laenge und Winkel zum vorigen Segment (erstes zur
    X-Achse); toleranz(Laenge) -> +-Abmass der Laenge (z. B. Allgemeintoleranz) oder None (ohne). Winkel ohne
    Abmasse (von Hand ergaenzen)."""
    pts = [np.asarray(p, float) for p in punkte]
    out, vorher = [], 0.0
    for i in range(1, len(pts)):
        d = pts[i] - pts[i - 1]
        laenge = float(np.linalg.norm(d))
        if laenge < 1e-9:
            continue  # doppelter Punkt
        richtung = math.degrees(math.atan2(d[1], d[0]))
        winkel = (richtung - vorher + 180.0) % 360.0 - 180.0 if out else richtung
        vorher = richtung
        t = toleranz(laenge) if toleranz else None
        name = (namen[i - 1] + " – " + namen[i]) if namen and len(namen) > i else tr("Segment {}").format(len(out) + 1)
        out.append(Segment(name, round(laenge, 6), t or 0.0, -(t or 0.0), round(winkel, 6)))
    return out


def werkstoff(k: Kette2D, s: Segment) -> str:
    """Werkstoff eines Segments: eigener, sonst der der Kette."""
    return s.werkstoff or k.werkstoff


def bei_temperatur(k: Kette2D, temperatur: float) -> Kette2D:
    """Kette bei einer Temperatur: jede Laenge waechst um alpha * L * (T - 20 °C) mit dem Werkstoff ihres Segments;
    Winkel bleiben (Abmasse wandern mit dem Nennwert)."""
    import copy
    from .werkstoffe import alpha_fuer, laengenaenderung
    out = copy.deepcopy(k)
    for s, o in zip(k.segmente, out.segmente):
        a = alpha_fuer(werkstoff(k, s))
        if a:
            o.laenge = s.laenge + laengenaenderung(a, abs(s.laenge), temperatur)
    return out


def freie(k: Kette2D) -> list[tuple[int, str]]:
    """Gleitende (abhaengige) Groessen (Segment, "laenge" | "winkel") in Kettenreihenfolge."""
    return [(i, s.frei) for i, s in enumerate(k.segmente) if s.frei in ("laenge", "winkel")]


def _parameter(k: Kette2D) -> list[tuple[int, str]]:
    """(Segment, "laenge" | "winkel") je unabhaengige Groesse (freie ergeben sich aus der Schliessbedingung)."""
    frei = set(freie(k))
    return [(i, g) for i in range(len(k.segmente)) for g in ("laenge", "winkel") if (i, g) not in frei]


def pruefe(k: Kette2D) -> str:
    """Fehlertext, wenn die gleitenden Groessen nicht passen ("" = in Ordnung)."""
    n = len(freie(k))
    if n not in (0, 2):
        return tr("Ein geschlossener Zug braucht genau zwei freie (gleitende) Größen – gewählt: {}").format(n)
    if n == 0 and k.schluss in ("frei1", "frei2"):
        return tr("Schlussgröße „freie Größe“ braucht zwei freie (gleitende) Größen")
    return ""


def _schliesse(k: Kette2D, werte: dict) -> dict:
    """Freie Groessen so, dass der Zug schliesst (Ende = Anfang); werte: {(i, g): Wert oder Array} der
    unabhaengigen Groessen (fehlende: Nennwert). Newton mit der analytischen 2x2-Jacobimatrix, auch je Probe."""
    frei = freie(k)
    if len(frei) != 2:
        return werte
    n = max((np.size(v) for v in werte.values()), default=1)
    alle = {(i, g): np.broadcast_to(np.asarray(werte.get((i, g), getattr(s, g)), float), (n,)).astype(float)
            for i, s in enumerate(k.segmente) for g in ("laenge", "winkel")}
    for _ in range(30):
        richtung = np.cumsum(np.radians([alle[(i, "winkel")] for i in range(len(k.segmente))]), axis=0)
        laengen = np.array([alle[(i, "laenge")] for i in range(len(k.segmente))])
        rest = np.array([np.sum(laengen * np.cos(richtung), axis=0), np.sum(laengen * np.sin(richtung), axis=0)])
        if np.max(np.abs(rest)) < 1e-11:
            break
        spalten = []
        for i, g in frei:
            if g == "laenge":
                spalten.append(np.array([np.cos(richtung[i]), np.sin(richtung[i])]))
            else:  # Winkel i dreht alle folgenden Segmente (je Grad)
                spalten.append(np.radians(1.0) * np.array([-np.sum(laengen[i:] * np.sin(richtung[i:]), axis=0),
                                                            np.sum(laengen[i:] * np.cos(richtung[i:]), axis=0)]))
        a, b = spalten
        det = a[0] * b[1] - a[1] * b[0]
        det = np.where(np.abs(det) < 1e-14, np.nan, det)  # nicht schliessbar: NaN statt Unsinn
        d0 = (rest[0] * b[1] - rest[1] * b[0]) / det
        d1 = (a[0] * rest[1] - a[1] * rest[0]) / det
        alle[frei[0]] = alle[frei[0]] - d0
        alle[frei[1]] = alle[frei[1]] - d1
    if n == 1:
        return {key: float(v[0]) for key, v in alle.items()}
    return alle


def punkte(k: Kette2D, werte: dict | None = None) -> np.ndarray:
    """Eckpunkte des Zugs (n+1 x 2) ab dem Ursprung; werte: {(i, groesse): Wert} ersetzt Nennwerte (freie Groessen
    aus der Schliessbedingung)."""
    werte = _schliesse(k, dict(werte or {})) if freie(k) else (werte or {})
    p, richtung, out = np.zeros(2), 0.0, [np.zeros(2)]
    for i, s in enumerate(k.segmente):
        richtung += math.radians(werte.get((i, "winkel"), s.winkel))
        lang = werte.get((i, "laenge"), s.laenge)
        p = p + lang * np.array([math.cos(richtung), math.sin(richtung)])
        out.append(p)
    return np.array(out)


def schlussgroesse(k: Kette2D, werte: dict | None = None) -> float:
    if freie(k):
        werte = _schliesse(k, dict(werte or {}))
        if k.schluss in ("frei1", "frei2"):
            return float(werte[freie(k)[0 if k.schluss == "frei1" else 1]])
    pts = punkte(k, werte)
    if k.schluss == "winkel":
        richtung = sum(werte.get((i, "winkel"), s.winkel) if werte else s.winkel for i, s in enumerate(k.segmente))
        return (richtung + 180.0) % 360.0 - 180.0
    v = pts[0] - pts[-1]  # Schlussvektor vom Ende zurueck zum Anfang
    return float(np.linalg.norm(v)) if k.schluss == "abstand" else float(v[0] if k.schluss == "x" else v[1])


def empfindlichkeiten(k: Kette2D, schritt: float = 1e-5) -> dict:
    """d(Schlussgroesse)/d(Groesse) je (Segment, Groesse) als zentrale Differenz."""
    out = {}
    for key in _parameter(k):
        i, g = key
        nenn = getattr(k.segmente[i], g)
        h = schritt * max(1.0, abs(nenn))
        out[key] = (schlussgroesse(k, {key: nenn + h}) - schlussgroesse(k, {key: nenn - h})) / (2 * h)
    return out


def als_glieder(k: Kette2D) -> list[Glied]:
    """Linearisierte Kette fuer das 1D-Werkzeug: je tolerierte Groesse ein Glied mit Faktor |dS/dp| und Richtung
    sign(dS/dp), dazu der Linearisierungsrest S(Nenn) - Summe(dS/dp * p) als Glied ohne Toleranz."""
    e = empfindlichkeiten(k)
    glieder, linear = [], 0.0
    for (i, g), d in e.items():
        s = k.segmente[i]
        nenn = getattr(s, g)
        oben, unten = getattr(s, g + "_oben"), getattr(s, g + "_unten")
        if abs(d) < 1e-12 or oben == unten == 0:
            continue  # untolerierte Groessen stecken im Linearisierungsrest
        linear += d * nenn
        einheit = "°" if g == "winkel" else ""
        name = f"{s.name} – {tr('Winkel') if g == 'winkel' else tr('Länge')} {nenn:g}{einheit}"
        glieder.append(Glied(name, nenn, nenn + oben, nenn + unten, 1 if d > 0 else -1, verteilung=s.verteilung,
                             quelle="eigen", faktor=abs(d), werkstoff=werkstoff(k, s) if g == "laenge" else "",
                             waerme=g == "laenge"))
    rest = schlussgroesse(k) - linear
    glieder.append(Glied(tr("Linearisierung (Nennlage)"), rest, rest, rest, 1, quelle="eigen", waerme=False))
    return glieder


def monte_carlo(k: Kette2D, proben: int = 50_000, cp: float = 1.0, zufall: int = 1) -> np.ndarray:
    """Schlussgroesse nichtlinear: alle Groessen nach ihrer Verteilung ausgewuerfelt, Zug exakt ausgewertet."""
    rng = np.random.default_rng(zufall)
    ziehungen = {}
    for i, g in _parameter(k):
        s = k.segmente[i]
        nenn = getattr(s, g)
        gl = Glied("", nenn, nenn + getattr(s, g + "_oben"), nenn + getattr(s, g + "_unten"), verteilung=s.verteilung)
        ziehungen[(i, g)] = gl.ziehe(rng, proben, cp) if gl.toleranz > 0 else np.full(proben, nenn)
    if freie(k):  # geschlossener Zug: freie Groessen je Probe aus der Schliessbedingung
        ziehungen = _schliesse(k, ziehungen)
        if k.schluss in ("frei1", "frei2"):
            return np.asarray(ziehungen[freie(k)[0 if k.schluss == "frei1" else 1]], float)
    # vektorisiert: Richtungen kumulieren, Punkte summieren
    richtung = np.cumsum(np.radians(np.array([ziehungen[(i, "winkel")] for i in range(len(k.segmente))])), axis=0)
    laengen = np.array([ziehungen[(i, "laenge")] for i in range(len(k.segmente))])
    x = np.sum(laengen * np.cos(richtung), axis=0)
    y = np.sum(laengen * np.sin(richtung), axis=0)
    if k.schluss == "winkel":
        return (np.degrees(richtung[-1]) + 180.0) % 360.0 - 180.0
    if k.schluss == "abstand":
        return np.hypot(x, y)
    return -x if k.schluss == "x" else -y


def als_dict(k: Kette2D) -> dict:
    from dataclasses import asdict
    return {"schluss": k.schluss, "segmente": [asdict(s) for s in k.segmente], "werkstoff": k.werkstoff,
            "temperaturen": list(k.temperaturen) if k.temperaturen else None,
            "anforderung": list(k.anforderung) if k.anforderung else None, "freigabe": dict(k.freigabe)}


def von_dict(d: dict) -> Kette2D:
    felder = set(Segment.__dataclass_fields__)
    return Kette2D([Segment(**{a: b for a, b in s.items() if a in felder}) for s in d.get("segmente", [])],
                   d.get("schluss", "abstand"), d.get("werkstoff", ""),
                   tuple(d["temperaturen"]) if d.get("temperaturen") else None,
                   tuple(d["anforderung"]) if d.get("anforderung") else None, dict(d.get("freigabe") or {}))
