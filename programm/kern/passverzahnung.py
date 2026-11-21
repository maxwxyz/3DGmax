"""Steckprofile im Stirnschnitt und Nennspiele koaxialer Welle-Nabe-Paare."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr

# Modulreihen nach ISO 4156-1:2021, Einleitung (https://www.iso.org/standard/77819.html).
MODULE_30_375 = (0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4, 5, 6, 8, 10)
MODULE_45 = (0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5)


def _profiltext(art):
    return {"keil": tr("Keilprofil mit parallelen Flanken"), "kerb": tr("Kerbprofil mit geraden Flanken"),
            "evolvente": tr("Evolventen-Steckprofil")}[art]


def _zentriertext(art):
    return {"aussen": tr("Hinweis auf Außendurchmesserzentrierung"),
            "innen": tr("Hinweis auf Innendurchmesserzentrierung"),
            "flanke": tr("Hinweis auf Flankenzentrierung"),
            "uebermass": tr("Übermaß in der Nenngeometrie"), "offen": tr("nicht bestimmbar")}[art]


def _bogenweite(r: np.ndarray, z: int, radius: float) -> float:
    """Mittlere Bogenbreite des Wellenzahns bzw. der Nabennut beim Radius, interpolierte Schnittpunkte."""
    dr = np.roll(r, -1) - r
    innen = r > radius
    wechsel = innen != np.roll(innen, -1)
    anteile = innen.astype(float)
    bruch = (radius - r[wechsel]) / dr[wechsel]
    anteile[wechsel] = np.where(innen[wechsel], bruch, 1.0 - bruch)
    return float(anteile.mean()) * 2 * math.pi * radius / z


def _fussform(r, innen, z):
    """Anteil der Teilung dicht am Fuss: beim runden Grund waechst die Breite mit der Wurzel der Tiefe."""
    tiefe = (r.max() - r if innen else r - r.min()) / np.ptp(r)
    schmal = np.count_nonzero(tiefe < 0.01)
    breit = np.count_nonzero(tiefe < 0.05)
    if schmal < 4 * z or not breit:
        return "offen"
    anteil = schmal / breit
    if anteil > 0.77:
        return "flach"
    if 0.35 < anteil < 0.60:
        return "gerundet"
    return "offen"


@dataclass
class Steckprofil:
    teil: str
    art: str
    innen: bool
    z: int
    mitte: np.ndarray
    achse: np.ndarray
    b: float
    d_min: float
    d_max: float
    r: np.ndarray = field(repr=False)
    fehler: float = 0.0
    winkel: float | None = None
    keilbreite: float | None = None
    db: float | None = None
    modul: float | None = None
    alpha: float | None = None
    koerper: str | None = None
    koerper_id: object | None = field(default=None, repr=False, compare=False)

    @property
    def fussform(self):
        return _fussform(self.r, self.innen, self.z)

    @property
    def normfamilie(self):
        if self.art == "evolvente":
            return "ISO 4156 / DIN 5480" if self.alpha == 30.0 else "ISO 4156"
        return "ISO 14" if self.art == "keil" else None

    @property
    def messradius(self):
        return (self.d_min + self.d_max) / 4

    def zeilen(self):
        quelle = tr("Stirnschnitt")
        zeilen = [(tr("Art"), _profiltext(self.art), quelle),
                  (tr("Bauteil"), tr("Nabe") if self.innen else tr("Welle"), quelle),
                  (tr("Zähnezahl z"), str(self.z), tr("Harmonische von r(θ)")),
                  (tr("Kopfkreis da"), f"{self.d_min if self.innen else self.d_max:.3f}", quelle),
                  (tr("Fußkreis df"), f"{self.d_max if self.innen else self.d_min:.3f}", quelle),
                  (tr("Zahnbreite b"), f"{self.b:.3f}", tr("gemessen")),
                  (tr("Messkreisdurchmesser"), f"{2 * self.messradius:.3f}", quelle),
                  (tr("Nutenweite am Messkreis") if self.innen else tr("Zahndicke am Messkreis"),
                   f"{_bogenweite(self.r, self.z, self.messradius):.3f}", tr("Mittlere Bogenbreite")),
                  (tr("Flanken-Fitfehler"), f"{self.fehler:.4f}", quelle)]
        if self.winkel is not None:
            zeilen.append((tr("Eingeschlossener Flankenwinkel"), f"{self.winkel:.2f}°", tr("Geradenfit")))
        if self.keilbreite is not None:
            zeilen.append((tr("Nutenbreite B") if self.innen else tr("Keilbreite B"),
                           f"{self.keilbreite:.3f}", tr("Geradenfit")))
        if self.db is not None:
            zeilen.append((tr("Grundkreis db"), f"{self.db:.3f}", tr("Evolventen-Fit")))
            quelle = tr("Grundkreis und mögliche Normmodule")
            zeilen += [(tr("Modul m"), f"{self.modul:.4g}" if self.modul else tr("nicht bestimmbar"), quelle),
                       (tr("Eingriffswinkel αn"), f"{self.alpha:g}°" if self.alpha else tr("nicht bestimmbar"), quelle)]
        fuss = {"flach": tr("flacher Fußbereich"), "gerundet": tr("gerundeter Fußbereich"),
                "offen": tr("nicht bestimmbar")}[self.fussform]
        zeilen += [(tr("Fußform (Hinweis)"), fuss, tr("Breite des Profils nahe dem Fußkreis")),
                   (tr("Wirksame Lückenweite") if self.innen else tr("Wirksame Zahndicke"),
                    tr("nicht bestimmbar"), tr("Nenngeometrie")),
                   (tr("Passungsklasse"), tr("nicht bestimmbar"), tr("Nenngeometrie"))]
        if self.normfamilie:
            zeilen.append((tr("Mögliche Normfamilie"), self.normfamilie, tr("Profilform")))
        return zeilen

    def als_dict(self):
        return {"teil": self.teil, "koerper": self.koerper, "profil": self.art, "innen": self.innen, "z": self.z,
                "d_min": self.d_min, "d_max": self.d_max, "b": self.b, "d_mess": 2 * self.messradius,
                "bogenweite": _bogenweite(self.r, self.z, self.messradius), "flankenwinkel": self.winkel,
                "keilbreite": self.keilbreite, "db": self.db, "modul": self.modul, "alpha": self.alpha,
                "fit_fehler": self.fehler, "passungsklasse": None, "wirksame_breite": None,
                "fussform": self.fussform, "moegliche_normfamilie": self.normfamilie, "mitte": self.mitte.tolist(),
                "achse": self.achse.tolist()}


def erkenne(v, mitte, q, r, harmonische, rb, fit):
    """Flanken auf einen Wellenzahn falten. Dessen symmetrische Flanken bilden an der Nabe die Nut."""
    if v.hand:
        return None
    rad = np.hypot(*q.T)
    lo, hi = float(rad.min()), float(rad.max())
    hoehe = hi - lo
    teilung = 2 * np.pi / v.z
    # Das Winkelraster fuer die FFT beginnt bei -pi (entscheidend bei ungeradem z).
    winkel = np.arctan2(q[:, 1], q[:, 0]) + np.pi + np.angle(harmonische) / v.z
    delta = (winkel + teilung / 2) % teilung - teilung / 2
    flanken = (rad > lo + 0.2 * hoehe) & (rad < hi - 0.2 * hoehe)
    if np.count_nonzero(flanken) < 12 or np.ptp(rad[flanken]) < 0.5 * hoehe:
        return None
    x = rad[flanken] * np.cos(delta[flanken])
    y = np.abs(rad[flanken] * np.sin(delta[flanken]))
    steigung, abschnitt = np.polyfit(x, y, 1)
    fehler = float(np.sqrt(np.mean((y - steigung * x - abschnitt) ** 2)))
    profil = Steckprofil(v.teil, "", v.innen, v.z, mitte, v.richtung, v.b, 2 * lo, 2 * hi, r)
    # Ausgepraegte Kopf- und Fussbereiche grenzen gerade Steckflanken gegen Vielkante ab.
    if (fehler < 0.001 * hoehe and fehler < fit
            and np.mean(r > hi - 0.02 * hoehe) > 0.04 and np.mean(r < lo + 0.02 * hoehe) > 0.04):
        winkel = math.degrees(2 * math.atan(-steigung))
        if abs(winkel) <= 0.5:
            profil.art = "keil"
            profil.keilbreite = float(2 * y.mean())
        elif 10 < winkel < 135:
            profil.art = "kerb"
        else:
            return None
        profil.winkel = abs(winkel)
        profil.fehler = fehler
        return profil
    if rb <= 0 or fit > 0.005 * hoehe or fit >= fehler:
        return None
    # Ein Grundkreis bestimmt m und alpha nur gemeinsam. Nur fuer flache Profile und passende Modulreihe.
    kandidaten = []
    for alpha, module in ((30.0, MODULE_30_375), (37.5, MODULE_30_375), (45.0, MODULE_45)):
        modul = 2 * rb / (math.cos(math.radians(alpha)) * v.z)
        fehler_m = min(abs(m - modul) / m for m in module)
        if fehler_m <= 0.003 and 0.8 <= hoehe / modul <= 1.6 and lo < v.z * modul / 2 < hi:
            kandidaten.append((modul, alpha))
    if not kandidaten:
        return None
    profil.art = "evolvente"
    profil.db, profil.fehler = 2 * rb, fit
    if len(kandidaten) == 1:
        profil.modul, profil.alpha = kandidaten[0]
    return profil


@dataclass
class Steckpaar:
    welle: Steckprofil
    nabe: Steckprofil
    ueberdeckung: float
    d_mess: float
    aussen: float
    innen: float
    flanke: float
    zentrierung: str

    def zeilen(self):
        return [(tr("Gemeinsame Verzahnungslänge"), f"{self.ueberdeckung:.3f}"),
                (tr("Messkreisdurchmesser"), f"{self.d_mess:.3f}"),
                (tr("Durchmesserspiel außen"), f"{self.aussen:.3f}"),
                (tr("Durchmesserspiel innen"), f"{self.innen:.3f}"),
                (tr("Umfangsspiel am Messkreis"), f"{self.flanke:.3f}"),
                (tr("Zentrierung aus Nennspielen"), _zentriertext(self.zentrierung))]

    def als_dict(self):
        return {"welle": self.welle.teil, "nabe": self.nabe.teil, "ueberdeckung": self.ueberdeckung,
                "d_mess": self.d_mess, "spiel_aussen": self.aussen, "spiel_innen": self.innen,
                "spiel_umfang": self.flanke, "zentrierung": self.zentrierung}


def _paar(w, n):
    if w.koerper_id is not None and w.koerper_id is n.koerper_id:
        return None
    if w.art != n.art or w.z != n.z or abs(w.achse @ n.achse) < 0.99999:
        return None
    versatz = n.mitte - w.mitte
    axial = float(w.achse @ versatz)
    if np.linalg.norm(versatz - w.achse * axial) > max(1e-5, 1e-5 * w.d_max):
        return None
    breite = min(w.b / 2, axial + n.b / 2) - max(-w.b / 2, axial - n.b / 2)
    d0, d1 = max(w.d_min, n.d_min), min(w.d_max, n.d_max)
    if breite <= 1e-5 or d0 >= d1:
        return None
    if w.art == "kerb" and abs(w.winkel - n.winkel) > 0.5:
        return None
    if w.art == "evolvente" and abs(w.db - n.db) > 0.002 * w.db:
        return None
    radius = (d0 + d1) / 4
    flanke = _bogenweite(n.r, n.z, radius) - _bogenweite(w.r, w.z, radius)
    spiele = {"aussen": n.d_max - w.d_max, "innen": n.d_min - w.d_min, "flanke": flanke}
    # Nur eine innerhalb der Abtastaufloesung schliessende Kontaktart liefert einen Hinweis.
    eps = max(4 * w.fehler, 4 * n.fehler, 2 * np.pi * radius / len(w.r), 1e-5)
    eng = [art for art, spiel in spiele.items() if abs(spiel) <= eps]
    art = "uebermass" if min(spiele.values()) < -eps else (eng[0] if len(eng) == 1 else "offen")
    return Steckpaar(w, n, breite, 2 * radius, spiele["aussen"], spiele["innen"], flanke, art)


def paare(liste):
    out = []
    for welle in liste:
        if not welle.innen:
            for nabe in liste:
                if nabe.innen:
                    paar = _paar(welle, nabe)
                    if paar:
                        out.append(paar)
    return out
