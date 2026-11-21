"""Nominale Evolventenraeder mit radialem Fussanschluss aus der Stirnradauslegung."""

from dataclasses import dataclass
from math import atan, cos, hypot, isclose, isfinite, pi, radians, sin, sqrt, tan

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCC.Core.TopLoc import TopLoc_Location

from ..i18n import tr
from .baum import Knoten, lies_baum
from .maschinenelemente import berechne
from .pmi import MASS, Pmi
from .teilausgabe import _flaechen, _step
from .zeichnungskoerper import schreibe_mit_massangaben


def _lage(winkel, x=0., z=0.):
    lage = gp_Trsf()
    lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1)), winkel)
    lage.SetTranslationPart(gp_Vec(x, 0, z))
    return TopLoc_Location(lage)


def _polar(radius, winkel):
    return gp_Pnt(radius*cos(winkel), radius*sin(winkel), 0.)


def _bogen(radius, anfang, ende):
    from OCC.Core.GC import GC_MakeArcOfCircle
    bogen = GC_MakeArcOfCircle(_polar(radius, anfang), _polar(radius, (anfang+ende)/2), _polar(radius, ende))
    return BRepBuilderAPI_MakeEdge(bogen.Value()).Edge()


@dataclass(frozen=True)
class Zahnprofil:
    z: int
    grund: float
    fuss: float
    kopf: float
    halbwinkel: float

    @classmethod
    def aus_nennmassen(cls, z, modul, alpha):
        teilradius = modul*z/2
        return cls(z, teilradius*cos(alpha), teilradius-1.25*modul, teilradius+modul,
                   pi/(2*z)+tan(alpha)-alpha)

    def abrollweg(self, radius):
        return sqrt(max(0., (radius-self.grund)*(radius+self.grund)))

    def winkel(self, t):
        return self.halbwinkel - (t-atan(t))

    def zahnkanten(self):
        from OCC.Core.GeomAPI import GeomAPI_Interpolate
        from OCC.Core.TColgp import TColgp_HArray1OfPnt

        start, ende = (self.abrollweg(r)/self.grund for r in (self.fuss, self.kopf))
        unten, oben = self.winkel(start), self.winkel(ende)
        if not 0 < oben < unten < pi/self.z:
            raise ValueError(tr("Die Zahnkontur schließt sich mit diesen Eingaben nicht."))
        kanten = []
        for seite in (-1, 1):
            if seite == -1 and self.grund-self.fuss > 1e-7:
                kanten.append(BRepBuilderAPI_MakeEdge(_polar(self.fuss, -unten), _polar(self.grund, -unten)).Edge())
            punkte = TColgp_HArray1OfPnt(1, 17)
            for i in range(17):
                t = start+(ende-start)*(i if seite < 0 else 16-i)/16
                punkte.SetValue(i+1, _polar(self.grund*hypot(1,t), seite*self.winkel(t)))
            kurve = GeomAPI_Interpolate(punkte, False, 1e-8)
            kurve.Perform()
            kanten.append(BRepBuilderAPI_MakeEdge(kurve.Curve()).Edge())
            if seite == -1:
                kanten.append(_bogen(self.kopf, -oben, oben))
            elif self.grund-self.fuss > 1e-7:
                kanten.append(BRepBuilderAPI_MakeEdge(_polar(self.grund, unten), _polar(self.fuss, unten)).Edge())
        kanten.append(_bogen(self.fuss, unten, 2*pi/self.z-unten))
        return kanten

    def koerper(self, breite, pruefe):
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCC.Core.TopoDS import topods
        zahn = self.zahnkanten()
        draht = BRepBuilderAPI_MakeWire()
        for i in range(self.z):
            pruefe()
            lage = _lage(2*pi*i/self.z)
            for kante in zahn:
                draht.Add(topods.Edge(kante.Moved(lage)))
        if not draht.IsDone() or not draht.Wire().Closed():
            raise ValueError(tr("Die Zahnkontur schließt sich mit diesen Eingaben nicht."))
        stirn = BRepBuilderAPI_MakeFace(draht.Wire()).Face()
        return BRepPrimAPI_MakePrism(stirn, gp_Vec(0,0,breite)).Shape()


