"""Konische Zahnprofile und ein- bis viergaengige Schraubprofile aus Stirnschnitten (PLAN 8.27a)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr


def stirnachse(flaechen, hauptachse):
    """Zwei parallele axiale Abschluesse bestaetigen die Achsrichtung auch bei einem unsymmetrischen Gewindegang."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane
    ebenen = []
    for f in flaechen:
        if BRep_Tool.Surface(f) is None:
            continue
        sf = BRepAdaptor_Surface(f)
        if sf.GetType() != GeomAbs_Plane:
            continue
        ax = sf.Plane().Axis()
        n = np.array(ax.Direction().Coord())
        if abs(n @ hauptachse) > .996:
            ebenen.append((n, np.array(ax.Location().Coord())))
    for i, (n, p) in enumerate(ebenen):
        if any(abs(nn @ n) > 1 - 1e-9 and abs((q - p) @ n) > 1e-5 for nn, q in ebenen[i + 1:]):
            return n if n @ hauptachse > 0 else -n
    return hauptachse


@dataclass
class Sonderprofil:
    teil: str
    art: str
    z: int
    punkt: np.ndarray  # Achspunkt am Beginn des Messbereichs; bei Kegeln am schmalen Ende
    richtung: np.ndarray
    breite: float  # axialer Abstand der aeussersten ausgewerteten Schnitte
    kopf: tuple  # Radien am Beginn und Ende des Messbereichs
    fuss: tuple
    phase: float | None  # Aenderung des Zahnspurwinkels ueber den Messbereich (rad)
    koerper: str | None = None
    bandgrenzen: tuple[float, float] | None = None  # belegte Stirnenden relativ zum Achspunkt
    koerper_id: object | None = field(default=None, repr=False, compare=False)

    def als_dict(self):
        return {"teil": self.teil, "koerper": self.koerper, "art": self.art, "anzahl": self.z, "messlaenge": self.breite,
                "achse": {"punkt": self.punkt.tolist(), "richtung": self.richtung.tolist()},
                "kopf_r": list(self.kopf), "fuss_r": list(self.fuss), "phasenweg_grad": math.degrees(self.phase) if self.phase is not None else None,
                **self._werte()}

    def _werte(self):
        if self.art == "konisch":
            return {"kopfkegelwinkel": math.degrees(math.atan((self.kopf[1] - self.kopf[0]) / self.breite)),
                    "fusskegelwinkel": math.degrees(math.atan((self.fuss[1] - self.fuss[0]) / self.breite))}
        hub = 2 * math.pi * self.breite / abs(self.phase)
        return {"vorschub": hub, "axialteilung": hub / self.z, "hand": "rechts" if self.phase > 0 else "links"}

    def zeilen(self):
        quelle = tr("Stirnschnitte")
        zeilen = [(tr("Art"), tr("Konisches Zahnprofil") if self.art == "konisch" else tr("Schraubprofil"), quelle),
                  (tr("Axiale Messstrecke"), f"{self.breite:.3f} mm", quelle)]
        d = self._werte()
        if self.art == "konisch":
            spur, versatz = tr("nicht bestimmbar"), tr("nicht bestimmbar")
            if self.phase is not None:
                spur = tr("gerade") if abs(self.phase) * self.z < .08 else tr("mit Umfangsversatz")
                versatz = f"{math.degrees(self.phase):+.2f}°"
            return zeilen + [(tr("Zähnezahl z"), str(self.z), quelle),
                             (tr("Kopfkegel-Halbwinkel"), f"{d['kopfkegelwinkel']:.2f}°", quelle),
                             (tr("Fußkegel-Halbwinkel"), f"{d['fusskegelwinkel']:.2f}°", quelle),
                             (tr("Zahnspur"), spur, quelle),
                             (tr("Zahnspurversatz"), versatz, quelle),
                             (tr("Teilkegel und Herstellverfahren"), tr("nicht bestimmbar"), tr("Einzelteil"))]
        return zeilen + [(tr("Gangzahl"), str(self.z), quelle),
                         (tr("Vorschub je Umdrehung"), f"{d['vorschub']:.3f} mm", quelle),
                         (tr("Axialteilung"), f"{d['axialteilung']:.3f} mm", quelle),
                         (tr("Steigungsrichtung"), tr("rechtssteigend") if self.phase > 0 else tr("linkssteigend"), quelle),
                         (tr("Schnecke oder Gewinde"), tr("nicht bestimmbar"), tr("Einzelteil"))]


