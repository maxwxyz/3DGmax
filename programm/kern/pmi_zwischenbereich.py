"""Profilrahmen mit gezeichnetem Doppelpfeil und zwei kantenbezogenen Endmarken."""

import re
from collections import defaultdict

import numpy as np
from scipy import ndimage

from .p21 import Ref
from .pmi_ableiten import aus_text


def _doppelpfeil(maske):
    """Beide Spitzen, beide Schultern und den durchgehenden schmalen Schaft pruefen."""
    y, x = np.nonzero(maske)
    if not len(x) or ndimage.label(maske, np.ones((3, 3)))[1] != 1:
        return False
    bild = ndimage.binary_fill_holes(maske[y.min():y.max()+1, x.min():x.max()+1])
    h, w = bild.shape
    if not 2.5*h < w < 12*h or h < 9:
        return False
    pos = np.arange(w)
    dicke = bild.sum(axis=0)
    breit = pos[dicke > .76*h]
    links, rechts = breit[breit < .45*w], breit[breit > .55*w]
    if not len(links) or not len(rechts):
        return False
    a, b = links.max(), rechts.min()
    if not .10*w < a < .40*w or not .10*w < w-1-b < .40*w:
        return False
    kern = np.median(dicke[a+2:b-1])
    if not .04*h < kern < .38*h:
        return False
    soll = np.where(pos <= a, 1+(h-1)*pos/a, np.where(pos >= b, 1+(h-1)*(w-1-pos)/(w-1-b), kern))
    raster = abs(np.arange(h)[:, None]-(h-1)/2) <= soll/2
    return (raster & bild).sum() > .86*(raster | bild).sum()


def _zeile(pfade, hoehe):
    from . import pmi_strichschrift as schrift
    if not pfade:
        return ()
    bild, _ = schrift._gesamtbild(pfade, 160/hoehe)
    if bild is None:
        return ()
    gruppen = schrift._gruppen(bild)
    if len(gruppen) != 3:
        return ()
    teile = [bild[:, l:r] for l, r in gruppen]
    a, b = (schrift._normale_zeile(teil) for teil in (teile[0], teile[2]))
    if a == b or not all(re.fullmatch("[A-Z]", s) for s in (a, b)) or not _doppelpfeil(teile[1]):
        return ()
    return a, b


def _fuehrung(pfade, links, rechts, mitte, h):
    """Alle uebrigen Striche muessen auf dem waagerechten Ansatz und seinem zweiten Schenkel liegen."""
    if not pfade:
        return True
    from .pmi_hinweislinie import _an_strecke
    p = np.vstack([q for q, _ in pfade])
    if p[:, 0].max() <= links+.02*h:
        pfade = [(q * [-1, 1], voll) for q, voll in pfade]
        p = p * [-1, 1]
        rechts = -links
    if p[:, 0].min() < rechts-.02*h:
        return False
    band = p[abs(p[:, 1]-mitte) < .025*h]
    if not len(band):
        return False
    start = np.array([band[:, 0].min(), mitte])
    knick = np.array([band[:, 0].max(), mitte])
    ende = p[np.argmax(abs(p[:, 1]-mitte))]
    if not (-.02*h <= start[0]-rechts < h and .05*h < knick[0]-start[0] < 2*h
            and abs(ende[1]-mitte) > .25*h):
        return False
    return all(np.all(_an_strecke(q, start, knick, .03*h)) or np.all(_an_strecke(q, knick, ende, .03*h))
               for q, _ in pfade)


