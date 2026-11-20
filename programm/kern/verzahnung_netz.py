"""Kantenzusammenhaengende Koerper und Achslage aus importierten Dreiecken fuer die Verzahnungsanalyse."""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def koerper(form):
    """B-Rep-Volumen und lose Netzflaechen desselben Baumblatts in ihrer Einbaulage."""
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import TopoDS_Compound, topods
    teile = []
    ex = TopExp_Explorer(form, TopAbs_SOLID)
    while ex.More():
        teile.append(ex.Current())
        ex.Next()
    netz, frei = [], []
    ex = TopExp_Explorer(form, TopAbs_FACE, TopAbs_SOLID)
    while ex.More():
        f = topods.Face(ex.Current())
        if BRep_Tool.Surface(f) is None:
            netz.append(f)
        else:
            frei.append(f)
        ex.Next()
    if frei:
        if not teile and not netz:
            return [form]
        b = BRep_Builder()
        c = TopoDS_Compound()
        b.MakeCompound(c)
        for f in frei:
            b.Add(c, f)
        teile.append(c)
    if netz:
        teile.extend(komponenten(netz))
    return teile


def komponenten(flaechen):
    """Identische Nahtknoten verschweissen. Nur Kanten mit genau zwei Facetten verbinden Koerper."""
    from .ausrichten import tesselliere
    netze = [(p, ix) for p, ix in tesselliere(flaechen) if len(ix)]
    if not netze:
        return []
    offset = np.cumsum([0] + [len(p) for p, _ in netze[:-1]])
    p, knoten = np.unique(np.vstack([p for p, _ in netze]), axis=0, return_inverse=True)
    ix = knoten[np.vstack([i + start for (_, i), start in zip(netze, offset)])]
    gueltig = (ix[:, 0] != ix[:, 1]) & (ix[:, 1] != ix[:, 2]) & (ix[:, 2] != ix[:, 0])
    ix = ix[gueltig & np.isfinite(p).all(axis=1)[ix].all(axis=1)]
    kantenvektor = np.cross(p[ix[:, 1]] - p[ix[:, 0]], p[ix[:, 2]] - p[ix[:, 0]])
    ix = ix[np.any(kantenvektor != 0, axis=1)]
    if not len(ix):
        return []
    kanten = np.sort(ix[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    folge = np.lexsort((kanten[:, 1], kanten[:, 0]))
    gleich = np.all(np.diff(kanten[folge], axis=0) == 0, axis=1)
    paar = gleich & ~np.r_[False, gleich[:-1]] & ~np.r_[gleich[1:], False]
    a, b = folge[:-1][paar] // 3, folge[1:][paar] // 3
    graph = coo_matrix((np.ones(len(a), dtype=bool), (a, b)), shape=(len(ix), len(ix)))
    _, gruppe = connected_components(graph, directed=False)
    folge = np.argsort(gruppe, kind="stable")
    return [p[ix[g]] for g in np.split(folge, np.flatnonzero(np.diff(gruppe[folge])) + 1) if len(g) >= 8]


def achse(t):
    """Flaechengewichtete Hauptachse aus exakten Dreiecksmomenten, unabhaengig von der Facettengroesse."""
    normal = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    flaeche = np.linalg.norm(normal, axis=1)
    gewicht = flaeche / flaeche.sum()
    mitte = np.average(t.mean(axis=1), weights=gewicht, axis=0)
    rel = t - mitte
    sums = rel.sum(axis=1)
    moment = sums.T @ (gewicht[:, None] * sums)
    for i in range(3):
        moment += rel[:, i].T @ (gewicht[:, None] * rel[:, i])
    w, v = np.linalg.eigh(moment)
    n = v[:, 0] if w[1] - w[0] > w[2] - w[1] else v[:, 2]
    # Bei einzelnen Schraubgaengen kann die Hauptachse leicht kippen. Zwei grosse parallele
    # ebene Abschluesse an beiden Enden bestaetigen die Richtung unabhaengig von der Zahnteilung.
    parallel = abs(normal @ n) > .996 * flaeche
    if parallel.any():
        i = np.argmax(np.where(parallel, flaeche, 0))
        stirn = normal[i] / flaeche[i]
        axial = rel @ stirn
        eben = abs(normal @ stirn) > (1 - 1e-7) * flaeche
        grenze = max(np.ptp(axial) * 1e-5, 1e-7)
        unten = eben & (axial.max(axis=1) < axial.min() + grenze)
        oben = eben & (axial.min(axis=1) > axial.max() - grenze)
        if min(flaeche[unten].sum(), flaeche[oben].sum()) > .01 * flaeche.sum():
            n = stirn
    return mitte, n