def _zahnspur(netz, schnitte, z):
    """Versetzte Zwischenschnitte pruefen die Phasenentfaltung; wechselnde Drehrichtung bleibt unbestimmt."""
    from .verzahnung import _verzahnt
    phasen = -np.unwrap(np.angle([t[3] for _, t in schnitte]))
    delta = np.diff(phasen)
    if np.max(abs(delta)) > .8 * math.pi:
        return None
    for (a, t), (b, _), dp in zip(schnitte, schnitte[1:], delta):
        pos = a + (b - a) * .367
        probe = _verzahnt(netz, pos)
        if probe is None or probe[2] != z or probe[4]:
            return None
        abweichung = np.angle(probe[3] / t[3] * np.exp(1j * dp * .367))
        if abs(abweichung) > .12:
            return None
    if max(phasen) - min(phasen) >= .08 and np.any(delta < -.04) and np.any(delta > .04):
        return None
    return float((phasen[-1] - phasen[0]) / z)


@dataclass
class Taillenrad:
    teil: str
    z: int
    punkt: np.ndarray  # Mittelpunkt des engsten gemessenen Zahnkopfschnitts
    richtung: np.ndarray
    breite: float
    kopf: float
    fuss: float
    aufweitung: float
    spursteigung: float
    koerper: str | None = None
    koerper_id: object | None = field(default=None, repr=False, compare=False)

    def zeilen(self):
        quelle = tr("Stirnschnitte")
        return [(tr("Art"), tr("Tailliertes Zahnrad"), quelle), (tr("Zähnezahl z"), str(self.z), quelle),
                (tr("Kehlkopfdurchmesser"), f"{2 * self.kopf:.3f} mm", quelle),
                (tr("Radiale Aufweitung zu beiden Seiten"), f"{self.aufweitung:.3f} mm", quelle)]

    def als_dict(self):
        return {"teil": self.teil, "koerper": self.koerper, "art": "tailliert", "z": self.z, "kehlkopfdurchmesser": 2 * self.kopf,
                "kehlfussdurchmesser": 2 * self.fuss, "aufweitung_beidseits": self.aufweitung,
                "messlaenge": self.breite, "spursteigung_rad_mm": self.spursteigung,
                "kehlachse": {"punkt": self.punkt.tolist(), "richtung": self.richtung.tolist()}}


def _taillenrad(teil, punkt, n, netz, schnitte, s, r, h, z):
    """Konkave Kopf- und Fusslinie mit gemeinsamer Kehle, beidseits durch mehrere Messstellen belegt."""
    from .verzahnung import _verzahnt
    i = int(r[:, 0].argmin())
    if i < 2 or i > len(s) - 3 or abs(i - int(r[:, 1].argmin())) > 1:
        return None
    hub = np.minimum(r[0], r[-1]) - r[i]
    if min(hub) < max(.1 * h, .005 * r.mean()):
        return None
    if np.max(np.diff(r[:i+1], axis=0)) > .03 * h or np.min(np.diff(r[i:], axis=0)) < -.03 * h:
        return None
    # Lokale Scheitelinterpolation, danach die Kehle tatsaechlich schneiden.
    ds = s[i-1:i+2] - s[i]
    a, b, _ = np.polyfit(ds, r[i-1:i+2, 0], 2)
    if a <= 0:
        return None
    mitte = s[i] + np.clip(-b / (2 * a), ds[0], ds[-1])
    probe = _verzahnt(netz, mitte)
    if probe is None or probe[2] != z or probe[4]:
        return None
    winkel = _zahnspur(netz, schnitte[i-1:i+2], z)
    if winkel is None:
        return None
    return Taillenrad(teil, z, punkt + mitte * n, n, float(s[-1] - s[0]), float(probe[1].max()),
                      float(probe[1].min()), float(hub[0]), winkel / (ds[-1] - ds[0]))


