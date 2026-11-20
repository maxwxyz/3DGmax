"""Rechteckige Platten aus bemassten orthogonalen Zeichnungsansichten aufbauen."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy import ndimage

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe


def rechteckansicht(bild, box):
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
    return x2-x1-links.mean()-rechts.mean(), y2-y1-oben.mean()-unten.mean()


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


def schreibe_platte(ziel, masse):
    """Geometrie und drei Masse in einer AP242-Kopie mit Darstellung speichern."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.DESTEP import DESTEP_Parameters
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from .laden import LadeFehler, lade_step
    from .step_schreiben import schreibe

    ziel = Path(ziel)
    with TemporaryDirectory(dir=ziel.parent) as tmp:
        roh = str(Path(tmp) / "geometry.stp")
        fertig = Path(tmp) / "model.stp"
        form = BRepPrimAPI_MakeBox(*(p.nennwert for p in masse)).Shape()
        writer = STEPControl_Writer()
        parameter = DESTEP_Parameters()
        parameter.WriteSchema = parameter.WriteMode_StepSchema_AP242DIS
        if writer.Transfer(form, STEPControl_AsIs, parameter) != IFSelect_RetDone or writer.Write(roh) != IFSelect_RetDone:
            raise ValueError(tr("Der Plattenkörper konnte nicht als STEP geschrieben werden."))
        try:
            modell = lade_step(roh)
        except LadeFehler as e:
            raise ValueError(str(e)) from e
        paare = [set() for _ in masse]
        for i, flaeche in enumerate(modell.flaechen):
            normal = BRepAdaptor_Surface(flaeche).Plane().Axis().Direction().Coord()
            paare[int(np.argmax(np.abs(normal)))].add(i)
        if any(len(paar) != 2 for paar in paare):
            raise ValueError(tr("Die gegenüberliegenden Plattenflächen sind nicht eindeutig."))
        merkmale = [replace(p, flaechen=paar, quelle="eigen", nummer=i, step_id=-i)
                    for i,(p,paar) in enumerate(zip(masse, paare, strict=True),1)]
        bericht = schreibe(roh, str(fertig), merkmale, modell)
        if len(bericht.neu) != len(masse) or len(bericht.dargestellt) != len(masse):
            raise ValueError(tr("Die Maßangaben konnten nicht vollständig als STEP-PMI geschrieben werden."))
        fertig.replace(ziel)
