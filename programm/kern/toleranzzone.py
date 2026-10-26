"""Toleranzzonen als Huellgeometrie (ohne Qt): Flaechen- und Lagetoleranzen anschaulich machen.

- Ebenheit, Parallelitaet, Rechtwinkligkeit, Neigung, Flaechenform, Linienform, Lauf: zwei Huellflaechen im Abstand
  +-t/2 zur Nennflaeche (Versatzflaechen in den Grenzen der Flaeche).
- Position, Koaxialitaet, Konzentrizitaet mit Durchmesserzone: Zylinder mit Durchmesser t um die Achse der
  Bohrung bzw. des Zapfens; ohne Durchmesserzone: zwei Ebenen im Abstand t (Breite).
Die Zone ist oft sehr schmal: sie wird bei Bedarf ueberhoeht (Faktor wird mitgeliefert).
"""

from __future__ import annotations

from dataclasses import dataclass, field

FLAECHENZONE = {"Flatness", "Parallelism", "Perpendicularity", "Angularity", "ProfileOfSurface", "ProfileOfLine",
                "CircularRunout", "TotalRunout", "Straightness", "CircularityOrRoundness", "Cylindricity", "Symmetry"}
ACHSZONE = {"Position", "Coaxiality", "Concentricity"}


@dataclass
class Zone:
    formen: list = field(default_factory=list)
    breite: float = 0.0  # wahre Zonenbreite (mm)
    faktor: float = 1.0  # Ueberhoehung fuer die Anzeige
    art: str = ""  # "flaechen" | "zylinder"


def _versatz(flaeche, abstand: float):
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepTools import breptools
    from OCC.Core.Geom import Geom_OffsetSurface
    from OCC.Core.TopAbs import TopAbs_REVERSED
    flaeche_geom = BRep_Tool.Surface(flaeche)
    if flaeche_geom is None:
        return None
    if flaeche.Orientation() == TopAbs_REVERSED:
        abstand = -abstand
    u0, u1, v0, v1 = breptools.UVBounds(flaeche)
    mf = BRepBuilderAPI_MakeFace(Geom_OffsetSurface(flaeche_geom, abstand), u0, u1, v0, v1, 1e-6)
    return mf.Face() if mf.IsDone() else None


def _achse(flaechen):
    """(Punkt, Richtung, Laenge, Radius) der Achse der ersten Zylinder-/Kegelflaeche oder None."""
    import numpy as np
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
    vmin, vmax, achse, r = None, None, None, 0.0
    for f in flaechen:
        if BRep_Tool.Surface(f) is None:
            continue
        s = BRepAdaptor_Surface(f, True)
        if s.GetType() not in (GeomAbs_Cylinder, GeomAbs_Cone):
            continue
        ax = s.Cylinder().Axis() if s.GetType() == GeomAbs_Cylinder else s.Cone().Axis()
        if achse is None:
            achse = ax
            r = s.Cylinder().Radius() if s.GetType() == GeomAbs_Cylinder else s.Cone().RefRadius()
        _, _, v0, v1 = breptools.UVBounds(f)
        vmin = v0 if vmin is None else min(vmin, v0)
        vmax = v1 if vmax is None else max(vmax, v1)
    if achse is None:
        return None
    p, d = achse.Location(), achse.Direction()
    start = np.array([p.X(), p.Y(), p.Z()]) + vmin * np.array([d.X(), d.Y(), d.Z()])
    return start, np.array([d.X(), d.Y(), d.Z()]), float(vmax - vmin), r


def zone(p, modell, sichtbar_mindest: float = 0.0) -> Zone | None:
    """Zone einer Toleranz-PMI; sichtbar_mindest: Mindestbreite fuer die Anzeige (mm), sonst wahre Breite."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    if p.art != "toleranz" or not p.wert or not p.flaechen:
        return None
    flaechen = [modell.flaechen[i] for i in sorted(p.flaechen) if i < len(modell.flaechen)]
    t = float(p.wert)
    faktor = max(1.0, sichtbar_mindest / t) if sichtbar_mindest > 0 else 1.0
    anzeige = t * faktor
    durchmesser = "Diameter" in p.modifikatoren or p.zone == "Diameter"
    if p.typ in ACHSZONE and durchmesser:
        a = _achse(flaechen)
        if a is not None:
            start, d, laenge, _ = a
            zyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*start), gp_Dir(*d)), anzeige / 2, max(laenge, 1e-3)).Shape()
            return Zone([zyl], t, faktor, "zylinder")
    if p.typ in FLAECHENZONE or p.typ in ACHSZONE:
        formen = [x for f in flaechen for x in (_versatz(f, anzeige / 2), _versatz(f, -anzeige / 2)) if x is not None]
        if formen:
            return Zone(formen, t, faktor, "flaechen")
    return None