def _bereichstext(g):
    from . import pmi_strichschrift as schrift
    if g.ebene is None or not schrift._lesbar(g):
        return None
    pfade = schrift._pfade(g, g.ebene)
    if not pfade:
        return None
    # Ausserhalb der Zeichenebene darf nur eine kleine, geschlossene runde Zielmarke liegen.
    o, _, _, n = g.ebene
    tiefen = [(linie-o) @ n for linie in g.linien if len(linie) >= 2]
    for xyz, indices in g.dreiecke:
        if len(indices):
            tiefen.extend(((xyz-o) @ n)[indices])
    auf, marke = [], []
    for pfad, tiefe in zip(pfade, tiefen, strict=True):
        if np.max(abs(tiefe)) <= .001:
            auf.append(pfad)
        elif np.ptp(tiefe) <= .001:
            marke.append(pfad)
        else:
            return None
    if not auf:
        return None
    zellen = schrift._zellen(auf)
    if not 2 <= len(zellen) <= 5:
        return None
    l, b, _, t = zellen[0]
    r, h = zellen[-1][2], t-b
    if marke:
        punkte = np.vstack([q for q, _ in marke])
        breite = np.ptp(punkte, axis=0)
        if (min(breite) <= 0 or max(breite) > .12*h or min(breite) < .9*max(breite)
                or not _runde_marke(marke, max(breite))):
            return None
    rahmen, zusatz, rest = [], [], []
    for pfad in auf:
        p, _ = pfad
        x, y = p.min(axis=0)
        xx, yy = p.max(axis=0)
        if l-.03*h <= x and xx <= r+.03*h and b-.03*h <= y and yy <= t+.03*h:
            rahmen.append(pfad)
        elif l-.15*h <= x and xx <= r+.03*h and b-1.7*h <= y and yy < b-.05*h:
            zusatz.append(pfad)
        else:
            rest.append(pfad)
    grenzen = _zeile(zusatz, h)
    if not grenzen or not _fuehrung(rest, l, r, (b+t)/2, h):
        return None
    wort = schrift._rahmentext(rahmen, zellen)
    daten = aus_text([wort], g.textfaktor) if wort else None
    if daten and daten.get("wert") is not None and daten["typ"] in ("ProfileOfSurface", "ProfileOfLine"):
        return wort, daten, grenzen
    return None


def _runde_marke(pfade, breite):
    from . import pmi_strichschrift as schrift
    bild, _ = schrift._gesamtbild(pfade, 60/breite)
    if bild is None:
        return False
    voll = ndimage.binary_fill_holes(bild)
    y, x = np.ogrid[:voll.shape[0], :voll.shape[1]]
    kreis = (x-(voll.shape[1]-1)/2)**2 + (y-(voll.shape[0]-1)/2)**2 <= 30**2
    return (kreis & voll).sum() > .9*(kreis | voll).sum()


def _endzeichen(g, kante):
    from . import pmi_strichschrift as schrift
    if g.ebene is None or g.erzeugt or g.platzhalter or not schrift._lesbar(g):
        return ""
    pfade = schrift._pfade(g, g.ebene)
    if not pfade:
        return ""
    groesse = np.ptp(np.vstack([p for p, _ in pfade]), axis=0).max()
    if groesse <= 0:
        return ""
    skala = 900/groesse
    bild, grenzen = schrift._gesamtbild(pfade, skala)
    if bild is None:
        return ""
    labels, _ = ndimage.label(bild, np.ones((3, 3)))
    boxen = ndimage.find_objects(labels)
    if not 2 <= len(boxen) <= 5:
        return ""
    teile = sorted(enumerate(boxen, 1), key=lambda z: max(s.stop-s.start for s in z[1]))
    nr, box = teile[-1]
    if max(s.stop-s.start for s in teile[-2][1]) > .3*max(s.stop-s.start for s in box):
        return ""
    fuehrung = labels[box] == nr
    if fuehrung.mean() >= .15:
        return ""
    def am_schenkel(punkte):
        o, x, y, _ = g.ebene
        u = np.rint(((punkte-o) @ x - grenzen[0])*skala+2).astype(int)
        v = np.rint((grenzen[3] - (punkte-o) @ y)*skala+2).astype(int)
        return np.all(umriss[v, u])

    buchstabe = schrift._normale_zeile(bild & (labels != nr))
    umriss = ndimage.binary_dilation(labels == nr)
    return buchstabe if buchstabe and _pfeil_an_kante(g, kante, am_schenkel) else ""


