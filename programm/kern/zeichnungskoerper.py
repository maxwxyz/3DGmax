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
    lagemasse: tuple[Pmi, Pmi] | None = None
    kern: int | None = None
    senkwinkel: Pmi | None = None
    spitzenwinkel: Pmi | None = None
    bis_spitze: bool = False


@dataclass(frozen=True)
class Plattentasche:
    x: float
    y: float
    breite: Pmi
    hoehe: Pmi
    tiefe: Pmi | None
    radius: Pmi | None = None
    langloch: bool = False
    achsabstand: Pmi | None = None
    gesamt_abgeleitet: bool = False
    lagemasse: tuple[Pmi, Pmi] | None = None

    @property
    def rundungsradius(self):
        if self.langloch:
            return min(self.breite.nennwert, self.hoehe.nennwert)/2
        return self.radius.nennwert if self.radius else 0.


def rechteckgrenzen(bild, box):
    """Vollstaendige achsparallele Aussenkontur einer ungebohrten Platte im Blattausschnitt."""
    h, w = bild.shape[:2]
    l, t, r, b = np.rint(np.clip(box, 0., 1.) * [w, h, w, h]).astype(int)
    tinte = bild[t:b, l:r, :3].min(axis=2) < 245
    return tintenrechteck(tinte, l, t)


def tintenrechteck(tinte, l, t):
    h, w = tinte.shape
    ys, xs = np.nonzero(tinte)
    if not xs.size:
        return None
    x1, x2, y1, y2 = xs.min(), xs.max(), ys.min(), ys.max()
    if min(x1, y1, w-1-x2, h-1-y2) < 1 or min(x2-x1, y2-y1) < 12:
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


def tiefenmass(text, faktor):
    wert = lese_angabe(text.strip().removeprefix("↧").strip(), faktor)
    if wert and wert.typ == "Location_LinearDistance" and not wert.passung and "Hilfsmass" not in wert.modifikatoren:
        return wert
    return None


def pruefe_tiefe(tiefe, dicke):
    minimum = dicke.grenzen()[1]
    grenze = min(dicke.nennwert, minimum) if minimum is not None else dicke.nennwert
    if not all(0 < g < grenze for g in (tiefe.nennwert, *tiefe.grenzen()) if g is not None):
        raise ValueError(tr("Die Tiefe muss mit ihren Grenzmaßen zwischen null und der kleinsten Plattendicke liegen."))


def koordinatenmasse(tx, ty):
    paar = tuple(lese_angabe(text, 1.) for text in (tx, ty))
    for p in paar:
        if not p or p.typ != "Location_LinearDistance" or p.nennwert is None or p.passung or p.modifikatoren:
            return None
        oben, unten = p.grenzen()
        if not all(np.isfinite(g) for g in (p.nennwert, oben, unten) if g is not None):
            return None
        if oben is not None and unten is not None and oben < unten:
            return None
    return paar


def massbereich(p):
    werte = [g for g in (p.nennwert, *p.grenzen()) if g is not None]
    return min(werte), max(werte)


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


