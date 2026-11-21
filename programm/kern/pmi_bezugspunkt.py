"""Punktbezugsstelle aus geteiltem Schriftkreis, Hinweislinie und Zielkreuz."""

from dataclasses import dataclass
from itertools import combinations
import re

import numpy as np
from scipy import ndimage


def _netzstriche(punkte, netz):
    """Mittellinien schmaler Rechtecke, auch wenn das STEP-Netz die Ecken dupliziert."""
    nach_diagonale = {}
    for dreieck in punkte[netz]:
        laengen = np.linalg.norm(np.roll(dreieck, -1, axis=0) - dreieck, axis=1)
        i = int(np.argmax(laengen))
        if not 0 < laengen.min() < .06 * laengen[i]:
            continue
        a, b, c = np.roll(dreieck, -i, axis=0)
        key = tuple(sorted((tuple(a), tuple(b))))
        d = nach_diagonale.pop(key, None)
        if d is None:
            nach_diagonale[key] = c
            continue
        if np.linalg.norm(a + b - c - d) > 1e-4 * laengen[i]:
            continue
        if np.linalg.norm(c - b) < np.linalg.norm(c - a):
            c, d = d, c
        yield np.array([(a+c)/2, (b+d)/2])


def _verbindungen(striche, start, laenge):
    """Bis zu drei zusammenhaengende Schaftsegmente bis zum Rand des Schriftkreises."""
    wege = [(start, frozenset())]
    besucht = set()
    for _ in range(3):
        neue = []
        for punkt, benutzt in wege:
            for i, s in enumerate(striche):
                if i in benutzt:
                    continue
                for ende in (0, 1):
                    if (i, ende) not in besucht and np.linalg.norm(s[ende] - punkt) < .005 * laenge:
                        besucht.add((i, ende))
                        ziel = s[1-ende]
                        weg = benutzt | {i}
                        neue.append((ziel, weg))
                        yield ziel, weg
        wege = neue


def _nummer(pfade, *, mit_flaechenmass=False):
    """Kennung unten lesen; beim Punktziel muss der obere Halbkreis leer sein."""
    from . import pmi_strichschrift as schrift
    maske = schrift._bild(pfade, (-1.1,-1.1,1.1,1.1), 64)
    if maske is None:
        return ""
    abstand = ndimage.distance_transform_edt(~maske)
    winkel = np.linspace(0, 2*np.pi, 96, endpoint=False)
    x = np.rint(2 + 64*(1.1 + np.cos(winkel))).astype(int)
    y = np.rint(2 + 64*(1.1 - np.sin(winkel))).astype(int)
    if np.max(abstand[y,x]) > 3.5:
        return ""
    glyphen = []
    for p, voll in pfade:
        if np.any(np.abs(p) > 1.06):
            continue
        if np.all(np.abs(np.linalg.norm(p,axis=1)-1) < .06) or np.max(abs(p[:,1])) < .025:
            continue
        if mit_flaechenmass and np.min(p[:,1]) > .015:
            continue
        if np.max(p[:,1]) >= -.015:
            return ""
        glyphen.append((p, voll))
    if not glyphen:
        return ""
    hoehe = np.ptp(np.vstack([p for p, _ in glyphen])[:,1])
    if not .13 < hoehe < .88:
        return ""
    namen = set()
    for pixel in (40, 50, 55, 80, 120):
        mask, _ = schrift._gesamtbild(glyphen, pixel/hoehe)
        if mask is not None and (text := schrift._normale_zeile(mask)):
            namen.add(text)
    if len(namen) == 1:
        name = namen.pop()
        if re.fullmatch(r"[A-Z]{1,2}[1-9][0-9]*", name):
            return name
    return ""


