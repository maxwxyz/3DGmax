"""Toleranzzonen als Huellgeometrie (ohne Qt): wo Flaechen und Achsen innerhalb der Toleranz liegen duerfen.

- Flaechenzonen (Ebenheit, Parallelitaet, Rechtwinkligkeit, Neigung, Flaechen-/Linienform, Lauf, Symmetrie, ...):
  zwei Versatzflaechen im Abstand +-t/2 zur Nennflaeche. Unsymmetrische Zone: ISO "UZ u" verschiebt die Mitte der
  Zone um u (+ = aus dem Material heraus), ASME (U) u ist der Anteil ausserhalb des Materials.
- Achszonen (Position, Koaxialitaet, Konzentrizitaet; Richtungs- und Geradheitstoleranzen mit Durchmesserzone):
  Zylinder mit Durchmesser t um die Nennachse. Dazu die Huellen, in denen die Zylinderflaeche selbst liegen kann
  (Masstoleranz plus Lagetoleranz). Mit Maximum-/Minimum-Material (M/L): Zone bei MMC und bei LMC (Bonus).
  Projizierte Zone (P): Zylinder ausserhalb des Elements in der angegebenen Laenge.
- Masstoleranzen (Durchmesser, Radius): Huellflaechen bei Hoechst- und Mindestmass.
- Allgemeintoleranzen (Auswahl): ISO 2768-1 (Masse) / -2 (Ebenheit) und ISO 22081 (Flaechenprofil) fuer Flaechen
  ohne eigene Angabe.
Schmale Zonen werden fuer die Anzeige ueberhoeht (der Faktor wird mitgeliefert; Abstaende zur Nennflaeche werden
skaliert, die Nenngeometrie bleibt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr

FLAECHENZONE = {"Flatness", "Parallelism", "Perpendicularity", "Angularity", "ProfileOfSurface", "ProfileOfLine",
                "CircularRunout", "TotalRunout", "Straightness", "CircularityOrRoundness", "Cylindricity", "Symmetry"}
ACHSZONE = {"Position", "Coaxiality", "Concentricity"}
# Richtungs- und Geradheitstoleranzen werden mit Durchmesserzone zur Achszone
ACHSE_MIT_DURCHMESSER = {"Perpendicularity", "Parallelism", "Angularity", "Straightness"}
GROESSE = {"Size_Diameter", "Size_Radius", "Size_SphericalDiameter", "Size_SphericalRadius"}
# ohne Durchmesserzone an zwei gegenueberliegenden Ebenen (Nut, Steg): Zone der abgeleiteten Mittelebene
MITTELEBENE = {"Symmetry", "Position", "Parallelism", "Perpendicularity", "Angularity", "Straightness"}

# Rollen der Teilformen (Farbe in der Ansicht)
ZONE, BONUS, HUELLE, ALLGEMEIN, VERSCHIEBUNG = "zone", "bonus", "huelle", "allgemein", "verschiebung"
FORM = {"Flatness", "Straightness", "CircularityOrRoundness", "Cylindricity"}
RICHTUNG = {"Parallelism", "Perpendicularity", "Angularity"}
LAGE = {"Position", "Symmetry", "Coaxiality", "Concentricity"}  # dazu Profil mit Bezug
LAUF = {"CircularRunout", "TotalRunout"}
BEZUG_MATERIAL = {"MaximumMaterialRequirement": "M", "LeastMaterialRequirement": "L"}


@dataclass
class Zone:
    formen: list = field(default_factory=list)
    breite: float = 0.0  # wahre Zonenbreite (mm)
    faktor: float = 1.0  # Ueberhoehung fuer die Anzeige
    art: str = ""  # "flaechen" | "zylinder" | "mass" | "allgemein"
    rollen: list[str] = field(default_factory=list)  # je Form: ZONE, BONUS, HUELLE, ALLGEMEIN, VERSCHIEBUNG
    hinweise: list[str] = field(default_factory=list)  # Erklaerung fuer die Statuszeile
    flaechen: set = field(default_factory=set)  # Quellflaechen (Index) der Zone, z. B. die Flaechen der PMI
    quellen: list = field(default_factory=list)  # je Form ihre Quellflaeche oder None (dann gilt flaechen)

    def dazu(self, form, rolle: str = ZONE, quelle: int | None = None):
        if form is not None:
            self.formen.append(form)
            self.rollen.append(rolle)
            self.quellen.append(quelle)

    def quellen_je_form(self) -> list[set[int]]:
        """Quellflaechen je Form (fuer die Anzeige an jeder Instanz eines mehrfach verbauten Teils)."""
        q = self.quellen if len(self.quellen) == len(self.formen) else [None] * len(self.formen)
        return [{x} if x is not None else set(self.flaechen) for x in q]


# --- Geometrie ---

def _versatz(flaeche, abstand: float):
    """Versatzflaeche; positiver Abstand zeigt aus dem Material heraus (Orientierung der Flaeche beachtet).
    Ebenen werden verschoben (echte Berandung mit Loechern), andere Flaechen ueber ihren Parameterbereich versetzt."""
    eben = _verschobene_ebene(flaeche, abstand)
    if eben is not None:
        return eben
    return _versatz_parameter(flaeche, abstand)


def _verschobene_ebene(flaeche, abstand: float):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.GeomAbs import GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_REVERSED
    from OCC.Core.gp import gp_Trsf, gp_Vec
    s = BRepAdaptor_Surface(flaeche)
    if s.GetType() != GeomAbs_Plane:
        return None
    n = s.Plane().Axis().Direction()
    if flaeche.Orientation() == TopAbs_REVERSED:
        abstand = -abstand
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(n.X() * abstand, n.Y() * abstand, n.Z() * abstand))
    return BRepBuilderAPI_Transform(flaeche, t, True).Shape()


def _versatz_parameter(flaeche, abstand: float):
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
    try:
        flaeche_neu = flaeche_geom if abs(abstand) < 1e-12 else Geom_OffsetSurface(flaeche_geom, abstand)
        mf = BRepBuilderAPI_MakeFace(flaeche_neu, u0, u1, v0, v1, 1e-6)
    except RuntimeError:  # z. B. Kegelspitze, Kugelpol: Versatz nicht definiert
        return None
    return mf.Face() if mf.IsDone() else None


def _achsen(flaechen) -> list[tuple]:
    """Je Achse (Bohrung, Zapfen; mehrere Flaechen auf einer Achse zusammengefasst):
    (Startpunkt, Richtung, Laenge, Radius, Flaeche)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
    gruppen = []  # [Punkt, Richtung, smin, smax, Radius, erste Flaeche]
    for f in flaechen:
        if BRep_Tool.Surface(f) is None:
            continue
        s = BRepAdaptor_Surface(f, True)
        if s.GetType() not in (GeomAbs_Cylinder, GeomAbs_Cone):
            continue
        zyl = s.GetType() == GeomAbs_Cylinder
        ax = s.Cylinder().Axis() if zyl else s.Cone().Axis()
        p = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
        d = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        _, _, v0, v1 = breptools.UVBounds(f)
        if not zyl:  # Kegel: v laeuft entlang der Mantellinie
            k = np.cos(s.Cone().SemiAngle())
            v0, v1 = v0 * k, v1 * k
        enden = [p + v0 * d, p + v1 * d]
        for g in gruppen:
            q = p - g[0]
            if abs(d @ g[1]) > 0.9999 and np.linalg.norm(q - g[1] * (q @ g[1])) < 1e-3:
                lage = [(e - g[0]) @ g[1] for e in enden]
                g[2], g[3] = min(g[2], *lage), max(g[3], *lage)
                break
        else:
            r = s.Cylinder().Radius() if zyl else s.Cone().RefRadius()
            gruppen.append([p, d, min(v0, v1), max(v0, v1), r, f])
    return [(g[0] + g[2] * g[1], g[1], float(g[3] - g[2]), g[4], g[5]) for g in gruppen]