def _plattenform(masse, bohrungen, taschen):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeCone
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopTools import TopTools_ListOfShape
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepPrimAPI_MakeBox(*(p.nennwert for p in masse)).Shape()
    if not bohrungen and not taschen:
        return form
    platte, werkzeuge = TopTools_ListOfShape(), TopTools_ListOfShape()
    platte.Append(form)
    dicke = masse[2].nennwert
    zugabe = max(.01, dicke*.01)
    for i, bohrung in enumerate(bohrungen):
        if bohrung.senkwinkel:
            radius = bohrung.durchmesser.nennwert/2
            innen = bohrungen[i-1].durchmesser.nennwert/2
            steigung = np.tan(np.deg2rad(bohrung.senkwinkel.nennwert)/2)
            hoehe = (radius-innen)/steigung
            achse = gp_Ax2(gp_Pnt(bohrung.x, bohrung.y, dicke-hoehe), gp_Dir(0, 0, 1))
            werkzeuge.Append(BRepPrimAPI_MakeCone(achse, innen, radius, hoehe).Shape())
            continue
        boden = dicke-bohrung.tiefe.nennwert if bohrung.tiefe else -zugabe
        radius = bohrung.durchmesser.nennwert/2
        if bohrung.spitzenwinkel:
            hoehe = radius/np.tan(np.deg2rad(bohrung.spitzenwinkel.nennwert)/2)
            if bohrung.bis_spitze:
                boden += hoehe
            spitze = gp_Ax2(gp_Pnt(bohrung.x, bohrung.y, boden-hoehe), gp_Dir(0, 0, 1))
            werkzeuge.Append(BRepPrimAPI_MakeCone(spitze, 0., radius, hoehe).Shape())
        achse = gp_Ax2(gp_Pnt(bohrung.x, bohrung.y, boden), gp_Dir(0, 0, 1))
        werkzeuge.Append(BRepPrimAPI_MakeCylinder(achse, radius, dicke+zugabe-boden).Shape())
    for tasche in taschen:
        x, y = tasche.breite.nennwert, tasche.hoehe.nennwert
        boden = dicke-tasche.tiefe.nennwert if tasche.tiefe else -zugabe
        if tasche.langloch:
            werkzeuge.Append(_langlochwerkzeug(tasche, boden, dicke+zugabe-boden))
            continue
        ecke = gp_Pnt(tasche.x-x/2, tasche.y-y/2, boden)
        werkzeug = BRepPrimAPI_MakeBox(ecke, x, y, dicke+zugabe-boden).Shape()
        if tasche.radius:
            werkzeug = _runde_senkrechte_kanten(werkzeug, tasche.radius.nennwert)
        werkzeuge.Append(werkzeug)
    schnitt = BRepAlgoAPI_Cut()
    schnitt.SetArguments(platte)
    schnitt.SetTools(werkzeuge)
    schnitt.Build()
    if not schnitt.IsDone() or not BRepCheck_Analyzer(schnitt.Shape()).IsValid():
        raise ValueError(tr("Die Innenkonturen konnten nicht ausgeschnitten werden."))
    return schnitt.Shape()


def _langlochwerkzeug(tasche, boden, tiefe):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.GC import GC_MakeArcOfCircle
    from OCC.Core.gp import gp_Pnt, gp_Vec
    x, y = tasche.breite.nennwert, tasche.hoehe.nennwert
    r, a = tasche.rundungsradius, abs(x-y)/2

    def punkt(langs, quer):
        dx, dy = (langs, quer) if x > y else (-quer, langs)
        return gp_Pnt(tasche.x+dx, tasche.y+dy, boden)

    links, rechts = punkt(-a,r), punkt(a,r)
    unten_rechts, unten_links = punkt(a,-r), punkt(-a,-r)
    draht = BRepBuilderAPI_MakeWire()
    draht.Add(BRepBuilderAPI_MakeEdge(links, rechts).Edge())
    draht.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(rechts, punkt(a+r,0), unten_rechts).Value()).Edge())
    draht.Add(BRepBuilderAPI_MakeEdge(unten_rechts, unten_links).Edge())
    draht.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(unten_links, punkt(-a-r,0), links).Value()).Edge())
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(draht.Wire()).Face(), gp_Vec(0,0,tiefe)).Shape()


def _runde_senkrechte_kanten(form, radius):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import topexp
    from OCC.Core.TopTools import TopTools_IndexedMapOfShape
    from OCC.Core.TopoDS import topods
    kanten = TopTools_IndexedMapOfShape()
    topexp.MapShapes(form, TopAbs_EDGE, kanten)
    rundung = BRepFilletAPI_MakeFillet(form)
    for i in range(1,kanten.Size()+1):
        k = topods.Edge(kanten.FindKey(i))
        if abs(BRepAdaptor_Curve(k).Line().Direction().Z()) > .999999:
            rundung.Add(radius, k)
    rundung.Build()
    if not rundung.IsDone():
        raise ValueError(tr("Die Taschenrundungen konnten nicht erzeugt werden."))
    return rundung.Shape()


