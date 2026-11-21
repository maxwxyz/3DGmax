"""Stufenzylindrische Wellen aus einer bemassten Laengsansicht rekonstruieren."""

from dataclasses import dataclass, replace

import re

import numpy as np

from ..i18n import tr
from .axialbohrung import Gegenbohrungen, Sacklochspur, bohrdurchmesser_am_absatz, bohrspur, tintenlaeufe
from .pmi import Pmi
from .zeichnungsabgleich import lese_angabe, musteranzahl
from .zeichnungskoerper import schreibe_bemassten_koerper


@dataclass(frozen=True)
class Sitzkontur:
    box: tuple  # Blattkoordinaten des Abschnitts
    laenge: float  # Pixel an den Strichmitten
    durchmesser: float


def _aussenlinien(spalte, mitte):
    laeufe = tintenlaeufe(spalte)
    if len(laeufe) < 2:
        return None
    oben, unten = laeufe[0], laeufe[-1]
    o, u = (v.mean()-.5 for v in (oben, unten))
    if abs((o+u)/2-mitte) > 1:
        return None
    stift = max(oben[1]-oben[0], unten[1]-unten[0])
    return u-o, stift


def _senkrechte(tinte, x, mitte, r1, r2, stift):
    # Auf beiden Schultern zwischen den Durchmessern die senkrechte Strichmitte suchen.
    for anteil in (.5, .7, .3, .85, .15, .925, .075):
        radius = r1+anteil*(r2-r1)
        lagen = []
        for vorzeichen in (-1, 1):
            spur = tinte[round(mitte+vorzeichen*radius)]
            treffer = [band.mean()-.5 for band in tintenlaeufe(spur) if band[1]-band[0] <= stift+2
                       and abs(band.mean()-.5-x) <= stift+2]
            if len(treffer) == 1:
                lagen.append(treffer[0])
        if len(lagen) == 2 and abs(lagen[0]-lagen[1]) <= 1:
            return sum(lagen)/2
    return None


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
                return None
    for x, links, rechts in zip(grenzen,[0.,*radien],[*radien,0.],strict=True):
        radius = max(links,rechts)
        erlaubt[band(mitte-radius,mitte+radius), band(x,x)] = True
    erlaubt[band(mitte,mitte)] = True  # Durchgezogene oder gestrichelte Mittellinie
    spur = bohrspur(tinte, erlaubt, grenzen, mitte, radien, stift)
    if spur is None:
        return None
    bohrung, wandstift = spur
    for x, links, rechts in zip(grenzen,[0.,*radien],[*radien,0.],strict=True):
        gross, klein = max(links,rechts), min(links,rechts)
        streifen = tinte[:,band(x,x)].any(axis=1)
        dm, kern = bohrdurchmesser_am_absatz(bohrung,x,grenzen)
        material = max(klein, dm/2)
        for y1,y2 in ((mitte-gross,mitte-material),(mitte+material,mitte+gross)):
            if not streifen[round(y1):round(y2)+1].all():
                return None
        # Die Ansicht kann durchgezogene Stirnkanten oder eine offene Schnittkontur zeigen.
        abstand = abs(np.arange(len(streifen))-mitte)
        innen = (abstand < klein-toleranz) & (abstand > dm/2+max(toleranz,wandstift/2+1))
        oeffnung = (abstand < kern/2-wandstift/2-1) & (abstand > toleranz)
        for maske in (innen, oeffnung):
            if streifen[maske].any() and not streifen[maske].all():
                return None
        if innen.any() and not streifen[innen].any() and streifen[oeffnung].any():
            return None
    return bohrung


