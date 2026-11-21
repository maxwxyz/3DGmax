"""Kantenzusammenhaengende Koerper und Achslage aus importierten Dreiecken fuer die Verzahnungsanalyse."""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def koerper(form):
    """B-Rep-Volumen und lose Netzkoerper desselben Baumblatts in ihrer Einbaulage."""
    return [k for k, _ in koerpergruppen(form)]


def koerpergruppen(form, ohne_profil=None):
    """Je Koerper seine Netz-Quellflaechen; am B-Rep sind die Flaechen direkt abfragbar."""
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import TopoDS_Compound, topods
    teile = []
    ex = TopExp_Explorer(form, TopAbs_SOLID)
    while ex.More():
        teile.append((ex.Current(), None))
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
            return [(form, None)]
        b = BRep_Builder()
        c = TopoDS_Compound()
        b.MakeCompound(c)
        for f in frei:
            b.Add(c, f)
        teile.append((c, None))
    if netz:
        teile.extend(_netzgruppen(netz, ohne_profil))
    return teile


def komponenten(flaechen):
    """Identische Nahtknoten verschweissen. Nur Kanten mit genau zwei Facetten verbinden Koerper."""
    return [t for t, _ in _netzgruppen(flaechen)]


def _netzgruppen(flaechen, ohne_profil=None):
    from .ausrichten import tesselliere
    netze = tesselliere(flaechen)
    if not any(len(ix) for _, ix in netze):
        return []
    offset = np.cumsum([0] + [len(p) for p, _ in netze[:-1]])
    p, knoten = np.unique(np.vstack([p for p, _ in netze]), axis=0, return_inverse=True)
    ix = knoten[np.vstack([i + start for (_, i), start in zip(netze, offset)])]
    gueltig = (ix[:, 0] != ix[:, 1]) & (ix[:, 1] != ix[:, 2]) & (ix[:, 2] != ix[:, 0])
    enden = np.cumsum([len(t) for _, t in netze])
    original = np.flatnonzero(gueltig & np.isfinite(p).all(axis=1)[ix].all(axis=1))
    ix = ix[original]
    kantenvektor = np.cross(p[ix[:, 1]] - p[ix[:, 0]], p[ix[:, 2]] - p[ix[:, 0]])
    regulaer = np.any(kantenvektor != 0, axis=1)
    ix, original = ix[regulaer], original[regulaer]
    if not len(ix):
        return []
    kanten = np.sort(ix[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    folge = np.lexsort((kanten[:, 1], kanten[:, 0]))
    gleich = np.all(np.diff(kanten[folge], axis=0) == 0, axis=1)
    paar = gleich & ~np.r_[False, gleich[:-1]] & ~np.r_[gleich[1:], False]
    a, b = folge[:-1][paar] // 3, folge[1:][paar] // 3
    graph = coo_matrix((np.ones(len(a), dtype=bool), (a, b)), shape=(len(ix), len(ix)))
    _, gruppe = connected_components(graph, directed=False)
    if ohne_profil is not None:
        # Eine Quellflaeche kann zugleich Dreiecke eines zu kleinen Nebenkoerpers enthalten.
        klein = np.bincount(gruppe)[gruppe] < 8
        fehlend = np.unique(enden.searchsorted(original[klein], side="right"))
        ohne_profil.update(flaechen[i] for i in fehlend)
    folge = np.argsort(gruppe, kind="stable")
    out = []
    for g in np.split(folge, np.flatnonzero(np.diff(gruppe[folge])) + 1):
        if len(g) >= 8:
            quellen = flaechen
            if len(flaechen) > 1:
                ids = np.unique(enden.searchsorted(original[g], side="right"))
                quellen = [flaechen[i] for i in ids]
            out.append((p[ix[g]], quellen))
    return out


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
