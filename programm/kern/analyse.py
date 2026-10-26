"""Analysen als Farbkarte je Netzknoten: Entformungsschraege, Kruemmungsradius, Wandstaerke (ohne Qt).

Grundlage sind die angezeigten Teile (Blaetter des Baums mit Lage); ebene Flaechen werden fuer feinere
Verlaeufe unterteilt. Ergebnis ist eine Karte wie beim Abweichungsvergleich (kern.abweichung.Karte) mit Skala.
"""

from __future__ import annotations

import math

import numpy as np

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepLProp import BRepLProp_SLProps
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCC.Core.gp import gp_Dir, gp_Lin, gp_Pnt
from OCC.Core.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods

from ..i18n import tr
from .abweichung import GRAU, Karte, Skala, _diagonale, verfeinere
from .ausrichten import tesselliere

ENTFORMUNG, KRUEMMUNG, WANDSTAERKE = "entformung", "kruemmung", "wandstaerke"


def _flaechen(teile) -> list[tuple[object, object]]:
    """(Flaeche mit Lage, Koerper) aller Teile."""
    out = []
    for koerper in teile:
        ex = TopExp_Explorer(koerper, TopAbs_FACE)
        while ex.More():
            out.append((topods.Face(ex.Current()), koerper))
            ex.Next()
    return out


def _uv(flaeche, geom, p):
    pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*p), geom)
    if not pr.IsDone() or pr.NbPoints() == 0:
        return None
    return pr.LowerDistanceParameters()


def _normale(flaeche, props, u, v):
    """Aeussere Normale (Flaechenorientierung beachtet) oder None."""
    props.SetParameters(u, v)
    if not props.IsNormalDefined():
        return None
    n = props.Normal()
    r = np.array([n.X(), n.Y(), n.Z()])
    return -r if flaeche.Orientation() == TopAbs_REVERSED else r


def berechne(art: str, teile: list, richtung=(0.0, 0.0, 1.0), feinheit: float = 0.2,
             fortschritt=lambda anteil: None, teilung: float = 50.0) -> Karte:
    """Werte je Knoten: Entformung in Grad (+ zur Ausformrichtung, - Hinterschnitt), Kruemmungsradius in mm
    (kleinster Hauptradius, eben = inf), Wandstaerke in mm (nan ohne Gegenflaeche)."""
    paare = _flaechen(teile)
    netze_roh = tesselliere([f for f, _ in paare], feinheit)
    laenge = _diagonale(netze_roh) / teilung
    d = np.asarray(richtung, float)
    d = d / (np.linalg.norm(d) or 1.0)
    schnitte: dict[int, IntCurvesFace_ShapeIntersector] = {}
    netze, werte = [], []
    for i, ((flaeche, koerper), (pts, tri)) in enumerate(zip(paare, netze_roh)):
        fortschritt(i / max(len(paare), 1))
        if not len(tri):
            netze.append((pts, tri))
            werte.append(np.zeros(0))
            continue
        eben = BRepAdaptor_Surface(flaeche, True).GetType() == GeomAbs_Plane
        if eben and art != KRUEMMUNG:
            pts, tri = verfeinere(pts, tri, laenge)
        geom = BRep_Tool.Surface(flaeche)
        props = BRepLProp_SLProps(BRepAdaptor_Surface(flaeche, True), 2, 1e-7)
        w = np.full(len(pts), np.nan)
        for j, p in enumerate(pts):
            uv = _uv(flaeche, geom, p)
            if uv is None:
                continue
            if art == KRUEMMUNG:
                if eben:
                    w[j] = math.inf
                    continue
                props.SetParameters(*uv)
                if props.IsCurvatureDefined():
                    k = max(abs(props.MaxCurvature()), abs(props.MinCurvature()))
                    w[j] = 1.0 / k if k > 1e-9 else math.inf
                continue
            n = _normale(flaeche, props, *uv)
            if n is None:
                continue
            if art == ENTFORMUNG:
                w[j] = math.degrees(math.asin(max(-1.0, min(1.0, float(n @ d)))))
            else:
                schl = id(koerper)
                if schl not in schnitte:
                    schnitte[schl] = IntCurvesFace_ShapeIntersector()
                    schnitte[schl].Load(koerper, 1e-6)
                s = schnitte[schl]
                s.Perform(gp_Lin(gp_Pnt(*p), gp_Dir(*(-n))), 0.01, 1e9)  # eigene Flaeche ueberspringen
                if s.IsDone() and s.NbPnt() > 0:
                    w[j] = min(s.WParameter(k) for k in range(1, s.NbPnt() + 1))
        netze.append((pts, tri))
        werte.append(w)
    fortschritt(1.0)
    return Karte(netze, werte, feinheit)