def _flaechenmasse(modell, masse, bohrungen, taschen):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone
    paare = [set() for _ in masse]
    waende = [set() for _ in bohrungen]
    spitzen = [set() for _ in bohrungen]
    ebenen = [{}, {}, {}]
    horizontal = ebenen[2]
    viertelkreise, halbkreise = {}, {}
    for i, flaeche in enumerate(modell.flaechen):
        s = BRepAdaptor_Surface(flaeche)
        if s.GetType() == GeomAbs_Plane:
            ebene = s.Plane()
            achse = int(np.argmax(np.abs(ebene.Axis().Direction().Coord())))
            ort = ebene.Location().Coord()[achse]
            ebenen[achse][i] = ort
            if abs(ort) < 1e-7 or abs(ort-masse[achse].nennwert) < 1e-7:
                paare[achse].add(i)
        elif s.GetType() in (GeomAbs_Cylinder, GeomAbs_Cone):
            kegel = s.GetType() == GeomAbs_Cone
            if kegel:
                z = s.Cone()
                ort = z.Location()
                rad = max(np.hypot(q.X()-ort.X(), q.Y()-ort.Y())
                          for q in (s.Value(0,s.FirstVParameter()), s.Value(0,s.LastVParameter())))
            else:
                z = s.Cylinder()
                ort, rad = z.Location(), z.Radius()
                winkel = s.LastUParameter()-s.FirstUParameter()
                if abs(winkel-np.pi) < 1e-6:
                    halbkreise[i] = (ort.X(), ort.Y(), rad)
                    continue
                if abs(winkel-np.pi/2) < 1e-6:
                    viertelkreise[i] = (ort.X(), ort.Y(), rad)
                    continue
            treffer = [j for j, b in enumerate(bohrungen) if abs(ort.X()-b.x) < 1e-6
                       and abs(ort.Y()-b.y) < 1e-6 and (kegel == bool(b.senkwinkel) or (kegel and b.spitzenwinkel))
                       and abs(rad-b.durchmesser.nennwert/2) < 1e-6]
            if len(treffer) != 1:
                raise ValueError(tr("Die Bohrungsflächen sind nicht eindeutig."))
            j, = treffer
            ziel = spitzen if kegel and bohrungen[j].spitzenwinkel else waende
            ziel[j].add(i)
    if not all(waende):
        raise ValueError(tr("Die Bohrungsflächen sind nicht eindeutig."))
    dicke = masse[2].nennwert
    deckel = {i for i, z in horizontal.items() if abs(z-dicke) < 1e-7}
    if len(deckel) != 1 or any(len(paar) != 2 for paar in paare):
        raise ValueError(tr("Die gegenüberliegenden Plattenflächen sind nicht eindeutig."))
    alle = [*masse, *(b.durchmesser for b in bohrungen)]
    flaechen = paare + waende
    for bohrung, wand in zip(bohrungen, waende, strict=True):
        if bohrung.lagemasse:
            for achse, mass in enumerate(bohrung.lagemasse):
                ursprung = {i for i in paare[achse] if abs(ebenen[achse][i]) < 1e-7}
                alle.append(replace(mass, typ="Location_LinearDistance_FromOuterToCenter"))
                flaechen.append(ursprung | wand)
    if taschen or any(b.tiefe or b.senkwinkel for b in bohrungen):
        from .vergleich_geo import _nachbarn
        nachbarn = _nachbarn(modell.flaechen, modell.flaechen_index)
        gruppen = {}
        for i, bohrung in enumerate(bohrungen):
            gruppen.setdefault(i if bohrung.kern is None else bohrung.kern, []).append(i)
        for gruppe in gruppen.values():
            eintritt = deckel
            for j in reversed(gruppe):
                bohrung = bohrungen[j]
                angrenzend = set().union(*(nachbarn[i] for i in waende[j]))
                if bohrung.senkwinkel:
                    if not deckel <= angrenzend or not waende[j-1] <= angrenzend:
                        raise ValueError(tr("Die Kegelsenkung ist keiner Eintrittsfläche und Kernbohrung eindeutig zugeordnet."))
                    alle[len(masse)+j] = replace(bohrung.durchmesser, massziel_step=_gemeinsamer_kreis(modell, waende[j], deckel))
                    alle.append(bohrung.senkwinkel)
                    flaechen.append(waende[j])
                    eintritt = waende[j]
                    continue
                if bohrung.spitzenwinkel:
                    if len(spitzen[j]) != 1 or not (eintritt | spitzen[j]) <= angrenzend:
                        raise ValueError(tr("Die Bohrspitze und das Ende der Zylinderwand sind nicht eindeutig."))
                    ziel, bezug = _spitzenziel(modell, waende[j], spitzen[j], bohrung.bis_spitze)
                    alle.extend((replace(bohrung.tiefe, massziel_step=ziel), bohrung.spitzenwinkel))
                    flaechen.extend((deckel | bezug, spitzen[j]))
                    continue
                ziel_z = dicke-bohrung.tiefe.nennwert if bohrung.tiefe else 0.
                boden = {i for i in angrenzend & horizontal.keys() if abs(horizontal[i]-ziel_z) < 1e-6}
                if len(boden) != 1 or not eintritt <= angrenzend:
                    raise ValueError(tr("Eintrittsfläche und Bohrungsgrund sind nicht eindeutig."))
                if bohrung.tiefe:
                    alle.append(bohrung.tiefe)
                    flaechen.append(deckel | boden)
                eintritt = boden
        for tasche in taschen:
            bezuege = _taschenflaechen(tasche, dicke, deckel, ebenen, nachbarn, viertelkreise, halbkreise)
            for mass, paar in zip((tasche.breite, tasche.hoehe), bezuege[:2], strict=True):
                if tasche.langloch and mass.nennwert > 2*tasche.rundungsradius:
                    if tasche.achsabstand:
                        alle.append(replace(tasche.achsabstand, mittenabstand=True))
                        flaechen.append(paar)
                    if tasche.gesamt_abgeleitet:
                        continue
                    mass = replace(mass, typ="Location_LinearDistance_FromOuterToOuter")
                alle.append(mass)
                flaechen.append(paar)
            if tasche.lagemasse:
                for achse, mass in enumerate(tasche.lagemasse):
                    ursprung, = (i for i in paare[achse] if abs(ebenen[achse][i]) < 1e-7)
                    alle.append(replace(mass,typ="Location_LinearDistance_FromOuterToCenter",mittenbezug=ursprung))
                    flaechen.append({ursprung} | bezuege[achse])
            if tasche.radius:
                alle.append(tasche.radius)
            if tasche.tiefe:
                alle.append(tasche.tiefe)
            flaechen.extend(bezuege[2:])
    return [replace(p, flaechen=f, quelle="eigen", nummer=i, step_id=-i)
            for i, (p, f) in enumerate(zip(alle, flaechen, strict=True), 1)]