def _achse(flaechen):
    """Erste Achse (siehe _achsen) oder None."""
    a = _achsen(flaechen)
    return a[0] if a else None


def _ist_innen(flaeche, start, richtung) -> bool:
    """Bohrung (Materialnormale zeigt zur Achse) oder Zapfen."""
    from OCC.Core.BRepGProp import BRepGProp_Face
    from OCC.Core.gp import gp_Pnt, gp_Vec
    gf = BRepGProp_Face(flaeche)
    u0, u1, v0, v1 = gf.Bounds()
    p, n = gp_Pnt(), gp_Vec()
    gf.Normal((u0 + u1) / 2, (v0 + v1) / 2, p, n)
    q = np.array([p.X(), p.Y(), p.Z()]) - start
    radial = q - richtung * (q @ richtung)
    return float(np.array([n.X(), n.Y(), n.Z()]) @ radial) < 0


def _zylinder(start, richtung, radius: float, laenge: float):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    if radius <= 0 or laenge <= 0:
        return None
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*map(float, start)), gp_Dir(*map(float, richtung))),
                                    float(radius), float(laenge)).Shape()


QUERSCHNITTE = (0.1, 0.5, 0.9)  # Lage der Ringzonen entlang der Achse (Anteil der Laenge)


def _ring(mitte, richtung, r_innen: float, r_aussen: float):
    """Ebene Kreisringflaeche (Zone in einem Querschnitt)."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
    if r_aussen <= 0:
        return None
    ax = gp_Ax2(gp_Pnt(*map(float, mitte)), gp_Dir(*map(float, richtung)))
    aussen = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(ax, float(r_aussen))).Edge()).Wire()
    f = BRepBuilderAPI_MakeFace(aussen)
    if r_innen > 1e-9:
        innen = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(ax, float(r_innen))).Edge()).Wire()
        innen.Reverse()
        f.Add(innen)
    return f.Face() if f.IsDone() else None


def _ringe(z: "Zone", start, richtung, laenge: float, r: float, halb: float, quelle=None):
    """Ringzonen r +- halb in den Querschnitten QUERSCHNITTE entlang einer Achse."""
    for anteil in QUERSCHNITTE:
        z.dazu(_ring(start + richtung * laenge * anteil, richtung, r - halb, r + halb), quelle=quelle)


def _querschnittzone(p, flaechen, t: float, faktor: float) -> "Zone | None":
    """Rundheit an Zylindern: je Querschnitt zwei konzentrische Kreise im Abstand t (Mitte frei, hier auf der
    Zylinderachse gezeigt)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    z = Zone(breite=t, faktor=faktor, art="querschnitt")
    for f in flaechen:
        if BRepAdaptor_Surface(f, True).GetType() != GeomAbs_Cylinder:
            return None  # Kegel, Kugel: Flaechenzone
        start, d, laenge, r, _e = _achse([f])
        _ringe(z, start, d, laenge, r, t / 2 * faktor)
    if z.formen:
        z.hinweise.append(tr("Zone je Querschnitt (gezeigt in drei Schnitten)"))
    return z if z.formen else None


def _im_material(modell, punkt) -> bool:
    from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
    from OCC.Core.TopAbs import TopAbs_IN
    from OCC.Core.gp import gp_Pnt
    try:
        k = BRepClass3d_SolidClassifier(modell.form, gp_Pnt(*map(float, punkt)), 1e-6)
        return k.State() == TopAbs_IN
    except Exception:  # noqa: BLE001 - Netze, offene Schalen: unbekannt
        return False