def grafischer_punkt(g):
    """Kennung und 3D-Kreuzmitte nur bei eindeutiger Verbindung mit einem Punktziel."""
    from . import pmi_strichschrift as schrift
    if not schrift._lesbar(g):
        return None
    striche = [l for l in g.linien if len(l) == 2]
    for p, t in g.dreiecke:
        striche.extend(_netzstriche(p, t))
    if not 4 <= len(striche) <= 150:
        return None
    punkte = np.vstack([*g.linien, *(p for p, _ in g.dreiecke)])
    ergebnis = {}
    for a, b in combinations(striche, 2):
        v, w = a[1]-a[0], b[1]-b[0]
        l, m = np.linalg.norm(v), np.linalg.norm(w)
        mitte = a.mean(axis=0)
        if (l <= 1e-8 or abs(l-m) > .05*l or np.linalg.norm(mitte-b.mean(axis=0)) > .01*l
                or abs(v@w) > .06*l*m):
            continue
        normal = np.cross(v,w)
        normal /= np.linalg.norm(normal)
        if np.ptp(punkte @ normal) > .005*l:
            continue
        kreuz = (mitte + b.mean(axis=0))/2
        for rand, weg in _verbindungen(striche, kreuz, l):
            for i, teiler in enumerate(striche):
                if i in weg or min(np.linalg.norm(teiler-rand,axis=1)) > .005*l:
                    continue
                achse = teiler[1]-teiler[0]
                radius = np.linalg.norm(achse)/2
                if radius < 1e-8 or abs(achse@normal) > .005*radius:
                    continue
                zentrum = teiler.mean(axis=0)
                if np.linalg.norm(zentrum-kreuz) <= 1.03*radius:
                    continue
                x = achse/(2*radius)
                y = np.cross(normal,x)
                if g.ebene is not None and abs(normal @ g.ebene[3]) < .999:
                    continue
                ebene = (zentrum,x,y,normal)
                pfade = [(p/radius,voll) for p,voll in schrift._pfade(g,ebene)]
                for sx, sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
                    if g.ebene is not None and (sx*x@g.ebene[1] < .98 or sy*y@g.ebene[2] < .98):
                        continue
                    name = _nummer([(p*[sx,sy],voll) for p,voll in pfade])
                    if name:
                        ergebnis[name,tuple(kreuz)] = (name,kreuz)
    return next(iter(ergebnis.values())) if len(ergebnis) == 1 else None


def kennung_im_kreis(g):
    """Untere Kennung bei Flaechenzielen mit Groessenangabe im oberen Halbkreis."""
    from . import pmi_strichschrift as schrift
    if g.ebene is None or not schrift._lesbar(g):
        return ""
    pfade = schrift._pfade(g, g.ebene)
    namen = set()
    for p, voll in pfade:
        if voll or len(p) != 2:
            continue
        dx, dy = p[1] - p[0]
        if abs(dx) < 1e-8 or abs(dy) > .005 * abs(dx):
            continue
        mitte, radius = p.mean(axis=0), abs(dx)/2
        if name := _nummer([((linie-mitte)/radius, f) for linie, f in pfade], mit_flaechenmass=True):
            namen.add(name)
    return namen.pop() if len(namen) == 1 else ""


