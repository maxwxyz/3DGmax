"""Lineares Starrkoerpermodell gemeinsamer Bezuege fuer die Baugruppenstreuung.

Koaxiale Lager werden an ihren Sitzmitten abgestuetzt. Koplanare Auflagen tragen
gemaess ihrer Flaeche und ihrem Flaechentraegheitsmoment zur Ausgleichsebene bei.
"""

import numpy as np

from .verbindung import _senkrechte


def _kreuz(v):
    """Matrix der Abbildung w -> v x w."""
    return np.cross(v, np.eye(3)).T


def _lager(elemente, mitte, d, punkt):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder

    stationen, intervalle = [], []
    for _, form, (_, o, achse, laenge) in elemente:
        if BRepAdaptor_Surface(form).GetType() != GeomAbs_Cylinder or laenge <= 1e-7:
            return None
        if np.linalg.norm(np.cross(achse, d)) > 1e-8 or np.linalg.norm(np.cross(o - mitte, d)) > 1e-6:
            return None
        t = (o - mitte) @ d
        stationen.append(t)
        intervalle.append((t - laenge / 2, t + laenge / 2))
    intervalle.sort()
    if any(b[0] < a[1] - 1e-7 for a, b in zip(intervalle, intervalle[1:])):
        return None
    quadratsumme = np.dot(stationen, stationen)
    if quadratsumme <= 1e-14:
        return None
    radial = np.eye(3) - np.outer(d, d)
    abbildungen = {}
    for (idx, _, (_, o, _, _)), t in zip(elemente, stationen, strict=True):
        # Ausgleichsgerade durch die radial verschobenen Sitzmitten, je Sitz gleiches Gewicht.
        kippung = _kreuz(d) * (t / quadratsumme)
        versatz = radial / len(elemente) - _kreuz(punkt - mitte) @ kippung
        sitzbewegung = np.c_[-_kreuz(o - punkt), np.eye(3)]
        abbildungen[idx] = np.vstack((kippung, versatz)) @ sitzbewegung
    return abbildungen


def _auflagen(elemente, mitte, d, punkt, lage):
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.gp import gp_Pnt

    tangenten = np.asarray(_senkrechte(d))
    gewichte = {}
    for idx, form, (_, o, normale, _) in elemente:
        if np.linalg.norm(normale - d) > 1e-8 or abs((o - mitte) @ d) > 1e-6:
            return None
        lokal = lage[:3, :3].T @ (o - lage[:3, 3])
        props = GProp_GProps(gp_Pnt(*lokal))
        brepgprop.SurfaceProperties(form, props)
        flaeche = props.Mass()
        if flaeche <= 1e-14:
            return None
        m = props.MatrixOfInertia()
        traegheit = np.array([[m.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
        zentral = np.trace(traegheit) / 2 * np.eye(3) - traegheit
        lokalachsen = tangenten @ lage[:3, :3]
        schwerpunkt = np.r_[1., tangenten @ (o - mitte)]
        gewicht = flaeche * np.outer(schwerpunkt, schwerpunkt)
        gewicht[1:, 1:] += lokalachsen @ zentral @ lokalachsen.T
        gewichte[idx] = gewicht
    # Die Ebene minimiert das Flaechenintegral des quadrierten Hoehenfehlers ueber alle Auflagen.
    # Koeffizienten sind Hoehe in der Mitte und zwei Neigungen in den Tangentenrichtungen.
    neigung = np.cross(tangenten, d)
    hoehenfeld = np.vstack((np.r_[np.cross(mitte - punkt, d), d], np.c_[neigung, np.zeros((2, 3))]))
    kippung = np.column_stack((np.zeros(3), neigung.T))
    versatz = np.column_stack((d, np.zeros((3, 2)))) - _kreuz(punkt - mitte) @ kippung
    bewegung = np.vstack((kippung, versatz))
    gram = sum(gewichte.values())
    try:
        return {idx: bewegung @ np.linalg.solve(gram, gewicht) @ hoehenfeld for idx, gewicht in gewichte.items()}
    except np.linalg.LinAlgError:
        return None


def aufloesen(elemente, punkt, lage):
    """Virtuelles Merkmal und Abbildungen der einzelnen Flaechentorsoren zum gemeinsamen Bezug."""
    art, _, d, _ = elemente[0][2]
    if any(g[0] != art for _, _, g in elemente):
        return None
    mitte = np.mean([g[1] for _, _, g in elemente], axis=0)
    if art == "achse":
        anteile = _lager(elemente, mitte, d, punkt)
    else:
        anteile = _auflagen(elemente, mitte, d, punkt, lage)
    if anteile is not None:
        return (art, mitte, d, 0.), anteile
    return None