# --- Werte aus den PMI ---

def unsymmetrisch(p) -> float | None:
    """Wert der unsymmetrischen Zone (Modifikator "UZ u") oder None."""
    for m in p.modifikatoren:
        treffer = re.match(r"UZ\s*([-+]?\d*\.?\d+)", str(m))
        if treffer:
            return float(treffer.group(1))
    return None


def _grenzen_aussen_innen(p, t: float) -> tuple[float, float]:
    """Abstaende der beiden Zonengrenzen zur Nennflaeche (+ = aus dem Material)."""
    u = unsymmetrisch(p)
    if u is None:
        return t / 2, -t / 2
    if p.norm == "asme":  # U: Anteil ausserhalb des Materials
        return u, u - t
    return u + t / 2, u - t / 2  # ISO UZ: Verschiebung der Zonenmitte


def _groesse(p, alle_pmi, durchmesser: float) -> tuple[float, float]:
    """(Mindest-, Hoechstdurchmesser) des Elements aus einer Masstoleranz auf denselben Flaechen."""
    for m in alle_pmi or []:
        if m.art == "mass" and m.typ in ("Size_Diameter", "Size_Radius") and m.flaechen & p.flaechen:
            hoechst, mindest = m.grenzen()
            if hoechst is not None and mindest is not None:
                f = 2.0 if m.typ == "Size_Radius" else 1.0
                return mindest * f, hoechst * f
    return durchmesser, durchmesser


def _bonus(material: str, innen: bool, d: float, dmin: float, dmax: float) -> float:
    """Bonustoleranz bei Istmass d (Abweichung vom MMC- bzw. LMC-Mass)."""
    if material == "M":
        return d - dmin if innen else dmax - d
    if material == "L":
        return dmax - d if innen else d - dmin
    return 0.0


# --- Bezugssystem ---

def _bezug_flaechen(name: str, alle_pmi) -> set[int]:
    return {i for q in alle_pmi or [] if q.art == "bezug" and q.typ == "Datum" and q.name == name for i in q.flaechen}


def bezugsachse(p, modell, alle_pmi):
    """(Start, Richtung, Laenge, Radius, Name) der Achse des ersten Bezugs mit Drehachse oder None."""
    for b in sorted(p.bezuege, key=lambda b: b.stelle):
        idx = _bezug_flaechen(b.name, alle_pmi)
        achsen = _achsen([modell.flaechen[i] for i in sorted(idx) if i < len(modell.flaechen)])
        if achsen:
            start, d, laenge, r, _f = achsen[0]
            return start, d, laenge, r, b.name
    return None


def bezugsverschiebung(p, alle_pmi) -> list[tuple[str, str, float]]:
    """Bezuege mit Materialbedingung: (Name, M/L, moegliche Verschiebung als Durchmesser) aus dem Mass des
    Bezugselements (Groessentoleranz; die eigene Form-/Lagetoleranz des Bezugs bleibt unberuecksichtigt)."""
    out = []
    for b in sorted(p.bezuege, key=lambda b: b.stelle):
        mat = next((BEZUG_MATERIAL[m] for m in b.modifikatoren if m in BEZUG_MATERIAL), "")
        if not mat:
            continue
        idx = _bezug_flaechen(b.name, alle_pmi)
        for m in alle_pmi or []:
            if m.art == "mass" and idx and m.flaechen & idx:
                hoechst, mindest = m.grenzen()
                if hoechst is not None and mindest is not None and hoechst > mindest:
                    faktor = 2.0 if m.typ in ("Size_Radius", "Size_SphericalRadius") else 1.0
                    out.append((b.name, mat, (hoechst - mindest) * faktor))
                    break
    return out


def _uebergeordnet(p, alle_pmi):
    """Die engste Toleranz einer hoeheren Stufe an denselben Flaechen: Form < Richtung < Lage (Profil mit Bezug)."""
    if p.typ in FORM:
        stufen = RICHTUNG | LAGE | {"ProfileOfSurface"}
    elif p.typ in RICHTUNG:
        stufen = LAGE | {"ProfileOfSurface"}
    else:
        return None
    kandidaten = [q for q in alle_pmi or [] if q is not p and q.art == "toleranz" and q.wert and q.typ in stufen
                  and q.flaechen & p.flaechen and (q.typ != "ProfileOfSurface" or q.bezuege)]
    return min(kandidaten, key=lambda q: q.wert) if kandidaten else None


# --- Zonen ---

def _achszone(p, modell, flaechen, t: float, faktor: float, alle_pmi) -> Zone | None:
    achsen = _achsen(flaechen)
    if not achsen:
        return None
    z = Zone(breite=t, faktor=faktor, art="zylinder")
    bezug = bezugsachse(p, modell, alle_pmi) if p.typ in ("Coaxiality", "Concentricity") else None
    verschiebung = sum(v for _n, _m, v in bezugsverschiebung(p, alle_pmi))
    werte = [_eine_achse(z, p, modell, achse, t, faktor, alle_pmi, bezug, verschiebung) for achse in achsen]
    t_max, innen_r, aussen_r = werte[0]  # Hinweise zum ersten Element (Muster haben gleiche Werte)
    if bezug is not None:
        z.hinweise.append(tr("Zone um die Bezugsachse {}").format(bezug[4]))
    for name, mat, v in bezugsverschiebung(p, alle_pmi):
        z.hinweise.append(tr("Bezug {} {}: Zone darf sich als Ganzes um bis zu ⌀{:.4g} verschieben").format(
            name, "Ⓜ" if mat == "M" else "Ⓛ", v))
    if len(achsen) > 1:
        z.hinweise.append(tr("{} Elemente").format(len(achsen)))
    if p.zone == "Projected" and p.zonen_wert:
        z.hinweise.append(tr("projizierte Zone {:.4g} mm außerhalb des Elements").format(p.zonen_wert))
    if t_max > t + 1e-12:
        z.hinweise.append(tr("Zone ⌀{:.4g} bei {}, bis ⌀{:.4g} mit Bonus").format(
            t, "MMC" if p.material == "M" else "LMC", t_max))
    z.hinweise.append(tr("Fläche zwischen ⌀{:.4g} und ⌀{:.4g}").format(2 * innen_r, 2 * aussen_r))
    return z if z.formen else None