def drehprofil(bild, box, senkrecht=False):
    """Abschnitte in Blattrichtung und durchgehende oder blinde axiale Bohrspur in Pixeln."""
    h, w = bild.shape[:2]
    l,t,r,b = np.rint(np.clip(box,0,1)*[w,h,w,h]).astype(int)
    tinte = bild[t:b,l:r,:3].min(axis=2) < 245
    if senkrecht:
        tinte = tinte.T
    if not tinte.any() or tinte[0].any() or tinte[-1].any():
        return [], None
    ys, xs = np.nonzero(tinte)
    mitte = (ys.min()+ys.max())/2
    linien = [(x, *paar) for x in range(xs.min(), xs.max()+1)
              if (paar := _aussenlinien(tinte[:,x], mitte)) is not None]
    if not linien:
        return [], None
    stift = float(np.median([d for _,_,d in linien]))
    gruppen = []
    for x, dm, strich in linien:
        if strich > stift+1 or dm < 3*stift:
            continue
        if not gruppen or abs(gruppen[-1][0][1]-dm) > 1:
            gruppen.append([])
        gruppen[-1].append((x, dm))
    if not gruppen or any(len(g) < max(3,stift) for g in gruppen):
        return [], None
    radien = [np.median([dm for _,dm in g])/2 for g in gruppen]
    vermutet = [gruppen[0][0][0], *((a[-1][0]+b[0][0])/2 for a,b in zip(gruppen,gruppen[1:])), gruppen[-1][-1][0]]
    grenzen = [_senkrechte(tinte,x,mitte,r1,r2,stift)
               for x,r1,r2 in zip(vermutet, [0.,*radien], [*radien,0.], strict=True)]
    if any(x is None for x in grenzen):
        return [], None
    if grenzen[0] <= stift/2 or grenzen[-1] >= tinte.shape[1]-1-stift/2:
        return [], None
    bohrung = _strichbild(tinte,grenzen,radien,mitte,stift)
    if bohrung is None:
        return [], None
    sitze = []
    for x1,x2,radius in zip(grenzen[:-1],grenzen[1:],radien,strict=True):
        y1, y2 = mitte-radius, mitte+radius
        rechteck = (y1,x1,y2,x2) if senkrecht else (x1,y1,x2,y2)
        box = tuple((np.asarray(rechteck)+[l,t,l,t])/[w,h,w,h])
        sitze.append(Sitzkontur(box, x2-x1, 2*radius))
    return sitze, bohrung or None


def drehkontur(bild, box, senkrecht=False):
    """Nur die Laengsansicht einer Vollwelle akzeptieren."""
    sitze, bohrung = drehprofil(bild, box, senkrecht)
    return [] if bohrung else sitze


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
    masse = []
    for i, (_, (laengentext, dmtext)) in enumerate(zip(kontur,zeilen,strict=True),1):
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
        masse.append((laenge, dm))
    _massstab(kontur, masse)
    return masse


def _massstab(kontur, masse, weitere=()):
    paare = list(weitere)
    schulter_px = schulter_mm = 0.
    for sitz, (laenge, dm) in zip(kontur,masse,strict=True):
        schulter_px += sitz.laenge
        schulter_mm += laenge.nennwert
        paare.extend(((sitz.durchmesser,dm.nennwert), (sitz.laenge,laenge.nennwert), (schulter_px,schulter_mm)))
    pixel, mm = np.array(paare).T
    if np.max((pixel-2)/mm) > np.min((pixel+2)/mm):
        raise ValueError(tr("Längen, Durchmesser oder Schulterlagen widersprechen der Längsansicht."))


_DURCHGANG = re.compile(r"(?<!\w)(?:THR(?:OUGH|U)(?:\s+ALL)?|DURCHGANG(?:SBOHRUNG)?|DURCHGEHEND|DURCHG?)[.]?(?!\w)", re.I)


def axiale_tiefe(spur, text, faktor):
    if not isinstance(spur, Sacklochspur) and not text.strip():
        return None
    if not isinstance(spur, Sacklochspur):
        raise ValueError(tr("Für eine Bohrtiefe muss die Längsansicht einen flachen Bohrungsgrund zeigen."))
    return _bohrtiefe(text, faktor)


def _bohrtiefe(text, faktor):
    tiefe = _mass(text.strip().removeprefix("↧").strip(), faktor, "Location_LinearDistance")
    if not tiefe or tiefe.passung:
        raise ValueError(tr("Die Bohrtiefe ab der Eintrittsfläche laut Zeichnung angeben."))
    return tiefe


def _lese_bohrmass(text, faktor, blind):
    angabe = text.strip()
    durchgang = _DURCHGANG.search(angabe)
    if blind and durchgang:
        raise ValueError(tr("Die Durchgangsangabe widerspricht dem gezeichneten Bohrungsgrund."))
    if durchgang and (durchgang.start() == 0 or durchgang.end() == len(angabe)):
        angabe = (angabe[:durchgang.start()]+angabe[durchgang.end():]).strip()
    elif durchgang:
        raise ValueError(tr("Den Durchmesser der Axialbohrung mit Ø angeben."))
    dm = _mass(angabe, faktor, "Size_Diameter")
    if dm is None:
        raise ValueError(tr("Den Durchmesser der Axialbohrung mit Ø angeben."))
    return dm, durchgang