def _gemeinsamer_kreis(modell, erste, zweite):
    from .step_schreiben import randkanten
    a, = erste
    b, = zweite
    kanten = (randkanten(modell.datei, modell.flaeche_zu_step[a])
              & randkanten(modell.datei, modell.flaeche_zu_step[b]))
    if len(kanten) != 1:
        raise ValueError(tr("Der gemeinsame Kreisrand der Bohrungsflächen ist nicht eindeutig."))
    return kanten.pop()


def _spitzenziel(modell, wand, spitze, gesamt):
    from .step_schreiben import randkanten, randpunkte
    kreis = _gemeinsamer_kreis(modell, wand, spitze)
    if not gesamt:
        return kreis, wand
    f, = spitze
    kanten = randkanten(modell.datei, modell.flaeche_zu_step[f])
    punkte = randpunkte(modell.datei, kanten) - randpunkte(modell.datei, [kreis])
    if len(punkte) != 1:
        raise ValueError(tr("Der Scheitelpunkt der Bohrspitze ist nicht eindeutig."))
    return punkte.pop(), spitze


def _taschenflaechen(tasche, dicke, deckel, ebenen, nachbarn, viertelkreise, halbkreise):
    ziel_z = dicke-tasche.tiefe.nennwert if tasche.tiefe else 0.
    kandidaten = []
    for i, z in ebenen[2].items():
        if abs(z-ziel_z) >= 1e-6:
            continue
        # Beim Durchbruch grenzt die Unterseite auch an Waende anderer Ausschnitte.
        if tasche.tiefe and len(nachbarn[i]) != (8 if tasche.radius else 4):
            continue
        waende = {j for j in nachbarn[i] if deckel <= nachbarn[j]}
        seiten = []
        for lagen, mitte, mass in zip(ebenen[:2], (tasche.x, tasche.y), (tasche.breite, tasche.hoehe)):
            for ort in (mitte-mass.nennwert/2, mitte+mass.nennwert/2):
                seiten.append({j for j in waende & lagen.keys() if abs(lagen[j]-ort) < 1e-6})
        if tasche.langloch or tasche.radius:
            if tasche.langloch:
                paare = _langlochwaende(tasche, seiten, waende, nachbarn, halbkreise)
            else:
                paare = _gerundete_waende(tasche, seiten, waende, nachbarn, viertelkreise)
            if paare:
                kandidaten.append((*paare, deckel | {i}) if tasche.tiefe else paare)
            continue
        # Alle vier Waende muessen zu demselben geschlossenen Rechteck gehoeren.
        for links in seiten[0]:
            oben = nachbarn[links] & seiten[2]
            unten = nachbarn[links] & seiten[3]
            if len(oben) != 1 or len(unten) != 1:
                continue
            quer = oben | unten
            for rechts in seiten[1]:
                if quer <= nachbarn[rechts]:
                    paare = ({links, rechts}, quer)
                    kandidaten.append((*paare, deckel | {i}) if tasche.tiefe else paare)
    if len(kandidaten) != 1:
        raise ValueError(tr("Die vier zusammenhängenden Wände der Innenkontur sind nicht eindeutig."))
    return kandidaten[0]


