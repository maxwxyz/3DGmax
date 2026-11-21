"""Gedruckte Anzahl koplanarer Zielflaechen am nominalen B-Rep pruefen."""

from dataclasses import dataclass

from .pmi_ableiten import KOPLANARHINWEIS


@dataclass(frozen=True)
class Koplanarbefund:
    soll: int
    ist: int | None
    grund: str

    @property
    def status(self):
        if self.grund == "getrennt":
            return "gleich"
        if self.grund in ("anzahl", "gekruemmt", "ebenen"):
            return "geaendert"
        return "offen"


def einzelanzahl(hinweis):
    m = KOPLANARHINWEIS.fullmatch(" ".join(hinweis.split()))
    if m and not m["simultan"] and len(m["anzahl"]) <= 4:
        return int(m["anzahl"])
    return None


def zielanzahl(text):
    treffer = [m["anzahl"] for z in text.splitlines()[2:]
               if (m := KOPLANARHINWEIS.fullmatch(" ".join(z.split())))]
    return int(treffer[0]) if len(treffer) == 1 and len(treffer[0]) <= 4 else None


def _getrennt(flaechen, tol):
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from .kollision import _box

    boxen = [_box(f, tol) for f in flaechen]
    if any(b.IsVoid() or b.IsOpen() for b in boxen):
        return "geometrie"
    grenzen = [b.Get() for b in boxen]
    achse = max(range(3), key=lambda i: max(g[i] for g in grenzen)-min(g[i] for g in grenzen))
    davor = []
    for j in sorted(range(len(grenzen)), key=lambda i: grenzen[i][achse]):
        davor = [i for i in davor if grenzen[i][achse+3] >= grenzen[j][achse]]
        for i in davor:
            if boxen[i].IsOut(boxen[j]):
                continue
            abstand = BRepExtrema_DistShapeShape(flaechen[i], flaechen[j])
            if not abstand.IsDone() or abstand.NbSolution() == 0:
                return "geometrie"
            if abstand.Value() <= tol:
                return "beruehrung"
        davor.append(j)
    return "getrennt"


def pruefe_koplanar(soll, ids, modell):
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Sphere, GeomAbs_Torus
    from OCC.Core.GeomLib import GeomLib_IsPlanarSurface
    from OCC.Core.Precision import precision

    if modell is None or not ids or any(i < 0 or i >= len(modell.flaechen) for i in ids):
        return Koplanarbefund(soll, None, "geometrie")
    flaechen = [modell.flaechen[i] for i in sorted(ids)]
    anzahl = len(flaechen)
    tol = precision.Confusion()
    try:
        basis = None
        for f in flaechen:
            flaeche = BRep_Tool.Surface(f)
            if flaeche is None:
                return Koplanarbefund(soll, None, "geometrie")
            suche = GeomLib_IsPlanarSurface(flaeche, tol)
            if not suche.IsPlanar():
                art = BRepAdaptor_Surface(f).GetType()
                gekruemmt = art in (GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Sphere, GeomAbs_Torus)
                return Koplanarbefund(soll, anzahl, "gekruemmt" if gekruemmt else "geometrie")
            ebene = suche.Plan()
            if basis is None:
                basis = ebene
            elif (not basis.Axis().IsParallel(ebene.Axis(), precision.Angular())
                  or basis.Distance(ebene.Location()) > tol):
                return Koplanarbefund(soll, anzahl, "ebenen")
        grund = _getrennt(flaechen, tol)
    except RuntimeError:
        return Koplanarbefund(soll, None, "geometrie")
    if grund == "getrennt" and anzahl != soll:
        grund = "anzahl"
    return Koplanarbefund(soll, anzahl, grund)