def _radmasse(modell, teil, profil, breite):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    stirn, kopf, fuss = set(), set(), set()
    for flaeche in _flaechen(teil.form):
        i = modell.flaechen_index(flaeche)
        s = BRepAdaptor_Surface(flaeche)
        if s.GetType() == GeomAbs_Plane and abs(s.Plane().Axis().Direction().Z()) > 1-1e-8:
            stirn.add(i)
        elif s.GetType() == GeomAbs_Cylinder:
            radius = s.Cylinder().Radius()
            if isclose(radius, profil.kopf, abs_tol=1e-7):
                kopf.add(i)
            elif isclose(radius, profil.fuss, abs_tol=1e-7):
                fuss.add(i)
    if None in stirn|kopf|fuss or (len(stirn),len(kopf),len(fuss)) != (2,profil.z,profil.z):
        raise ValueError(tr("Zahnkopf, Zahnfuß oder Stirnflächen konnten nicht eindeutig zugeordnet werden."))
    return [Pmi(MASS, "Location_LinearDistance", name=tr("Zahnbreite b"), nennwert=breite, flaechen=stirn),
            Pmi(MASS, "Size_Diameter", name=tr("Kopfkreis da"), nennwert=2*profil.kopf, flaechen=kopf),
            Pmi(MASS, "Size_Diameter", name=tr("Fußkreis df"), nennwert=2*profil.fuss, flaechen=fuss)]


def schreibe_stirnradpaar(ziel, eingaben, breite_ritzel, breite_rad, pruefe=lambda: None):
    """Zwei benannte Komponenten mit gemeinsamer Mittelebene am Nennachsabstand schreiben."""
    # Die Geometrie folgt aus den Nennmassen und ist vom Betriebsmoment unabhaengig.
    masse = berechne("stirnrad", {**eingaben, "t": 0.})
    breiten = {tr("Ritzel"): breite_ritzel, tr("Rad"): breite_rad}
    if any(not isfinite(b) or b <= 1e-6 for b in (*breiten.values(), eingaben["m"])):
        raise ValueError(tr("Maße außerhalb des STEP-Exportbereichs."))
    alpha = radians(eingaben["alpha"])
    a, b = (Zahnprofil.aus_nennmassen(int(eingaben[z]), eingaben["m"], alpha) for z in ("z1", "z2"))
    raeder = {tr("Ritzel"): a, tr("Rad"): b}
    # Der Kontakt am Kopf des einen Rads muss auf der Evolvente des Gegenrads liegen.
    wirkstrecke = masse["a"]*sin(alpha)
    if any(rad.abrollweg(rad.kopf)+partner.abrollweg(partner.fuss) > wirkstrecke+1e-8
           for rad, partner in ((a,b),(b,a))):
        raise ValueError(tr("Der Zahnkopf greift unter den nutzbaren Evolventenbereich des Gegenrads."))
    if a.abrollweg(a.kopf)+b.abrollweg(b.kopf)-wirkstrecke < pi*eingaben["m"]*cos(alpha):
        raise ValueError(tr("Die Profilüberdeckung ist für einen durchgehenden Eingriff zu klein."))

    def geometrie(pfad):
        kinder = [Knoten(name, profil.koerper(breiten[name], pruefe), nummer=i)
                  for i, (name, profil) in enumerate(raeder.items(), 1)]
        # Ein Zahn des Ritzels steht im Achsschnitt in der Mitte einer Zahnluecke am Rad.
        lage = _lage(0. if b.z % 2 else pi/b.z, masse["a"], (breite_ritzel-breite_rad)/2)
        kinder[1].form = kinder[1].form.Moved(lage)
        wurzel = Knoten(tr("Geradverzahntes Stirnradpaar"), None, kinder, baugruppe=True)
        pruefe()
        if not _step(pfad, wurzel, {k.nummer: k.form for k in kinder}, None, {}):
            raise ValueError(tr("Der Körper konnte nicht als STEP geschrieben werden."))

    def merkmale(modell):
        teile = list(lies_baum(modell).blaetter())
        if len(teile) != 2 or {k.name for k in teile} != raeder.keys():
            raise ValueError(tr("Die beiden Räder konnten beim STEP-Export nicht zugeordnet werden."))
        ziele = [p for k in teile for p in _radmasse(modell, k, raeder[k.name], breiten[k.name])]
        for i, p in enumerate(ziele, 1):
            p.nummer, p.step_id, p.quelle = i, -i, "eigen"
        return ziele

    return schreibe_mit_massangaben(ziel, geometrie, merkmale, pruefe)