# --- Skalen ---

def skala_entformung(mindest: float = 1.0) -> Skala:
    """Gruen: genug Schraege zur Ausformrichtung, blau: zur Gegenrichtung, rot: zu wenig (|a| < Mindestwinkel)."""
    def farbe(a):
        if a != a:
            return GRAU
        if abs(a) < mindest:
            return (0.90, 0.20, 0.20)
        t = min((abs(a) - mindest) / 15.0, 1.0)
        if a > 0:
            return (0.55 * (1 - t) + 0.15 * t, 0.80 * (1 - t) + 0.62 * t, 0.30 * (1 - t) + 0.28 * t)
        return (0.45 * (1 - t) + 0.15 * t, 0.65 * (1 - t) + 0.40 * t, 0.95 * (1 - t) + 0.85 * t)
    grenzen = [-90.0, -15.0, -5.0, -mindest, mindest, 5.0, 15.0, 90.0]
    return Skala(tr("Entformung (°), Mindestwinkel {:.1f}°").format(mindest), grenzen, farbe,
                 lambda a: f"{a:+.2f}°", [f"{g:+.0f}°" if abs(g) >= 5 else f"{g:+.1f}°" for g in grenzen],
                 "Entformungsschräge")


def skala_kruemmung(klein: float = 1.0, gross: float = 50.0) -> Skala:
    """Kleiner Radius rot, grosser blau, eben grau (logarithmische Stufen)."""
    grenzen = [klein * (gross / klein) ** (i / 6) for i in range(7)]

    def farbe(r):
        if r != r or math.isinf(r):
            return GRAU
        t = min(max(math.log(max(r, 1e-9) / klein) / math.log(gross / klein), 0.0), 1.0)
        return (0.92 * (1 - t) + 0.20 * t, 0.30 + 0.35 * (1 - abs(2 * t - 1)), 0.20 * (1 - t) + 0.90 * t)
    return Skala(tr("Krümmungsradius (mm), eben = grau"), grenzen, farbe,
                 lambda r: tr("eben") if math.isinf(r) else f"R {r:.3f} mm", [f"{g:.3g}" for g in grenzen],
                 "Krümmungsradius")


def skala_wandstaerke(werte: np.ndarray) -> Skala:
    """Duenn rot, dick blau; Stufen zwischen 2. und 98. Perzentil."""
    w = werte[np.isfinite(werte)]
    lo, hi = (float(np.percentile(w, 2)), float(np.percentile(w, 98))) if len(w) else (0.0, 1.0)
    hi = max(hi, lo + 1e-6)
    grenzen = list(np.linspace(lo, hi, 7))

    def farbe(x):
        if x != x:
            return GRAU
        t = min(max((x - lo) / (hi - lo), 0.0), 1.0)
        return (0.92 * (1 - t) + 0.20 * t, 0.30 + 0.35 * (1 - abs(2 * t - 1)), 0.20 * (1 - t) + 0.90 * t)
    return Skala(tr("Wandstärke (mm)"), grenzen, farbe, lambda x: f"{x:.3f} mm", [f"{g:.2f}" for g in grenzen],
                 "Wandstärke")