def _eine_achse(z: Zone, p, modell, achse, t: float, faktor: float, alle_pmi, bezug=None,
                verschiebung: float = 0.0) -> tuple[float, float, float]:
    """Zone, Bonuszone und Huellen eines Elements; Rueckgabe (groesste Zone, Huellradius innen, aussen).
    bezug: Bezugsachse (Koaxialitaet: Zone um sie); verschiebung: Bezugsverschiebung (Durchmesser)."""
    start, d, laenge, r, erste = achse
    laenge = max(laenge, 1e-3)
    innen = _ist_innen(erste, start, d)
    dmin, dmax = _groesse(p, alle_pmi, 2 * r)
    # Lagetoleranz je Istmass; Huellen der Flaeche ueber beide Grenzmasse (linear, Endpunkte genuegen)
    toleranzen = {dd: t + _bonus(p.material, innen, dd, dmin, dmax) for dd in (dmin, dmax)}
    t_max = max(toleranzen.values())
    fuss, richtung, hoehe = start, d, laenge
    if p.zone == "Projected" and p.zonen_wert:
        ende_plus = start + d * laenge
        if not _im_material(modell, ende_plus + d * laenge * 1e-3):
            fuss, richtung = ende_plus, d
        else:
            fuss, richtung = start, -d
        hoehe = float(p.zonen_wert)
    elif bezug is not None:  # Koaxialitaet: Zone auf der Bezugsachse, ueber die Laenge des Elements
        b_start, b_d = bezug[0], bezug[1] * (1.0 if bezug[1] @ d >= 0 else -1.0)
        fuss, richtung = b_start + b_d * ((start - b_start) @ b_d), b_d
    z.dazu(_zylinder(fuss, richtung, t * faktor / 2, hoehe))
    if t_max > t + 1e-12:
        z.dazu(_zylinder(fuss, richtung, t_max * faktor / 2, hoehe), BONUS)
    if verschiebung > 0:
        z.dazu(_zylinder(fuss, richtung, (t_max + verschiebung) * faktor / 2, hoehe), VERSCHIEBUNG)
    # Raum, in dem die Zylinderflaeche liegen kann (Mass + Lage); Abweichungen ueberhoeht wie die Zone
    innen_r = min(dd / 2 - tol / 2 for dd, tol in toleranzen.items())
    aussen_r = max(dd / 2 + tol / 2 for dd, tol in toleranzen.items())
    for rr in (innen_r, aussen_r):
        z.dazu(_zylinder(start, d, r + (rr - r) * faktor, laenge), HUELLE)
    return t_max, innen_r, aussen_r


def _kugel(flaechen):
    """(Mittelpunkt, Radius, Flaeche) der ersten Kugelflaeche oder None."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Sphere
    for f in flaechen:
        if BRep_Tool.Surface(f) is None:
            continue
        s = BRepAdaptor_Surface(f, True)
        if s.GetType() == GeomAbs_Sphere:
            c = s.Sphere().Location()
            return np.array([c.X(), c.Y(), c.Z()]), s.Sphere().Radius(), f
    return None


def _kugelzone(p, flaechen, t: float, faktor: float, alle_pmi) -> Zone | None:
    """Kugelfoermige Zone (S⌀) um den Mittelpunkt einer Kugel; dazu der Raum der Kugelflaeche."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCC.Core.gp import gp_Pnt
    k = _kugel(flaechen)
    if k is None:
        return None
    mitte, r, f = k
    dmin, dmax = 2 * r, 2 * r
    for m in alle_pmi or []:
        if m.art == "mass" and m.typ in ("Size_SphericalDiameter", "Size_SphericalRadius") and m.flaechen & p.flaechen:
            hoechst, mindest = m.grenzen()
            if hoechst is not None and mindest is not None:
                g = 2.0 if m.typ == "Size_SphericalRadius" else 1.0
                dmin, dmax = mindest * g, hoechst * g
    z = Zone(breite=t, faktor=faktor, art="kugel")

    def kugel(radius):
        return BRepPrimAPI_MakeSphere(gp_Pnt(*map(float, mitte)), float(radius)).Shape() if radius > 0 else None
    z.dazu(kugel(t * faktor / 2))
    innen_r, aussen_r = dmin / 2 - t / 2, dmax / 2 + t / 2
    for rr in (innen_r, aussen_r):
        z.dazu(kugel(r + (rr - r) * faktor), HUELLE)
    z.hinweise.append(tr("Kugelzone S⌀{:.4g} um den Mittelpunkt").format(t))
    z.hinweise.append(tr("Fläche zwischen S⌀{:.4g} und S⌀{:.4g}").format(2 * innen_r, 2 * aussen_r))
    return z if z.formen else None