def _stirnende(netz, ort, richtung, z, kopf, fuss, breite):
    """Stirnschnitt und ebene Abschlussfacetten muessen das Zahnende rundum bestaetigen."""
    from .verzahnung import _verzahnt
    eps = max(1e-8, netz.r_max * 2e-6)
    probe = _verzahnt(netz, ort + richtung * min(breite / 100, 3 * eps))
    if probe is None or probe[2] != z or probe[4]:
        return False
    hoehe = kopf - fuss
    if max(abs(probe[1].max() - kopf), abs(probe[1].min() - fuss)) > .05 * hoehe:
        return False
    eben = ((abs(netz.a[:, 2] - ort) <= eps) & (abs(netz.b[:, 2] - ort) <= eps) &
            (abs(netz.c[:, 2] - ort) <= eps))
    xy = np.vstack((netz.a[eben, :2], netz.b[eben, :2], netz.c[eben, :2]))
    spitzen = xy[abs(np.hypot(*xy.T) - kopf) <= .05 * hoehe]
    if len(spitzen) < z:
        return False
    winkel = np.sort(np.arctan2(spitzen[:, 1], spitzen[:, 0]))
    return np.diff(winkel, append=winkel[0] + 2 * math.pi).max() <= 1.15 * (2 * math.pi / z)


def zahnkoerper(teil, punkt, richtung, netz, schnitte, band):
    """Kopf- und Fussradius ueber den zusammenhaengenden Zahnbereich auf Taille oder Konizitaet pruefen."""
    if len(schnitte) < 5:
        return None
    s = np.array([pos for pos, _ in schnitte])
    z = schnitte[0][1][2]
    if np.diff(s).max() > 1.6 * np.median(np.diff(s)) or any(t[2] != z or t[4] for _, t in schnitte):
        return None
    r = np.array([[t[1].max(), t[1].min()] for _, t in schnitte])
    h = (r[:, 0] - r[:, 1]).mean()
    # Echte Luecken reichen unter die Sehne benachbarter Zahnkoepfe; ein konischer Vielkant faellt weg.
    if np.any(r[:, 1] >= r[:, 0] * math.cos(math.pi / z) - .01 * h):
        return None
    taille = _taillenrad(teil, punkt, richtung, netz, schnitte, s, r, h, z)
    if taille is not None:
        return taille
    steigung, start = np.polyfit(s - s[0], r, 1)
    breit = float(s[-1] - s[0])
    if steigung[0] * steigung[1] <= 0 or min(abs(steigung)) * breit < max(.4 * h, .02 * r.mean()):
        return None
    if np.max(abs(r - (start + np.outer(s - s[0], steigung)))) > .05 * h:
        return None
    ende = start + steigung * breit
    weg = _zahnspur(netz, schnitte, z)
    unten, oben = band
    grenzen = None
    if all(_stirnende(netz, ort, vorzeichen, z, *(start + (ort - s[0]) * steigung), oben - unten)
           for ort, vorzeichen in ((unten, 1), (oben, -1))):
        grenzen = ((s[-1] - oben, s[-1] - unten) if steigung[0] < 0 else
                   (unten - s[0], oben - s[0]))
    if steigung[0] < 0:
        start, ende = ende, start
        punkt, richtung = punkt + s[-1] * richtung, -richtung
    else:
        punkt = punkt + s[0] * richtung
    return Sonderprofil(teil, "konisch", z, punkt, richtung, breit, (float(start[0]), float(ende[0])),
                        (float(start[1]), float(ende[1])), weg, bandgrenzen=grenzen)


