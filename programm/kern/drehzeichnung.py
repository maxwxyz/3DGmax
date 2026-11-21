"""Stufenzylindrische Vollwellen aus einer bemassten Laengsansicht rekonstruieren."""

from dataclasses import dataclass, replace

import numpy as np

from ..i18n import tr
from .zeichnungsabgleich import lese_angabe, musteranzahl
from .zeichnungskoerper import schreibe_bemassten_koerper


@dataclass(frozen=True)
class Sitzkontur:
    box: tuple  # Blattkoordinaten des Abschnitts
    laenge: float  # Pixel an den Strichmitten
    durchmesser: float


def _laeufe(spur):
    grenzen = np.flatnonzero(np.diff(spur, prepend=False, append=False))
    return grenzen.reshape(-1,2)


def _aussenlinien(spalte, mitte):
    laeufe = _laeufe(spalte)
    if len(laeufe) == 3:
        a, b = laeufe[1]
        if abs((a+b-1)/2-mitte) > 1:
            return None
    elif len(laeufe) != 2:
        return None
    oben, unten = laeufe[0], laeufe[-1]
    o, u = (v.mean()-.5 for v in (oben, unten))
    if abs((o+u)/2-mitte) > 1:
        return None
    stift = max(oben[1]-oben[0], unten[1]-unten[0])
    return u-o, stift


def _senkrechte(tinte, x, mitte, r1, r2, stift):
    # Auf beiden Schultern zwischen den Durchmessern die senkrechte Strichmitte suchen.
    radius = (r1+r2)/2
    lagen = []
    for vorzeichen in (-1, 1):
        spur = tinte[round(mitte+vorzeichen*radius)]
        treffer = [band.mean()-.5 for band in _laeufe(spur) if band[1]-band[0] <= stift+2
                   and abs(band.mean()-.5-x) <= stift+2]
        if len(treffer) != 1:
            return None
        lagen.append(treffer[0])
    return sum(lagen)/2 if abs(lagen[0]-lagen[1]) <= 1 else None


def _strichbild(tinte, grenzen, radien, mitte, stift):
    erlaubt = np.zeros_like(tinte)
    toleranz = stift/2+1
    def band(start, ende):
        return slice(max(0, int(np.ceil(start-toleranz))), int(np.floor(ende+toleranz))+1)

    for i, radius in enumerate(radien):
        x1, x2 = grenzen[i:i+2]
        for y in (mitte-radius, mitte+radius):
            streifen = band(y,y)
            erlaubt[streifen, band(x1,x2)] = True
            if not tinte[streifen, round(x1):round(x2)+1].any(axis=0).all():
                return False
    for i, x in enumerate(grenzen):
        vorher = radien[i-1] if i else 0.
        danach = radien[i] if i < len(radien) else 0.
        gross, klein = max(vorher,danach), min(vorher,danach)
        streifen = band(x,x)
        erlaubt[band(mitte-gross,mitte+gross), streifen] = True
        # Eine sichtbare Innenkante der Schulter geht ueber den ganzen kleineren Durchmesser.
        if klein:
            innen = np.arange(int(np.ceil(mitte-klein+toleranz+1)), int(np.ceil(mitte+klein-toleranz)))
            innen = innen[abs(innen-mitte) > toleranz]
            sichtbar = tinte[innen, streifen].any(axis=1)
            if sichtbar.any() and not sichtbar.all():
                return False
        for y1, y2 in ((mitte-gross, mitte-klein), (mitte+klein, mitte+gross)):
            if not tinte[round(y1):round(y2)+1, streifen].any(axis=1).all():
                return False
    erlaubt[band(mitte,mitte)] = True  # Durchgezogene oder gestrichelte Mittellinie
    return not (tinte & ~erlaubt).any()


def drehkontur(bild, box, senkrecht=False):
    """Abschnitte von links nach rechts bzw. oben nach unten in der Blattansicht."""
    h, w = bild.shape[:2]
    l,t,r,b = np.rint(np.clip(box,0,1)*[w,h,w,h]).astype(int)
    tinte = bild[t:b,l:r,:3].min(axis=2) < 245
    if senkrecht:
        tinte = tinte.T
    if not tinte.any() or tinte[0].any() or tinte[-1].any():
        return []
    ys, xs = np.nonzero(tinte)
    mitte = (ys.min()+ys.max())/2
    linien = [(x, *paar) for x in range(xs.min(), xs.max()+1)
              if (paar := _aussenlinien(tinte[:,x], mitte)) is not None]
    if not linien:
        return []
    stift = float(np.median([d for _,_,d in linien]))
    gruppen = []
    for x, dm, strich in linien:
        if strich > stift+1 or dm < 3*stift:
            continue
        if not gruppen or abs(gruppen[-1][0][1]-dm) > 1:
            gruppen.append([])
        gruppen[-1].append((x, dm))
    if not gruppen or any(len(g) < max(3,stift) for g in gruppen):
        return []
    radien = [np.median([dm for _,dm in g])/2 for g in gruppen]
    vermutet = [gruppen[0][0][0], *((a[-1][0]+b[0][0])/2 for a,b in zip(gruppen,gruppen[1:])), gruppen[-1][-1][0]]
    grenzen = [_senkrechte(tinte,x,mitte,r1,r2,stift)
               for x,r1,r2 in zip(vermutet, [0.,*radien], [*radien,0.], strict=True)]
    if any(x is None for x in grenzen):
        return []
    if grenzen[0] <= stift/2 or grenzen[-1] >= tinte.shape[1]-1-stift/2:
        return []
    if not _strichbild(tinte,grenzen,radien,mitte,stift):
        return []
    sitze = []
    for x1,x2,radius in zip(grenzen[:-1],grenzen[1:],radien,strict=True):
        y1, y2 = mitte-radius, mitte+radius
        rechteck = (y1,x1,y2,x2) if senkrecht else (x1,y1,x2,y2)
        box = tuple((np.asarray(rechteck)+[l,t,l,t])/[w,h,w,h])
        sitze.append(Sitzkontur(box, x2-x1, 2*radius))
    return sitze