def axiales_bohrmass(kontur, masse, spur, stirn, text, faktor, tiefe=None):
    blind = isinstance(spur, Sacklochspur)
    if blind != (tiefe is not None):
        raise ValueError(tr("Bohrtiefe und gezeichneter Bohrungsgrund müssen zusammenpassen."))
    if spur is None and stirn is None and not text.strip():
        return None
    if stirn is not None and not stirn:
        raise ValueError(tr("Die Stirnansicht muss vollständige konzentrische Ringe zeigen."))
    dm, durchgang = _lese_bohrmass(text,faktor,blind)
    if spur is None and not (stirn and durchgang):
        raise ValueError(tr("Ohne durchgehende Wandlinien sind Stirnansicht und ein Ø-Maß mit Durchgangsangabe erforderlich."))
    rechts = blind and spur.von_rechts
    _pruefe_wand(masse, dm, tiefe, rechts)
    if blind:
        _massstab(kontur, masse, [(spur.durchmesser,dm.nennwert),(spur.tiefe,tiefe.nennwert)])
    elif spur is not None:
        _massstab(kontur, masse, [(spur,dm.nennwert)])
    if stirn:
        _pruefe_stirn(stirn,masse,[dm.nennwert],rechts if blind else None)
    return dm


def _pruefe_stirn(stirn, masse, bohrungen, rechts):
    aussen = [p.nennwert for _,p in masse]
    folgen = [aussen,aussen[::-1]] if rechts is None else [aussen[::-1] if rechts else aussen]
    sichtbar = {tuple(np.unique(np.maximum.accumulate(folge))) for folge in folgen}
    pixel = np.asarray(stirn)
    treffer = 0
    for durchmesser in sichtbar:
        mm = np.array([*bohrungen,*durchmesser])
        if len(mm) == len(pixel) and np.max((pixel-2)/mm) <= np.min((pixel+2)/mm):
            treffer += 1
    if treffer != 1:
        raise ValueError(tr("Die konzentrischen Ringe passen nicht zu Bohrung und Außendurchmessern."))


@dataclass(frozen=True)
class Bohrspitze:
    winkel: Pmi
    bis_spitze: bool

    def tiefen(self, dm, tiefe):
        hoehe = dm.nennwert/(2*np.tan(np.deg2rad(self.winkel.nennwert)/2))
        zylinder = tiefe.nennwert-hoehe if self.bis_spitze else tiefe.nennwert
        return zylinder,zylinder+hoehe


def _bohrzeile(dmtext, tiefentext, blind, faktor, i):
    try:
        dm, _ = _lese_bohrmass(dmtext,faktor,blind)
        tiefe = _bohrtiefe(tiefentext,faktor) if blind else None
        if not blind and tiefentext.strip():
            raise ValueError(tr("Die durchgehende Kernbohrung hat kein Tiefenmaß."))
    except ValueError as e:
        raise ValueError(tr("Bohrstufe {} – {}").format(i,e)) from e
    return dm,tiefe


def stufenmasse(kontur, masse, spur, stirn, zeilen, faktor, spitze=None):
    if bool(spur.spitzenhoehe) != bool(spitze):
        raise ValueError(tr("Für die gezeichnete Bohrspitze Spitzenwinkel und Tiefenbezug angeben."))
    profil, messungen = [], []
    for i,((dm_px,tiefe_px),(dmtext,tiefentext)) in enumerate(zip(spur.stufen,zeilen,strict=True),1):
        dm,tiefe = _bohrzeile(dmtext,tiefentext,tiefe_px is not None,faktor,i)
        messungen.append((dm_px,dm.nennwert))
        if spitze and i == len(spur.stufen):
            zylinder,scheitel = spitze.tiefen(dm,tiefe)
            if zylinder <= 0:
                raise ValueError(tr("Die Gesamttiefe lässt mit ihren Grenzmaßen keinen zylindrischen Abschnitt übrig."))
            messungen.extend(((tiefe_px,zylinder),(tiefe_px+spur.spitzenhoehe,scheitel),
                              (spur.spitzenhoehe,scheitel-zylinder)))
        elif tiefe:
            messungen.append((tiefe_px,tiefe.nennwert))
        profil.append((dm,tiefe))
    _pruefe_bohrprofil(masse,profil,spur.von_rechts,spitze)
    _massstab(kontur,masse,messungen)
    if stirn is not None:
        _pruefe_stirn(stirn,masse,[dm.nennwert for dm,_ in reversed(profil)],spur.von_rechts)
    return profil


