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
from . import gemeinsamer_bezug, projektionszone
from . import merkmal_material as mm
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
    material: mm.Materialstreuung | None = None

    def ziehe(self, rng, proben):
        if self.material is not None:
            return self.material.ziehe(rng, proben)
        mittel, sigma = (self.oben + self.unten) / 2, (self.oben - self.unten) / 6
        return np.clip(rng.normal(mittel, sigma, proben), self.unten, self.oben)


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


def _zylindrisch(d, laenge, kraft, moment, lagezonen, neigung):
    """Die radiale Bewegung beider Achsenden liegt je in einer Kreisscheibe. Nur Kippen: Mitte fest."""
    if laenge <= 1e-9:
        return None
    rad = kraft - d * (kraft @ d)
    winkel = np.cross(moment, d) / laenge
    h = mm.achsenhub(rad, winkel, lagezonen, neigung)
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
    refs = sorted(getattr(p, "bezuege", ()), key=lambda b: b.stelle)
    if len({b.stelle for b in refs}) != len(refs) or any(b.stelle < 1 for b in refs):
        return None
    return tuple("-".join(sorted(name.strip() for name in b.name.split("-")))
                 for b in refs)


def _angaben(pmi, art, einzelachse):
    lage, neigung, gueltig, fehlt = [], [], [], []
    for p in pmi:
        mods = getattr(p, "modifikatoren", ())
        zone = getattr(p, "zone", "")
        mat = getattr(p, "material", "")
        matmod = {"M": "Maximum_Material_Requirement", "L": "Least_Material_Requirement"}.get(mat)
        if getattr(p, "bearbeitet", False) and "material" in (getattr(p, "original", None) or {}):
            mods = [m for m in mods if m not in ("Maximum_Material_Requirement", "Least_Material_Requirement")]
        deckel = getattr(p, "maximum_toleranz", None)
        if (p.wert is None or not np.isfinite(p.wert) or p.wert < 0 or (not p.wert and not mat) or
                not getattr(p, "semantisch", True) or not einzelachse(p) or
                (mat and (not matmod or art != "achse" or p.typ not in {"Position"} | ORIENTIERUNG)) or
                (deckel is not None and (not mat or not np.isfinite(deckel) or deckel <= p.wert)) or
                any(b.modifikatoren or getattr(b, "element_modifikatoren", {}) for b in getattr(p, "bezuege", ())) or
                any(x not in ("Diameter", matmod) and not x.startswith("UZ ") for x in mods) or
                zone not in ("", "Diameter", "Projected") or (zone == "Projected" and art != "achse")):
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
                elif p.art == "bezug" and p.typ == "Datum" and getattr(p, "semantisch", True):
                    self.datum[p.name].add(idx)
                elif p.art == "mass" and p.typ in ("Size_Diameter", "Size_Radius"):
                    self.groessen[idx].append(p)
        self.zonen, self.hinweise = {}, []
        self.bezugsmodelle = defaultdict(set)
        self.kraefte = defaultdict(lambda: np.zeros(6))
        self.masse, self.schluessel, self.durchmesserfaktoren = {}, {}, {}

    def _form(self, teil, idx):
        key = (teil, idx)
        if key not in self.formen:
            self.formen[key] = self.form_fuer(teil, idx) if self.form_fuer else None
        return self.formen[key]

    def _unvollstaendig(self, teil, idx, text):
        meldung = tr("Teil {}, Fläche {}: {} nicht vollständig ausgewertet.").format(teil, idx, text)
        if meldung not in self.hinweise:
            self.hinweise.append(meldung)

    def _bezugsfach(self, teil, name, lage, belegt):
        elemente = []
        for buchstabe in name.split("-"):
            if not buchstabe.strip():
                return None
            kandidaten = [(i, f) for i in self.datum[buchstabe.strip()] if (f := self._form(teil, i)) is not None]
            if len(kandidaten) != 1:
                return None
            i, f = kandidaten[0]
            g = _merkmal(f, lage)
            if g is None or i in belegt or any(f.IsSame(andere) for _, andere, _ in elemente):
                return None
            belegt.add(i)
            elemente.append((i, f, g))
        if len(elemente) == 1:
            i, _, g = elemente[0]
            return g, {i: np.eye(6)}
        return gemeinsamer_bezug.aufloesen(elemente, self.punkt, lage)

    def _bezugssystem(self, teil, idx, refs):
        merkmale, abbildungen, belegt = [], {}, set()
        for rang, name in enumerate(refs):
            fach = self._bezugsfach(teil, name, self.bg.lage(teil), belegt)
            if fach is None:
                self._unvollstaendig(teil, idx, tr("Bezug {}").format(name))
                return [], {}
            merkmal, abbildungen[rang] = fach
            merkmale.append((rang, merkmal))
            if len(abbildungen[rang]) > 1:
                text = (tr("Gemeinsamer Bezug {}: Achse aus Sitzmitten") if merkmal[0] == "achse" else
                        tr("Gemeinsamer Bezug {}: flächengewichtete Ausgleichsebene"))
                self.bezugsmodelle[teil, idx].add(text.format(name))
        return merkmale, abbildungen

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
        def form_fuer(i):
            return self._form(teil, i)

        def einzelachse(p):
            return len(p.flaechen) == 1 or projektionszone.einzelachse(p, form, form_fuer)

        lage, neigung, angaben, fehlt = _angaben(self.pmi[idx], art, einzelachse)
        if fehlt:
            self._unvollstaendig(teil, idx, ", ".join(p.wert_text() for p in fehlt))
        if not angaben:
            return
        systeme = {_bezuege(p) for p in angaben}
        if None in systeme:
            self._unvollstaendig(teil, idx, tr("Rangfolge der Bezüge"))
            return
        if len(systeme) != 1:
            self._unvollstaendig(teil, idx, tr("Verschiedene Bezugssysteme"))
            return
        formen = {frozenset(p.flaechen) for p in angaben}
        if len(formen) != 1:
            self._unvollstaendig(teil, idx, tr("Verschiedene tolerierte Flächen"))
            return
        gruppe = next(iter(formen))
        if any((teil, i) in self.verbunden for i in gruppe):
            return
        key = (teil, min(gruppe))
        merkmal, hinweis = projektionszone.messmerkmal(angaben, form, merkmal, self.bg.lage(teil), form_fuer)
        if hinweis:
            self._unvollstaendig(teil, idx, hinweis)
            return
        art, o, d, _ = merkmal
        if any(getattr(p, "material", "") for p in angaben):
            masse = {id(p): p for i in gruppe for p in self.groessen[i]}
            mass = mm.zylindermass(form, masse.values(), einzelachse)
            if mass is None:
                self._unvollstaendig(teil, idx, tr("Größenmaße für die Materialbedingung"))
                return
            self.masse[key] = mass
        self.schluessel.update({(teil, i): key for i in gruppe})
        self.zonen[key] = (merkmal, lage, neigung, angaben)
        self.kraefte[key] += kraft
        if not lage:
            anteil = kraft[3:] @ d if art == "ebene" else np.linalg.norm(np.cross(kraft[3:], d))
            if abs(anteil) > 1e-9:
                self._unvollstaendig(teil, idx, tr("Lage des nur richtungstolerierten Merkmals"))
        refs = next(iter(systeme))
        if not refs:
            return
        merkmale, abbildungen = self._bezugssystem(teil, key[1], refs)
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
        for rang, k in anteile.items():
            for i, abbildung in abbildungen[rang].items():
                self.verfolge(teil, i, k @ abbildung, (*besucht, idx))

    def groesse_am_punkt(self, teil, idx, kraft):
        """Groessentoleranz eines Zylinders am angeklickten Mantelpunkt; die Achse bleibt dabei ortsfest."""
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.GeomAbs import GeomAbs_Cylinder
        from OCC.Core.TopoDS import topods
        key = self.schluessel.get((teil, idx), (teil, idx))
        if not self.groessen[idx] and key not in self.masse:
            return []
        if (teil, idx) in self.verbunden:
            self._unvollstaendig(teil, idx, tr("Größenstreuung am Kontaktpunkt"))
            return []
        form = self._form(teil, idx)
        if form is None or BRepAdaptor_Surface(topods.Face(form)).GetType() != GeomAbs_Cylinder:
            return []
        _, o, d, laenge = _merkmal(form, self.bg.lage(teil))
        radial = self.punkt - o
        axial = radial @ d
        radial -= d * axial
        radius = BRepAdaptor_Surface(topods.Face(form)).Cylinder().Radius()
        if abs(axial) > laenge / 2 + 1e-6 or not np.isclose(np.linalg.norm(radial), radius, atol=1e-6, rtol=1e-7):
            return []
        faktor = float(radial @ kraft) / np.linalg.norm(radial)
        if key in self.masse:
            self.durchmesserfaktoren[key] = faktor / 2
            return []
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
            material = None
            if art == "ebene":
                grenzen = _planar(self._form(teil, idx), self.bg.lage(teil), o, d, k[3:], moment, lage, neigung)
            elif (teil, idx) in self.masse:
                material = self._materialstreuung(teil, idx, d, laenge, k[3:], moment, angaben)
                grenzen = material.grenzen()
            else:
                grenzen = _zylindrisch(d, laenge, k[3:], moment, lage, neigung)
            if grenzen is None:
                self._unvollstaendig(teil, idx, tr("Geometrie der Toleranzzone"))
            elif max(abs(w) for w in grenzen) > 1e-12:
                texte = [p.wert_text() for p in angaben] + sorted(self.bezugsmodelle[teil, idx])
                if material is not None:
                    mass = material.mass
                    texte.append(tr("Istmaß ⌀{:.4g} bis {:.4g} mm mit gekoppeltem Bonus").format(mass.klein, mass.gross))
                out.append(Anteil(teil, idx, *grenzen, ", ".join(texte), material))
        return out

    def _materialstreuung(self, teil, idx, d, laenge, kraft, moment, angaben):
        radial = kraft - d * (kraft @ d)
        winkel = np.cross(moment, d) / laenge
        zonen = [(p.wert, getattr(p, "material", ""), getattr(p, "maximum_toleranz", None),
                  p.typ in ORIENTIERUNG) for p in angaben]
        return mm.Materialstreuung(self.masse[teil, idx], self.durchmesserfaktoren.get((teil, idx), 0.),
                                   tuple(radial), tuple(winkel), zonen)