def _mass(text, faktor, typ):
    if musteranzahl(text) or not (p := lese_angabe(text, faktor)) or p.typ != typ or p.nennwert is None:
        return None
    oben, unten = p.grenzen()
    if "Hilfsmass" in p.modifikatoren or (oben is not None and unten is not None and unten > oben):
        return None
    return p if all(np.isfinite(v) and v > 0 for v in (p.nennwert,oben,unten) if v is not None) else None


def drehmasse(kontur, zeilen, faktor):
    if not kontur:
        raise ValueError(tr("Die geschlossene Längsansicht des Drehteils einrahmen."))
    masse, pixel, mm = [], [], []
    schulter_px = schulter_mm = 0.
    for i, (sitz, (laengentext, dmtext)) in enumerate(zip(kontur,zeilen,strict=True),1):
        laenge = _mass(laengentext, faktor, "Location_LinearDistance")
        dm = _mass(dmtext, faktor, "Size_Diameter")
        if not laenge or not dm:
            raise ValueError(tr("Für Abschnitt {} Länge und Durchmesser mit Ø und geklärter Einheit angeben.").format(i))
        if masse:
            vorher = masse[-1][1]
            klein, gross = sorted((vorher,dm), key=lambda p: p.nennwert)
            if max(v for v in (klein.nennwert,*klein.grenzen()) if v is not None) >= min(
                    v for v in (gross.nennwert,*gross.grenzen()) if v is not None):
                raise ValueError(tr("Die Durchmessergrenzen benachbarter Abschnitte müssen die Schulter erhalten."))
        schulter_px += sitz.laenge
        schulter_mm += laenge.nennwert
        pixel.extend((sitz.durchmesser, sitz.laenge, schulter_px))
        mm.extend((dm.nennwert, laenge.nennwert, schulter_mm))
        masse.append((laenge, dm))
    if np.max((np.array(pixel)-2)/mm) > np.min((np.array(pixel)+2)/mm):
        raise ValueError(tr("Längen, Durchmesser oder Schulterlagen widersprechen der Längsansicht."))
    return masse


def _drehform(masse):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt
    profil = BRepBuilderAPI_MakePolygon()
    x = 0.
    profil.Add(gp_Pnt(0,0,0))
    for laenge, dm in masse:
        profil.Add(gp_Pnt(x,0,dm.nennwert/2))
        x += laenge.nennwert
        profil.Add(gp_Pnt(x,0,dm.nennwert/2))
    profil.Add(gp_Pnt(x,0,0))
    profil.Close()
    flaeche = BRepBuilderAPI_MakeFace(profil.Wire(), True).Face()
    return BRepPrimAPI_MakeRevol(flaeche, gp_Ax1(gp_Pnt(0,0,0),gp_Dir(1,0,0))).Shape()


def _sitzmasse(modell, masse):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from .vergleich_geo import _nachbarn
    nachbarn = _nachbarn(modell.flaechen, modell.flaechen_index)
    ebenen, zylinder = {}, {}
    for i, f in enumerate(modell.flaechen):
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Plane:
            ebenen[i] = s.Plane().Location().X()
        elif s.GetType() == GeomAbs_Cylinder:
            zylinder[i] = 2*s.Cylinder().Radius()
    x = 0.
    merkmale = []
    for laenge, dm in masse:
        ende = x+laenge.nennwert
        stirn = [{i for i, ort in ebenen.items() if abs(ort-ziel) < 1e-6} for ziel in (x,ende)]
        waende = [i for i,d in zylinder.items() if abs(d-dm.nennwert) < 1e-6 and
                  all(len(s) == 1 and s <= nachbarn[i] for s in stirn)]
        if len(waende) != 1:
            raise ValueError(tr("Zylinderwand und Stirnflächen eines Abschnitts sind nicht eindeutig."))
        for p, f in ((laenge, stirn[0] | stirn[1]), (dm, set(waende))):
            nr = len(merkmale)+1
            merkmale.append(replace(p,flaechen=f,nummer=nr,step_id=-nr,quelle="eigen"))
        x = ende
    return merkmale


def schreibe_drehteil(ziel, masse):
    return schreibe_bemassten_koerper(ziel, _drehform(masse), lambda modell: _sitzmasse(modell, masse))
