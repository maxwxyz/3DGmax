"""Lineare Abweichung starrer Messmerkmale in der Messrichtung.

Eine ebene Flaeche hat einen Normalversatz und zwei Kippwinkel, eine gerade Achse
zwei radiale Versatze und zwei Kippwinkel. Die Zonengrenzen gelten ueber die
Ausdehnung des Merkmals. Freie Verschiebung einer Orientierungszone bleibt nominal.
Alle Torsoren beziehen sich auf denselben Messpunkt in Zusammenbaulage.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ..i18n import tr
from . import toleranzzone as tz
from .verbindung import ORT_TYPEN, _senkrechte

ORIENTIERUNG = {"Parallelism", "Perpendicularity", "Angularity"}


@dataclass
class Anteil:
    teil: int
    flaeche: int
    unten: float
    oben: float
    text: str


def _randpunkte(f, lage):
    """Gerade Kanten exakt; Punkte auf gekruemmten Raendern liefern eine konservative aeussere Torsorgrenze."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Line
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    kanten = TopExp_Explorer(f, TopAbs_EDGE)
    punkte = set()
    while kanten.More():
        k = BRepAdaptor_Curve(topods.Edge(kanten.Current()))
        zahl = 2 if k.GetType() == GeomAbs_Line else 65
        for t in np.linspace(k.FirstParameter(), k.LastParameter(), zahl):
            punkte.add(tuple(k.Value(t).Coord()))
        kanten.Next()
    if len(punkte) < 3:
        return None
    return np.asarray(sorted(punkte)) @ lage[:3, :3].T + lage[:3, 3]


def _planar(f, lage, zentrum, d, kraft, moment, lagezonen, neigung):
    from scipy.optimize import linprog
    punkte = _randpunkte(f, lage)
    if punkte is None:
        return None
    tangenten = np.asarray(_senkrechte(d)).T
    kippen = np.cross(punkte - zentrum, d) @ tangenten
    n = len(punkte)
    # s und zwei Kippwinkel; die Orientierungszone darf parallel verschoben werden (vierte Variable).
    a, b = [], []
    for unten, oben, schwimmend in [(*z, False) for z in lagezonen] + [
            (-w / 2, w / 2, True) for w in neigung]:
        z = np.column_stack((np.full(n, not schwimmend), kippen, np.full(n, schwimmend)))
        a.extend((z, -z))
        b.extend((np.full(n, oben), np.full(n, -unten)))
    ziel = np.r_[kraft @ d, moment @ tangenten, 0.]
    grenzen = [(None, None) if lagezonen else (0., 0.), (None, None), (None, None), (None, None)]
    werte = []
    for vorzeichen in (1., -1.):
        lp = linprog(vorzeichen * ziel, A_ub=np.vstack(a), b_ub=np.concatenate(b), bounds=grenzen, method="highs")
        if not lp.success:
            return None
        werte.append(float(ziel @ lp.x))
    return tuple(werte)