def gegenbohrmasse(kontur, masse, spur, stirnseiten, zeilen, faktor):
    werte, messungen = [], []
    for i,((dm_px,tiefe_px),(dmtext,tiefentext)) in enumerate(zip(spur.stufen,zeilen,strict=True),1):
        dm,tiefe = _bohrzeile(dmtext,tiefentext,tiefe_px is not None,faktor,i)
        messungen.append((dm_px,dm.nennwert))
        if tiefe:
            messungen.append((tiefe_px,tiefe.nennwert))
        werte.append((dm,tiefe))
    links = tuple(werte[:len(spur.links)])
    rechts = tuple(werte[len(links):len(links)+len(spur.rechts)])
    kern = werte[-1][0] if spur.kern is not None else None
    gegen = Gegenbohrungen(links,rechts,kern)
    _pruefe_gegenbohrungen(masse,gegen)
    _massstab(kontur,masse,messungen)
    for rev,(profil,stirn) in enumerate(zip((links,rechts),stirnseiten,strict=True)):
        if stirn is not None:
            ringe = [dm.nennwert for dm,_ in reversed(profil)]
            if kern:
                ringe.insert(0,kern.nennwert)
            _pruefe_stirn(stirn,masse,ringe,bool(rev))
    return gegen


def _groessen(p):
    oben, unten = p.grenzen()
    if p.passung and (oben is None or unten is None):
        raise ValueError(tr("Für diese Passung die Grenzmaße aus der Zeichnung angeben."))
    return [g for g in (p.nennwert,oben,unten) if g is not None]


def _pruefe_wand(masse, dm, tiefe, rechts):
    bohrmasse = _groessen(dm)
    tiefen = _groessen(tiefe) if tiefe else []
    reichweite = max(tiefen) if tiefen else np.inf
    station = 0.
    for laenge, aussen in (reversed(masse) if rechts else masse):
        if station-reichweite > 1e-9:
            break
        if min(bohrmasse) <= 0 or max(bohrmasse) >= min(_groessen(aussen)):
            raise ValueError(tr("Die Bohrung muss bei Grenzmaß innerhalb der durchbohrten Wellenabschnitte liegen."))
        station += min(_groessen(laenge))
    if tiefen and (min(tiefen) <= 0 or station-reichweite <= 1e-9):
        raise ValueError(tr("Die Tiefe muss auch bei Grenzmaß Material hinter dem Bohrungsgrund lassen."))


def _pruefe_spitzenwand(masse, dm, tiefe, rechts, spitze):
    if tiefe is None or spitze.bis_spitze not in (True,False):
        raise ValueError(tr("Für die gezeichnete Bohrspitze Spitzenwinkel und Tiefenbezug angeben."))
    winkel = _groessen(spitze.winkel)
    if spitze.winkel.typ != "Size_Angular" or not all(0 < w < 180 for w in winkel):
        raise ValueError(tr("Für eine Bohrspitze die Bohrtiefe und den eingeschlossenen Spitzenwinkel mit Gradzeichen angeben."))
    radius = max(_groessen(dm))/2
    eng, weit = np.tan(np.deg2rad([min(winkel),max(winkel)])/2)
    kurz, lang = min(_groessen(tiefe)), max(_groessen(tiefe))
    zyl_min = kurz-radius/eng if spitze.bis_spitze else kurz
    spitze_max = lang if spitze.bis_spitze else lang+radius/eng
    if zyl_min <= 0 or min(_groessen(dm)) <= 0:
        raise ValueError(tr("Die Gesamttiefe lässt mit ihren Grenzmaßen keinen zylindrischen Abschnitt übrig."))
    station = 0.
    for laenge,aussen in (reversed(masse) if rechts else masse):
        if station < spitze_max:
            if spitze.bis_spitze:
                wand = min(radius,(lang-station)*weit)
            else:
                wand = radius-max(0.,station-lang)*eng
            if 2*wand >= min(_groessen(aussen))-1e-9:
                raise ValueError(tr("Die Bohrung muss bei Grenzmaß innerhalb der durchbohrten Wellenabschnitte liegen."))
        station += min(_groessen(laenge))
    if station-spitze_max <= 1e-9:
        raise ValueError(tr("Die Tiefe muss auch bei Grenzmaß Material hinter dem Bohrungsgrund lassen."))
    return zyl_min


