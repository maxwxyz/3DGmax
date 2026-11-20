"""Rechteckige Platten aus bemassten orthogonalen Zeichnungsansichten aufbauen."""

from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy import ndimage

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe
from .pmi import Pmi


@dataclass(frozen=True)
class Plattenbohrung:
    x: float
    y: float
    durchmesser: Pmi
    tiefe: Pmi | None = None


def rechteckgrenzen(bild, box):
    """Vollstaendige achsparallele Aussenkontur einer ungebohrten Platte im Blattausschnitt."""
    h, w = bild.shape[:2]
    l, t, r, b = np.rint(np.clip(box, 0., 1.) * [w, h, w, h]).astype(int)
    tinte = bild[t:b, l:r, :3].min(axis=2) < 245
    ys, xs = np.nonzero(tinte)
    if not xs.size:
        return None
    x1, x2, y1, y2 = xs.min(), xs.max(), ys.min(), ys.max()
    if min(x1, y1, r-l-1-x2, b-t-1-y2) < 1 or min(x2-x1, y2-y1) < 12:
        return None
    kontur = tinte[y1:y2+1, x1:x2+1]
    # Jede Kante muss durchlaufen. Innenlinien, Bohrungen und zusaetzliche Konturen bleiben offen.
    rand = max(2, min(12, round(min(kontur.shape)*.10)))
    kanten = []
    for lage in (kontur, kontur[::-1], kontur.T, kontur.T[::-1]):
        band = lage[:rand, rand:-rand]
        strich = np.flatnonzero(band.all(axis=1))
        if not len(strich) or len(strich) != 1+strich[-1]-strich[0]:
            return None
        kanten.append(strich)
    oben, unten, links, rechts = kanten
    innen = kontur[oben[-1]+1:len(kontur)-unten[-1]-1, links[-1]+1:kontur.shape[1]-rechts[-1]-1]
    if innen.any() or ndimage.label(kontur)[1] != 1:
        return None
    geschlossen = ndimage.binary_fill_holes(kontur, structure=np.ones((3,3), dtype=bool))
    if not geschlossen[kontur.shape[0]//2, kontur.shape[1]//2]:
        return None
    # Die Mittellinien der Striche statt der aeusseren Tintenraender verwenden.
    return l+x1+links.mean(), t+y1+oben.mean(), l+x2-rechts.mean(), t+y2-unten.mean()


def rechteckansicht(bild, box):
    grenzen = rechteckgrenzen(bild, box)
    if grenzen is not None:
        l, t, r, b = grenzen
        return r-l, b-t


def plattenmasse(texte, faktor, grundriss, vorderansicht=None):
    if grundriss is None:
        raise ValueError(tr("Die rechteckige Außenkontur im Grundriss einrahmen."))
    masse = []
    for text, feld in zip(texte, (tr("Breite"), tr("Höhe"), tr("Dicke")), strict=True):
        p = lese_angabe(text, faktor) if text.strip() else None
        if (p is None or p.typ != "Location_LinearDistance" or p.nennwert is None
                or not np.isfinite(p.nennwert) or p.nennwert <= 0 or "Hilfsmass" in p.modifikatoren):
            raise ValueError(tr("Für {} ein positives Längenmaß mit geklärter Einheit angeben.").format(feld))
        if any(g is not None and (not np.isfinite(g) or g <= 0) for g in p.grenzen()):
            raise ValueError(tr("Die Grenzmaße für {} müssen positiv sein.").format(feld))
        masse.append(p)
    def passt(ansicht, quer, hoch):
        breite, hoehe = ansicht
        # Ein gemeinsamer Massstab muss beide gezeichneten Strecken innerhalb zweier Pixel treffen.
        return abs(breite*hoch-hoehe*quer) <= 2*(hoch+quer)
    x, y, z = (p.nennwert for p in masse)
    if not passt(grundriss, x, y):
        raise ValueError(tr("Breite und Höhe widersprechen dem Seitenverhältnis des Grundrisses."))
    if vorderansicht and not passt(vorderansicht, x, z):
        raise ValueError(tr("Breite und Dicke widersprechen dem Seitenverhältnis der Vorderansicht."))
    return masse


def _plattenform(masse, bohrungen):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopTools import TopTools_ListOfShape
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepPrimAPI_MakeBox(*(p.nennwert for p in masse)).Shape()
    if not bohrungen:
        return form
    platte, bohrer = TopTools_ListOfShape(), TopTools_ListOfShape()
    platte.Append(form)
    dicke = masse[2].nennwert
    zugabe = max(.01, dicke*.01)
    for bohrung in bohrungen:
        boden = dicke-bohrung.tiefe.nennwert if bohrung.tiefe else -zugabe
        achse = gp_Ax2(gp_Pnt(bohrung.x, bohrung.y, boden), gp_Dir(0, 0, 1))
        bohrer.Append(BRepPrimAPI_MakeCylinder(achse, bohrung.durchmesser.nennwert/2, dicke+zugabe-boden).Shape())
    schnitt = BRepAlgoAPI_Cut()
    schnitt.SetArguments(platte)
    schnitt.SetTools(bohrer)
    schnitt.Build()
    if not schnitt.IsDone() or not BRepCheck_Analyzer(schnitt.Shape()).IsValid():
        raise ValueError(tr("Die Bohrungen konnten nicht erzeugt werden."))
    return schnitt.Shape()


def _flaechenmasse(modell, masse, bohrungen):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
    paare = [set() for _ in masse]
    waende = [set() for _ in bohrungen]
    horizontal = {}
    for i, flaeche in enumerate(modell.flaechen):
        s = BRepAdaptor_Surface(flaeche)
        if s.GetType() == GeomAbs_Plane:
            ebene = s.Plane()
            achse = int(np.argmax(np.abs(ebene.Axis().Direction().Coord())))
            if achse == 2:
                horizontal[i] = ebene.Location().Z()
            else:
                paare[achse].add(i)
        elif s.GetType() == GeomAbs_Cylinder:
            z = s.Cylinder()
            ort = z.Location()
            treffer = [j for j, b in enumerate(bohrungen) if abs(ort.X()-b.x) < 1e-6
                       and abs(ort.Y()-b.y) < 1e-6 and abs(z.Radius()-b.durchmesser.nennwert/2) < 1e-6]
            if len(treffer) != 1:
                raise ValueError(tr("Die Bohrungsflächen sind nicht eindeutig."))
            waende[treffer[0]].add(i)
    if not all(waende):
        raise ValueError(tr("Die Bohrungsflächen sind nicht eindeutig."))
    dicke = masse[2].nennwert
    deckel = {i for i, z in horizontal.items() if abs(z-dicke) < 1e-7}
    paare[2] = deckel | {i for i, z in horizontal.items() if abs(z) < 1e-7}
    if len(deckel) != 1 or any(len(paar) != 2 for paar in paare):
        raise ValueError(tr("Die gegenüberliegenden Plattenflächen sind nicht eindeutig."))
    alle = [*masse, *(b.durchmesser for b in bohrungen)]
    flaechen = paare + waende
    if any(b.tiefe for b in bohrungen):
        from .vergleich_geo import _nachbarn
        nachbarn = _nachbarn(modell.flaechen, modell.flaechen_index)
        for b, wand in zip(bohrungen, waende, strict=True):
            if b.tiefe is None:
                continue
            angrenzend = set().union(*(nachbarn[i] for i in wand))
            boden = {i for i in (angrenzend & horizontal.keys()) - paare[2]
                     if abs(horizontal[i] - (dicke-b.tiefe.nennwert)) < 1e-6}
            if len(boden) != 1 or not deckel <= angrenzend:
                raise ValueError(tr("Eintrittsfläche und Bohrungsgrund sind nicht eindeutig."))
            alle.append(b.tiefe)
            flaechen.append(deckel | boden)
    return [replace(p, flaechen=f, quelle="eigen", nummer=i, step_id=-i)
            for i, (p, f) in enumerate(zip(alle, flaechen, strict=True), 1)]


def schreibe_platte(ziel, masse, bohrungen=()):
    """Geometrie und flaechenbezogene Masse mit Darstellung als AP242 speichern."""
    from OCC.Core.DESTEP import DESTEP_Parameters
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from .laden import LadeFehler, lade_step
    from .step_schreiben import schreibe

    bohrungen = [b if isinstance(b, Plattenbohrung) else Plattenbohrung(*b) for b in bohrungen]
    ziel = Path(ziel)
    with TemporaryDirectory(dir=ziel.parent) as tmp:
        roh = str(Path(tmp) / "geometry.stp")
        fertig = Path(tmp) / "model.stp"
        form = _plattenform(masse, bohrungen)
        writer = STEPControl_Writer()
        parameter = DESTEP_Parameters()
        parameter.WriteSchema = parameter.WriteMode_StepSchema_AP242DIS
        if writer.Transfer(form, STEPControl_AsIs, parameter) != IFSelect_RetDone or writer.Write(roh) != IFSelect_RetDone:
            raise ValueError(tr("Der Plattenkörper konnte nicht als STEP geschrieben werden."))
        try:
            modell = lade_step(roh)
        except LadeFehler as e:
            raise ValueError(str(e)) from e
        merkmale = _flaechenmasse(modell, masse, bohrungen)
        bericht = schreibe(roh, str(fertig), merkmale, modell)
        if len(bericht.neu) != len(merkmale) or len(bericht.dargestellt) != len(merkmale):
            raise ValueError(tr("Die Maßangaben konnten nicht vollständig als STEP-PMI geschrieben werden."))
        fertig.replace(ziel)
        return len(merkmale)
