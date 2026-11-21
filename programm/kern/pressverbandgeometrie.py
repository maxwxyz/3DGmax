"""Nenngeometrie von Welle und Nabe mit Fertigungsabmassen an beiden Sitzflaechen."""

from math import isclose

from ..i18n import tr
from .maschinenelemente import pruefe_sitzmasse
from .pmi import MASS, Pmi
from .teilausgabe import _flaechen
from .zeichnungskoerper import schreibe_bemasste_baugruppe


def schreibe_pressverband(ziel, d, l, da, ei_w, es_w, ei_n, es_n):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

    pruefe_sitzmasse(d, l, da, ei_w, es_w, ei_n, es_n)
    welle = BRepPrimAPI_MakeCylinder(d/2, l).Shape()
    aussen = BRepPrimAPI_MakeCylinder(da/2, l).Shape()
    nabe = BRepAlgoAPI_Cut(aussen, welle).Shape()

    def teilmasse(modell, teil):
        innen = teil.name == tr("Nabe")
        abmasse = (ei_n, es_n) if innen else (ei_w, es_w)
        stirn, sitz, mantel = set(), set(), set()
        for f in _flaechen(teil.form):
            flaeche = BRepAdaptor_Surface(f)
            nr = modell.flaechen_index(f)
            if flaeche.GetType() == GeomAbs_Plane:
                stirn.add(nr)
            elif flaeche.GetType() == GeomAbs_Cylinder:
                dm = 2*flaeche.Cylinder().Radius()
                if isclose(dm, d, rel_tol=0., abs_tol=1e-7):
                    sitz.add(nr)
                elif innen and isclose(dm, da, rel_tol=0., abs_tol=1e-7):
                    mantel.add(nr)
        if None in stirn|sitz|mantel or (len(stirn), len(sitz), len(mantel)) != (2, 1, int(innen)):
            raise ValueError(tr("Die Sitzflächen konnten beim STEP-Export nicht eindeutig zugeordnet werden."))
        masse = [Pmi(MASS, "Size_Diameter", name=tr("Nabenbohrung") if innen else tr("Wellensitz"),
                     nennwert=d, unten=d+abmasse[0]/1000, oben=d+abmasse[1]/1000, grenzmass=True, flaechen=sitz),
                 Pmi(MASS, "Location_LinearDistance", name=tr("Wirksame Länge"), nennwert=l, flaechen=stirn)]
        if innen:
            masse.append(Pmi(MASS, "Size_Diameter", name=tr("Nabenaußendurchmesser"), nennwert=da, flaechen=mantel))
        return masse

    return schreibe_bemasste_baugruppe(ziel, tr("Pressverband"), {tr("Welle"): welle, tr("Nabe"): nabe}, teilmasse)