def _pruefe_bohrprofil(masse, profil, rechts, spitze=None):
    for i,(dm,tiefe) in enumerate(profil):
        if spitze and i == len(profil)-1:
            zyl_min = _pruefe_spitzenwand(masse,dm,tiefe,rechts,spitze)
        else:
            _pruefe_wand(masse,dm,tiefe,rechts)
            zyl_min = min(_groessen(tiefe)) if tiefe else np.inf
        if i:
            vorher, absatz = profil[i-1]
            if absatz is None or min(_groessen(vorher)) <= max(_groessen(dm)):
                raise ValueError(tr("Die Durchmessergrenzen müssen jede innere Schulter erhalten."))
            if zyl_min <= max(_groessen(absatz)):
                raise ValueError(tr("Die Tiefen ab Eintritt müssen auch bei Grenzmaß von Stufe zu Stufe zunehmen."))


def _pruefe_gegenbohrungen(masse, gegen):
    reichweite = 0.
    for rechts,seite in ((False,gegen.links),(True,gegen.rechts)):
        if not seite or any(t is None for _,t in seite):
            raise ValueError(tr("Für jedes Wellenende mindestens einen Durchmesser mit Tiefe angeben."))
        profil = [*seite,(gegen.kern,None)] if gegen.kern else seite
        _pruefe_bohrprofil(masse,profil,rechts)
        reichweite += max(_groessen(seite[-1][1]))
    if sum(min(_groessen(l)) for l,_ in masse)-reichweite <= 1e-9:
        raise ValueError(tr("Zwischen beiden Bohrungsenden muss auch bei Grenzmaß ein Kernabschnitt oder Materialsteg bleiben."))


def _bohrweg(bohrprofil, x, spitze=None):
    innen = []
    start = 0.
    for i,(dm,tiefe) in enumerate(bohrprofil):
        ende = tiefe.nennwert if tiefe else x
        scheitel = ende
        if spitze and i == len(bohrprofil)-1:
            ende,scheitel = spitze.tiefen(dm,tiefe)
        innen.extend(((start,dm.nennwert/2),(ende,dm.nennwert/2)))
        start = scheitel
    return innen,start


def _drehform(masse, bohrprofil, rechts, spitze, gegen):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt
    profil = BRepBuilderAPI_MakePolygon()
    x = 0.

    for laenge, dm in masse:
        profil.Add(gp_Pnt(x,0,dm.nennwert/2))
        x += laenge.nennwert
        profil.Add(gp_Pnt(x,0,dm.nennwert/2))
    if gegen:
        links,a = _bohrweg(gegen.links,x)
        rechtspunkte,b = _bohrweg(gegen.rechts,x)
        radius = gegen.kern.nennwert/2 if gegen.kern else 0.
        innen = [*links,(a,radius),(x-b,radius),*((x-ort,r) for ort,r in reversed(rechtspunkte))]
    else:
        innen,start = _bohrweg(bohrprofil,x,spitze)
        if start < x:
            innen.extend(((start,0.),(x,0.)))
    for ort,radius in (innen if rechts else reversed(innen)):
        profil.Add(gp_Pnt(x-ort if rechts else ort,0,radius))
    profil.Close()
    flaeche = BRepBuilderAPI_MakeFace(profil.Wire(), True).Face()
    return BRepPrimAPI_MakeRevol(flaeche, gp_Ax1(gp_Pnt(0,0,0),gp_Dir(1,0,0))).Shape()