def _schraubschnitt(netz, s):
    from .verzahnung import _r_theta
    konturen = netz.konturen(s)
    if not konturen:
        return None
    q = max(konturen, key=lambda k: np.hypot(*k.T).max())
    winkel = np.sort(np.arctan2(q[:, 1], q[:, 0]))
    if np.diff(winkel, append=winkel[0] + 2 * math.pi).max() > .1:
        return None
    _, r = _r_theta(q)
    if np.ptp(r) < .025 * r.mean():
        return None
    f = np.fft.rfft(r - r.mean())
    leistung = np.abs(f[1:]) ** 2
    z = int(np.argmax(leistung)) + 1
    if z > 4 or leistung[z - 1::z].sum() < .93 * leistung.sum():
        return None
    # Geometrisches Merkmal einer Profilnut: ein Teil der Kontur liegt innerhalb ihrer konvexen Huelle.
    from scipy.spatial import ConvexHull
    ecken = q[ConvexHull(q).vertices]
    huelle = _r_theta_huelle(ecken, len(r))
    if np.max(huelle - r) < .01 * np.ptp(r):
        return None
    return z, f[z], float(r.max()), float(r.min())


def _r_theta_huelle(q, n):
    """Radien des konvexen Polygons. Exakter Schnitt der Geraden zwischen zwei benachbarten Eckrichtungen."""
    th = np.arctan2(q[:, 1], q[:, 0])
    reihe = np.argsort(th)
    th, q = th[reihe], q[reihe]
    raster = np.linspace(-np.pi, np.pi, n, endpoint=False)
    j = np.searchsorted(th, raster) % len(th)
    a, b = q[j - 1], q[j]
    delta = b - a
    return (a[:, 0] * delta[:, 1] - a[:, 1] * delta[:, 0]) / (
        np.cos(raster) * delta[:, 1] - np.sin(raster) * delta[:, 0])


def schraube(teil, punkt, richtung, netz):
    """Gangzahl und konstante Steigung der umlaufenden Nut, nur bei stabiler Form und axialer Wiederholung."""
    lo = min(p[:, 2].min() for p in (netz.a, netz.b, netz.c))
    hi = max(p[:, 2].max() for p in (netz.a, netz.b, netz.c))
    s = np.linspace(lo, hi, 18)[1:-1]
    # Ein versetzter Schnitt unterscheidet aliasierte Steigungen, die auf einem gleichmaessigen Raster gleich sind.
    s[::2] += (s[1] - s[0]) * .227
    # Jeder zusammenhaengende Sechserblock trifft mindestens eine Vorprobe. Fremdteile frueh ausscheiden.
    vorproben = {i: _schraubschnitt(netz, s[i]) for i in (4, 9, 14)}
    if all(t is None for t in vorproben.values()):
        return None
    schnitte = [vorproben[i] if i in vorproben else _schraubschnitt(netz, x) for i, x in enumerate(s)]
    ind = np.array([i for i, t in enumerate(schnitte) if t is not None])
    if len(ind) < 6 or np.diff(ind).max() > 1:
        return None
    s = s[ind]
    daten = [schnitte[i] for i in ind]
    z = daten[0][0]
    if any(t[0] != z for t in daten):
        return None
    r = np.array([t[2:] for t in daten])
    h = (r[:, 0] - r[:, 1]).mean()
    if np.max(np.ptp(r, axis=0)) > .1 * h:
        return None
    # Nahe der Mitte die lokale Drehung bestimmen. Auch mehr als eine Periode zwischen den weiten Schnitten aufloesen.
    i = len(s) // 2
    ds = (s[-1] - s[0]) / 601
    probe = _schraubschnitt(netz, s[i] + ds)
    if probe is None or probe[0] != z:
        return None
    ph = np.angle([t[1] / daten[i][1] for t in daten])
    rate = np.angle(probe[1] / daten[i][1]) / ds
    ph += 2 * np.pi * np.rint((rate * (s - s[i]) - ph) / (2 * np.pi))
    fit = np.polyfit(s - s[i], ph, 1)
    if np.max(abs(ph - np.polyval(fit, s - s[i]))) > .12:
        return None
    breite = float(s[-1] - s[0])
    weg = float(-fit[0] * breite / z)
    if abs(weg) * z < 2 * math.pi:
        return None
    kopf, fuss = map(float, r.mean(axis=0))
    return Sonderprofil(teil, "schraube", z, punkt + s[0] * richtung, richtung, breite,
                        (kopf, kopf), (fuss, fuss), weg)


