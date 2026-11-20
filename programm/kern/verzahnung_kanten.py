"""Explizite Fussrundungen und gerade Kopfkantenbrueche eines Stirnrads aus den B-Rep-Flaechen."""

from __future__ import annotations

import math

import numpy as np


def _lage(p, basis, mitte):
    return (np.array(p.Coord()) - mitte) @ basis


def _auf_kontur(p, r, tol):
    winkel = math.atan2(p[1], p[0])
    s = ((winkel + math.pi) / (2 * math.pi) * len(r)) % len(r)
    i = int(s)
    # Am Uebergang Flanke/Fuss kann ein Winkelschritt mehrere Hundertstel in r ueberbruecken.
    r0, r1 = r[i], r[(i + 1) % len(r)]
    return min(r0, r1) - tol <= math.hypot(*p[:2]) <= max(r0, r1) + tol


def _kreis(s, v, basis, hoehe, tol):
    """Kreisbogen in der Fusszone, tangential zum Fusskreis und auf der gemessenen Stirnkontur."""
    zyl = s.Cylinder()
    richtung = np.array(zyl.Axis().Direction().Coord())
    rho = zyl.Radius()
    if abs(richtung @ v.richtung) < 0.999999 or not tol < rho < 2 * hoehe:
        return None
    zentrum = _lage(zyl.Location(), basis, v.punkt)
    orbital = math.hypot(*zentrum[:2])
    if abs(orbital + (rho if v.innen else -rho) - v.df / 2) > tol:
        return None
    tief = -zentrum[2] / (richtung @ v.richtung)
    if not s.FirstVParameter() - tol <= tief <= s.LastVParameter() + tol:
        return None
    u0, u1 = s.FirstUParameter(), s.LastUParameter()
    if not math.radians(8) < u1 - u0 < math.pi + 1e-5:
        return None
    punkte = [_lage(s.Value(u, tief), basis, v.punkt) for u in np.linspace(u0, u1, 7)]
    if not all(_auf_kontur(p, v.r_mitte, tol) for p in punkte):
        return None
    return math.atan2(zentrum[1], zentrum[0]), rho


def _fase(s, f, v, basis, hoehe, tol):
    """Gerade Kante im Stirnschnitt: vom Kopf in die Flanke, mit Abtrag gegen die ideale Evolvente."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopAbs import TopAbs_VERTEX
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    normale = np.array(s.Plane().Axis().Direction().Coord())
    if abs(normale @ v.richtung) > 1e-6:
        return None
    # Flaechen der Evolventenfacetten liegen meist weit unter dem Kopfkreis.
    q = _lage(s.Value((s.FirstUParameter() + s.LastUParameter()) / 2,
                      (s.FirstVParameter() + s.LastVParameter()) / 2), basis, v.punkt)
    if abs(math.hypot(*q[:2]) - v.da / 2) > 0.45 * hoehe:
        return None
    ex = TopExp_Explorer(f, TopAbs_VERTEX)
    ecken = []
    while ex.More():
        ecken.append(_lage(BRep_Tool.Pnt(topods.Vertex(ex.Current())), basis, v.punkt))
        ex.Next()
    if not ecken:
        return None
    punkte = np.asarray(ecken)
    if punkte[:, 2].min() >= -tol or punkte[:, 2].max() <= tol:
        return None
    rad = np.hypot(punkte[:, 0], punkte[:, 1])
    i = int(rad.argmin() if v.innen else rad.argmax())
    j = int(rad.argmax() if v.innen else rad.argmin())
    tip, start = punkte[i, :2], punkte[j, :2]
    tiefe = abs(rad[i] - rad[j])
    if abs(rad[i] - v.da / 2) > tol or not 0.02 * hoehe < tiefe < 0.4 * hoehe:
        return None
    if not all(_auf_kontur(p, v.r_mitte, tol) for p in (tip, start, (tip + start) / 2)):
        return None
    if min(rad[i], rad[j]) <= v.db / 2:
        return None
    return tip, start, float(tiefe)


def _zahnlage(winkel, null, teilung, z):
    nr = round((winkel - null) / teilung)
    return nr % z, winkel - null - nr * teilung


def _evolventenwinkel(db, punkt):
    a = math.acos(db / (2 * math.hypot(*punkt)))
    return math.tan(a) - a


def _gleichmaessig(gruppen, z, teilung, tol, beidseitig):
    """Gleiche Werte und gespiegelte Winkel an allen Zaehnen (geteilte Flaechen zusammenfassen)."""
    if len(gruppen) != z:
        return None
    werte, muster = [], None
    for treffer in gruppen.values():
        lagen = sorted({round(w / teilung, 3) for w, _ in treffer})
        if len(lagen) > 2 or (beidseitig and len(lagen) != 2) or abs(lagen[0] + lagen[-1]) > 0.01:
            return None
        if muster is not None and (len(lagen) != len(muster) or not np.allclose(lagen, muster, atol=0.01)):
            return None
        if muster is None:
            muster = lagen
        werte.extend(wert for _, wert in treffer)
    return float(np.mean(werte)) if np.ptp(werte) <= tol else None


def erkenne(form, v, u, w):
    """(Fussradius, radiale Kopf-Fasenhoehe) aus wiederholten B-Rep-Merkmalen; sonst None."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    if v.beta or v.db <= 0 or v.r_mitte is None:
        return None, None
    basis = np.column_stack((u, w, v.richtung))
    h = abs(v.da - v.df) / 2
    tol = max(1e-5, h * 0.003, math.pi * max(v.da, v.df) / len(v.r_mitte) * 0.25)
    teilung = 2 * math.pi / v.z
    phase = np.angle(np.fft.rfft(v.r_mitte)[v.z])
    zahnmitte = -math.pi - phase / v.z + (teilung / 2 if v.innen else 0.0)
    kreise, fasen = {}, {}
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        if BRep_Tool.Surface(f) is None:
            continue
        sf = BRepAdaptor_Surface(f, True)
        if sf.GetType() == GeomAbs_Cylinder:
            kreis = _kreis(sf, v, basis, h, tol)
            if kreis is not None:
                angle, rho = kreis
                nr, winkel = _zahnlage(angle, zahnmitte + teilung / 2, teilung, v.z)
                kreise.setdefault(nr, []).append((winkel, rho))
        if sf.GetType() == GeomAbs_Plane:
            fase = _fase(sf, f, v, basis, h, tol)
            if fase is None:
                continue
            tip, start, tiefe = fase
            nr, wt = _zahnlage(math.atan2(tip[1], tip[0]), zahnmitte, teilung, v.z)
            nr0, ws = _zahnlage(math.atan2(start[1], start[0]), zahnmitte, teilung, v.z)
            if nr != nr0 or wt * ws <= 0:
                continue
            differenz = _evolventenwinkel(v.db, tip) - _evolventenwinkel(v.db, start)
            soll = abs(ws) + (differenz if v.innen else -differenz)
            abtrag = (soll - abs(wt)) * v.da / 2
            if abtrag > max(tol, tiefe * math.tan(math.radians(8))):
                fasen.setdefault(nr, []).append((wt, tiefe))
    return (_gleichmaessig(kreise, v.z, teilung, tol, False),
            _gleichmaessig(fasen, v.z, teilung, tol, True))
