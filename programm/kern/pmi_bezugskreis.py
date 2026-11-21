"""Kreisfoermige Bezugsstelle aus Schriftkreis und zugeordneter ebener Ringflaeche."""

from dataclasses import dataclass
import re

import numpy as np

from .pmi_bezugspunkt import _halbkreistext, _netzstriche, _nummer, hat_kontakt


@dataclass
class Bezugskreis:
    name: str
    durchmesser: float
    mitte: np.ndarray
    normale: np.ndarray

    def passt(self, p):
        return (p.modifikatoren == ["circle"] and p.bezugsdurchmesser is not None
                and np.isclose(p.bezugsdurchmesser, self.durchmesser, rtol=0, atol=1e-7)
                and np.shape(p.bezugspunkt) == (3,) and np.shape(p.bezugsnormale) == (3,)
                and np.allclose(p.bezugspunkt, self.mitte, rtol=0, atol=1e-6)
                and np.allclose(p.bezugsnormale, self.normale, rtol=0, atol=1e-8))


def _freies_ende(striche, teiler, mitte, radius, punkte):
    """Die gesamte Hinweislinie muss an einem Ende des Durchmessers beginnen."""
    aussen = [s for s in striche if np.linalg.norm(s-mitte, axis=1).max() > 1.15*radius]
    if not 1 <= len(aussen) <= 3:
        return None
    # Auch zusaetzliche, nicht als Striche erkannte Geometrie ausserhalb des Ballons beachten.
    fern = punkte[np.linalg.norm(punkte-mitte, axis=1) > 1.15*radius]
    getroffen = np.zeros(len(fern), dtype=bool)
    for a, b in aussen:
        v = b-a
        if v @ v < 1e-14:
            return None
        t = np.clip(((fern-a) @ v)/(v @ v), 0, 1)
        getroffen |= np.linalg.norm(fern - a - t[:, None]*v, axis=1) < .01*radius
    if not getroffen.all():
        return None
    for start in teiler:
        punkt = start
        rest = list(aussen)
        while rest:
            anschluss = [(i, k) for i, s in enumerate(rest) for k in (0, 1)
                         if np.linalg.norm(s[k]-punkt) < .005*radius]
            if len(anschluss) != 1:
                break
            i, k = anschluss[0]
            punkt = rest.pop(i)[1-k]
        if not rest and np.linalg.norm(punkt-mitte) > 1.15*radius:
            return punkt
    return None


def _beschriftung(g):
    from . import pmi_strichschrift as schrift
    if not g.textfaktor or not schrift._lesbar(g):
        return None
    striche = [s for s in g.linien if len(s) == 2]
    for p, t in g.dreiecke:
        striche.extend(_netzstriche(p, t))
    if not 2 <= len(striche) <= 150:
        return None
    punkte = np.vstack([*g.linien, *(p for p, _ in g.dreiecke)])
    if not np.isfinite(punkte).all():
        return None
    normal = (g.ebene[3] if g.ebene is not None else
              np.linalg.svd(punkte-punkte.mean(axis=0), full_matrices=False)[2][-1])
    fund = {}
    for teiler in striche:
        v = teiler[1]-teiler[0]
        mitte, radius = teiler.mean(axis=0), np.linalg.norm(v)/2
        if radius < 1e-8 or np.ptp(punkte @ normal) > .005*radius:
            continue
        spitze = _freies_ende(striche, teiler, mitte, radius, punkte)
        if spitze is None:
            continue
        for x in (v/(2*radius), -v/(2*radius)):
            quer = np.cross(normal,x)
            for y in (quer, -quer):
                if g.ebene is not None and (x @ g.ebene[1] < .98 or y @ g.ebene[2] < .98):
                    continue
                pfade = [(p/radius, f) for p, f in schrift._pfade(g, (mitte,x,y,normal))]
                name = _nummer(pfade, mit_flaechenmass=True)
                if not name:
                    continue
                mass = _halbkreistext(pfade, oben=True, zweites_feld=True)
                if m := re.fullmatch(r"⌀(\d+(?:[.,]\d+)?|[.,]\d+)", mass):
                    d = float(m[1].replace(",", "."))*g.textfaktor
                    if d > 0 and np.isfinite(d):
                        fund[name, d, tuple(spitze)] = (name, d, spitze, normal)
    return next(iter(fund.values())) if len(fund) == 1 else None