def _achsenden_maximum(a, b, summe, sehne):
    """Maximiere a*x + b*y fuer zwei Punkte im Einheitskreis mit Abstand <= sehne."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0 or sehne >= 2:
        return na + nb
    ua, ub = a / na, b / nb
    if np.linalg.norm(ua - ub) <= sehne:
        return na + nb

    ns = np.linalg.norm(summe)
    if ns == 0:
        return sehne * na
    # Nur ein Ende auf dem Kreis: y = Richtung(summe), x = y + sehne * ua (bzw. umgekehrt).
    richtung = summe / ns
    for u, n in ((ua, na), (ub, nb)):
        if richtung @ u <= -sehne / 2:
            return ns + sehne * n

    # Beide Enden auf dem Kreis, ihr Abstand ist aktiv. Die halbe Sehne liegt
    # senkrecht zur Mitte. Beide Drehsinne pruefen und gemeinsam optimal drehen.
    sinus = sehne / 2
    cosinus = np.sqrt((1 - sinus) * (1 + sinus))
    differenz = a - b
    return np.sqrt((cosinus * ns)**2 + (sinus * np.linalg.norm(differenz))**2
                   + 2 * cosinus * sinus * np.linalg.norm(np.cross(summe, differenz)))


def _zylindrisch(d, laenge, kraft, moment, lagezonen, neigung):
    """Die radiale Bewegung beider Achsenden liegt je in einer Kreisscheibe. Nur Kippen: Mitte fest."""
    if laenge <= 1e-9:
        return None
    rad = kraft - d * (kraft @ d)
    winkel = np.cross(moment, d) / laenge
    if not lagezonen:
        h = min(neigung) * np.linalg.norm(winkel)
    else:
        h = min(o for _, o in lagezonen)
        if h == 0:
            return 0., 0.
        a, b = rad / 2 - winkel, rad / 2 + winkel
        sehne = min(neigung) / h if neigung else 2.
        h *= _achsenden_maximum(a, b, rad, sehne)
    return -h, h


def _merkmal(f, lage):
    from .baugruppe_mass import ebene
    pl = ebene(f, lage)
    if pl is not None:
        return "ebene", *pl, 0.
    a = tz._achse([f])
    if a is not None:
        o, d, laenge = a[:3]
        return "achse", lage[:3, :3] @ (o + d * laenge / 2) + lage[:3, 3], lage[:3, :3] @ d, laenge
    return None


def _rahmenanteile(merkmale, punkt, empfindlichkeit):
    """Bezugssystem in Rangfolge aufbauen: Richtung vor Ort, nur noch offene Freiheitsgrade sperren."""
    frei = np.eye(6)
    abbildungen = {}
    for idx, (art, o, d, _) in merkmale:
        rang = np.asarray(_senkrechte(d))
        richtungen = d[None, :] if art == "ebene" else rang
        saetze = [np.c_[rang, np.zeros_like(rang)],
                  np.c_[np.cross(o - punkt, richtungen), richtungen]]
        abbildungen[idx] = np.zeros((6, 6))
        for zeilen in saetze:
            offen = zeilen @ frei
            u, s, vt = np.linalg.svd(offen, full_matrices=False)
            wirksam = s > 1e-9 * max(1., np.linalg.norm(zeilen))
            if not wirksam.any():
                continue
            inv = (vt[wirksam].T / s[wirksam]) @ u[:, wirksam].T
            korr = inv @ zeilen
            for key in abbildungen:
                abbildungen[key] -= korr @ abbildungen[key]
            abbildungen[idx] += korr
            frei -= vt[wirksam].T @ vt[wirksam]
    return {i: empfindlichkeit @ a for i, a in abbildungen.items()}, np.linalg.norm(empfindlichkeit @ frei)


def _bezuege(p):
    return tuple(b.name for b in sorted(getattr(p, "bezuege", ()), key=lambda b: b.stelle))


def _angaben(pmi, art):
    lage, neigung, gueltig, fehlt = [], [], [], []
    for p in pmi:
        mods = getattr(p, "modifikatoren", ())
        zone = getattr(p, "zone", "")
        if (p.wert is None or p.wert <= 0 or not getattr(p, "semantisch", True) or len(p.flaechen) != 1 or
                getattr(p, "material", "") or any(b.modifikatoren for b in getattr(p, "bezuege", ())) or
                any(x not in ("Diameter",) and not x.startswith("UZ ") for x in mods) or zone not in ("", "Diameter")):
            fehlt.append(p)
        elif p.typ not in ORT_TYPEN | ORIENTIERUNG or (hasattr(p, "bezuege") and not p.bezuege):
            fehlt.append(p)  # Form allein bindet das starre Merkmal nicht an ein Bezugssystem.
        elif art == "achse" and not (p.typ in {"Position", "Coaxiality", "Concentricity"} | ORIENTIERUNG and
                                     (zone == "Diameter" or "Diameter" in mods) and not any(x.startswith("UZ ") for x in mods)):
            fehlt.append(p)
        elif art == "ebene" and (p.typ not in {"ProfileOfSurface", "Position"} | ORIENTIERUNG or
                                 "Diameter" in mods or zone == "Diameter"):
            fehlt.append(p)
        else:
            gueltig.append(p)
            if p.typ in ORIENTIERUNG:
                neigung.append(p.wert)
            else:
                gr = tz._grenzen_aussen_innen(p, p.wert)[::-1] if any(x.startswith("UZ ") for x in mods) else (
                    -p.wert / 2, p.wert / 2)
                lage.append(gr)
    return lage, neigung, gueltig, fehlt


class Messmerkmale:
    """Merkmale und Bezuege einer Messung, nach Teilinstanz aufgeloest."""

    def __init__(self, bg, m, fa, fb, pmi, punkt, form_fuer):
        self.bg, self.punkt, self.form_fuer = bg, punkt, form_fuer
        self.formen = {(m.teil_a, m.flaeche_a): fa, (m.teil_b, m.flaeche_b): fb}
        self.verbunden = set()
        for v in bg.verbindungen:
            keys = [(v.teil, v.flaeche), (v.gegen_teil, v.gegen_flaeche)]
            self.verbunden.update(keys)
            self.formen.update(zip(keys, bg.formen.get(v.nummer, ())))
        self.pmi, self.datum, self.groessen = defaultdict(list), defaultdict(set), defaultdict(list)
        for p in pmi:
            for idx in p.flaechen:
                if p.art == "toleranz":
                    self.pmi[idx].append(p)
                elif p.art == "bezug" and p.typ == "Datum":
                    self.datum[p.name].add(idx)
                elif p.art == "mass" and p.typ in ("Size_Diameter", "Size_Radius"):
                    self.groessen[idx].append(p)
        self.zonen, self.hinweise = {}, []
        self.kraefte = defaultdict(lambda: np.zeros(6))

    def _form(self, teil, idx):
        key = (teil, idx)
        if key not in self.formen:
            self.formen[key] = self.form_fuer(teil, idx) if self.form_fuer else None
        return self.formen[key]

    def _unvollstaendig(self, teil, idx, text):
        meldung = tr("Teil {}, Fläche {}: {} nicht vollständig ausgewertet.").format(teil, idx, text)
        if meldung not in self.hinweise:
            self.hinweise.append(meldung)

    def _bezugssystem(self, teil, idx, refs):
        merkmale = []
        for name in refs:
            kandidaten = [(i, f) for i in self.datum[name] if (f := self._form(teil, i)) is not None]
            if len(kandidaten) != 1:
                self._unvollstaendig(teil, idx, tr("Bezug {}").format(name))
                return []
            i, f = kandidaten[0]
            g = _merkmal(f, self.bg.lage(teil))
            if g is None or any(j == i for j, _ in merkmale):
                self._unvollstaendig(teil, idx, tr("Bezug {}").format(name))
                return []
            merkmale.append((i, g))
        return merkmale

    def verfolge(self, teil, idx, kraft, besucht=()):
        if (teil, idx) in self.verbunden or not self.pmi[idx] or np.linalg.norm(kraft) < 1e-10:
            return
        if idx in besucht:
            self._unvollstaendig(teil, idx, tr("Zyklisches Bezugssystem"))
            return
        form = self._form(teil, idx)
        merkmal = _merkmal(form, self.bg.lage(teil)) if form is not None else None
        if merkmal is None:
            self._unvollstaendig(teil, idx, tr("Geometrie der Toleranzzone"))
            return
        art, o, d, _ = merkmal
        lage, neigung, angaben, fehlt = _angaben(self.pmi[idx], art)
        if fehlt:
            self._unvollstaendig(teil, idx, ", ".join(p.wert_text() for p in fehlt))
        if not angaben:
            return
        systeme = {_bezuege(p) for p in angaben}
        if len(systeme) != 1:
            self._unvollstaendig(teil, idx, tr("Verschiedene Bezugssysteme"))
            return
        self.zonen[teil, idx] = (merkmal, lage, neigung, angaben)
        self.kraefte[teil, idx] += kraft
        if not lage:
            anteil = kraft[3:] @ d if art == "ebene" else np.linalg.norm(np.cross(kraft[3:], d))
            if abs(anteil) > 1e-9:
                self._unvollstaendig(teil, idx, tr("Lage des nur richtungstolerierten Merkmals"))
        refs = next(iter(systeme))
        if not refs:
            return
        merkmale = self._bezugssystem(teil, idx, refs)
        if not merkmale:
            return
        # Nur die von der Zone gebundenen Bewegungen ihres zugeordneten Bezugsrahmens weitergeben.
        n = kraft[3:]
        moment = kraft[:3] + np.cross(self.punkt - o, n)
        moment -= d * (moment @ d)
        f = (d * (n @ d) if art == "ebene" else n - d * (n @ d)) if lage else np.zeros(3)
        ursprung = np.r_[moment - np.cross(self.punkt - o, f), f]
        anteile, rest = _rahmenanteile(merkmale, self.punkt, ursprung)
        if rest > 1e-7 * max(1., np.linalg.norm(ursprung)):
            self._unvollstaendig(teil, idx, tr("Offener Freiheitsgrad im Bezugssystem"))
        for i, k in anteile.items():
            self.verfolge(teil, i, k, (*besucht, idx))

    def groesse_am_punkt(self, teil, idx, kraft):
        """Groessentoleranz eines Zylinders am angeklickten Mantelpunkt; die Achse bleibt dabei ortsfest."""
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.GeomAbs import GeomAbs_Cylinder
        from OCC.Core.TopoDS import topods
        if not self.groessen[idx]:
            return []
        if (teil, idx) in self.verbunden:
            self._unvollstaendig(teil, idx, tr("Größenstreuung am Kontaktpunkt"))
            return []
        form = self._form(teil, idx)
        if form is None or BRepAdaptor_Surface(topods.Face(form)).GetType() != GeomAbs_Cylinder:
            return []
        _, o, d, _ = _merkmal(form, self.bg.lage(teil))
        radial = self.punkt - o
        radial -= d * (radial @ d)
        if np.linalg.norm(radial) < 1e-9:
            return []
        faktor = float(radial @ kraft) / np.linalg.norm(radial)
        grenzen, texte = [], []
        for p in self.groessen[idx]:
            oben, unten = p.abmasse()
            if oben is None and unten is None and not p.passung:
                continue
            if (oben is None or unten is None or not p.semantisch or p.modifikatoren or
                    len(p.flaechen) != 1 or unten > oben):
                self._unvollstaendig(teil, idx, p.wert_text())
                continue
            k = faktor / 2 if p.typ == "Size_Diameter" else faktor
            grenzen.append(sorted((k * unten, k * oben)))
            texte.append(p.wert_text())
        if not grenzen:
            return []
        u, o = max(g[0] for g in grenzen), min(g[1] for g in grenzen)
        if u > o:
            self._unvollstaendig(teil, idx, ", ".join(texte))
            return []
        return [Anteil(teil, idx, u, o, ", ".join(texte))] if u or o else []

    def beitraege(self):
        out = []
        for (teil, idx), (merkmal, lage, neigung, angaben) in self.zonen.items():
            art, o, d, laenge = merkmal
            k = self.kraefte[teil, idx]
            moment = k[:3] + np.cross(self.punkt - o, k[3:])
            if art == "ebene":
                grenzen = _planar(self._form(teil, idx), self.bg.lage(teil), o, d, k[3:], moment, lage, neigung)
            else:
                grenzen = _zylindrisch(d, laenge, k[3:], moment, lage, neigung)
            if grenzen is None:
                self._unvollstaendig(teil, idx, tr("Geometrie der Toleranzzone"))
            elif max(abs(w) for w in grenzen) > 1e-12:
                out.append(Anteil(teil, idx, *grenzen, ", ".join(p.wert_text() for p in angaben)))
        return out