def hat_kontakt(modell, flaechen, punkt):
    """Kreuz liegt innerhalb 1 Mikrometer auf der zugeordneten getrimmten Flaeche."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.gp import gp_Pnt
    if len(flaechen) != 1 or np.shape(punkt) != (3,) or not np.isfinite(punkt).all():
        return False
    i, = flaechen
    if not 0 <= i < len(modell.flaechen):
        return False
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*punkt)).Vertex()
    abstand = BRepExtrema_DistShapeShape(vertex, modell.flaechen[i])
    return abstand.IsDone() and abstand.NbSolution() == 1 and abstand.Value() <= .001


@dataclass
class _Stellengrafik:
    produktformen: set[int]
    kennung: str
    kreuz: np.ndarray | None
    flaechen: set[int]


class Stellenbestand:
    """Vorhandene Stellennummern und noch ungepruefte Originalgrafiken je Produktform."""

    def __init__(self, datei, modell):
        from .p21 import Ref
        self.datei, self.modell = datei, modell
        self.nummern = {}
        self.offen = None
        for e in datei.of_types_by_id(("DATUM_TARGET", "PLACED_DATUM_TARGET_FEATURE")):
            for rid in datei.referrers().get(e.id, ()):
                rel = datei.get(rid)
                args = rel.args("SHAPE_ASPECT_RELATIONSHIP") if rel.is_a("SHAPE_ASPECT_RELATIONSHIP") else ()
                if len(args) >= 4 and args[2] == Ref(e.id):
                    d = datei.get(args[3])
                    if d is not None and d.is_a("DATUM"):
                        self.nummern.setdefault(d.id, set()).add(str(e.args()[4]))

    def originalgrafiken(self):
        from .p21 import Ref
        from .pmi_reparieren import aus_name
        from .praesentation import ANNOTATIONEN, lies_grafik
        from .step_schreiben import _semantische_callouts
        if self.offen is None:
            ids = set()
            for e in self.datei.of_types_by_id((*ANNOTATIONEN, "DRAUGHTING_CALLOUT")):
                args = e.parts.get("REPRESENTATION_ITEM") or e.args()
                if args and isinstance(args[0], str) and aus_name(args[0]) == ("bezug", "DatumTarget"):
                    ids.add(e.id)
            self.offen = {}
            if not ids:
                return self.offen
            ids.difference_update(_semantische_callouts(self.datei))
            if not ids:
                return self.offen
            from .pmi_lesen import flaechen_von_aspekt
            for nr, g in lies_grafik(self.datei, ids=ids).items():
                formen, flaechen = set(), set()
                for i in g.pmi_ids:
                    e = self.datei.get(i)
                    if e is not None and e.is_a("SHAPE_ASPECT") and isinstance(e.args("SHAPE_ASPECT")[2], Ref):
                        formen.add(e.args("SHAPE_ASPECT")[2].id)
                        flaechen.update(flaechen_von_aspekt(self.datei, self.modell, i))
                fund = grafischer_punkt(g)
                name = fund[0] if fund else kennung_im_kreis(g)
                self.offen[nr] = _Stellengrafik(formen, name, fund[1] if fund else None, flaechen)
        return self.offen

    def fehlende(self, pds, buchstabe):
        return [g.kennung or f"#{nr}" for nr, g in self.originalgrafiken().items()
                if (not g.produktformen or pds in g.produktformen)
                and (not g.kennung or g.kennung.rstrip("0123456789") == buchstabe)]


def lese_kontakt(datei, target, flaeche, skalen):
    """Position aus der Parameterdarstellung mit Einheiten und Bauteillage lesen."""
    from OCC.Core.gp import gp_Pnt
    from .p21 import Ref
    punkte = set()
    verweise = datei.referrers()
    for i in verweise.get(target, ()):
        eig = datei.get(i)
        if not eig.is_a("PROPERTY_DEFINITION") or eig.args("PROPERTY_DEFINITION")[2] != Ref(target):
            continue
        for j in verweise.get(i, ()):
            link = datei.get(j)
            if not link.is_a("SHAPE_DEFINITION_REPRESENTATION"):
                continue
            rep = datei.get(link.args("SHAPE_DEFINITION_REPRESENTATION")[1])
            if rep is None or not rep.is_a("SHAPE_REPRESENTATION_WITH_PARAMETERS"):
                continue
            _, elemente, kontext = rep.args("SHAPE_REPRESENTATION_WITH_PARAMETERS")
            faktor = skalen.get(kontext.id) if isinstance(kontext, Ref) else None
            if not faktor:
                continue
            for ref in elemente:
                ax = datei.get(ref)
                if ax is None or not ax.is_a("AXIS2_PLACEMENT_3D"):
                    continue
                pos = datei.get(ax.args("AXIS2_PLACEMENT_3D")[1])
                if pos is not None and pos.is_a("CARTESIAN_POINT"):
                    xyz = pos.args("CARTESIAN_POINT")[1]
                    if len(xyz) == 3 and np.isfinite(xyz).all():
                        p = gp_Pnt(*(w*faktor for w in xyz)).Transformed(flaeche.Location().Transformation())
                        punkte.add(tuple(p.Coord()))
    return list(punkte.pop()) if len(punkte) == 1 else None