def _sitzmasse(modell, masse, bohrprofil, rechts, spitze, gegen):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    from .vergleich_geo import _nachbarn
    nachbarn = _nachbarn(modell.flaechen, modell.flaechen_index)
    ebenen, zylinder, kegel = {}, {}, set()
    for i, f in enumerate(modell.flaechen):
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Plane:
            ebenen[i] = s.Plane().Location().X()
        elif s.GetType() == GeomAbs_Cone:
            kegel.add(i)
        elif s.GetType() == GeomAbs_Cylinder:
            zylinder[i] = 2*s.Cylinder().Radius()
    def flaechen(dm, anfang, ende):
        treffer = []
        for i, d in zylinder.items():
            if abs(d-dm) >= 1e-6:
                continue
            paar = sorted((ebenen[k],k) for k in nachbarn[i] if k in ebenen)
            if len(paar) == 2 and abs(paar[0][0]-anfang) < 1e-6 and abs(paar[1][0]-ende) < 1e-6:
                treffer.append(({i},{k for _,k in paar}))
        if len(treffer) != 1:
            raise ValueError(tr("Zylinderwand und Stirnflächen eines Abschnitts sind nicht eindeutig."))
        return treffer[0]

    x = 0.
    ziele = []
    for laenge, dm in masse:
        ende = x+laenge.nennwert
        wand, stirn = flaechen(dm.nennwert,x,ende)
        ziele.extend(((laenge,stirn),(dm,wand)))
        x = ende
    def bohrungsziele(bohrprofil, rechts, spitze=None):
        start = eintritt = x if rechts else 0.
        bezug = None
        for j,(dm,tiefe) in enumerate(bohrprofil):
            if spitze and j == len(bohrprofil)-1:
                from .zeichnungskoerper import _spitzenziel
                wand = {i for i,d in zylinder.items() if abs(d-dm.nennwert) < 1e-6 and kegel & nachbarn[i]}
                if len(wand) != 1 or len(kegel) != 1:
                    raise ValueError(tr("Die Bohrspitze und das Ende der Zylinderwand sind nicht eindeutig."))
                if bezug is None:
                    f, = wand
                    bezug, = (i for i in nachbarn[f] if i in ebenen and abs(ebenen[i]-eintritt) < 1e-6)
                ziel, referenz = _spitzenziel(modell,wand,kegel,spitze.bis_spitze)
                ziele.extend(((dm,wand),(replace(tiefe,massziel_step=ziel),{bezug}|referenz),(spitze.winkel,kegel)))
                break
            laenge = tiefe.nennwert if tiefe else x
            ende = eintritt-laenge if rechts else laenge
            wand, stirn = flaechen(dm.nennwert,*sorted((start,ende)))
            if bezug is None:
                bezug, = (i for i in stirn if abs(ebenen[i]-eintritt) < 1e-6)
            ziele.append((dm,wand))
            if tiefe:
                grund, = (i for i in stirn if abs(ebenen[i]-ende) < 1e-6)
                ziele.append((tiefe,{bezug,grund}))
            start = ende
        return start

    if gegen:
        a = bohrungsziele(gegen.links,False)
        b = bohrungsziele(gegen.rechts,True)
        if gegen.kern:
            wand,_ = flaechen(gegen.kern.nennwert,a,b)
            ziele.append((gegen.kern,wand))
    else:
        bohrungsziele(bohrprofil,rechts,spitze)
    return [replace(p,flaechen=f,nummer=n,step_id=-n,quelle="eigen") for n,(p,f) in enumerate(ziele,1)]


def schreibe_drehteil(ziel, masse, bohrung=None, tiefe=None, rechts=False, stufen=(), spitze=None, gegen=None):
    if (tiefe or stufen or spitze) and not bohrung:
        raise ValueError(tr("Den Durchmesser der Axialbohrung mit Ø angeben."))
    profil = [*stufen,(bohrung,tiefe)] if bohrung else []
    if gegen is not None:
        if profil or rechts:
            raise ValueError(tr("Die Bohrungsdaten für beide Wellenenden gemeinsam angeben."))
        _pruefe_gegenbohrungen(masse,gegen)
    else:
        _pruefe_bohrprofil(masse,profil,rechts,spitze)
    form = _drehform(masse,profil,rechts,spitze,gegen)
    return schreibe_bemassten_koerper(ziel,form,lambda modell: _sitzmasse(modell,masse,profil,rechts,spitze,gegen))