def _ebenen_paar(flaechen):
    """Zwei gegenueberliegende parallele Ebenen (Nut oder Steg): (Mittelpunkt, Normale, Flaechen) oder None."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane
    ebenen = []
    for f in flaechen:
        if BRep_Tool.Surface(f) is None:
            continue
        s = BRepAdaptor_Surface(f, True)
        if s.GetType() != GeomAbs_Plane:
            return None  # nur reine Ebenen-Paare (sonst Flaechenzone)
        pl = s.Plane()
        n = np.array([pl.Axis().Direction().X(), pl.Axis().Direction().Y(), pl.Axis().Direction().Z()])
        o = np.array([pl.Location().X(), pl.Location().Y(), pl.Location().Z()])
        ebenen.append((o, n, f))
    for i, (o1, n1, f1) in enumerate(ebenen):
        for o2, n2, f2 in ebenen[i + 1:]:
            abstand = abs((o2 - o1) @ n1)
            if abs(n1 @ n2) > 0.9999 and abstand > 1e-6:
                return o1 + n1 * ((o2 - o1) @ n1) / 2, n1, [f for _, n, f in ebenen if abs(n @ n1) > 0.9999]
    return None


def _ebene_als_flaeche(mitte, n, flaechen, versatz: float):
    """Rechteck in der um 'versatz' verschobenen Mittelebene, so gross wie die Flaechen in der Ebene."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    pl = gp_Pln(gp_Ax3(gp_Pnt(*map(float, mitte + n * versatz)), gp_Dir(*map(float, n))))
    x = np.array([pl.XAxis().Direction().X(), pl.XAxis().Direction().Y(), pl.XAxis().Direction().Z()])
    y = np.cross(n, x)
    ecken = np.array([q for f in flaechen for q in _ecken(f)])
    u, v = (ecken - mitte) @ x, (ecken - mitte) @ y
    mf = BRepBuilderAPI_MakeFace(pl, float(u.min()), float(u.max()), float(v.min()), float(v.max()))
    return mf.Face() if mf.IsDone() else None