def _pfeil_an_kante(g, kante, am_schenkel):
    """Die Spitze eines schmalen Pfeildreiecks muss die zugeordnete Kante treffen."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.gp import gp_Pnt
    if kante is None or kante.IsNull():
        return False
    dreiecke = [l[:3] for l in g.linien if len(l) == 4 and np.allclose(l[0], l[-1], rtol=0, atol=1e-6)]
    for xyz, indices in g.dreiecke:
        dreiecke.extend(xyz[indices])
    for punkte in dreiecke:
        laengen = np.linalg.norm(np.roll(punkte, -1, axis=0) - punkte, axis=1)
        basis = int(np.argmin(laengen))
        kurz, mittel, lang = sorted(laengen)
        if not 0 < kurz < .8*mittel or lang > 1.1*mittel or not am_schenkel(punkte):
            continue
        spitze = BRepBuilderAPI_MakeVertex(gp_Pnt(*punkte[(basis+2) % 3])).Vertex()
        abstand = BRepExtrema_DistShapeShape(spitze, kante)
        if abstand.IsDone() and abstand.Value() <= .001:
            return True
    return False


def _ziele(datei, aspekt):
    from .pmi_lesen import NUTZUNGEN
    out = set()
    for i in datei.referrers().get(aspekt, ()):
        e = datei.get(i)
        for typ in NUTZUNGEN:
            a = e.parts.get(typ, ())
            if len(a) == 5 and a[2] == Ref(aspekt) and isinstance(a[4], Ref):
                out.add(a[4].id)
    return out


def begrenzter_verband(datei, flaechen, kanten):
    from .step_schreiben import randkanten
    if len(kanten) != 2 or len(set(kanten)) != 2 or not flaechen or any(not datei.get(f) for f in flaechen):
        return False
    raender = {f: randkanten(datei, f) for f in flaechen}
    nachbarn = defaultdict(set)
    for f, rand in raender.items():
        for k in rand:
            nachbarn[k].add(f)
    if any(len(nachbarn[k]) != 1 for k in kanten):
        return False
    offen = [next(iter(raender))]
    gesehen = set(offen)
    while offen:
        for k in raender[offen.pop()]:
            for f in nachbarn[k] - gesehen:
                gesehen.add(f)
                offen.append(f)
    return len(gesehen) == len(raender)


def ergaenze(v, g, modell, grafiken):
    from .merkmalstext import aspekte_am_callout
    from .pmi_freier_hinweis import _ansichten, _mitglieder
    if (not modell.datei or v.art != "toleranz" or v.typ not in ("", "ProfileOfSurface", "ProfileOfLine")
            or v.wert is not None or v.validierungstexte or g.erzeugt or g.platzhalter or not v.flaechen):
        return
    ergebnis = _bereichstext(g)
    if not ergebnis:
        return
    wort, daten, namen = ergebnis
    if v.typ and v.typ != daten["typ"]:
        return
    d = modell.datei
    flaechen = {modell.flaeche_zu_step.get(i) for i in v.flaechen}
    def ziele(nr):
        return {z for a in aspekte_am_callout(d, nr) for z in _ziele(d, a)}
    if ziele(g.callout_id) != flaechen:
        return
    ansichten = defaultdict(set)
    for ansicht in _ansichten(d, g.callout_id):
        for nr in _mitglieder(d, [ansicht]):
            ansichten[nr].add(ansicht)
    grenzen = {}
    for nr in grafiken.keys() & ansichten.keys():
        ziel = ziele(nr)
        if len(ziel) != 1:
            continue
        k = ziel.pop()
        if not d.get(k) or not d.get(k).is_a("EDGE_CURVE"):
            continue
        name = _endzeichen(grafiken[nr], modell.form_von_step(k))
        if name in namen:
            if name in grenzen:
                return
            grenzen[name] = (k, nr)
    if not all(n in grenzen for n in namen):
        return
    marken = [grenzen[n][1] for n in namen]
    if not ansichten[marken[0]] & ansichten[marken[1]]:
        return
    kanten = [grenzen[n][0] for n in namen]
    if not begrenzter_verband(d, flaechen, kanten):
        return
    for feld, wert in daten.items():
        setattr(v, feld, wert)
    v.bereichsgrenzen = [[n, k] for n, k in zip(namen, kanten)]
    v.grenzgrafiken = marken
    v.ocr_text = v.nur_grafik_text = wort + "\n" + " ↔ ".join(namen)


def lies_grenzen(datei, aspekt):
    grenzen = {}
    for i in datei.referrers().get(aspekt, ()):
        rel = datei.get(i).parts.get("SHAPE_ASPECT_RELATIONSHIP", ())
        if len(rel) != 4 or rel[0] not in ("start feature", "end feature") or rel[2] != Ref(aspekt):
            continue
        if not isinstance(rel[3], Ref):
            return []
        kind = datei.get(rel[3])
        if not kind or not kind.is_a("SHAPE_ASPECT"):
            return []
        k = _ziele(datei, kind.id)
        if len(k) != 1 or rel[0] in grenzen:
            return []
        ziel = k.pop()
        if not datei.get(ziel) or not datei.get(ziel).is_a("EDGE_CURVE"):
            return []
        args = kind.args("SHAPE_ASPECT")
        if not args or not isinstance(args[0], str):
            return []
        grenzen[rel[0]] = [args[0], ziel]
    return [grenzen["start feature"], grenzen["end feature"]] if len(grenzen) == 2 else []