@dataclass
class Teilkegelband:
    innen: float  # Laengen auf der Teilkegel-Mantellinie ab Kegelspitze
    aussen: float
    modul_aussen: float
    modul_mitte: float

    @property
    def breite(self):
        return self.aussen - self.innen

    def als_dict(self):
        return {"kegellaenge_innen": self.innen, "kegellaenge_aussen": self.aussen,
                "zahnbreite": self.breite, "b_durch_re": self.breite / self.aussen,
                "stirnmodul_aussen": self.modul_aussen, "stirnmodul_mitte": self.modul_mitte}


@dataclass
class Kegelpaar:
    a: Sonderprofil
    b: Sonderprofil
    achswinkel: float
    teil_a: float
    teil_b: float
    baender: tuple[Teilkegelband | None, Teilkegelband | None] = (None, None)

    @property
    def gemeinsame_breite(self):
        a, b = self.baender
        if a is not None and b is not None:
            return max(0., min(a.aussen, b.aussen) - max(a.innen, b.innen))
        return None

    def zeilen(self):
        zeilen = [(tr("Zuordnung"), tr("Mögliches äußeres Kegelradpaar")),
                  (tr("Achswinkel"), f"{self.achswinkel:.2f}°"),
                  (tr("Zähnezahlverhältnis z₂/z₁"), f"{self.b.z / self.a.z:.4g}"),
                  (tr("Teilkegel-Halbwinkel δ₁ / δ₂"), f"{self.teil_a:.2f}° / {self.teil_b:.2f}°")]
        daten = [band.als_dict() if band else None for band in self.baender]
        for beschriftung, feld in ((tr("Äußere Kegellänge Rₑ (mm)"), "kegellaenge_aussen"),
                                   (tr("Zahnbreite am Teilkegel (mm)"), "zahnbreite"),
                                   (tr("Breitenverhältnis b/Rₑ"), "b_durch_re"),
                                   (tr("Äußerer Stirnmodul (mm)"), "stirnmodul_aussen"),
                                   (tr("Mittlerer Stirnmodul (mm)"), "stirnmodul_mitte")):
            werte = [f"{band[feld]:.4f}" if band else tr("nicht bestimmbar") for band in daten]
            zeilen.append((beschriftung + " 1 / 2", " / ".join(werte)))
        b = self.gemeinsame_breite
        zeilen.append((tr("Gemeinsame Zahnbreite am Teilkegel (mm)"),
                       f"{b:.4f}" if b is not None else tr("nicht bestimmbar")))
        return zeilen

    def als_dict(self):
        return {"teile": [self.a.teil, self.b.teil], "achs_winkel": self.achswinkel,
                "z2_durch_z1": self.b.z / self.a.z, "teilwinkel": [self.teil_a, self.teil_b],
                "teilkegelbaender": [band.als_dict() if band else None for band in self.baender],
                "gemeinsame_zahnbreite": self.gemeinsame_breite}


def _teilkegelband(rad, delta, spitze):
    """Modul aus Teilkreisdurchmesser und Zaehnezahl an bestaetigten Stirnenden."""
    if rad.bandgrenzen is None:
        return None
    pos = np.asarray(rad.bandgrenzen)
    radius = (pos - spitze) * math.tan(delta)
    kopf = rad.kopf[0] + pos * (rad.kopf[1] - rad.kopf[0]) / rad.breite
    fuss = rad.fuss[0] + pos * (rad.fuss[1] - rad.fuss[0]) / rad.breite
    if radius[0] <= 0 or np.any(radius < fuss) or np.any(radius > kopf):
        return None
    innen, aussen = (pos - spitze) / math.cos(delta)
    return Teilkegelband(float(innen), float(aussen), float(2 * radius[1] / rad.z),
                         float((radius[0] + radius[1]) / rad.z))