def _ecken(flaeche):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(flaeche, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def _mittelebenenzone(p, flaechen, t: float, faktor: float) -> Zone | None:
    paar = _ebenen_paar(flaechen)
    if paar is None:
        return None
    mitte, n, ebene = paar
    z = Zone(breite=t, faktor=faktor, art="mittelebene")
    for v in (t * faktor / 2, -t * faktor / 2):
        z.dazu(_ebene_als_flaeche(mitte, n, ebene, v))
    z.hinweise.append(tr("Zone der abgeleiteten Mittelebene (zwei Ebenen im Abstand {:.4g})").format(t))
    return z if z.formen else None


def _flaechenzone(p, flaechen, t: float, faktor: float) -> Zone | None:
    aussen, innen = _grenzen_aussen_innen(p, t)
    z = Zone(breite=t, faktor=faktor, art="flaechen")
    for f in flaechen:
        z.dazu(_versatz(f, aussen * faktor))
        z.dazu(_versatz(f, innen * faktor))
    if unsymmetrisch(p) is not None:
        z.hinweise.append(tr("unsymmetrisch: {:.4g} mm aus dem Material, {:.4g} mm ins Material").format(
            aussen, -innen))
    return z if z.formen else None


def _laufzone(p, modell, flaechen, t: float, faktor: float, alle_pmi) -> Zone | None:
    """Lauf: an Zylindern zwei koaxiale Zylinder um die Bezugsachse (Radius +- t/2), an Planflaechen Versatzflaechen."""
    bezug = bezugsachse(p, modell, alle_pmi)
    if bezug is None:
        return None
    b_start, b_d = bezug[0], bezug[1]
    z = Zone(breite=t, faktor=faktor, art="lauf")
    for f in flaechen:
        a = _achse([f])
        if a is not None and abs(a[1] @ b_d) > 0.9999:
            start, _d, laenge, r, _e = a
            fuss = b_start + b_d * ((start - b_start) @ b_d)
            richtung = b_d * (1.0 if _d @ b_d >= 0 else -1.0)
            if p.typ == "CircularRunout":  # Rundlauf gilt je Querschnitt: Ringe um die Bezugsachse
                _ringe(z, fuss, richtung, max(laenge, 1e-3), r, t / 2 * faktor)
                continue
            for rr in (r - t / 2 * faktor, r + t / 2 * faktor):
                z.dazu(_zylinder(fuss, richtung, rr, max(laenge, 1e-3)))
        else:
            z.dazu(_versatz(f, t / 2 * faktor))
            z.dazu(_versatz(f, -t / 2 * faktor))
    z.hinweise.append(tr("Zone um die Bezugsachse {}").format(bezug[4]))
    return z if z.formen else None


def _massgrenzen(p) -> tuple[float, float, float] | None:
    """(Hoechstmass, Mindestmass, Faktor Mass -> Radius) einer Durchmesser-/Radiusangabe."""
    hoechst, mindest_mass = p.grenzen()
    if hoechst is None or mindest_mass is None or p.nennwert is None or hoechst <= mindest_mass:
        return None
    return hoechst, mindest_mass, 0.5 if p.typ in ("Size_Diameter", "Size_SphericalDiameter") else 1.0


def _masszone(p, flaechen, faktor: float) -> Zone | None:
    """Huellen bei Hoechst- und Mindestmass einer Durchmesser-/Radiusangabe."""
    hoechst, mindest_mass, f = _massgrenzen(p)
    nenn = abs(p.nennwert)
    z = Zone(breite=hoechst - mindest_mass, faktor=faktor, art="mass")
    for fl in flaechen:
        a = _achse([fl])
        innen = a is not None and _ist_innen(fl, a[0], a[1])
        for grenze in (hoechst, mindest_mass):
            dr = (grenze - nenn) * f * faktor  # Radiusaenderung
            z.dazu(_versatz(fl, -dr if innen else dr))
    return z if z.formen else None


def _flaechen_inhalt(flaechen) -> float:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    g = GProp_GProps()
    for f in flaechen:
        brepgprop.SurfaceProperties(f, g)
    return g.Mass()


def _laengenzone(p, modell, faktor: float) -> Zone | None:
    """Laengenmass zwischen zwei ebenen Seiten: die zweite Seite liegt zwischen zwei Ebenen bei Mindest- und
    Hoechstmass, gemessen von der Seite mit der groesseren Flaeche (Bezugsseite; ohne Ursprungsangabe gewaehlt)."""
    from .scanpruefung import _seiten
    from .toleranzkette import _aussen_normale
    hoechst, mindest = p.grenzen()
    if hoechst is None or mindest is None or p.nennwert is None or hoechst <= mindest:
        return None
    seiten = _seiten(modell, set(p.flaechen))
    if seiten is None or any(art != "ebene" for _o, _i, art in seiten[1]):
        return None
    n, gruppen = seiten
    formen = [[modell.flaechen[i] for i in sorted(idx)] for _o, idx, _a in gruppen]
    ref = 0 if _flaechen_inhalt(formen[0]) >= _flaechen_inhalt(formen[1]) else 1
    andere = 1 - ref
    s = 1.0 if gruppen[andere][0] > gruppen[ref][0] else -1.0  # groesseres Mass: weiter von der Bezugsseite weg
    z = Zone(breite=hoechst - mindest, faktor=faktor, art="mass")
    for f in formen[andere]:
        aus = float(np.sign(_aussen_normale(f) @ n)) or 1.0
        for grenze in (hoechst, mindest):
            z.dazu(_versatz(f, s * (grenze - p.nennwert) * faktor * aus))
    z.hinweise.append(tr("Längenmaß: Zone der zweiten Seite, gemessen von der größeren Fläche (Bezugsseite)"))
    return z if z.formen else None


def _winkelzone(p, modell, faktor: float) -> Zone | None:
    """Winkelmass zwischen zwei Ebenengruppen: die zweite Gruppe um die Schnittlinie auf Mindest- und
    Hoechstwinkel gedreht (Bezug: groessere Flaeche)."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    from .toleranzkette import _ebene_oder_achse
    hoechst, mindest = p.grenzen()
    if hoechst is None or mindest is None or p.nennwert is None or hoechst <= mindest:
        return None
    gruppen: list[list] = []
    for i in sorted(p.flaechen):
        g = _ebene_oder_achse(modell.flaechen[i]) if i < len(modell.flaechen) else None
        if g is None or g[0] != "ebene":
            continue
        for gr in gruppen:
            if abs(abs(float(gr[1] @ g[2])) - 1) < 1e-6:
                gr[2].append(modell.flaechen[i])
                break
        else:
            gruppen.append([g[1], g[2] / np.linalg.norm(g[2]), [modell.flaechen[i]]])
    if len(gruppen) != 2:
        return None
    ref = 0 if _flaechen_inhalt(gruppen[0][2]) >= _flaechen_inhalt(gruppen[1][2]) else 1
    (p1, n1, _), (p2, n2, formen) = gruppen[ref], gruppen[1 - ref]
    achse = np.cross(n1, n2)
    if np.linalg.norm(achse) < 1e-9:
        return None
    achse /= np.linalg.norm(achse)
    # Punkt auf beiden Ebenen (kleinste Norm)
    a = np.array([n1, n2, achse])
    punkt = np.linalg.solve(a, np.array([n1 @ p1, n2 @ p2, 0.0]))

    def winkel(n):  # Winkel wie im Mass angegeben: w oder 180 - w, naeher am Nennwert
        w = float(np.degrees(np.arccos(np.clip(abs(n1 @ n), -1, 1))))
        return min((w, 180 - w), key=lambda x: abs(x - p.nennwert))

    def gedreht(n, grad):
        k = np.array([[0, -achse[2], achse[1]], [achse[2], 0, -achse[0]], [-achse[1], achse[0], 0]])
        r = np.eye(3) + np.sin(np.radians(grad)) * k + (1 - np.cos(np.radians(grad))) * k @ k
        return r @ n
    vz = 1.0 if winkel(gedreht(n2, 0.01)) > winkel(n2) else -1.0  # Drehsinn, der den Winkel vergroessert
    z = Zone(breite=float(np.radians(hoechst - mindest)), faktor=faktor, art="mass")
    for grenze in (hoechst, mindest):
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(*map(float, punkt)), gp_Dir(*map(float, achse))),
                      float(np.radians(vz * (grenze - p.nennwert) * faktor)))
        for f in formen:
            z.dazu(BRepBuilderAPI_Transform(f, t, True).Shape())
    z.hinweise.append(tr("Winkelmaß: zweite Fläche um die Schnittlinie auf Mindest- und Höchstwinkel gedreht"))
    return z if z.formen else None


def _ist_laengenmass(p) -> bool:
    return p.art == "mass" and p.nennwert is not None and p.typ not in GROESSE and "Angular" not in (p.typ or "")


def breite(p) -> float | None:
    """Breite, nach der die Ueberhoehung bemessen wird (Toleranzwert bzw. Radiusband einer Masstoleranz)."""
    if not p.flaechen:
        return None
    if p.art == "mass" and p.typ in GROESSE:
        g = _massgrenzen(p)
        return None if g is None else (g[0] - g[1]) * g[2]
    if p.art == "mass" and p.nennwert is not None:  # Laengen- und Winkelmasse (Winkel: Breite ~ 10 mm Hebel)
        h, m = p.grenzen()
        if h is None or m is None or h <= m:
            return None
        return (h - m) * (np.radians(1) * 10 if "Angular" in (p.typ or "") else 1.0)
    if p.art != "toleranz" or p.wert is None:
        return None
    if p.wert <= 0 and not p.material:  # Nulltoleranz nur mit M/L sinnvoll (Zone = Bonus)
        return None
    return float(p.wert)


def zone(p, modell, sichtbar_mindest: float = 0.0, alle_pmi=None, faktor: float | None = None) -> Zone | None:
    """Zone einer PMI; sichtbar_mindest: Mindestbreite fuer die Anzeige (mm), sonst wahre Breite; faktor: feste
    Ueberhoehung (mehrere Zonen gemeinsam). alle_pmi: fuer das Mass eines Elements (Huellen, Bonus bei M/L)."""
    z = _zone(p, modell, sichtbar_mindest, alle_pmi, faktor)
    if z is not None:
        z.flaechen = set(p.flaechen)
    return z


def _zone(p, modell, sichtbar_mindest: float = 0.0, alle_pmi=None, faktor: float | None = None) -> Zone | None:
    b = breite(p)
    if b is None:
        return None
    if faktor is None:
        faktor = max(1.0, sichtbar_mindest / b) if sichtbar_mindest > 0 and b > 0 else 1.0
    flaechen = [modell.flaechen[i] for i in sorted(p.flaechen) if i < len(modell.flaechen)]
    if p.art == "mass" and p.typ in GROESSE:
        return _masszone(p, flaechen, faktor)
    if p.art == "mass" and "Angular" in (p.typ or ""):
        return _winkelzone(p, modell, faktor)
    if p.art == "mass":
        return _laengenzone(p, modell, faktor)
    t = b
    durchmesser = "Diameter" in p.modifikatoren or p.zone == "Diameter"
    z = None
    if "SphericalDiameter" in p.modifikatoren:
        z = _kugelzone(p, flaechen, t, faktor, alle_pmi)
    if z is None and durchmesser and (p.typ in ACHSZONE or p.typ in ACHSE_MIT_DURCHMESSER):
        z = _achszone(p, modell, flaechen, t, faktor, alle_pmi)
    if z is None and not durchmesser and p.typ in MITTELEBENE and _mittelebene_gemeint(p, alle_pmi):
        z = _mittelebenenzone(p, flaechen, t, faktor)
    if z is None and p.typ in LAUF:
        z = _laufzone(p, modell, flaechen, t, faktor, alle_pmi)
    if z is None and p.typ == "CircularityOrRoundness":
        z = _querschnittzone(p, flaechen, t, faktor)
    if z is None and (p.typ in FLAECHENZONE or p.typ in ACHSZONE):
        z = _flaechenzone(p, flaechen, t, faktor)
    if z is not None:
        z.hinweise += _weitere_hinweise(p)
        _hierarchie(z, p, modell, alle_pmi, faktor)
    return z


def _hierarchie(z: Zone, p, modell, alle_pmi, faktor: float):
    """Form-/Richtungszone liegt in der Zone der naechsthoeheren Toleranz an denselben Flaechen: diese als Huelle
    zeigen; ist die untergeordnete Toleranz nicht kleiner, ist sie wirkungslos (Hinweis)."""
    q = _uebergeordnet(p, alle_pmi)
    if q is None:
        return
    oben = zone(q, modell, faktor=faktor)  # ohne alle_pmi: keine weitere Stufe, keine Rekursion
    if oben is not None:
        for f in oben.formen:
            z.dazu(f, HUELLE)
    z.hinweise.append(tr("liegt in der Zone von {} (PMI {})").format(q.wert_text(), q.nummer))
    if p.wert is not None and p.wert >= q.wert:
        z.hinweise.append(tr("Widerspruch: {:.4g} ist nicht kleiner als {:.4g} – die Angabe ist ohne Wirkung").format(
            p.wert, q.wert))


def _mittelebene_gemeint(p, alle_pmi) -> bool:
    """Symmetrie und Position an zwei Ebenen meinen die Mittelebene; Richtungs- und Geradheitstoleranzen nur, wenn
    die Flaechen ein Groessenmasselement sind (ein Mass auf genau diesen Flaechen), sonst gilt jede Flaeche."""
    if p.typ in ("Symmetry", "Position"):
        return True
    return any(m.art == "mass" and m.flaechen == p.flaechen for m in alle_pmi or [])


def _weitere_hinweise(p) -> list[str]:
    """Angaben, die die Zone ergaenzen, aber nicht als Geometrie gezeigt werden."""
    out = []
    for m in p.modifikatoren:
        if str(m).startswith("je "):
            out.append(tr("gilt je Teillänge {}").format(str(m)[3:]))
    if p.typ in ("Parallelism", "Perpendicularity", "Angularity") and not p.zone == "Projected":
        out.append(tr("Richtungszone: in der Lage frei verschiebbar"))
    if p.typ in ("Flatness", "Straightness", "CircularityOrRoundness", "Cylindricity") or \
            (p.typ in ("ProfileOfSurface", "ProfileOfLine") and not p.bezuege):
        out.append(tr("Formzone: in Lage und Richtung frei"))
    if p.typ in ("CircularRunout", "ProfileOfLine", "CircularityOrRoundness", "Concentricity"):
        out.append(tr("gilt je Querschnitt"))
    return out


def zonen(liste, modell, sichtbar_mindest: float = 0.0, alle_pmi=None) -> list[tuple[object, Zone]]:
    """Zonen mehrerer PMI (gewaehlte, auf gewaehlten Flaechen oder alle) mit gemeinsamer Ueberhoehung."""
    breiten = [b for p in liste for b in [breite(p)] if b]  # Nulltoleranzen (M/L) bestimmen sie nicht
    # eine Ueberhoehung fuer alle, damit die Zonen vergleichbar bleiben; bemessen an der mittleren Breite, sonst
    # wuerde eine sehr enge Zone alle anderen riesig machen
    faktor = max(1.0, sichtbar_mindest / float(np.median(breiten))) if sichtbar_mindest > 0 and breiten else 1.0
    return [(p, z) for p in liste for z in [zone(p, modell, alle_pmi=alle_pmi, faktor=faktor)] if z is not None]


# --- Allgemeintoleranzen ---

# ISO 2768-1: Grenzabmasse (+-) fuer Laengenmasse ohne Toleranzangabe, Nennmassbereiche bis (mm)
ISO2768_1_BEREICHE = (3, 6, 30, 120, 400, 1000, 2000, 4000)
ISO2768_1 = {"f": (0.05, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, None),
             "m": (0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 2.0),
             "c": (0.2, 0.3, 0.5, 0.8, 1.2, 2.0, 3.0, 4.0),
             "v": (None, 0.5, 1.0, 1.5, 2.5, 4.0, 6.0, 8.0)}
# ISO 2768-2: Geradheit und Ebenheit, Nennlaengenbereiche bis (mm)
ISO2768_2_BEREICHE = (10, 30, 100, 300, 1000, 3000)
ISO2768_2 = {"H": (0.02, 0.05, 0.1, 0.2, 0.3, 0.4),
             "K": (0.05, 0.1, 0.2, 0.4, 0.6, 0.8),
             "L": (0.1, 0.2, 0.4, 0.8, 1.2, 1.6)}


def _tabelle(wert: float, bereiche, zeile) -> float | None:
    for grenze, t in zip(bereiche, zeile):
        if wert <= grenze:
            return t
    return None


def iso2768_laenge(klasse: str, nennmass: float) -> float | None:
    """Grenzabmass +- nach ISO 2768-1 (None: ausserhalb der Tabelle oder nicht festgelegt)."""
    if klasse not in ISO2768_1 or nennmass < 0.5:
        return None
    return _tabelle(nennmass, ISO2768_1_BEREICHE, ISO2768_1[klasse])


def iso2768_ebenheit(klasse: str, laenge: float) -> float | None:
    """Ebenheits-/Geradheitstoleranz nach ISO 2768-2."""
    if klasse not in ISO2768_2:
        return None
    return _tabelle(laenge, ISO2768_2_BEREICHE, ISO2768_2[klasse])


@dataclass
class Allgemein:
    """Gewaehlte Allgemeintoleranzen: ISO 2768 Klasse (z. B. "m", "K") und/oder ISO 22081 Profilwert (mm)."""
    laenge: str = ""  # f, m, c, v
    form: str = ""  # H, K, L
    profil: float | None = None  # ISO 22081: Flaechenprofil t

    def leer(self) -> bool:
        return not self.laenge and not self.form and not self.profil

    def text(self) -> str:
        teile = []
        if self.laenge or self.form:
            teile.append(f"ISO 2768-{self.laenge}{self.form}")
        if self.profil:
            teile.append(f"ISO 22081 ⌓{self.profil:g}")
        return ", ".join(teile)


def allgemein_aus_hinweisen(pmi) -> Allgemein | None:
    """Allgemeintoleranzen aus Hinweistexten (z. B. "ISO 2768-mK", "ISO 22081 ... 0.5"), sonst None."""
    texte = " ".join(p.nur_grafik_text or p.name or "" for p in pmi if p.art == "hinweis")
    a = Allgemein()
    m = re.search(r"2768\s*-?\s*([fmcv])\s*-?\s*([HKL])?", texte)
    if m:
        a.laenge, a.form = m.group(1), m.group(2) or ""
    m = re.search(r"22081\D{0,40}?(\d+[.,]\d+|\d+)", texte)
    if m:
        a.profil = float(m.group(1).replace(",", "."))
    return None if a.leer() else a


def _ausdehnung(flaeche) -> float:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(flaeche, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    return float(max(x1 - x0, y1 - y0, z1 - z0))


def allgemein_zone(modell, pmi, allgemein: Allgemein, sichtbar_mindest: float = 0.0,
                   faktor: float | None = None, nur: set[int] | None = None) -> Zone | None:
    """Zonen der Allgemeintoleranzen fuer Flaechen ohne eigene Mass- oder Toleranzangabe (nur: Flaechenindizes)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    if allgemein is None or allgemein.leer():
        return None
    belegt = {i for p in pmi if p.art in ("mass", "toleranz") for i in p.flaechen}
    teile = []  # (Flaeche, aus dem Material, ins Material, Index)
    for i, f in enumerate(modell.flaechen):
        if i in belegt or (nur is not None and i not in nur) or BRep_Tool.Surface(f) is None:
            continue
        if allgemein.profil:
            teile.append((f, allgemein.profil / 2, -allgemein.profil / 2, i))
            continue
        s = BRepAdaptor_Surface(f, True)
        if s.GetType() == GeomAbs_Plane and allgemein.form:
            t = iso2768_ebenheit(allgemein.form, _ausdehnung(f))
            if t:
                teile.append((f, t / 2, -t / 2, i))
        elif s.GetType() == GeomAbs_Cylinder and allgemein.laenge:
            a = iso2768_laenge(allgemein.laenge, 2 * s.Cylinder().Radius())
            if a:
                teile.append((f, a / 2, -a / 2, i))  # Radius aendert sich um die Haelfte des Durchmesserabmasses
    if not teile:
        return None
    schmalste = min(o - u for _, o, u, _ in teile)
    if faktor is None:
        faktor = max(1.0, sichtbar_mindest / schmalste) if sichtbar_mindest > 0 else 1.0
    z = Zone(breite=schmalste, faktor=faktor, art="allgemein")
    for f, o, u, i in teile:
        z.dazu(_versatz(f, o * faktor), ALLGEMEIN, i)
        z.dazu(_versatz(f, u * faktor), ALLGEMEIN, i)
    z.hinweise.append(tr("Allgemeintoleranzen {} auf {} Flächen").format(allgemein.text(), len(teile)))
    return z if z.formen else None
