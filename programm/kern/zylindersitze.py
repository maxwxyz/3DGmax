"""Zylinderabschnitte und moegliche Sitzpartner in Einbaulage."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from math import pi

import numpy as np
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods

from .toleranzzone import _ist_innen


@dataclass(frozen=True)
class Sitz:
    nummer: int
    teil: str
    innen: bool
    d_mm: float
    mitte_mm: tuple
    richtung: tuple
    laenge_mm: float


@dataclass(frozen=True)
class Sitzpaar:
    zapfen: Sitz
    bohrung: Sitz
    ueberdeckung_mm: float
    differenz_mm: float


def erkenne(form, nummer, name, pruefe=None):
    gruppen = {}
    ex = TopExp_Explorer(form, TopAbs_FACE)
    anzahl = 0
    while ex.More():
        if pruefe and anzahl % 128 == 0:
            pruefe()
        anzahl += 1
        f = topods.Face(ex.Current())
        ex.Next()
        if BRep_Tool.Surface(f) is None:
            continue
        s = BRepAdaptor_Surface(f)
        if s.GetType() != GeomAbs_Cylinder:
            continue
        z = s.Cylinder()
        r = z.Radius()
        u = np.array(z.Axis().Direction().Coord())
        punkt = np.array(z.Location().Coord())
        a, b = s.FirstVParameter(), s.LastVParameter()
        laenge = b - a
        if laenge < 1e-5 or r < 1e-5:
            continue
        mitte = punkt + (.5 * (a + b)) * u
        innen = _ist_innen(f, punkt, u)
        if u[np.argmax(abs(u))] < 0:
            u = -u
        sitz = Sitz(nummer, name, innen, 2 * r, tuple(mitte), tuple(u), laenge)
        key = (innen, *np.round((*mitte, *u, r, laenge), 6))
        prop = GProp_GProps()
        brepgprop.SurfaceProperties(f, prop)
        alt = gruppen.get(key)
        gruppen[key] = (sitz, (alt[1] if alt else 0) + prop.Mass() / (2 * pi * r * laenge))
    return [s for s, anteil in gruppen.values() if abs(anteil - 1) < 1e-5]


def paare(sitze, pruefe=None):
    innen = sorted((s for s in sitze if s.innen), key=lambda s: s.d_mm)
    durchmesser = [s.d_mm for s in innen]
    baum = None
    if len(innen) > 48:
        from scipy.spatial import cKDTree
        baum = cKDTree([s.mitte_mm for s in innen])
        max_laenge = max(s.laenge_mm for s in innen)
    out = []
    for a in sitze:
        if pruefe:
            pruefe()
        if a.innen:
            continue
        # Enger Nennmassbereich fuer Kandidaten, keine Passungstoleranz.
        band = min(.1, a.d_mm * .005)
        i, j = bisect_left(durchmesser, a.d_mm - band), bisect_right(durchmesser, a.d_mm + band)
        u = np.array(a.richtung)
        if baum is not None and j-i > 48:
            umkreis = (a.laenge_mm + max_laenge)/2 + .001
            kandidaten = (innen[k] for k in sorted(baum.query_ball_point(a.mitte_mm, umkreis)) if i <= k < j)
        else:
            kandidaten = innen[i:j]
        for b in kandidaten:
            if a.nummer == b.nummer or np.linalg.norm(np.cross(u, b.richtung)) > 1e-6:
                continue
            delta = np.subtract(b.mitte_mm, a.mitte_mm)
            axial = float(delta @ u)
            if np.linalg.norm(delta - axial * u) > .001:
                continue
            l = min(a.laenge_mm / 2, axial + b.laenge_mm / 2) - max(-a.laenge_mm / 2, axial - b.laenge_mm / 2)
            if l > .001:
                out.append(Sitzpaar(a, b, l, b.d_mm - a.d_mm))
    return out


def kragensitze(sitze, sitzpaare, kegelraeder):
    """Eingreifender Kragen mit kleinerer Bohrung und angrenzendem, groesserem Bund am Kegelradruecken."""
    from collections import defaultdict
    je_teil = defaultdict(list)
    for sitz in sitze:
        je_teil[sitz.nummer].append(sitz)
    out = []
    for paar in sitzpaare:
        zapfen, bohrung = paar.zapfen, paar.bohrung
        for rad in kegelraeder.get(bohrung.nummer, ()):
            if not any(abs(s["durchmesser_mm"] - bohrung.d_mm) < .002 * bohrung.d_mm for s in rad.ruecksitze):
                continue
            n = rad.richtung
            delta = np.subtract(bohrung.mitte_mm, rad.punkt)
            if np.linalg.norm(np.cross(bohrung.richtung, n)) > 1e-5 or np.linalg.norm(np.cross(delta, n)) > .001:
                continue
            mit_bohrung = mit_bund = False
            for s in je_teil[zapfen.nummer]:
                pos = np.subtract(s.mitte_mm, zapfen.mitte_mm)
                if np.linalg.norm(np.cross(s.richtung, n)) > 1e-5 or np.linalg.norm(np.cross(pos, n)) > .001:
                    continue
                links, rechts = float(pos @ n) - s.laenge_mm/2, float(pos @ n) + s.laenge_mm/2
                if s.innen and s.d_mm < zapfen.d_mm and links <= -.5*zapfen.laenge_mm+.001 and rechts >= .5*zapfen.laenge_mm-.001:
                    mit_bohrung = True
                if not s.innen and s.d_mm > bohrung.d_mm and abs(links-.5*zapfen.laenge_mm) < .05:
                    mit_bund = True
            if mit_bohrung and mit_bund:
                out.append(paar)
                break
    return out