def _ring(face):
    """Vollstaendige konzentrische Randkreise und nach aussen orientierte Normale."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    if face is None or face.IsNull() or BRep_Tool.Surface(face) is None:
        return None
    sf = BRepAdaptor_Surface(face)
    if sf.GetType() != GeomAbs_Plane or face.Orientation() not in (TopAbs_FORWARD, TopAbs_REVERSED):
        return None
    normale = np.asarray(sf.Plane().Axis().Direction().Coord())
    if face.Orientation() == TopAbs_REVERSED:
        normale = -normale
    mitte, winkel = None, {}
    ex = TopExp_Explorer(face, TopAbs_EDGE)
    while ex.More():
        c = BRepAdaptor_Curve(topods.Edge(ex.Current()))
        if c.GetType() != GeomAbs_Circle:
            return None
        kreis = c.Circle()
        z = np.asarray(kreis.Location().Coord())
        if mitte is not None and np.linalg.norm(mitte-z) > .001:
            return None
        mitte = z
        r = next((r for r in winkel if abs(r-kreis.Radius()) <= .001), kreis.Radius())
        winkel[r] = winkel.get(r, 0.) + abs(c.LastParameter()-c.FirstParameter())
        ex.Next()
    if len(winkel) != 2 or any(abs(w-2*np.pi) > 1e-5 for w in winkel.values()):
        return None
    return mitte, normale, min(winkel), max(winkel)


def grafischer_kreis(g, modell, flaechen):
    if len(flaechen) != 1:
        return None
    i, = flaechen
    if not 0 <= i < len(modell.flaechen):
        return None
    ring = _ring(modell.flaechen[i])
    if ring is None or not (text := _beschriftung(g)):
        return None
    name, d, spitze, schreibnormale = text
    mitte, normale, innen, aussen = ring
    delta = spitze-mitte
    abstand = delta @ normale
    radial = np.linalg.norm(delta-abstand*normale)
    # Der Hinweis muss zur wirklichen Auflage zwischen Bohrung und Zielkreis zeigen.
    if (not innen < d/2 <= aussen or not innen-.001 <= radial <= d/2+.001
            or not -.001 <= abstand <= d/4 or abs(delta @ schreibnormale) > .001):
        return None
    projektion = spitze - abstand*normale
    if not hat_kontakt(modell, flaechen, projektion):
        return None
    return Bezugskreis(name, d, mitte, normale)


def lese_kreis(datei, target, face, skalen):
    """Mitte, orientierte Achse und explizites Durchmessermass derselben Darstellung."""
    from OCC.Core.gp import gp_Dir, gp_Pnt
    from .pmi_bezugspunkt import parameterdarstellungen
    from .pmi_step import _gesicherte_laenge
    lage = face.Location().Transformation()
    kreise = set()
    for elemente, faktor in parameterdarstellungen(datei, target, skalen):
        achsen, masse = [], []
        for ref in elemente:
            e = datei.get(ref)
            if e is None:
                continue
            if e.is_a("AXIS2_PLACEMENT_3D"):
                _, pos, richtung, _ = e.args("AXIS2_PLACEMENT_3D")
                p, n = datei.get(pos), datei.get(richtung)
                if p is None or not p.is_a("CARTESIAN_POINT") or n is None or not n.is_a("DIRECTION"):
                    continue
                xyz, v = p.args("CARTESIAN_POINT")[1], n.args("DIRECTION")[1]
                if len(xyz) == len(v) == 3 and np.isfinite([xyz,v]).all() and np.linalg.norm(v) > 1e-12:
                    mitte = gp_Pnt(*(k*faktor for k in xyz)).Transformed(lage)
                    normal = gp_Dir(*v).Transformed(lage)
                    achsen.append((tuple(mitte.Coord()), tuple(normal.Coord())))
            elif e.parts.get("REPRESENTATION_ITEM") == ["target diameter"] and e.is_a("LENGTH_MEASURE_WITH_UNIT"):
                wert = _gesicherte_laenge(datei, ref)
                if wert is not None and wert > 0:
                    masse.append(wert)
        if len(achsen) == len(masse) == 1:
            kreise.add((*achsen[0], masse[0]))
    if len(kreise) == 1:
        mitte, normale, d = kreise.pop()
        return list(mitte), list(normale), d
    return None