def _langlochwaende(tasche, seiten, waende, nachbarn, halbkreise):
    x, y = tasche.breite.nennwert, tasche.hoehe.nennwert
    r, a = tasche.rundungsradius, abs(x-y)/2
    seitenpaar = seiten[2:] if x > y else seiten[:2]
    enden = set()
    for vorzeichen in (-1,1):
        dx, dy = (vorzeichen*a, 0) if x > y else (0, vorzeichen*a)
        ziel = np.array([tasche.x+dx, tasche.y+dy, r])
        treffer = [k for k in waende & halbkreise.keys() if np.max(np.abs(ziel-halbkreise[k])) < 1e-6]
        if len(treffer) != 1:
            return None
        enden.add(treffer[0])
    links, rechts = ({j for j in seite if enden <= nachbarn[j]} for seite in seitenpaar)
    if len(enden) == 2 and len(links) == len(rechts) == 1:
        return (enden, links | rechts) if x > y else (links | rechts, enden)


def _gerundete_waende(tasche, seiten, waende, nachbarn, viertelkreise):
    radius = tasche.radius.nennwert
    halbx, halby = tasche.breite.nennwert/2-radius, tasche.hoehe.nennwert/2-radius
    ecken = set()
    seitenwaende = [set() for _ in seiten]
    for i, sx in enumerate((-1,1)):
        for j, sy in enumerate((-1,1), 2):
            ziel = np.array([tasche.x+sx*halbx, tasche.y+sy*halby, radius])
            ecke = [k for k in waende & viertelkreise.keys()
                    if np.max(np.abs(ziel-viertelkreise[k])) < 1e-6]
            if len(ecke) != 1:
                return None
            k, = ecke
            ecken.add(k)
            for n in (i,j):
                wand = nachbarn[k] & seiten[n]
                if len(wand) != 1:
                    return None
                seitenwaende[n].update(wand)
    if len(ecken) == 4 and all(len(w) == 1 for w in seitenwaende):
        return seitenwaende[0] | seitenwaende[1], seitenwaende[2] | seitenwaende[3], ecken


def schreibe_platte(ziel, masse, bohrungen=(), taschen=()):
    """Geometrie und flaechenbezogene Masse mit Darstellung als AP242 speichern."""
    bohrungen = [b if isinstance(b, Plattenbohrung) else Plattenbohrung(*b) for b in bohrungen]
    return schreibe_bemassten_koerper(ziel, _plattenform(masse, bohrungen, taschen),
                                      lambda modell: _flaechenmasse(modell, masse, bohrungen, taschen))


def schreibe_bemassten_koerper(ziel, form, flaechenmasse):
    from OCC.Core.DESTEP import DESTEP_Parameters
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from .laden import LadeFehler, lade_step
    from .step_schreiben import schreibe

    ziel = Path(ziel)
    with TemporaryDirectory(dir=ziel.parent) as tmp:
        roh = str(Path(tmp) / "geometry.stp")
        fertig = Path(tmp) / "model.stp"
        writer = STEPControl_Writer()
        parameter = DESTEP_Parameters()
        parameter.WriteSchema = parameter.WriteMode_StepSchema_AP242DIS
        if writer.Transfer(form, STEPControl_AsIs, parameter) != IFSelect_RetDone or writer.Write(roh) != IFSelect_RetDone:
            raise ValueError(tr("Der Körper konnte nicht als STEP geschrieben werden."))
        try:
            modell = lade_step(roh)
        except LadeFehler as e:
            raise ValueError(str(e)) from e
        merkmale = flaechenmasse(modell)
        bericht = schreibe(roh, str(fertig), merkmale, modell)
        if len(bericht.neu) != len(merkmale) or len(bericht.dargestellt) != len(merkmale):
            raise ValueError(tr("Die Maßangaben konnten nicht vollständig als STEP-PMI geschrieben werden."))
        fertig.replace(ziel)
        return len(merkmale)