def _kegelpaar(a, b):
    # Aeussere Schnittachsenraeder: delta1 + delta2 = Sigma, sin(delta2)/sin(delta1) = z2/z1
    # Quelle: KHK, Bevel Gears, Pitch Angles of Bevel Gears (M. Kubota, Haguruma Nyumon, Abb. 8.1).
    cos = float(np.clip(a.richtung @ b.richtung, -1, 1))
    if abs(cos) > .999:
        return None
    achswinkel = math.acos(cos)
    q = b.punkt - a.punkt
    sa, sb = np.linalg.lstsq(np.column_stack([a.richtung, -b.richtung]), q, rcond=None)[0]
    differenz = a.punkt + sa * a.richtung - b.punkt - sb * b.richtung
    if np.linalg.norm(differenz) > max(.001, 1e-4 * min(a.kopf[0], b.kopf[0])):
        return None
    da = math.atan2(math.sin(achswinkel), b.z / a.z + cos)
    db = achswinkel - da
    if not (0 < da < math.pi / 2 and 0 < db < math.pi / 2):
        return None
    bereiche, baender = [], []
    for rad, delta, s in ((a, da, sa), (b, db, sb)):
        axial = np.array([-s, rad.breite - s])
        soll = axial * math.tan(delta)
        if not (np.all(soll >= rad.fuss) and np.all(soll <= rad.kopf)):
            return None
        band = _teilkegelband(rad, delta, s)
        bereiche.append((band.innen, band.aussen) if band else axial / math.cos(delta))
        baender.append(band)
    if min(w[1] for w in bereiche) - max(w[0] for w in bereiche) <= 1e-7:
        return None
    return Kegelpaar(a, b, math.degrees(achswinkel), math.degrees(da), math.degrees(db), tuple(baender))


def kegelpaar_kandidaten(liste):
    """Nur Schnittachsen, deren theoretische Teilkegel im gemessenen Zahnband beider Teile liegen."""
    kegelprofile = [p for p in liste if isinstance(p, Sonderprofil) and p.art == "konisch"]
    return [paar for i, a in enumerate(kegelprofile) for b in kegelprofile[i + 1:]
            if (paar := _kegelpaar(a, b)) is not None]


@dataclass
class Schneckenpaar:
    a: Sonderprofil
    b: Taillenrad
    achsabstand: float
    achswinkel: float

    def zeilen(self):
        return [(tr("Zuordnung"), tr("Mögliches Schneckenradpaar")),
                (tr("Achswinkel"), f"{self.achswinkel:.2f}°"),
                (tr("Achsabstand"), f"{self.achsabstand:.3f} mm"),
                (tr("Zähnezahl / Gangzahl"), f"{self.b.z / self.a.z:.4g}")]

    def als_dict(self):
        return {"teile": [self.a.teil, self.b.teil], "achsabstand": self.achsabstand,
                "achswinkel": self.achswinkel, "zaehne_durch_gaenge": self.b.z / self.a.z}


def schneckenpaar_kandidaten(liste):
    """Rechtwinklige Paarung aus Schraubnut und tailliertem Rad: Kehllage, Teilung, Radiusbaender und Zahnspur."""
    schrauben = [v for v in liste if isinstance(v, Sonderprofil) and v.art == "schraube"]
    raeder = [v for v in liste if isinstance(v, Taillenrad)]
    paare = []
    for w in schrauben:
        for rad in raeder:
            cos = float(w.richtung @ rad.richtung)
            if abs(cos) > math.sin(math.radians(.5)):
                continue
            q = rad.punkt - w.punkt
            sw, sr = np.linalg.lstsq(np.column_stack([w.richtung, -rad.richtung]), q, rcond=None)[0]
            if not 0 < sw < w.breite or abs(sr) > max(.02, .06 * rad.breite):
                continue
            abstand = float(np.linalg.norm(w.punkt + sw * w.richtung - rad.punkt - sr * rad.richtung))
            # Axialteilung der Schnecke = Umfangsteilung des Rads im Achskreuz (KHK, Worm Gears).
            d = w._werte()
            r2 = d["axialteilung"] * rad.z / (2 * math.pi)
            r1 = abstand - r2
            if not (rad.fuss < r2 < rad.kopf and w.fuss[0] < r1 < w.kopf[0]):
                continue
            gamma = math.atan2(d["vorschub"], 2 * math.pi * r1)
            beta = math.atan(r2 * rad.spursteigung)
            if beta * w.phase <= 0 or abs(abs(beta) - gamma) > math.radians(2):
                continue
            paare.append(Schneckenpaar(w, rad, abstand, math.degrees(math.acos(abs(cos)))))
    return paare
