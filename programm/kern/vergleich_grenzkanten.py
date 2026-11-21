"""Anfangs- und Endkanten begrenzter PMI zwischen zwei ausgerichteten STEP-Staenden zuordnen."""

from collections import defaultdict

import numpy as np
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.IntTools import IntTools_EdgeEdge
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FORWARD
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods
from scipy.spatial import cKDTree


def _kanten(erg):
    """Kante am tolerierten Flaechenvorkommen aufsuchen; verschiedene Einbaulagen bleiben offen."""
    gesucht, nummern = defaultdict(set), set()
    for p in erg.pmi:
        for _, nr in p.bereichsgrenzen or ():
            nummern.add(nr)
            for f in p.flaechen:
                gesucht[f].add(nr)
    orte = {nr: set() for nr in nummern}
    basis = {}
    for nr in nummern:
        form = erg.modell.form_von_step(nr)
        if form is not None and form.ShapeType() == TopAbs_EDGE:
            basis[nr] = form.Located(TopLoc_Location()).Oriented(TopAbs_FORWARD)
    grenzt_an = defaultdict(set)
    for f, am_rand in gesucht.items():
        if not 0 <= f < len(erg.modell.flaechen):
            continue
        ziel = defaultdict(list)
        for nr in am_rand:
            if nr in basis:
                ziel[basis[nr]].append(nr)
        kanten = TopExp_Explorer(erg.modell.flaechen[f], TopAbs_EDGE)
        while kanten.More():
            k = kanten.Current().Oriented(TopAbs_FORWARD)
            for nr in ziel.get(k.Located(TopLoc_Location()), ()):
                orte[nr].add(k)
                grenzt_an[nr].add(f)
            kanten.Next()
    return {nr: (topods.Edge(next(iter(k))) if len(k) == 1 else None) for nr, k in orte.items()}, grenzt_an


def _abgedeckt(kante, intervalle, toleranz):
    """Vollstaendiges Parameterintervall, inklusive mehrerer Teilstuecke an einer Naht."""
    kurve = BRepAdaptor_Curve(kante)
    ende = kurve.FirstParameter()
    eps = kurve.Resolution(toleranz)
    for anfang, bis in sorted(intervalle):
        if anfang > ende + eps:
            return False
        ende = max(ende, bis)
    return bool(intervalle) and ende + eps >= kurve.LastParameter()


def _deckung(a, b, toleranz):
    """Gemeinsame Kantenabschnitte in beiden Parameterraeumen; einzelne Schnittpunkte genuegen nie."""
    try:
        test = IntTools_EdgeEdge()
        test.SetEdge1(a)
        test.SetEdge2(b)
        test.SetFuzzyValue(toleranz)
        test.Perform()
        if not test.IsDone():
            return None
        teile = test.CommonParts()
        ia, ib = [], []
        for i in range(1, teile.Length()+1):
            teil = teile.Value(i)
            if teil.Type() != TopAbs_EDGE:
                continue
            erste, zweite = (ia, ib) if teil.Edge1().IsSame(a) else (ib, ia)
            r = teil.Range1()
            erste.append((r.First(), r.Last()))
            bereiche = teil.Ranges2()
            for j in range(1, bereiche.Length()+1):
                r = bereiche.Value(j)
                zweite.append((r.First(), r.Last()))
        return _abgedeckt(a, ia, toleranz) and _abgedeckt(b, ib, toleranz)
    except RuntimeError:
        return None


def _box(kante):
    if kante is None or BRep_Tool.Degenerated(kante):
        return None
    b = Bnd_Box()
    try:
        brepbndlib.AddOptimal(kante, b, False, False)
        if not b.IsVoid() and not b.IsOpen():
            box = np.array(b.Get()).reshape(2, 3)
            if np.isfinite(box).all():
                return box
    except RuntimeError:
        pass
    return None


def grenzschluessel(alt, neu, ausrichtung, toleranz, flaechenzuordnung):
    """Gleiche Schluessel nur fuer eindeutige Entsprechungen. None bedeutet ungeprueft."""
    if not any(p.bereichsgrenzen for p in alt.pmi) or not any(p.bereichsgrenzen for p in neu.pmi):
        return {}, {}
    a, traeger_a = _kanten(alt)
    b, traeger_b = _kanten(neu)
    lage = TopLoc_Location(ausrichtung.gp_trsf())
    boxen = {nr: box for nr, k in a.items() if (box := _box(k)) is not None}
    links = {nr: nr if nr in boxen else None for nr in a}
    rechts = dict.fromkeys(b)
    if not boxen:
        return links, rechts
    nummern = list(boxen)
    baum = cKDTree([boxen[n].mean(axis=0) for n in nummern])
    eps = max(toleranz, 1e-7)
    for nr, kante in b.items():
        if kante is None:
            continue
        k = topods.Edge(kante.Moved(lage))
        box = _box(k)
        if box is None:
            continue
        kandidaten = baum.query_ball_point(box.mean(axis=0), eps, p=np.inf)
        flaechen = {flaechenzuordnung[f] for f in traeger_b[nr] if f in flaechenzuordnung}
        treffer = []
        for i in kandidaten:
            ziel = nummern[i]
            if flaechen and not flaechen.intersection(traeger_a[ziel]):
                continue
            if np.max(abs(box-boxen[ziel])) > eps:
                continue
            gleich = _deckung(a[ziel], k, eps)
            if gleich is not False:
                treffer.append(ziel if gleich else None)
        if len(treffer) == 1:
            rechts[nr] = treffer[0]
        elif not treffer:
            rechts[nr] = -nr
    belegt = defaultdict(list)
    for nr, ziel in rechts.items():
        if ziel is not None and ziel > 0:
            belegt[ziel].append(nr)
    for partner in belegt.values():
        if len(partner) > 1:
            rechts.update(dict.fromkeys(partner))
    return links, rechts
